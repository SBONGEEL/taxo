/** الهاتف في الواجهة — **والبادئةُ من الخلفية لا من هنا**.
 *
 * `GET /config` ينشر لكل دولة `dial_code` و`national_number_length` من
 * `core/phone.py` نفسه، فلا تُكتب «962» في كود أيّ تطبيق: بادئةٌ مكتوبةٌ في
 * تطبيقين تفترق عن ذلك الجدول يوماً، وتفترق عن نفسها في التطبيقين قبله.
 *
 * الخلفية هي المرجع وتطبّع كل ما يصلها؛ وهذه النسخة لغرضين لا ثالث لهما:
 * **العرض** (رقمٌ يُقرأ كما كتبه صاحبه)، و**تدفّق Firebase** الذي يقع على
 * الجهاز ويحتاج صيغة E.164 قبل أن تصل الخلفيةَ كلمة (SPEC القسم 15/أ:
 * «الصيغتان E.164 كلتاهما فالمقارنة نصّية مباشرة»).
 *
 * ولا يُتخذ هنا أيُّ قرارٍ من قراراتها: ما يخالف هذا التطبيع ترفضه الخلفية
 * برسالتها العربية، ولا تخترع الواجهة رفضاً من عندها.
 */

import type { CountryCode } from "@/api/types";

export const COUNTRY_LABEL: Record<CountryCode, string> = {
  JO: "🇯🇴 الأردن",
  LY: "🇱🇾 ليبيا",
};

const ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩";

/** يحوّل الأرقام العربية-الهندية إلى لاتينية ويسقط ما ليس رقماً. */
export function digitsOnly(input: string): string {
  return [...input]
    .map((char) => {
      const arabic = ARABIC_DIGITS.indexOf(char);
      return arabic >= 0 ? String(arabic) : char;
    })
    .filter((char) => char >= "0" && char <= "9")
    .join("");
}

/** الرقم الوطني كما يُكتب في حقلٍ أمامه بادئةٌ ثابتة.
 *
 * **يحذف الصفر البادئ** فور كتابته: من يكتب `0791234567` وأمامه `+962` يقصد
 * `+962791234567` لا `+9620791234567`. ويسقط تكرارَ البادئة كذلك، فمن لصق
 * رقماً دولياً كاملاً في حقلٍ يحمل بادئتَه لا يصير رقمُه ضِعفَين.
 */
export function toNational(input: string, dialCode: string): string {
  let digits = digitsOnly(input);
  if (digits.startsWith("00")) digits = digits.slice(2);
  if (digits.startsWith(dialCode)) digits = digits.slice(dialCode.length);
  return digits.replace(/^0+/, "");
}

/** صيغة E.164 لما يُرسل ولتدفّق Firebase. */
export function toE164(raw: string, dialCode: string): string {
  return `+${dialCode}${toNational(raw, dialCode)}`;
}

/** رقمٌ يبدو مكتملاً — حارسُ واجهةٍ يمنع نداءً فاشلاً، لا قاعدةَ تحقق. */
export function looksComplete(raw: string, nationalLength: number): boolean {
  return digitsOnly(raw).length === nationalLength;
}
