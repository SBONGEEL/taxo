/** **سياسةُ الخصوصية وشروطُ الاستخدام — صفحتا الموقع القائمتان** (§٦١-و/٦، §٦١-ط/٣).
 *
 * **قوقل تشترط بلوغَهما من داخل التطبيق**، وهما منشورتان على الموقع (`site/privacy.html` · `terms.html`، نصُّهما من
 * السياسة المنشورة في القاعدة) — **فالرابطُ إليهما لا نسخةٌ ثانيةٌ تفترق عنهما**. والفتحُ بـ`AppLauncher` كما يُفتح الموقعُ
 * في «التبديل إلى تطبيق السائق»: في الغلاف يفتح المتصفّح، وفي الويب نافذةً جديدة.
 */

import { AppLauncher } from "@capacitor/app-launcher";

const SITE = "https://taxo.tajora.ly";

export const LEGAL_PAGES = [
  { key: "privacy", label: "سياسة الخصوصية", url: `${SITE}/privacy` },
  { key: "terms", label: "شروط الاستخدام", url: `${SITE}/terms` },
] as const;

export function openLegal(url: string): void {
  void AppLauncher.openUrl({ url });
}
