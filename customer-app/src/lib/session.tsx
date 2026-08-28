/** الجلسة: من المستخدم، وكيف يدخل ويخرج، ومتى يُسجَّل جهازه.
 *
 * ثلاث قواعد من SPEC القسم 10/11.8 تسكن هنا لأنها **عقدٌ يلتزم به التطبيق**
 * لا شاشةٌ تُرسم:
 *
 * - بعد الدخول (وكلما دار رمز FCM): `PUT /me/devices`.
 * - عند الخروج: `DELETE /me/devices/{device_id}` **قبل** إبطال الجلسة —
 *   رمزٌ لحسابٍ غادر الهاتف يوصل إشعاراته إلى من يحمله بعده.
 * - المقبس يُفتح بنفس `device_id` (انظر `lib/socket.ts`).
 */

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
  refreshNow,
  setRefreshPersister,
  setSessionLostHandler,
  tokens,
} from "@/api/client";
import {
  biometryStatus,
  disableBiometric,
  enableBiometric,
  forgetToken,
  proveBiometry,
  rememberToken,
  unlockToken,
  type BiometryStatus,
} from "@/lib/biometric";
import {
  getMe,
  logout as logoutRequest,
  registerDevice,
  unregisterDevice,
} from "@/api/endpoints";
import type { AuthResponse, User } from "@/api/types";
import { firebaseConfigOf, useConfig } from "@/lib/config";
import { deviceId, platform } from "@/lib/device";
import { requestPushToken } from "@/lib/firebase";

interface SessionState {
  user: User | null;
  loading: boolean;
  signIn: (response: AuthResponse) => void;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
  /** حالُ الدخول بالبصمة — **تُقاس ولا تُفترض**، و`null` «لم تُقرأ بعد». */
  biometry: BiometryStatus | null;
  refreshBiometry: () => Promise<void>;
  setBiometric: (on: boolean) => Promise<void>;
  signInWithBiometry: () => Promise<void>;
}

const SessionContext = createContext<SessionState>({
  user: null,
  loading: true,
  signIn: () => undefined,
  signOut: async () => undefined,
  refreshUser: async () => undefined,
  biometry: null,
  refreshBiometry: async () => undefined,
  setBiometric: async () => undefined,
  signInWithBiometry: async () => undefined,
});

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const { config } = useConfig();
  const registered = useRef(false);
  const [biometry, setBiometry] = useState<BiometryStatus | null>(null);

  // انتهاء الجلسة يقع في عمق عميل HTTP؛ هذا ما يترجمه إلى «عد لشاشة الدخول»
  useEffect(() => {
    setSessionLostHandler(() => {
      setUser(null);
      // **الثالثةُ من الأربع**: ردُّ الخادم بأن الجلسة لم تعد صالحة يمحو المخزَّن
      void forgetToken().then(() => biometryStatus().then(setBiometry));
    });
  }, []);

  useEffect(() => {
    if (!tokens.access()) {
      setLoading(false);
      return;
    }
    getMe()
      .then(setUser)
      .catch(() => tokens.clear())
      .finally(() => setLoading(false));
  }, []);

  /** تسجيل الجهاز بعد الدخول — يُبتلع فشلُه: إشعاراتٌ لا تصل أهون من دخولٍ
   * لا يكتمل (SPEC القسم 10: «الفشل يُبتلع ويُسجَّل»). */
  useEffect(() => {
    if (!user || registered.current) return;
    const fcm = firebaseConfigOf(config?.providers.fcm);
    const vapid = config?.providers.fcm?.vapid_key;
    if (!fcm || !vapid) return;

    registered.current = true;
    requestPushToken(fcm, vapid)
      .then((token) =>
        token
          ? registerDevice({ device_id: deviceId(), token, platform: platform() })
          : null,
      )
      .catch((error) => console.warn("تعذّر تسجيل الجهاز للإشعارات", error));
  }, [user, config]);

  const refreshBiometry = useCallback(async () => {
    setBiometry(await biometryStatus());
  }, []);

  useEffect(() => {
    void refreshBiometry();
  }, [refreshBiometry]);

  /** **الرمزُ المخزَّنُ يتبع التدوير** — يُكتب بعد كلِّ `tokens.save`. */
  useEffect(() => {
    setRefreshPersister((token) => {
      void rememberToken(token);
    });
  }, []);

  const signIn = useCallback(
    (response: AuthResponse) => {
      tokens.save(response.tokens);
      setUser(response.user);
      void refreshBiometry();
    },
    [refreshBiometry],
  );

  /** **الرابعةُ من الأربع** — الإطفاءُ من الإعدادات يمحو ويطفئ معاً. */
  const setBiometric = useCallback(
    async (on: boolean) => {
      if (on) {
        await proveBiometry("لتفعيل الدخول بالبصمة");
        await enableBiometric(tokens.refresh());
        tokens.detachFromLocalStorage();
      } else {
        await disableBiometric();
      }
      await refreshBiometry();
    },
    [refreshBiometry],
  );

  /** **الفتحُ ثم التجديد** — والخلفيةُ لا ترى إلا رمزاً كأيِّ رمز. */
  const signInWithBiometry = useCallback(async () => {
    const token = await unlockToken("لتسجيل الدخول إلى TAXO");
    tokens.adoptRefresh(token);
    const ok = await refreshNow();
    if (!ok) {
      await forgetToken();
      await refreshBiometry();
      throw new Error("انتهت الجلسة المحفوظة — سجّل الدخول بكلمة المرور");
    }
    setUser(await getMe());
    await refreshBiometry();
  }, [refreshBiometry]);

  const signOut = useCallback(async () => {
    const refresh = tokens.refresh();
    // الترتيب مقصود: يُحذف الجهاز والتوكن ما زال صالحاً
    await unregisterDevice(deviceId()).catch(() => undefined);
    if (refresh) await logoutRequest(refresh).catch(() => undefined);
    tokens.clear();
    // **الأولى من الأربع**: الخروجُ يمحو المخزَّن، والتفضيلُ يبقى
    await forgetToken();
    registered.current = false;
    setUser(null);
    await refreshBiometry();
  }, [refreshBiometry]);

  const refreshUser = useCallback(async () => {
    setUser(await getMe());
  }, []);

  const value = useMemo<SessionState>(
    () => ({
      user,
      loading,
      signIn,
      signOut,
      refreshUser,
      biometry,
      refreshBiometry,
      setBiometric,
      signInWithBiometry,
    }),
    [
      user,
      loading,
      signIn,
      signOut,
      refreshUser,
      biometry,
      refreshBiometry,
      setBiometric,
      signInWithBiometry,
    ],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  return useContext(SessionContext);
}
