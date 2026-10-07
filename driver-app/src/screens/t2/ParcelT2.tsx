/** **الطرد** (§٦٣-ج/٤) — وجوهُه في تطبيق الكبتن: **صفُّ المستلم** باسمه وعنوانه وزرِّ الاتصال به (بعد القبول وحدَه —
 * `recipient_*` لا تُنشر قبله)، **و«ارفض الطرد» بخطوة تأكيدها** في طور «وصل».
 *
 * **لا لوحةَ لها في Claude Design** — فتُركَّب من عُدّة الهوية: صفُّ المستلم هو صفُّ الراكب الفعليّ نفسُه (`t2-rd-rider` ·
 * `t2-fo-call`)، و«ارفض الطرد» زرُّ «نقطة توقف» الثانويّ (`t2-rd-btn ghost`)، **وتأكيدُه ورقةُ أسباب الإلغاء** (`t2-rd-cx-*`).
 * وشارةُ «طرد» على العرض وسطرُ دافعه في بيتيهما (`OfferT2` · `PayerNoteT2`).
 *
 * **والرفضُ إلغاءٌ تكتب الخلفيةُ سببَه** (`parcel_refused`) **بلا مالٍ على أحد** — فليس سبباً بين أسباب «إلغاء الرحلة».
 */

import type { Ride } from "@/api/types";
import { Icon } from "@/taxo2";

/** **المستلم** — «المستلم: الاسم» وعنوانُ التسليم تحته، وزرُّ `tel:` بالرقم كما طبّعته الخلفيةُ E.164. **ولا يُرسم بلا اسم**:
 *  الثلاثةُ تُنشر من القبول حتى الانتهاء وحدَه، وصفٌّ فارغٌ يُقرأ عطباً. */
export function RecipientRowT2({ ride }: { ride: Ride }) {
  if (ride.ride_type !== "parcel" || !ride.recipient_name) return null;
  return (
    <div className="t2-rd-rider t2-fo-passenger t2-pc-recipient">
      <span className="t2-fo-passenger-icon" aria-hidden="true">
        <Icon name="package_2" />
      </span>
      <div className="t2-rd-rider-main">
        <div className="t2-rd-rider-name">المستلم: {ride.recipient_name}</div>
        {ride.recipient_address ? <div className="t2-rd-rider-sub">{ride.recipient_address}</div> : null}
      </div>
      {ride.recipient_phone ? (
        <a className="t2-fo-call" href={`tel:${ride.recipient_phone}`} aria-label="اتصل بالمستلم">
          <Icon name="call" />
        </a>
      ) : null}
    </div>
  );
}

/** **«ارفض الطرد»** — فعلٌ ثانويٌّ تحت «بدء الرحلة» في طور «وصل» وحدَه: من شكّ في طردٍ عند استلامه لا يحمله. */
export function RefuseParcelButtonT2({ busy, onOpen }: { busy: boolean; onOpen: () => void }) {
  return (
    <button type="button" className="t2-rd-btn ghost" onClick={onOpen} disabled={busy}>
      ارفض الطرد
    </button>
  );
}

/** **تأكيدُ الرفض** — ورقةُ أسباب الإلغاء بلغتها، **بلا أسباب**: السببُ واحدٌ تكتبه الخلفية، والجملةُ تقول أثرَه قبل أن يقع. */
export function RefuseParcelSheetT2({
  busy,
  onConfirm,
  onClose,
}: {
  busy: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <div className="t2-rd-cx-shade">
      <div className="t2-rd-cx-sheet" role="dialog" aria-label="ارفض الطرد">
        <div className="t2-rd-grab" />
        <h2 className="t2-rd-cx-title">ترفض الطرد عند الاستلام؟</h2>
        <p className="t2-rd-cx-note">تُلغى الرحلةُ بلا مالٍ على أحد.</p>
        <button type="button" className="t2-rd-cx-confirm" disabled={busy} onClick={onConfirm}>
          نعم، ارفض الطرد
        </button>
        <button type="button" className="t2-rd-cancel" onClick={onClose}>
          تراجع
        </button>
      </div>
    </div>
  );
}
