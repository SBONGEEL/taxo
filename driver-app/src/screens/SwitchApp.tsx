/** صفحتا التبديل: «غير مثبَّت» وصفحةُ استقبال الجلسة.
 *
 * **و«غير مثبَّت» صفحةٌ لا رسالةُ خطأ**: من ضغط «تبديل» يريد شيئاً، وقولُ
 * «تعذّر» يتركه بلا خطوةٍ تالية. فتُشرح الحالُ ويُعطى مدخلُ التثبيت.
 */

import { AppLauncher } from "@capacitor/app-launcher";

import { Button } from "@/components/ui/Button";
import { useGoBack } from "@/lib/back";

/** صفحةُ التنزيل — **مصدرٌ واحدٌ** يقرّر بنفسه أحزمةٌ أم متجر. */
const INSTALL_PAGE = "https://taxo.tajora.ly";

export function RiderNotInstalledScreen() {
  const goBack = useGoBack();
  return (
    <div className="h-full bg-bg px-16 pb-nav pt-safe">
      <div className="mb-16 mt-6 flex items-center gap-10">
        <button
          type="button"
          onClick={() => goBack()}
          aria-label="رجوع"
          className="pressable text-18 text-muted"
        >
          →
        </button>
        <h1 className="text-20 font-bold text-ink">تطبيق الراكب</h1>
      </div>

      <section className="card p-16">
        <p className="text-13.5 font-semibold text-ink">
          تطبيق الراكب غير مثبَّت على هذا الجهاز
        </p>
        <p className="mt-8 text-12 leading-note text-muted">
          حسابك واحد، وتدخل به التطبيقين بلا تسجيلٍ جديد. ثبّت تطبيق الراكب ثم
          عد إلى هنا واضغط «تبديل» — تنتقل جلستك وحدها.
        </p>
        <Button
          className="mt-14"
          onClick={() => {
            void AppLauncher.openUrl({ url: INSTALL_PAGE });
          }}
        >
          احصل على تطبيق الراكب
        </Button>
      </section>
    </div>
  );
}
