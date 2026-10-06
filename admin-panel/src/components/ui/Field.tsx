/** حقلٌ بتسميته — **حقلُ TAXO 2.0** (`.fld` في `t2/kit.css`: ٤٤ بزاويةٍ ١٢ على غائر البطاقة، وحافّةٌ بالجمر عند التركيز).
 *
 * التسمية **فوق** الحقل دائماً، والخطأُ **تحته** بأيقونته.
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
import { DateField, Icon, Switch as Knob } from "@/taxo2";

/** **سببُ الخطأ تحت حقله** (§٦٢/٢٠) — أيقونةٌ ممتلئةٌ ونصٌّ بلون الخطأ، **كسطر الخطأ في الهوية**. */
export function FieldError({ id, message }: { id?: string; message: string }) {
  return (
    <p id={id} className="ad-err">
      <Icon name="error" fill />
      <span>{message}</span>
    </p>
  );
}

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  /** سببُ الرفض — و`null` يعني لا خطأ. يُمرَّر أو يُلتقط من `FormErrors`. */
  error?: string | null;
}

export function Field({ label, className, id, error, ...rest }: Props) {
  // **والتاريخُ من اليسار دائماً** (§39٫١٢٫٢، قِيس 2026-09-03): `type="date"`
  // يرسم منتقيَ المتصفّح بخاناتٍ لاتينية، **وثلاثُ شاشاتٍ كانت تكتب `dir`
  // وثلاثٌ تنساه** — `PromoCodes` يمرّرها و`VehicleSkins` و`Storefront`
  // و`Drivers` لا. **فافترق شكلُ الشيء الواحد**، وهو الشكلُ الثامن يُصنع بيد.
  // **والبيتُ يعرف الجواب فلا يكتبه كلُّ مستدعٍ**، ومن مرّر `dir` صراحةً يبقى
  // له ما مرّر.
  //
  // **ولم يعد في اللوحة حقلُ تاريخٍ أصليٌّ ظاهر** (المرحلةُ الثانية من TAXO 2.0): الخمسةُ صارت `DateInput` تحت — فحتى بـ`dir`
  // قِيست خاناتُه معكوسة («ةنس/رهش/موي»). **والفرعُ باقٍ** لمن يكتب `type="date"` بعدُ، فلا يرجع ما أُصلح.
  const dir = rest.type === "date" ? (rest.dir ?? "ltr") : rest.dir;
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
        className={cn("fld", reason && "invalid", className)}
        aria-invalid={reason ? true : undefined}
        aria-describedby={reason ? `${inputId}-error` : undefined}
        {...rest}
        dir={dir}
      />
      {reason ? <FieldError id={`${inputId}-error`} message={reason} /> : null}
    </div>
  );
}

/** **حقلُ التاريخ (والموعد) بتسميته** — `DateField` الهوية بدل `<input type="date">` الظاهر (§٦٢/٢٠).
 *
 * **لماذا لا `Field type="date"`**: في صفحةٍ عربيّةٍ يرسم المتصفّحُ خاناتِه «يوم/شهر/سنة» بحروفٍ معكوسة — **قِيس «ةنس/رهش/موي»
 * في الدرج ولو بـ`dir="ltr"`** (المرحلةُ الأولى). فالظاهرُ زرٌّ بلغة الحقل، **والمنتقي منتقي النظام نفسُه**.
 *
 * **والعقدُ كما كان**: القيمةُ نصُّ `YYYY-MM-DD` (أو `YYYY-MM-DDTHH:MM` للموعد) تُرسل كما هي، **والخطأُ يجد حقلَه بالاسم**
 * كـ`Field` (`useFieldError(name)`) — فالحدُّ أحمرُ والسببُ تحته. والتسميةُ مربوطةٌ بالزرّ (`htmlFor`): نقرُها يفتح المنتقي. */
export function DateInput({
  label,
  name,
  id,
  value,
  onChange,
  kind = "date",
  min,
  max,
  error,
}: {
  label: string;
  /** اسمُ الحقل في مخطط الخلفية — به يجد خطأه */
  name?: string;
  id?: string;
  value: string;
  onChange: (value: string) => void;
  kind?: "date" | "datetime-local";
  min?: string;
  max?: string;
  /** سببُ الرفض — و`null` يعني لا خطأ. يُمرَّر أو يُلتقط من `FormErrors`. */
  error?: string | null;
}) {
  const generated = useId();
  const inputId = id ?? name ?? generated;
  const fromContext = useFieldError(name);
  const reason = error ?? fromContext;
  return (
    <div>
      <label className="label" htmlFor={inputId}>
        {label}
      </label>
      <DateField
        id={inputId}
        kind={kind}
        value={value}
        onChange={onChange}
        label={label}
        min={min}
        max={max}
        className={reason ? "invalid" : undefined}
      />
      {reason ? <FieldError id={`${inputId}-error`} message={reason} /> : null}
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
    // **الزرُّ هو المفتاحُ عند قارئ الشاشة، والرسمُ مفتاحُ الهوية** (`taxo2/Switch`: ٤٨×٢٨، مشتعلٌ بالجمر)
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="ad-switch"
    >
      <Knob on={checked} />
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
      className="ad-check-row"
    >
      <span aria-hidden className={checked ? "ad-check on" : "ad-check"}>
        <Icon name="check" />
      </span>
      <span className="ad-check-text">{children}</span>
    </button>
  );
}
