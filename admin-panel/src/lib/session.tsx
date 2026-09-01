/** الجلسة: من المستخدم، وكيف يدخل ويخرج، وما يملك أن يفعله.
 *
 * **وتسجيلُ الجهاز هنا منذ 2026-09-01 — على الغلاف الأصليِّ وحدَه.** وكان
 * مكتوباً هنا أن اللوحة «لا تستقبل إشعارات Push: لا بطاقةَ طلبٍ تنتظرها ولا
 * رحلةً تتابعها» — **وكان صحيحاً يومَ كُتب**. وما نقضه ليس رأياً بل بابٌ
 * بُني: `POST /payments/cliq/{cart}/declare`، **فصار للوحة حدثٌ ينتظره
 * إنسان** — كبتنٌ حوّل مالاً من حسابه، **والصمتُ عنده يُقرأ «لم يصل»**.
 *
 * **وفي المتصفح لا يقع شيء**: `registerNativePush` يردّ `unsupported` بلا
 * نداءٍ ولا خطأ — فلا رمزَ لجهازٍ مكتبيٍّ يُسجَّل، وذلك بعينه ما كان يُقال.
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

import { Capacitor } from "@capacitor/core";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";

import {
  setEnrollmentRequiredHandler,
  setSessionLostHandler,
  tokens,
} from "@/api/client";
import {
  getMe,
  getMyTotp,
  logout as logoutRequest,
  registerDevice,
  unregisterDevice,
} from "@/api/endpoints";
import type { AuthResponse, TotpStatus, User } from "@/api/types";
import { deviceId, platform } from "@/lib/device";
import { useIdleLogout } from "@/lib/idle";
import { registerNativePush, type PushState } from "@/lib/push";

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
  /** حالُ إذن الإشعارات على الغلاف — `null` في المتصفح وقبل أن يُسأل. */
  pushState: PushState | null;
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
  pushState: null,
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
  const [pushState, setPushState] = useState<PushState | null>(null);
  const registered = useRef(false);

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

  /** تسجيلُ الجهاز بعد الدخول — **ويُبتلع فشلُه**: إشعاراتٌ لا تصل أهون من
   * دخولٍ لا يكتمل (SPEC القسم 10: «الفشل يُبتلع ويُسجَّل»).
   *
   * **وبعد أن يُعرف المستخدمُ لا عند الإقلاع**: طلبُ الإذن على شاشة دخولٍ
   * يُرفض ثمّ لا يُسأل ثانية.
   */
  useEffect(() => {
    if (!user || registered.current) return;
    if (!Capacitor.isNativePlatform()) return;
    registered.current = true;

    void (async () => {
      try {
        const outcome = await registerNativePush();
        setPushState(outcome.state);
        if (outcome.token) {
          await registerDevice({
            device_id: deviceId(),
            token: outcome.token,
            platform: platform(),
          });
        }
      } catch (error) {
        console.warn("تعذّر تسجيل الجهاز للإشعارات", error);
      }
    })();
  }, [user]);

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
    // **الترتيبُ مقصود**: يُحذف الجهازُ والرمزُ ما زال صالحاً — ومن خرج ثمّ
    // بقي رمزُه مسجَّلاً يستقبل إشعاراتِ لوحةٍ لم يعد فيها
    if (Capacitor.isNativePlatform()) {
      await unregisterDevice(deviceId()).catch(() => undefined);
    }
    if (refresh) await logoutRequest(refresh).catch(() => undefined);
    tokens.clear();
    setUser(null);
    setFactor(null);
    setEnrollmentRequired(false);
    setLastReason(reason);
    registered.current = false;
    setPushState(null);
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
      pushState,
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
      pushState,
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
