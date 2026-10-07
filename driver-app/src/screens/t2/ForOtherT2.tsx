/** **رحلةٌ لشخصٍ آخر** (§٦٣-ج/١) — وجهاها في تطبيق الكبتن: **سطرُ الدافع** (بطاقةُ العرض C05 وورقةُ الرحلة C06–C07)،
 * **وصفُّ الراكب الفعليّ** باسمه وزرِّ الاتصال به (بعد القبول وحدَه — `passenger_*` لا يُنشران قبله).
 *
 * **لا لوحةَ لها في Claude Design** — فتُركَّب من عُدّة الهوية: صفُّ الراكب هو `t2-rd-rider` نفسُه، والسطرُ بنبرتي النجاح والتنبيه
 * من الرموز. **و«لا تستلم شيئاً» مُبرَزةٌ بقصد**: كبتنٌ يقبض نقداً من راكبٍ دفع عنه غيرُه يقبض الأجرةَ مرّتين من جيبين.
 */

import type { Ride, RidePayer } from "@/api/types";
import { Icon } from "@/taxo2";

/** **من يدفع — سطرٌ يُقرأ قبل القبول وبعده**: نقدُ الراكب الفعليّ بنبرة النجاح (مالٌ في اليد كأيِّ كاش)، **ودفعُ صاحب الطلب
 *  بنبرة التنبيه** — فهو الحالُ الوحيدةُ التي يُطلب فيها من الكبتن ألّا يأخذ شيئاً.
 *
 *  **ونقدُ مستلم الطرد بنبرة النجاح كذلك** (§٦٣-ج/٤، `ParcelT2`) — مالٌ في يده عند التسليم. **و`requester` في طردٍ لا يُرسم هنا**:
 *  مرسلُه يدفع عند الالتقاط كأيِّ رحلة، و«لا تستلم شيئاً» عنه كذب. */
export function PayerNoteT2({ payer }: { payer: RidePayer }) {
  if (payer === "recipient_cash") {
    return (
      <p className="t2-fo-payer ok">
        <Icon name="payments" />
        <span>يدفع المستلمُ نقداً عند التسليم</span>
      </p>
    );
  }
  if (payer === "requester") {
    return (
      <p className="t2-fo-payer warn">
        <Icon name="info" fill />
        <span>
          مدفوعة من صاحب الطلب — <b>لا تستلم شيئاً</b>
        </span>
      </p>
    );
  }
  return (
    <p className="t2-fo-payer ok">
      <Icon name="payments" />
      <span>يدفع الراكبُ نقداً عند الوصول</span>
    </p>
  );
}

/** **الراكبُ الفعليُّ** — اسمُه ورقمُه وزرُّ الاتصال (`tel:` بالرقم كما طبّعته الخلفيةُ E.164). **ولا يُرسم بلا اسم**: الاسمُ والرقمُ
 *  يُنشران من القبول حتى الانتهاء وحدَه، وصفٌّ فارغٌ يُقرأ عطباً. */
export function PassengerRowT2({ ride }: { ride: Ride }) {
  if (!ride.for_other || !ride.passenger_name) return null;
  return (
    <div className="t2-rd-rider t2-fo-passenger">
      <span className="t2-fo-passenger-icon" aria-hidden="true">
        <Icon name="person" />
      </span>
      <div className="t2-rd-rider-main">
        <div className="t2-rd-rider-name">الراكب: {ride.passenger_name}</div>
        {ride.passenger_phone ? (
          <div className="t2-rd-rider-sub">
            <span dir="ltr">{ride.passenger_phone}</span>
          </div>
        ) : null}
      </div>
      {ride.passenger_phone ? (
        <a className="t2-fo-call" href={`tel:${ride.passenger_phone}`} aria-label="اتصل بالراكب">
          <Icon name="call" />
        </a>
      ) : null}
    </div>
  );
}
