/** إعدادات المنصة كما تسلّمها الخلفية — تُقرأ مرةً ويقرؤها الجميع.
 *
 * في اللوحة تخدم شيئين: **بادئةُ الهاتف** في شاشة الدخول (لا تُكتب «962» في
 * كود أيّ واجهة)، و**ساعاتُ الهدوء** المنشورة لكل دولة — تعرضها صفحةُ الحملات
 * بجانب الجدولة لأن حملةً تُجدول داخل النافذة تُؤجَّل ولا تُرسل، وذلك أمرٌ
 * يجب أن يعرفه من يجدول قبل أن يضغط.
 */

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { getConfig } from "@/api/endpoints";
import { useCountries } from "@/lib/countries";
import type { AppConfig, CountryCode, CountryConfig } from "@/api/types";

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

/** وصفُ الدولة المعروضة — **من باب اللوحة أولاً** (SPEC §24).
 *
 * `/config` مصفّىً بمفتاح الظهور، فسوقٌ يُجهَّز قبل فتحه يغيب عنه ومعه عملتُه
 * وساعاتُ هدوئه — وهما ما تقرؤه شاشتا النظرة العامة والحملات. فيُقرأ من
 * `/admin/countries` حين يكون حاضراً، ويبقى `/config` مخرجاً قبل الدخول.
 *
 * **والوصفُ واحدٌ في البابين** (`services/country_config.build`)، فلا يفترق
 * حقلٌ بين قراءتين — وهو الشكلُ الثامن بعينه.
 */
export function useCountryConfig(
  country: CountryCode | undefined,
): CountryConfig | null {
  const { config } = useConfig();
  const { rows } = useCountries();
  if (!country) return null;
  const admin = rows?.find((row) => row.country_code === country);
  if (admin) return admin.config;
  return (
    config?.countries.find((entry) => entry.country_code === country) ?? null
  );
}
