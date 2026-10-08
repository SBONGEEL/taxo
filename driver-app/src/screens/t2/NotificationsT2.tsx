/** الإشعارات — TAXO 2.0 «C14» (Claude Design «Captain»)، **في المظهر الداكن المرسوم وحدَه**.
 *
 * **السلوكُ هو هو** (`screens/Notifications.tsx`): صفحاتٌ من ثلاثين (`GET /me/notifications`
 * بإزاحة) و«عرض المزيد»؛ والنقرُ على غير المقروء يعلّمه وحدَه (`POST /me/notifications/read`
 * بمعرّفه) ثمّ يفتح وجهتَه أو يعيد التحميل؛ و«قراءة الكل» تعلّم الكلَّ وتقرأ محلّياً كما كانت.
 * والصياغةُ من `lib/notification-text`، والوجهةُ من `lib/notification-route` — بيتٌ واحدٌ للشاشتين.
 * **وما تغيّر طبقةُ العرض وحدَها**: التجميعُ باليوم، ودوائرُ الأنواع بنبرات C14، ونقطةُ غير المقروء.
 *
 * **وما لم تَرسمه اللوحةُ — بعلّته** (`design/TAXO2-DESIGN-CORRECTIONS.md`): «أقدم» لما قبل الأسبوع،
 * و«عرض المزيد» (التطبيقُ يقلّب صفحاتٍ اليوم)، وأيقوناتُ أنواعٍ لم تُرسم بنبرات C14 نفسِها.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { listNotifications, markNotificationsRead } from "@/api/endpoints";
import type { UserNotification } from "@/api/types";
import { EmptyNote, ErrorNote, Spinner } from "@/components/ui/Feedback";
import { useGoBack } from "@/lib/back";
import { destinationFor } from "@/lib/notification-route";
import { composeBody } from "@/lib/notification-text";
import { DISPLAY_LOCALE } from "@/lib/utils";

import "@/taxo2";
import "./t2.css";

const PAGE_SIZE = 30;

type Tone = "ok" | "warn" | "hot" | "danger" | "plain";

/** الأيقونةُ (Material Symbols) ونبرتُها — **معنى القائمة نفسُه بلغة C14**:
 *  أخضرُ لما وصل، وكهرمانٌ لما يقترب أجلُه، وجمرٌ للرحلة الجارية، وأحمرُ لما يوقف العمل. */
const KIND_STYLE: Record<string, { icon: string; tone: Tone }> = {
  driver_assigned: { icon: "local_taxi", tone: "hot" },
  ride_started: { icon: "local_taxi", tone: "hot" },
  ride_completed: { icon: "local_taxi", tone: "ok" },
  ride_cancelled: { icon: "local_taxi", tone: "danger" },
  cliq_transfer_submitted: { icon: "account_balance_wallet", tone: "warn" },
  subscription_expiring: { icon: "card_membership", tone: "warn" },
  subscription_expired: { icon: "card_membership", tone: "danger" },
  document_approved: { icon: "verified", tone: "ok" },
  document_rejected: { icon: "description", tone: "danger" },
  // **الحجزُ المضمون** (§٦٣-ج/٣) — سؤالُ «هل أنت في الطريق؟» بالجمر، وسحبُه بلا ردٍّ بالكهرمان
  guarantee_confirm: { icon: "schedule", tone: "hot" },
  guarantee_dropped: { icon: "event_upcoming", tone: "warn" },
  // **المدفوعاتُ غيرُ المؤكَّدة** (`design/PAYMENTS-UNCONFIRMED.md` §٣/§٦، SPEC §٦٤-ز) — التذكيرُ بالكهرمان (أجلٌ يقترب)، والنزاعُ
  // بالأحمر، و«عُدّ مبلغُ رحلة … مستلَماً» بالكهرمان: نافذةُ اعتراضٍ تقترب. **ولمستُها تفتح «ركّابٌ ينتظرون تأكيدك»**
  // (`notification-route`) — وأيقوناتُها من خطِّ التطبيق المقتطع (`index.html`)
  payment_reminder: { icon: "payments", tone: "warn" },
  payment_disputed: { icon: "error", tone: "danger" },
  payment_auto_confirmed: { icon: "receipt_long", tone: "warn" },
  campaign: { icon: "campaign", tone: "plain" },
};
const DEFAULT_STYLE = { icon: "notifications", tone: "plain" as Tone };

type Group = "today" | "yesterday" | "week" | "older";
const GROUP_LABEL: Record<Group, string> = {
  today: "اليوم",
  yesterday: "أمس",
  week: "هذا الأسبوع",
  older: "أقدم",
};
const GROUP_ORDER: Group[] = ["today", "yesterday", "week", "older"];
const DAY_MS = 24 * 60 * 60 * 1000;

function groupOf(iso: string, startOfToday: number): Group {
  const at = new Date(iso).getTime();
  if (at >= startOfToday) return "today";
  if (at >= startOfToday - DAY_MS) return "yesterday";
  if (at >= startOfToday - 6 * DAY_MS) return "week";
  return "older";
}

/** الوقتُ كما في اللوحة: ساعةٌ بأربعٍ وعشرين لليوم وأمس، واسمُ اليوم للأسبوع، والتاريخُ لما قبله. */
function whenLabel(iso: string, group: Group): string {
  const at = new Date(iso);
  if (group === "today" || group === "yesterday") {
    return at.toLocaleTimeString(DISPLAY_LOCALE, {
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    });
  }
  if (group === "week") {
    return at.toLocaleDateString(DISPLAY_LOCALE, { weekday: "long" });
  }
  return at.toLocaleDateString(DISPLAY_LOCALE, { day: "numeric", month: "long" });
}

export function NotificationsT2Screen() {
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
    const destination = destinationFor(entry.kind, entry.data);
    if (destination) navigate(destination);
    else void load(0);
  }

  const unread = (entries ?? []).some((entry) => entry.read_at === null);
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const grouped = new Map<Group, UserNotification[]>();
  for (const entry of entries ?? []) {
    const group = groupOf(entry.created_at, startOfToday);
    grouped.set(group, [...(grouped.get(group) ?? []), entry]);
  }

  return (
    <div className="t2 t2-notifs">
      <div className="t2-head">
        <button type="button" className="t2-back" aria-label="رجوع" onClick={() => goBack()}>
          <span className="t2-icon" aria-hidden="true">arrow_forward</span>
        </button>
        <h1 className="t2-title">الإشعارات</h1>
        {unread ? (
          <button type="button" className="t2-action" onClick={() => void readAll()}>
            قراءة الكل
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

      {GROUP_ORDER.filter((group) => grouped.has(group)).map((group) => (
        <section key={group}>
          <div className="t2-group">{GROUP_LABEL[group]}</div>
          <div className="t2-list">
            {(grouped.get(group) ?? []).map((entry) => {
              const style = KIND_STYLE[entry.kind] ?? DEFAULT_STYLE;
              return (
                <button
                  key={entry.id}
                  type="button"
                  className="t2-row"
                  onClick={() => void open(entry)}
                >
                  <span className={`t2-badge ${style.tone}`}>
                    <span className="t2-icon" aria-hidden="true">{style.icon}</span>
                  </span>
                  <span className="t2-row-main">
                    <span className="t2-row-top">
                      <span className="t2-row-title">{entry.title}</span>
                      <span className="t2-row-when">
                        {/* الساعةُ وحدَها بخطٍّ لاتينيٍّ متّصل؛ واسمُ اليوم والتاريخُ عربيّان */}
                        <span dir={group === "today" || group === "yesterday" ? "ltr" : undefined}>
                          {whenLabel(entry.created_at, group)}
                        </span>
                        {entry.read_at === null ? (
                          <span className="t2-unread" aria-label="غير مقروء" />
                        ) : null}
                      </span>
                    </span>
                    <span className="t2-row-body">{composeBody(entry) ?? entry.body}</span>
                  </span>
                </button>
              );
            })}
          </div>
        </section>
      ))}

      {more ? (
        <button
          type="button"
          className="t2-more"
          disabled={busy}
          onClick={() => void load(entries?.length ?? 0)}
        >
          {busy ? "…" : "عرض المزيد"}
        </button>
      ) : null}
    </div>
  );
}
