/** ثلاثةُ حقولٍ لها بيتٌ واحد: **مال · تاريخ · مدّة** (قرارُ المالك
 *  2026-09-01).
 *
 * **العلّةُ واحدة**: ثلاثةُ مفاهيمَ تُكتب اليومَ بيدٍ في كلِّ شاشةٍ على حدة،
 * **فتفترق الشاشاتُ في صياغة الشيء نفسِه** — وهو الشكلُ الثامن يُصنع بيد.
 */

import { useId } from "react";

import { useFieldError } from "@/lib/form-errors";
import { currencyLabel } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Currency } from "@/api/types";

/** حقلُ مالٍ واحدٌ لكلِّ شاشة — **يعرض العملةَ ويصوغ الصفرَ كما يصوغه النظام**.
 *
 * **ولا يحسب شيئاً**: §14 يحصر حسابَ المال في الخلفية، **و`check:money-math`
 * يقرأ العُقَد** — فهذا حقلُ إدخالٍ لا آلةٌ حاسبة.
 *
 * **والقيمةُ نصٌّ لا رقم**: `NUMERIC(12,3)` لا يُمثَّل في `number` جافاسكربت
 * بلا خسارة، **وتحويلُه ذهاباً وإياباً يُنتج `0.1+0.2`** — فالنصُّ يُرسل كما
 * كُتب وتتولّاه الخلفية.
 *
 * **والصفرُ `0.000` لا `0`** (الشكلُ السابع، `tests/money_format.py`): يُصاغ
 * **عند فقدان التركيز لا عند كلِّ حرف** — من يكتب «5» يجدها صارت «5.000» تحت
 * إصبعه فلا يستطيع كتابة «5.5».
 */
export function MoneyField({
  label,
  value,
  onChange,
  currency,
  name,
  error,
  disabled = false,
  hint,
}: {
  label?: string;
  value: string;
  onChange: (next: string) => void;
  /** رمزُ العملة — **يُمرَّر ولا يُخمَّن**، والسوقُ هو من يعرفه. */
  currency: Currency | string;
  name?: string;
  error?: string | null;
  disabled?: boolean;
  hint?: string;
}) {
  const generated = useId();
  const id = name ?? generated;
  const fromContext = useFieldError(name);
  const reason = error ?? fromContext;

  return (
    <div>
      {label ? (
        <label className="label" htmlFor={id}>
          {label}
        </label>
      ) : null}
      <div
        className={cn(
          "flex items-center gap-8 rounded-10 border bg-surface-2 px-12",
          reason ? "border-danger" : "border-line",
        )}
      >
        <input
          id={id}
          name={name}
          type="text"
          inputMode="decimal"
          dir="ltr"
          disabled={disabled}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onBlur={() => {
            const text = value.trim();
            if (!text) return;
            const parsed = Number(text.replace(",", "."));
            if (!Number.isFinite(parsed)) return;
            // **الصياغةُ عند الخروج وحدَه** — وثلاثُ خاناتٍ كصيغة القاعدة
            onChange(parsed.toFixed(3));
          }}
          className="w-full bg-transparent py-8 text-start text-12.5 text-ink outline-none"
          aria-invalid={reason ? true : undefined}
        />
        <span className="shrink-0 text-11.5 font-semibold text-muted">
          {currencyLabel(currency)}
        </span>
      </div>
      {hint && !reason ? (
        <p className="mt-6 text-11 leading-note text-muted">{hint}</p>
      ) : null}
      {reason ? <p className="mt-6 text-12 text-danger">{reason}</p> : null}
    </div>
  );
}

/** حقلُ تاريخٍ — **من تقويمِ المتصفّح لا بكتابةٍ حرّة**.
 *
 * **العلّةُ**: «٢٠٢٦-٩-١» و«1/9/2026» و«٠١-٠٩-٢٠٢٦» ثلاثةُ نصوصٍ لتاريخٍ
 * واحد، **واثنان منها يُرفضان في الخلفية** فيقرأ المشرفُ خطأً لا يفهمه.
 * `type="date"` يعطي منتقياً أصلياً ويُرسل `YYYY-MM-DD` دائماً.
 *
 * **والخاناتُ لاتينيةٌ بحكم المتصفح** — وهو ما تريده القاعدةُ أصلاً.
 */
export function DateField({
  label,
  value,
  onChange,
  name,
  min,
  max,
  error,
  disabled = false,
  hint,
}: {
  label?: string;
  /** `YYYY-MM-DD` أو فراغ. */
  value: string;
  onChange: (next: string) => void;
  name?: string;
  min?: string;
  max?: string;
  error?: string | null;
  disabled?: boolean;
  hint?: string;
}) {
  const generated = useId();
  const id = name ?? generated;
  const fromContext = useFieldError(name);
  const reason = error ?? fromContext;

  return (
    <div>
      {label ? (
        <label className="label" htmlFor={id}>
          {label}
        </label>
      ) : null}
      <input
        id={id}
        name={name}
        type="date"
        dir="ltr"
        value={value}
        min={min}
        max={max}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className={cn("fld text-start", reason && "border-danger")}
        aria-invalid={reason ? true : undefined}
      />
      {hint && !reason ? (
        <p className="mt-6 text-11 leading-note text-muted">{hint}</p>
      ) : null}
      {reason ? <p className="mt-6 text-12 text-danger">{reason}</p> : null}
    </div>
  );
}

/** وحداتُ المدّة — **والقيمةُ المرسَلةُ ثوانٍ كما تفهمها الخلفية**. */
const UNITS: { key: string; label: string; seconds: number }[] = [
  { key: "minute", label: "دقيقة", seconds: 60 },
  { key: "hour", label: "ساعة", seconds: 3600 },
  { key: "day", label: "يوم", seconds: 86_400 },
  { key: "week", label: "أسبوع", seconds: 604_800 },
];

/** يختار أكبرَ وحدةٍ تقسم العددَ بلا كسر — **فـ`604800` تُعرض «أسبوع ١»**
 *  لا «٦٠٤٨٠٠ ثانية**. */
function split(seconds: number): { count: string; unit: string } {
  for (const unit of [...UNITS].reverse()) {
    if (seconds > 0 && seconds % unit.seconds === 0) {
      return { count: String(seconds / unit.seconds), unit: unit.key };
    }
  }
  return { count: seconds ? String(Math.round(seconds / 60)) : "", unit: "minute" };
}

/** حقلُ مدّة — **عددٌ ووحدة، لا رقمُ ثوانٍ يُحسب بالرأس**.
 *
 * **العلّةُ مقيسةٌ في هذا المشروع**: `86400` تُقرأ «يوم» بعد حسبة، و`604800`
 * تُقرأ خطأً «أسبوعين» عند التعب. **والخطأُ هنا يظهر بعد أسبوعٍ لا فوراً.**
 *
 * **والقيمةُ على السلك ثوانٍ كما هي** — لا يُغيَّر عقدُ الخلفية.
 */
export function DurationField({
  label,
  seconds,
  onChange,
  error,
  disabled = false,
  hint,
}: {
  label?: string;
  seconds: number;
  onChange: (next: number) => void;
  error?: string | null;
  disabled?: boolean;
  hint?: string;
}) {
  const id = useId();
  const current = split(seconds);
  const unit = UNITS.find((u) => u.key === current.unit) ?? UNITS[0];

  function emit(count: string, unitKey: string) {
    const factor = UNITS.find((u) => u.key === unitKey)?.seconds ?? 60;
    const parsed = Number(count);
    onChange(Number.isFinite(parsed) && parsed > 0 ? Math.round(parsed * factor) : 0);
  }

  return (
    <div>
      {label ? (
        <label className="label" htmlFor={id}>
          {label}
        </label>
      ) : null}
      <div className="flex gap-8">
        <input
          id={id}
          type="number"
          min={0}
          dir="ltr"
          disabled={disabled}
          value={current.count}
          onChange={(event) => emit(event.target.value, unit.key)}
          className={cn("fld w-full text-start", error && "border-danger")}
        />
        <select
          disabled={disabled}
          value={unit.key}
          onChange={(event) => emit(current.count || "1", event.target.value)}
          className="fld w-auto shrink-0"
          aria-label="وحدة المدّة"
        >
          {UNITS.map((option) => (
            <option key={option.key} value={option.key}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
      {hint && !error ? (
        <p className="mt-6 text-11 leading-note text-muted">{hint}</p>
      ) : null}
      {error ? <p className="mt-6 text-12 text-danger">{error}</p> : null}
    </div>
  );
}
