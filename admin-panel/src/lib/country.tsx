/** الدولة المعروضة — **حالةُ عرضٍ لا إعدادُ حساب**.
 *
 * اللوحة تدير سوقين، وكلُّ شاشةٍ فيها تضيّق بما هو معروض الآن: جدولُ الحملات
 * يقرأ منها ساعاتِ الهدوء، والتسعيرةُ والاشتراكات تقرأ منها صفوفَها. ولأنها
 * عرضٌ لا هوية، مكانُها `sessionStorage` لا الخلفية: مشرفٌ يفتح تبويبين
 * لسوقين لا يجوز أن يبدّل أحدُهما ما يراه الآخر.
 *
 * **وآخرُ اختيارٍ يُذكر على الجهاز** (قرارُ المالك 2026-10-22): `sessionStorage` يضيع بإغلاق التطبيق على الهاتف فيعود كلَّ
 * مرّةٍ إلى الافتراض. فيُكتب في `localStorage` أيضاً، **ويُقرأ بعد `sessionStorage` لا قبله** — فالتبويبان يبقيان مستقلَّين،
 * والفتحُ الجديدُ يبدأ من آخر سوق.
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

// **التخزينُ قد يُمنع** (نافذةٌ خاصّة) — فالقراءةُ والكتابةُ لا تُسقطان اللوحة
function readLast(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

function writeLast(country: string) {
  try {
    localStorage.setItem(KEY, country);
  } catch {
    // لا شيء — يبقى الاختيارُ لهذا التبويب وحده
  }
}

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
    const saved = sessionStorage.getItem(KEY) ?? readLast();
    return saved && /^[A-Z]{2}$/.test(saved) ? (saved as CountryCode) : fallback;
  });
  const { rows } = useCountries();
  // **سوقٌ محفوظٌ لم يعد موجوداً يعود إلى الافتراض** — حين يُعرف الموجودُ من الخلفية لا قبلها
  useEffect(() => {
    if (rows && !rows.some((row) => row.country_code === country)) setStored(fallback);
  }, [rows, country, fallback]);

  const setCountry = useCallback((next: CountryCode) => {
    sessionStorage.setItem(KEY, next);
    writeLast(next);
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
