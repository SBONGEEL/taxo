/** ضغطُ الصورة قبل الرفع — **بيتٌ واحدٌ لكلِّ ما يُرفع من هذا التطبيق**.
 *
 * **والعقدُ هو عقدُ `driver-app/src/lib/shrink.ts` حرفاً** (نفسُ الأسماء ونفسُ
 * المآلات ونفسُ سطرِ الخبر): بابان يضغطان صورةً ويختلفان في شكل جوابهما
 * يجعلان الشاشتين تقولان لصاحبَيهما شيئين عن فعلٍ واحد. **وما يفترق هو
 * الرقمُ وحدَه، وله سببٌ مقيس** (أدناه).
 *
 * **ولمَ ٥١٢ لا ١٦٠٠**: وثيقةُ الكبتن يقرؤها مشرفٌ بعينه فتحتاج نصّاً
 * مقروءاً؛ **وهذه صورةُ وجهٍ لا تُقرأ بل تُميَّز** — **وكلُّ بابٍ يعرضها في
 * الخلفية يمرّ بـ`services/avatar.py` الذي يُنزلها إلى `SIZE = 256`** (قِيس
 * في الشجرة: بابُ الكبتن، وبابُ الراكب، وبابُ المشرف على البلاغ — ثلاثتُها
 * `avatar.render`). فما فوق ٥١٢ بايتاتٌ تُرفع ثم تُرمى قبل أن تصل عيناً،
 * و٥١٢ تُبقي ضعفَ ما يُعرض هامشاً لو رُفع `SIZE` يوماً.
 *
 * **ولا يُضغط ما ليس صورة**، **والفشلُ يعيد الأصل لا يرمي**: من اختار صورةً
 * صحيحةً لا يُمنع لأن متصفحاً لم يدعم `toBlob` — والسقفُ في الخلفية يبقى
 * الحارسَ الأخير.
 */

import { digits } from "@/lib/utils";

/** أقصى بُعدٍ بعد التصغير — بالبكسل. */
export const MAX_EDGE = 512;

/** جودةُ JPEG. */
export const QUALITY = 0.85;

/** حجمٌ لا يستحق الضغطَ أصلاً: صورةٌ صغيرةٌ قد تكبر بإعادة الترميز. */
const SKIP_BELOW_BYTES = 60 * 1024;

/** لماذا خرج الملفُّ على هذه الحال — **وهو ما يمنع صمتاً يُقرأ عطباً**.
 *
 * **الشكلُ الثاني عشر يتربّص هنا**: «ارتدادٌ نجاحُه لا يُميَّز عن عمل
 * الميزة». فبلا هذا الحقل يستوي على الشاشة ثلاثةُ أشياءَ مختلفة: صورةٌ لم
 * تكن تحتاج ضغطاً، وصورةٌ **فشل** ضغطُها، وملفٌّ ليس صورةً أصلاً.
 */
export type ShrinkOutcome =
  /** صُغِّرت فعلاً. */
  | "shrunk"
  /** صورةٌ لا تحتاج: صغيرةٌ أصلاً، أو إعادةُ الترميز لم تربح شيئاً. */
  | "no_gain"
  /** ليست صورة — ولا وعدَ عليها فلا خبرَ عنها. */
  | "not_an_image"
  /** تعذّر الضغطُ فرُفع الأصل — **يُقال، لأن صمتَه يساوي صمتَ النجاح**. */
  | "failed";

export interface ShrinkResult {
  file: File;
  outcome: ShrinkOutcome;
  /** الحجمُ قبل — يُعرض لصاحبه فيرى ما وقع، ويُقاس في التقارير. */
  before: number;
  after: number;
}

export async function shrinkImage(file: File): Promise<ShrinkResult> {
  const before = file.size;
  const unchanged: ShrinkResult = {
    file,
    before,
    after: before,
    outcome: "no_gain",
  };

  if (!file.type.startsWith("image/")) return { ...unchanged, outcome: "not_an_image" };
  if (file.type === "image/gif") return { ...unchanged, outcome: "not_an_image" };
  if (before <= SKIP_BELOW_BYTES) return unchanged;

  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, MAX_EDGE / Math.max(bitmap.width, bitmap.height));
    const width = Math.round(bitmap.width * scale);
    const height = Math.round(bitmap.height * scale);

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) return unchanged;
    context.drawImage(bitmap, 0, 0, width, height);
    bitmap.close?.();

    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob(resolve, "image/jpeg", QUALITY),
    );
    if (!blob) return unchanged;

    // **ولا يُقبل ما كبر**: إعادةُ الترميز قد تزيد حجمَ صورةٍ مضغوطةٍ سلفاً،
    // فالأصلُ يبقى — والقاعدةُ «لا يضرّ» لا «يُضغط دائماً»
    if (blob.size >= before) return unchanged;

    const renamed = file.name.replace(/\.[^.]+$/, "") + ".jpg";
    return {
      file: new File([blob], renamed, { type: "image/jpeg" }),
      before,
      after: blob.size,
      outcome: "shrunk",
    };
  } catch {
    // متصفحٌ لا يدعم `createImageBitmap`/`toBlob`، أو صورةٌ تالفة — يُرفع الأصل
    return { ...unchanged, outcome: "failed" };
  }
}

/** يصف الضغطَ في سطرٍ واحدٍ لصاحبه — **بيتٌ واحدٌ يقرؤه كلُّ مُنادٍ**.
 *
 * **ولماذا يُقال أصلاً**: من رفع صورةً بثمانية ميجا ورآها تُرفع في ثانيتين
 * يظنّ أن شيئاً نقص منها. والسطرُ يقول ما وقع، فيقطع السؤال قبل أن يُسأل.
 *
 * **والخاناتُ لاتينيةٌ بحكم §20**، والقيمةُ تمرّ بـ`digits` لا لأنها قد تأتي
 * عربيةً بل ليبقى المصفى واحداً: `toFixed` يعطي لاتينيةً اليوم، و«اليوم»
 * افتراضٌ لا يُبنى عليه.
 */
export function describeShrink(result: ShrinkResult): string | null {
  switch (result.outcome) {
    case "shrunk":
      return `صُغِّرت قبل الرفع: ${megabytes(result.before)} ← ${megabytes(result.after)}`;
    case "no_gain":
      return `رُفعت كما هي (${megabytes(result.before)}) — لا حاجة للضغط`;
    case "failed":
      return `تعذّر الضغط — رُفعت كما هي (${megabytes(result.before)})`;
    case "not_an_image":
      return null;
  }
}

/** ميجابايت بخانةٍ عشريةٍ واحدة — ودقّةٌ أعلى لا يقرؤها أحد. */
function megabytes(bytes: number): string {
  return `${digits((bytes / (1024 * 1024)).toFixed(1))} م.ب`;
}
