/** حقلُ الهاتف: بادئةُ الدولة ثابتةٌ أمامه، والرقم الوطني وحده يُكتب.
 *
 * **البادئة من `GET /config`** (`countries[].dial_code`) لا من الواجهة، ودولةُ
 * الشاشة هي `default_country_code` — لا منتقيَ دولٍ كما في التصميم، ولا حسابَ
 * بعدُ لتُعرف دولتُه منه.
 *
 * والصفرُ البادئ يُحذف فور كتابته: من يكتب `0791234567` وأمامه `+962` يقصد
 * `+962791234567`. وهذا ما كان يرتدّ سابقاً برسالة «أرسل الرقم بالصيغة
 * الدولية» على من كتب رقمه كما يكتبه كل يوم.
 *
 * الشكلُ من `design/DESIGN.md` §2.3: التسمية 12px فوق الحقل، والحقل `.fld`
 * — والبادئة داخله بلون `--mut` يفصلها خطٌّ رأسي بلون `--brd`.
 */

import type { CountryCode } from "@/api/types";
import { usePhoneCountry } from "@/lib/config";
import { toNational } from "@/lib/phone";

interface Props {
  value: string;
  onChange: (national: string) => void;
  label?: string;
  disabled?: boolean;
  autoFocus?: boolean;
  /** دولةٌ صريحة — لشاشة التسجيل وحدها، وفيها منتقي دولةٍ بحكم التصميم. */
  country?: CountryCode;
}

export function PhoneField({
  value,
  onChange,
  label = "رقم الهاتف",
  disabled,
  autoFocus,
  country,
}: Props) {
  const { dialCode, nationalLength } = usePhoneCountry(country);

  return (
    <div>
      <label className="label" htmlFor="phone">
        {label}
      </label>
      <div
        dir="ltr"
        className="flex w-full items-stretch overflow-hidden rounded-13 border border-line bg-surface focus-within:border-ink"
      >
        <span className="flex select-none items-center border-e border-line px-13 text-14.5 text-muted">
          +{dialCode}
        </span>
        <input
          id="phone"
          name="phone"
          type="tel"
          inputMode="numeric"
          autoComplete="tel-national"
          autoFocus={autoFocus}
          disabled={disabled}
          // طولُ الرقم الوطني من الخلفية كذلك — لا تسعةٌ مكتوبةٌ هنا
          maxLength={nationalLength}
          placeholder={"7".padEnd(nationalLength, "X")}
          value={value}
          onChange={(event) =>
            onChange(toNational(event.target.value, dialCode))
          }
          className="w-full bg-transparent px-15 py-13 text-14.5 text-ink outline-none placeholder:text-muted disabled:opacity-60"
        />
      </div>
    </div>
  );
}
