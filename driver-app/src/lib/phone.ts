/** الهاتف في الواجهة — **والبادئةُ من الخلفية لا من هنا**.
 *
 * `GET /config` ينشر لكل دولة `dial_code` و`national_number_length` من
 * `core/phone.py` نفسه، فلا تُكتب «962» في كود أيّ تطبيق: بادئةٌ مكتوبةٌ في
 * تطبيقين تفترق عن ذلك الجدول يوماً، وتفترق عن نفسها في التطبيقين قبله.
 *
 * والخلفية هي المرجع وتطبّع كل ما يصلها (`normalize_phone`)؛ وهذه النسخة
 * لغرضين لا ثالث لهما: **العرض** (بادئةٌ ثابتة أمام حقلٍ يكتب فيه صاحبه
 * رقمه الوطني) و**تدفّق Firebase** الذي يقع على الجهاز ويحتاج E.164 قبل أن
 * تصل الخلفيةَ كلمة. ولا يُتخذ هنا أيُّ قرارٍ من قراراتها: ما تخالفه ترفضه
 * الخلفية برسالتها العربية.
 */

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
 * **يحذف الصفر البادئ** فور كتابته: من يكتب `0791234567` وأمامه `+962`
 * يقصد `+962791234567` لا `+9620791234567`. ويسقط تكرارَ البادئة كذلك، فمن
 * لصق رقماً دولياً كاملاً في حقلٍ يحمل بادئتَه لا يصير رقمُه ضِعفَين.
 */
export function toNational(input: string, dialCode: string): string {
  let digits = digitsOnly(input);
  if (digits.startsWith("00")) digits = digits.slice(2);
  if (digits.startsWith(dialCode)) digits = digits.slice(dialCode.length);
  return digits.replace(/^0+/, "");
}

/** صيغة E.164 لما يُرسل ولتدفّق Firebase. */
export function toE164(national: string, dialCode: string): string {
  return `+${dialCode}${toNational(national, dialCode)}`;
}

/** رقمٌ يبدو مكتملاً — حارسُ واجهةٍ يمنع نداءً فاشلاً، لا قاعدةَ تحقق. */
export function looksComplete(national: string, length: number): boolean {
  return digitsOnly(national).length === length;
}
