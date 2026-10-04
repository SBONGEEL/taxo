/** صياغةُ صفِّ الإشعار ووجهتُه — **بيتٌ واحدٌ للشاشتين** (القائمة وTAXO 2.0 «R14»).
 *
 * **نُقلتا من `screens/Notifications.tsx` حرفاً** يومَ صار للإشعارات شاشتان (§61-ب: المظهرُ
 * المرسومُ بتصميمه الجديد، والآخرُ بشاشته القائمة حتى يُرسم). **وشاشتان تصوغان النصَّ مرّتين
 * تفترقان أوّلَ نوعٍ يُضاف** — فالصياغةُ والوجهةُ هنا، وكلُّ شاشةٍ ترسم ما يخرج منهما.
 *
 * **والنصُّ يُصاغ من `data` لا يُقرأ من `body`**: الخلفيةُ تكتب `title` و`body` لدرج نظام
 * التشغيل وتضع القيمَ خاماً في `data` (القسم 10). فما نعرف صياغتَه نصوغه، وما لا نعرفه يقع
 * على نصِّ الخلفية: **نوعٌ جديدٌ يظهر بنصٍّ صحيح بدل صفٍّ فارغ**.
 */

import type { UserNotification } from "@/api/types";
import { formatMoney } from "@/lib/utils";

/** نصُّ الصف مصوغاً من القيم الخام — و`null` يعني «قع على نصّ الخلفية». */
export function composeBody(entry: UserNotification): string | null {
  const data = entry.data;
  if (!data) return null;

  const money =
    data.amount && data.currency
      ? formatMoney(data.amount, data.currency)
      : null;

  switch (entry.kind) {
    case "ride_completed":
      return money ? `أجرة الرحلة ${money}.` : null;
    case "cliq_confirmation_expired":
      return money ? `${money} — تفصل فيها الإدارة الآن.` : null;
    case "topup_confirmed":
      return money ? `أُضيف ${money} إلى رصيدك.` : null;
    default:
      return null;
  }
}

/** أين يذهب الصفُّ حين يُنقر — **من `data` لا من نصّ العنوان**. */
export function destinationOf(entry: UserNotification): string | null {
  const rideId = entry.data?.ride_id;
  const bookingId = entry.data?.booking_id;
  if (bookingId && !rideId) return "/account/bookings";
  if (rideId) return `/rides/${rideId}`;
  if (entry.kind === "topup_confirmed") return "/wallet";
  return null;
}
