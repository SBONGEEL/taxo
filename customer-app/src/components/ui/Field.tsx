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
  ({ label, hint, error, suffix, prefix, className, id, ...props }, ref) => {
    const generated = useId();
    const inputId = id ?? generated;

    return (
      <div className="w-full">
        {label ? (
          <label className="label" htmlFor={inputId}>
            {label}
          </label>
        ) : null}

        <div className="relative flex items-center">
          {prefix ? (
            <span className="pointer-events-none absolute start-3 text-muted">{prefix}</span>
          ) : null}
          <input
            ref={ref}
            id={inputId}
            className={cn(
              "field",
              prefix && "ps-10",
              suffix && "pe-16",
              error && "border-danger focus:border-danger focus:ring-danger/30",
              className,
            )}
            aria-invalid={error ? true : undefined}
            {...props}
          />
          {suffix ? (
            <span className="absolute end-3 text-sm text-muted">{suffix}</span>
          ) : null}
        </div>

        {error ? (
          <p className="mt-1.5 text-sm text-danger">{error}</p>
        ) : hint ? (
          <p className="mt-1.5 text-sm text-muted">{hint}</p>
        ) : null}
      </div>
    );
  },
);
Field.displayName = "Field";
