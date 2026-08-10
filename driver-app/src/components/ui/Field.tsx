/** حقلٌ بتسميته — `design/DESIGN.md` §2.3.
 *
 * التسمية **فوق** الحقل دائماً (12px، `--mut`، مسافة 6px تحتها)، والحقل
 * نفسه `.fld` في `index.css`. ولا حالةَ خطأ مرسومةً على الحقل في التصميم:
 * نصُّ الخطأ يظهر تحت النموذج بلون `--dng` (انظر `Feedback`).
 */

import type { InputHTMLAttributes } from "react";

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
