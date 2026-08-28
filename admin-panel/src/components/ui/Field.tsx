/** حقلٌ بتسميته — `design/DESIGN.md` §2.3.
 *
 * التسمية **فوق** الحقل دائماً (12px، `--mut`، مسافة 6px تحتها)، والحقل
 * نفسه `.fld` في `index.css`.
 *
 * **وللحقل حالةُ خطأٍ منذ عقد الأخطاء** (SPEC ١٧.٧). وكان التصميمُ يضع نصَّ
 * الخطأ تحت النموذج كلِّه — وهو صحيحٌ لخطأٍ يخصّ الطلبَ كلَّه («تعذّر
 * الاتصال»)، وخاطئٌ لخطأٍ يخصّ **حقلاً بعينه**: من رُفض حقلٌ من أربعين حقلاً في
 * شاشة الإعدادات يقرأ سطراً أحمرَ ولا يعرف أيَّها. وهو نفسُ التغيير الذي وقع في
 * التطبيقين بعد تجربةٍ على هاتف، فهذا **لحاقٌ بأخويه** لا انحرافٌ عن التصميم.
 *
 * **والوسمُ يقع بالاسم لا بالترتيب**: الحقلُ يعلن `name` مطابقاً لاسم الحقل في
 * مخطط الخلفية، فيجد الخطأُ حقلَه بلا خريطةٍ تُكتب في كل شاشة وتفترق عن الشاشة
 * أوّلَ تعديل.
 */

import { useId } from "react";
import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

import { useFieldError } from "@/lib/form-errors";
import { cn } from "@/lib/utils";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  /** سببُ الرفض — و`null` يعني لا خطأ. يُمرَّر أو يُلتقط من `FormErrors`. */
  error?: string | null;
}

export function Field({ label, className, id, error, ...rest }: Props) {
  // **مُعرّفٌ مولَّدٌ حين لا يُمرَّر**: بغيره يصير `htmlFor={undefined}` فلا
  // تُربَط التسميةُ بحقلها — نقرُ التسمية لا يركّز الحقل، وقارئُ الشاشة يقرأ
  // حقلاً بلا اسم. وكانت خمسةٌ وعشرون من تسعةٍ وعشرين حقلاً في اللوحة كذلك،
  // لأن أغلبَ المستدعين لا يمرّرون `id` ولا `name`. و`useId` من React موجودٌ
  // لهذا بعينه، فالإصلاحُ في المكوّن يصلح كلَّ مستدعٍ بلا لمسه
  const generated = useId();
  const inputId = id ?? rest.name ?? generated;
  // **يُقرأ من السياق حين لا يُمرَّر**: فالشاشةُ لا تكتب خريطةً، والحقلُ الذي
  // يعلن اسمَه يجد خطأه وحدَه
  const fromContext = useFieldError(rest.name);
  const reason = error ?? fromContext;
  return (
    <div>
      {label ? (
        <label className="label" htmlFor={inputId}>
          {label}
        </label>
      ) : null}
      <input
        id={inputId}
        // الحدُّ الأحمر يقول «هنا»، والنصُّ يقول «لماذا» — وأحدهما بلا الآخر
        // إمّا لونٌ بلا سبب أو سببٌ لا يُعرف موضعه
        className={cn("fld", reason && "border-danger", className)}
        aria-invalid={reason ? true : undefined}
        aria-describedby={reason ? `${inputId}-error` : undefined}
        {...rest}
      />
      {reason ? (
        <p id={`${inputId}-error`} className="mt-6 text-12 text-danger">
          {reason}
        </p>
      ) : null}
    </div>
  );
}

/** قائمةٌ منسدلة بنفس هيئة الحقل — التصميم لا يرسم `select` منفصلاً. */
export function Select({
  label,
  className,
  id,
  children,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement> & { label?: string }) {
  const generated = useId();
  const inputId = id ?? rest.name ?? generated;
  return (
    <div>
      {label ? (
        <label className="label" htmlFor={inputId}>
          {label}
        </label>
      ) : null}
      <select id={inputId} className={cn("fld", className)} {...rest}>
        {children}
      </select>
    </div>
  );
}

/** مربّع الاختيار — `DESIGN.md` §2.5: `18×18` نصف قطر 5، والمُختار `--acc`
 * بعلامةٍ `--inv`.
 *
 * مبنيٌّ لا `accent-color` على `input` أصلي: اسمُ اللون في اللوحة `accent`
 * وهو تعبئةُ الزرّ الأساسي، فـ`accent-ink` صنفٌ يشير إلى لونٍ آخر تماماً
 * (`accent-ink` = `--inv`) — تصادمُ أسماءٍ يُخرج مربّعاً بلون الخلفية.
 */
/** **مفتاحٌ يقول حالَه في سمةٍ لا في لون** (قرارُ المالك 2026-08-28).
 *
 * كانت مفاتيحُ اللوحة `<button>` عاريةً بـ`aria-label` وحدَه: **الحالُ لونُ
 * الخلفية**. فقارئُ الشاشة يقول «زرّ: تفعيل العمولة» ولا يقول **أمفعّلةٌ
 * هي أم لا** — ومن لا يرى اللونَ لا يعرف ما سيفعله ضغطُه. **وقياسُها
 * اضطُرّ إلى النقر ومراقبة الخلفية**، وهو قياسٌ يغيّر ما يقيسه.
 *
 * **و`role="switch"` لا `checkbox`**: كلاهما يحمل `aria-checked`، لكنّ
 * الأولَ يُنطق «مفتاح» — وهو ما ترسمه الشاشةُ فعلاً. **وبيتٌ واحدٌ لا ثلاثة**
 * كي لا يُكتب الرابعُ عارياً كما كُتبت الثلاثة.
 */
export function Switch({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  /** ما يُنطق قبل الحال — والحالُ يأتي من `aria-checked` لا منه. */
  label: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        "relative block h-27 w-46 flex-none rounded-full transition-colors disabled:opacity-60",
        checked ? "bg-ok" : "bg-line",
      )}
    >
      <span
        aria-hidden
        className={cn(
          "absolute top-3 block size-21 rounded-full bg-surface transition-all",
          checked ? "start-22" : "start-3",
        )}
      />
    </button>
  );
}

export function Checkbox({
  checked,
  onChange,
  children,
  disabled,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
  children: ReactNode;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="checkbox"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="flex w-full items-start gap-9 text-start disabled:opacity-60"
    >
      <span
        aria-hidden
        className={cn(
          "mt-2 flex size-18 flex-none items-center justify-center rounded-5 border text-11 font-bold",
          checked
            ? "border-accent bg-accent text-accent-ink"
            : "border-line text-transparent",
        )}
      >
        ✓
      </span>
      <span className="min-w-0">{children}</span>
    </button>
  );
}
