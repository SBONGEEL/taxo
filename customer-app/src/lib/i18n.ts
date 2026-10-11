/** **الترجمة** (SPEC §٧٣-هـ المرحلة ٥) — العربيّةُ والفرنسيّة، **والنصُّ العربيُّ هو المفتاح**.
 *
 * **ولمَ المفتاحُ عربيٌّ لا اسمٌ مخترع**: `tr(نص)` في العربيّة **تعيد النصَّ نفسَه حرفاً** — فما يراه المستخدمُ العربيُّ لم يتغيّر بالترجمة
 * **بالبناء لا بالمراجعة**، ويحرسه `tools/check-arabic-frozen.mjs` (جردُ كلِّ نصٍّ عربيٍّ قبل اللفّ). وفي الفرنسيّة يُقرأ النصُّ من
 * `i18n/fr.json`، **ونصٌّ بلا فرنسيّةٍ يُرسم عربيّاً** ولا يُرسم فارغاً.
 *
 * **واللغةُ تُحسم مرّةً عند الإقلاع** — ما اختاره المستخدمُ في الإعدادات (`taxo.lang`)، وإلا **لغةُ الهاتف** (فرنسيّةٌ ⇐ فرنسيّة، وكلُّ ما
 * سواها عربيّة كما كان). **وتغييرُها يعيد تحميلَ التطبيق** (`setLanguage`): نصوصٌ كثيرةٌ تُحسب عند تحميل وحداتها (أسماءُ الحالات
 * وغيرُها)، **وتطبيقٌ نصفُه بلغةٍ ونصفُه بأخرى أسوأُ من ثانيةِ إعادة**. **والاتجاهُ يتبع اللغة**: `rtl` للعربيّة و`ltr` للفرنسيّة.
 *
 * **ولا مكتبةَ خارجيّة** — ملفٌّ واحدٌ بلا تبعيّة: لا حزمةَ تُحدَّث تحت التطبيق، ولا شيفرةَ غريبةً في مسار كلِّ نصّ.
 */

import FR from "@/i18n/fr.json";

export type Language = "ar" | "fr";
export const LANGUAGES: readonly Language[] = ["ar", "fr"];
/** **اسمُ كلِّ لغةٍ بلغتها** — يُرسم كما هو في الحالين */
export const LANGUAGE_NAME: Record<Language, string> = { ar: "العربية", fr: "Français" };

const STORE_KEY = "taxo.lang";

function chosen(): Language | null {
  try {
    const value = localStorage.getItem(STORE_KEY);
    return value === "ar" || value === "fr" ? value : null;
  } catch {
    return null;
  }
}

/** **لغةُ الهاتف** — أوّلُ ما يُعرف منها بين العربيّة والفرنسيّة، وإلا العربيّة */
function phone(): Language {
  if (typeof navigator === "undefined") return "ar";
  const list = navigator.languages?.length ? navigator.languages : [navigator.language];
  for (const tag of list) {
    const prefix = (tag || "").toLowerCase().slice(0, 2);
    if (prefix === "ar") return "ar";
    if (prefix === "fr") return "fr";
  }
  return "ar";
}

export const language: Language = chosen() ?? phone();

if (typeof document !== "undefined") {
  document.documentElement.lang = language;
  document.documentElement.dir = language === "ar" ? "rtl" : "ltr";
}

const dictionary: Readonly<Record<string, string>> = language === "fr" ? (FR as Record<string, string>) : {};

/** **النصُّ بلغة التطبيق** — والعربيُّ كما هو. `vars` تملأ `{0}` `{1}` (قوالبُ النصوص) أو `{اسم}`، **والقيمةُ تُكتب كما يكتبها قالبٌ نصّيّ**. */
export function tr(ar: string, vars?: Readonly<Record<string | number, unknown>>): string {
  const text = dictionary[ar] ?? ar;
  if (!vars) return text;
  return text.replace(/\{(\w+)\}/g, (whole, key: string) => (key in vars ? String(vars[key]) : whole));
}

/** **تغييرُ اللغة من الإعدادات** — يُحفظ على الجهاز ثمّ يُعاد تحميلُ التطبيق؛ وحفظُه في الحساب على من يناديه (`PATCH /auth/me`). */
export function setLanguage(next: Language): void {
  try {
    localStorage.setItem(STORE_KEY, next);
  } catch {
    // **بلا تخزين** (نافذةٌ خاصّة) — تبقى لغةُ الهاتف، ولا يسقط شيء
  }
  window.location.reload();
}
