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

import { setSessionLostHandler, tokens } from "@/api/client";
import { getMe, logout as logoutRequest } from "@/api/endpoints";
import type { AuthResponse, User } from "@/api/types";

interface SessionState {
  user: User | null;
  loading: boolean;
  isAdmin: boolean;
  signIn: (response: AuthResponse) => void;
  signOut: () => Promise<void>;
}

const SessionContext = createContext<SessionState>({
  user: null,
  loading: true,
  isAdmin: false,
  signIn: () => undefined,
  signOut: async () => undefined,
});

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!tokens.access()) {
      setLoading(false);
      return;
    }
    getMe()
      .then(setUser)
      .catch(() => {
        tokens.clear();
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const signIn = useCallback((response: AuthResponse) => {
    tokens.save(response.tokens);
    setUser(response.user);
  }, []);

  const signOut = useCallback(async () => {
    const refresh = tokens.refresh();
    if (refresh) await logoutRequest(refresh).catch(() => undefined);
    tokens.clear();
    setUser(null);
  }, []);

  // سقوطُ التجديد يعني جلسةً انتهت — تُمسح ويعود الدخول بلا رسالة عطل
  useEffect(() => {
    setSessionLostHandler(() => {
      tokens.clear();
      setUser(null);
    });
  }, []);

  const value = useMemo<SessionState>(
    () => ({
      user,
      loading,
      isAdmin: user?.role === "admin",
      signIn,
      signOut,
    }),
    [user, loading, signIn, signOut],
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession() {
  return useContext(SessionContext);
}
