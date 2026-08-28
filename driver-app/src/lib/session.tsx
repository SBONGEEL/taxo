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

import {
  refreshNow,
  setRefreshPersister,
  setSessionLostHandler,
  tokens,
} from "@/api/client";
import {
  getMe,
  logout as logoutRequest,
  registerDevice,
  unregisterDevice,
} from "@/api/endpoints";
import type { AuthResponse, User } from "@/api/types";
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
  /** حالُ الدخول بالبصمة — **تُقاس ولا تُفترض**، و`null` تعني «لم تُقرأ بعد».
   *  انظر `lib/biometric.ts` لعلّة البيت الواحد. */
  biometry: BiometryStatus | null;
  /** يُعيد قراءةَ الحال بعد إشعالٍ أو إطفاء. */
  refreshBiometry: () => Promise<void>;
  setBiometric: (on: boolean) => Promise<void>;
  /** **الفتحُ ثم التجديد**: البصمةُ تفتح الرمزَ، والخلفيةُ تراه رمزاً كأيِّ رمز. */
  signInWithBiometry: () => Promise<void>;
}

const SessionContext = createContext<SessionState>({
  user: null,
  loading: true,
  signIn: () => undefined,
  signOut: async () => undefined,
  refreshUser: async () => undefined,
  pushState: null,
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
  const [pushState, setPushState] = useState<PushState | null>(null);
  const [biometry, setBiometry] = useState<BiometryStatus | null>(null);

  const refreshBiometry = useCallback(async () => {
    setBiometry(await biometryStatus());
  }, []);

  useEffect(() => {
    void refreshBiometry();
  }, [refreshBiometry]);

  /** **الرمزُ المخزَّنُ يتبع التدوير** — يُكتب بعد كلِّ `tokens.save`.
   *  ولولا هذا لَعمل الفتحُ مرّةً ثمّ ردَّ «جلسة منتهية» (الشكلُ الثامن). */
  useEffect(() => {
    setRefreshPersister((token) => {
      void rememberToken(token);
    });
  }, []);

  // انتهاء الجلسة يقع في عمق عميل HTTP؛ هذا ما يترجمه إلى «عد لشاشة الدخول»
  //
  // **والثالثةُ من الأربع هنا** (قرارُ المالك): ردُّ الخادم بأن الجلسة لم تعد
  // صالحة **يمحو المخزَّن** — فرمزٌ أبطله الخادمُ لا يُفتح ببصمةٍ إلى الأبد،
  // ولا يُترك ليُقرأ زرّاً يفشل عند الضغط.
  useEffect(() => {
    setSessionLostHandler(() => {
      setUser(null);
      void forgetToken().then(refreshBiometry);
    });
  }, [refreshBiometry]);

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

  const signIn = useCallback(
    (response: AuthResponse) => {
      // `tokens.save` يستدعي الحاقنَ، فيصل الرمزُ إلى المخزن الآمن إن أُشعلت
      // الميزةُ سلفاً — **فمن خرج ثمّ دخل بكلمته يعود زرُّه بلا أن يُشعلها**
      tokens.save(response.tokens);
      setUser(response.user);
      void refreshBiometry();
    },
    [refreshBiometry],
  );

  const signOut = useCallback(async () => {
    const refresh = tokens.refresh();
    // الترتيب مقصود: يُحذف الجهاز والتوكن ما زال صالحاً
    await unregisterDevice(deviceId()).catch(() => undefined);
    if (refresh) await logoutRequest(refresh).catch(() => undefined);
    tokens.clear();
    // **الأولى من الأربع**: الخروجُ يمحو المخزَّن — والتفضيلُ يبقى، فمن
    // أشعلها لا يطفئها خروجُه
    await forgetToken();
    registered.current = false;
    setPushState(null);
    setUser(null);
    await refreshBiometry();
  }, [refreshBiometry]);

  const refreshUser = useCallback(async () => {
    setUser(await getMe());
  }, []);

  /** **الرابعةُ من الأربع** — الإطفاءُ من إعدادات المستخدم يمحو ويطفئ معاً. */
  const setBiometric = useCallback(
    async (on: boolean) => {
      if (on) {
        // **البصمةُ تُطلب عند الإشعال لا عند أوّل استعمال**: من أشعلها بلا
        // إصبعٍ يظنّها تعمل، ثمّ يكتشف يومَ يحتاجها أنها لا تفتح
        await proveBiometry("لتفعيل الدخول بالبصمة");
        await enableBiometric(tokens.refresh());
        // **بيتٌ واحد**: يُنزع من `localStorage` بعد أن يستقرّ في المخزن الآمن
        tokens.detachFromLocalStorage();
      } else {
        await disableBiometric();
      }
      await refreshBiometry();
    },
    [refreshBiometry],
  );

  /** **الفتحُ ثم التجديد** — والخلفيةُ لا ترى إلا رمزاً كأيِّ رمز.
   *
   *  **ولا يُعلَن نجاحٌ قبل أن يُرى المستخدم**: `getMe` بعد التجديد هو ما
   *  يقول إن الجلسةَ قامت — و«فُتح المخزن» ليس «دخلتَ».
   */
  const signInWithBiometry = useCallback(async () => {
    const token = await unlockToken("لتسجيل الدخول إلى TAXO");
    tokens.adoptRefresh(token);
    // التجديدُ يستهلك المفتوحَ ويُصدر زوجاً جديداً، و`tokens.save` داخله
    // يعيد كتابةَ الجديد في المخزن الآمن
    const ok = await refreshNow();
    if (!ok) {
      // **الرمزُ المخزَّنُ ميّت** — يُمحى ولا يُترك زرّاً يفشل كلَّ مرّة
      await forgetToken();
      await refreshBiometry();
      throw new Error("انتهت الجلسة المحفوظة — سجّل الدخول بكلمة المرور");
    }
    setUser(await getMe());
    await refreshBiometry();
  }, [refreshBiometry]);

  const value = useMemo<SessionState>(
    () => ({
      user,
      loading,
      signIn,
      signOut,
      refreshUser,
      pushState,
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
      pushState,
      biometry,
      refreshBiometry,
      setBiometric,
      signInWithBiometry,
    ],
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession() {
  return useContext(SessionContext);
}
