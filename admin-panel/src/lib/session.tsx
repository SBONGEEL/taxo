/** الجلسة: من المستخدم، وكيف يدخل ويخرج، وما يملك أن يفعله.
 *
 * **ولا تسجيلَ جهازٍ هنا** خلافاً للتطبيقين: اللوحة لا تستقبل إشعارات Push —
 * لا بطاقةَ طلبٍ تنتظرها ولا رحلةً تتابعها، وتسجيلُ رمزٍ لجهازٍ مكتبيّ يفتح
 * باباً بلا مستفيد.
 *
 * **والدور يُقرأ من الخلفية لا من الشاشة**: `admin` كاملٌ و`support` قراءةٌ
 * ومعالجةُ نزاعات (SPEC القسم 13/8). وما تخفيه الواجهة عن `support` تخفيه
 * **راحةً لا حماية** — الحماية في الخلفية على كل مسار، وإخفاءُ زرٍّ لا يمنع
 * نداءً. ولذلك `isAdmin` هنا يرسم الواجهة ولا يُستعمل حارساً لشيء.
 *
 * **وثلاثةٌ من المرحلة 12-د تسكن هنا** لأنها تخصّ الجلسة نفسها لا شاشةً:
 *
 * 1. **حالةُ العامل الثاني** (`factor`) تُقرأ مرةً عند الإقلاع: منها مهلةُ
 *    الخمول، ومنها «هل أنا مُلزَمٌ ولم أسجّل».
 * 2. **مؤقّتُ الخمول** — على نشاط الإنسان لا على النداءات (`lib/idle.ts`).
 * 3. **بوابةُ الإلزام**: `totp_enrollment_required` قد يرتدّ من أيّ نداء، فيُرفع
 *    علمٌ واحد يقود إلى شاشة الأمان بدل أن تترجمه كلُّ شاشة بخطأٍ أحمر.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";

import {
  setEnrollmentRequiredHandler,
  setSessionLostHandler,
  tokens,
} from "@/api/client";
import { getMe, getMyTotp, logout as logoutRequest } from "@/api/endpoints";
import type { AuthResponse, TotpStatus, User } from "@/api/types";
import { useIdleLogout } from "@/lib/idle";

/** سببُ آخر خروج — تقرؤه شاشةُ الدخول فتقول ما جرى بدل أن تبدو معطّلة. */
export type SignOutReason = "manual" | "idle" | "expired";

interface SessionState {
  user: User | null;
  loading: boolean;
  isAdmin: boolean;
  /** حالةُ العامل الثاني لصاحب الجلسة — `null` قبل أن تُقرأ. */
  factor: TotpStatus | null;
  /** الخلفيةُ ردّت «سجّل عاملاً أولاً» — كلُّ مسارٍ إداريٍّ مغلقٌ حتى يُسجّل. */
  enrollmentRequired: boolean;
  lastReason: SignOutReason | null;
  signIn: (response: AuthResponse) => void;
  signOut: (reason?: SignOutReason) => Promise<void>;
  refreshFactor: () => Promise<void>;
}

const SessionContext = createContext<SessionState>({
  user: null,
  loading: true,
  isAdmin: false,
  factor: null,
  enrollmentRequired: false,
  lastReason: null,
  signIn: () => undefined,
  signOut: async () => undefined,
  refreshFactor: async () => undefined,
});

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [factor, setFactor] = useState<TotpStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [enrollmentRequired, setEnrollmentRequired] = useState(false);
  const [lastReason, setLastReason] = useState<SignOutReason | null>(null);

  const refreshFactor = useCallback(async () => {
    // **ولا تُسقط الجلسةَ إن تعذّرت**: مهلةُ الخمول وحالةُ العامل معلوماتُ
    // راحةٍ، وخطأٌ عارضٌ فيها لا يستحق إخراج المشرف من عمله
    try {
      setFactor(await getMyTotp());
    } catch {
      setFactor(null);
    }
  }, []);

  useEffect(() => {
    if (!tokens.access()) {
      setLoading(false);
      return;
    }
    getMe()
      .then((me) => {
        setUser(me);
        return refreshFactor();
      })
      .catch(() => {
        tokens.clear();
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, [refreshFactor]);

  const signIn = useCallback(
    (response: AuthResponse) => {
      tokens.save(response.tokens);
      setUser(response.user);
      setEnrollmentRequired(false);
      setLastReason(null);
      void refreshFactor();
    },
    [refreshFactor],
  );

  const signOut = useCallback(async (reason: SignOutReason = "manual") => {
    const refresh = tokens.refresh();
    if (refresh) await logoutRequest(refresh).catch(() => undefined);
    tokens.clear();
    setUser(null);
    setFactor(null);
    setEnrollmentRequired(false);
    setLastReason(reason);
  }, []);

  // سقوطُ التجديد يعني جلسةً انتهت — تُمسح ويعود الدخول بلا رسالة عطل.
  // ومنها **مهلةُ الخمول في الخلفية**: مفتاحُ الـrefresh انتهى عمره، فما يراه
  // المستخدم هنا هو الطبقةُ الأولى تعمل
  useEffect(() => {
    setSessionLostHandler(() => {
      tokens.clear();
      setUser(null);
      setFactor(null);
      setLastReason("expired");
    });
    setEnrollmentRequiredHandler(() => setEnrollmentRequired(true));
  }, []);

  const onIdle = useCallback(() => {
    if (!tokens.access()) return;
    void signOut("idle");
  }, [signOut]);

  useIdleLogout(user ? (factor?.session_idle_timeout_minutes ?? null) : null, onIdle);

  const value = useMemo<SessionState>(
    () => ({
      user,
      loading,
      isAdmin: user?.role === "admin",
      factor,
      enrollmentRequired,
      lastReason,
      signIn,
      signOut,
      refreshFactor,
    }),
    [
      user,
      loading,
      factor,
      enrollmentRequired,
      lastReason,
      signIn,
      signOut,
      refreshFactor,
    ],
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession() {
  return useContext(SessionContext);
}
