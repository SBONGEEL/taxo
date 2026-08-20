/** ضغطُ صورة الوثيقة قبل الرفع — **بيتٌ واحدٌ يقرؤه المُنادِيان**.
 *
 * **والعلّةُ حسابيةٌ لا ذوقية**: كاميرا هاتفٍ اليومَ تعطي ٧٦٨ ك.ب في أهدأ
 * حالاتها وأضعافَها في أوسعها، والكبتنُ يرفع **إحدى عشرةَ وثيقة**. فالأسوأُ
 * ٥٥ ميجا للواحد على سقفِ ٥ — أي أن **ألفاً وثمانمئة كبتنٍ يملؤون قرصَ الخادم
 * (١٠٠ جيجا)** ومعه تتوقف القاعدةُ والنسخُ والسجلات.
 *
 * **ووثيقةٌ تُقرأ بالعين لا تحتاج اثنَي عشرَ ميجابكسل**: ما يُراد منها أن يقرأ
 * المشرفُ رقمَ الرخصة واسمَ صاحبها. فالعرضُ الأقصى ١٦٠٠ بكسل وجودةُ ٠٫٨ —
 * وهما ما يُبقيان النصَّ مقروءاً ويُنزلان الحجمَ إلى الثلث.
 *
 * **ولا يُضغط ما ليس صورة**: ملفُّ PDF يُرفع كما هو — تمريرُه بلوحةِ رسمٍ يجعله
 * صورةً واحدةً بلا نصٍّ ولا صفحاتٍ بعده.
 *
 * **والفشلُ يعيد الأصل لا يرمي**: من رفع وثيقةً صحيحةً لا يُمنع لأن متصفحاً
 * لم يدعم `toBlob` — والسقفُ في الخلفية يبقى الحارسَ الأخير.
 */

import { digits } from "@/lib/utils";

/** أقصى بُعدٍ بعد التصغير — بالبكسل. */
export const MAX_EDGE = 1600;

/** جودةُ JPEG — مقايضةٌ بين وضوحِ النصِّ والحجم. */
export const QUALITY = 0.8;

/** حجمٌ لا يستحق الضغطَ أصلاً: صورةٌ صغيرةٌ قد تكبر بإعادة الترميز. */
const SKIP_BELOW_BYTES = 120 * 1024;

export interface ShrinkResult {
  file: File;
  /** الحجمُ قبل — يُعرض للكبتن فيرى ما وقع، ويُقاس في التقارير. */
  before: number;
  // **وكان هذا الوعدُ بلا قارئ حتى 2026-08-20**: الحقولُ الثلاثةُ تُحسب
  // ويرميها المُنادِيان، فلا شاشةَ تعرض شيئاً — «حقلٌ بلا قارئ»، وشكلٌ
  // لهذا المشروع سابقة. وما يجعله صامتاً أن الضغطَ **يعمل**: الملفُّ يصغر
  // ويُرفع، ولا شيءَ يفشل — والغائبُ هو الخبرُ وحدَه.
  after: number;
  changed: boolean;
}

export async function shrinkImage(file: File): Promise<ShrinkResult> {
  const before = file.size;
  const unchanged: ShrinkResult = { file, before, after: before, changed: false };

  if (!file.type.startsWith("image/")) return unchanged;
  if (file.type === "image/gif") return unchanged; // متحرّكةٌ تفقد إطاراتِها
  if (before <= SKIP_BELOW_BYTES) return unchanged;

  try {
    const bitmap = await createImageBitmap(file);
    const scale = Math.min(1, MAX_EDGE / Math.max(bitmap.width, bitmap.height));
    const width = Math.round(bitmap.width * scale);
    const height = Math.round(bitmap.height * scale);

    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) return unchanged;
    ctx.drawImage(bitmap, 0, 0, width, height);
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
      changed: true,
    };
  } catch {
    // متصفحٌ لا يدعم `createImageBitmap`/`toBlob`، أو صورةٌ تالفة — يُرفع الأصل
    return unchanged;
  }
}

/** يصف الضغطَ في سطرٍ واحدٍ للكبتن — **بيتٌ واحدٌ يقرؤه المُنادِيان**.
 *
 * **ولماذا يُقال أصلاً**: من رفع صورةً بثمانية ميجا ورآها تُرفع في ثانيتين
 * يظنّ أن شيئاً نقص منها. والسطرُ يقول ما وقع، فيقطع السؤال قبل أن يُسأل.
 *
 * **والخاناتُ لاتينيةٌ بحكم §20**، والقيمةُ تمرّ بـ`digits` لا لأنها قد تأتي
 * عربيةً بل ليبقى المصفى واحداً: `toFixed` يعطي لاتينيةً اليوم، و«اليوم»
 * افتراضٌ لا يُبنى عليه — وهو درسُ `DISPLAY_LOCALE` بعينه.
 */
export function describeShrink(result: ShrinkResult): string | null {
  if (!result.changed) return null;
  return `صُغِّرت قبل الرفع: ${megabytes(result.before)} ← ${megabytes(result.after)}`;
}

/** ميجابايت بخانةٍ عشريةٍ واحدة — ودقّةٌ أعلى لا يقرؤها أحد. */
function megabytes(bytes: number): string {
  return `${digits((bytes / (1024 * 1024)).toFixed(1))} م.ب`;
}
