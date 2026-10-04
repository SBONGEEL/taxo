/** تتبّعُ الرحلة — TAXO 2.0 «R07 البحث · R08 الكبتن في الطريق · R09 أثناء الرحلة» (Claude Design «Rider»)،
 * **في المظهر النهاريّ المرسوم وحدَه**.
 *
 * **وجهٌ ثانٍ لورقة التتبّع لا ورقةٌ ثانية**: الإلغاءُ بأسبابه، وإرسالُ التفاصيل، ورسمةُ المركبة كلُّها من `useTrackingSheet`
 * — **فلا يفترق الوجهان في إلغاءٍ ولا في سببٍ ولا في رسم**. والقائمُ في الليليّ كما هو (`TrackingSheet`).
 *
 * **والقيمُ الحيّةُ من بياناتٍ أو لا شيء** (§٦١-د/د): المسافةُ إلى الكبتن من موقعه المبثوث ونقطة الالتقاء، و«كم متبقية» من
 * المسار المجمَّد على الرحلة وموضع الكبتن عليه — **حسابُ هندسةٍ للعرض لا يُسعَّر منه شيء** (`lib/route-line`).
 *
 * **وما رسمته اللوحةُ ولا مصدرَ له اليوم — لم يُرسم** (`TAXO2-DESIGN-CORRECTIONS.md` §٢٤): رمزُ الرحلة · مهلةُ الوصول ووقتُه ·
 * عددُ رحلات الكبتن · «اتصال» و«رسالة» و«أمان» و«طوارئ SOS» · «عادةً أقل من دقيقة» · السياراتُ حولك أثناء البحث.
 *
 * **وما في الورقة القائمة ولم يُرسم يبقى بلغة اللوحة**: شارةُ «رحلة نسائية» وانتظارُ الكبتنة واقتراحُ المشاركة لها (§61: كما هي
 * اليوم) · شارتا المشاركة · المحطاتُ وعدّادُ الانتظار والوقفةُ غيرُ المخطَّطة (مالٌ يُقال حين ينشأ) · رسمةُ مركبة المتجر · أسبابُ
 * الإلغاء بعد القبول.
 */

import { useState } from "react";

import type { Ride } from "@/api/types";
import { PaymentPicker, PAY_ICON_T2 } from "@/components/payment/PaymentPicker";
import { DriverAvatar } from "@/components/ride/DriverAvatar";
import { PauseNotice } from "@/components/ride/PauseNotice";
import { StopProgress } from "@/components/ride/StopProgress";
import { CANCELLABLE, CANCEL_REASONS, shareRide, useTrackingSheet } from "@/components/ride/useTrackingSheet";
import { ErrorNote } from "@/components/ui/Feedback";
import { useCountryConfig } from "@/lib/config";
import { PAYMENT_METHOD_LABEL, VEHICLE_LABEL } from "@/lib/labels";
import { usePaymentPreference } from "@/lib/payment";
import { distanceKm, lengthKm, trimRoute, type LatLng } from "@/lib/route-line";
import { skinImageUrl } from "@/lib/skin";
import { currencyLabel, formatDistance, formatMoney } from "@/lib/utils";

import { SheetT2 } from "./SheetT2";
import "@/taxo2";
import "./t2.css";

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

export function TrackingSheetT2({ ride, onChanged, driverPing, routePoints, pickupLine }: TrackingT2Props) {
  const t = useTrackingSheet({ ride, onChanged });
  const countryConfig = useCountryConfig(ride.country_code);
  // **طريقةُ الدفع تفضيلٌ محلّي** كما في ورقة الطلب — تُعرض هنا وتُبدَّل، **ولا تُرسل مع الرحلة** (`lib/payment`)
  const { available: channels, resolved: payMethod, choose } = usePaymentPreference(countryConfig);
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
    t.gendered || Number(ride.share_discount_percent) > 0 ? (
      <div className="t2-trk-badges">
        {t.gendered ? <span className="t2-trk-badge women">رحلة نسائية</span> : null}
        {Number(ride.share_discount_percent) > 0 ? (
          <span className="t2-trk-badge">{ride.share_group_id ? "رحلة مشتركة" : "بانتظار شريك"}</span>
        ) : null}
      </div>
    ) : null;

  /** **تأكيدُ الإلغاء بنصِّ الورقة القائمة حرفاً** — وأسبابُه بعد القبول وحدَه، و«ليس أنثى» لرحلةٍ طُلب فيها جنس. */
  const confirm = t.confirming ? (
    <div className="t2-trk-confirm">
      <p className="t2-trk-confirm-text">
        {t.afterAccept ? "الكبتن في طريقه إليك — قد تُطبَّق رسوم إلغاء." : "سيتوقف البحث عن كبتن. متأكد؟"}
      </p>
      {t.afterAccept ? (
        <div className="t2-trk-reasons">
          {CANCEL_REASONS.filter((option) => option.code !== "gender_mismatch" || t.gendered).map((option) => (
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
        variant="t2"
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
        {/* **سطرُ التطبيق القائم لا سطرُ اللوحة**: «عادةً أقل من دقيقة» وعدٌ بلا مصدر (§٦١-د/د) */}
        <p className="t2-trk-sub">نعرض طلبك على أقرب الكباتن — قد يستغرق دقيقتين</p>
        {/* **شريطٌ يتحرّك ولا يتقدّم** — «لا نعرف كم يبقى، وشريطٌ يتقدّم يَعِد بما لا نملكه» (الورقة القائمة) */}
        <div className="t2-trk-bar" role="progressbar" aria-label="نبحث عن كبتن" aria-busy="true">
          <span />
        </div>
        <div className="t2-trk-route">
          <div className="t2-trk-route-points">
            <span className="t2-trk-dot from" aria-hidden="true" />
            <span className="t2-trk-route-text">{ride.pickup_address ?? pickupLine ?? "نقطة الانطلاق"}</span>
            <span className="t2-trk-dot to" aria-hidden="true" />
            <span className="t2-trk-route-text">{ride.dropoff_address ?? "الوجهة"}</span>
          </div>
          <div className="t2-trk-route-fare">
            <div className="t2-trk-route-kind">
              {VEHICLE_LABEL[ride.vehicle_category]}
              {payMethod ? ` · ${PAYMENT_METHOD_LABEL[payMethod.method]}` : ""}
            </div>
            <div className="t2-trk-route-price">
              <span dir="ltr" className="t2-num">{formatMoney(ride.estimated_fare)}</span> {currencyLabel(ride.currency)}
            </div>
          </div>
        </div>
        {/* انتظارُ الكبتنة يُقال حين يُشعر به (المرحلة 10-ج) — كما هو اليوم */}
        {t.gendered ? (
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
        {badges}
        <div className={progress ? "t2-trk-stats" : "t2-trk-stats two"}>
          {progress ? (
            <div className="t2-trk-stat">
              <div dir="ltr" className="t2-trk-stat-value">{progress.left.toFixed(1)}</div>
              <div className="t2-trk-stat-label">كم متبقية</div>
            </div>
          ) : null}
          <div className="t2-trk-stat">
            <div dir="ltr" className="t2-trk-stat-value">{formatMoney(ride.estimated_fare)}</div>
            <div className="t2-trk-stat-label">{currencyLabel(ride.currency)} تقديرياً</div>
          </div>
        </div>
        {/* المحطاتُ وعدّادُ الانتظار، والوقفةُ غيرُ المخطَّطة حين تنشأ — **مالٌ يُقال في لحظته** كما في الورقة القائمة */}
        <StopProgress ride={ride} />
        <PauseNotice ride={ride} />
        {/* **اقتراحُ المشاركة لمن طلبت الخدمة** لحظةَ تحرّك السيارة (المرحلة 10-ج) — كما هو اليوم */}
        {ride.status === "in_progress" && t.gendered && !t.shareHintClosed ? (
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
        {skinRow}
        {shareRow}
        {payMethod ? (
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
          <div className="t2-trk-title2">{arrived ? "الكبتن ينتظرك في نقطة الانطلاق" : "الكبتن في الطريق إليك"}</div>
          {vehicle ? (
            <div className="t2-trk-veh">
              {vehicle.make} {vehicle.model} · {vehicle.color}
            </div>
          ) : null}
        </div>
        {badges}
      </div>
      {driver ? (
        <div className="t2-trk-driver">
          <DriverAvatar rideId={ride.id} name={driver.name} className="t2-trk-avatar" />
          <div className="t2-trk-dmain">
            <div className="t2-trk-dname lg">{driver.name}</div>
            <div className="t2-trk-rating">
              <span className="t2-icon fill" aria-hidden="true">star</span>
              <span className="t2-trk-rating-value">{Number(driver.rating_avg).toFixed(2)}</span>
            </div>
          </div>
          {vehicle ? (
            <div dir="ltr" className="t2-trk-plate">
              <span className="t2-trk-plate-cc">{ride.country_code}</span>
              <span className="t2-trk-plate-no">{vehicle.plate_number}</span>
            </div>
          ) : null}
        </div>
      ) : null}
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
export function ApproachChipT2({ ride, driverPing }: { ride: Ride; driverPing: LatLng | null }) {
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
  return (
    <div className="t2 t2-trk-card">
      <div className="t2-trk-card-label">في الطريق إلى</div>
      <div className="t2-trk-card-dest">{ride.dropoff_address ?? "وجهتك"}</div>
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
