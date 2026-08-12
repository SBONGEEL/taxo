/** حقلٌ بتسميته — `design/DESIGN.md` §2.3.
 *
 * التسمية **فوق** الحقل دائماً (12px، `--mut`، مسافة 6px تحتها)، والحقل
 * نفسه `.fld` في `index.css`. ولا حالةَ خطأ مرسومةً على الحقل في التصميم:
 * نصُّ الخطأ يظهر تحت النموذج بلون `--dng` (انظر `Feedback`).
 */

import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export function Field({ label, className, id, ...rest }: Props) {
  const inputId = id ?? rest.name;
  return (
    <div>
      {label ? (
        <label className="label" htmlFor={inputId}>
          {label}
        </label>
      ) : null}
      <input id={inputId} className={cn("fld", className)} {...rest} />
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
  const inputId = id ?? rest.name;
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
