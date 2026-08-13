/** الإشعارات — تصميمُ الراكب (`pgNotifs`) و`DESIGN.md` §5.2.
 *
 * **نقصٌ وظيفيٌّ لا شكليّ** (قرارُ المالك 2026-08-13): الصندوقُ مبنيٌّ في
 * الخلفية منذ 9-ب ويُكتب فيه من بابَي الإرسال معاً، وتطبيقُ الكبتن يقرؤه —
 * وتطبيقُ الراكب لم يكن يقرؤه. فكان الراكبُ لا يرى نتيجةَ نزاعٍ فُصل، ولا
 * تنبيهاً وصله والتطبيقُ مغلق، ولا حجزاً لم يُنفَّذ.
 *
 * **والنصُّ يُصاغ هنا من `data` لا يُقرأ من `body`**: الخلفيةُ تكتب `title`
 * و`body` لدرج نظام التشغيل — يرسمهما والتطبيقُ مغلقٌ ولا واجهةَ تصوغ حينها —
 * وتضع القيمَ خاماً في `data` (القسم 10). فما نعرف صياغتَه نصوغه، وما لا نعرفه
 * يقع على نصِّ الخلفية: **نوعٌ جديدٌ يظهر بنصٍّ صحيح بدل صفٍّ فارغ**.
 *
 * **ولا زرَّ حذف**: الصفُّ أثرُ حدثٍ وقع، وحذفُه محوُ سجلٍّ لا تنظيمُ صندوق —
 * والتقليمُ بالعمر مهمةٌ دورية (`inbox.trim`، تسعون يوماً).
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bell,
  CalendarClock,
  Car,
  CheckCheck,
  Megaphone,
  TicketPercent,
  Wallet,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { ApiError } from "@/api/client";
import { listNotifications, markNotificationsRead } from "@/api/endpoints";
import type { UserNotification } from "@/api/types";
import { Screen } from "@/components/ui/Screen";
import { Stagger, StaggerItem } from "@/components/ui/Motion";
import { EmptyState, ErrorNote, Spinner } from "@/components/ui/Feedback";
import { formatMoney } from "@/lib/utils";
import { cn } from "@/lib/utils";

/** الأيقونةُ واللونُ بحسب النوع — والافتراضُ جرسٌ محايد لنوعٍ لا نعرفه. */
const KIND_STYLE: Record<string, { icon: LucideIcon; tone: string }> = {
  driver_assigned: { icon: Car, tone: "text-ink" },
  driver_arrived: { icon: Car, tone: "text-ink" },
  ride_started: { icon: Car, tone: "text-ink" },
  ride_completed: { icon: Car, tone: "text-ok" },
  ride_cancelled: { icon: Car, tone: "text-danger" },
  no_driver_found: { icon: Car, tone: "text-warn" },
  stop_wait_exceeded: { icon: CalendarClock, tone: "text-warn" },
  cliq_confirmation_expired: { icon: Wallet, tone: "text-danger" },
  topup_confirmed: { icon: Wallet, tone: "text-ok" },
  booking_missed: { icon: CalendarClock, tone: "text-warn" },
  booking_no_driver: { icon: CalendarClock, tone: "text-danger" },
  booking_preference_dropped: { icon: CalendarClock, tone: "text-warn" },
  women_mode_revoked: { icon: Bell, tone: "text-warn" },
  campaign: { icon: Megaphone, tone: "text-muted" },
  promo: { icon: TicketPercent, tone: "text-ok" },
};

/** نصُّ الصف مصوغاً من القيم الخام — و`null` يعني «قع على نصّ الخلفية». */
function composeBody(entry: UserNotification): string | null {
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
function destinationOf(entry: UserNotification): string | null {
  const rideId = entry.data?.ride_id;
  const bookingId = entry.data?.booking_id;
  if (bookingId && !rideId) return "/account/bookings";
  if (rideId) return `/rides/${rideId}`;
  if (entry.kind === "topup_confirmed") return "/wallet";
  return null;
}

function when(iso: string): string {
  return new Date(iso).toLocaleString("ar", {
    day: "numeric",
    month: "long",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function NotificationsScreen() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<UserNotification[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRows(await listNotifications());
  }, []);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة الإشعارات",
      ),
    );
  }, [load]);

  async function markAll() {
    try {
      await markNotificationsRead();
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر التحديد");
    }
  }

  const unread = (rows ?? []).some((row) => row.read_at === null);

  return (
    <Screen
      title="الإشعارات"
      back="/account"
      nav
      action={
        unread ? (
          <button
            type="button"
            onClick={() => void markAll()}
            className="pressable flex items-center gap-6 text-12.5 font-semibold text-muted"
          >
            <CheckCheck className="size-14" />
            تحديد الكل كمقروء
          </button>
        ) : undefined
      }
    >
      <ErrorNote message={error} />
      {rows === null && !error ? <Spinner /> : null}
      {rows?.length === 0 ? (
        <EmptyState
          title="لا إشعارات بعد"
          hint="ستجد هنا أخبار رحلاتك وشحن رصيدك."
        />
      ) : null}

      <Stagger className="space-y-8">
        {(rows ?? []).map((entry) => {
          const style = KIND_STYLE[entry.kind] ?? {
            icon: Bell,
            tone: "text-muted",
          };
          const Icon = style.icon;
          const to = destinationOf(entry);
          return (
            <StaggerItem key={entry.id}>
              <button
                type="button"
                disabled={to === null}
                onClick={() => to && navigate(to)}
                className={cn(
                  "pressable card flex w-full items-start gap-12 p-14 text-start",
                  to ? "transition hover:bg-surface-2" : "cursor-default",
                  // **غيرُ المقروء يُعلَم بحدٍّ لا بخلفيةٍ ملوّنة**: الخلفيةُ
                  // الملوّنة على صفوفٍ كثيرةٍ تصير هي الصفحةَ لا التمييز
                  entry.read_at === null && "border-accent-line",
                )}
              >
                <Icon className={cn("mt-2 size-18 shrink-0", style.tone)} />
                <span className="min-w-0 flex-1">
                  <span className="block font-medium text-ink">
                    {entry.title}
                  </span>
                  <span className="mt-2 block text-12.5 leading-relaxed text-muted">
                    {composeBody(entry) ?? entry.body}
                  </span>
                  <span className="mt-4 block text-11 text-muted">
                    {when(entry.created_at)}
                  </span>
                </span>
                {entry.read_at === null ? (
                  <span className="mt-6 size-8 shrink-0 rounded-full bg-accent" />
                ) : null}
              </button>
            </StaggerItem>
          );
        })}
      </Stagger>
    </Screen>
  );
}
