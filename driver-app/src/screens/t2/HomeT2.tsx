/** **الرئيسيةُ ورحلتُها في TAXO 2.0** — C04 الرئيسية · C05 طلبٌ وارد · C06 الطريقُ إلى الراكب · C07 أثناء الرحلة ·
 * C08 التحصيل (الليليُّ المرسوم وحدَه — §٦١-د؛ والفاتحُ بالشاشة القائمة كما هي، `ByTheme` في `App.tsx`).
 *
 * **المنطقُ كلُّه من `useHomeScreen`** (`screens/Home.tsx`): المقبسُ والعرضُ والرحلةُ وانتقالاتُها وخطُّها وتعليمتُها
 * ووصولُها المتوقَّع وما بعد الإنهاء — **فلا يقرّر هذا الملفُّ شيئاً ولا يكتب حالاً**؛ يرسم. **والأفعالُ نداءاتُ الشاشة
 * القائمة بحرفها** (القبولُ والرفضُ والانتقالاتُ والوقفةُ والمحطةُ والإلغاء) — منسوخةً من سطور JSX هناك لأنها مكتوبةٌ فيها.
 *
 * **والخريطةُ عقدةٌ واحدةٌ في الأطوار كلِّها** — بطاقةً في الخمول وإطاراً أعلى الشاشة في الطلب والرحلة: **موضعُها في الشجرة
 * ثابتٌ ويتبدّل صنفُها** (قاعدةُ `MapCard`)، فلا يُبنى `mapbox-gl` من جديدٍ بين الرئيسية والرحلة.
 *
 * ## C04 — ما رسمته اللوحةُ ولا مصدرَ له لا يُرسم مكانَه شيء (§٦١-د/د)
 *
 * - **«6:20 ساعة»**: لا ساعاتِ عملٍ في أيِّ باب. («9 رحلات» و«4.92» بُنيتا: `completed_rides` · `rating_avg`.)
 * - **«خريطة الطلب» ومناطقُها** («عبدون ×1.4» · «الأقرب لك: عبدون ×1.4 · 2.3 كم»): لا خريطةَ طلبٍ ولا مضاعِفَ سعرٍ في النظام
 *   (التسعيرُ المتحرّك «لا يُبنى الآن»). **وموضعُ الشارة صار «توسيع»** — ميزةُ البطاقة القائمة (قرارُ المالك 2026-08-30) بلغة الشارة.
 *   **وفي موضع «الأقرب لك» تحت «متصل» سطرُ «الطلب مرتفع حولك الآن»** (§٦٢-ج/٤٣) — من عدِّ ما طُلب حوله لا من خريطة (`useDemandHigh`).
 * - **«الكل» ونقطةُ «الوثائق» بُنيتا** (§٦٢-ج/٤٣، `ServicesT2`): ستُّ بلاطاتٍ هنا ما يعمل منها أوّلاً، و«الكل» حين تزيد؛ والنقطةُ على
 *   بلاطة المركبة ووثائقها حين تحتاج وثائقُه فعلاً. **وأيقوناتُ البلاطات الستّ المرسومة صارت في قائمة اللوحة** والجسرِ والخطّ.
 * - **«أرباح اليوم»** ⇐ **«صافي اليوم»**: الرقمُ صافي ما دخل المحفظة (`earnings.net`) — الكاشُ وكليك خارجه، كما قيل في C09.
 *
 * ## وما في الرئيسية القائمة ولم يُرسم — باقٍ بلغة اللوحة
 *
 * تفضيلُ جنس الركّاب · تحذيرُ الأذونات · الخطأ · «رقمُك قيد التحقق» · اللافتاتُ وعرضُ الاشتراك · سطرُ الاشتراك و«جدّد» ·
 * المركبةُ وبابُها · **«توسيع» الخريطة** · حالُ الاتصال بأطواره («جارٍ الاتصال…» · «بانتظار إشارة الموقع» · «نفتح الطلب…»).
 * **ومبدّلُ السِمة في «الإعدادات» الليلية** (C15 · «المظهر») و**نسبةُ العمولة في «الأرباح»** (C09) — نُزعا من الرأس ولم يضيعا.
 *
 * ## CW2 · CW3 — الوضعُ النسائيّ والطلبُ النسائيّ (§٦٢-ج/٢٣ — `WomenRideT2.tsx`، وما لم يُبنَ منهما بعلّته هناك)
 *
 * كبتنةٌ اختارت «الراكبات فقط»: «وضع نسائي» في الرأس، والحرفُ بالبرقوق، و«متصلة — طلبات الراكبات فقط» في الحبّة **مكانَ** شريط
 * التفضيل — **والاستقبالُ هو هو**.
 */

import { useCallback, useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import type { NavigateFunction } from "react-router-dom";

import {
  acceptRide,
  arriveAtStop,
  beginPause,
  cancelRide,
  declineRide,
  refuseParcel,
  resumeFromStop,
  resumePause,
} from "@/api/endpoints";
import type { Coordinates, Currency, MyProgress, MySubscription, ServiceTile } from "@/api/types";
import { CliqTransferSheet } from "@/components/CliqTransferSheet";
import { useMapExpand } from "@/components/home/MapCard";
import { BannerImage, OfferCard, PromoBanners, type PromoSkin } from "@/components/home/PromoBanners";
import { MapView } from "@/components/map/MapView";
import { PermissionNotice } from "@/components/PermissionNotice";
import { PhonePendingNotice } from "@/components/PhonePendingNotice";
import { useDemandHigh, useDocumentsAttention } from "@/lib/attention";
import { setTrafficLayer, trafficLayer } from "@/lib/driving-prefs";
import { metersBetween } from "@/lib/eta";
import { openIn } from "@/lib/external-maps";
import { reversePlace, type PlaceReading } from "@/lib/geocode";
import { useGuaranteeEntry, type GuaranteeEntry } from "@/lib/guarantees";
import { isActive } from "@/lib/ride";
import { CATEGORY_LABEL, CURRENCY_LABEL, PREFERENCE_LABEL } from "@/lib/rideFormat";
import { digits, ratedAverage } from "@/lib/utils";
import { useHomeScreen } from "@/screens/Home";
import { LEVEL_LABEL } from "@/screens/Missions";
import { CollectT2Screen } from "@/screens/t2/CollectT2";
import { OfferT2 } from "@/screens/t2/OfferT2";
import { RideT2 } from "@/screens/t2/RideT2";
import { HOME_TILES, ServiceGrid, homeTiles } from "@/screens/t2/ServicesT2";
import { WomenModeChipT2, isWomenMode, womenGoText } from "@/screens/t2/WomenRideT2";
import { Icon, Wordmark } from "@/taxo2";

import { countBookings } from "./count";

import "./t2.css";
import "./ride.css";
import "./guarantees.css";

export function HomeT2Screen() {
  const {
    navigate,
    user,
    womenService,
    profile,
    activeSkin,
    preference,
    token,
    online,
    connecting,
    ride,
    offer,
    transfer,
    position,
    error,
    goOnline,
    goOffline,
    setRide,
    dismissOffer,
    dismissTransfer,
    clearError,
    awaitedOffer,
    settling,
    setSettling,
    subscription,
    earnings,
    storefront,
    progress,
    busy,
    unread,
    actionError,
    actionErrorCode,
    currency,
    colleagues,
    routeLine,
    steps,
    thresholdM,
    eta,
    approachNow,
    offerMinutes,
    instruction,
    covered,
    run,
    advance,
    goLabel,
    subscriptionLine,
    vehicleLine,
    vehicleNote,
    level,
  } = useHomeScreen();
  // **يُشتقّ هنا** كما في الشاشة القائمة — به يعرف `tsc` أنّ `ride` رحلةٌ في فرع التتبّع
  const tracking = isActive(ride);
  const { open, setOpen } = useMapExpand();
  // **طبقةُ الزحام وبطاقةُ النقر** (§٦٢-ج/٤٨): التفضيلُ على الجهاز ويتبعه في خرائطه كلِّها، **والنقرُ في الخريطة الموسَّعة وحدَها**
  // — الصغيرةُ بطاقةٌ تُلمس للتوسيع، والرحلةُ خريطةُ قيادةٍ لا تُسأل
  const [traffic, setTraffic] = useState(trafficLayer);
  const toggleTraffic = () => {
    const next = !traffic;
    setTrafficLayer(next);
    setTraffic(next);
  };
  const [tapped, setTapped] = useState<Tapped | null>(null);
  const reading = useRef<AbortController | null>(null);
  const tapAt = useCallback(
    (at: Coordinates) => {
      reading.current?.abort();
      const controller = new AbortController();
      reading.current = controller;
      setTapped({ at, place: null, reading: true });
      void reversePlace(token ?? "", at, controller.signal).then((place) => {
        if (!controller.signal.aborted) setTapped({ at, place, reading: false });
      });
    },
    [token],
  );
  // **البطاقةُ تُغلق مع الخريطة** — ولا تبقى نقطةٌ منقورةٌ في خريطةٍ أُغلقت
  useEffect(() => {
    if (open) return;
    reading.current?.abort();
    setTapped(null);
  }, [open]);
  const [sheetRef, sheetHeight] = useMeasuredHeight();
  const mode = tracking ? "ride" : offer ? "offer" : "home";
  // **ما يحتاج انتباهَه** (§٦٢-ج/٤٣): نقطةُ «الوثائق»، و«الطلب مرتفع» ما دام متصلاً في الرئيسية وحدَها
  const documentsAttention = useDocumentsAttention();
  const demandHigh = useDemandHigh(online && mode === "home");
  // **الحجوزُ المضمونة** (§٦٣-ج/٣) — تُقرأ في الرئيسية وحدَها، وتُعاد كلَّما عاد إليها من رحلةٍ أو طلب
  const guarantee = useGuaranteeEntry(mode === "home");
  // **الطلبُ والرحلةُ يبدآن من أعلى الصفحة**: طبقاتُ الإطار مطلقةُ الموضع داخل جذرٍ يتمرّر، **ورئيسيةٌ مُمرَّرةٌ ثمّ طلبٌ وارد
  // كانت تُزيح البطاقةَ والورقةَ بمقدار التمرير**
  const root = useRef<HTMLDivElement | null>(null);
  useLayoutEffect(() => {
    if (mode !== "home" && root.current) root.current.scrollTop = 0;
  }, [mode]);

  // **التحصيلُ يسبق كلَّ شيء** كما في الشاشة القائمة — **والتقييمُ فيه** (C08)، فلا شاشةَ تقييمٍ بعده
  if (settling) {
    return (
      <CollectT2Screen
        ride={settling}
        currencyLabel={currency}
        onDone={() => setSettling(null)}
      />
    );
  }

  const riding = tracking && (ride.status === "in_progress" || ride.status === "at_stop");
  // **زرُّ الاستقبال نفسُه** — سطرُ `onToggleOnline` في الشاشة القائمة بحرفه
  const toggleOnline = () => {
    clearError();
    if (!covered) navigate("/subscription");
    else if (online) goOffline();
    else goOnline();
  };
  // **التقييمُ كما يصل** (`rating_avg` بمنزلتين — «4.92» كما رُسم)؛ والشاشةُ القائمةُ تقرّبه إلى منزلة
  // **ولا شارةَ «★ 0.00» لمن لم يُقيَّم بعد** (§٦٢-ب/٤٩) — كما لا تُرسم «0 رحلة» رقماً
  const rating = profile ? ratedAverage(profile.driver.rating_avg) : null;
  // **CW2 — الوضعُ النسائيّ** (§٦٢-ج/٢٣): كبتنةٌ اختارت «الراكبات فقط» حيث الخدمةُ مشتعلة
  const womenMode = isWomenMode(womenService, preference, user?.gender);

  return (
    <div
      ref={root}
      className={`t2 t2-hm ${mode}`}
      style={mode === "ride" && sheetHeight ? ({ "--t2-sheet-h": `${sheetHeight}px` } as CSSProperties) : undefined}
    >
      {mode === "home" ? (
        <div className="t2-hm-head">
          <Wordmark size={19} />
          {level !== null ? (
            <span className="t2-hm-level">
              <Icon name="workspace_premium" fill />
              {LEVEL_LABEL[level] ?? `المستوى ${digits(String(level))}`}
            </span>
          ) : null}
          {womenMode ? <WomenModeChipT2 onOpen={() => navigate("/account/settings/women")} /> : null}
          <span className="t2-hm-gap" />
          <button
            type="button"
            className="t2-hm-bell"
            onClick={() => navigate("/notifications")}
            aria-label="الإشعارات"
          >
            <Icon name="notifications" />
            {unread > 0 ? <span className="t2-hm-bell-dot" /> : null}
          </button>
          <div className={womenMode ? "t2-hm-avatar women" : "t2-hm-avatar"} aria-hidden="true">
            {(user?.name ?? "كبتن").slice(0, 1)}
          </div>
        </div>
      ) : null}

      {mode === "home" ? (
        <div className="t2-hm-earn">
          {/* **«صافي اليوم» لا «أرباح اليوم»** — الرقمُ صافي ما دخل المحفظة، **ولا يُرسم صفرٌ مكانَ «لم يُعرف بعد»** */}
          <div className="t2-hm-earn-label">صافي اليوم</div>
          <div className="t2-hm-earn-row">
            <span className="t2-hm-earn-num" dir="ltr">
              {earnings ? digits(earnings.net) : "—"}
            </span>
            {earnings ? <span className="t2-hm-earn-cur">{CURRENCY_LABEL[earnings.currency]}</span> : null}
          </div>
          <div className="t2-hm-chips">
            {earnings ? (
              <span className="t2-hm-chip">
                <Icon name="local_taxi" />
                <RideCount n={earnings.completed_rides} />
              </span>
            ) : null}
            {rating ? (
              <span className="t2-hm-chip">
                <Icon name="star" fill />
                <span className="t2-hm-chip-num" dir="ltr">
                  {digits(rating)}
                </span>
              </span>
            ) : null}
          </div>
        </div>
      ) : null}

      {/* **فوق زرِّ الاستقبال لا تحته** (الرئيسيةُ القائمة): من ضيّق ركّابه، ومن رفض إذناً، ومن رُدّ اتصالُه — يقرأ ذلك وهو يقرّر
          أن يعمل. **ولا يظهر شيءٌ هنا إلا حين يكون** — والفارغُ يختفي فتبقى البطاقةُ في موضعها المرسوم */}
      {mode === "home" ? (
        <div className="t2-hm-notes t2-legacy">
          {/* **وفي الوضع النسائيّ تقوله الحبّةُ والشارة** (CW2) — فلا شريطَ ثانٍ بالشيء نفسِه */}
          {womenService && preference !== "any" && !womenMode ? (
            <button type="button" className="t2-hm-pref" onClick={() => navigate("/account/settings")}>
              <span className="t2-hm-pref-text">أستقبل ركاباً: {PREFERENCE_LABEL[preference]}</span>
              <span className="t2-hm-pref-go">تغيير</span>
            </button>
          ) : null}
          <PermissionNotice />
          {error || actionError ? (
            <p className="t2-note danger">
              <Icon name="error" fill />
              {error ?? actionError}
            </p>
          ) : null}
        </div>
      ) : null}

      {/* **الخريطة — عقدةٌ واحدةٌ في موضعٍ ثابتٍ من الشجرة** (الطفلُ الرابعُ دائماً)؛ يتبدّل صنفُ الجذر وصنفُها */}
      <div className={`t2-hm-map${mode === "home" && open ? " open" : ""}`}>
        <MapView
          token={token}
          center={position}
          selfSkin={activeSkin}
          subscribed={covered}
          colleagues={colleagues}
          pickup={tracking ? ride.pickup : offer ? offer.ride.pickup : null}
          dropoff={tracking ? ride.dropoff : offer ? offer.ride.dropoff : null}
          fit={tracking || offer !== null}
          routePoints={routeLine}
          trimAt={position}
          etaMinutes={eta}
          t2
          routeTraveled={riding}
          traffic={traffic}
          onTap={mode === "home" && open ? tapAt : null}
          tapPin={mode === "home" && open ? (tapped?.at ?? null) : null}
        />
        {mode === "home" ? (
          <>
            <div className="t2-hm-shade" />
            <button
              type="button"
              className="t2-hm-mapchip"
              onClick={() => setOpen(!open)}
              aria-label={open ? "إغلاق الخريطة" : undefined}
            >
              <Icon name={open ? "close" : "open_in_full"} />
              {open ? null : "توسيع"}
            </button>
            {open ? (
              <button
                type="button"
                className={traffic ? "t2-hm-traffic on" : "t2-hm-traffic"}
                onClick={toggleTraffic}
                aria-pressed={traffic}
                aria-label="طبقة الزحام"
                title="طبقة الزحام"
              >
                <Icon name="traffic" />
              </button>
            ) : null}
            {open && tapped ? <TapCard tapped={tapped} position={position} onClose={() => setTapped(null)} /> : null}
            <GoPill
              online={online}
              connecting={connecting}
              located={position !== null}
              awaitedOffer={awaitedOffer}
              goLabel={goLabel}
              demandHigh={demandHigh}
              onToggle={toggleOnline}
              women={womenMode}
            />
          </>
        ) : null}
      </div>

      {mode === "home" ? (
        <div className="t2-hm-notes t2-legacy">
          {/* **فوق البلاطات لا تحتها** — الحسابُ المحدود يُمنع من أوّلِ ما تفتحه البلاطات (الرئيسيةُ القائمة) */}
          <PhonePendingNotice />
        </div>
      ) : null}

      {/* **الحجوزُ المضمونة** (§٦٣-ج/٣) — فوق الخدمات حين يكون فيها شيءٌ وحدَه: عرضٌ ينتظر، أو حجزٌ قبله، **أو سؤالُ «هل أنت
          في الطريق؟»** وهو أوّلُها لأن الحجزَ يُسحب بعده بلا ردّ. ومطفأً أو فارغاً لا صفّ */}
      {mode === "home" && guarantee ? <GuaranteeEntryRow entry={guarantee} onOpen={() => navigate("/guarantees")} /> : null}

      {mode === "home" ? (
        <Services
          tiles={storefront?.tiles ?? []}
          subscription={subscription}
          progress={progress}
          attention={documentsAttention}
          covered={covered}
          navigate={navigate}
        />
      ) : null}

      {mode === "home" ? (
        <div className="t2-hm-more">
          <div className="t2-legacy">
            <PromoBanners banners={storefront?.banners ?? []} offer={storefront?.offer ?? null} skin={PROMO_SKIN} />
          </div>
          {subscriptionLine ? (
            <button type="button" className="t2-hm-row" onClick={() => navigate("/subscription")}>
              <Icon name="workspace_premium" fill />
              <span className="t2-hm-row-main">
                <span className="t2-hm-row-title">{subscriptionLine}</span>
              </span>
              <span className="t2-hm-row-go">جدّد</span>
            </button>
          ) : null}
          {vehicleLine ? (
            <button type="button" className="t2-hm-row" onClick={() => navigate("/account/vehicle")}>
              <span className="t2-hm-row-main">
                <span className="t2-hm-row-title">{vehicleLine}</span>
                {vehicleNote ? <div className="t2-hm-row-sub">{vehicleNote}</div> : null}
              </span>
              <Icon name="chevron_left" className="go" />
            </button>
          ) : null}
        </div>
      ) : null}

      {offer ? (
        <OfferT2
          offer={offer}
          minutes={offerMinutes}
          currencyLabel={currency}
          categoryLabel={CATEGORY_LABEL[offer.ride.vehicle_category]}
          busy={busy}
          over={tracking}
          onAccept={() =>
            void run(async () => {
              setRide(await acceptRide(offer.ride.id));
              dismissOffer();
            })
          }
          onDecline={() =>
            void run(async () => {
              await declineRide(offer.ride.id);
              dismissOffer();
            })
          }
        />
      ) : null}

      {tracking ? (
        <RideT2
          ride={ride}
          currencyLabel={currency}
          busy={busy}
          error={actionError}
          instruction={instruction}
          steps={steps}
          thresholdM={thresholdM}
          position={position}
          routeLine={routeLine}
          eta={eta}
          approachNow={approachNow}
          genderPreference={profile?.driver.gender_preference ?? "any"}
          sheetRef={sheetRef}
          onAdvance={(code) => void advance(code)}
          errorCode={actionErrorCode}
          onPause={() => void run(async () => setRide(await beginPause(ride.id)))}
          onResume={() => void run(async () => setRide(await resumePause(ride.id)))}
          onArriveStop={(stopId) => void run(async () => setRide(await arriveAtStop(ride.id, stopId)))}
          onResumeStop={(stopId) => void run(async () => setRide(await resumeFromStop(ride.id, stopId)))}
          onCancel={(reason) => void run(async () => setRide(await cancelRide(ride.id, reason.label, reason.code)))}
          // **«ارفض الطرد»** (§٦٣-ج/٤) — بابُه وحدَه، والرحلةُ تعود ملغاةً كما يعيدها الإلغاء
          onRefuseParcel={() => void run(async () => setRide(await refuseParcel(ride.id)))}
        />
      ) : null}

      {/* بطاقةُ حوالة كليك — تصل من المقبس في أي وقت (القسم 6.2)، **والورقةُ القائمةُ نفسُها** بألوان الهوية */}
      {transfer ? (
        <div className="t2-legacy">
          <CliqTransferSheet
            transfer={transfer}
            currencyLabel={CURRENCY_LABEL[transfer.currency as Currency]}
            onConfirmed={dismissTransfer}
            onDispute={() => {
              const rideId = transfer.rideId;
              dismissTransfer();
              navigate(`/rides/${rideId}/dispute`);
            }}
            onDismiss={dismissTransfer}
          />
        </div>
      ) : null}
    </div>
  );
}

/** **مقاسُ الورقة يُقاس** — فتنتهي الخريطةُ تحت حافّتها بخمسين كما رُسمت، ويبقى زرُّ الموقع ونسبةُ Mapbox فوقها. */
function useMeasuredHeight(): [(element: HTMLElement | null) => void, number | null] {
  const [height, setHeight] = useState<number | null>(null);
  const observer = useRef<ResizeObserver | null>(null);
  const ref = useCallback((element: HTMLElement | null) => {
    observer.current?.disconnect();
    observer.current = null;
    if (!element) {
      setHeight(null);
      return;
    }
    const watch = new ResizeObserver(() => setHeight(element.offsetHeight));
    watch.observe(element);
    observer.current = watch;
    setHeight(element.offsetHeight);
  }, []);
  return [ref, height];
}

/** «9 رحلات» كما رُسمت: **الرقمُ بخطّ الأرقام والتمييزُ بالنصّ** — وصيغُ العدد من بيتها (`count.ts`: «رحلة واحدة» · «رحلتان»). */
function RideCount({ n }: { n: number }) {
  if (n < 3) return <>{n === 0 ? "لا رحلات" : n === 1 ? "رحلة واحدة" : "رحلتان"}</>;
  return (
    <>
      <span className="t2-hm-chip-num" dir="ltr">
        {digits(String(n))}
      </span>
      {n <= 10 ? "رحلات" : "رحلة"}
    </>
  );
}

/** النقطةُ المنقورةُ في الخريطة الموسَّعة — وعنوانُها حين يُقرأ (`null` إن لم يُعرف). */
interface Tapped {
  at: Coordinates;
  place: PlaceReading | null;
  reading: boolean;
}

/** **بطاقةُ النقر** (§٦٢-ج/٤٨، `FUTURE-FEATURES` الخرائط #٣): اسمُ النقطة وعنوانُها وبُعدُها، **و«افتح في الملاحة»** إلى تطبيق خرائطه
 *  المختار (`openIn` — بابُ «فتح في الملاحة» نفسُه). **ولا عنوانَ يُخترع**: ما لم يُقرأ يُقال «نقطة على الخريطة». */
function TapCard({ tapped, position, onClose }: { tapped: Tapped; position: Coordinates | null; onClose: () => void }) {
  const title = tapped.place?.name ?? (tapped.reading ? "جارٍ قراءة العنوان…" : "نقطة على الخريطة");
  const km = position ? metersBetween(position, tapped.at) / 1000 : null;
  const sub = [km !== null ? `على بعد ${digits(km.toFixed(1))} كم` : null, tapped.place?.address ?? null]
    .filter(Boolean)
    .join(" · ");
  return (
    <div className="t2-hm-tapcard" role="dialog" aria-label="نقطة على الخريطة">
      <div className="t2-hm-tapcard-text">
        <span className="t2-hm-tapcard-name">{title}</span>
        {sub ? <span className="t2-hm-tapcard-sub">{sub}</span> : null}
      </div>
      <button
        type="button"
        className="t2-button action t2-hm-tapcard-go"
        onClick={() =>
          openIn({
            lat: tapped.at.lat,
            lng: tapped.at.lng,
            label: tapped.place?.name ?? "نقطة على الخريطة",
            cta: "افتح في الملاحة",
          })
        }
      >
        <Icon name="navigation" />
        افتح في الملاحة
      </button>
      <button type="button" className="t2-hm-tapcard-close" aria-label="إغلاق" onClick={onClose}>
        <Icon name="close" />
      </button>
    </div>
  );
}

/** **حبّةُ الاستقبال** في قاع البطاقة — متصلٌ بالجمر ونبضُه، وغيرُ متصلٍ بالسطح وزرُّ التشغيل بالجمر. **والحالُ بأطوارها
 *  القائمة**: «بانتظار إشارة الموقع» قبل أوّل بثّ (لا يُدخل الكبتنَ التوزيعَ غيرُه)، و«نفتح الطلب…» لمن نقر إشعارَ طلب. */
function GoPill({
  online,
  connecting,
  located,
  awaitedOffer,
  goLabel,
  demandHigh,
  onToggle,
  women = false,
}: {
  online: boolean;
  connecting: boolean;
  located: boolean;
  awaitedOffer: boolean;
  goLabel: string;
  /** «الطلب مرتفع حولك الآن» تحت «متصل» — في موضع «الأقرب لك» المرسوم (§٦٢-ج/٤٣). */
  demandHigh: boolean;
  onToggle: () => void;
  /** **CW2 — الوضعُ النسائيّ** (§٦٢-ج/٢٣): نصّاها مؤنّثين و«طلبات الراكبات فقط»، والحبّةُ برقوقاً (`WomenRideT2`). */
  women?: boolean;
}) {
  const shown = women ? womenGoText({ online, connecting, located, awaitedOffer, goLabel }) : null;
  const title = shown
    ? shown.title
    : online
      ? `متصل — ${awaitedOffer ? "نفتح الطلب…" : located ? "بانتظار الطلبات" : "بانتظار إشارة الموقع"}`
      : connecting
        ? goLabel
        : "غير متصل";
  // **«الطلب مرتفع» لغير الوضع النسائيّ** (§٦٢-ج/٤٣): العدُّ لكلِّ الطلبات، ومن لا تصلها إلا طلباتُ الراكبات يقرؤه وعداً لا يقع —
  // وسطرُها («يمكنك تغيير ذلك من الإعدادات») باقٍ في موضعه
  const demand = !women && online && demandHigh ? "الطلب مرتفع حولك الآن" : null;
  const sub = shown ? shown.sub : online ? demand : connecting ? null : goLabel;
  return (
    <button
      type="button"
      className={`t2-hm-go ${online ? "on" : "off"}${women ? " women" : ""}`}
      onClick={onToggle}
      disabled={connecting}
      // **الفعلُ يُقال لقارئ الشاشة مع الحال** — الحبّةُ تقول «متصل»، والضغطةُ «إيقاف الاستقبال»
      aria-label={online ? `${title}${demand ? `، ${demand}` : ""}، ${goLabel}` : undefined}
    >
      <span className="t2-hm-go-dot" aria-hidden="true">
        {online ? <i className="pulse" /> : null}
        <i />
      </span>
      <span className="t2-hm-go-text">
        <span className="t2-hm-go-title">{title}</span>
        {sub ? (
          <span className="t2-hm-go-sub">
            {demand ? <Icon name="local_fire_department" fill /> : null}
            {sub}
          </span>
        ) : null}
      </span>
      <span className="t2-hm-go-power" aria-hidden="true">
        <Icon name="power_settings_new" />
      </span>
    </button>
  );
}

/** **مدخلُ الحجوز المضمونة** (§٦٣-ج/٣) — صفُّ «جدّد» نفسُه بالجمر. **والسؤالُ يسبق العرض**: حجزٌ يُسأل عنه الآن يُسحب بلا ردّ،
 *  والعروضُ تنتظر. **والعددُ بالعربية** (`countBookings`) لا «2 حجز». */
function GuaranteeEntryRow({ entry, onOpen }: { entry: GuaranteeEntry; onOpen: () => void }) {
  const title = entry.asking ? "هل أنت في الطريق؟" : entry.offers > 0 ? "عروضٌ تنتظرك" : "حجوزُك المضمونة القادمة";
  const sub = entry.asking
    ? "حجزُك المضمون قريب — أكّده الآن، وإلا عاد لغيرك"
    : entry.offers > 0
      ? `${countBookings(entry.offers)} في فئة مركبتك — ورسمُ الضمان لك كاملاً`
      : `لك ${countBookings(entry.upcoming)} — نسألك قبل الموعد بساعة`;
  return (
    <div className="t2-gu-home">
      <button type="button" className={entry.asking ? "t2-hm-row t2-gu-entry asking" : "t2-hm-row t2-gu-entry"} onClick={onOpen}>
        <Icon name={entry.asking ? "schedule" : "event_upcoming"} fill />
        <span className="t2-hm-row-main">
          <span className="t2-hm-row-title">{title}</span>
          <div className="t2-hm-row-sub">{sub}</div>
        </span>
        <Icon name="chevron_left" className="go" />
      </button>
    </div>
  );
}

/** **خدماتك** — ستُّ بلاطاتٍ بلغة C04 (`homeTiles`: ما يعمل أوّلاً)، **و«الكل» حين تزيد** (§٦٢-ج/٤٣) — والشبكةُ وشاراتُها ونقطتُها
 *  من بيتها (`ServiceGrid`) فلا تفترق عن صفحة «الكل». */
function Services({
  tiles,
  subscription,
  progress,
  covered,
  attention,
  navigate,
}: {
  tiles: ServiceTile[];
  subscription: MySubscription | null;
  progress: MyProgress | null;
  covered: boolean;
  attention: boolean;
  navigate: NavigateFunction;
}) {
  if (tiles.length === 0) return null;
  return (
    <>
      <div className="t2-hm-svc-head">
        <span className="t2-hm-svc-title">خدماتك</span>
        {tiles.length > HOME_TILES ? (
          <button type="button" className="t2-hm-svc-all" onClick={() => navigate("/services")}>
            الكل
          </button>
        ) : null}
      </div>
      <ServiceGrid
        tiles={homeTiles(tiles)}
        subscription={subscription}
        progress={progress}
        covered={covered}
        attention={attention}
        navigate={navigate}
      />
    </>
  );
}

/** **لافتاتُ اللوحة بجلد الهوية** — بطاقةُ الجمر بشريطها كما رُسمت للراكب (R05)، **والدورانُ والسحبُ والنقرُ والصورُ من
 *  `PromoBanners`** (جلدٌ لا صندوقٌ ثانٍ). **وعرضُ الاشتراك** بوجهه القائم. */
const PROMO_SKIN: PromoSkin = {
  frame: "t2-hm-promo",
  face: (slide, loadImage) => {
    if (slide.kind === "offer") return <OfferCard offer={slide.offer} />;
    const { banner } = slide;
    const opens = banner.link_kind !== "none" && banner.link !== null;
    return (
      <>
        {loadImage ? <BannerImage bannerId={banner.id} /> : null}
        <div className="t2-hm-promo-row">
          <span className="t2-hm-promo-stripe" aria-hidden="true" />
          {/* **«30%» الكبيرة** (§٦٢-ج/٢٦) — من حقلها في صفِّ اللافتة، كوجه الراكب */}
          {banner.headline ? (
            <span className="t2-hm-promo-big" dir="ltr">
              {banner.headline}
            </span>
          ) : null}
          <div className="t2-hm-promo-text">
            <div className="t2-hm-promo-title">{banner.title}</div>
            {banner.body ? <div className="t2-hm-promo-body">{banner.body}</div> : null}
          </div>
          {opens ? (
            <span className="t2-icon t2-hm-promo-go" aria-hidden="true">
              arrow_back
            </span>
          ) : null}
        </div>
      </>
    );
  },
  dots: "t2-hm-promo-dots",
  dot: (on) => (on ? "t2-hm-promo-dot on" : "t2-hm-promo-dot"),
};
