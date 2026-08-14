/** منتقي الدولة في شاشات المصادقة (البند ١٠، `DESIGN-DECISIONS` 59).
 *
 * **كان في التسجيل وحدَه** — والقرارُ السابق «بادئةٌ ثابتةٌ من
 * `default_country_code`» نُقض بنصِّه: المنصّةُ سوقان، وبادئةٌ واحدةٌ معروضة
 * تجعل نصفَ من نخاطبهم يرى مفتاحَ بلدٍ ليس بلدَه، فيكتب رقمَه فيُرفض بلا أن
 * يفهم لماذا. فصار في الثلاث: الدخول والتسجيل والاستعادة.
 *
 * **ولا يظهر حيث لا خيار**: سوقٌ واحدٌ في `/config` يعني منتقياً بزرٍّ واحد —
 * وهو سؤالٌ بلا جواب. والشكلُ زرّان لا قائمةٌ منسدلة: خياران اثنان يُقرآن
 * معاً، والمنسدلةُ تُخفي أحدَهما خلف لمسة.
 */

import type { CountryCode } from "@/api/types";
import { cn } from "@/lib/utils";

/** **بيتُ التسميات هنا**: كانت في `screens/Register.tsx` وحدَها، ومنتقٍ في ثلاث
 *  شاشاتٍ يقرأ اسمَ دولةٍ من شاشةِ تسجيلٍ هو بيتٌ ثانٍ ينتظر أن يفترق. */
const COUNTRY_LABEL: Record<CountryCode, string> = {
  JO: "الأردن",
  LY: "ليبيا",
};

export function CountryPicker({
  country,
  countries,
  onChange,
  disabled,
}: {
  country: CountryCode;
  countries: CountryCode[];
  onChange: (value: CountryCode) => void;
  disabled?: boolean;
}) {
  if (countries.length < 2) return null;

  return (
    <div>
      <span className="label">الدولة</span>
      <div className="flex gap-8">
        {countries.map((code) => (
          <button
            key={code}
            type="button"
            disabled={disabled}
            onClick={() => onChange(code)}
            className={cn(
              "pressable flex-1 rounded-13 border p-12 text-13.5 font-semibold",
              code === country
                ? "border-ink bg-surface-2 text-ink"
                : "border-line text-ink",
            )}
          >
            {COUNTRY_LABEL[code]}
          </button>
        ))}
      </div>
    </div>
  );
}
