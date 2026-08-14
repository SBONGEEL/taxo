/** حقلٌ بتسميته — `design/DESIGN.md` §2.3.
 *
 * التسمية **فوق** الحقل دائماً (12px، `--mut`، مسافة 6px تحتها)، والحقل
 * نفسه `.fld` في `index.css`.
 *
 * **وخطأُ الحقل تحته لا تحت النموذج** (2026-08-14، بعد تجربةٍ على هاتف).
 * كان التصميم يضع نصَّ الخطأ تحت النموذج كلِّه — وهو صحيحٌ لخطأٍ يخصّ الطلبَ
 * كلَّه («تعذّر الاتصال»)، وخاطئٌ لخطأٍ يخصّ **حقلاً بعينه**: من كتب كلمةَ مرورٍ
 * قصيرة كان يرى زرَّ «متابعة» معطَّلاً بصمتٍ ولا يعرف أيُّ حقلٍ يمنعه. فصار
 * للحقل خطؤه، ويبقى `ErrorNote` تحت النموذج لما يخصّ الإرسال نفسَه.
 *
 * ونسخةُ تطبيق الراكب تحمل هذا منذ المرحلة 9 — فهذا **لحاقٌ بأخيه** لا انحراف.
 */

import type { InputHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  /** سببُ الرفض **لحظةَ الكتابة** — و`null` يعني لا خطأ. */
  error?: string | null;
}

export function Field({ label, error, className, id, ...rest }: Props) {
  const inputId = id ?? rest.name;
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
        className={cn("fld", error && "border-danger", className)}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${inputId}-error` : undefined}
        {...rest}
      />
      {error ? (
        <p id={`${inputId}-error`} className="mt-6 text-12 text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
