/** **سياسةُ الخصوصية وشروطُ الاستخدام — صفحتا الموقع القائمتان** (§٦١-و/٦، §٦١-ط/٣).
 *
 * **قوقل تشترط بلوغَهما من داخل التطبيق**، وهما منشورتان على الموقع (`site/privacy.html` · `terms.html`، نصُّهما من
 * السياسة المنشورة في القاعدة) — **فالرابطُ إليهما لا نسخةٌ ثانيةٌ تفترق عنهما**. والفتحُ بـ`AppLauncher` كما يُفتح الموقعُ
 * في «التبديل إلى تطبيق السائق»: في الغلاف يفتح المتصفّح، وفي الويب نافذةً جديدة.
 */

import { AppLauncher } from "@capacitor/app-launcher";

const SITE = "https://taxo.tajora.ly";

export type LegalKey = "privacy" | "terms";

/** **صفحتا دولة الراكب ولغتِه** (SPEC §٧٤-ل/١): للجزائر صفحاتُها (`dz-privacy` · `dz-terms`، و`-fr` لمن لغتُه الفرنسيّة) —
 * **فراكبُ الجزائر لا يُفتح له نصُّ الأردن** وتحته «النصُّ الذي وافقتَ عليه». وما سواها صفحتا الموقع كما كانتا. */
export function legalPages(country: string | undefined, language: string): { key: LegalKey; url: string }[] {
  const own = country ? COUNTRY_PAGES[country] : undefined;
  const prefix = own?.prefix ?? "";
  const suffix = own?.french && language === "fr" ? "-fr" : "";
  return (["privacy", "terms"] as const).map((key) => ({ key, url: `${SITE}/${prefix}${key}${suffix}` }));
}

/** **الدولُ التي لها صفحاتُها على الموقع** — خبرٌ عن ملفّات `site/` لا قائمةُ أسواق: دولةٌ تُضاف صفحاتُها تُضاف هنا، وما ليس
 * هنا يُفتح له ما كان يُفتح. */
const COUNTRY_PAGES: Partial<Record<string, { prefix: string; french: boolean }>> = {
  DZ: { prefix: "dz-", french: true },
  // **ليبيا** (SPEC §٧٦/٣): صفحاتُها نُشرت مع السياسات الكاملة — فلا يُفتح لراكبها نصُّ الأردن بعد اليوم
  LY: { prefix: "ly-", french: false },
};

export function openLegal(url: string): void {
  // **وغلافٌ أقدمُ بلا `AppLauncher` لا يرسل وعداً مرفوضاً** (الشكلُ الذي أنتج بلاغَ 496)
  void AppLauncher.openUrl({ url }).catch(() => undefined);
}
