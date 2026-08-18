/** التحقق الفوري من القواعد المنشورة — SPEC القسم ١٧.٣.
 *
 * **لا قاعدةَ مكتوبةٌ هنا ولا نصَّ عربيٌّ مصاغٌ هنا.** القواعدُ والنصوصُ تصل من
 * `GET /config` مُشتقّةً من مخططات الخلفية، وهذا الملفُّ **مُطبِّقٌ** لها لا
 * مصدرٌ ثانٍ. وحدٌّ يُكتب في التطبيق يفترق عن حدِّ المخطط أوّلَ تعديل: فيمنع
 * التطبيقُ ما تقبله الخلفية، أو — وهو الأسوأ — يقبل ما ترفضه فيصل المستخدمُ
 * إلى ٤٢٢ بعد رحلة شبكة.
 *
 * **وآخرُ نسخةٍ تُخزَّن محلياً** ليتحقق التطبيقُ قبل وصول الرد وعند انقطاع
 * الشبكة. والخلفيةُ تبقى المرجعَ النهائي: هذا يُغني عن الانتظار، لا عن الحارس.
 */

import type { FieldRule } from "@/api/types";

const CACHE_KEY = "taxo.validation.rules";

type Forms = Record<string, Record<string, FieldRule>>;

/** يخزّن آخرَ نسخةٍ وصلت — والفشلُ صامتٌ عمداً.
 *
 * امتلاءُ التخزين أو منعُه لا يجوز أن يُسقط شاشةً: غايةُ الخزن تسريعُ تحققٍ
 * تملك الخلفيةُ نسختَه على أي حال.
 */
export function cacheRules(forms: Forms): void {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(forms));
  } catch {
    /* لا شيء — الخزنُ تحسينٌ لا شرط */
  }
}

export function cachedRules(): Forms | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    return raw ? (JSON.parse(raw) as Forms) : null;
  } catch {
    return null;
  }
}

/** قواعدُ نموذجٍ بعينه — من الإعداد الحيّ، وإلا من آخر نسخةٍ مخزَّنة. */
export function rulesFor(
  forms: Forms | null | undefined,
  form: string,
): Record<string, FieldRule> {
  return forms?.[form] ?? cachedRules()?.[form] ?? {};
}

/** يفحص قيمةً واحدة ويعيد **نصَّ الخلفية** للشرط المكسور، أو `null`.
 *
 * **والترتيبُ مقصود**: «مطلوب» قبل كل شيء (حقلٌ فارغٌ لا يُقاس طولُه)، ثم
 * النوعُ قبل المدى (نصٌّ ليس رقماً لا يُقارن بحدٍّ عدديّ) — وبغير ذلك يقرأ من
 * ترك الحقلَ فارغاً «يجب ألّا تقلّ عن ١٩٩٠».
 */
export function checkField(rule: FieldRule | undefined, raw: string): string | null {
  if (!rule) return null;
  const value = raw.trim();

  if (!value) return rule.required ? (rule.messages.required ?? null) : null;

  if (rule.type === "number") {
    // **`Number("")` صفرٌ و`Number("٢٠٢٠")` NaN** — وكلاهما يمرّ فحصاً ساذجاً.
    // فيُشترط أن يكون النصُّ كلُّه أرقاماً لاتينية بعد التحويل.
    if (!/^\d+$/.test(value)) return rule.messages.type ?? null;
    const numeric = Number(value);
    if (rule.min !== undefined && numeric < rule.min) {
      return rule.messages.min ?? null;
    }
    if (rule.max !== undefined && numeric > rule.max) {
      return rule.messages.max ?? null;
    }
    return null;
  }

  if (rule.type === "choice") {
    if (rule.choices && !rule.choices.includes(value)) {
      return rule.messages.choices ?? null;
    }
    return null;
  }

  if (rule.min_length !== undefined && value.length < rule.min_length) {
    return rule.messages.min_length ?? null;
  }
  if (rule.max_length !== undefined && value.length > rule.max_length) {
    return rule.messages.max_length ?? null;
  }
  return null;
}

/** يفحص نموذجاً كاملاً ويعيد **أوّلَ** حقلٍ مرفوضٍ ورسالتَه — أو `null`.
 *
 * ويُحافَظ على ترتيب الحقول كما جاءت من الخلفية، فيوافق ترتيبُ التركيز ترتيبَ
 * الشاشة بدل أن يقفز إلى حقلٍ أسفلها.
 */
export function checkForm(
  rules: Record<string, FieldRule>,
  values: Record<string, string>,
): { field: string; message: string } | null {
  for (const [field, rule] of Object.entries(rules)) {
    if (!(field in values)) continue;
    const message = checkField(rule, values[field]);
    if (message) return { field, message };
  }
  return null;
}

/** ينقل التركيزَ إلى الحقل الذي سمّته الخلفية (SPEC ١٧.٧).
 *
 * **والخريطةُ لأن اسمَ الحقل في الشاشة ليس دائماً اسمَه في المخطط**: كلمةُ
 * المرور الجديدة تُسمّى `new-password` لدلالة الإكمال التلقائي، والخلفيةُ
 * تسمّيها `password`. وبغير التوجيه يُعلَّم لا شيء ولا ينتقل التركيزُ إلى مكان.
 */
const FIELD_INPUT: Record<string, string> = {
  password: "new-password",
};

export function focusField(field: string): void {
  document
    .querySelector<HTMLInputElement>(`[name="${FIELD_INPUT[field] ?? field}"]`)
    ?.focus();
}
