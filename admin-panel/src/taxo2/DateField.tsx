/** حقلُ التاريخ (والموعد) — **عربيٌّ لا يتكسّر** (§٦٢/٢٠).
 *
 * **لماذا لا `<input type="date">` ظاهراً**: في صفحةٍ عربيّةٍ يرسم المتصفّحُ خاناتِه «يوم/شهر/سنة» بحروفٍ معكوسة — قِيس
 * «ةنس/رهش/موي» في متصفّح النظام (٢٠٢٦-١٠-٠٥، وثيقةُ الكبتن ومنتقي موعد الراكب). **فالظاهرُ زرٌّ بلغة الحقل**: تلميحٌ عربيٌّ
 * أو القيمةُ بأرقامٍ لاتينيةٍ من اليسار (يوم/شهر/سنة)، **والمنتقي منتقي النظام نفسُه** (`showPicker`) — فلا تقويمَ يُخترع.
 *
 * **والحقلُ الأصليُّ مخفيٌّ بصرياً لا مُزال**: قيمتُه ونطاقُه (`min`/`max`) وحدثُه كما كانت، فلا يتغيّر عقدُ الشاشة التي تستعمله.
 * والزرُّ هو ما يُعلَن لقارئ الشاشة (`aria-label` يحمل التسميةَ والقيمة).
 */
import { useRef } from "react";

type Kind = "date" | "datetime-local";

/** «2027-05-01» ← «01/05/2027»، و«2027-05-01T14:30» ← «01/05/2027 · 14:30» — **أرقامٌ لاتينيةٌ بلا محلّل**. */
function face(value: string, kind: Kind): string {
  const [date, time] = value.split("T");
  const [y, m, d] = date.split("-");
  if (!y || !m || !d) return value;
  const day = `${d}/${m}/${y}`;
  return kind === "datetime-local" && time ? `${day} · ${time.slice(0, 5)}` : day;
}

export function DateField({
  id,
  value,
  onChange,
  label,
  kind = "date",
  min,
  max,
  hint = kind === "date" ? "اختر التاريخ" : "اختر الموعد",
  className,
}: {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  /** اسمُ الحقل لقارئ الشاشة — يُضاف إليه ما اختير */
  label: string;
  kind?: Kind;
  min?: string;
  max?: string;
  hint?: string;
  className?: string;
}) {
  const native = useRef<HTMLInputElement>(null);
  const open = () => {
    const input = native.current;
    if (!input) return;
    try {
      input.showPicker();
    } catch {
      // متصفّحٌ بلا `showPicker` — التركيزُ يفتح منتقيَه في الهاتف
      input.focus();
    }
  };
  return (
    <span className={className ? `t2-date ${className}` : "t2-date"}>
      <button
        id={id}
        type="button"
        className="t2-date-face"
        onClick={open}
        aria-label={value ? `${label}: ${face(value, kind)}` : label}
      >
        <span className="t2-icon" aria-hidden="true">
          {kind === "date" ? "calendar_today" : "event"}
        </span>
        {value ? (
          <span className="t2-date-value" dir="ltr">
            {face(value, kind)}
          </span>
        ) : (
          <span className="t2-date-hint">{hint}</span>
        )}
      </button>
      <input
        ref={native}
        type={kind}
        className="t2-date-native"
        tabIndex={-1}
        aria-hidden="true"
        value={value}
        min={min}
        max={max}
        onChange={(event) => onChange(event.target.value)}
      />
    </span>
  );
}
