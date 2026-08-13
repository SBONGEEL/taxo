/** إعدادات المنصة كما تسلّمها الخلفية — تُقرأ مرةً ويقرؤها الجميع.
 *
 * `GET /config` هو ما يجعل الواجهة **لا تفترض شيئاً**: أيُّ مُحقِّقٍ يرسم في
 * شاشة التسجيل، وأيُّ قنوات دفعٍ تعرض في هذه الدولة، وأيُّ توكن خرائط
 * تستعمل. مفتاحٌ يُطفأ من اللوحة يختفي أثرُه من التطبيق بلا نشر (SPEC القسم 4).
 */

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { getConfig } from "@/api/endpoints";
import type { AppConfig, CountryCode, CountryConfig } from "@/api/types";
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

export function ConfigProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getConfig()
      .then((value) => !cancelled && (setConfig(value), setError(null)))
      .catch((err: Error) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [nonce]);

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
export function useAuthCountry(): {
  country: CountryCode;
  countries: CountryCode[];
} {
  const { config } = useConfig();
  return {
    country: config?.default_country_code ?? "JO",
    countries: config?.countries.map((entry) => entry.country_code) ?? ["JO"],
  };
}

export function usePhoneCountry(override?: CountryCode): {
  country: CountryCode;
  dialCode: string;
  nationalLength: number;
} {
  const { config } = useConfig();
  const country = override ?? config?.default_country_code ?? "JO";
  const entry = config?.countries.find((item) => item.country_code === country);
  return {
    country,
    dialCode: entry?.dial_code ?? "962",
    nationalLength: entry?.national_number_length ?? 9,
  };
}

export function useMapboxToken(): string | null {
  return useConfig().config?.providers.mapbox?.public_token ?? null;
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
