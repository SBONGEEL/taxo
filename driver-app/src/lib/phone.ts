/** تطبيع الهاتف في الواجهة — مرآةٌ مبسّطة لـ `backend/app/core/phone.py`.
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

export const DIAL_CODE: Record<CountryCode, string> = { JO: "962", LY: "218" };

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

/** صيغة E.164 لرقمٍ محلي أو دولي — للعرض ولتدفّق Firebase. */
export function toE164(raw: string, country: CountryCode): string {
  const dial = DIAL_CODE[country];
  let digits = digitsOnly(raw);

  if (digits.startsWith("00")) digits = digits.slice(2);
  if (digits.startsWith(dial)) return `+${digits}`;
  return `+${dial}${digits.replace(/^0+/, "")}`;
}

/** رقمٌ يبدو مكتملاً — حارسُ واجهةٍ يمنع نداءً فاشلاً، لا قاعدةَ تحقق. */
export function looksComplete(raw: string, country: CountryCode): boolean {
  const national = toE164(raw, country).slice(DIAL_CODE[country].length + 1);
  return national.length >= 8 && national.length <= 12;
}
