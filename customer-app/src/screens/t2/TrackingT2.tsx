/** تتبّعُ الرحلة — TAXO 2.0 «R07 البحث · R08 الكبتن في الطريق · R09 أثناء الرحلة» (Claude Design «Rider»)،
 * **في المظهرين** — رُسم نهاريّاً، **والليليُّ برموز إسفلت الهوية نفسِها** (§٦٢/٣).
 *
 * **وجهٌ ثانٍ لورقة التتبّع لا ورقةٌ ثانية**: الإلغاءُ بأسبابه، وإرسالُ التفاصيل، ورسمةُ المركبة كلُّها من `useTrackingSheet`
 * — **فلا يفترق الوجهان في إلغاءٍ ولا في سببٍ ولا في رسم**. **وكان القائمُ في الليليّ** (`TrackingSheet`) — **ونُزع** (§٦٢/٣).
 *
 * **والقيمُ الحيّةُ من بياناتٍ أو لا شيء** (§٦١-د/د): المسافةُ إلى الكبتن من موقعه المبثوث ونقطة الالتقاء، و«كم متبقية» من
 * المسار المجمَّد على الرحلة وموضع الكبتن عليه — **حسابُ هندسةٍ للعرض لا يُسعَّر منه شيء** (`lib/route-line`).
 *
 * **وما رسمته اللوحةُ ولا مصدرَ له اليوم — لم يُرسم** (`TAXO2-DESIGN-CORRECTIONS.md` §٢٤): رمزُ الرحلة · مهلةُ الوصول ووقتُه ·
 * «أمان» و«طوارئ SOS» · «عادةً أقل من دقيقة». **و«رسالة» و«اتصال» صار لهما مصدر** (SPEC §٦٦، ٢٠٢٦-١٠-٠٨): `CommsButtonsT2` في
 * R08 · R09 من قبول الكبتن حتى انتهاء الرحلة، وطبقتُهما فوق الشاشات (`lib/comms.tsx`).
 *
 * **وبُني منها بندان** (§٦٢-ج/٢٧): **السياراتُ حولك أثناء البحث** وعدُّها في سطر R07 («6 كباتن حولك الآن» — ممّا تُرسمه الخريطةُ
 * نفسُها، `Home.tsx`)، **وعددُ رحلات الكبتن** في بطاقة R08 («4.92 · 2,140 رحلة» — `GET /rides/{id}/driver/stats`).
 *
 * **و«RW4» وجهُ R08 لمن طلبت كبتنة** (§٦٢-ج/٢٣، `WomenRideT2.tsx` — وما لم يُبنَ منها بعلّته هناك): الحبّةُ برقوقاً، والعنوانُ
 * مؤنّثاً، وبطاقةُ الكبتنة بدائرتها وعلامتها — **والإلغاءُ والإرسالُ والرسمةُ هي هي**.
 *
 * **وما في الورقة القائمة ولم يُرسم يبقى بلغة اللوحة**: شارةُ «رحلة نسائية» وانتظارُ الكبتنة واقتراحُ المشاركة لها (§61: كما هي
 * اليوم) · شارتا المشاركة · المحطاتُ وعدّادُ الانتظار والوقفةُ غيرُ المخطَّطة (مالٌ يُقال حين ينشأ) · رسمةُ مركبة المتجر · أسبابُ
 * الإلغاء بعد القبول.
 *
 * **ورحلةٌ لشخصٍ آخر** (§٦٣-ج/١، `ForOtherTrackT2`) — لا لوحةَ لها: اسمُ الراكب حين يُنشر، وسطرُ الدافع، و«شارك رابط التتبّع»
 * في الأطوار الثلاثة؛ **وقنواتُ الدفع المعروضةُ تضيق بالدافع** (`usePayerPreference`).
 *
 * **والطرد** (§٦٣-ج/٤، `ParcelTrackT2`) — لا لوحةَ له: شارةُ «طرد» بين أخواتها، و«إلى: المستلم» وعنوانُه حين يُنشران، وسطرُ
 * «يدفع المستلمُ نقداً» **ولا قناةَ تُعرض** حينها؛ **وبطاقةُ الطريق في R09 «طردك في الطريق» إلى مستلمه**. ومن الصفّ لا من المفتاح.
 *
 * **و«بالساعة»** (§٦٣-ج/٥، `HourlyTrackT2`) — لا لوحةَ لها: شارةُ «بالساعة»، و«بالساعة · 3 ساعات · حتى 45 كم»، **وقبل البدء من أين
 * يُدفع المحجوزُ بزرِّ تبديله**؛ **وفي R09 الساعةُ مكانَ «كم متبقية»** — الباقي من الساعات ثمّ «وقتٌ زائد» بنبرة التنبيه — **والوجهةُ
 * «بلا وجهة» حين لم تُختر**. وتأكيدُ الإلغاء يقول رسمَ ما بعد الوصول. ومن الصفّ لا من المفتاح.
 */

import { useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { changeHourlyPrepay, getRideDriverStats } from "@/api/endpoints";
import type { Ride } from "@/api/types";
import { PaymentPicker, PAY_ICON_T2 } from "@/components/payment/PaymentPicker";
import { DriverAvatar } from "@/components/ride/DriverAvatar";
import { PauseNotice } from "@/components/ride/PauseNotice";
import { StopProgress } from "@/components/ride/StopProgress";
import { CANCELLABLE, shareRide, useTrackingSheet } from "@/components/ride/useTrackingSheet";
import { ErrorNote } from "@/components/ui/Feedback";
import { useCountryConfig } from "@/lib/config";
import { payerScope, usePayerPreference } from "@/lib/for-other";
import { clockText, hoursLabel, noDestination, useHourlyClock } from "@/lib/hourly";
import { PAYMENT_METHOD_LABEL, VEHICLE_LABEL } from "@/lib/labels";
import { distanceKm, lengthKm, trimRoute, type LatLng } from "@/lib/route-line";
import { skinImageUrl } from "@/lib/skin";
import { DISPLAY_LOCALE, currencyLabel, formatDistance, formatMoney, ratedAverage } from "@/lib/utils";

import { CommsButtonsT2 } from "./CommsT2";
import { ForOtherTrackT2 } from "./ForOtherT2";
import { HourlyTrackT2 } from "./HourlyT2";
import { ParcelTrackT2 } from "./ParcelT2";
import { nearbyLabel } from "./RiderHomeT2";
import { SheetT2 } from "./SheetT2";
import { isWomenRide, RideCodeCardT2, WomenApproachChipT2, womenApproachTitle, WomenCaptainCardT2 } from "./WomenRideT2";
import "@/taxo2";
import "./t2.css";
import "./tracking-count.css";

export interface TrackingT2Props {
  ride: Ride;
  onChanged: () => void;
  /** موضعُ الكبتن المبثوث — منه «كم متبقية». */
  driverPing: LatLng | null;
  /** المسارُ المجمَّد على الرحلة بعد القبول (البند ٨) — `[lng, lat]`. */
  routePoints: number[][] | null;
  /** **عنوانُ نقطة الانطلاق من Mapbox** حين طُلبت من موقع الجهاز بلا عنوان — ما رأته في «R06» بعينه، **ويُمرَّر حين تكون
   *  النقطةُ هي هي** (`Home`)، وإلا فلا: عنوانُ موقعٍ آخرَ ليس انطلاقَ هذه الرحلة. */
  pickupLine?: string | null;
  /** **كم سيارةً ترسمها الخريطةُ حولك أثناء البحث** (R07، §٦٢-ج/٢٧) — العددُ نفسُه لا عدٌّ ثانٍ، و`null` حين لا تُرسم سيارة
   *  (تفضيلُ الرحلة غيرُ تفضيل الملفّ) فلا يُقال عددٌ لا تراه. */
  nearby?: number | null;
}

/** «2,140 رحلة» كما رُسمت في R08 — **والتمييزُ بآخر خانتين**: «3 رحلات» و«103 رحلات»، و«11 رحلة» و«2,140 رحلة»؛ والخاناتُ
 *  لاتينيةٌ بفواصل الآلاف (`DISPLAY_LOCALE`، §20). */
function ridesLabel(count: number): string {
  if (count === 1) return "رحلة واحدة";
  if (count === 2) return "رحلتان";
  const tail = count % 100;
  // **مسافةٌ لا تنكسر** بين العدد ومعدوده — فلا يبقى الرقمُ آخرَ سطرٍ والتمييزُ أوّلَ تاليه
  return `${new Intl.NumberFormat(DISPLAY_LOCALE).format(count)} ${tail >= 3 && tail <= 10 ? "رحلات" : "رحلة"}`;
}

/** **عددُ رحلات الكبتن المكتملة لبطاقته في R08** — يُسأل مرّةً لكلِّ رحلةٍ ما دام الكبتنُ في الطريق أو ينتظر، **ولا يُعرض صفرٌ
 *  ولا يُنتظر**: بطاقةٌ بلا العدد حتى يصل، أو إن تعثّر. */
function useDriverRides(ride: Ride): number | null {
  const [count, setCount] = useState<number | null>(null);
  const approaching = ride.driver !== null && (ride.status === "accepted" || ride.status === "arrived");
  useEffect(() => {
    if (!approaching) return;
    let live = true;
    getRideDriverStats(ride.id)
      .then((stats) => {
        if (live) setCount(stats.completed_rides);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [ride.id, approaching]);
  return count;
}

/** ما بقي من الطريق وما مضى منه — **من المسار المجمَّد وموضع الكبتن عليه**، و`null` بلا أحدهما: لا رقمَ يُخمَّن. */
export function tripProgress(routePoints: number[][] | null, driverPing: LatLng | null) {
  if (!routePoints || routePoints.length < 2 || !driverPing) return null;
  const whole = lengthKm(routePoints);
  if (whole <= 0) return null;
  const left = lengthKm(trimRoute(routePoints, driverPing));
  return { left, done: Math.min(1, Math.max(0, 1 - left / whole)) };
}

const riding = (ride: Ride) => ride.status === "in_progress" || ride.status === "at_stop";

/** **«ادفع الساعاتِ نقداً بدل المحفظة» وعكسُه** (§٦٣-ج/٥) — قبل البدء وحدَه، **والرحلةُ تُعاد من الخلفية بعده** (`onChanged`)
 *  فلا تُكتب القيمةُ الجديدةُ محلّياً قبل أن تقبلها. ورفضُه (٤٠٩ بعد البدء) يُقال بنصّ الخلفية تحت الزرّ. */
function useHourlyPrepaySwitch(ride: Ride, onChanged: () => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function toggle() {
    setBusy(true);
    setError(null);
    try {
      await changeHourlyPrepay(ride.id, ride.hourly_prepay_method === "cash" ? "wallet" : "cash");
      onChanged();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر تغيير طريقة الدفع");
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, toggle: () => void toggle() };
}

export function TrackingSheetT2({ ride, onChanged, driverPing, routePoints, pickupLine, nearby = null }: TrackingT2Props) {
  const t = useTrackingSheet({ ride, onChanged });
  const driverRides = useDriverRides(ride);
  const countryConfig = useCountryConfig(ride.country_code);
  // **طريقةُ الدفع تفضيلٌ محلّي** كما في ورقة الطلب — تُعرض هنا وتُبدَّل، **ولا تُرسل مع الرحلة** (`lib/payment`).
  // **ومضيَّقةٌ بالدافع في رحلةٍ لغيره** (§٦٣-ج/١): المحفظةُ والبطاقةُ وحدهما، **ولا قناةَ تُعرض** إن دفع الراكبُ نقداً —
  // فسطرُ الدافع في كتلتها (`ForOtherTrackT2`) هو ما يُقال بدلها. **وطردٌ يدفعه مستلمُه كذلك** (`ParcelTrackT2`)
  const { available: channels, resolved: payMethod, choose } = usePayerPreference(countryConfig, payerScope(ride));
  const parcel = ride.ride_type === "parcel";
  // **بالساعة** (§٦٣-ج/٥) — من الصفّ لا من المفتاح، **وساعتُها من البدء المقيس** (`null` قبله): وقتٌ يُحسب لا مال
  const hourly = ride.ride_type === "hourly";
  const clock = useHourlyClock(hourly ? ride.started_at : null, ride.hourly_hours);
  const prepaySwitch = useHourlyPrepaySwitch(ride, onChanged);
  // **المشوارُ الثابت** (§٦٣-ج/٦) — مدفوعةٌ من الاشتراك: **لا قناةَ تُعرض ولا تُبدَّل**، بل «مدفوعة من اشتراكك». ومن الصفّ
  const commute = ride.commute;
  const [pickingPay, setPickingPay] = useState(false);

  const share = async () => {
    const shared = await shareRide(ride);
    if (!shared) {
      t.setCopied(true);
      window.setTimeout(() => t.setCopied(false), 2_500);
    }
  };

  /** شارتا الطلب — **وصفٌ لما طُلب** كما في الورقة القائمة: «رحلة نسائية» تطمينٌ بأن الشرطَ سارٍ، والمشاركةُ بحاليها. */
  const badges =
    t.women || Number(ride.share_discount_percent) > 0 || parcel || hourly || commute ? (
      <div className="t2-trk-badges">
        {/* **«مشوارٌ ثابت»** (§٦٣-ج/٦) — رحلةٌ من اشتراكه، من الصفّ لا من المفتاح */}
        {commute ? <span className="t2-trk-badge">مشوارٌ ثابت</span> : null}
        {/* **«طرد»** (§٦٣-ج/٤) — وصفٌ لما طُلب كأخواتها، من الصفّ لا من المفتاح */}
        {parcel ? <span className="t2-trk-badge">طرد</span> : null}
        {/* **«بالساعة»** (§٦٣-ج/٥) — بالحكم نفسِه */}
        {hourly ? <span className="t2-trk-badge">بالساعة</span> : null}
        {t.women ? <span className="t2-trk-badge women">رحلة نسائية</span> : null}
        {Number(ride.share_discount_percent) > 0 ? (
          <span className="t2-trk-badge">{ride.share_group_id ? "رحلة مشتركة" : "بانتظار شريك"}</span>
        ) : null}
      </div>
    ) : null;

  /** **تأكيدُ الإلغاء بنصِّ الورقة القائمة حرفاً** — وأسبابُه بعد القبول وحدَه، و«ليس أنثى» لرحلةٍ طُلب فيها جنس. */
  const confirm = t.confirming ? (
    <div className="t2-trk-confirm">
      <p className="t2-trk-confirm-text">
        {/* **وللساعات رسمُ ما بعد الوصول من سعرها** (§٦٣-ج/٥، `hourly.cancel_fee`) — يُقال قبل «نعم» **بلا رقم**: الرحلةُ لا تنشر
            دقائقَه، ورقمٌ يُخمَّن هنا يفترق عمّا جُمِّد عليها */}
        {t.afterAccept
          ? hourly && ride.status === "arrived"
            ? "الكبتن عندك — إلغاؤك بعد وصول الكبتن يُحتسب عليه رسمُ إلغاءٍ من سعر الساعة."
            : hourly
              ? "الكبتن في طريقه إليك — قد تُطبَّق رسوم إلغاء، وإلغاؤك بعد وصوله يُحتسب عليه رسمُ إلغاءٍ من سعر الساعة."
              : "الكبتن في طريقه إليك — قد تُطبَّق رسوم إلغاء."
          : "سيتوقف البحث عن كبتن. متأكد؟"}
      </p>
      {t.afterAccept ? (
        <div className="t2-trk-reasons">
          {t.reasons.map((option) => (
            <button
              key={option.label}
              type="button"
              className={t.reason?.label === option.label ? "t2-trk-reason on" : "t2-trk-reason"}
              onClick={() => t.setReason(option)}
            >
              {option.label}
            </button>
          ))}
          {t.reason?.code === "gender_mismatch" ? (
            <p className="t2-trk-reason-note">
              بلا رسوم إلغاء على أيٍّ من الطرفين. ويُسجَّل بلاغٌ على الحساب الآخر، وتكرارُ البلاغات يوسم الحساب للمراجعة.
            </p>
          ) : null}
        </div>
      ) : null}
      <div className="t2-trk-confirm-row">
        <button type="button" className="t2-button danger" disabled={t.busy} aria-busy={t.busy} onClick={t.cancel}>
          نعم، ألغِ الرحلة
        </button>
        <button type="button" className="t2-button secondary" onClick={() => t.setConfirming(false)}>
          تراجع
        </button>
      </div>
    </div>
  ) : null;

  const picker =
    pickingPay && payMethod ? (
      <PaymentPicker
        channels={channels}
        selected={payMethod.method}
        onSelect={(method) => {
          choose(method);
          setPickingPay(false);
        }}
        onClose={() => setPickingPay(false)}
        walletHint={null}
      />
    ) : null;

  // ── R07: البحث ─────────────────────────────────────────────────────────────────────────────────────
  if (t.searching) {
    return (
      <SheetT2
        footer={
          confirm ?? (
            <>
              <button type="button" className="t2-trk-cancel" disabled={t.busy} onClick={() => t.setConfirming(true)}>
                إلغاء الطلب
              </button>
              {/* **صدقٌ لا وعد**: الإلغاءُ مجانيٌّ قبل القبول (القسم 5) — ورسمُه بعده يُقال هناك */}
              <p className="t2-trk-free">الإلغاء الآن مجاني.</p>
            </>
          )
        }
      >
        <div className="t2-trk-head">
          <h3 className="t2-trk-title">نبحث لك عن كبتن قريب</h3>
          {badges}
        </div>
        {/* **سطرُ التطبيق القائم لا سطرُ اللوحة**: «عادةً أقل من دقيقة» وعدٌ بلا مصدر (§٦١-د/د). **و«6 كباتن حولك الآن» من اللوحة**
            (§٦٢-ج/٢٧) — عددُ ما ترسمه الخريطةُ نفسُه، **ولا يُقال صفرٌ ولا عددٌ لا يُرسم** */}
        {/* **«انتظري، نوسّع البحث» اختارته هي** (§٦٤-ج/٤-٣، `search_widened`) — فالسطرُ يقول ما يقع الآن **بلا عددٍ ولا نصفِ قطر**:
            عددُ الكبتنات القريبات لم يُقَل (`APPROVALS-62` §٦-٢)، **ولا يُلحق به عددُ السيارات** ولو وصل */}
        <p className="t2-trk-sub">
          {ride.search_widened ? "نوسّع البحث بين الكبتنات…" : "نعرض طلبك على أقرب الكباتن — قد يستغرق دقيقتين"}
          {/* **والعددُ لا ينفصل عن معدوده** آخرَ السطر (` `) — قِيس: «6» وحدَها آخرَ سطرٍ و«كباتن» أوّلَ تاليه */}
          {nearby && !ride.search_widened ? `. ${nearby > 2 ? `${nearby} ` : ""}${nearbyLabel(nearby)} الآن.` : ""}
        </p>
        {/* **شريطٌ يتحرّك ولا يتقدّم** — «لا نعرف كم يبقى، وشريطٌ يتقدّم يَعِد بما لا نملكه» (الورقة القائمة) */}
        <div className="t2-trk-bar" role="progressbar" aria-label="نبحث عن كبتن" aria-busy="true">
          <span />
        </div>
        <div className="t2-trk-route">
          <div className="t2-trk-route-points">
            <span className="t2-trk-dot from" aria-hidden="true" />
            <span className="t2-trk-route-text">{ride.pickup_address ?? pickupLine ?? "نقطة الانطلاق"}</span>
            <span className="t2-trk-dot to" aria-hidden="true" />
            {/* **ساعاتٌ بلا وجهةٍ تقول ذلك** (§٦٣-ج/٥) — لا «الوجهة» عن نقطة الانطلاق نفسِها */}
            <span className="t2-trk-route-text">
              {hourly && noDestination(ride) ? "بلا وجهة — تقولها للكبتن" : (ride.dropoff_address ?? "الوجهة")}
            </span>
          </div>
          <div className="t2-trk-route-fare">
            <div className="t2-trk-route-kind">
              {VEHICLE_LABEL[ride.vehicle_category]}
              {commute ? " · مدفوعة من اشتراكك" : payMethod ? ` · ${PAYMENT_METHOD_LABEL[payMethod.method]}` : ""}
            </div>
            <div className="t2-trk-route-price">
              <span dir="ltr" className="t2-num">{formatMoney(ride.estimated_fare)}</span> {currencyLabel(ride.currency)}
            </div>
          </div>
        </div>
        {/* **رحلةٌ لشخصٍ آخر** (§٦٣-ج/١): الدافعُ ورابطُ التتبّع من أوّل البحث — والاسمُ لا يُنشر قبل القبول */}
        {ride.for_other ? <ForOtherTrackT2 ride={ride} /> : null}
        {/* **والطرد** (§٦٣-ج/٤): دافعُه من أوّل البحث، والمستلمُ بعد القبول */}
        {parcel ? <ParcelTrackT2 ride={ride} /> : null}
        {/* **والساعات** (§٦٣-ج/٥): عددُها وكيلومتراتُها، ومن أين يُدفع محجوزُها بزرِّ تبديله — من أوّل البحث */}
        {hourly ? <HourlyTrackT2 ride={ride} prepaySwitch={prepaySwitch} /> : null}
        {/* انتظارُ الكبتنة يُقال حين يُشعر به (المرحلة 10-ج) — كما هو اليوم */}
        {t.women ? (
          <p className="t2-note">
            <span className="t2-icon" aria-hidden="true">schedule</span>
            نبحث عن كبتنة متاحة. عددهنّ أقل، فقد يطول الانتظار قليلاً — ونوسّع دائرة البحث قبل أن نعتذر.
          </p>
        ) : null}
        <ErrorNote message={t.error} className="t2-error" />
      </SheetT2>
    );
  }

  const driver = ride.driver;
  const vehicle = driver?.vehicle ?? null;
  const skinRow =
    driver?.skin && t.skinArt !== "broken" ? (
      // **مركبةُ المتجر — ما يتحرّك على الخريطة هو ما يُرسم هنا** (2026-08-22)، ولا يُحجز مكانٌ لرسمةٍ لم تصل
      <div className={t.skinArt === "loading" ? "t2-trk-skin hidden" : "t2-trk-skin"}>
        <img
          src={skinImageUrl(driver.skin.image_url)}
          alt=""
          width={44}
          height={44}
          onLoad={() => t.setSkinArt("ready")}
          onError={() => t.setSkinArt("broken")}
        />
        <p>هذه المركبة التي تتحرّك على خريطتك — ابحث عنها في الشارع.</p>
      </div>
    ) : null;

  const shareRow = (
    <button type="button" className="t2-trk-rowbtn" onClick={() => void share()}>
      <span className="t2-icon" aria-hidden="true">share_location</span>
      <span className="t2-trk-rowbtn-text">{t.copied ? "نُسخت التفاصيل" : "شارك رحلتك مع شخص تثق به"}</span>
      <span className="t2-icon t2-trk-rowbtn-go" aria-hidden="true">chevron_left</span>
    </button>
  );

  // ── R09: أثناء الرحلة ────────────────────────────────────────────────────────────────────────────────
  if (riding(ride)) {
    const progress = tripProgress(routePoints, driverPing);
    return (
      <SheetT2>
        {driver ? (
          <div className="t2-trk-drow">
            <DriverAvatar rideId={ride.id} name={driver.name} className="t2-trk-avatar sm" />
            <div className="t2-trk-dmain">
              <div className="t2-trk-dname">{driver.name}</div>
              {vehicle ? (
                <div className="t2-trk-dmeta">
                  {vehicle.make} {vehicle.model} · <span dir="ltr">{vehicle.plate_number}</span>
                </div>
              ) : null}
            </div>
          </div>
        ) : null}
        {/* **«رسالة» و«اتصال»** (§٦٦) — تحت الكبتن ما دامت الرحلةُ جارية، ويغيبان بانتهائها */}
        <CommsButtonsT2 />
        {badges}
        <div className={progress || clock ? "t2-trk-stats" : "t2-trk-stats two"}>
          {/* **الساعةُ مكانَ «كم متبقية» للساعات** (§٦٣-ج/٥): الباقي من «البدء + الساعات»، **ثمّ «وقتٌ زائد» بنبرة التنبيه** — وما
              زاد يُسعَّر في الخلفية عند الإنهاء، فلا مبلغَ يُقال هنا */}
          {clock ? (
            clock.left > 0 ? (
              <div className="t2-trk-stat">
                <div dir="ltr" className="t2-trk-stat-value">{clockText(clock.left)}</div>
                <div className="t2-trk-stat-label">الوقتُ الباقي</div>
              </div>
            ) : (
              <div className="t2-trk-stat t2-hr-over" role="status">
                <div className="t2-trk-stat-value">وقتٌ زائد · {clock.over} د</div>
                <div className="t2-trk-stat-label">فوق الساعات المحجوزة</div>
              </div>
            )
          ) : progress ? (
            <div className="t2-trk-stat">
              <div dir="ltr" className="t2-trk-stat-value">{progress.left.toFixed(1)}</div>
              <div className="t2-trk-stat-label">كم متبقية</div>
            </div>
          ) : null}
          <div className="t2-trk-stat">
            <div dir="ltr" className="t2-trk-stat-value">{formatMoney(ride.estimated_fare)}</div>
            {/* **سعرُ المشوار مجمَّدٌ لا تقدير** (§٦٣-ج/٦) — دُفع مع الاشتراك */}
            <div className="t2-trk-stat-label">
              {currencyLabel(ride.currency)} {commute ? "من اشتراكك" : "تقديرياً"}
            </div>
          </div>
        </div>
        {/* المحطاتُ وعدّادُ الانتظار، والوقفةُ غيرُ المخطَّطة حين تنشأ — **مالٌ يُقال في لحظته** كما في الورقة القائمة */}
        <StopProgress ride={ride} />
        <PauseNotice ride={ride} />
        {/* **اقتراحُ المشاركة لمن طلبت الخدمة** لحظةَ تحرّك السيارة (المرحلة 10-ج) — كما هو اليوم */}
        {ride.status === "in_progress" && t.women && !t.shareHintClosed ? (
          <div className="t2-callout">
            <span className="t2-icon fill" aria-hidden="true">verified_user</span>
            <div className="t2-callout-main">
              <div className="t2-callout-title">شاركي رحلتك مع من تثقين</div>
              <p className="t2-callout-body">نرسل اسم الكبتن ولوحة المركبة والوجهة — بلا موقعك اللحظي.</p>
              <div className="t2-trk-hint-row">
                <button
                  type="button"
                  className="t2-button primary"
                  onClick={async () => {
                    await share();
                    t.setShareHintClosed(true);
                  }}
                >
                  مشاركة
                </button>
                <button type="button" className="t2-button secondary" onClick={() => t.setShareHintClosed(true)}>
                  ليس الآن
                </button>
              </div>
            </div>
          </div>
        ) : null}
        {/* **الراكبُ الفعليُّ والدافعُ ورابطُ التتبّع** (§٦٣-ج/١) — تحت بطاقة الرحلة */}
        {ride.for_other ? <ForOtherTrackT2 ride={ride} /> : null}
        {/* **مستلمُ الطرد ودافعُه** (§٦٣-ج/٤) */}
        {parcel ? <ParcelTrackT2 ride={ride} /> : null}
        {/* **والساعاتُ وكيلومتراتُها المشمولة** (§٦٣-ج/٥) — بلا تبديل: المحجوزُ دُفع عند البدء */}
        {hourly ? <HourlyTrackT2 ride={ride} prepaySwitch={prepaySwitch} /> : null}
        {skinRow}
        {shareRow}
        {/* **«مدفوعة من اشتراكك» مكانَ صفِّ الدفع** (§٦٣-ج/٦) — صفٌّ يُقرأ ولا يُضغط: لا قناةَ تُبدَّل */}
        {commute ? (
          <div className="t2-trk-rowbtn" role="note">
            <span className="t2-icon" aria-hidden="true">event_repeat</span>
            <span className="t2-trk-rowbtn-text">الدفع: مدفوعة من اشتراكك</span>
          </div>
        ) : payMethod ? (
          <button
            type="button"
            className="t2-trk-rowbtn"
            disabled={channels.length < 2}
            onClick={() => setPickingPay(true)}
          >
            <span className="t2-icon" aria-hidden="true">{PAY_ICON_T2[payMethod.method]}</span>
            <span className="t2-trk-rowbtn-text">الدفع: {PAYMENT_METHOD_LABEL[payMethod.method]}</span>
            {channels.length > 1 ? <span className="t2-trk-change">تغيير</span> : null}
          </button>
        ) : null}
        <ErrorNote message={t.error} className="t2-error" />
        {picker}
      </SheetT2>
    );
  }

  // ── R08: الكبتن في الطريق · ينتظرك ───────────────────────────────────────────────────────────────────
  const arrived = ride.status === "arrived";
  // **RW4 — الكبتنةُ لمن طلبتها** (§٦٢-ج/٢٣): العنوانُ مؤنّثاً، وبطاقتُها بالبرقوق (`WomenRideT2`)
  const womenRide = isWomenRide(ride);
  return (
    <SheetT2
      footer={
        CANCELLABLE.has(ride.status)
          ? confirm ?? (
              <button
                type="button"
                className="t2-trk-cancel-link"
                disabled={t.busy}
                onClick={() => t.setConfirming(true)}
              >
                إلغاء الرحلة · قد تُطبَّق رسوم
              </button>
            )
          : null
      }
    >
      <div className="t2-trk-head2">
        <div className="t2-trk-head2-main">
          <div className="t2-trk-title2">
            {womenRide ? womenApproachTitle(arrived) : arrived ? "الكبتن ينتظرك في نقطة الانطلاق" : "الكبتن في الطريق إليك"}
          </div>
          {vehicle ? (
            <div className="t2-trk-veh">
              {vehicle.make} {vehicle.model} · {vehicle.color}
            </div>
          ) : null}
        </div>
        {badges}
      </div>
      {driver && womenRide ? <WomenCaptainCardT2 ride={ride} /> : null}
      {/* **رمزُ الرحلة تحت بطاقتها** (RW4، §٦٢-ج/٥) — لرحلةٍ تطلبه وحدَها */}
      {driver && womenRide ? <RideCodeCardT2 ride={ride} /> : null}
      {driver && !womenRide ? (
        <div className="t2-trk-driver">
          <DriverAvatar rideId={ride.id} name={driver.name} className="t2-trk-avatar" />
          <div className="t2-trk-dmain">
            <div className="t2-trk-dname lg">{driver.name}</div>
            {/* **ولا «★ 0.00» لكبتنٍ لم يُقيَّم بعد** (`ratedAverage`، §٦٢-ب/٤٩) — والسطرُ كلُّه يغيب إن لم يبقَ فيه شيء */}
            {ratedAverage(driver.rating_avg) || driverRides ? (
              <div className={driverRides ? "t2-trk-rating with-rides" : "t2-trk-rating"}>
                {ratedAverage(driver.rating_avg) ? (
                  <>
                    <span className="t2-icon fill" aria-hidden="true">star</span>
                    <span className="t2-trk-rating-value">{Number(driver.rating_avg).toFixed(2)}</span>
                  </>
                ) : null}
                {/* **«· 2,140 رحلة» كما رُسمت** (§٦٢-ج/٢٧) — ما أكمله فعلاً، **ولا يُرسم صفرٌ** لكبتنٍ في أوّل رحلاته. **والعددُ ومعدودُه
                    لا ينفصلان** (`t2-trk-rides`): على ٣٦٠ ينزلان سطراً معاً بدل «2,140» وحدَها و«رحلة» تحتها (قِيس) */}
                {driverRides ? (
                  <>
                    {ratedAverage(driver.rating_avg) ? <span aria-hidden="true">·</span> : null}
                    <span className="t2-trk-rides">{ridesLabel(driverRides)}</span>
                  </>
                ) : null}
              </div>
            ) : null}
          </div>
          {vehicle ? (
            <div dir="ltr" className="t2-trk-plate">
              <span className="t2-trk-plate-cc">{ride.country_code}</span>
              <span className="t2-trk-plate-no">{vehicle.plate_number}</span>
            </div>
          ) : null}
        </div>
      ) : null}
      {/* **«رسالة» و«اتصال»** (§٦٦) — من قبول الكبتن، تحت بطاقته (وبطاقةِ الكبتنة ورمزِ الرحلة في RW4) */}
      {driver ? <CommsButtonsT2 /> : null}
      {/* **الراكبُ الفعليُّ والدافعُ ورابطُ التتبّع** (§٦٣-ج/١) — تحت بطاقة الكبتن */}
      {ride.for_other ? <ForOtherTrackT2 ride={ride} /> : null}
      {/* **مستلمُ الطرد ودافعُه** (§٦٣-ج/٤) — تحت بطاقة الكبتن */}
      {parcel ? <ParcelTrackT2 ride={ride} /> : null}
      {/* **والساعاتُ ومن أين يُدفع محجوزُها** (§٦٣-ج/٥) — والتبديلُ ممكنٌ حتى يبدأ الكبتن */}
      {hourly ? <HourlyTrackT2 ride={ride} prepaySwitch={prepaySwitch} /> : null}
      {skinRow}
      {/* **انتظارُ الوصول يُقال حين ينشأ** (§5.10) — مالٌ في لحظته كما في الورقة القائمة */}
      <PauseNotice ride={ride} />
      <div className="t2-trk-gap" />
      {shareRow}
      <ErrorNote message={t.error} className="t2-error" />
    </SheetT2>
  );
}

/** **«الكبتن على بعد…» فوق الخريطة** (R08) — من موقعه المبثوث إلى نقطة الالتقاء خطّاً مستقيماً، و«وصل» حين يصل. */
export function ApproachChipT2({
  ride,
  driverPing,
  minutes = null,
}: {
  ride: Ride;
  driverPing: LatLng | null;
  /** **دقائقُه الباقية** من مسار الاقتراب (§٦٢-ج/١٠) — و`null` حيث المفتاحُ مطفأ: المسافةُ وحدَها كما كانت. */
  minutes?: number | null;
}) {
  // **RW4 — حبّةُ الكبتنة بالبرقوق** لمن طلبت كبتنة (§٦٢-ج/٢٣)
  if (isWomenRide(ride)) return <WomenApproachChipT2 ride={ride} driverPing={driverPing} minutes={minutes} />;
  if (ride.status === "arrived") {
    return (
      <div className="t2 t2-trk-chip">
        <span className="t2-trk-chip-dot" aria-hidden="true" />
        وصل الكبتن
      </div>
    );
  }
  if (ride.status !== "accepted" || !driverPing) return null;
  return (
    <div className="t2 t2-trk-chip">
      <span className="t2-trk-chip-dot" aria-hidden="true" />
      الكبتن على بعد {formatDistance(distanceKm(driverPing, ride.pickup))}
      {minutes !== null ? ` · ${minutes} د` : ""}
    </div>
  );
}

/** **بطاقةُ الطريق فوق الخريطة** (R09) — الوجهةُ وتقدّمُ الكبتن على المسار المجمَّد. **ولا «وقت الوصول»**: لا مصدرَ له. */
export function TripCardT2({
  ride,
  driverPing,
  routePoints,
}: {
  ride: Ride;
  driverPing: LatLng | null;
  routePoints: number[][] | null;
}) {
  const progress = tripProgress(routePoints, driverPing);
  // **الطرد** (§٦٣-ج/٤): «طردك في الطريق» — **وإلى مستلمه باسمه** حين يُنشر، وإلا فإلى وجهته كأيِّ رحلة
  const parcel = ride.ride_type === "parcel";
  // **بالساعة** (§٦٣-ج/٥): «بالساعة · 3 ساعات» — **و«بلا وجهة» حين لم تُختر**: الوجهاتُ يقولها الراكبُ للكبتن
  const hourly = ride.ride_type === "hourly" && ride.hourly_hours !== null;
  return (
    <div className="t2 t2-trk-card">
      <div className="t2-trk-card-label">
        {parcel ? "طردك في الطريق" : hourly ? `بالساعة · ${hoursLabel(ride.hourly_hours!)}` : "في الطريق إلى"}
      </div>
      <div className="t2-trk-card-dest">
        {parcel && ride.recipient_name
          ? `إلى: ${ride.recipient_name}`
          : hourly && noDestination(ride)
            ? "بلا وجهة — تقولها للكبتن"
            : (ride.dropoff_address ?? "وجهتك")}
      </div>
      {progress ? (
        <div className="t2-trk-progress" role="img" aria-label={`قُطع ${Math.round(progress.done * 100)}٪ من الطريق`}>
          <span className="t2-trk-progress-track" />
          <span className="t2-trk-progress-fill" style={{ width: `${progress.done * 100}%` }} />
          <span className="t2-trk-progress-from" />
          <span className="t2-trk-progress-to" />
          {/* **علامةُ الكبتن على الشريط X الهوية** كما رُسمت — خطٌّ بالجمر وآخرُ أبيض */}
          <span className="t2-trk-progress-car" style={{ insetInlineStart: `${progress.done * 100}%` }}>
            <i />
            <i />
          </span>
        </div>
      ) : null}
    </div>
  );
}

/** **مبدّلُ السِمة أثناء الرحلة** — لم يُرسم في R07–R09، **وقرارُ المالك ٢٥ يُبقيه**: «من يبدّلها لأن الشمس على الشاشة يبدّلها وهو
 *  ينظر إلى الخريطة» — وفي الرحلة لا شريطَ ولا «إعدادات» يُبلغان. وموضعُه طرفُ الرأس، **وتحت بطاقة الطريق** في R09. */
export function ThemeButtonT2({ dark, low, onToggle }: { dark: boolean; low: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      className={low ? "t2 t2-mapbtn t2-trk-theme low" : "t2 t2-mapbtn t2-trk-theme"}
      onClick={onToggle}
      aria-label={dark ? "الوضع النهاري" : "الوضع الليلي"}
    >
      <span className="t2-icon" aria-hidden="true">{dark ? "light_mode" : "dark_mode"}</span>
    </button>
  );
}
