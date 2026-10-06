/** الخدمةُ النسائيةُ في الرحلة — TAXO 2.0 «RW2» (ورقةُ الطلب) و«RW3» (لا كبتنة قريبة) و«RW4» (تتبّعُ الكبتنة)، **في المظهرين
 *  والنسائيّ** (§٦٢-ج/٢٣).
 *
 * **وجوهٌ لا منطق**: الطلبُ ورقةُ R06 نفسُها (`ConfirmRideT2` · `useConfirmRide`) بتفضيل «كبتنة» — شارتُها ومسافتُها فوق المسار، وفئتُها
 * بحافّة البرقوق، وزرُّها «اطلبي كبتنة»؛ **والتتبّعُ ورقةُ R08 نفسُها** (`TrackingT2` · `useTrackingSheet`) بحبّة الكبتنة ودائرتها
 * وعلامتها. **فما يُرسل ويُحسب ويُلغى هو هو** — لا يفترق الوجهان في طلبٍ ولا في سعرٍ ولا في إلغاء.
 *
 * **وRW3 بقول المالك حرفاً**: «كبتنةٌ فقط، والراكبةُ نفسُها تختار «أي كبتن»… ولا يبدّلها التطبيقُ بنفسه» — **فلا خيارَ مختارٌ سلفاً**،
 * و«متابعة» لا تعمل حتى تختار. **و«اطلبي رحلة عادية»** طلبٌ جديدٌ بالنقطتين نفسيهما بتفضيل «أي كبتن» (`acceptAnyDriver` القائم في
 * الرئيسية). **و«جدولي الرحلة لوقت لاحق»** ورقةُ الطلب نفسُها بمنتقي الموعد مفتوحاً — بنقطتيها وفئتها **وتفضيلها «كبتنة»** — والحجزُ
 * بابُه القائم (`createBooking`): **يحمل التفضيلَ ويُفحص عند الحجز وعند التنفيذ** (`services/bookings.py`)، **ويظهر حيث الحجوزُ مشتعلةٌ
 * وحدَها** (`scheduled_rides_enabled`، `lib/bookings.ts`).
 *
 * **وما رسمته اللوحةُ ولم يُبنَ — بعلّته**:
 * - **RW2 · «تصل خلال 7 د»**: زمنُ الوصول بندٌ يُبنى بعد هذا (§٦٢-ج/١٠) — ولا رقمَ بلا مصدر. **و«نسائية» فئةً بأيقونتها**: الخدمةُ
 *   تفضيلٌ لا فئة (R06) — فالفئاتُ كما هي بحافّة البرقوق، و«كبتنة موثّقة» سطرُها.
 * - **RW2 · «مشاركة الرحلة مع أمي — تلقائياً في كل رحلة نسائية»**: رابطُ التتبّع الحيّ ينتظر إذنَ المالك (§٦٢-ج/١٩، بيانات).
 * - **RW3 · «انتظري، نوسّع البحث»**: «أنتظر كبتنة» بندٌ مطفأٌ لم يُبنَ (§٦٢-ج/٢٨)، **والبحثُ المنتهي لا يُستأنف** (`no_driver_found`
 *   نهائيّ). **و«متابعة البحث»** ⇐ «متابعة»: لا بحثَ يُتابَع.
 * - **RW3 · «بحثنا في محيط 5 كم»**: المدى ثابتٌ في الخلفية (`geo.GENDERED_MAX_SEARCH_RADIUS_KM`) **ولا يُنشر** — ورقمٌ يُكتب هنا نسخةٌ
 *   ثانيةٌ تفترق، والمرسومُ «5» يخالفه أصلاً.
 * - **RW3 · «نحجز لك كبتنة مسبقاً للوقت الذي تختارينه»**: الحجزُ لا يحجز كبتنة — **يبدأ البحثَ قبل الموعد بعشر دقائق** (R06)، فهذا ما يُقال.
 * - **RW3 · «سيكون السائق كبتناً رجلاً»** ⇐ «**قد يكون**»: «أي كبتن» تقبل كبتنةً أيضاً — والتحذيرُ يصدق بلا أن يَعِد بما لا يُعرف.
 * - **RW4 · «5 د»** (زمنُ الوصول، §٦٢-ج/١٠) · **«رمز الرحلة»** (§٦٢-ج/٥، مطفأٌ لم يُبنَ) · **«رحلتك مشاركة مع أمي مباشرة · إيقاف»**
 *   (§٦٢-ج/١٩) · **«اتصال»**: رقمُ الكبتنة لا يصل الراكبةَ (`RideDriverOut` بلا هاتف)، والاتصالُ المقنَّعُ بندٌ ينتظر إذنَ المالك
 *   (§٦٢-ج/٣) · **«رسالة»** (محادثةُ الرحلة، §٦٢-ج/١) · **«طوارئ»** (§٦٢-ج/٤).
 *
 * **وما في الورقتين القائمتين ولم يُرسم يبقى**: منتقي التفضيل بخياراته الثلاثة (هي تغيّره بنفسها)، والدفعُ والكوبونُ والمشاركةُ والحجزُ
 * والمحطات في RW2؛ وشارةُ «رحلة نسائية» وإرسالُ التفاصيل ورسمةُ المركبة والوقفةُ والإلغاءُ بأسبابه في RW4.
 */

import { useState } from "react";

import type { Ride } from "@/api/types";
import { DriverAvatar } from "@/components/ride/DriverAvatar";
import { useScheduledRides } from "@/lib/bookings";
import { distanceKm, type LatLng } from "@/lib/route-line";
import { formatDistance, ratedAverage } from "@/lib/utils";
import { useWomenService } from "@/lib/women";
import { Icon } from "@/taxo2";

import { NoteT2 } from "./KitT2";
import { SheetT2 } from "./SheetT2";
import "@/taxo2";
import "./t2.css";
import "./request.css";
import "./women.css";

/** **رحلةُ الخدمة النسائية** = ما طُلبت فيه كبتنة — **تفضيلُ الطلب لا جنسُ أحد**. («ذكور» ليست الخدمة النسائية.) */
export function isWomenRide(ride: Pick<Ride, "gender_preference">): boolean {
  return ride.gender_preference === "female";
}

// ── RW2 ─────────────────────────────────────────────────────────────────────────────────────────────

/** **رأسُ الطلب النسائيّ** (RW2): شارةُ «رحلة نسائية»، والمسافةُ والزمنُ كما قدّرتهما الخلفية — مكانُهما في R06 رأسُ الفئات. */
export function WomenRequestHeadT2({ meta }: { meta: string | null }) {
  return (
    <div className="t2-wreq-head">
      <span className="t2-wchip">
        <Icon name="woman" fill />
        رحلة نسائية
      </span>
      {meta ? <span className="t2-pick-meta">{meta}</span> : null}
    </div>
  );
}

// ── RW3 ─────────────────────────────────────────────────────────────────────────────────────────────

/** **خيارا الشاشة لا قيمُ عقد** — «اطلبي رحلة عادية» يرسل `gender_preference: "any"` من الرئيسية، لا هذا الاسم. */
type Choice = "later" | "anyCaptain";

/** **لا كبتنة قريبة** (RW3) — مكانَ خاتمة R29 لطلب «كبتنة» انتهى بلا كبتنة: **خياراتٌ تختارها هي، ولا شيءَ يقع قبل «متابعة»**. */
export function WomenNoCaptainT2({
  onDismiss,
  onAcceptAnyDriver,
  onScheduleAgain,
  error,
}: {
  onDismiss: () => void;
  /** «اطلبي رحلة عادية» — طلبٌ جديدٌ بـ«أي كبتن» (الرئيسية). */
  onAcceptAnyDriver: () => Promise<void>;
  /** «جدولي الرحلة لوقت لاحق» — ورقةُ الطلب بمنتقي الموعد (الرئيسية). **وبلا هذا الفعل لا يُعرض الخيار.** */
  onScheduleAgain?: () => void;
  /** خطأُ «اطلبي رحلة عادية» — من الرئيسية التي ترسل الطلب. */
  error: string | null;
}) {
  const scheduled = useScheduledRides();
  const women = useWomenService();
  const [choice, setChoice] = useState<Choice | null>(null);
  const [busy, setBusy] = useState(false);
  // **الحجزُ بتفضيل «كبتنة» يُرفض حيث الخدمةُ مطفأة** (`bookings.create`) — فلا يُعرض خيارٌ يُردّ
  const canSchedule = scheduled && women.enabled && onScheduleAgain !== undefined;

  const options: { value: Choice; icon: string; title: string; sub: string; warn?: boolean }[] = [
    ...(canSchedule
      ? [
          {
            value: "later" as const,
            icon: "event_upcoming",
            title: "جدولي الرحلة لوقت لاحق",
            sub: "نبدأ البحث عن كبتنة قبل موعدك بعشر دقائق.",
          },
        ]
      : []),
    {
      value: "anyCaptain",
      icon: "local_taxi",
      title: "اطلبي رحلة عادية",
      sub: "قد يكون السائق كبتناً رجلاً — لن نرسله إلا إن اخترتِ هذا.",
      warn: true,
    },
  ];

  async function proceed() {
    if (choice === "later") {
      onScheduleAgain?.();
      return;
    }
    if (choice !== "anyCaptain") return;
    setBusy(true);
    try {
      await onAcceptAnyDriver();
    } finally {
      setBusy(false);
    }
  }

  return (
    <SheetT2
      footer={
        <div className="t2-out-actions">
          <button
            type="button"
            className="t2-wbtn"
            disabled={choice === null || busy}
            aria-busy={busy}
            onClick={() => void proceed()}
          >
            {busy ? "نرسل طلبك…" : "متابعة"}
          </button>
          {error ? <NoteT2 tone="danger">{error}</NoteT2> : null}
          {/* **يطوي الخاتمة** — الطلبُ انتهى في الخلفية أصلاً، فلا شيءَ يُلغى هناك ولا رسمَ عليه */}
          <button type="button" className="t2-out-later t2-wcancel" onClick={onDismiss}>
            إلغاء الطلب
          </button>
        </div>
      }
    >
      <div className="t2-out-head">
        <span className="t2-out-icon women">
          <Icon name="hourglass_top" />
        </span>
        <div>
          <h3 className="t2-out-title">لا توجد كبتنة قريبة الآن</h3>
          <p className="t2-wno-sub">بحثنا حولك ولم نجد كبتنةً متاحة. اختاري ما يناسبك:</p>
        </div>
      </div>
      <div className="t2-wopts" role="radiogroup" aria-label="اختاري ما يناسبك">
        {options.map((option) => {
          const on = choice === option.value;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={on}
              className={on ? "t2-wopt on" : "t2-wopt"}
              onClick={() => setChoice(option.value)}
            >
              <Icon name={option.icon} className="t2-wopt-icon" />
              <span className="t2-wopt-main">
                <span className="t2-wopt-title">{option.title}</span>
                <span className={option.warn ? "t2-wopt-sub warn" : "t2-wopt-sub"}>{option.sub}</span>
              </span>
              <Icon name={on ? "radio_button_checked" : "radio_button_unchecked"} className="t2-wopt-radio" />
            </button>
          );
        })}
      </div>
    </SheetT2>
  );
}

// ── RW4 ─────────────────────────────────────────────────────────────────────────────────────────────

/** **«الكبتنة على بعد…» بالبرقوق** (RW4) — من موقعها المبثوث إلى نقطة الالتقاء خطّاً مستقيماً، كحبّة R08 بعينها. */
export function WomenApproachChipT2({
  ride,
  driverPing,
  minutes = null,
}: {
  ride: Ride;
  driverPing: LatLng | null;
  /** دقائقُها الباقية من مسار الاقتراب (§٦٢-ج/١٠) — و`null` حيث المفتاحُ مطفأ. */
  minutes?: number | null;
}) {
  if (ride.status === "arrived") {
    return (
      <div className="t2 t2-trk-chip women">
        <Icon name="woman" fill />
        وصلت الكبتنة
      </div>
    );
  }
  if (ride.status !== "accepted" || !driverPing) return null;
  return (
    <div className="t2 t2-trk-chip women">
      <Icon name="woman" fill />
      الكبتنة على بعد {formatDistance(distanceKm(driverPing, ride.pickup))}
      {minutes !== null ? ` · ${minutes} د` : ""}
    </div>
  );
}

/** عنوانُ ورقة RW4 — مؤنّثاً كما رُسم. */
export function womenApproachTitle(arrived: boolean): string {
  return arrived ? "الكبتنة تنتظرك في نقطة الانطلاق" : "الكبتنة في الطريق إليك";
}

/** **بطاقةُ الكبتنة** (RW4) مكانَ بطاقة R08: دائرتُها بحافّة البرقوق، وعلامةُ التوثيق بجانب اسمها، و«كبتنة موثّقة» تحته — **وهي كذلك
 *  يقيناً**: طلبُ «كبتنة» لا يُسنَد إلا لكبتنةٍ ثبّت المشرفُ جنسَها من هويتها (`dispatch._eligible_levels`: `gender_verified_at`). */
export function WomenCaptainCardT2({ ride }: { ride: Ride }) {
  const driver = ride.driver;
  if (!driver) return null;
  const vehicle = driver.vehicle;
  return (
    <div className="t2-trk-driver">
      <DriverAvatar rideId={ride.id} name={driver.name} className="t2-trk-avatar women" />
      <div className="t2-trk-dmain">
        <div className="t2-trk-dname lg t2-wname">
          {driver.name}
          <Icon name="verified" fill />
        </div>
        <div className="t2-trk-rating">
          {/* **ولا «★ 0.00» لكبتنةٍ لم تُقيَّم بعد** (§٦٢-ب/٤٩) — «كبتنة موثّقة» وحدَها */}
          {ratedAverage(driver.rating_avg) ? (
            <>
              <Icon name="star" fill />
              <span className="t2-trk-rating-value">{Number(driver.rating_avg).toFixed(2)}</span>
              <span aria-hidden="true">·</span>
            </>
          ) : null}
          كبتنة موثّقة
        </div>
      </div>
      {vehicle ? (
        <div dir="ltr" className="t2-trk-plate">
          <span className="t2-trk-plate-cc">{ride.country_code}</span>
          <span className="t2-trk-plate-no">{vehicle.plate_number}</span>
        </div>
      ) : null}
    </div>
  );
}
