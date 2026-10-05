/** اختيارُ الدولة في شاشات المصادقة بلغة TAXO 2.0 (`AuthChoice`) — **منطقُ `CountryPicker` نفسُه** (البند ١٠،
 * `DESIGN-DECISIONS` 59): زرّان لا قائمة، **ولا يظهر حيث لا خيار** — سوقٌ واحدٌ في `/config` سؤالٌ بلا جواب.
 *
 * **وهنا بيتُ التسميات الوحيد**: كانت في `CountryPicker` (بطاقةُ الترحيب السابقة والدخولُ القديم) — **وحُذف حين لم يبقَ من
 * يقرؤه** (§٦٢/١)، فلا يبقى لاسم الدولة بيتان يفترقان أوّلَ سوقٍ يُضاف.
 */
import type { CountryCode } from "@/api/types";
import { AuthBlock, AuthChoice } from "@/taxo2";

const COUNTRY_LABEL: Record<CountryCode, string> = {
  JO: "الأردن",
  LY: "ليبيا",
};

export function MarketChoice({
  country,
  countries,
  onChange,
}: {
  country: CountryCode;
  countries: CountryCode[];
  onChange: (value: CountryCode) => void;
}) {
  if (countries.length < 2) return null;
  return (
    <AuthBlock label="الدولة">
      <AuthChoice
        label="الدولة"
        value={country}
        options={countries.map((code) => ({ value: code, label: COUNTRY_LABEL[code] }))}
        onChange={onChange}
      />
    </AuthBlock>
  );
}
