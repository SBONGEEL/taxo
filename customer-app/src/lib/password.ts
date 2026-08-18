/** سياسةُ كلمة المرور كما يراها الكاتبُ **لحظةَ الكتابة** — لا بعد الإرسال.
 *
 * العطبُ الذي أنشأ هذا الملف قِيس على هاتفٍ حقيقي: كلمةُ مرورٍ قصيرة تجعل زرَّ
 * «متابعة» **معطَّلاً بصمت** — لا حمرةَ تحت حقلٍ ولا سطرَ سبب. فمن كتب سبع
 * خاناتٍ يرى زراً لا يستجيب ولا يعرف لماذا، فيظنّ التطبيقَ عاطلاً.
 *
 * **والحدُّ يُقرأ من القواعد المنشورة، ولم يعد مكتوباً هنا** (SPEC ١٧.٣،
 * قرارُ المالك 2026-08-18). كان الملفُّ يحمل `MIN_PASSWORD = 8` **مرآةً** يدوية
 * للخلفية — وهو بالضبط «نسخةُ القواعد داخل التطبيق» التي يمنعها القرار: تعديلُ
 * الحدِّ في المخطط يتركها على القديم، فيقبل التطبيقُ ما ترفضه الخلفية.
 *
 * **وحيث لا قاعدةَ معروفة، لا حكمَ محلياً**: أوّلُ إقلاعٍ بلا شبكةٍ ولا نسخةٍ
 * مخزَّنة يترك الحكمَ للخلفية — وهو أصدقُ من رقمٍ نخمّنه ونعامله يقيناً.
 *
 * **ونعدّ ما بقي لا ما نقص**: «بقيت ٣ خانات» يقول للكاتب ماذا يفعل الآن،
 * و«ثمانية أحرف على الأقل» يصف قاعدةً عليه أن يطرح منها بنفسه. ولذلك يبقى
 * النصُّ هنا: هو **عدٌّ تفاعليٌّ** لا رسالةَ رفضٍ — ورسالةُ الرفض تأتي من
 * السجل المركزي عبر `messages`.
 */

import type { FieldRule } from "@/api/types";
import { rulesFor } from "@/lib/validation";

/** قاعدةُ كلمة المرور في نموذج التسجيل — أو `null` إن لم تصل بعد. */
export function passwordRule(): FieldRule | null {
  return rulesFor(null, "register").password ?? null;
}

export function minPassword(): number | null {
  return passwordRule()?.min_length ?? null;
}

export function maxPassword(): number | null {
  return passwordRule()?.max_length ?? null;
}

/** خطأُ كلمة المرور نفسِها — أو `null` إن كانت مقبولة أو القاعدةُ مجهولة.
 *
 * **ولا خطأَ على حقلٍ فارغٍ لم يُلمس**: من فتح الشاشة للتوّ لم يخطئ بعد،
 * وحمرةٌ قبل أوّل حرفٍ تُقرأ اتهاماً.
 */
export function passwordError(value: string): string | null {
  if (value.length === 0) return null;
  const rule = passwordRule();
  if (!rule) return null;

  const min = rule.min_length;
  if (min !== undefined && value.length < min) {
    const left = min - value.length;
    return `أقصر من المطلوب — بقيت ${left} ${left === 1 ? "خانة" : "خانات"}`;
  }
  const max = rule.max_length;
  if (max !== undefined && value.length > max) {
    return rule.messages.max_length ?? `أطول من المسموح (${max} خانة)`;
  }
  return null;
}

/** خطأُ حقل التأكيد — يُقاس بعد أن يكتب فيه شيئاً.
 *
 * **وهذا شرطُ شاشةٍ لا شرطُ مخطط**: الخلفيةُ لا تعرف حقلَ تأكيدٍ أصلاً، فلا
 * قاعدةَ منشورةً له — ونصُّه يبقى هنا بحق.
 */
export function confirmError(password: string, confirm: string): string | null {
  if (confirm.length === 0) return null;
  return confirm === password ? null : "الكلمتان غير متطابقتين";
}

/** هل الكلمتان صالحتان للإرسال؟ — نفسُ الشرطين اللذين يرسمان الخطأ.
 *
 * **والقاعدةُ المجهولة تُقرأ «اسمح»** لا «امنع»: زرٌّ معطَّلٌ لأن الإعداد لم
 * يصل بعد هو الزرُّ الصامتُ الذي وُجد هذا الملفُّ لإزالته.
 */
export function passwordsReady(password: string, confirm: string): boolean {
  if (confirm !== password || password.length === 0) return false;
  return passwordError(password) === null;
}
