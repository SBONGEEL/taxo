/** **مُختارُ الدولة في حقل الهاتف** (SPEC §٧٤-أ/٤ — لوحاتُ «مختار الدولة» في Claude Design): زرٌّ في الحقل وورقةُ الدول.
 *
 * **والمنطقُ في `useAuthCountry(mode)`** (ما يُعرض وما يُختار والافتراض)، **والشكلُ في نظام التصميم** (`AuthPhone` · `AuthCountrySheet`) —
 * وهذا يصلهما: يفتح الورقة ويغلقها، ويكتب نصوصَها بحسب الشاشة. **والدخولُ «دولةُ حسابك»** — كلُّ دولة؛ **والتسجيلُ «اختر دولتك»** —
 * تُختار مرّةً واحدة.
 */
import { useCallback, useState } from "react";
import type { ReactNode } from "react";

import type { CountryCode } from "@/api/types";
import type { AuthMode } from "@/lib/config";
import { tr } from "@/lib/i18n";
import { AuthCountrySheet } from "@/taxo2";

type Auth = {
  country: CountryCode;
  name: string;
  options: Array<{ code: CountryCode; name: string; dial: string; soon: boolean }>;
  setCountry: (value: CountryCode) => void;
};

export function useCountryPick(
  auth: Auth,
  mode: AuthMode,
  options: { feminine?: boolean; disabled?: boolean } = {},
): { trigger: { code: string; name: string; onOpen: () => void; disabled?: boolean }; sheet: ReactNode } {
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  const signup = mode === "signup";
  const sheet = (
    <AuthCountrySheet
      open={open}
      title={signup ? (options.feminine ? tr("اختاري دولتك") : tr("اختر دولتك")) : tr("دولةُ حسابك")}
      sub={signup ? tr("منها عملتُك وأسعارُك وطرقُ دفعك — وتُختار مرّةً واحدة.") : tr("اختر الدولةَ التي سجّلت فيها رقمك.")}
      note={
        signup
          ? tr("عندك حسابٌ في دولةٍ أخرى؟ ادخل منه — الدخولُ متاحٌ من كلِّ دولة.")
          : tr("في الدخول كلُّ الدول — فحسابُك يدخل ولو لم تُفتح دولتُه للتسجيل بعد.")
      }
      options={auth.options}
      value={auth.country}
      onPick={(code) => {
        auth.setCountry(code as CountryCode);
        setOpen(false);
      }}
      onClose={close}
    />
  );
  return {
    trigger: { code: auth.country, name: auth.name, onOpen: () => setOpen(true), disabled: options.disabled },
    sheet,
  };
}
