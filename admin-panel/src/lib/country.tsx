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
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";

import type { CountryCode } from "@/api/types";

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
    const saved = sessionStorage.getItem(KEY);
    return saved === "JO" || saved === "LY" ? saved : fallback;
  });

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
