/** **C06 الطريقُ إلى الراكب · C07 أثناء الرحلة** (TAXO 2.0، الليليُّ المرسوم وحدَه — §٦١-د).
 *
 * **الطورُ وزرُّه وأسبابُ الإلغاء من بيتها** (`useActiveRide` في `components/ActiveRide`)، **والانتقالاتُ نداءاتُ الشاشة
 * القائمة نفسُها** يمرّرها `HomeT2` — فلا يقرّر هذا الملفُّ طوراً ولا يكتب حالاً. والتعليمةُ التاليةُ وما بعدها من خطوات
 * المسار المجمَّد (`lib/next-instruction`)، والمتبقّي من الخطّ نفسِه (`lib/eta`) — **أرقامُ وقتٍ ومسافةٍ تُقاس في الجهاز
 * من بياناتٍ حقيقية، لا مال** (§14).
 *
 * **وما رسمته اللوحةُ ولا مصدرَ له لا يُرسم مكانَه شيء** (§٦١-د/د):
 * - **سهمُ المناورة بُني** (§٦٢-ج/٤٢): الخطوةُ تحمل نوعَ مناورتها واتجاهَها بكلمة Mapbox (`maneuverIcon`) — **وخطوةٌ بلا كلمةٍ
 *   نصٌّ بلا سهم**، فسهمٌ يُخمَّن خطأً يكذب على من يقود.
 * - **«4 د» إلى نقطة الالتقاء**: الخطُّ المجمَّدُ خطُّ الرحلة نفسِها لا اقترابِ الكبتن — فالوقتُ المحسوبُ منه وقتٌ إلى الوجهة.
 *   **والمسافةُ مستقيمةٌ من موقعه إلى نقطة الالتقاء** (كمسافة العرض نفسِها)، والوقتُ لا يُرسم.
 * - **مسارُ الاقتراب المنقَّط** · **«اتصال» و«رسالة»** · **ملاحظةُ الراكب** · **«أمان»** · **«رمز الرحلة مطابق»** ·
 *   **«كاش»** · **اسمُ الراكب وتقييمُه**: لا بابَ لأيٍّ منها اليوم. **و«حتى الآن» بُني** (§٦٢-ج/٤٢) بمعناه في نظامٍ سعرُه مقدَّم:
 *   المقدَّرةُ وما تراكم من انتظارٍ ووقفات (`current_fare`) — **لا عدّادَ مسافة**.
 *
 * **وما في الشاشة القائمة ولم يُرسم — باقٍ بلغة اللوحة**: صورةُ الراكب ببلاغها · الأجرةُ المقدَّرة · حالُ المشاركة ·
 * المحطاتُ بعناوينها وعدّادُ انتظارها ورسمُه · الوقفةُ غيرُ المخطَّطة («نقطة توقف» · «استئناف») · «وصلتُ المحطة» ·
 * «افتح في الخرائط» أثناء الرحلة · أسبابُ الإلغاء ونصُّ «عدم التطابق».
 *
 * **ورحلةٌ لشخصٍ آخر** (§٦٣-ج/١، `ForOtherT2`) — بلا لوحة: «الراكب: الاسم» بزرِّ «اتصل بالراكب» (الاسمُ والرقمُ من القبول حتى
 * الانتهاء)، وسطرُ الدافع تحته.
 *
 * **والطرد** (§٦٣-ج/٤، `ParcelT2`) — بلا لوحة: «المستلم: الاسم» وعنوانُه بزرِّ «اتصل بالمستلم»، **ولا صورةَ للمرسل** (كرحلةٍ
 * لغيره)، وسطرُ «يدفع المستلمُ نقداً» حين يدفع هو، **و«ارفض الطرد» بتأكيده في طور «وصل» وحدَه**.
 *
 * **و«بالساعة»** (§٦٣-ج/٥، `HourlyT2`) — بلا لوحة: قبل البدء سطرُ الساعات وكيلومتراتها ومن أين يُدفع المحجوز، **وأثناءها عدّادُ
 * «الوقتُ الباقي / الساعات» والكيلومتراتُ المشمولة، وبطاقةُ «استلم … نقداً» حين يُدفع المحجوزُ نقداً**؛ والوجهةُ «يقولها الراكب» حين
 * لم تُختر. **ورفضُ البدء** (رصيدُ الراكب لا يغطّي المحجوز، ٤٠٩) يُقال بنصّ الخلفية تحت الزرّ كأيِّ خطأ فعل.
 */

import { Fragment, useEffect, useRef, useState, type CSSProperties, type PointerEvent as ReactPointerEvent } from "react";

import type { Coordinates, GenderPreference, Ride } from "@/api/types";
import { type CancelReason, useActiveRide, useElapsedMinutes } from "@/components/ActiveRide";
import { RiderAvatar } from "@/components/ride/RiderAvatar";
import { metersBetween, remainingMeters } from "@/lib/eta";
import { openIn } from "@/lib/external-maps";
import { useGuaranteeCancelCost } from "@/lib/guarantees";
import { digitsOnly } from "@/lib/phone";
import { currentStep, maneuverIcon, type NextInstruction, type RouteStep } from "@/lib/next-instruction";
import { digits } from "@/lib/utils";
import { PassengerRowT2, PayerNoteT2 } from "@/screens/t2/ForOtherT2";
import { HourlyCashCardT2, HourlyMeterT2, HourlyPlanT2, noDestination } from "@/screens/t2/HourlyT2";
import { RecipientRowT2, RefuseParcelButtonT2, RefuseParcelSheetT2 } from "@/screens/t2/ParcelT2";
import { Icon } from "@/taxo2";

interface Props {
  ride: Ride;
  currencyLabel: string;
  busy: boolean;
  /** خطأُ الفعل الأخير — **يُقال في الورقة** (الشاشةُ القائمةُ لا تعرضه أثناء الرحلة؛ §٢٩ في المسوّدة). */
  error: string | null;
  /** **ورمزُه** — خطأُ رمز الرحلة يُقال تحت خاناته كما رُسم (CW4). */
  errorCode?: string | null;
  instruction: NextInstruction | null;
  steps: RouteStep[];
  thresholdM: number;
  position: Coordinates | null;
  routeLine: number[][] | null;
  eta: number | null;
  /** **ما بقي من الاقتراب** (§٦٢-ج/١٠) — دقائقُه ومسافتُه على خطّه؛ و`null` حيث لا مسار (المفتاحُ مطفأ). */
  approachNow?: { minutes: number; km: number } | null;
  genderPreference: GenderPreference;
  /** الورقةُ تُقاس — فتنتهي الخريطةُ تحت حافّتها كما رُسمت (`HomeT2`). */
  sheetRef: (element: HTMLElement | null) => void;
  /** **و`code` رمزُ الرحلة** حين تطلبه (§٦٢-ج/٥) — يُرسل مع البدء. */
  onAdvance: (code?: string) => void;
  onCancel: (reason: CancelReason) => void;
  onPause: () => void;
  onResume: () => void;
  onArriveStop: (stopId: string) => void;
  onResumeStop: (stopId: string) => void;
  /** **«ارفض الطرد»** (§٦٣-ج/٤) — نداءُ `parcel-refuse` بعد تأكيده؛ وفي طور «وصل» على رحلة طردٍ وحدَه. */
  onRefuseParcel: () => void;
}

export function RideT2({
  ride,
  currencyLabel,
  busy,
  error,
  errorCode = null,
  instruction,
  steps,
  thresholdM,
  position,
  routeLine,
  eta,
  approachNow = null,
  genderPreference,
  sheetRef,
  onAdvance,
  onCancel,
  onPause,
  onResume,
  onArriveStop,
  onResumeStop,
  onRefuseParcel,
}: Props) {
  const { phase, riding, waiting, stopAction, picking, setPicking, reason, setReason, reasons, mapTarget } =
    useActiveRide(ride, genderPreference);
  // **الطرد** (§٦٣-ج/٤): من الصفّ لا من المفتاح — طردٌ قُبل يبقى طرداً ولو أُطفئ المفتاحُ بعده. **وصورةُ المرسل ليست وجهَ
  // أحدٍ في السيارة** — فلا تُعرض، كرحلةٍ لغيره
  const parcel = ride.ride_type === "parcel";
  const noRiderPhoto = ride.for_other || parcel;
  // **«ارفض الطرد» عند الاستلام وحدَه** — والخلفيةُ ترفض غيرَه ٤٠٩
  const canRefuse = parcel && ride.status === "arrived";
  const [refusing, setRefusing] = useState(false);
  // **ثمنُ الإلغاء قبل تأكيده** (§٦٤-د): رحلةٌ مضمونةٌ أكّدها ⇒ رسمُها يخرج من محفظته — يُسأل حين تُفتح ورقةُ الأسباب
  const cancelCost = useGuaranteeCancelCost(ride.id, ride.scheduled_for !== null, picking);
  useEffect(() => setRefusing(false), [ride.id, ride.status]);
  // **CW4 — رمزُ الرحلة** (§٦٢-ج/٥): عند الوصول لرحلةٍ تطلبه، **ولا بدءَ قبل خاناته الأربع**؛ ويُمحى إن تبدّلت الرحلة
  const needsCode = ride.status === "arrived" && ride.start_code_required;
  const [code, setCode] = useState("");
  useEffect(() => setCode(""), [ride.id]);
  const codeError = errorCode === "start_code_mismatch" || errorCode === "start_code_locked" ? error : null;

  // **ما بعد التعليمة التالية** (صفُّ «ثم…» في C06) — من الخطوات نفسِها: الخطوةُ التي يقف عليها، فالتاليةُ، فما بعدها.
  // **ولا يظهر إلا مع التعليمة**: شرطُ ظهورها وتأنّيه (`BACK_ON_ROUTE_STREAK`) هو شرطُه
  const here = instruction ? currentStep(steps, position, thresholdM) : null;
  const after = here ? steps[here.index + 2] : undefined;
  const then =
    here && after
      ? { text: after.text, meters: Math.round(steps[here.index + 1].distance_m), icon: maneuverIcon(after) }
      : null;

  const shared = Number(ride.share_discount_percent) > 0;
  const shareText = ride.share_group_id ? "رحلة مشتركة — راكبان" : "مشتركة — قد ينضم راكب ثانٍ";

  return (
    <>
      {instruction ? (
        <div className={`t2-rd-nav ${riding ? "trip" : "approach"}`}>
          <div className="t2-rd-nav-main">
            {/* **السهمُ كما رُسم**: كبيرٌ على الجمر في الطريق إلى الراكب (C06)، وفي مربّعٍ من الجمر أثناء الرحلة (C07) */}
            {instruction.icon ? (
              riding ? (
                <span className="t2-rd-nav-tile">
                  <Icon name={instruction.icon} />
                </span>
              ) : (
                <Icon name={instruction.icon} className="t2-rd-nav-ico" />
              )
            ) : null}
            <div className="t2-rd-nav-text">
              <div className="t2-rd-nav-dist">
                <span className="t2-rd-nav-num" dir="ltr">
                  {digits(String(instruction.meters))}
                </span>
                <span className="t2-rd-nav-unit">م</span>
              </div>
              <div className="t2-rd-nav-say">{instruction.text}</div>
            </div>
          </div>
          {!riding && then ? (
            <div className="t2-rd-nav-then">
              {then.icon ? <Icon name={then.icon} /> : null}
              <span>
                ثم {then.text} بعد {digits(String(then.meters))} م
              </span>
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="t2-rd-sheet" ref={sheetRef}>
        <div className="t2-rd-grab" />

        {riding ? (
          <TripHead ride={ride} currencyLabel={currencyLabel} position={position} routeLine={routeLine} eta={eta} />
        ) : (
          <div className="t2-rd-head">
            <ApproachHead ride={ride} position={position} title={phase.title} approachNow={approachNow} />
            {mapTarget ? (
              <button
                type="button"
                className="t2-rd-navbtn"
                onClick={() => openIn(mapTarget)}
                aria-label={mapTarget.cta}
                title={mapTarget.cta}
              >
                <Icon name="navigation" />
                فتح في الملاحة
              </button>
            ) : null}
          </div>
        )}

        {riding ? (
          <div className="t2-rd-chips">
            {mapTarget ? (
              <button
                type="button"
                className="t2-rd-chip"
                onClick={() => openIn(mapTarget)}
                aria-label={mapTarget.cta}
                title={mapTarget.cta}
              >
                <Icon name="navigation" />
                فتح في الملاحة
              </button>
            ) : null}
            {shared ? <span className="t2-rd-chip">{shareText}</span> : null}
            {/* **صورةُ الراكب بزرّها وبلاغها** في موضع شارة الراكب — **ولا اسمَ يصل الكبتن**: «راكب TAXO» كما في الشاشة القائمة */}
            <span className="t2-rd-chip avatar">
              {/* **رحلةٌ لشخصٍ آخر: صورةُ الطالب ليست وجهَ من سيركب** (§٦٣-ج/١) — فلا تُعرض، والراكبُ الفعليُّ في صفّه باسمه.
                  **ولا في الطرد** (§٦٣-ج/٤) — المستلمُ في صفّه */}
              {noRiderPhoto ? null : (
                <span className="t2-rd-avatar">
                  <RiderAvatar rideId={ride.id} />
                </span>
              )}
              {/* **في الطرد صاحبُ الطلب مرسلٌ لا راكب** (§٦٣-ج/٤) */}
              {ride.ride_type === "parcel" ? "مرسل الطرد" : "راكب TAXO"}
            </span>
          </div>
        ) : (
          <div className="t2-rd-rider">
            {/* **وفي رحلةٍ لشخصٍ آخر لا صورةَ للطالب** — ليس هو من يُلتقط (§٦٣-ج/١). **ولا في الطرد** (§٦٣-ج/٤) */}
            {noRiderPhoto ? null : (
              <span className="t2-rd-avatar">
                <RiderAvatar rideId={ride.id} />
              </span>
            )}
            <div className="t2-rd-rider-main">
              <div className="t2-rd-rider-name">{ride.ride_type === "parcel" ? "مرسل الطرد" : "راكب TAXO"}</div>
              <div className="t2-rd-rider-sub">{ride.pickup_address ?? "نقطة الانطلاق"}</div>
              {shared ? <div className="t2-rd-rider-share">{shareText}</div> : null}
            </div>
            {/* **الأجرةُ المقدَّرة** — كانت تحت اسم الراكب في الورقة القائمة، وتبقى في صفّه */}
            <div className="t2-rd-rider-fare">
              <span className="t2-rd-rider-fare-num" dir="ltr">
                {digits(ride.estimated_fare)}
              </span>{" "}
              <span className="t2-rd-fare-cur">{currencyLabel}</span>
            </div>
          </div>
        )}

        {/* **رحلةٌ لشخصٍ آخر** (§٦٣-ج/١): الراكبُ الفعليُّ بزرِّ الاتصال، وسطرُ الدافع — **و«لا تستلم شيئاً» مُبرَزة** */}
        {ride.for_other ? (
          <>
            <PassengerRowT2 ride={ride} />
            <PayerNoteT2 payer={ride.payer} />
          </>
        ) : null}

        {/* **الطرد** (§٦٣-ج/٤): المستلمُ وعنوانُه بزرِّ الاتصال، **وسطرُ الدافع حين يدفع المستلمُ وحدَه** — ومرسلُه الدافعُ كأيِّ راكب */}
        {parcel ? (
          <>
            <RecipientRowT2 ride={ride} />
            {ride.payer === "recipient_cash" ? <PayerNoteT2 payer={ride.payer} /> : null}
          </>
        ) : null}

        {/* **المشوارُ الثابت** (§٦٣-ج/٦) — دفعها الراكبُ مقدّماً مع اشتراكه: **«لا تستلم شيئاً» مُبرَزة** بسطر الدافع نفسِه، من
            الصفّ لا من المفتاح */}
        {ride.commute ? (
          <p className="t2-fo-payer warn">
            <Icon name="event_repeat" fill />
            <span>
              مدفوعة من اشتراك الراكب — <b>لا تستلم شيئاً</b>
            </span>
          </p>
        ) : null}

        {/* **بالساعة** (§٦٣-ج/٥) — من الصفّ لا من المفتاح: قبل البدء سطرُها، وأثناءها عدّادُها **وبطاقةُ نقد المحجوز** إن كان نقداً */}
        {ride.ride_type === "hourly" ? (
          riding ? (
            <>
              <HourlyMeterT2 ride={ride} />
              <HourlyCashCardT2 ride={ride} currencyLabel={currencyLabel} />
            </>
          ) : (
            <HourlyPlanT2 ride={ride} />
          )
        ) : null}

        <StopsT2 ride={ride} currencyLabel={currencyLabel} />
        <PauseT2 ride={ride} currencyLabel={currencyLabel} />

        {/* **«نقطة توقف» بعد بدء الرحلة وحدَها** (§5.10-ب) — كما في الورقة القائمة */}
        {riding ? (
          <button
            type="button"
            className={`t2-rd-btn ghost${ride.open_pause ? " ok" : ""}`}
            onClick={() => (ride.open_pause ? onResume() : onPause())}
            disabled={busy}
          >
            {ride.open_pause ? "استئناف" : "نقطة توقف"}
          </button>
        ) : null}

        {stopAction ? (
          <button type="button" className="t2-rd-btn" onClick={() => onArriveStop(stopAction.stop.id)} disabled={busy}>
            {stopAction.label}
          </button>
        ) : null}

        {/* **الإنهاءُ سحباً** كما رُسم (C07) — **ولمسةٌ عابرةٌ لا تُنهي رحلة**. والاستئنافُ من محطةٍ والطوران الأوّلان أزرار */}
        {needsCode ? <RideCodeT2 code={code} onChange={setCode} error={codeError} /> : null}

        {riding && !waiting ? (
          <SwipeToFinish label="اسحب لإنهاء الرحلة" busy={busy} onDone={() => onAdvance()} />
        ) : (
          <button
            type="button"
            className={`t2-rd-btn${stopAction ? " ghost" : ""}${needsCode ? " women" : ""}`}
            onClick={() => (waiting ? onResumeStop(waiting.id) : onAdvance(needsCode ? code : undefined))}
            disabled={busy || (needsCode && code.length < 4)}
          >
            {phase.action}
          </button>
        )}

        {/* **«ارفض الطرد»** (§٦٣-ج/٤) — ثانويٌّ تحت «بدء الرحلة»، وتأكيدُه ورقةٌ تقول أثرَه */}
        {canRefuse ? <RefuseParcelButtonT2 busy={busy} onOpen={() => setRefusing(true)} /> : null}

        {error && !codeError ? (
          <p className="t2-note danger t2-rd-error">
            <Icon name="error" fill />
            {error}
          </p>
        ) : null}

        {/* **لا إلغاء بعد بدء الرحلة** — الإنهاءُ مخرجُه الوحيد (SPEC القسم 5)، كما في الورقة القائمة */}
        {riding ? null : (
          <button type="button" className="t2-rd-cancel" onClick={() => setPicking(true)} disabled={busy}>
            إلغاء الرحلة
          </button>
        )}
      </div>

      {/* **ورقةُ أسباب الإلغاء** — الأسبابُ وشرطُ «عدم التطابق» ونصُّه وتراجعُه من الورقة القائمة */}
      {picking ? (
        <div className="t2-rd-cx-shade">
          <div className="t2-rd-cx-sheet">
            <div className="t2-rd-grab" />
            <h2 className="t2-rd-cx-title">سبب الإلغاء</h2>
            <div className="t2-rd-cx-list">
              {reasons.map((option) => (
                <button
                  key={option.label}
                  type="button"
                  className={`t2-rd-cx-opt${reason?.label === option.label ? " on" : ""}`}
                  onClick={() => setReason(option)}
                >
                  <span className="t2-rd-cx-radio" />
                  {option.label}
                </button>
              ))}
            </div>
            {cancelCost?.cancel_penalty ? (
              <p className="t2-rd-cx-note warn">
                رحلةٌ مضمونةٌ أكّدتَها — إلغاؤها يأخذ من محفظتك حتى{" "}
                <b dir="ltr">{digits(cancelCost.cancel_penalty)}</b> {currencyLabel} للراكب، ويُنقص تقييمَك ويُسجَّل عليك إنذار.
                وبلوغُ {digits(String(cancelCost.ban_threshold))} من الاعتذارات خلال {digits(String(cancelCost.ban_days))} يوماً
                يحجبك عن الحجوزات المضمونة.
              </p>
            ) : null}
            {reason?.code === "gender_mismatch" ? (
              <p className="t2-rd-cx-note">
                لن تُحتسب عليكِ رسوم إلغاء. ويُسجَّل بلاغٌ على حساب الراكب، وتكرارُ البلاغات يوسم الحساب للمراجعة.
              </p>
            ) : null}
            <button
              type="button"
              className="t2-rd-cx-confirm"
              disabled={busy || reason === null}
              onClick={() => {
                setPicking(false);
                onCancel(reason!);
              }}
            >
              تأكيد الإلغاء
            </button>
            <button type="button" className="t2-rd-cancel" onClick={() => setPicking(false)}>
              تراجع
            </button>
          </div>
        </div>
      ) : null}

      {refusing && canRefuse ? (
        <RefuseParcelSheetT2
          busy={busy}
          onConfirm={() => {
            setRefusing(false);
            onRefuseParcel();
          }}
          onClose={() => setRefusing(false)}
        />
      ) : null}
    </>
  );
}

/** رأسُ الطريق إلى الراكب — **المسافةُ المستقيمةُ من موقعه إلى نقطة الالتقاء** (كمسافة العرض)، أو عنوانُ الطور حين لا
 *  موقعَ ولا معنى للمسافة («بانتظار الراكب» وهو عندها). */
function ApproachHead({
  ride,
  position,
  title,
  approachNow,
}: {
  ride: Ride;
  position: Coordinates | null;
  title: string;
  approachNow: { minutes: number; km: number } | null;
}) {
  const km = ride.status === "accepted" && position ? metersBetween(position, ride.pickup) / 1000 : null;
  // **«4 د · 1.2 كم» كما رُسم في C06** حين يُعرف الاقتراب (§٦٢-ج/١٠) — المسافةُ على الطريق لا مستقيمة
  if (ride.status === "accepted" && approachNow) {
    return (
      <div className="t2-rd-head-main">
        <div className="t2-rd-big">
          <span className="t2-rd-big-num" dir="ltr">
            {digits(String(approachNow.minutes))}
          </span>
          <span className="t2-rd-big-unit">د</span>
          <span className="t2-rd-big-unit">· {digits(approachNow.km.toFixed(1))} كم</span>
        </div>
        <div className="t2-rd-caption">إلى نقطة الالتقاء</div>
      </div>
    );
  }
  return (
    <div className="t2-rd-head-main">
      {km !== null ? (
        <div className="t2-rd-big">
          <span className="t2-rd-big-num" dir="ltr">
            {digits(km.toFixed(1))}
          </span>
          <span className="t2-rd-big-unit">كم</span>
        </div>
      ) : (
        <div className="t2-rd-big-title">{title}</div>
      )}
      {ride.status === "accepted" ? <div className="t2-rd-caption">إلى نقطة الالتقاء</div> : null}
    </div>
  );
}

/** رأسُ الرحلة — الوجهةُ وما بقي إليها (الوقتُ حين يُقاس، والمسافةُ من الخطّ المجمَّد)، **وعدّادُ الأجرة** (§٦٢-ج/٤٢):
 *  `current_fare` كما يجمعه الخادم. **واسمُه يقول ما فيه**: «تقديرياً» ما لم يتراكم شيء (هو المقدَّرةُ نفسُها)، و«حتى الآن» حين
 *  دخله انتظارٌ أو وقفة — فلا يُقرأ عدّادَ مسافةٍ في نظامٍ سعرُه مقدَّم (القسم 5.7). */
function TripHead({
  ride,
  currencyLabel,
  position,
  routeLine,
  eta,
}: {
  ride: Ride;
  currencyLabel: string;
  position: Coordinates | null;
  routeLine: number[][] | null;
  eta: number | null;
}) {
  const meters = remainingMeters(routeLine, position);
  const left =
    meters === null
      ? null
      : `${eta !== null ? `${digits(String(eta))} د · ` : ""}${digits((meters / 1000).toFixed(1))} كم متبقية`;
  return (
    <div className="t2-rd-head trip">
      <div className="t2-rd-head-main">
        <div className="t2-rd-caption">إلى</div>
        {/* **ساعاتٌ بلا وجهة** (§٦٣-ج/٥) — الطلبُ أرسل نقطةَ الانطلاق وجهةً، **والوجهاتُ يقولها الراكبُ في السيارة** */}
        <div className="t2-rd-to">
          {ride.ride_type === "hourly" && noDestination(ride) ? "الوجهاتُ يقولها الراكب" : (ride.dropoff_address ?? "الوجهة")}
        </div>
        {left ? <div className="t2-rd-left">{left}</div> : null}
      </div>
      <div className="t2-rd-fare">
        <div className="t2-rd-fare-row">
          <span className="t2-rd-fare-num" dir="ltr">
            {digits(ride.current_fare)}
          </span>
          <span className="t2-rd-fare-cur">{currencyLabel}</span>
        </div>
        <div className="t2-rd-fare-note">
          {Number(ride.waiting_charge) > 0 || Number(ride.pause_charge) > 0 ? "حتى الآن" : "تقديرياً"}
        </div>
      </div>
    </div>
  );
}

/** المحطاتُ بعناوينها وحالها، وعدّادُ انتظار المحطة الحالية ورسمُه — **نصوصُ `StopStrip` وشروطُه في الورقة القائمة**،
 *  **والعنوانُ والرقمُ معاً**: الشريطُ القائمُ يقول «محطة ٢» وخطُّ الطريق يقول عنوانَها. */
function StopsT2({ ride, currencyLabel }: { ride: Ride; currencyLabel: string }) {
  const waiting = ride.stops.find((stop) => stop.arrived_at !== null && stop.resumed_at === null);
  // **قبل الخروج المبكر**: خطّافٌ بعد `return` يكسر ترتيبَ الخطّافات
  const waitedMinutes = useElapsedMinutes(waiting?.arrived_at ?? null);
  if (ride.stops.length === 0) return null;
  return (
    <div className="t2-rd-strip">
      <div className="t2-rd-stops">
        {ride.stops.map((stop) => {
          const done = stop.resumed_at !== null;
          const at = stop.arrived_at !== null && stop.resumed_at === null;
          return (
            <Fragment key={stop.id}>
              <span className={`t2-rd-stop-dot${done ? " done" : at ? " here" : ""}`} />
              <span className={`t2-rd-stop-name${done ? " done" : ""}`}>
                {stop.address ?? `محطة ${digits(String(stop.sequence))}`}
              </span>
              <span className={`t2-rd-stop-tag${at ? " here" : ""}`}>محطة {digits(String(stop.sequence))}</span>
            </Fragment>
          );
        })}
      </div>
      {waiting ? (
        <div className="t2-rd-wait">
          <span>انتظارٌ {digits(String(waitedMinutes))} دقيقة</span>
          <span>
            {digits(ride.waiting_charge)} {currencyLabel}
          </span>
        </div>
      ) : null}
      {waiting?.over_max_wait ? (
        <p className="t2-rd-strip-warn">تجاوز الانتظارُ السقف — يمكنك إنهاء الرحلة عند هذه المحطة بدل الاستئناف.</p>
      ) : null}
    </div>
  );
}

/** الوقفةُ غيرُ المخطَّطة (§5.10-ب) — **العدّادُ يمشي محلياً والمبلغُ من الخلفية** (`PauseStrip` في الورقة القائمة بنصّها). */
function PauseT2({ ride, currencyLabel }: { ride: Ride; currencyLabel: string }) {
  const pause = ride.open_pause;
  const minutes = useElapsedMinutes(pause?.started_at ?? null);
  if (!pause) return null;
  const free = pause.free_minutes;
  const billing = minutes >= free;
  return (
    <div className={`t2-rd-strip${pause.over_max ? " warn" : ""}`}>
      <div className="t2-rd-strip-row">
        <span className="t2-rd-strip-label">{pause.kind === "arrival" ? "بانتظار الراكب" : "وقفة"}</span>
        <span className="t2-rd-strip-min">{digits(String(minutes))} دقيقة</span>
        <span className="t2-rd-strip-end">
          {billing ? `${digits(ride.pause_charge)} ${currencyLabel}` : `مهلة ${digits(String(free))} دقائق`}
        </span>
      </div>
      {pause.over_max ? (
        <p className="t2-rd-strip-warn">تجاوز الانتظارُ حدَّه — لك أن تستأنف أو تُنهي، والقرارُ قرارك.</p>
      ) : null}
    </div>
  );
}

/** **«اسحب لإنهاء الرحلة»** (C07): المقبضُ يُسحب من البداية إلى النهاية، **وما دون ٨٥٪ يعود** — فلمسةٌ عابرةٌ أو سحبةٌ قصيرةٌ
 *  لا تُنهي رحلةً وراكبُها في السيارة. **والإنهاءُ نفسُه نداءُ الشاشة القائمة** (`onDone` ⇐ `advance`). ومن لا يسحب (لوحةُ
 *  مفاتيح أو قارئُ شاشة) يُفعّله بـ«إدخال» — فعلٌ مقصودٌ لا لمسة. */
/** **CW4 — رمزُ الرحلة** (§٦٢-ج/٥): «اطلبي من الراكبة رمز الرحلة» وأربعُ خاناتٍ كما رُسمت — **حقلٌ واحدٌ خلفها** (لوحةُ أرقامٍ ولصقٌ
 *  ورمزٌ يُقرأ صوتاً)، **والخاناتُ العربيةُ تُقرأ لاتينيةً** (`digitsOnly`): لوحةُ مفاتيحَ عربيةٌ لا تُسقط رمزاً صحيحاً. والخطأُ تحتها بنصّ
 *  الخلفية — رسالةُ CW4 بحرفها. */
function RideCodeT2({ code, onChange, error }: { code: string; onChange: (next: string) => void; error: string | null }) {
  return (
    <div className={error ? "t2-rd-code wrong" : "t2-rd-code"}>
      <div className="t2-rd-code-title">اطلبي من الراكبة رمز الرحلة</div>
      <div className="t2-rd-code-sub">لا تبدأ الرحلة قبل أن يطابق الرمز.</div>
      <div className="t2-rd-code-boxes" dir="ltr">
        {[0, 1, 2, 3].map((index) => (
          <span key={index} className={index === code.length ? "t2-rd-code-box on" : "t2-rd-code-box"} aria-hidden="true">
            {code[index] ?? ""}
          </span>
        ))}
        <input
          className="t2-rd-code-input"
          inputMode="numeric"
          autoComplete="one-time-code"
          aria-label="رمز الرحلة"
          value={code}
          onChange={(event) => onChange(digitsOnly(event.target.value).slice(0, 4))}
        />
      </div>
      {error ? (
        <p className="t2-rd-code-error" role="alert">
          <Icon name="error" fill />
          {error}
        </p>
      ) : null}
    </div>
  );
}

function SwipeToFinish({ label, busy, onDone }: { label: string; busy: boolean; onDone: () => void }) {
  const track = useRef<HTMLDivElement | null>(null);
  const start = useRef<number | null>(null);
  const travel = useRef(0);
  const [drag, setDrag] = useState(0);
  const [dragging, setDragging] = useState(false);

  // **يعود المقبضُ حين ينتهي الطلب** — نجح فتبدّلت الورقة، أو سقط فيُسحب ثانيةً
  useEffect(() => {
    if (!busy) {
      travel.current = 0;
      setDrag(0);
    }
  }, [busy]);

  const room = () => (track.current ? track.current.clientWidth - 54 - 12 : 0);

  const down = (event: ReactPointerEvent<HTMLButtonElement>) => {
    if (busy) return;
    start.current = event.clientX;
    setDragging(true);
    // **الإصبعُ يبقى للمقبض ولو خرج عنه** — وبعضُ الأغلفة ترفض الالتقاط، فيُكمَل بلا التقاطٍ بدل أن يسقط المقبض
    try {
      event.currentTarget.setPointerCapture(event.pointerId);
    } catch {
      // بلا التقاط: الحركةُ تُقرأ ما دام فوق المقبض
    }
  };
  const move = (event: ReactPointerEvent<HTMLButtonElement>) => {
    if (start.current === null) return;
    // **من البداية إلى النهاية في العربية**: البدايةُ يمينٌ والسحبُ يساراً
    travel.current = Math.min(room(), Math.max(0, start.current - event.clientX));
    setDrag(travel.current);
  };
  const up = () => {
    if (start.current === null) return;
    start.current = null;
    setDragging(false);
    if (travel.current >= room() * 0.85) {
      travel.current = room();
      setDrag(travel.current);
      onDone();
    } else {
      travel.current = 0;
      setDrag(0);
    }
  };

  return (
    <div
      ref={track}
      className={`t2-rd-swipe${dragging ? " dragging" : ""}${busy ? " busy" : ""}`}
      style={{ "--drag": `${drag}px` } as CSSProperties}
    >
      <span className="t2-rd-swipe-label" aria-hidden="true">
        <Icon name="chevron_left" />
        {label}
        <Icon name="chevron_left" />
      </span>
      <button
        type="button"
        className="t2-rd-swipe-knob"
        aria-label={label}
        disabled={busy}
        onPointerDown={down}
        onPointerMove={move}
        onPointerUp={up}
        onPointerCancel={up}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onDone();
          }
        }}
      >
        <Icon name="arrow_back" />
      </button>
    </div>
  );
}
