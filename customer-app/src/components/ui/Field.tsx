import { forwardRef, useId } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

// `prefix` موجودٌ في `InputHTMLAttributes` بمعنى آخر (سِمة HTML قديمة نوعُها
// `string`)، فيُستبعد قبل التوسيع بدل أن يُعاد تعريفه فوقه
interface FieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "prefix"> {
  label?: string;
  hint?: ReactNode;
  error?: string | null;
  /** لاحقةٌ وسابقةٌ داخل الحقل: رمز الدولة، العملة، زر إظهار كلمة المرور… */
  suffix?: ReactNode;
  prefix?: ReactNode;
}

export const Field = forwardRef<HTMLInputElement, FieldProps>(
  ({ label, hint, error, suffix, prefix, className, id, dir, ...props }, ref) => {
    const generated = useId();
    const inputId = id ?? generated;

    return (
      <div className="w-full">
        {label ? (
          <label className="label" htmlFor={inputId}>
            {label}
          </label>
        ) : null}

        {/* **`dir` على الغلاف لا على الحقل وحده.**
         *
         * الحشوةُ (`ps`/`pe`) تُحسب باتجاه **الحقل**، وموضعُ اللاحقة
         * (`start`/`end`) باتجاه **أبيه**. فحقلٌ `dir="ltr"` داخل صفحةٍ عربية
         * كان يحجز الحشوة يميناً ويضع اللاحقة يساراً — فتقع «د.أ» فوق المبلغ
         * المكتوب، ويظهر رمزُ الدولة **بعد** الرقم في حقل الهاتف بدل أن
         * يسبقه. ووضعُ الاتجاه على الغلاف يجعل الطرفين يقرآن الاتجاه نفسه. */}
        <div className="relative flex items-center" dir={dir}>
          {prefix ? (
            <span className="pointer-events-none absolute start-12 text-muted">{prefix}</span>
          ) : null}
          <input
            ref={ref}
            id={inputId}
            className={cn(
              "field",
              // الحشوةُ تحجز عرضَ السابقة/اللاحقة **وفراغاً بعدها**: «‎+962»
              // بمقاس 16 نحوُ ٣٨px يبدأ عند 12، فأربعون كانت تُقصّ الرقمَ
              // على حرفه الأول
              prefix && "ps-52",
              suffix && "pe-64",
              error && "border-danger focus:border-danger focus:ring-danger",
              className,
            )}
            aria-invalid={error ? true : undefined}
            dir={dir}
            {...props}
          />
          {suffix ? (
            <span className="absolute end-12 text-14 text-muted">{suffix}</span>
          ) : null}
        </div>

        {error ? (
          <p className="mt-6 text-14 text-danger">{error}</p>
        ) : hint ? (
          <p className="mt-6 text-14 text-muted">{hint}</p>
        ) : null}
      </div>
    );
  },
);
Field.displayName = "Field";
