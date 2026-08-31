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

export function PhonePendingNotice() {
  const { user } = useSession();
  if (!user?.phone_pending) return null;

  return (
    <div
      role="status"
      className="mb-10 flex items-start gap-10 rounded-14 border border-line bg-surface-2 px-12 py-10"
    >
      <ShieldAlert className="mt-2 size-16 shrink-0 text-warn" />
      <div className="min-w-0 flex-1">
        <div className="text-12 font-bold text-ink">أكّد رقم هاتفك</div>
        <p className="mt-2 text-11 leading-note text-muted">
          سجّلتَ ببريدك، والرقمُ محجوزٌ باسمك ولم يُثبَت بعد — فلا محفظةَ حتى تؤكّده،
          ولا اعتمادَ لوثائقك.
        </p>
        <Link
          to="/account/settings"
          className="mt-6 inline-block text-11 font-semibold text-accent underline"
        >
          أكّده الآن
        </Link>
      </div>
    </div>
  );
}
