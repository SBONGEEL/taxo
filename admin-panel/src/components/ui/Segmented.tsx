/** **المبدّلُ المقطَّع** — «اليوم · الأسبوع · الشهر» كما رسمته C09: وعاءُ السطح، والمختارُ ورقٌ على الإسفلت وحبرٌ على الحجر.
 *
 * **ولمَ ليس `Pills`**: الحبّاتُ فلترةُ قائمةٍ تلتفّ، **وهذا اختيارٌ واحدٌ من قليلٍ يغيّر معنى الأرقام كلِّها** — فيُرسم كتلةً
 * واحدةً في رأس الصفحة، **ويُعلَن `radiogroup`** فيُقرأ أيُّها قائمٌ لا من اللون (قرارُ المالك 2026-08-28).
 */

export function Segmented<T extends string>({
  value,
  options,
  onPick,
  label,
}: {
  value: T;
  options: { key: T; label: string }[];
  onPick: (key: T) => void;
  /** اسمُ المجموعة لقارئ الشاشة («المدى»). */
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="ad-seg">
      {options.map((option) => (
        <button
          key={option.key}
          type="button"
          role="radio"
          aria-checked={value === option.key}
          onClick={() => onPick(option.key)}
          className={value === option.key ? "ad-seg-opt on" : "ad-seg-opt"}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
