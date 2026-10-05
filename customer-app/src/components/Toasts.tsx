/** ما يصل والتطبيق مفتوح — يُعرض داخل الشاشة.
 *
 * الخلفية **لا ترسل Push لجهازٍ سوكته نشط** (SPEC القسم 10)، والمتصفح لا يعرض
 * ما يصل عبر `onMessage` والصفحةُ مفتوحة. فهذه هي القناة الوحيدة التي يرى بها
 * المستخدم الحدثَ وهو ينظر إلى الشاشة.
 *
 * **بلغة TAXO 2.0 في المظهرين** (§٦٢/١ و/٨) — `t2-notice` في `taxo2/primitives.css`: كانت بطاقةً بيضاءَ بلغةٍ سابقةٍ
 * حتى في الداكن، **فكان القديمُ يظهر فوق الجديد** كلّما وصل حدث.
 */

import { useRide } from "@/lib/ride";

import "@/taxo2";

export function Toasts() {
  const { toasts, dismissToast } = useRide();
  if (!toasts.length) return null;

  return (
    <div className="t2 t2-notices">
      {toasts.map((toast) => (
        <div key={toast.id} className="t2-notice" role="status">
          <span className="t2-notice-icon" aria-hidden="true">
            <span className="t2-icon">notifications</span>
          </span>
          <div className="t2-notice-main">
            <p className="t2-notice-title">{toast.title}</p>
            {toast.body ? <p className="t2-notice-body">{toast.body}</p> : null}
          </div>
          <button type="button" className="t2-notice-close" onClick={() => dismissToast(toast.id)} aria-label="إغلاق">
            <span className="t2-icon" aria-hidden="true">
              close
            </span>
          </button>
        </div>
      ))}
    </div>
  );
}
