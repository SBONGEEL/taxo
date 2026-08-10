/** حقل الهاتف: بادئةُ الدولة أمامه، والأرقام لاتينية دائماً.
 *
 * **البادئة من `GET /config`** (`countries[].dial_code`) لا من الواجهة:
 * قيمةٌ مكتوبةٌ في تطبيقين تفترق عن `core/phone.py` يوماً، وتفترق عن نفسها
 * في التطبيقين قبله.
 *
 * والصفرُ البادئ يُحذف فور كتابته: من يكتب `0791234567` وأمامه `+962` يقصد
 * `+962791234567`.
 *
 * ومنتقي الدولة **اختياري**: شاشتا الدخول والاستعادة بلا منتقٍ (كما في
 * التصميم، ودولتُهما `default_country_code`)، والتسجيلُ والتحويل يختاران.
 */

import type { CountryCode } from "@/api/types";
import { Field } from "@/components/ui/Field";
import { usePhoneCountry } from "@/lib/config";
import { COUNTRY_LABEL, toNational } from "@/lib/phone";

export function PhoneInput({
  phone,
  country,
  onPhoneChange,
  onCountryChange,
  countries,
  error,
  disabled,
  showCountry = true,
}: {
  phone: string;
  country: CountryCode;
  onPhoneChange: (value: string) => void;
  onCountryChange: (value: CountryCode) => void;
  countries: CountryCode[];
  error?: string | null;
  disabled?: boolean;
  showCountry?: boolean;
}) {
  const { dialCode, nationalLength } = usePhoneCountry(country);
  return (
    <div className="space-y-3">
      {showCountry ? (
        <div>
          <label className="label" htmlFor="country">
            الدولة
          </label>
          <select
            id="country"
            className="field appearance-none"
            value={country}
            disabled={disabled}
            onChange={(event) =>
              onCountryChange(event.target.value as CountryCode)
            }
          >
            {countries.map((code) => (
              <option key={code} value={code}>
                {COUNTRY_LABEL[code]}
              </option>
            ))}
          </select>
        </div>
      ) : null}

      <Field
        label="رقم الهاتف"
        type="tel"
        inputMode="tel"
        autoComplete="tel"
        dir="ltr"
        className="text-start"
        value={phone}
        disabled={disabled}
        error={error}
        prefix={<span dir="ltr">+{dialCode}</span>}
        maxLength={nationalLength}
        placeholder={"7".padEnd(nationalLength, "X")}
        onChange={(event) =>
          onPhoneChange(toNational(event.target.value, dialCode))
        }
      />
    </div>
  );
}
