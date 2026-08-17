/** إعدادات المنصة كما تسلّمها الخلفية — تُقرأ مرةً ويقرؤها الجميع.
 *
 * `GET /config` هو ما يجعل الواجهة **لا تفترض شيئاً**: أيُّ مُحقِّقٍ يرسم في
 * شاشة التسجيل، ووأيُّ قنوات دفعٍ تعرض في هذه الدولة، وأيُّ توكن خرائط
 * تستعمل. مفتاحٌ يُطفأ من اللوحة يختفي أثرُه من التطبيق بلا نشر (SPEC القسم 4).
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

import { getConfig } from "@/api/endpoints";
import type { AppConfig, CountryCode, CountryConfig } from "@/api/types";
import { onSplashRetry, setSplashStatus } from "@/lib/splash";
import type { FirebaseWebConfig } from "@/lib/firebase";

interface ConfigState {
  config: AppConfig | null;
  error: string | null;
  reload: () => void;
}

const ConfigContext = createContext<ConfigState>({
  config: null,
  error: null,
  reload: () => undefined,
});

/** بعدها يُقرأ الصمتُ بطءاً لا سكوناً — أطولُ من نداءٍ سويٍّ وأقصرُ من صبرِ أحد. */
const SLOW_AFTER_MS = 4_000;

export function ConfigProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);
  const [attempt, setAttempt] = useState(0);

  /** **الانقطاعُ والبطءُ حالان لا حال** (`DESIGN.md` §7.8):
   *
   * - **انقطاع**: `navigator.onLine === false`، أو سقوطُ النداء بخطأ شبكة.
   * - **بطء**: مضت `SLOW_AFTER_MS` ولا ردَّ ولا خطأ — الطلبُ ما زال معلّقاً.
   *
   * وتمييزُهما ليس تجميلاً: «لا اتصال» يقول افتح الشبكة، و«ضعيفة» يقول لا
   * تفعل شيئاً. ونصٌّ واحدٌ للحالين يجعل أحدَ الجوابين خطأً دائماً.
   *
   * **وإعادةُ المحاولة تلقائيةٌ بتباعدٍ متزايد** (٢ ← ٤ ← ٨ ← ١٥ ثانيةً سقفاً):
   * محاولةٌ كلَّ ثانيةٍ على شبكةٍ مقطوعة تستنزف بطاريةً بلا فائدة، ومحاولةٌ
   * واحدةٌ ثم انتظارُ ضغطةٍ تترك التطبيقَ معلّقاً على شبكةٍ عادت وحدها.
   *
   * **والعودةُ فورَ عودة الاتصال بلا ضغطة**: حدثُ `online` يُسقط التباعدَ كلَّه.
   */
  useEffect(() => {
    let cancelled = false;
    let slowTimer: number | null = null;

    if (!navigator.onLine) {
      setSplashStatus("offline");
    } else {
      slowTimer = window.setTimeout(
        () => !cancelled && setSplashStatus("slow"),
        SLOW_AFTER_MS,
      );
    }

    getConfig()
      .then((value) => {
        if (cancelled) return;
        setConfig(value);
        setError(null);
        setSplashStatus(null);
        setAttempt(0);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setError(err.message);
        setSplashStatus(navigator.onLine ? "slow" : "offline");
        setAttempt((n) => n + 1);
      })
      .finally(() => slowTimer !== null && window.clearTimeout(slowTimer));

    return () => {
      cancelled = true;
      if (slowTimer !== null) window.clearTimeout(slowTimer);
    };
  }, [nonce]);

  // التباعدُ المتزايد — ولا يعمل بعد أن تصل الإعدادات
  useEffect(() => {
    if (config || attempt === 0) return;
    const delay = Math.min(2_000 * 2 ** (attempt - 1), 15_000);
    const timer = window.setTimeout(() => setNonce((n) => n + 1), delay);
    return () => window.clearTimeout(timer);
  }, [attempt, config]);

  // عودةُ الاتصال تُسقط الانتظارَ كلَّه — بلا ضغطةٍ من أحد
  useEffect(() => {
    const back = () => {
      setAttempt(0);
      setNonce((n) => n + 1);
    };
    window.addEventListener("online", back);
    return () => window.removeEventListener("online", back);
  }, []);

  // زرُّ «إعادة المحاولة» على الشاشة الترحيبية
  useEffect(() => {
    onSplashRetry(() => {
      setAttempt(0);
      setNonce((n) => n + 1);
    });
  }, []);

  const value = useMemo<ConfigState>(
    () => ({ config, error, reload: () => setNonce((n) => n + 1) }),
    [config, error],
  );

  return (
    <ConfigContext.Provider value={value}>{children}</ConfigContext.Provider>
  );
}

export function useConfig() {
  return useContext(ConfigContext);
}

/** إعدادات دولة المستخدم — منها تُقرأ مفاتيح الميزات وفئات المركبات. */
export function useCountryConfig(
  country: CountryCode | undefined,
): CountryConfig | null {
  const { config } = useConfig();
  if (!config || !country) return null;
  return (
    config.countries.find((entry) => entry.country_code === country) ?? null
  );
}

/** «هل هذه الميزة مفعّلة في هذه الدولة؟» — والغياب معطّل دائماً (SPEC القسم 4). */
export function useFeature(
  country: CountryCode | undefined,
  key: string,
): boolean {
  return useCountryConfig(country)?.features[key] === true;
}

/** إعدادُ تطبيق الويب لدى Firebase من عقدٍ بعينه — `null` بغير عقد مكتمل. */
export function firebaseConfigOf(
  values:
    | {
        project_id?: string;
        api_key?: string;
        auth_domain?: string;
        app_id?: string;
        sender_id?: string;
      }
    | undefined,
): FirebaseWebConfig | null {
  if (!values?.project_id || !values.api_key || !values.app_id) return null;
  return {
    apiKey: values.api_key,
    authDomain: values.auth_domain ?? `${values.project_id}.firebaseapp.com`,
    projectId: values.project_id,
    appId: values.app_id,
    messagingSenderId: values.sender_id,
  };
}

/** التوكن العام للخرائط — من عقد Mapbox عبر `/config`، لا من `.env`. */
export function useMapboxToken(): string | null {
  return useConfig().config?.providers.mapbox?.public_token ?? null;
}

/** دولةُ شاشات ما قبل الدخول وبادئتُها — من `GET /config` وحده.

 * لا حسابَ بعدُ فلا دولةَ معروفة، والتصميم بلا منتقي دول؛ فالخلفية تنشر
 * `default_country_code` وتنشر بادئةَ كل دولة وطولَ رقمها الوطني. والقيم
 * الاحتياطية هنا لحظةَ ما قبل وصول الإعدادات فقط — والشاشات لا تُرسم قبله
 * أصلاً (`Boot` في `App.tsx`).
 */
/** مفتاحُ اختيار الدولة **على الجهاز لا على الحساب** (`DESIGN-DECISIONS` 59):
 *  من يدخل ليس له حسابٌ بعد، فلا مكانَ آخرَ يحفظ اختيارَه. */
const COUNTRY_KEY = "taxo.auth.country";

/** دولةُ شاشات المصادقة: المختارةُ إن اختار، وإلا افتراضيةُ `/config`.
 *
 * **والقائمةُ هي الحاكمة**: اختيارٌ لا تعرفه `/config` (سوقٌ أُغلق، أو مفتاحٌ
 * عبث به أحد) يُهمَل ويعود إلى الافتراضي — بدل أن يُرسَل رمزُ دولةٍ لا وجود لها.
 */
export function useAuthCountry(): {
  country: CountryCode;
  countries: CountryCode[];
  setCountry: (value: CountryCode) => void;
} {
  const { config } = useConfig();
  const countries = config?.countries.map((entry) => entry.country_code) ?? ["JO"];
  const fallback = config?.default_country_code ?? "JO";

  const [chosen, setChosen] = useState<CountryCode | null>(() => {
    const held = localStorage.getItem(COUNTRY_KEY);
    return held ? (held as CountryCode) : null;
  });

  const country = chosen && countries.includes(chosen) ? chosen : fallback;

  const setCountry = useCallback((value: CountryCode) => {
    localStorage.setItem(COUNTRY_KEY, value);
    setChosen(value);
  }, []);

  return { country, countries, setCountry };
}

export function usePhoneCountry(override?: CountryCode): {
  country: CountryCode;
  /** `null` حين لا تُنشر الدولةُ في `GET /config` — **ولا افتراضَ ثابت**. */
  dialCode: string | null;
  nationalLength: number;
} {
  const { config } = useConfig();
  const country = override ?? config?.default_country_code ?? "JO";
  const entry = config?.countries.find((item) => item.country_code === country);

  // **ولا مفتاحَ دولةٍ احتياطيٌّ ثابت.** كان `dial_code ?? "962"`، فلو غابت
  // دولةٌ من `GET /config` — عقدٌ يُطفأ، أو سوقٌ يُضاف ولا يُنشر — لَبقي
  // **المفتاحُ المعروضُ ليبيّاً والرقمُ يُبنى بمفتاح الأردن**: رقمٌ يذهب إلى
  // صاحبٍ آخرَ أو إلى لا أحد، ورمزٌ يُقال إنه أُرسل ولا يصل.
  //
  // **والافتراضُ هنا أخطرُ من الغياب**: رقمٌ بلا مفتاحٍ يفشل ظاهراً فيُصلَح،
  // ورقمٌ بمفتاحٍ خاطئٍ ينجح ظاهراً فيبقى. فـ`null` تُجبر من يقرأ على أن
  // يقرّر — والحقلُ يُعطَّل ولا يبني رقماً بمفتاحٍ لا يخصّ الدولةَ المختارة.
  return {
    country,
    dialCode: entry?.dial_code ?? null,
    nationalLength: entry?.national_number_length ?? 9,
  };
}
