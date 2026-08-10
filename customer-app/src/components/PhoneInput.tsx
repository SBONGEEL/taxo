/** حقل الهاتف: رمز الدولة إلى جانبه، والأرقام لاتينية دائماً.
 *
 * الدولة تُختار هنا لا تُخمَّن: الخلفية تطبّع الرقم برمز الدولة المُرسل
 * (`core/phone.py::normalize_phone`)، و«٠٧٩…» بلا دولةٍ رقمان مختلفان في
 * سوقين.
 */

import type { CountryCode } from "@/api/types";
import { Field } from "@/components/ui/Field";
import { COUNTRY_LABEL, DIAL_CODE, digitsOnly } from "@/lib/phone";

export function PhoneInput({
  phone,
  country,
  onPhoneChange,
  onCountryChange,
  countries,
  error,
  disabled,
}: {
  phone: string;
  country: CountryCode;
  onPhoneChange: (value: string) => void;
  onCountryChange: (value: CountryCode) => void;
  countries: CountryCode[];
  error?: string | null;
  disabled?: boolean;
}) {
  return (
    <div className="space-y-3">
      <div>
        <label className="label" htmlFor="country">
          الدولة
        </label>
        <select
          id="country"
          className="field appearance-none"
          value={country}
          disabled={disabled}
          onChange={(event) => onCountryChange(event.target.value as CountryCode)}
        >
          {countries.map((code) => (
            <option key={code} value={code}>
              {COUNTRY_LABEL[code]}
            </option>
          ))}
        </select>
      </div>

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
        prefix={<span dir="ltr">+{DIAL_CODE[country]}</span>}
        placeholder="79 123 4567"
        onChange={(event) => onPhoneChange(digitsOnly(event.target.value))}
      />
    </div>
  );
}
