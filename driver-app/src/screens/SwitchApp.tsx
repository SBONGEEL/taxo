/** صفحتا التبديل: «غير مثبَّت» وصفحةُ استقبال الجلسة.
 *
 * **و«غير مثبَّت» صفحةٌ لا رسالةُ خطأ**: من ضغط «تبديل» يريد شيئاً، وقولُ
 * «تعذّر» يتركه بلا خطوةٍ تالية. فتُشرح الحالُ ويُعطى مدخلُ التثبيت.
 *
 * **بلغة TAXO 2.0** «C30» (`design/t2-new/captain/C30-switch-rider-missing.dc.html`): **لغةُ جولة الأذونات** (`PermissionsIntro`)
 * — رجوعٌ دائريّ، ومربّعُ الجمر الخافت، والعنوانُ وسطرُه، والفعلُ أسفلَ الشاشة. **والعنوانُ الصغيرُ «تطبيق الراكب» سقط**: العنوانُ
 * الكبيرُ يقوله كاملاً. **والفعلُ هو هو**: يفتح صفحةَ التنزيل.
 */

import { AppLauncher } from "@capacitor/app-launcher";

import { useGoBack } from "@/lib/back";
import { Icon } from "@/taxo2";

import "@/screens/t2/account.css";

/** صفحةُ التنزيل — **مصدرٌ واحدٌ** يقرّر بنفسه أحزمةٌ أم متجر. */
const INSTALL_PAGE = "https://taxo.tajora.ly";

export function RiderNotInstalledScreen() {
  const goBack = useGoBack();
  return (
    <div className="t2 t2-ax">
      <div className="t2-ax-scroll has-foot">
        <div className="t2-head">
          <button type="button" className="t2-back" aria-label="رجوع" onClick={() => goBack()}>
            <Icon name="arrow_forward" />
          </button>
        </div>
        <span className="t2-swap-icon" aria-hidden="true">
          <Icon name="swap_horiz" />
        </span>
        <h1 className="t2-swap-title">تطبيق الراكب غير مثبَّت على هذا الجهاز</h1>
        <p className="t2-swap-text">
          حسابك واحد، وتدخل به التطبيقين بلا تسجيلٍ جديد. ثبّت تطبيق الراكب ثم
          عد إلى هنا واضغط «تبديل» — تنتقل جلستك وحدها.
        </p>
      </div>
      <div className="t2-ax-foot">
        <button
          type="button"
          className="t2-ax-cta"
          onClick={() => {
            void AppLauncher.openUrl({ url: INSTALL_PAGE });
          }}
        >
          احصل على تطبيق الراكب
        </button>
      </div>
    </div>
  );
}
