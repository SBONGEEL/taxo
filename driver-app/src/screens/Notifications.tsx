/** الإشعارات — SPEC القسم 12/8، وشكلُها من `DESIGN.md` §5.3.
 *
 * **صندوقُ وارد لا سجلُّ إرسال**: الصفُّ يُكتب في `user_notifications` قبل
 * محاولة الدفع بـPush وفي `try/except` مستقل (`_safe_notify` — المرحلة 9-ب)،
 * فهو أثرُ **الحدث** لا أثرُ المزود: يوجد بلا عقد FCM أصلاً، ويوجد حين كان
 * المقبس مفتوحاً فلم يُرسل Push من الأساس.
 *
 * **وما لا يُحفظ هنا محذوفٌ بقصد**: بطاقةُ الطلب (`EPHEMERAL_KINDS`) عمرُها
 * عشرون ثانية، وصفٌّ باقٍ اسمُه «طلبٌ جديد» يفتح لا شيءَ بعد انقضائها —
 * و`driver_assigned` هو الأثرُ الصحيح لما وقع. والحملاتُ التسويقية تُكتب
 * لمن وصلَته وحده (`DeliveryStatus.SENT`)، فوجودُ صفٍّ لمن أطفأ إشعارات
 * العروض التفافٌ على اختيارٍ صريح.
 *
 * **و`kind` هو `data.type` نفسه**، فالنقرُ على الصف والنقرُ على إشعار نظام
 * التشغيل يفتحان الشاشة ذاتها — لا خريطتان تفترقان.
 *
 * **والنصُّ يُصاغ هنا من `data` لا يُقرأ من `body`.** الخلفية تكتب `title`
 * و`body` لدرج نظام التشغيل — يرسمهما والتطبيق مغلق ولا واجهةَ تصوغ حينها —
 * وتضع القيم خاماً في `data`. فما نعرف صياغته نصوغه بخاناتٍ عربيةٍ-هندية
 * ورمزِ عملةٍ عربي، وما لا نعرفه يقع على نصّ الخلفية: نوعٌ جديد يظهر بنصٍّ
 * صحيح بدل صفٍّ فارغ.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { destinationFor } from "@/lib/notification-route";
import {
  Bell,
  BadgeCheck,
  CalendarClock,
  Car,
  ChevronLeft,
  FileWarning,
  Megaphone,
  Wallet,
  type LucideIcon,
} from "lucide-react";

import { ApiError } from "@/api/client";
import { Stagger, StaggerItem } from "@/components/ui/Motion";
import { listNotifications, markNotificationsRead } from "@/api/endpoints";
import type { Currency, UserNotification } from "@/api/types";
import { EmptyNote, ErrorNote, Spinner } from "@/components/ui/Feedback";
import { CURRENCY_LABEL, formatWhen } from "@/lib/rideFormat";
import { digits, cn } from "@/lib/utils";
import { useGoBack } from "@/lib/back";

const PAGE_SIZE = 30;

/** أيقونةُ كل نوعٍ ولونُه — والمفاتيح هي قيم `RideEvent`/`PaymentEvent`
 * وأخواتها حرفاً بحرف، فنوعٌ جديدٌ في الخلفية يسقط على الافتراضي ولا يكسر. */
const KIND_STYLE: Record<string, { icon: LucideIcon; tone: string }> = {
  driver_assigned: { icon: Car, tone: "text-ink" },
  ride_started: { icon: Car, tone: "text-ink" },
  ride_completed: { icon: Car, tone: "text-ok" },
  ride_cancelled: { icon: Car, tone: "text-danger" },
  cliq_transfer_submitted: { icon: Wallet, tone: "text-warn" },
  subscription_expiring: { icon: CalendarClock, tone: "text-warn" },
  subscription_expired: { icon: CalendarClock, tone: "text-danger" },
  document_approved: { icon: BadgeCheck, tone: "text-ok" },
  document_rejected: { icon: FileWarning, tone: "text-danger" },
  campaign: { icon: Megaphone, tone: "text-muted" },
};

/** نصُّ الصف مصوغاً من القيم الخام — و`null` يعني «قع على نصّ الخلفية». */
function composeBody(entry: UserNotification): string | null {
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

/** أين يذهب الصفُّ حين يُنقر — **من `lib/notification-route` لا من هنا**.
 *
 * نُقل الحسابُ إلى بيتٍ واحدٍ حين وُلد مسارُ إشعارات النظام (2026-08-21):
 * النقرُ على الصفِّ والنقرُ على الإشعار **حدثٌ واحد**، وبيتان له يفتحان
 * شاشتين لنفس الخبر.
 */
function destinationOf(entry: UserNotification): string | null {
  return destinationFor(entry.kind, entry.data);
}

export function NotificationsScreen() {
  const navigate = useNavigate();
  const goBack = useGoBack();
  const [entries, setEntries] = useState<UserNotification[] | null>(null);
  const [more, setMore] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (offset: number) => {
    setBusy(true);
    try {
      const page = await listNotifications(PAGE_SIZE, offset);
      setEntries((current) =>
        offset === 0 ? page : [...(current ?? []), ...page],
      );
      setMore(page.length === PAGE_SIZE);
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة الإشعارات",
      );
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void load(0);
  }, [load]);

  async function readAll() {
    try {
      await markNotificationsRead();
      // القراءةُ محلياً كذلك: الخلفية تردّ العدّاد لا الصفوف
      setEntries((current) =>
        (current ?? []).map((entry) =>
          entry.read_at
            ? entry
            : { ...entry, read_at: new Date().toISOString() },
        ),
      );
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر التعليم");
    }
  }

  async function open(entry: UserNotification) {
    if (!entry.read_at) {
      await markNotificationsRead([entry.id]).catch(() => undefined);
    }
    const destination = destinationOf(entry);
    if (destination) navigate(destination);
    else void load(0);
  }

  const unread = (entries ?? []).some((entry) => entry.read_at === null);

  return (
    <div className="scr h-full bg-bg px-16 pb-12 pt-safe">
      <div className="mb-16 mt-6 flex items-center gap-10">
        <button
          type="button"
          onClick={() => goBack()}
          aria-label="رجوع"
          className="pressable text-18 text-muted"
        >
          →
        </button>
        <h1 className="flex-1 text-20 font-bold text-ink">الإشعارات</h1>
        {unread ? (
          <button
            type="button"
            onClick={() => void readAll()}
            className="pressable text-11.5 font-semibold text-muted"
          >
            تعليم الكل كمقروء
          </button>
        ) : null}
      </div>

      <ErrorNote message={error} />

      {entries === null && !error ? <Spinner className="mx-auto" /> : null}

      {entries?.length === 0 ? (
        <EmptyNote
          title="لا إشعارات"
          hint="ما يخص رحلاتك واشتراكك ومستنداتك يصلك هنا، ويبقى بعد أن يمر."
        />
      ) : null}

      <Stagger className="flex flex-col gap-9">
        {(entries ?? []).map((entry) => {
          const style = KIND_STYLE[entry.kind] ?? {
            icon: Bell,
            tone: "text-muted",
          };
          const Icon = style.icon;
          return (
            <StaggerItem key={entry.id}>
              <button
                type="button"
                onClick={() => void open(entry)}
                className={cn(
                  "pressable flex w-full items-start gap-12 rounded-15 border bg-surface px-14 py-13 text-start",
                  entry.read_at ? "border-line" : "border-ink",
                )}
              >
                <span
                  className={cn(
                    "flex size-30 flex-none items-center justify-center rounded-9 bg-surface-2",
                    style.tone,
                  )}
                >
                  <Icon size={14} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-13 font-bold text-ink">
                    {entry.title}
                  </span>
                  <span className="mt-2 block text-11.5 leading-snug text-muted">
                    {composeBody(entry) ?? entry.body}
                  </span>
                  <span className="mt-5 block text-10.5 text-muted">
                    {formatWhen(entry.created_at)}
                  </span>
                </span>
                {/* سهمٌ لما يفتح شاشة: صفٌّ قابلٌ للنقر بلا علامةٍ لا يُنقر */}
                {destinationOf(entry) ? (
                  <ChevronLeft size={15} className="mt-3 shrink-0 text-muted" />
                ) : null}
              </button>
            </StaggerItem>
          );
        })}
      </Stagger>

      {more ? (
        <button
          type="button"
          disabled={busy}
          onClick={() => void load(entries?.length ?? 0)}
          className="pressable mt-12 w-full rounded-14 border border-line py-13 text-center text-12.5 font-semibold text-muted disabled:opacity-60"
        >
          {busy ? "…" : "عرض المزيد"}
        </button>
      ) : null}
    </div>
  );
}
