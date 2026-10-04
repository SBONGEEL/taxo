/** «أكّد رقمك» — **سطرٌ في كلِّ فتحة** (قرارُ المالك 2026-08-31).
 *
 * **ولمَ في كلِّ فتحةٍ لا مرّةً واحدة**: `WomenModeNotice` جارُه يظهر مرّةً
 * لأنه **تعريفٌ بمفتاح** — قيل ما يُقال وانتهى. **وهذا حالٌ قائمةٌ لا خبر**:
 * الحسابُ محدودٌ **الآن**، ولا رحلةَ ولا محفظةَ حتى يُثبَت الرقم. **وإشعارٌ
 * يُغلق مرّةً يترك صاحبَه أمام رفضٍ لا يعرف سببَه بعد أسبوع.**
 *
 * **ولا يُغلَق بزرّ** للعلّة نفسِها: زرُّ إغلاقٍ على حالٍ قائمةٍ يخفي السببَ
 * ولا يزيله — **ومن أغلقه يبقى محدوداً ولا يرى لمَ**.
 *
 * **ويقول ما يُفعل لا ما وقع**: «رفضٌ بلا مخرجٍ ليس رفضاً» — وهي القاعدةُ
 * التي أصلحت التفضيلَ المجنَّس في 10-ج. فالسطرُ يحمل الطريقَ إلى الإثبات.
 *
 * **ولا يُرسم لمن رقمُه غيرُ مُثبَتٍ لسببٍ آخر**: `phone_verified === false`
 * لها معنيان — حسابٌ أُنشئ والمفتاحُ مطفأٌ للطوارئ **وهو كاملُ الصلاحية**،
 * وحسابٌ سجّل ببريده **وهو محدود**. **فيُقرأ `phone_pending` وحدَه**، وإلا
 * قيل لكاملِ الصلاحية إنه ممنوعٌ من الركوب وهو ليس كذلك.
 */

import { ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";

import { useSession } from "@/lib/session";

/** **مسارُ التأكيد في هذا التطبيق** — بيتٌ واحدٌ يقرؤه الحالان. */
const CONFIRM_PATH = "/account/profile";

/** نصُّ الحال المحدودة — **بيتٌ واحدٌ للوجهين**، فلا يفترق ما يقوله القائمُ عمّا يقوله TAXO 2.0. */
const PENDING_BODY =
  "سجّلتَ ببريدك، والرقمُ محجوزٌ باسمك ولم يُثبَت بعد — فلا طلبَ رحلةٍ ولا محفظةَ حتى تؤكّده.";

/** **وجهُ TAXO 2.0** — الحالان والنصّان والوجهةُ هي هي، والشكلُ من الهوية (`.t2-callout`). */
function CalloutT2({ tone, title, body }: { tone: "danger" | "warn"; title: string; body: string }) {
  return (
    <div role="status" className={`t2-callout ${tone}`}>
      <span className="t2-icon fill" aria-hidden="true">
        error
      </span>
      <div className="t2-callout-main">
        <div className="t2-callout-title">{title}</div>
        <p className="t2-callout-body">{body}</p>
        <Link to={CONFIRM_PATH} className="t2-callout-link">
          أكّده الآن
        </Link>
      </div>
    </div>
  );
}

export function PhonePendingNotice({ variant }: { variant?: "t2" } = {}) {
  const { user } = useSession();
  // **حالان لا واحدة**: `suspension` حسابٌ **كان كاملاً فأُوقف** بانقضاء
  // مهلة الحملة، و`phone_pending` حسابٌ **وُلد محدوداً** لأنه سجّل ببريده.
  // **والموقوفُ أشدّ فيُقدَّم**، ونصُّه يأتي من الخلفية لا يُكتب هنا.
  if (user?.suspension) {
    if (variant === "t2")
      return <CalloutT2 tone="danger" title="حسابك موقوف" body={user.suspension.message} />;
    return (
      <div
        role="status"
        className="mb-10 flex items-start gap-10 rounded-14 border border-line bg-surface-2 px-12 py-10"
      >
        <ShieldAlert className="mt-2 size-16 shrink-0 text-danger" />
        <div className="min-w-0 flex-1">
          <div className="text-12 font-bold text-ink">حسابك موقوف</div>
          <p className="mt-2 text-11 leading-note text-muted">
            {user.suspension.message}
          </p>
          <Link
            to={CONFIRM_PATH}
            className="mt-6 inline-block text-11 font-semibold text-accent underline"
          >
            أكّده الآن
          </Link>
        </div>
      </div>
    );
  }
  if (!user?.phone_pending) return null;

  if (variant === "t2")
    return (
      <CalloutT2
        tone="warn"
        title="أكّد رقم هاتفك"
        body={PENDING_BODY}
      />
    );

  return (
    <div
      role="status"
      className="mb-10 flex items-start gap-10 rounded-14 border border-line bg-surface-2 px-12 py-10"
    >
      <ShieldAlert className="mt-2 size-16 shrink-0 text-warn" />
      <div className="min-w-0 flex-1">
        <div className="text-12 font-bold text-ink">أكّد رقم هاتفك</div>
        <p className="mt-2 text-11 leading-note text-muted">{PENDING_BODY}</p>
        <Link
          to={CONFIRM_PATH}
          className="mt-6 inline-block text-11 font-semibold text-accent underline"
        >
          أكّده الآن
        </Link>
      </div>
    </div>
  );
}
