/** **حقلُ رقم المحوَّل إليه** (أمرُ المالك ٢٠٢٦-١١-٢٢، `design/OWNER-2026-11-22-CROSS-TRANSFER.md`).
 *
 * علمُ الدولة ومفتاحُها في أوّل الحقل (🇱🇾 ‎+218)، **والافتراضُ دولةُ المرسل**. اللمسةُ على العلم تفتح ورقةَ الدول (`AuthCountrySheet`،
 * ورقةُ التسجيل نفسُها بالبحث): **ليبيا ثمّ الأردن ثمّ الجزائر**. **وتُكتشف الدولةُ آليّاً** من رقمٍ يُكتب أو يُلصق برمزه (‎+962… · 00213…).
 *
 * **والدولُ المعروضةُ هي التي يمكن التحويلُ إليها الآن وحدَها**: دولةُ المرسل دائماً، **والأخرى حين يكون «التحويل بين الدول» مشتعلاً في
 * الدولتين** — والخلفيةُ تسأل المفتاحَ نفسَه وتردّ ما سواه (هذا يمنع الوصولَ إلى الردّ لا يستبدله). ورقمٌ يُلصق من دولةٍ غير متاحةٍ يقول ذلك
 * تحت الحقل ولا يُبنى بمفتاحٍ غير مفتاحه.
 *
 * **والمثالُ من قواعد الدولة المنشورة** (`mobile_prefixes` · `national_number_length` في `GET /config`): ليبيا 9XXXXXXXX، الأردن 7XXXXXXXX،
 * الجزائر 5/6/7XXXXXXXX — **من الجدول الذي تطبّع به الخلفيةُ نفسُه** لا من نصٍّ هنا.
 */

import { useState } from "react";

import type { CountryCode } from "@/api/types";
import { useConfig, usePhoneCountry } from "@/lib/config";
import { tr } from "@/lib/i18n";
import { COUNTRY_LABEL, digitsOnly } from "@/lib/phone";
import { useSession } from "@/lib/session";
import { AuthBlock, AuthCountrySheet, AuthPhone } from "@/taxo2";

/** **ترتيبُ الورقة بلفظ المالك**: ليبيا، الأردن، الجزائر */
const ORDER: CountryCode[] = ["LY", "JO", "DZ"];
const CROSS_FLAG = "cross_country_transfer_enabled";

/** **مثالُ رقمٍ بشكل الدولة** — البادئةُ الأولى ثمّ أرقامٌ متتالية، مجمّعةً كما تُكتب على البطاقات */
function sample(prefixes: string[], length: number): string {
  const digits = ((prefixes[0] ?? "") + "123456789").slice(0, length);
  return `${digits.slice(0, 2)} ${digits.slice(2, 5)} ${digits.slice(5)}`.trim();
}

export function useTransferPhone() {
  const { user } = useSession();
  const { config } = useConfig();
  const home: CountryCode = user?.country_code ?? config?.default_country_code ?? "JO";
  const entries = config?.countries ?? [];
  const on = (code: CountryCode) => entries.find((entry) => entry.country_code === code)?.features[CROSS_FLAG] === true;
  const allowed = ORDER.filter(
    (code) => code === home || (on(home) && on(code) && entries.some((entry) => entry.country_code === code)),
  );

  const [country, setCountry] = useState<CountryCode>(home);
  const [national, setNational] = useState("");
  /** رقمٌ لُصق برمز دولةٍ لا يُحوَّل إليها الآن */
  const [blocked, setBlocked] = useState<CountryCode | null>(null);
  const { dialCode, nationalLength, prefixes } = usePhoneCountry(country);

  function setPhone(input: string) {
    const digits = digitsOnly(input);
    const international = input.trim().startsWith("+") || digits.startsWith("00");
    let rest = digits.startsWith("00") ? digits.slice(2) : digits;
    if (international || rest.length > nationalLength) {
      const match = entries.find((entry) => entry.dial_code && rest.startsWith(entry.dial_code));
      if (match) {
        rest = rest.slice(match.dial_code.length).replace(/^0+/, "");
        if (allowed.includes(match.country_code)) {
          setCountry(match.country_code);
          setBlocked(null);
          setNational(rest.slice(0, match.national_number_length ?? 9));
        } else {
          setBlocked(match.country_code);
          setNational(rest.slice(0, 12));
        }
        return;
      }
    }
    setBlocked(null);
    setNational(rest.replace(/^0+/, "").slice(0, nationalLength));
  }

  const badStart = national.length > 0 && prefixes.length > 0 && !prefixes.some((p) => national.startsWith(p));
  const complete = dialCode !== null && blocked === null && !badStart && national.length === nationalLength;
  const problem =
    dialCode === null
      ? tr("مفتاحُ الدولة غير متاح الآن — أعد المحاولة بعد قليل.")
      : blocked !== null
        ? tr("التحويل إلى {0} غير متاحٍ الآن", { 0: COUNTRY_LABEL[blocked] })
        : badStart
          ? tr("رقمُ الجوّال في {0} يبدأ بـ{1}", { 0: COUNTRY_LABEL[country], 1: prefixes.join(tr(" أو ")) })
          : null;

  return {
    home,
    country,
    allowed,
    dialCode,
    nationalLength,
    prefixes,
    national,
    setPhone,
    pick: (code: CountryCode) => {
      setCountry(code);
      setBlocked(null);
      setNational("");
    },
    reset: () => {
      setNational("");
      setBlocked(null);
    },
    complete,
    problem,
    cross: country !== home,
    full: complete && dialCode !== null ? `+${dialCode}${national}` : null,
    example: sample(prefixes, nationalLength),
  };
}

export function TransferPhoneT2({
  draft,
  id,
  error,
  disabled = false,
}: {
  draft: ReturnType<typeof useTransferPhone>;
  id: string;
  error: string | null;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const { country, allowed, dialCode, nationalLength, prefixes, national, setPhone, complete, example } = draft;
  const { config } = useConfig();
  const hint =
    prefixes.length > 1
      ? tr("يبدأ بـ{0} — مثال: {1}", { 0: prefixes.join(tr(" أو ")), 1: example })
      : tr("مثال: {0}", { 0: example });
  return (
    <>
      <AuthBlock label={tr("رقم الهاتف")} htmlFor={id} error={error} hint={<span dir="ltr">{hint}</span>}>
        <AuthPhone
          id={id}
          type="tel"
          autoComplete="off"
          dial={dialCode}
          country={{ code: country, name: COUNTRY_LABEL[country], onOpen: () => setOpen(true), disabled }}
          value={national}
          placeholder={(prefixes.length > 1 ? prefixes.join("/") : prefixes[0] ?? "").padEnd(
            nationalLength + Math.max(0, prefixes.length - 1) * 2,
            "X",
          )}
          valid={complete}
          disabled={disabled || dialCode === null}
          invalid={Boolean(error)}
          onChange={(event) => setPhone(event.target.value)}
        />
      </AuthBlock>
      <AuthCountrySheet
        open={open}
        title={tr("اختر الدولة")}
        sub={allowed.length > 1 ? tr("التحويلُ إلى دولةٍ أخرى بسعر الصرف المعروض قبل التأكيد") : undefined}
        options={allowed.map((code) => ({
          code,
          name: COUNTRY_LABEL[code],
          dial: config?.countries.find((entry) => entry.country_code === code)?.dial_code ?? "",
        }))}
        value={country}
        onPick={(code) => {
          draft.pick(code as CountryCode);
          setOpen(false);
        }}
        onClose={() => setOpen(false)}
      />
    </>
  );
}
