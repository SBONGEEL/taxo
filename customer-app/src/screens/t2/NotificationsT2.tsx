/** الإشعارات — TAXO 2.0 «R14» (Claude Design «Rider»)، **في المظهرين** — رُسم نهاريّاً، **والليليُّ برموز إسفلت الهوية نفسِها** (§٦٢/٣).
 *
 * **الطلباتُ والوجهاتُ والنصوصُ هي هي** (`screens/Notifications.tsx`): `GET /notifications`
 * ثمّ `POST /notifications/read` لـ«قراءة الكل»، والصياغةُ والوجهةُ من `lib/notification-text`
 * — بيتٌ واحدٌ للشاشتين. **وما تغيّر طبقةُ العرض وحدَها**: التجميعُ باليوم، والدوائرُ بأنواعها،
 * ونقطةُ غير المقروء بجانب الوقت، وزرُّ الرجوع، **ولا شريطَ تبويبٍ** كما في اللوحة.
 *
 * **وما لم تَرسمه اللوحةُ — بعلّته** (`design/TAXO2-DESIGN-CORRECTIONS.md`):
 * - **أقدمُ من الأسبوع**: اللوحةُ ترسم «اليوم · أمس · هذا الأسبوع» وحدَها، فالأقدمُ تحت «أقدم».
 * - **أنواعٌ لم تُرسم** (حجزٌ لم يُنفَّذ، إلغاء…): بالدائرة المحايدة ولونِ معناها من الهوية
 *   (`Identity`: نجاح · تنبيه · خطأ) — لا لونٌ جديد.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { listNotifications, markNotificationsRead } from "@/api/endpoints";
import type { UserNotification } from "@/api/types";
import { EmptyState, ErrorNote, Spinner } from "@/components/ui/Feedback";
import { composeBody, destinationOf } from "@/lib/notification-text";
import { DISPLAY_LOCALE } from "@/lib/utils";

import "@/taxo2";
import "./t2.css";

type Tone = "live" | "plain" | "offer" | "money" | "women" | "warn" | "danger";

/** الأيقونةُ (Material Symbols) ونبرةُ دائرتها بحسب النوع — **معنى القائمة نفسُه بلغة اللوحة**. */
const KIND_STYLE: Record<string, { icon: string; tone: Tone }> = {
  driver_assigned: { icon: "local_taxi", tone: "live" },
  driver_arrived: { icon: "local_taxi", tone: "live" },
  ride_started: { icon: "local_taxi", tone: "live" },
  ride_completed: { icon: "receipt_long", tone: "plain" },
  ride_cancelled: { icon: "local_taxi", tone: "danger" },
  no_driver_found: { icon: "local_taxi", tone: "warn" },
  stop_wait_exceeded: { icon: "calendar_clock", tone: "warn" },
  cliq_confirmation_expired: { icon: "account_balance_wallet", tone: "danger" },
  topup_confirmed: { icon: "account_balance_wallet", tone: "money" },
  booking_missed: { icon: "calendar_clock", tone: "warn" },
  booking_no_driver: { icon: "calendar_clock", tone: "danger" },
  booking_preference_dropped: { icon: "calendar_clock", tone: "warn" },
  // **حجزٌ نسائيٌّ لم نطلبه والخدمةُ متوقّفة** (§٦٤-ج/٤-١) — بالبرقوق كأخيه `women_mode_revoked`، ولمستُه تفتح «رحلاتي المجدولة»
  // حيث تختار هي «أي كبتن» أو الإلغاء (`destinationOf`: حجزٌ بلا رحلة)
  booking_women_paused: { icon: "woman", tone: "women" },
  // **الحجزُ المضمون** (§٦٣-ج/٣) — كبتنٌ قبله · اعتذر فنبحث عن غيره · رُدّ الرسمُ إلى المحفظة
  guarantee_accepted: { icon: "verified_user", tone: "live" },
  guarantee_reopened: { icon: "calendar_clock", tone: "warn" },
  guarantee_refunded: { icon: "account_balance_wallet", tone: "money" },
  // **الاسترداد الأسبوعي** (§٦٣-ج/٨) — تذكيراتُه الثلاثة (صباحاً · مساءً · قبل أن يفوت اليوم) بنار الرئيسية نفسِها، ولمستُها تفتحها
  cashback_reminder: { icon: "local_fire_department", tone: "offer" },
  // **المدفوعاتُ غيرُ المؤكَّدة** (`design/PAYMENTS-UNCONFIRMED.md` §٣، SPEC §٦٤-ز) — التذكيرُ بنبرة التنبيه (مالٌ لم يُحسم لا خطأ)،
  // والنزاعُ بنبرة الخطأ كـ«انقضت مهلة كليك». **ولمستُهما تفتح «رحلةٌ لم يكتمل دفعها»** (`destinationOf`)
  payment_reminder: { icon: "payments", tone: "warn" },
  payment_disputed: { icon: "gavel", tone: "danger" },
  women_mode_revoked: { icon: "woman", tone: "women" },
  campaign: { icon: "campaign", tone: "plain" },
  promo: { icon: "sell", tone: "offer" },
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

/** الوقتُ كما في اللوحة: ساعةٌ بأربعٍ وعشرين لليوم وأمس، واسمُ اليوم للأسبوع، والتاريخُ لما قبله.
 *  **وبخاناتٍ لاتينية** (`DISPLAY_LOCALE`) كقاعدة المشروع كلِّه. */
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
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const grouped = new Map<Group, UserNotification[]>();
  for (const row of rows ?? []) {
    const group = groupOf(row.created_at, startOfToday);
    grouped.set(group, [...(grouped.get(group) ?? []), row]);
  }

  return (
    <div className="t2 t2-notifs">
      <div className="t2-head">
        <button
          type="button"
          className="t2-back"
          aria-label="رجوع"
          onClick={() => navigate("/account")}
        >
          <span className="t2-icon" aria-hidden="true">arrow_forward</span>
        </button>
        <h1 className="t2-title">الإشعارات</h1>
        {unread ? (
          <button type="button" className="t2-action" onClick={() => void markAll()}>
            قراءة الكل
          </button>
        ) : null}
      </div>

      <ErrorNote message={error} />
      {rows === null && !error ? <Spinner /> : null}
      {rows?.length === 0 ? (
        <EmptyState
          title="لا إشعارات بعد"
          hint="ستجد هنا أخبار رحلاتك وشحن رصيدك."
        />
      ) : null}

      {GROUP_ORDER.filter((group) => grouped.has(group)).map((group) => (
        <section key={group}>
          <div className="t2-group">{GROUP_LABEL[group]}</div>
          <div className="t2-list">
            {(grouped.get(group) ?? []).map((entry) => {
              const style = KIND_STYLE[entry.kind] ?? DEFAULT_STYLE;
              const to = destinationOf(entry);
              return (
                <button
                  key={entry.id}
                  type="button"
                  className="t2-row"
                  disabled={to === null}
                  onClick={() => to && navigate(to)}
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
                    <span className="t2-row-body">
                      {composeBody(entry) ?? entry.body}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </section>
      ))}
    </div>
  );
}
