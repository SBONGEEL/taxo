/** بطاقةُ الهوية والصورة — **والصورةُ بورقة §١٠٩-هـ** (`components/ProfilePhoto`: التقاط · معرض · تعديلٌ دائريّ · حذف)؛ — TAXO 2.0 «R22» (`design/t2-new/rider/R22-profile.dc.html`): **الدائرةُ هي الصورة** — المختارةُ
 *  أو المرفوعةُ في هذه الجلسة، وإلا الحرفُ الأوّل كما في R15 — وبجانبها الاسمُ والرقم، ثمّ البريدُ المُثبَت، ثمّ «صورتي» وأفعالُها.
 *
 * **والصورةُ اختياريةٌ، بمعاينةٍ قبل الرفع، وبلا مراجعة**
 *  (قرارُ المالك 2026-08-22، `PUT`/`DELETE /auth/me/photo`).
 *
 * **ولا تُكتب هنا كلمةٌ توحي بانتظار موافقة**: البابُ يَنشر فور الرفع، وشاشةٌ
 * تقول «قيد المراجعة» عن شيءٍ لا يُراجَع تجعل صاحبَها ينتظر ما وقع أصلاً.
 *
 * **والرفعُ بلا مهلةٍ يلزمه ثلاثة** (SPEC ١٧.٦): **نسبةٌ** تقول «يتقدّم»،
 * **وزرُّ إلغاءٍ** يقول «تستطيع الخروج»، **وكاشفُ ركود** — والثالثُ ليس
 * تكراراً للثاني: الإلغاءُ يعالج من قرّر التوقّف، والركودُ يعالج **وصلةً
 * ماتت صامتة** فيقف الشريطُ بلا حدثٍ ولا رسالة. وهما يمرّان بنفس الحدث
 * ويُفرَّقان: قطعُ الركود خطأٌ يُعرض ومعه **زرٌّ يحمل الملفَّ نفسَه**، وقطعُ
 * صاحبه قرارُه هو فلا يُعرض له شيء.
 *
 * **ولا منطقَ «هل له صورة» في التطبيق**: البابُ الذي يعرضها للكبتن يردّ
 * ٢٠٠ بصورةٍ دائماً بطولٍ ثابت — والغيابُ المرئيُّ نفسُه وشاية (الشكلُ
 * الثالثَ عشر). فلا تُرسم هنا حالٌ اسمُها «لا صورةَ لك» ولا يُقاس عليها شيء.
 *
 * **والاسمُ والرقمُ والبريدُ هنا لا في الشاشة** لأن الدائرةَ بجانبها هي الصورةُ نفسُها — فلا تُرسم دائرتان لشخصٍ واحد.
 * **والرقمُ لا يُحرَّر ولا يُعرَّب** — معرَّفٌ يُقارَن ويُملى؛ **والبريدُ يُعرض ولا يُحرَّر** (قرارُ المالك 2026-08-31): تغييرُ
 * بريدٍ مُثبَتٍ يحتاج إثباتَ الجديد، و`null` تعني لا بريدَ مُثبَت فلا يُرسم سطرٌ فارغ.
 */

import { clearMyPhoto, getMyPhoto, setMyPhoto } from "@/api/endpoints";
import { ProfilePhoto } from "@/components/ProfilePhoto";
import { useSession } from "@/lib/session";
import { tr } from "@/lib/i18n";

export function PhotoCard() {
  const { user, refreshUser } = useSession();

  return (
    <section className="t2-idcard">
      <div className="t2-idcard-top">
        {/* **الدائرةُ هي الصورة** — صورتُه كما رفعها (`GET /auth/me/photo`)، وإلا حرفُ اسمه في دائرةٍ لونُها من اسمه */}
        <ProfilePhoto
          name={user?.name ?? ""}
          load={() => getMyPhoto().catch(() => null)}
          upload={async (file) => {
            await setMyPhoto(file);
          }}
          remove={async () => {
            await clearMyPhoto();
          }}
          onChanged={() => void refreshUser()}
        />
        <div className="t2-prof-main">
          <div className="t2-prof-name">{user?.name}</div>
          <div dir="ltr" className="t2-prof-phone">
            {user?.phone}
          </div>
        </div>
      </div>

      {user?.email ? (
        <div className="t2-idcard-sec">
          <p className="t2-idcard-label">{tr("البريد المُثبَت")}</p>
          <p dir="ltr" className="t2-idcard-email">
            {user.email}
          </p>
        </div>
      ) : null}

      <div className="t2-idcard-sec">
        <p className="t2-idcard-title">{tr("صورتي")}</p>
        <p className="t2-idcard-body">
          {tr("اختياريةٌ، ويراها كابتنُ رحلتك بعد قبوله طلبَك وحده — لا قبله، ولا يراها راكبٌ آخر. وتظهر فور رفعها. المس الدائرةَ لتغييرها أو حذفها.")}
        </p>
      </div>
    </section>
  );
}
