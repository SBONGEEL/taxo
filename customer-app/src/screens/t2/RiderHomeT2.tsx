/** الرئيسية — TAXO 2.0 «R05» (Claude Design «Rider»)، **في المظهر النهاريّ المرسوم وحدَه**.
 *
 * **وجهٌ لا منطق**: الشاشةُ (`screens/Home.tsx`) تمرّر الشيءَ نفسَه للوجهين (`RiderHomeProps`) — الخريطةُ عقدةٌ
 * واحدة، والنداءاتُ هي هي (المحفظةُ والمتجرُ والإحالةُ وآخرُ الرحلات)، **وكلُّ زرٍّ يذهب حيث يذهب في القائم**.
 * والبلاطاتُ واللافتاتُ من اللوحة بسلوكها (`StorefrontT2`)، **والتوسيعُ وزرُّ الجهاز الخلفيُّ من `useExpandable`**.
 *
 * **وما رسمته اللوحةُ ولم يُبنَ — بعلّته** (`TAXO2-DESIGN-CORRECTIONS.md` §٢٢):
 * - **«اقتصادي يصل خلال 3 د»** وشارةُ «3 د» على «رحلة»: **المهلةُ لا تُحسب قبل أن تُعرف نقطةُ الالتقاط** — وهي علّةُ
 *   الرئيسية القائمة نفسُها. فالبطاقةُ «إلى أين؟» وحدَها.
 * - **«طرد»**: التوصيلُ مسارٌ آخرُ لم يُبنَ (SPEC-DELIVERY)، **وبلاطتُه في اللوحة «قريباً»** فتظهر بين البلاطات بحالها.
 *   **فـ«رحلة» تملأ العمودَ وحدَها.**
 * - **«نسائية» بلاطةً**: لا بلاطةَ بها في المتجر — والخدمةُ النسائيةُ كما هي اليوم (§61).
 * - **السهمُ في شارة الموقع** (تغييرُ نقطة الانطلاق من الرئيسية): لا بابَ له هنا اليوم — تُغيَّر في ورقة الطلب.
 *
 * **وما في الرئيسية القائمة ولم يُرسم يبقى بلغة اللوحة**: الأماكنُ المحفوظة · سطرُ تأكيد الرقم · الإحالةُ · آخرُ
 * رحلاتك (وتوسيعُ الخريطة). **ونُزل اثنان**: رصيدُ المحفظة في الرأس (لا مكانَ له في الرأس المرسوم، وتبويبُ المحفظة
 * يحمله) والتحيّةُ («صباح الخير») — والشارةُ تقول أين هو.
 */

import { PhonePendingNotice } from "@/components/PhonePendingNotice";
import { PromoBanners } from "@/components/home/PromoBanners";
import type { RiderHomeProps } from "@/components/home/RiderHome";
import { useExpandable } from "@/components/home/MapCard";
import { formatMoney } from "@/lib/utils";
import { Wordmark } from "@/taxo2";

import { PROMO_SKIN_T2, ServiceTilesT2 } from "./StorefrontT2";
import "@/taxo2";
import "./t2.css";

/** أيقونةُ المكان المحفوظ **من عموده `icon`** — كالرئيسية القائمة (`PLACE_MARK`) بالأسماء الثلاثة نفسِها. */
const PLACE_ICON: Record<string, string> = { home: "home", work: "work", star: "star" };

/** «كم كبتناً حولك» بعربيةٍ تُقرأ — **العددُ وحدَه بلا مهلة** (المهلةُ لا تُقاس قبل نقطة الالتقاط). */
function nearbyLabel(count: number): string {
  if (count === 1) return "كبتن حولك";
  if (count === 2) return "كبتنان حولك";
  if (count <= 10) return "كباتن حولك";
  return "كبتناً حولك";
}

/** **الخريطةُ بطاقةً** — والعقدةُ هي هي في الحالين: يتبدّل صنفُ الحاوية لا موضعُها (كـ`MapCard`). */
function MapCardT2({
  map,
  nearby,
  onAskDestination,
}: {
  map: RiderHomeProps["map"];
  nearby: number;
  onAskDestination: () => void;
}) {
  const [open, setOpen] = useExpandable();
  return (
    <div className={open ? "t2-home-map open" : "t2-home-map"}>
      {map}
      {!open && nearby > 0 ? (
        <span className="t2-home-near">
          {nearby > 2 ? <span className="t2-num">{nearby}</span> : null}
          {nearbyLabel(nearby)}
        </span>
      ) : null}
      {/* **التوسيعُ شارةٌ ظاهرةٌ لا نقرٌ صامت** (قرارُ المالك ٢٠٢٦-٠٨-٣٠) — بلغة الهوية */}
      {!open ? (
        <button type="button" className="t2-home-expand" onClick={() => setOpen(true)}>
          <span className="t2-icon" aria-hidden="true">open_in_full</span>
          توسيع
        </button>
      ) : (
        <>
          <button type="button" className="t2-home-close" onClick={() => setOpen(false)} aria-label="إغلاق الخريطة">
            <span className="t2-icon" aria-hidden="true">close</span>
          </button>
          {/* **وزرُّ العمل في متناوله وهي موسَّعة** — فلا يُغلقها ليطلب */}
          <div className="t2-home-map-action">
            <button type="button" className="t2-button action" onClick={onAskDestination}>
              إلى أين؟ اطلب رحلة
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export function RiderHomeT2({
  name,
  place,
  unread,
  currency,
  nearby,
  onOpenNotifications,
  onOpenAccount,
  onAskDestination,
  places,
  onPickPlace,
  tiles,
  banners,
  referrals,
  onOpenReferrals,
  recent,
  onOpenRides,
  onRepeat,
  map,
}: RiderHomeProps) {
  // **أوّلُ برنامجٍ مشتعل** — بالشرط نفسِه في الرئيسية القائمة: بجائزةٍ مقروءةٍ أو لا صفّ
  const program =
    referrals?.programs.find((row) => row.enabled && row.reward_amount !== "0") ?? null;

  return (
    <div className="t2 t2-page t2-home pb-nav">
      <div className="t2-home-head">
        <span className="t2-home-brand">
          <Wordmark size={15} />
        </span>
        {/* **ولا مدينةَ تُخمَّن**: عنوانُ موقعه حين يُعرف، وإلا فلا شارة */}
        {place ? (
          <span className="t2-home-place">
            <span className="t2-icon fill" aria-hidden="true">location_on</span>
            <span className="t2-home-place-text">{place}</span>
          </span>
        ) : null}
        <span className="t2-home-spacer" />
        <button type="button" className="t2-home-bell" onClick={onOpenNotifications} aria-label="الإشعارات">
          <span className="t2-icon" aria-hidden="true">notifications</span>
          {/* **نقطةٌ لا رقم** — السؤالُ هنا «هل ثمّ جديد؟» */}
          {unread ? <span className="t2-home-dot" /> : null}
        </button>
        <button type="button" className="t2-avatar sm" onClick={onOpenAccount} aria-label="حسابي">
          {name.slice(0, 1)}
        </button>
      </div>

      <button type="button" className="t2-home-hero" onClick={onAskDestination}>
        <span className="t2-home-hero-stripe" aria-hidden="true" />
        <span className="t2-home-hero-title">إلى أين؟</span>
        <span className="t2-home-hero-go" aria-hidden="true">
          <span className="t2-icon">arrow_back</span>
        </span>
      </button>

      <div className="t2-home-grid">
        <MapCardT2 map={map} nearby={nearby} onAskDestination={onAskDestination} />
        <button type="button" className="t2-home-ride" onClick={onAskDestination}>
          <span className="t2-icon" aria-hidden="true">local_taxi</span>
          <span className="t2-home-ride-label">رحلة</span>
        </button>
      </div>

      {/* ── أماكنُه المحفوظة — **ولا صفَّ بلا أماكن** (في القائمة، ولم تُرسم) */}
      {places.length > 0 ? (
        <div className="t2-home-places">
          {places.slice(0, 3).map((saved) => (
            <button key={saved.id} type="button" className="t2-home-chip" onClick={() => onPickPlace(saved)}>
              <span className="t2-icon" aria-hidden="true">{PLACE_ICON[saved.icon] ?? "star"}</span>
              <span>{saved.label}</span>
            </button>
          ))}
        </div>
      ) : null}

      {/* **فوق البلاطات لا تحتها** — الحسابُ المحدود يُمنع من أوّل ما تفتحه */}
      <PhonePendingNotice variant="t2" />
      <ServiceTilesT2 tiles={tiles} />
      <PromoBanners banners={banners} skin={PROMO_SKIN_T2} />

      {program ? (
        <button type="button" className="t2-home-row" onClick={onOpenReferrals}>
          <span className="t2-icon" aria-hidden="true">redeem</span>
          <span className="t2-home-row-label">
            ادعُ صديقاً واربح {formatMoney(program.reward_amount, currency)}
          </span>
          <span className="t2-home-row-trail">مشاركة</span>
        </button>
      ) : null}

      {recent.length > 0 ? (
        <>
          <div className="t2-section">
            آخر رحلاتك
            <button type="button" className="t2-section-aside t2-home-all" onClick={onOpenRides}>
              الكل
            </button>
          </div>
          <div className="t2-home-recent">
            {recent.map((ride) => (
              <button key={ride.id} type="button" className="t2-home-trip" onClick={() => onRepeat(ride)}>
                {/* **الأجرةُ النهائيةُ إن كانت** — ولا يُعرض تقديرٌ في موضع محصَّل */}
                <span className="t2-home-trip-fare">{formatMoney(ride.final_fare, ride.currency)}</span>
                <span className="t2-home-trip-route">
                  {ride.pickup_address ?? "نقطة الانطلاق"} ← {ride.dropoff_address ?? "الوجهة"}
                </span>
                <span className="t2-home-trip-go">أعِد الرحلة</span>
              </button>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}
