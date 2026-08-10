/** خانات الرمز — `design/DESIGN.md` §2.3: `58×64`، نصف قطر 14، خطّ 24/700،
 * فجوة 10، والصفُّ `dir="ltr"` بهامش `34px 0`.
 *
 * حقلٌ واحد شفافٌ فوق الخانات لا حقلٌ لكل خانة: لوحةُ المفاتيح تُفتح مرةً،
 * ولصقُ رمزٍ من رسالةٍ يملأ الكل، و`autocomplete="one-time-code"` يعمل —
 * وثلاثةٌ من هذه تنكسر مع حقولٍ منفصلة.
 *
 * وعددُ الخانات **من الخلفية** (`config.auth.otp_length`) لا أربعةٌ ثابتة
 * كما في النموذج: طولُ الرمز قرارُ المزود، وأربعةٌ مكتوبةٌ في الواجهة تكسر
 * تبديلَه بلا نشر.
 */

import { useId, useRef } from "react";

import { arabicDigits } from "@/lib/utils";

interface Props {
  value: string;
  onChange: (value: string) => void;
  length: number;
  disabled?: boolean;
}

export function OtpBoxes({ value, onChange, length, disabled }: Props) {
  const inputId = useId();
  const input = useRef<HTMLInputElement>(null);

  return (
    <div className="relative my-34">
      <div dir="ltr" className="flex justify-center gap-10">
        {Array.from({ length }, (_, index) => (
          <div
            key={index}
            aria-hidden
            className="flex h-64 w-58 items-center justify-center rounded-14 border border-line bg-surface text-24 font-bold text-ink"
          >
            {value[index] ? arabicDigits(value[index]) : ""}
          </div>
        ))}
      </div>

      <input
        id={inputId}
        ref={input}
        aria-label="رمز التحقق"
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={length}
        disabled={disabled}
        value={value}
        onChange={(event) => onChange(event.target.value.replace(/\D/g, "").slice(0, length))}
        className="absolute inset-0 h-full w-full cursor-pointer bg-transparent text-transparent caret-transparent outline-none"
      />
    </div>
  );
}
