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

export function useCountryConfig(
  country: CountryCode | undefined,
): CountryConfig | null {
  const { config } = useConfig();
  if (!config || !country) return null;
  return (
    config.countries.find((entry) => entry.country_code === country) ?? null
  );
}
