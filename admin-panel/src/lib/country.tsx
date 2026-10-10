/** الدولة المعروضة — **حالةُ عرضٍ لا إعدادُ حساب**.
 *
 * اللوحة تدير سوقين، وكلُّ شاشةٍ فيها تضيّق بما هو معروض الآن: جدولُ الحملات
 * يقرأ منها ساعاتِ الهدوء، والتسعيرةُ والاشتراكات تقرأ منها صفوفَها. ولأنها
 * عرضٌ لا هوية، مكانُها `sessionStorage` لا الخلفية: مشرفٌ يفتح تبويبين
 * لسوقين لا يجوز أن يبدّل أحدُهما ما يراه الآخر.
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

import type { CountryCode } from "@/api/types";
import { useCountries } from "@/lib/countries";

const KEY = "taxo.admin.country";

interface CountryState {
  country: CountryCode;
  setCountry: (country: CountryCode) => void;
}

const CountryContext = createContext<CountryState>({
  country: "JO",
  setCountry: () => undefined,
});

export function CountryProvider({
  children,
  fallback,
}: {
  children: ReactNode;
  /** دولةُ اللوحة قبل أي اختيار — من `/config` لا مكتوبةً هنا. */
  fallback: CountryCode;
}) {
  const [country, setStored] = useState<CountryCode>(() => {
    // **أيُّ رمزِ دولةٍ لا السوقان** (SPEC §٧٣-ج/١٢): كان `saved === "JO" || saved === "LY"` فيضيع اختيارُ سوقٍ ثالثٍ عند كلِّ
    // تحديث. **ولا قائمةَ دولٍ هنا** — الصحّةُ تُحكم أدناه حين تصل الأسواقُ من مصدرها
    const saved = sessionStorage.getItem(KEY);
    return saved && /^[A-Z]{2}$/.test(saved) ? (saved as CountryCode) : fallback;
  });
  const { rows } = useCountries();
  // **سوقٌ محفوظٌ لم يعد موجوداً يعود إلى الافتراض** — حين يُعرف الموجودُ من الخلفية لا قبلها
  useEffect(() => {
    if (rows && !rows.some((row) => row.country_code === country)) setStored(fallback);
  }, [rows, country, fallback]);

  const setCountry = useCallback((next: CountryCode) => {
    sessionStorage.setItem(KEY, next);
    setStored(next);
  }, []);

  const value = useMemo<CountryState>(
    () => ({ country, setCountry }),
    [country, setCountry],
  );

  return (
    <CountryContext.Provider value={value}>{children}</CountryContext.Provider>
  );
}

export function useCountry() {
  return useContext(CountryContext);
}
