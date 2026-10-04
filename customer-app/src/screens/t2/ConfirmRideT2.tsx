/** طلبُ رحلة — TAXO 2.0 «R06» (Claude Design «Rider»)، **في المظهر النهاريّ المرسوم وحدَه**.
 *
 * **وجهٌ ثانٍ لورقة التأكيد لا ورقةٌ ثانية**: المنطقُ كلُّه من `useConfirmRide` — التقديرُ من الخلفية بكلِّ تبديل،
 * والكوبونُ يُتحقَّق منه هناك ويُعاد إن تغيّر التقدير، والمشاركةُ بموافقتيها، وطريقةُ الدفع تفضيلٌ محلّيّ، والحجزُ بموعده،
 * **وما يُرسل مع الطلب هو هو**. فلا يفترق الوجهان في طلبٍ ولا في رقمٍ ولا في شرط.
 *
 * **وسعرٌ على كلِّ فئةٍ كما رُسم** (§٦١-د: المطابقةُ التامّة) — **من الخلفية لا من الواجهة**: المختارةُ من تقدير الخطّاف
 * كما هو، **وكلُّ فئةٍ غيرها بنداء التقدير نفسِه** (`useCategoryFares`) — نداءٌ ومسارٌ من Mapbox لكلِّ فئةٍ مع كلِّ مسار،
 * **وهو كلفةُ تشغيلٍ على المالك قِيست وقُرِّرت** لا مالٌ يمسّ أحداً. وفئةٌ فشل تقديرُها لا رقمَ عليها — لا رقمَ يُخمَّن.
 *
 * **وما رسمته اللوحةُ ولم يُبنَ — بعلّته** (`TAXO2-DESIGN-CORRECTIONS.md` §٢٣):
 * - **«عائلي»**: لا فئةَ بها (`economy` · `comfort`). **و«نسائية» فئةً**: الخدمةُ النسائيةُ تفضيلٌ لا فئة — فبقي منتقي
 *   التفضيل بخياراته الثلاثة لمن عُرضت عليها الخدمة، كما هو اليوم (§61).
 * - **«4 ركاب · يصل خلال 3 د»**: لا مهلةَ قبل نقطة الالتقاط ولا عددَ مقاعد في الفئة — فالسطرُ وصفُ الفئة القائم.
 *
 * **وما في الورقة القائمة ولم يُرسم يبقى بلغة اللوحة**: المحطاتُ وترتيبُها · ملاحظةُ رسم الانتظار · المشاركة · رصيدُ
 * المحفظة · الحجز · الحدُّ الأدنى للأجرة · سطرُ «السعر النهائي قد يتغيّر». **و«رجوع» صار زرَّ السهم فوق الخريطة** كما رُسم.
 * **ومقدارُ الخصم وإزالةُ الكوبون** خلف لمسة «مطبّق» — الشارةُ كما رُسمت، والفعلُ باقٍ.
 */

import { useEffect, useState } from "react";

import { estimateRide } from "@/api/endpoints";
import type { RideEstimate, VehicleCategory } from "@/api/types";
import { ErrorNote } from "@/components/ui/Feedback";
import { StopsEditor } from "@/components/home/StopsEditor";
import { PREFERENCE_NOTE, useConfirmRide, waitingNote, type ConfirmRideProps } from "@/components/home/useConfirmRide";
import { PAY_ICON_T2, PaymentPicker } from "@/components/payment/PaymentPicker";
import { earliest, latest, localInputValue } from "@/lib/bookings";
import { PAYMENT_METHOD_LABEL, VEHICLE_HINT, VEHICLE_LABEL } from "@/lib/labels";
import { MAX_STOPS } from "@/lib/multistop";
import { currencyLabel, formatDistance, formatDuration, formatMoney } from "@/lib/utils";

import { SheetT2 } from "./SheetT2";
import "@/taxo2";
import "./t2.css";

/** رمزُ كلِّ فئةٍ كما رسمته اللوحة. */
const CATEGORY_ICON: Record<string, string> = { economy: "local_taxi", comfort: "directions_car" };

/** «14 د» كما رسمتها اللوحة — والساعةُ فما فوقها بصيغة التطبيق نفسِها. */
function shortDuration(minutes: string | number) {
  const value = Math.round(Number(minutes));
  return Number.isFinite(value) && value < 60 ? `${value} د` : formatDuration(minutes);
}

/** **تقديرُ كلِّ فئةٍ غيرِ المختارة** — بالحمولة نفسِها التي يرسلها الخطّاف، **ويُعاد مع كلِّ مسارٍ أو محطة**.
 *
 * والمختارةُ لا تُسأل هنا: الخطّافُ يسألها كما يسألها اليوم (ومعه الكوبونُ والمشاركة) — فلا نداءَ مكرّر. ومن بدّل
 * الفئةَ سأل الخطّافُ الجديدةَ كما يسأل اليوم، **وبقي رقمُ القديمة ممّا سُئل قبل**. */
function useCategoryFares(
  props: ConfirmRideProps,
  selected: VehicleCategory,
  selectedEstimate: RideEstimate | null,
): Partial<Record<VehicleCategory, RideEstimate>> {
  const { pickup, dropoff, stops, categories } = props;
  const [fares, setFares] = useState<Partial<Record<VehicleCategory, RideEstimate>>>({});
  // **مفتاحٌ نصّيٌّ للفئات** لا المصفوفةُ نفسُها: بديلُها الافتراضيُّ (`["economy"]`) مصفوفةٌ جديدةٌ كلَّ رسم فتدور الحلقة
  const key = categories.join(",");

  useEffect(() => {
    let cancelled = false;
    setFares({});
    for (const category of key.split(",") as VehicleCategory[]) {
      if (category === selected) continue;
      estimateRide({
        pickup,
        dropoff,
        vehicle_category: category,
        stops: stops.map((stop) => ({ lat: stop.lat, lng: stop.lng })),
      })
        .then((value) => !cancelled && setFares((previous) => ({ ...previous, [category]: value })))
        .catch(() => undefined);
    }
    return () => {
      cancelled = true;
    };
    // **المختارةُ ليست في التبعيات عمداً**: تبديلُ الفئة لا يغيّر سعرَ غيرها — والخطّافُ يسأل الجديدة
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pickup, dropoff, stops, key]);

  // تقديرُ الخطّاف للمختارة يُحفظ رقماً لها حين تصير غيرَ مختارة
  useEffect(() => {
    if (selectedEstimate && selectedEstimate.vehicle_category === selected) {
      setFares((previous) => ({ ...previous, [selected]: selectedEstimate }));
    }
  }, [selected, selectedEstimate]);

  return fares;
}

/** **المبلغُ بخطّين كما رُسم** — الرقمُ بخطِّ الأرقام والعملةُ صغيرةً خافتة. */
function Fare({ estimate }: { estimate: RideEstimate }) {
  return (
    <span className="t2-cat-price">
      <span dir="ltr" className="t2-cat-amount">{formatMoney(estimate.estimated_fare)}</span>
      <span className="t2-cat-cur">{currencyLabel(estimate.currency)}</span>
    </span>
  );
}

const PREFERENCES = [
  { value: "female", label: "إناث" },
  { value: "male", label: "ذكور" },
  { value: "any", label: "الجميع" },
] as const;

export function ConfirmRideT2(props: ConfirmRideProps) {
  const {
    pickupAddress,
    dropoffAddress,
    categories,
    onEditDestination,
    requesting,
    requestError,
    stops,
    onStopsChange,
    onAddStop,
    blockedByPreference,
    onClearPreference,
    countryConfig,
  } = props;
  const c = useConfirmRide(props);
  const currency = c.estimate?.currency ?? countryConfig?.currency;
  const fares = useCategoryFares(props, c.category, c.loading ? null : c.estimate);
  // **تفصيلُ الكوبون خلف لمسة «مطبّق»**: مقدارُ الخصم وإزالتُه — الشارةُ كما رُسمت، والفعلُ باقٍ
  const [promoOpen, setPromoOpen] = useState(false);

  return (
    <SheetT2
      footer={
        <>
          {/* **سطرُ الخطأ فوق الزرِّ مباشرةً** — بشرط الورقة القائمة نفسِه */}
          {blockedByPreference ? null : <ErrorNote message={c.error ?? requestError} className="t2-error" />}
          <button
            type="button"
            className="t2-cta"
            disabled={!c.estimate || c.loading || requesting}
            aria-busy={requesting}
            onClick={() =>
              props.onRequest(c.category, c.preference, c.applied?.code, {
                share: c.shareReady,
                shareGenderConfirmed: c.shareReady && c.shareGuarded,
              })
            }
          >
            <span>{requesting ? "نرسل طلبك…" : `اطلب ${VEHICLE_LABEL[c.category]}`}</span>
            {/* **الرقمُ آخرُ ما تقع عليه العين** — ويختفي ما دام يُحسب: رقمٌ قديمٌ على زرِّ التزامٍ أسوأ من لا رقم */}
            {c.shownFare && !c.loading ? (
              <span className="t2-cta-price">{formatMoney(c.shownFare, currency)}</span>
            ) : null}
          </button>
        </>
      }
    >
      {/* المسار: «من» و«إلى» بنقطتيهما، و«+» محطةٌ في الطريق */}
      <div className="t2-route">
        <span className="t2-route-from" aria-hidden="true" />
        <div className="t2-route-text">
          <div className="t2-route-label">من</div>
          {/* **وموقعُ الجهاز بعنوانه من Mapbox** كما رُسم («شارع الرينبو، جبل عمّان») — للعرض وحدَه */}
          <div className="t2-route-value">{pickupAddress ?? props.pickupLine ?? "نقطة الانطلاق المحددة"}</div>
        </div>
        <span />
        <span className="t2-route-join" aria-hidden="true" />
        <span />
        <span />
        <span className="t2-route-to" aria-hidden="true" />
        <button type="button" className="t2-route-text t2-route-edit" onClick={onEditDestination}>
          <span className="t2-route-label">إلى</span>
          <span className="t2-route-value">{dropoffAddress ?? "الوجهة المحددة"}</span>
        </button>
        {c.multiStop && stops.length < MAX_STOPS ? (
          <button type="button" className="t2-route-add" onClick={onAddStop} aria-label="إضافة محطة">
            <span className="t2-icon" aria-hidden="true">add</span>
          </button>
        ) : (
          <span />
        )}
      </div>

      {c.multiStop ? (
        <StopsEditor
          stops={stops}
          onChange={onStopsChange}
          onAdd={onAddStop}
          waitingNote={waitingNote(c.estimate)}
          variant="t2"
        />
      ) : null}

      <div className="t2-pick-head">
        <span className="t2-pick-title">اختر الفئة</span>
        {c.estimate && !c.loading ? (
          <span className="t2-pick-meta">
            {formatDistance(c.estimate.distance_km)} · {shortDuration(c.estimate.duration_min)}
          </span>
        ) : null}
      </div>
      <div className="t2-cats" role="radiogroup" aria-label="الفئة">
        {categories.map((option) => {
          const on = option === c.category;
          return (
            <button
              key={option}
              type="button"
              role="radio"
              aria-checked={on}
              className={on ? "t2-cat on" : "t2-cat"}
              onClick={() => c.setCategory(option)}
            >
              <span className="t2-cat-icon">
                <span className="t2-icon" aria-hidden="true">{CATEGORY_ICON[option] ?? "local_taxi"}</span>
              </span>
              <span className="t2-cat-main">
                <span className="t2-cat-name">{VEHICLE_LABEL[option]}</span>
                <span className="t2-cat-hint">{VEHICLE_HINT[option]}</span>
              </span>
              {/* **السعرُ على كلِّ فئةٍ كما رُسم** — المختارةُ من تقدير الخطّاف كما هو (و«نحسب…» ما دام يُحسب)، وغيرُها
                  من تقديرها (`useCategoryFares`)، **والمخصومُ على الزرّ** */}
              {on ? (
                c.loading ? (
                  <span className="t2-cat-wait">نحسب…</span>
                ) : c.estimate ? (
                  <Fare estimate={c.estimate} />
                ) : null
              ) : fares[option] ? (
                <Fare estimate={fares[option]!} />
              ) : null}
            </button>
          );
        })}
      </div>
      {c.estimate?.minimum_fare_applied && !c.loading ? (
        <p className="t2-sheet-fine">طُبِّق الحد الأدنى للأجرة</p>
      ) : null}

      {/* **تفضيلُ الكبتن** — لمن عُرضت عليها الخدمةُ وحدَها، بقرار `lib/women.ts` (§61: كما هو اليوم) */}
      {c.women.available ? (
        <div className="t2-pref">
          <div className="t2-pref-title">تفضيل الكبتن</div>
          <div className="t2-seg" role="radiogroup" aria-label="تفضيل الكبتن">
            {PREFERENCES.map((option) => (
              <button
                key={option.value}
                type="button"
                role="radio"
                aria-checked={option.value === c.preference}
                className={option.value === c.preference ? "t2-seg-opt on" : "t2-seg-opt"}
                onClick={() => c.setPreference(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
          <p className="t2-note">
            {c.preference === "any" ? null : (
              <span className="t2-icon" aria-hidden="true">schedule</span>
            )}
            {PREFERENCE_NOTE[c.preference]}
          </p>
        </div>
      ) : null}

      {/* **الدفعُ والكوبونُ صفٌّ واحد** كما رُسم — وكلٌّ بشرطه: لا منتقٍ بقناةٍ وحيدة، ولا كوبونَ حيث المفتاحُ مطفأ */}
      {(c.payMethod && c.channels.length > 1) || c.promoEnabled ? (
        <div className="t2-payrow">
          {c.payMethod && c.channels.length > 1 ? (
            <button type="button" className="t2-payrow-pay" onClick={() => c.setPickingPay(true)}>
              <span className="t2-icon" aria-hidden="true">{PAY_ICON_T2[c.payMethod.method]}</span>
              {PAYMENT_METHOD_LABEL[c.payMethod.method]}
              <span className="t2-icon t2-payrow-more" aria-hidden="true">expand_more</span>
            </button>
          ) : null}
          {c.payMethod && c.channels.length > 1 && c.promoEnabled ? <span className="t2-payrow-sep" /> : null}
          {c.promoEnabled ? (
            c.applied ? (
              <button
                type="button"
                className="t2-payrow-promo"
                aria-expanded={promoOpen}
                onClick={() => setPromoOpen((open) => !open)}
              >
                <span className="t2-icon" aria-hidden="true">sell</span>
                <span dir="ltr">{c.applied.code}</span> مطبّق
              </button>
            ) : c.couponOpen ? null : (
              <button type="button" className="t2-payrow-coupon" onClick={() => c.setCouponOpen(true)}>
                <span className="t2-icon" aria-hidden="true">sell</span>
                عندي كوبون خصم
              </button>
            )
          ) : null}
        </div>
      ) : null}

      {/* **تفصيلُ الكوبون المطبَّق** — مقدارُه كما ردّته الخلفية، وإزالتُه كما كانت (`أزل الكوبون`) */}
      {c.promoEnabled && c.applied && promoOpen ? (
        <div className="t2-promo-detail">
          <span>
            خصم {formatMoney(c.applied.discount, c.applied.currency)}
          </span>
          <button
            type="button"
            className="t2-promo-remove"
            onClick={() => {
              c.setApplied(null);
              c.setCouponInput("");
              c.setCouponError(null);
              setPromoOpen(false);
            }}
          >
            أزل الكوبون
          </button>
        </div>
      ) : null}

      {c.promoEnabled && !c.applied && c.couponOpen ? (
        <div className="t2-coupon">
          <label className="t2-coupon-label" htmlFor="promo">
            رمز الكوبون
          </label>
          <div className="t2-coupon-row">
            <input
              id="promo"
              dir="ltr"
              autoFocus
              maxLength={32}
              placeholder="WELCOME"
              className="t2-input t2-coupon-input"
              value={c.couponInput}
              onChange={(event) => c.setCouponInput(event.target.value)}
            />
            <button
              type="button"
              className="t2-button primary t2-coupon-apply"
              disabled={c.couponInput.trim().length < 2 || !c.estimate || c.checking}
              onClick={() => void c.apply()}
            >
              {c.checking ? "…" : "تطبيق"}
            </button>
          </div>
          <ErrorNote message={c.couponError} className="t2-error" />
        </div>
      ) : null}

      {/* **المشاركة** (12-ي) بموافقتيها — وتُخفى ما دام لا سعرَ لها */}
      {c.shareOffered ? (
        <div className="t2-share">
          <label className="t2-share-row">
            <input
              type="checkbox"
              className="t2-check"
              checked={c.share}
              onChange={(event) => {
                c.setShare(event.target.checked);
                if (!event.target.checked) c.setShareGendered(false);
              }}
            />
            <span className="t2-share-main">
              <span className="t2-share-title">
                <span className="t2-icon" aria-hidden="true">group</span>
                شارك الرحلة ووفّر
              </span>
              <span className="t2-share-body">
                قد ينضم راكبٌ آخر في طريقك، وتدفع {formatMoney(c.estimate!.share_fare!, c.estimate?.currency)} بدل{" "}
                {formatMoney(c.estimate!.estimated_fare, c.estimate?.currency)} — وتصل متأخراً قليلاً. والسعرُ لك حتى لو لم
                يوجد شريك.
              </span>
            </span>
          </label>
          {c.share && c.shareGuarded ? (
            <label className="t2-share-row t2-share-guard">
              <input
                type="checkbox"
                className="t2-check"
                checked={c.shareGendered}
                onChange={(event) => c.setShareGendered(event.target.checked)}
              />
              <span className="t2-share-body">
                طلبكِ يحدّد جنس الكبتن. أوافق على أن تشاركني الرحلةَ <b>راكبةٌ أخرى</b> — ولن يُضاف راكبٌ من غير ذلك.
              </span>
            </label>
          ) : null}
        </div>
      ) : null}

      {blockedByPreference ? (
        <div className="t2-callout warn" role="status">
          <span className="t2-icon fill" aria-hidden="true">error</span>
          <div className="t2-callout-main">
            <div className="t2-callout-title">خدمة الكبتنات غير مفعّلة في بلدك الآن</div>
            <p className="t2-callout-body">
              في حسابك تفضيلٌ محفوظ بطلب كبتنة، ولا يمكن تنفيذه هنا — فتُرفض كل رحلة. أعِد التفضيل إلى «أي كبتن» لتتمكّني من
              الطلب، ويبقى بإمكانك تغييره متى عادت الخدمة.
            </p>
            <button type="button" className="t2-button secondary t2-callout-action" onClick={onClearPreference}>
              اقبل أي كبتن
            </button>
          </div>
        </div>
      ) : null}

      {c.walletNote ? <p className="t2-note warn">{c.walletNote}</p> : null}

      {/* **حدّد موعداً** (12-ط) — زرٌّ ثانويٌّ لا مساوٍ للأول، ويُخفى حيث المفتاح مطفأ */}
      {c.scheduled ? (
        c.scheduling ? (
          <div className="t2-schedule">
            <label className="t2-coupon-label" htmlFor="booking-when">
              موعد الانطلاق
            </label>
            <input
              id="booking-when"
              type="datetime-local"
              className="t2-input"
              value={c.when}
              min={localInputValue(earliest())}
              max={localInputValue(latest())}
              onChange={(event) => c.setWhen(event.target.value)}
            />
            <p className="t2-sheet-fine">
              نبدأ البحث عن كبتنٍ قبل موعدك بعشر دقائق. <b>والسعر يُحسب عند التنفيذ</b> — الرقمُ أعلاه تقديرُ اليوم.
            </p>
            <div className="t2-schedule-row">
              <button
                type="button"
                className="t2-button primary"
                disabled={!c.when}
                onClick={() => props.onSchedule(c.category, c.preference, c.when)}
              >
                ثبّت الحجز
              </button>
              <button type="button" className="t2-button secondary" onClick={() => c.setScheduling(false)}>
                إلغاء
              </button>
            </div>
          </div>
        ) : (
          <button
            type="button"
            className="t2-button secondary t2-schedule-open"
            onClick={() => {
              c.setWhen(localInputValue(earliest()));
              c.setScheduling(true);
            }}
          >
            <span className="t2-icon" aria-hidden="true">event_upcoming</span>
            حدّد موعداً
          </button>
        )
      ) : null}

      <p className="t2-sheet-fine center">السعر النهائي قد يتغيّر إن اختلف المسار الفعلي كثيراً عن المقدَّر.</p>

      {c.pickingPay && c.payMethod ? (
        <PaymentPicker
          channels={c.channels}
          selected={c.payMethod.method}
          onSelect={c.choose}
          onClose={() => c.setPickingPay(false)}
          walletHint={c.balance === null ? null : `الرصيد: ${formatMoney(c.balance, currency)}`}
          variant="t2"
        />
      ) : null}
    </SheetT2>
  );
}
