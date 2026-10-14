/** إعدادات المنصة كما تسلّمها الخلفية — تُقرأ مرةً ويقرؤها الجميع.
 *
 * `GET /config` هو ما يجعل الواجهة **لا تفترض شيئاً**: أيُّ مُحقِّقٍ يرسم في
 * شاشة التسجيل، وأيُّ قنوات دفعٍ تعرض في هذه الدولة، وأيُّ توكن خرائط
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

import { Capacitor } from "@capacitor/core";

import { ApiError } from "@/api/client";
import { getConfig } from "@/api/endpoints";
import { registerCategoryFaces } from "@/lib/labels";
import { registerCurrencies } from "@/lib/utils";
import { cacheRules } from "@/lib/validation";
import type { AppConfig, CountryCode, CountryConfig } from "@/api/types";
import { onSplashRetry, setSplashStatus } from "@/lib/splash";
import type { FirebaseWebConfig } from "@/lib/firebase"; import { tr } from "@/lib/i18n";

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

/** **رمزٌ فنّيٌّ قصيرٌ ممّا يُعرف يقيناً — لا تشخيصٌ ولا تخمين.**
 *
 * يُقرأ عند الشكوى فيعرف من يسمعه **أين ينظر**: `HTTP 503` خادمٌ يردّ،
 * و`NETWORK` طلبٌ لم يصل أصلاً (حجبٌ أو DNS أو انقطاعٌ لحظيّ)، و`TIMEOUT`
 * انقضت المهلة. **ولا يُترجَم**: هو للمشرف لا للراكب.
 */
function reachCode(error: unknown): string {
  if (error instanceof ApiError) {
    return error.status > 0 ? `HTTP ${error.status}` : `ERR ${error.code}`;
  }
  const name = error instanceof Error ? error.name : "";
  if (name === "AbortError" || name === "TimeoutError") return "TIMEOUT";
  return "NETWORK";
}

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
        // **الفئاتُ الجديدةُ تُسمّى قبل أن تُرسم أيُّ شاشة** (SPEC §٦٧)
        registerCategoryFaces(value.countries.flatMap((country) => country.ride_categories ?? []));
        // **والعملاتُ كذلك** (SPEC §٧٣-ج/١٢) — علامتُها وخاناتُها من الخلفية قبل أن يُرسم مبلغ
        registerCurrencies(value.countries);
        setConfig(value);
        // آخرُ نسخةٍ من القواعد تُخزَّن لحظةَ وصولها (SPEC ١٧.٣)
        cacheRules(value.validation);
        setError(null);
        setSplashStatus(null);
        setAttempt(0);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setError(err.message);
        setSplashStatus(
          navigator.onLine ? "unreachable" : "offline",
          reachCode(err),
        );
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

/** دولةُ شاشات ما قبل الدخول وبادئتُها — من `GET /config` وحده.
 *
 * لا حسابَ بعدُ فلا دولةَ معروفة؛ فالخلفية تنشر `default_country_code` وتنشر
 * بادئةَ كل دولة وطولَ رقمها الوطني من `core/phone.py`.
 */
/** دولةُ **شاشات المصادقة** — بيتٌ واحدٌ لا اجتهادٌ لكل شاشة.
 *
 * قبل هذا كانت كلُّ شاشةٍ تختار بنفسها: الدخول من `default_country_code`،
 * والتسجيل من `default_country_code ?? countries[0]`، **والاستعادة من
 * `countries[0]` وحدها** — و`/config` يردّ الدول بترتيب التعداد `LY, JO`
 * بينما الافتراضية `JO`. فكانت شاشةُ الاستعادة تفترض ليبيا **ومنتقي الدولة
 * فيها مخفيّ**، أي أن أردنياً يدخل بحسابه ولا يستطيع استعادة كلمته: رقمُه
 * يُطبَّع بمفتاح `+218` فلا يجد حساباً. وقد كُتب في `Register.tsx` تعليقٌ
 * يشرح هذا العطبَ بعينه — أُصلح في شاشةٍ ونُسي في أختها، فصار المصدرُ هنا.
 *
 * ولا يُقرأ من هنا شيءٌ عن **حساب** قائم: بعد الدخول تُقرأ دولةُ صاحبه من
 * `user.country_code` (`usePhoneCountry(user?.country_code)`).
 */
/** مفتاحُ اختيار الدولة **على الجهاز لا على الحساب** (`DESIGN-DECISIONS` 59):
 *  من يدخل ليس له حسابٌ بعد، فلا مكانَ آخرَ يحفظ اختيارَه. */
const COUNTRY_KEY = "taxo.auth.country";

/** **ما تعرضه شاشةُ المصادقة من الدول** (SPEC §٧٤-أ/٤): **الدخولُ كلُّ دولة** — فالحساباتُ القائمةُ تدخل دائماً؛ **والتسجيلُ المفتوحةُ تُختار**،
 *  والمغلقةُ «قريباً» رماديّةً أو لا تُرسم بحسب ما اختاره المالكُ لها في «الدول» (`signup` في `/config`). */
export type AuthMode = "login" | "signup";

/** **دولةُ الموقع** — تخمينٌ ثالثٌ لا يُسأل له إذن: يُقرأ الموقعُ إن كان الإذنُ ممنوحاً سلفاً، وإلا لا شيء. **والصندوقُ من الخلفية**
 *  (`area` — صندوقُ نطاق الخدمة نفسُه)، فلا حدودَ مكتوبةٌ هنا. */
async function locatedCountry(entries: CountryConfig[]): Promise<CountryCode | null> {
  try {
    const state = await navigator.permissions?.query({ name: "geolocation" as PermissionName });
    if (state?.state !== "granted") return null;
    const position = await new Promise<GeolocationPosition>((resolve, reject) =>
      navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 4000, maximumAge: 600_000 }),
    );
    const { latitude, longitude } = position.coords;
    const hit = entries.find(({ area }) => {
      const [south, north, west, east] = area;
      return latitude >= south && latitude <= north && longitude >= west && longitude <= east;
    });
    return hit?.country_code ?? null;
  } catch {
    return null;
  }
}

/** **إقليمُ لغة الهاتف** (`fr-DZ` ⇒ `DZ`) — أقربُ ما يصل إليه تطبيقُ ويبٍ من الشريحة. */
function localeRegion(): string | null {
  const region = (navigator.language || "").split("-")[1];
  return region ? region.toUpperCase() : null;
}

export function useAuthCountry(mode: AuthMode = "login"): {
  country: CountryCode;
  /** **ما يُختار** — في الدخول كلُّ دولة، وفي التسجيل المفتوحةُ وحدَها */
  countries: CountryCode[];
  /** **ما ترسمه ورقةُ الدول** — ومعه المغلقةُ «قريباً» في التسجيل */
  options: Array<{ code: CountryCode; name: string; dial: string; soon: boolean }>;
  /** اسمُ الدولة المختارة بلغة الطلب — من `/config` */
  name: string;
  setCountry: (value: CountryCode) => void;
} {
  const { config } = useConfig();
  // **ولا رمزَ دولةٍ مكتوبٌ هنا** (SPEC §24): القائمةُ من `/config` وحدها، والافتراضيةُ منها كذلك — وقبل وصولها لا قائمةَ ولا
  // اختيار، وهي حالٌ لا تُرسم أصلاً (`Boot` ينتظر `/config`)
  const all = useMemo(() => config?.countries ?? [], [config]);
  const shown = mode === "signup" ? all.filter((entry) => entry.signup !== "hidden") : all;
  const selectable = mode === "signup" ? shown.filter((entry) => entry.signup === "open") : shown;
  const countries = selectable.map((entry) => entry.country_code);

  const [chosen, setChosen] = useState<CountryCode | null>(() => {
    const held = localStorage.getItem(COUNTRY_KEY);
    return held ? (held as CountryCode) : null;
  });
  const [located, setLocated] = useState<CountryCode | null>(null);
  const network = config?.network_country ?? null;

  // **الموقعُ آخرُ التخمينات** — لا يُطلب إلا حين لا اختيارَ محفوظاً ولا شبكةَ تقول شيئاً
  useEffect(() => {
    if (chosen || network || all.length === 0) return;
    let alive = true;
    void locatedCountry(all).then((code) => {
      if (alive) setLocated(code);
    });
    return () => {
      alive = false;
    };
  }, [chosen, network, all]);

  // **الافتراضُ بالترتيب** (§٧٤-أ/٤): ما اختاره صاحبُ الجهاز · شبكتُه · إقليمُ لغته · موقعُه · افتراضيّةُ الخلفية · أوّلُ ما يُختار —
  // **وكلٌّ لا يُقبل إلا إن كان ممّا يُختار في هذه الشاشة** (دولةٌ مغلقةٌ اختيرت للدخول لا تصير افتراضَ التسجيل).
  // **والتخمينُ لا يقع على سوقٍ مغلق ما وُجد مفتوح** (أمرُ المالك ٢٠٢٦-١٠-١٥): الدخولُ يقبل كلَّ دولة، فكانت شبكةٌ ليبيّةٌ
  // (`network_country: LY`) تفتح شاشةَ دخول الكبتن على +218 وليبيا «قريباً». **واختيارُ صاحب الجهاز وحدَه يُحترم ولو مغلقاً** —
  // حسابٌ قائمٌ في سوقٍ مغلقٍ يدخل، وقد اختاره بيده.
  const open = all.filter((entry) => entry.status === "open").map((entry) => entry.country_code);
  const guesses = [network, localeRegion(), located, config?.default_country_code, countries[0]];
  const allowed = (code: string | null | undefined): code is CountryCode => !!code && countries.includes(code as CountryCode);
  const country = ((allowed(chosen) ? chosen : null) ??
    guesses.find((code) => allowed(code) && open.includes(code)) ??
    guesses.find(allowed) ??
    countries[0] ??
    config?.default_country_code ??
    "") as CountryCode;

  const setCountry = useCallback((value: CountryCode) => {
    localStorage.setItem(COUNTRY_KEY, value);
    setChosen(value);
  }, []);

  const options = shown.map((entry) => ({
    code: entry.country_code,
    name: entry.name,
    dial: entry.dial_code,
    soon: mode === "signup" && entry.signup !== "open",
  }));
  const name = all.find((entry) => entry.country_code === country)?.name ?? country;
  return { country, countries, options, name, setCountry };
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

export function useMapboxToken(): string | null {
  const mapbox = useConfig().config?.providers.mapbox;
  // **iOS يقرأ توكنَه وحدَه، بلا رجوعٍ إلى أخيه** (قرارُ المالك ٢٠٢٦-٠٩-٢٩):
  // التوكنُ المقيَّدُ يُرفض ٤٠٣ من `capacitor://` لأن WebKit لا يرسل `Referer`
  // — **فالرجوعُ إليه خريطةٌ فارغةٌ صامتة**، وهو ما يُسمّى بدله في
  // `useMapboxMissing`. وأندرويد والويب كما كانا حرفاً.
  if (Capacitor.getPlatform() === "ios") return mapbox?.ios_public_token || null;
  return mapbox?.public_token ?? null;
}

/** **غيابُ توكن iOS يُسمّى ولا يُرسم فراغاً** — `null` حين لا شيءَ يُسمّى.
 *
 *  **وقبل وصول `/config` لا يُسمّى شيء**: غيابٌ لم يُقَس بعدُ ليس غياباً. */
export const IOS_MAP_TOKEN_MISSING =
  tr("الخريطة غير متاحة على iPhone حالياً — توكن الخرائط الخاص بـiOS غير مضبوط.");

export function useMapboxMissing(): string | null {
  const { config } = useConfig();
  if (!config || Capacitor.getPlatform() !== "ios") return null;
  return config.providers.mapbox?.ios_public_token ? null : IOS_MAP_TOKEN_MISSING;
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
