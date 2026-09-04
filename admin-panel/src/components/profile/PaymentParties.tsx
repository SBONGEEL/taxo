/** طرفا الدفعة في خليّةٍ واحدة — **بيتٌ واحدٌ لشاشتين** (§٤٧٫١٩، §50).
 *
 * **شاشتا «المدفوعات» و«النزاعات» تقرآن البابَ نفسَه** (`GET /admin/payments`)
 * وترسمان الصفَّ نفسَه. **ونسختان من هذه الخليّة تفترقان أوّلَ تعديل** — وهو
 * الشكلُ الثامن الذي أنشأ `OpenProfile` قبلها.
 *
 * ## والراكبُ سطرٌ والكبتنُ تحته — ولكلٍّ زرُّ ملفِّه
 *
 * **ولا يُدمجان في زرٍّ واحد**: «افتح الملفّ» على صفٍّ فيه إنسانان **لا يقول
 * ملفَّ أيِّهما يفتح**، ومشرفٌ يفصل نزاعاً يحتاج الاثنين لا أحدَهما.
 *
 * ## والكبتنُ قد يغيب — **وذاك واقعةٌ لا نقص**
 *
 * رحلةٌ أُلغيت قبل القبول لا كبتنَ لها، **ورسمُ إلغائها دفعةٌ بلا كبتن**.
 * فيُقال «—» ولا يُرسم زرٌّ يفتح لا شيء.
 */

import type { Payment } from "@/api/types";
import { OpenProfile } from "@/components/profile/OpenProfile";

export function PaymentParties({ payment }: { payment: Payment }) {
  return (
    <span className="min-w-0">
      <span className="flex items-center gap-6">
        <span className="min-w-0 truncate text-11.5 text-ink">
          {payment.rider?.name ?? "—"}
        </span>
        {payment.rider ? (
          <OpenProfile kind="rider" id={payment.rider.user_id} />
        ) : null}
      </span>
      <span className="flex items-center gap-6">
        <span className="min-w-0 truncate text-10.5 text-muted">
          {payment.driver?.name ?? "—"}
        </span>
        {payment.driver ? (
          // **ويُضيَّق برقمه**: لا بابَ يقرأ صفَّ كبتنٍ واحد، فالدرجُ يُفتح
          // بمطابقة `drivers.id` **داخل القائمة المرشَّحة** — وقائمةٌ بلا
          // ترشيحٍ تعرض أوّلَ خمسين، فمن كان خارجها لا يُفتح ملفُّه أبداً
          <OpenProfile
            kind="driver"
            id={payment.driver.driver_id}
            search={payment.driver.phone || payment.driver.name}
          />
        ) : null}
      </span>
    </span>
  );
}
