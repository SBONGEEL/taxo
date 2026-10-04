/** صياغةُ صفِّ الإشعار — **بيتٌ واحدٌ للشاشتين** (القائمة وTAXO 2.0 «C14»).
 *
 * **نُقلت من `screens/Notifications.tsx` حرفاً** يومَ صار للإشعارات شاشتان (§61-ب: المظهرُ
 * المرسومُ بتصميمه الجديد، والآخرُ بشاشته القائمة حتى يُرسم). **وشاشتان تصوغان النصَّ مرّتين
 * تفترقان أوّلَ نوعٍ يُضاف.** والوجهةُ بيتُها `lib/notification-route` منذ 2026-08-21.
 *
 * **والنصُّ يُصاغ من `data` لا يُقرأ من `body`.** الخلفية تكتب `title` و`body` لدرج نظام
 * التشغيل وتضع القيمَ خاماً في `data`. فما نعرف صياغته نصوغه، وما لا نعرفه يقع على نصّ
 * الخلفية: نوعٌ جديدٌ يظهر بنصٍّ صحيح بدل صفٍّ فارغ.
 */

import type { Currency, UserNotification } from "@/api/types";
import { CURRENCY_LABEL, formatWhen } from "@/lib/rideFormat";
import { digits } from "@/lib/utils";

/** نصُّ الصف مصوغاً من القيم الخام — و`null` يعني «قع على نصّ الخلفية». */
export function composeBody(entry: UserNotification): string | null {
  const data = entry.data;
  if (!data) return null;

  const money =
    data.amount && data.currency
      ? `${digits(data.amount)} ${CURRENCY_LABEL[data.currency as Currency] ?? ""}`
      : null;

  switch (entry.kind) {
    case "cliq_transfer_submitted":
      return money && data.transfer_reference
        ? `${money} — مرجع الحوالة ${data.transfer_reference}`
        : money;
    case "cliq_confirmation_expired":
      return money ? `${money} — تفصل فيها الإدارة الآن.` : null;
    case "ride_completed":
      return money ? `أجرة الرحلة ${money}.` : null;
    case "document_rejected":
      return data.review_note || null;
    case "subscription_expiring":
    case "subscription_expired":
      return data.expires_at
        ? `تغطيتك حتى ${formatWhen(data.expires_at)}.`
        : null;
    default:
      return null;
  }
}
