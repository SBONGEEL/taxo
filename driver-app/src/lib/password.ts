/** سياسةُ كلمة المرور كما يراها الكاتبُ **لحظةَ الكتابة** — لا بعد الإرسال.
 *
 * العطبُ الذي أنشأ هذا الملف قِيس على هاتفٍ حقيقي: كلمةُ مرورٍ قصيرة تجعل زرَّ
 * «متابعة» **معطَّلاً بصمت** — لا حمرةَ تحت حقلٍ ولا سطرَ سبب. فمن كتب سبع
 * خاناتٍ يرى زراً لا يستجيب ولا يعرف لماذا، فيظنّ التطبيقَ عاطلاً. **وزرٌّ
 * معطَّلٌ بلا سببٍ مكتوب أسوأُ من زرٍّ يُضغط فيَرُدّ**: الثاني يخبرك، والأول
 * يتركك تخمّن.
 *
 * **والقاعدةُ مرآةُ الخلفية لا اجتهاد** (`services/auth/password.py`): ثماني
 * خاناتٍ حدّاً أدنى ومئةٌ وثمانٍ وعشرون حدّاً أعلى. ولو اختلف الرقمان لصار
 * التطبيقُ يقبل ما ترفضه الخلفية — وهو الشكلُ الذي يُقرأ «أرسلتُ فرُفض بلا سبب».
 *
 * **ونعدّ ما بقي لا ما نقص**: «بقيت ٣ خانات» يقول للكاتب ماذا يفعل الآن،
 * و«ثمانية أحرف على الأقل» يصف قاعدةً عليه أن يطرح منها بنفسه.
 */

/** مرآةُ `MIN_PASSWORD_LENGTH` في الخلفية. */
export const MIN_PASSWORD = 8;
/** مرآةُ `MAX_PASSWORD_LENGTH`. */
export const MAX_PASSWORD = 128;

/** خطأُ كلمة المرور نفسِها — أو `null` إن كانت مقبولة.
 *
 * **ولا خطأَ على حقلٍ فارغٍ لم يُلمس**: من فتح الشاشة للتوّ لم يخطئ بعد،
 * وحمرةٌ قبل أوّل حرفٍ تُقرأ اتهاماً.
 */
export function passwordError(value: string): string | null {
  if (value.length === 0) return null;
  if (value.length < MIN_PASSWORD) {
    const left = MIN_PASSWORD - value.length;
    return `أقصر من المطلوب — بقيت ${left} ${left === 1 ? "خانة" : "خانات"}`;
  }
  if (value.length > MAX_PASSWORD) {
    return `أطول من المسموح (${MAX_PASSWORD} خانة)`;
  }
  return null;
}

/** خطأُ حقل التأكيد — يُقاس بعد أن يكتب فيه شيئاً. */
export function confirmError(password: string, confirm: string): string | null {
  if (confirm.length === 0) return null;
  return confirm === password ? null : "الكلمتان غير متطابقتين";
}

/** هل الكلمتان صالحتان للإرسال؟ — نفسُ الشرطين اللذين يرسمان الخطأ. */
export function passwordsReady(password: string, confirm: string): boolean {
  return (
    password.length >= MIN_PASSWORD &&
    password.length <= MAX_PASSWORD &&
    confirm === password
  );
}
