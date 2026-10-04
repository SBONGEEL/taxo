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
 * **والمرشّحاتُ الأربعة بُنيت بقرار المالك** (§٦١-ط/١): «مكتملة» و«ملغاة» **تصفّيان في الخلفية** (`?group=`) — تصفيةُ
 * صفحةٍ محمَّلةٍ كانت ستكذب على ما لم يُحمَّل — و«مجدولة» **بابُ الحجوز القائم** (`GET /me/bookings`، القائمةُ منها)، و«الكل»
 * **كما كان حرفاً** وفوقه بطاقةُ ما جُدول كما رُسم. **وزرُّ «تعديل» لم يُبنَ**: تعديلُ الحجز ينتظر إقرارَ المالك (`APPROVALS-MONEY.md`
 * §١) — فالبطاقةُ تفتح «رحلات مجدولة» حيث يُلغى. **والأجرةُ عليها «تقديرياً»**: تُحسب عند التنفيذ (القسم 5.11).
 */

import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { listBookings, listMyRides } from "@/api/endpoints";
import type { Booking, RideGroup, RideListItem, RideStatus } from "@/api/types";
import { EmptyState, ErrorNote, Spinner } from "@/components/ui/Feedback";
import { PAYMENT_METHOD_LABEL, RIDE_STATUS_LABEL, VEHICLE_LABEL } from "@/lib/labels";
import { formatDistance, formatMoney } from "@/lib/utils";

import { aheadParts, byMonth, startOfToday, whenParts } from "./when";

import "@/taxo2";
import "./t2.css";

const PAGE = 20;

type Filter = "all" | RideGroup | "scheduled";

/** المرشّحاتُ كما رُسمت، بترتيبها. */
const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "الكل" },
  { key: "completed", label: "مكتملة" },
  { key: "scheduled", label: "مجدولة" },
  { key: "cancelled", label: "ملغاة" },
];

const EMPTY: Record<Filter, { title: string; hint?: string }> = {
  all: { title: "لا رحلات بعد", hint: "أول رحلة تبدأ من الشاشة الرئيسية." },
  completed: { title: "لا رحلات مكتملة بعد" },
  scheduled: { title: "لا رحلات مجدولة" },
  cancelled: { title: "لا رحلات ملغاة" },
};

/** **ما ينتظر موعدَه وحدَه** — ما نُفِّذ صار رحلةً في القائمة، وما فات أو أُلغي في «رحلات مجدولة». */
const upcoming = (bookings: Booking[]) => bookings.filter((booking) => booking.status === "pending");

/** الحالاتُ التي ترسمها اللوحةُ «ملغاة» — **ونصُّ كلٍّ منها يبقى نصَّه** (من ألغى). */
const ENDED_UNSERVED: RideStatus[] = ["cancelled_by_rider", "cancelled_by_driver", "no_driver_found"];

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
  const [filter, setFilter] = useState<Filter>("all");
  const [rides, setRides] = useState<RideListItem[]>([]);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [more, setMore] = useState(false);
  // **جوابٌ متأخّرٌ لمرشّحٍ سابقٍ لا يكتب فوق الحاليّ** — من بدّل المرشّحَ مرّتين بسرعةٍ يرى ما اختاره آخراً
  const latest = useRef(0);

  async function load(offset: number, which: Filter) {
    const ticket = ++latest.current;
    try {
      if (which === "scheduled") {
        const all = await listBookings();
        if (ticket !== latest.current) return;
        setBookings(upcoming(all));
        setRides([]);
        setMore(false);
        return;
      }
      const [page, booked] = await Promise.all([
        listMyRides(PAGE, offset, which === "all" ? undefined : which),
        // **وفي «الكل» بطاقةُ ما جُدول فوق السجلّ** كما رُسمت — **وتعثّرُها لا يُسقط السجلّ**: هي إضافةٌ على الشاشة القائمة
        which === "all" && offset === 0 ? listBookings().catch(() => null) : Promise.resolve(null),
      ]);
      if (ticket !== latest.current) return;
      setRides((current) => (offset === 0 ? page : [...current, ...page]));
      if (offset === 0) setBookings(booked ? upcoming(booked) : []);
      setMore(page.length === PAGE);
    } catch (caught) {
      if (ticket !== latest.current) return;
      setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة رحلاتك");
    } finally {
      if (ticket === latest.current) setLoading(false);
    }
  }

  useEffect(() => {
    void load(0, filter);
    // التحميلُ لكلِّ مرشّح — والصفحاتُ التالية من «عرض المزيد»
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filter]);

  function choose(next: Filter) {
    if (next === filter) return;
    setLoading(true);
    setError(null);
    setRides([]);
    setBookings([]);
    setFilter(next);
  }

  const today = startOfToday();
  const months = byMonth(rides, (item) => item.ride.created_at);

  return (
    <div className="t2 t2-page pb-nav">
      <h1 className="t2-h1">رحلاتي</h1>

      <div className="t2-filters" role="tablist" aria-label="تصفية الرحلات">
        {FILTERS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={filter === key}
            className={filter === key ? "t2-filter on" : "t2-filter"}
            onClick={() => choose(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <Spinner />
      ) : (
        <>
          <ErrorNote message={error} />

          {rides.length === 0 && bookings.length === 0 && !error ? (
            <EmptyState title={EMPTY[filter].title} hint={EMPTY[filter].hint} />
          ) : null}

          {bookings.map((booking) => {
            const at = aheadParts(booking.scheduled_at, today);
            const fare = booking.estimated_fare_at_booking;
            return (
              <Link key={booking.id} to="/account/bookings" className="t2-booking">
                <span className="t2-booking-when">
                  <span className="t2-icon" aria-hidden="true">event_upcoming</span>
                  مجدولة · {at.day} <span dir="ltr">{at.time}</span> {at.half}
                </span>
                <span className="t2-route">
                  <span className="t2-dot" />
                  <span className="t2-place">{booking.pickup_address ?? "نقطة على الخريطة"}</span>
                  <span className="t2-dot to" />
                  <span className="t2-place strong">{booking.dropoff_address ?? "وجهة على الخريطة"}</span>
                </span>
                <span className="t2-booking-foot">
                  <span>{booking.gender_preference === "female" ? "نسائية" : VEHICLE_LABEL[booking.vehicle_category]}</span>
                  {fare !== null ? (
                    <span className="t2-booking-fare">
                      {formatMoney(fare, booking.currency)} <small>تقديرياً</small>
                    </span>
                  ) : null}
                </span>
              </Link>
            );
          })}

          {months.map((month) => (
            <section key={month.label}>
              <div className="t2-month">{month.label}</div>
              <div className="t2-cards">
                {month.items.map((item) => {
                  const { ride, has_open_dispute, payment_methods, settlement } = item;
                  const when = whenParts(ride.created_at, today);
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
            <button type="button" className="t2-more" onClick={() => void load(rides.length, filter)}>
              عرض المزيد
            </button>
          ) : null}
        </>
      )}
    </div>
  );
}
