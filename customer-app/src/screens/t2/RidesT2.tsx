/** رحلاتي — TAXO 2.0 «R12» (Claude Design «Rider»)، **في المظهر النهاريّ المرسوم وحدَه**.
 *
 * **الطلبُ هو هو** (`screens/Rides.tsx`): `GET /rides/me` بصفحاتٍ من عشرين و«عرض المزيد»،
 * والنقرُ إلى `/rides/:id`. **وما تغيّر طبقةُ العرض**: العنوانُ الكبير، والتجميعُ بالشهر، والبطاقةُ
 * بلغة اللوحة — الوقتُ والحالةُ فوق، والنقطتان، ثمّ الفئةُ والكبتنُ والأجرة.
 *
 * **وما في الصفّ اليومَ ولم ترسمه اللوحةُ يبقى** (القرار 37 · `TAXO2-DESIGN-CORRECTIONS.md` §١٣):
 * المسافةُ والقناة، وشارةُ النزاع، و«لم تُدفع»/«بانتظار التأكيد»، **ومن ألغى** — فـ«ملغاة» وحدَها
 * تجمع ثلاثَ حالاتٍ يفرّقها السجلُّ اليوم.
 *
 * **وما رسمته اللوحةُ بلا بابٍ في التطبيق لا يُبنى** حتى يقرّره المالك: المرشّحاتُ الأربعة (لا مرشّحَ
 * في `GET /rides/me`، وتصفيةُ صفحةٍ محمَّلةٍ تكذب على ما لم يُحمَّل)، وبطاقةُ المجدولة بـ«تعديل»
 * (الحجزُ يُلغى ولا يُعدَّل، ويعيش في «رحلات مجدولة» بطلبه).
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { listMyRides } from "@/api/endpoints";
import type { RideListItem, RideStatus } from "@/api/types";
import { EmptyState, ErrorNote, Spinner } from "@/components/ui/Feedback";
import { PAYMENT_METHOD_LABEL, RIDE_STATUS_LABEL, VEHICLE_LABEL } from "@/lib/labels";
import { DISPLAY_LOCALE, formatDistance, formatMoney } from "@/lib/utils";

import "./t2.css";

const PAGE = 20;
const DAY_MS = 24 * 60 * 60 * 1000;

/** الحالاتُ التي ترسمها اللوحةُ «ملغاة» — **ونصُّ كلٍّ منها يبقى نصَّه** (من ألغى). */
const ENDED_UNSERVED: RideStatus[] = ["cancelled_by_rider", "cancelled_by_driver", "no_driver_found"];

/** «اليوم · 10:12» · «أمس · 21:40» · «2 أكتوبر · 08:05» — كما في اللوحة، **بخاناتٍ لاتينية**. */
function whenParts(iso: string, startOfToday: number): { day: string; time: string } {
  const at = new Date(iso);
  const time = at.toLocaleTimeString(DISPLAY_LOCALE, {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  const ms = at.getTime();
  if (ms >= startOfToday) return { day: "اليوم", time };
  if (ms >= startOfToday - DAY_MS) return { day: "أمس", time };
  return { day: at.toLocaleDateString(DISPLAY_LOCALE, { day: "numeric", month: "long" }), time };
}

/** رأسُ الشهر: «أكتوبر 2026». */
function monthOf(iso: string): string {
  return new Date(iso).toLocaleDateString(DISPLAY_LOCALE, { month: "long", year: "numeric" });
}

/** نصُّ شارة الحالة ونبرتُها: «مكتملة» بالأخضر كما في اللوحة، **ونصُّ الإلغاء نصُّ السجلّ** بالأحمر —
 *  ومعه «بلا رسوم» حين لم يُقدَّر رسم (`cancellation_fee` صفرٌ أو غائب)، **ولا رقمَ حين قُدِّر**: الرسمُ
 *  قد يُعفى منه بعد التقدير، فالمبلغُ يُقرأ في التفاصيل لا هنا. */
function statusChip(item: RideListItem): { text: string; tone: "ok" | "danger" | "plain" } {
  const { ride } = item;
  if (ride.status === "completed") return { text: "مكتملة", tone: "ok" };
  if (ENDED_UNSERVED.includes(ride.status)) {
    const fee = ride.cancellation_fee;
    const free = fee === null || Number(fee) === 0;
    return { text: free ? `${RIDE_STATUS_LABEL[ride.status]} · بلا رسوم` : RIDE_STATUS_LABEL[ride.status], tone: "danger" };
  }
  return { text: RIDE_STATUS_LABEL[ride.status], tone: "plain" };
}

export function RidesT2Screen() {
  const [rides, setRides] = useState<RideListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [more, setMore] = useState(false);

  async function load(offset: number) {
    try {
      const page = await listMyRides(PAGE, offset);
      setRides((current) => (offset === 0 ? page : [...current, ...page]));
      setMore(page.length === PAGE);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة رحلاتك");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load(0);
  }, []);

  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  // **بالترتيب الذي يصل به** (الأحدثُ أوّلاً من الخلفية) — والشهرُ رأسُ كلِّ سلسلةٍ متّصلة
  const months: { label: string; items: RideListItem[] }[] = [];
  for (const item of rides) {
    const label = monthOf(item.ride.created_at);
    const last = months[months.length - 1];
    if (last && last.label === label) last.items.push(item);
    else months.push({ label, items: [item] });
  }

  return (
    <div className="t2 t2-page pb-nav">
      <h1 className="t2-h1">رحلاتي</h1>

      {loading ? (
        <Spinner />
      ) : (
        <>
          <ErrorNote message={error} />

          {rides.length === 0 ? (
            <EmptyState title="لا رحلات بعد" hint="أول رحلة تبدأ من الشاشة الرئيسية." />
          ) : null}

          {months.map((month) => (
            <section key={month.label}>
              <div className="t2-month">{month.label}</div>
              <div className="t2-cards">
                {month.items.map((item) => {
                  const { ride, has_open_dispute, payment_methods, settlement } = item;
                  const when = whenParts(ride.created_at, startOfToday);
                  const chip = statusChip(item);
                  const unserved = ENDED_UNSERVED.includes(ride.status);
                  // «نسائية» مكانَ الفئة كما في اللوحة — **وصفٌ للطلب لا لصاحبته** (`TrackingSheet`)
                  const kind = ride.gender_preference === "female" ? "نسائية" : VEHICLE_LABEL[ride.vehicle_category];
                  const meta = [
                    kind,
                    ride.driver?.name,
                    formatDistance(ride.actual_distance_km ?? ride.distance_km),
                    payment_methods.length > 0
                      ? payment_methods.map((method) => PAYMENT_METHOD_LABEL[method]).join(" + ")
                      : null,
                  ].filter(Boolean);
                  return (
                    <Link key={ride.id} to={`/rides/${ride.id}`} className="t2-ride">
                      <span className="t2-ride-top">
                        <span className="t2-ride-when">
                          {when.day} · <span dir="ltr">{when.time}</span>
                        </span>
                        <span className="t2-chips">
                          {/* شارةُ النزاع وحالُ السداد — **من الصفّ القائم**، والحكمُ يصل محسوباً (`settlement`) */}
                          {has_open_dispute ? <span className="t2-chip danger">نزاع</span> : null}
                          {settlement === "due" || settlement === "awaiting" ? (
                            <span className="t2-chip warn">
                              {settlement === "awaiting" ? "بانتظار التأكيد" : "لم تُدفع"}
                            </span>
                          ) : null}
                          <span className={`t2-chip ${chip.tone}`}>{chip.text}</span>
                        </span>
                      </span>

                      <span className={unserved ? "t2-route off" : "t2-route"}>
                        <span className="t2-dot" />
                        <span className="t2-place">{ride.pickup_address ?? "نقطة على الخريطة"}</span>
                        <span className="t2-dot to" />
                        <span className="t2-place">{ride.dropoff_address ?? "وجهة على الخريطة"}</span>
                      </span>

                      <span className="t2-ride-foot">
                        <span className="t2-ride-meta">{meta.join(" · ")}</span>
                        {/* **ولا أجرةَ على رحلةٍ لم تُخدَم** كما في اللوحة — كان السجلُّ يعرض تقديرَها */}
                        {unserved ? null : (
                          <span className="t2-fare">
                            {formatMoney(ride.final_fare ?? ride.estimated_fare, ride.currency)}
                          </span>
                        )}
                      </span>
                    </Link>
                  );
                })}
              </div>
            </section>
          ))}

          {more ? (
            <button type="button" className="t2-more" onClick={() => void load(rides.length)}>
              عرض المزيد
            </button>
          ) : null}
        </>
      )}
    </div>
  );
}
