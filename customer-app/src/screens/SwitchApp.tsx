/** صفحتا التبديل: «غير مثبَّت» — TAXO 2.0 «R28» (`design/t2-new/rider/R28-driver-not-installed.dc.html`)، **في المظهرين
 *  والنسائيّ**: بطاقةُ الحبر بشريطها (R05 «إلى أين؟») ودائرةُ الجمر، وزرُّ الجمر للفعل.
 *
 * **و«غير مثبَّت» صفحةٌ لا رسالةُ خطأ**: من ضغط «تبديل» يريد شيئاً، وقولُ
 * «تعذّر» يتركه بلا خطوةٍ تالية. فتُشرح الحالُ ويُعطى مدخلُ التثبيت.
 */

import { AppLauncher } from "@capacitor/app-launcher";

import { useGoBack } from "@/lib/back";
import { SubHeadT2 } from "@/screens/t2/KitT2";
import { Icon } from "@/taxo2";

import "@/screens/t2/t2.css";
import "@/screens/t2/account.css";

/** صفحةُ التنزيل — **مصدرٌ واحدٌ** يقرّر بنفسه أحزمةٌ أم متجر. */
const INSTALL_PAGE = "https://taxo.tajora.ly";

export function DriverNotInstalledScreen() {
  const goBack = useGoBack();
  return (
    <div className="t2 t2-page pb-nav">
      <SubHeadT2 title="تطبيق السائق" onBack={() => goBack()} />

      <section className="t2-hero">
        <span className="t2-hero-stripe" aria-hidden="true" />
        <span className="t2-hero-icon">
          <Icon name="directions_car" />
        </span>
        <p className="t2-hero-title">تطبيق السائق غير مثبَّت على هذا الجهاز</p>
        <p className="t2-hero-body">
          حسابك واحد، وتدخل به التطبيقين بلا تسجيلٍ جديد. ثبّت تطبيق السائق ثم عد إلى هنا واضغط «تبديل» — تنتقل جلستك
          وحدها.
        </p>
      </section>

      <button
        type="button"
        className="t2-button action t2-wide"
        onClick={() => {
          void AppLauncher.openUrl({ url: INSTALL_PAGE });
        }}
      >
        <Icon name="open_in_new" />
        احصل على تطبيق السائق
      </button>
    </div>
  );
}
