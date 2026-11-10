/** **ملخّصُ الأسبوع الماضي** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٧) — تحت «أرباحي»، وإليه يفتح إشعارُ السبت.
 *
 * **سبعةُ أيامٍ كاملةٌ تنتهي بأمس، ومقارنتُها بالسبعة قبلها** — والأرقامُ كلُّها من `GET /drivers/me/earnings/weekly` كما تصل
 * (§14: لا قسمةَ ولا طرحَ هنا — النسبةُ محسوبةٌ في الخلفية). **وما لم يُقَس لا يُرسم**: ساعاتُ الاتصال حيث مفتاحُها مطفأ، والتقييمُ
 * بلا تقييمات، وأفضلُ يومٍ في أسبوعٍ بلا صافٍ موجب.
 */

import { useEffect, useState } from "react";

import { getWeeklyDigest } from "@/api/endpoints";
import type { WeeklyDigest } from "@/api/types";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { tr } from "@/lib/i18n";
import { DISPLAY_LOCALE, digits } from "@/lib/utils";

import { countRides, hoursClock } from "./count";

function weekday(value: string): string {
  return new Intl.DateTimeFormat(DISPLAY_LOCALE, { weekday: "long", timeZone: "UTC" }).format(new Date(`${value}T12:00:00Z`));
}

function hourLabel(hour: number): string {
  return digits(`${String(hour).padStart(2, "0")}:00`);
}

export function WeeklyDigestT2() {
  const [data, setData] = useState<WeeklyDigest | null>(null);

  useEffect(() => {
    getWeeklyDigest()
      .then(setData)
      .catch(() => undefined);
  }, []);

  if (data === null) return null;
  const change = data.earned_change_percent;

  return (
    <section className="t2-wal-break" id="weekly-digest" aria-labelledby="weekly-digest-title">
      <h2 id="weekly-digest-title" className="t2-wal-line" style={{ fontWeight: 700 }}>
        <span>{tr("ملخّص الأسبوع الماضي")}</span>
        <span>{countRides(data.completed_rides)}</span>
      </h2>
      <div className="t2-wal-line">
        <span>{tr("ما كسبته فعلاً")}</span>
        <span>
          <span dir="ltr">{digits(data.earned)}</span> {CURRENCY_LABEL[data.currency]}
        </span>
      </div>
      {change !== null ? (
        <div className={change >= 0 ? "t2-wal-line ok" : "t2-wal-line"}>
          <span>{tr("مقارنةً بالأسبوع السابق")}</span>
          <span dir="ltr">{digits(`${change > 0 ? "+" : ""}${change}%`)}</span>
        </div>
      ) : null}
      <div className="t2-wal-line">
        <span>{tr("رحلات الأسبوع السابق")}</span>
        <span>{countRides(data.previous_rides)}</span>
      </div>
      {data.online_minutes !== null ? (
        <div className="t2-wal-line">
          <span>{tr("ساعات الاتصال")}</span>
          <span dir="ltr">{hoursClock(data.online_minutes)}</span>
        </div>
      ) : null}
      {data.best_day ? (
        <div className="t2-wal-line">
          <span>{tr("أفضل يوم")}</span>
          <span>{weekday(data.best_day)}</span>
        </div>
      ) : null}
      {data.best_hours.length > 0 ? (
        <div className="t2-wal-line">
          <span>{tr("أكثر ساعاتك رحلات")}</span>
          <span dir="ltr">{data.best_hours.map((item) => hourLabel(item.hour)).join(" · ")}</span>
        </div>
      ) : null}
      {data.rating_average !== null ? (
        <div className="t2-wal-line">
          <span>{tr("تقييمك هذا الأسبوع")}</span>
          <span dir="ltr">
            {digits(data.rating_average.toFixed(2))} ★ ({digits(String(data.rating_count))})
          </span>
        </div>
      ) : null}
      <p className="t2-wal-hint">
        {tr("الأسبوع سبعة أيام كاملة تنتهي بأمس. «ما كسبته فعلاً» كلُّ ما حصّلته ناقصاً العمولة والاقتطاعات.")}
      </p>
    </section>
  );
}
