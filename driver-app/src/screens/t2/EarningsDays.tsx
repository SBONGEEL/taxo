/** **أيّامُ نافذة الأرباح** — رسمُ C09 (§٦٢-ج/٣٨): عمودٌ لكلِّ يومٍ بيوم الدولة، **واليومُ بالجمر وقيمتُه فوقه** كما رُسم.
 *
 * **ولا حسابَ مالٍ هنا** (§14): الأعمدةُ تُرسم بـ`peak_share` كما تصل من الخلفية (حصّةُ اليوم من أكبر أيّام النافذة بإشارته)،
 * والقيمةُ نصُّها كما وصل. **وأيّامُها تُجمع إلى الرقم الكبير فوقها** — `days` و`net` من استعلامٍ واحدٍ بقاعدةٍ واحدة.
 *
 * **وما لم يُرسم ويقع**:
 * - **يومٌ بلا قيد** بالإطار المتقطّع الذي رُسم لليوم الذي لم يأتِ — «لا شيء» شكلٌ واحدٌ في الحالين.
 * - **يومٌ سالبٌ يتدلّى تحت خطِّ الصفر** بلون الخطر: عمولةُ رحلاتٍ نقديةٍ بلا أرباحٍ تقابلها (القسم 9). وعمودٌ صاعدٌ له يكذب.
 * - **«الشهر» ثلاثون عموداً** بلا قيمةٍ فوق اليوم (لا تتّسع)، وتحت كلِّ سابعٍ من اليوم رقمُ يومه من الشهر.
 */

import type { EarningsDay } from "@/api/types";
import { digits } from "@/lib/utils";

/** `getDay()`: الأحدُ صفر — **والحرفُ كما رُسم** (س ح ن ث ر خ ج). */
const WEEKDAY_LETTER = ["ح", "ن", "ث", "ر", "خ", "ج", "س"];
const WEEKDAY_NAME = ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"];

/** أطولُ عمودٍ بالبكسل — عمودُ «ث» المرسوم (86). */
const BAR_MAX = 86;

/** تاريخُ يوم الدولة كما وصل (`YYYY-MM-DD`) — **بلا مِنطقةٍ تُزيحه** إلى أمسِ في جهازٍ غربَ غرينتش. */
function calendarDay(day: string): Date {
  const [year, month, date] = day.split("-").map(Number);
  return new Date(year, month - 1, date);
}

export function EarningsDays({
  days,
  currency,
}: {
  days: EarningsDay[];
  currency: string;
}) {
  const month = days.length > 7;
  // **مقياسٌ واحدٌ للصاعد والنازل**: حصّتان بإشارتيهما من أكبر يومٍ — فيتقاسمان ارتفاعَ الرسم بنسبتهما
  const up = Math.max(0, ...days.map((day) => day.peak_share));
  const down = Math.max(0, ...days.map((day) => -day.peak_share));
  const scale = BAR_MAX / (up + down || 1);
  const upZone = Math.max(6, up * scale);
  const last = days.length - 1;

  return (
    <div className="t2-days-card" style={{ ["--t2-days-up" as string]: `${upZone}px` }}>
      {/* **خطُّ الصفر حين يتدلّى يوم** — وبلا يومٍ سالبٍ لا خطَّ كما رُسم */}
      {down > 0 ? <span className="t2-days-zero" aria-hidden="true" /> : null}
      <ol className={month ? "t2-days month" : "t2-days"} aria-label="صافي كلِّ يوم">
        {days.map((day, index) => {
          const date = calendarDay(day.day);
          const today = index === last;
          const share = day.peak_share;
          const label = month
            ? (last - index) % 7 === 0
              ? String(date.getDate())
              : ""
            : WEEKDAY_LETTER[date.getDay()];
          return (
            <li
              key={day.day}
              className={today ? "t2-days-col today" : "t2-days-col"}
              aria-label={`${WEEKDAY_NAME[date.getDay()]} ${date.getDate()}/${date.getMonth() + 1}: ${digits(day.net)} ${currency}`}
            >
              <span className="t2-days-up" aria-hidden="true">
                {today && !month ? (
                  <span className="t2-days-val" dir="ltr">
                    {digits(day.net)}
                  </span>
                ) : null}
                {share > 0 ? (
                  <span className="t2-days-bar" style={{ height: Math.max(4, share * scale) }} />
                ) : share === 0 ? (
                  <span className="t2-days-empty" />
                ) : null}
              </span>
              {down > 0 ? (
                <span className="t2-days-down" aria-hidden="true" style={{ height: down * scale }}>
                  {share < 0 ? (
                    <span className="t2-days-bar neg" style={{ height: Math.max(4, -share * scale) }} />
                  ) : null}
                </span>
              ) : null}
              <span className="t2-days-label" aria-hidden="true">
                {label || " "}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
