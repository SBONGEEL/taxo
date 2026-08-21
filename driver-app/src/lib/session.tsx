/** الجلسة: من الكبتن، وكيف يدخل ويخرج، ومتى يُسجَّل جهازه.
 *
 * ثلاث قواعد من SPEC القسم 10/12.8 تسكن هنا لأنها **عقدٌ يلتزم به التطبيق**
 * لا شاشةٌ تُرسم — و«أشدُّ إلزاماً» هنا منها في تطبيق الراكب: بطاقةُ الطلب
 * مهلتُها عشرون ثانية، فجهازٌ لم يسجّل رمزه لا تصله طلبات والتطبيق مغلق،
 * ويبدو للكبتن كأن لا رحلات في المنطقة:
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

import { Capacitor } from "@capacitor/core";

import { setSessionLostHandler, tokens } from "@/api/client";
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
import { registerNativePush, type PushState } from "@/lib/push";

interface SessionState {
  user: User | null;
  loading: boolean;
  signIn: (response: AuthResponse) => void;
  signOut: () => Promise<void>;
  refreshUser: () => Promise<void>;
  /** حالُ إذن الإشعارات — **تُنشر ليقولها `Home` للكبتن** (شرطُ المالك):
   *  من رفض الإذن لا تصله طلباتٌ وهو خارج التطبيق، فلا يظنّ نفسه عاملاً.
   *  و`null` تعني «لم يُسأل بعد» — فلا سطرَ قبل أن يُعرف الجواب. */
  pushState: PushState | null;
}

const SessionContext = createContext<SessionState>({
  user: null,
  loading: true,
  signIn: () => undefined,
  signOut: async () => undefined,
  refreshUser: async () => undefined,
  pushState: null,
});

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const { config } = useConfig();
  const registered = useRef(false);
  const [pushState, setPushState] = useState<PushState | null>(null);

  // انتهاء الجلسة يقع في عمق عميل HTTP؛ هذا ما يترجمه إلى «عد لشاشة الدخول»
  useEffect(() => {
    setSessionLostHandler(() => setUser(null));
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
   * لا يكتمل (SPEC القسم 10: «الفشل يُبتلع ويُسجَّل»).
   *
   * **ومسارانِ لا مسار** (2026-08-21): على الجهاز **المسارُ الأصليّ**، وفي
   * المتصفح مسارُ الويب كما كان. **والسببُ مقيسٌ لا مُفضَّل**: `Notification`
   * و`PushManager` **غائبان في WebView أندرويد**، فمسارُ الويب هناك يردّ
   * `null` قبل أن يبدأ — **وهو ما جعل `device_tokens` صفراً منذ نشأتها**.
   *
   * **ورفضُ الإذن حالٌ تُحفظ لا تُبتلع**: منها يرسم `Home` سطرَه للكبتن.
   */
  useEffect(() => {
    if (!user || registered.current) return;
    registered.current = true;

    void (async () => {
      try {
        if (Capacitor.isNativePlatform()) {
          const outcome = await registerNativePush();
          setPushState(outcome.state);
          if (outcome.token) {
            await registerDevice({
              device_id: deviceId(),
              token: outcome.token,
              platform: platform(),
            });
          }
          return;
        }

        const fcm = firebaseConfigOf(config?.providers.fcm);
        const vapid = config?.providers.fcm?.vapid_key;
        if (!fcm || !vapid) return;
        const token = await requestPushToken(fcm, vapid);
        if (token) {
          await registerDevice({
            device_id: deviceId(),
            token,
            platform: platform(),
          });
        }
      } catch (error) {
        console.warn("تعذّر تسجيل الجهاز للإشعارات", error);
      }
    })();
  }, [user, config]);

  const signIn = useCallback((response: AuthResponse) => {
    tokens.save(response.tokens);
    setUser(response.user);
  }, []);

  const signOut = useCallback(async () => {
    const refresh = tokens.refresh();
    // الترتيب مقصود: يُحذف الجهاز والتوكن ما زال صالحاً
    await unregisterDevice(deviceId()).catch(() => undefined);
    if (refresh) await logoutRequest(refresh).catch(() => undefined);
    tokens.clear();
    registered.current = false;
    setPushState(null);
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    setUser(await getMe());
  }, []);

  const value = useMemo<SessionState>(
    () => ({ user, loading, signIn, signOut, refreshUser, pushState }),
    [user, loading, signIn, signOut, refreshUser, pushState],
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession() {
  return useContext(SessionContext);
}
