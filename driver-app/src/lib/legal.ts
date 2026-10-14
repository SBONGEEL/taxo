/** **صفحتا الكبتن — الخصوصيةُ والشروط** (SPEC §٧٦/٣): قوقل تشترط بلوغَ السياسة من داخل التطبيق، **وتطبيقُ الكبتن كان بلا رابطٍ
 * إليهما** إلا موافقةَ التسجيل. **والرابطُ إلى صفحات الموقع لا نسخةٌ ثانية** — نصُّها مخبوزٌ من السياسة المنشورة في القاعدة.
 *
 * **ودولةُ الكبتن ولغتُه** كما في تطبيق الراكب (`customer-app/src/lib/legal.ts`): للجزائر صفحاتُها (و`-fr` لمن لغتُه الفرنسيّة)،
 * ولليبيا صفحاتُها، **وما سواهما صفحتا الأردن** (الموقعُ بلا بادئة).
 */

import { AppLauncher } from "@capacitor/app-launcher";

const SITE = "https://taxo.tajora.ly";

export type LegalKey = "privacy" | "terms";

/** **الدولُ التي لها صفحاتُها على الموقع** — خبرٌ عن ملفّات `site/` لا قائمةُ أسواق. */
const COUNTRY_PAGES: Partial<Record<string, { prefix: string; french: boolean }>> = {
  DZ: { prefix: "dz-", french: true },
  LY: { prefix: "ly-", french: false },
};

export function legalPages(country: string | undefined, language: string): { key: LegalKey; url: string }[] {
  const own = country ? COUNTRY_PAGES[country] : undefined;
  const prefix = own?.prefix ?? "";
  const suffix = own?.french && language === "fr" ? "-fr" : "";
  return (["privacy", "terms"] as const).map((key) => ({ key, url: `${SITE}/${prefix}driver-${key}${suffix}` }));
}

export function openLegal(url: string): void {
  // **وغلافٌ أقدمُ بلا `AppLauncher` لا يرسل وعداً مرفوضاً**
  void AppLauncher.openUrl({ url }).catch(() => undefined);
}
