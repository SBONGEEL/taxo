/** أسواقُ المنصّة كما تراها اللوحة — **كلُّها، ظاهرةً كانت أو مخفيّة** (SPEC §24).
 *
 * مفتاحُ `country_visible` يحذف الدولةَ من `GET /config`، وهو ما تقرؤه
 * التطبيقات. واللوحةُ لا تقرأ منه: من يُجهّز سوقاً **قبل** فتحه — تسعيرتَه
 * وحملاتِه وعقودَه — يحتاج أن يراه وهو مطفأ، وإلا صار الإشعالُ زرّاً في شاشةٍ
 * لا تُظهر ما يشعله.
 *
 * **ولا قائمةَ دولٍ مكتوبةً في الواجهة**: كانت `["JO","LY"]` في الترويسة،
 * فإضافةُ سوقٍ ثالث تعني تعديلَ ملفٍّ ونشرَ حزمة. الآن الخلفيةُ تقولها.
 */

import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { getCountries } from "@/api/endpoints";
import type { CountryCode, CountryRow } from "@/api/types";

interface CountriesState {
  rows: CountryRow[] | null;
  reload: () => void;
}

const CountriesContext = createContext<CountriesState>({
  rows: null,
  reload: () => undefined,
});

export function CountriesProvider({
  children,
  enabled,
}: {
  children: ReactNode;
  /** لا يُسأل قبل الدخول — البابُ `StaffUser`، وشاشةُ الدخول تقرأ `/config`. */
  enabled: boolean;
}) {
  const [rows, setRows] = useState<CountryRow[] | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (!enabled) {
      setRows(null);
      return;
    }
    let cancelled = false;
    getCountries()
      .then((value) => !cancelled && setRows(value.countries))
      // **وفشلُ النداء لا يُعطّل اللوحة**: `rows` تبقى `null` فتُقرأ الدولُ
      // من `/config` كما كانت — أضيقُ ممّا يجب، ولا شاشةَ بيضاء
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [enabled, nonce]);

  const value = useMemo<CountriesState>(
    () => ({ rows, reload: () => setNonce((n) => n + 1) }),
    [rows],
  );

  return (
    <CountriesContext.Provider value={value}>
      {children}
    </CountriesContext.Provider>
  );
}

export function useCountries() {
  return useContext(CountriesContext);
}

/** اسمُ الدولة كما تكتبه الخلفية — ولا جدولَ أسماءٍ ثانٍ في الواجهة. */
export function useCountryName(code: CountryCode): string {
  const { rows } = useCountries();
  return rows?.find((row) => row.country_code === code)?.name ?? code;
}
