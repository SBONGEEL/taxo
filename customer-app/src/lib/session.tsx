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

import { ApiError, hydrateTokens, setRefreshStore, setSessionLostHandler, tokens } from "@/api/client";
import {
  biometryStatus,
  deviceSecretForRevoke,
  forgetDeviceSecret,
  isBiometricPreferred,
  nativeRefreshStore,
  proveBiometry,
  setBiometricPreferred,
  storeDeviceSecret,
  unlockDeviceSecret,
  type BiometryStatus,
} from "@/lib/biometric";
import {
  deviceLogin,
  enrollDeviceLogin,
  forgetDeviceLogin,
  getMe,
  logout as logoutRequest,
  registerDevice,
  revokeAllSessions,
  unregisterDevice,
} from "@/api/endpoints";
import { forgetRememberedLogin, rememberLogin } from "@/lib/remembered";
import type { AuthResponse, User } from "@/api/types";
import { firebaseConfigOf, useConfig } from "@/lib/config";
import { deviceId, platform } from "@/lib/device";
import { requestPushToken } from "@/lib/firebase";
import { channelSet, markPushReady, registerNativePush } from "@/lib/push";
import { setSplashStatus } from "@/lib/splash"; import { tr } from "@/lib/i18n";

/** **عطبٌ عابرٌ لا حكمٌ على الجلسة**: شبكةٌ (`status 0`) أو خادمٌ ساقطٌ (`5xx`)،
 *  أو خطأٌ لم يمرّ بعميل HTTP أصلاً. وما عدا ذلك قاله الخادمُ عن الحساب. */
function isTransient(error: unknown): boolean {
  if (!(error instanceof ApiError)) return true;
  return error.status === 0 || error.status >= 500;
}

// **بيتُ رمز التجديد يُحقن قبل أيِّ رسم** (SPEC §60-ج): الإقلاعُ يقرؤه، فلا يجوز أن يسبقه أثرٌ لم يُركَّب بعد
setRefreshStore(nativeRefreshStore);

/** **يُشعل الدخولَ بالبصمة على هذا الجهاز** بجلسةٍ قائمة — والسرُّ إلى المخزن الآمن. */
async function enrollHere(): Promise<void> {
  const { secret } = await enrollDeviceLogin(deviceId());
  await storeDeviceSecret(secret);
}

interface SessionState {
  user: User | null;
  loading: boolean;
  signIn: (response: AuthResponse, options?: { viaDevice?: boolean }) => void;
  signOut: () => Promise<void>;
  /** إنهاءُ كلِّ جلسات الحساب على كلِّ الأجهزة — وهذه منها (SPEC §60). */
  signOutEverywhere: () => Promise<void>;
  refreshUser: () => Promise<void>;
  /** حالُ الدخول بالبصمة — **تُقاس ولا تُفترض**، و`null` «لم تُقرأ بعد». */
  biometry: BiometryStatus | null;
  refreshBiometry: () => Promise<void>;
  setBiometric: (on: boolean) => Promise<void>;
  signInWithBiometry: () => Promise<void>;
  /** **«الدخول بحساب آخر»** — يُبطل بيانَ البصمة على الخادم ويمحو الرقمَ المتذكَّر والتفضيل (SPEC §60-ج). */
  signInAsAnother: () => Promise<void>;
}

const SessionContext = createContext<SessionState>({
  user: null,
  loading: true,
  signIn: () => undefined,
  signOut: async () => undefined,
  signOutEverywhere: async () => undefined,
  refreshUser: async () => undefined,
  biometry: null,
  refreshBiometry: async () => undefined,
  setBiometric: async () => undefined,
  signInWithBiometry: async () => undefined,
  signInAsAnother: async () => undefined,
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
      // **جلسةٌ رُفضت لا تمحو بيانَ البصمة** (SPEC §60-ج): الخادمُ يُبطله بنفسه حين يجب (استعادةُ الكلمة، الإيقاف، إنهاءُ كلِّ
      // الجلسات)، **وإلا فهو باقٍ** — والدخولُ به يقول إن كان قد أُبطل
      void biometryStatus().then(setBiometry);
    });
  }, []);

  useEffect(() => {
    // **إقلاعٌ بلا شبكة لا يُخرج** (SPEC §60، قرارُ المالك ٢٠٢٦-١٠-٠٤): كان أيُّ
    // فشلٍ في `GET /auth/me` يمحو الرموز — فمن فتح التطبيقَ في نفقٍ أو والخادمُ
    // يُعاد تشغيلُه وجد نفسَه خارجَ حسابه. **فالعابرُ يُعاد وتبقى الترحيبيةُ**
    // تقول حالَ الشبكة، وما قاله الخادمُ (`401` بعد تجديدٍ مرفوض، أو حظر)
    // يمحو كما كان.
    let cancelled = false;
    let attempt = 0;
    const load = () => {
      getMe()
        .then((me) => {
          if (cancelled) return;
          setSplashStatus(null);
          setUser(me);
          setLoading(false);
        })
        .catch((error: unknown) => {
          if (cancelled) return;
          if (isTransient(error)) {
            attempt += 1;
            setSplashStatus(navigator.onLine === false ? "offline" : "slow");
            window.setTimeout(load, Math.min(10_000, 1_000 * 2 ** attempt));
            return;
          }
          tokens.clear();
          setLoading(false);
        });
    };
    // **بيتُ الجهاز يُقرأ قبل الحكم** (أمرُ المالك ٢٠٢٦-١١-٠٢): رمزُ الوصول ينتهي بعد نصف ساعة، **ورمزُ التجديد في المخزن
    // الآمن هو الجلسةُ** — فلا خروجَ إلا حين لا يبقى أيٌّ منهما
    void hydrateTokens().then(() => {
      if (cancelled) return;
      if (!tokens.access() && !tokens.refresh()) {
        setLoading(false);
        return;
      }
      load();
    });
    return () => {
      cancelled = true;
    };
  }, []);

  /** تسجيل الجهاز بعد الدخول — يُبتلع فشلُه: إشعاراتٌ لا تصل أهون من دخولٍ
   * لا يكتمل (SPEC القسم 10: «الفشل يُبتلع ويُسجَّل»). */
  //
  // **ومسارانِ لا مسار** (قرارُ المالك ٢٠٢٦-٠٩-٢٩، كالكبتن منذ ٢٠٢٦-٠٨-٢١): على
  // الجهاز **الطريقُ الأصليّ** على أندرويد وiOS، وفي المتصفّح طريقُ الويب كما
  // كان. **ولا يُسأل الأصليُّ عن `vapid`**: ذاك مفتاحُ Web Push وحدَه.
  useEffect(() => {
    if (!user || registered.current) return;

    if (Capacitor.isNativePlatform()) {
      registered.current = true;
      void (async () => {
        const { token } = await registerNativePush();
        if (!token) return;
        // **ومعه ما على الجهاز من قنوات** (§٦١-ل): به يختار الخادمُ القناة
        const channels = await channelSet();
        await registerDevice({
          device_id: deviceId(),
          token,
          platform: platform(),
          ...(channels ? { push_channels: channels } : {}),
        });
        markPushReady();
      })().catch((error) => console.warn("تعذّر تسجيل الجهاز للإشعارات", error));
      return;
    }

    const fcm = firebaseConfigOf(config?.providers.fcm);
    const vapid = config?.providers.fcm?.vapid_key;
    if (!fcm || !vapid) return;

    registered.current = true;
    requestPushToken(fcm, vapid)
      .then(async (token) => {
        if (!token) return;
        await registerDevice({ device_id: deviceId(), token, platform: platform() });
        markPushReady();
      })
      .catch((error) => console.warn("تعذّر تسجيل الجهاز للإشعارات", error));
  }, [user, config]);

  const refreshBiometry = useCallback(async () => {
    setBiometry(await biometryStatus());
  }, []);

  useEffect(() => {
    void refreshBiometry();
  }, [refreshBiometry]);

  const signIn = useCallback(
    (response: AuthResponse, options: { viaDevice?: boolean } = {}) => {
      tokens.save(response.tokens);
      setUser(response.user);
      // **الرقمُ والدولةُ يُتذكَّران — وكلمةُ المرور لا** (SPEC §60-ج)
      if (response.user.phone) rememberLogin({ phone: response.user.phone, country: response.user.country_code });
      // **ومن أشعل البصمةَ يعود بيانُه بعد كلِّ دخولٍ بكلمته** — بيانٌ أُبطل (استعادةُ الكلمة، الإيقاف) يُستبدل بلا أن يُشعلها
      // من جديد. **والدخولُ بالبصمة نفسُه حمل سرَّه المُدوَّر**، فلا إشعالَ ثانٍ
      if (!options.viaDevice && isBiometricPreferred() && Capacitor.isNativePlatform()) {
        void enrollHere()
          .catch((error) => console.warn("تعذّر تجديدُ الدخول بالبصمة", error))
          .finally(() => void refreshBiometry());
      } else {
        void refreshBiometry();
      }
    },
    [refreshBiometry],
  );

  /** **الرابعةُ من الأربع** — الإطفاءُ من الإعدادات يمحو ويطفئ معاً. */
  const setBiometric = useCallback(
    async (on: boolean) => {
      if (on) {
        await proveBiometry(tr("لتفعيل الدخول بالبصمة"));
        try {
          await enrollHere();
        } catch (caught) {
          throw caught instanceof ApiError ? caught : new Error(tr("تعذّر تفعيل الدخول بالبصمة — أعد المحاولة"));
        }
        setBiometricPreferred(true);
      } else {
        const secret = await deviceSecretForRevoke();
        if (secret) await forgetDeviceLogin(deviceId(), secret).catch(() => undefined);
        await forgetDeviceSecret();
        setBiometricPreferred(false);
      }
      await refreshBiometry();
    },
    [refreshBiometry],
  );

  /** **البصمةُ ثمّ بيانُ الجهاز** — جلسةٌ جديدةٌ وسرٌّ مُدوَّرٌ يُكتب مكانَ المصروف (SPEC §60-ج). */
  const signInWithBiometry = useCallback(async () => {
    const secret = await unlockDeviceSecret(tr("لتسجيل الدخول إلى TAXO"));
    let response: Awaited<ReturnType<typeof deviceLogin>>;
    try {
      response = await deviceLogin(deviceId(), secret);
    } catch (caught) {
      // **`401` حكمُ الخادم على البيان** — أُبطل (استعادةُ الكلمة، الإيقاف، إنهاءُ كلِّ الجلسات): يُمحى ويُقال الطريق.
      // وما عداه (شبكة، حدّ) عابرٌ يُقال ولا يمحو
      if (caught instanceof ApiError && caught.status === 401) {
        await forgetDeviceSecret();
        await refreshBiometry();
        throw new Error(tr("انتهى الدخولُ بالبصمة على هذا الجهاز — ادخل بكلمة المرور مرّةً، ويعود بعدها."));
      }
      throw caught;
    }
    await storeDeviceSecret(response.device_secret);
    signIn({ user: response.user, tokens: response.tokens }, { viaDevice: true });
  }, [refreshBiometry, signIn]);

  /** **«الدخول بحساب آخر»** — يُبطَل البيانُ على الخادم أوّلاً ثمّ يُمحى ما على الجهاز: الرقمُ والدولةُ والسرُّ والتفضيل. */
  const signInAsAnother = useCallback(async () => {
    const secret = await deviceSecretForRevoke();
    if (secret) await forgetDeviceLogin(deviceId(), secret).catch(() => undefined);
    await forgetDeviceSecret();
    setBiometricPreferred(false);
    forgetRememberedLogin();
    await refreshBiometry();
  }, [refreshBiometry]);

  const signOut = useCallback(async () => {
    const refresh = tokens.refresh();
    // الترتيب مقصود: يُحذف الجهاز والتوكن ما زال صالحاً
    await unregisterDevice(deviceId()).catch(() => undefined);
    if (refresh) await logoutRequest(refresh).catch(() => undefined);
    tokens.clear();
    // **والخروجُ لا يمحو بيانَ البصمة ولا الرقمَ المتذكَّر** (أمرُ المالك ٢٠٢٦-١١-٠٢): الجلسةُ انتهت على الخادم، **والدخولُ التالي
    // بالبصمة يفتح جلسةً جديدة**. ومن أراد محوَهما فـ«الدخول بحساب آخر»
    registered.current = false;
    setUser(null);
    await refreshBiometry();
  }, [refreshBiometry]);

  /** **إنهاءُ كلِّ الجلسات** (SPEC §60-ب/١) — لهاتفٍ أو حاسوبٍ ضاع.
   *
   * الخلفيةُ تُبطل كلَّ جلسات الحساب **وهذه منها**، وتمحو رموزَ الإشعار لكلِّ
   * أجهزته؛ فلا يبقى هنا إلا ما يفعله الخروجُ محلّياً. **والجهازُ يُحذف أوّلاً**
   * والتوكنُ ما زال صالحاً، كما في الخروج.
   */
  const signOutEverywhere = useCallback(async () => {
    await unregisterDevice(deviceId()).catch(() => undefined);
    await revokeAllSessions();
    tokens.clear();
    // **والخادمُ أبطل بيانَ البصمة معها** (`revoke_all_for_user`) — فيُمحى هنا ولا يبقى زرٌّ يفشل
    await forgetDeviceSecret();
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
      signOutEverywhere,
      refreshUser,
      biometry,
      refreshBiometry,
      setBiometric,
      signInWithBiometry,
      signInAsAnother,
    }),
    [
      user,
      loading,
      signIn,
      signOut,
      signOutEverywhere,
      refreshUser,
      biometry,
      refreshBiometry,
      setBiometric,
      signInWithBiometry,
      signInAsAnother,
    ],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  return useContext(SessionContext);
}
