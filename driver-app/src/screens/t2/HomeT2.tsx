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
 * - **«خريطة الطلب» ومناطقُها** («عبدون ×1.4» · «الأقرب لك: عبدون ×1.4 · 2.3 كم»): لا خريطةَ طلبٍ ولا مضاعِفَ سعرٍ في النظام.
 *   **وموضعُ الشارة صار «توسيع»** — ميزةُ البطاقة القائمة (قرارُ المالك 2026-08-30) بلغة الشارة.
 * - **«الكل»**: لا شاشةَ خدماتٍ كاملة — البلاطاتُ كلُّها هنا.
 * - **نقطةُ «الوثائق» الحمراء**: البلاطاتُ من اللوحة (`GET /storefront`) ولا حالَ مستنداتٍ معها.
 * - **«أرباح اليوم»** ⇐ **«صافي اليوم»**: الرقمُ صافي ما دخل المحفظة (`earnings.net`) — الكاشُ وكليك خارجه، كما قيل في C09.
 *
 * ## وما في الرئيسية القائمة ولم يُرسم — باقٍ بلغة اللوحة
 *
 * تفضيلُ جنس الركّاب · تحذيرُ الأذونات · الخطأ · «رقمُك قيد التحقق» · اللافتاتُ وعرضُ الاشتراك · سطرُ الاشتراك و«جدّد» ·
 * المركبةُ وبابُها · **«توسيع» الخريطة** · حالُ الاتصال بأطواره («جارٍ الاتصال…» · «بانتظار إشارة الموقع» · «نفتح الطلب…»).
 * **ومبدّلُ السِمة في «الإعدادات» الليلية** (C15 · «المظهر») و**نسبةُ العمولة في «الأرباح»** (C09) — نُزعا من الرأس ولم يضيعا.
 */

import { useCallback, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import type { NavigateFunction } from "react-router-dom";

import {
  acceptRide,
  arriveAtStop,
  beginPause,
  cancelRide,
  declineRide,
  resumeFromStop,
  resumePause,
} from "@/api/endpoints";
import type { Currency, MyProgress, MySubscription, ServiceTile } from "@/api/types";
import { CliqTransferSheet } from "@/components/CliqTransferSheet";
import { useMapExpand } from "@/components/home/MapCard";
import { BannerImage, OfferCard, PromoBanners, type PromoSkin } from "@/components/home/PromoBanners";
import { tileOpenable } from "@/components/home/ServiceTiles";
import { MapView } from "@/components/map/MapView";
import { PermissionNotice } from "@/components/PermissionNotice";
import { PhonePendingNotice } from "@/components/PhonePendingNotice";
import { isActive } from "@/lib/ride";
import { CATEGORY_LABEL, CURRENCY_LABEL, PREFERENCE_LABEL } from "@/lib/rideFormat";
import { digits } from "@/lib/utils";
import { useHomeScreen } from "@/screens/Home";
import { LEVEL_LABEL } from "@/screens/Missions";
import { CollectT2Screen } from "@/screens/t2/CollectT2";
import { countDays } from "@/screens/t2/count";
import { OfferT2 } from "@/screens/t2/OfferT2";
import { RideT2 } from "@/screens/t2/RideT2";
import { Icon, Wordmark, serviceIcon } from "@/taxo2";

import "./t2.css";
import "./ride.css";

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
    currency,
    colleagues,
    routeLine,
    steps,
    thresholdM,
    eta,
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
  const [sheetRef, sheetHeight] = useMeasuredHeight();
  const mode = tracking ? "ride" : offer ? "offer" : "home";
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
  const rating = profile ? profile.driver.rating_avg : null;

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
          <div className="t2-hm-avatar" aria-hidden="true">
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
          {womenService && preference !== "any" ? (
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
            <GoPill
              online={online}
              connecting={connecting}
              located={position !== null}
              awaitedOffer={awaitedOffer}
              goLabel={goLabel}
              onToggle={toggleOnline}
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

      {mode === "home" ? (
        <Services
          tiles={storefront?.tiles ?? []}
          subscription={subscription}
          progress={progress}
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
          genderPreference={profile?.driver.gender_preference ?? "any"}
          sheetRef={sheetRef}
          onAdvance={() => void advance()}
          onPause={() => void run(async () => setRide(await beginPause(ride.id)))}
          onResume={() => void run(async () => setRide(await resumePause(ride.id)))}
          onArriveStop={(stopId) => void run(async () => setRide(await arriveAtStop(ride.id, stopId)))}
          onResumeStop={(stopId) => void run(async () => setRide(await resumeFromStop(ride.id, stopId)))}
          onCancel={(reason) => void run(async () => setRide(await cancelRide(ride.id, reason.label, reason.code)))}
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

/** **حبّةُ الاستقبال** في قاع البطاقة — متصلٌ بالجمر ونبضُه، وغيرُ متصلٍ بالسطح وزرُّ التشغيل بالجمر. **والحالُ بأطوارها
 *  القائمة**: «بانتظار إشارة الموقع» قبل أوّل بثّ (لا يُدخل الكبتنَ التوزيعَ غيرُه)، و«نفتح الطلب…» لمن نقر إشعارَ طلب. */
function GoPill({
  online,
  connecting,
  located,
  awaitedOffer,
  goLabel,
  onToggle,
}: {
  online: boolean;
  connecting: boolean;
  located: boolean;
  awaitedOffer: boolean;
  goLabel: string;
  onToggle: () => void;
}) {
  const title = online
    ? `متصل — ${awaitedOffer ? "نفتح الطلب…" : located ? "بانتظار الطلبات" : "بانتظار إشارة الموقع"}`
    : connecting
      ? goLabel
      : "غير متصل";
  const sub = online || connecting ? null : goLabel;
  return (
    <button
      type="button"
      className={`t2-hm-go ${online ? "on" : "off"}`}
      onClick={onToggle}
      disabled={connecting}
      // **الفعلُ يُقال لقارئ الشاشة مع الحال** — الحبّةُ تقول «متصل»، والضغطةُ «إيقاف الاستقبال»
      aria-label={online ? `${title}، ${goLabel}` : undefined}
    >
      <span className="t2-hm-go-dot" aria-hidden="true">
        {online ? <i className="pulse" /> : null}
        <i />
      </span>
      <span className="t2-hm-go-text">
        <span className="t2-hm-go-title">{title}</span>
        {sub ? <span className="t2-hm-go-sub">{sub}</span> : null}
      </span>
      <span className="t2-hm-go-power" aria-hidden="true">
        <Icon name="power_settings_new" />
      </span>
    </button>
  );
}

/** **خدماتك** — البلاطاتُ من اللوحة (`GET /storefront`) بلغة C04، **وقاعدةُ الضغط من بيتها** (`tileOpenable`): «قريباً» تُقرأ
 *  ولا تُنقر. **وشارةُ البلاطة من بيانها**: «جديد» محسوبةٌ في الخلفية، والأيّامُ الباقيةُ من الاشتراك، والمهامُّ المنجزةُ
 *  من المستوى — **ولا رقمَ يُخترع لبلاطةٍ لا بيانَ معها**. */
function Services({
  tiles,
  subscription,
  progress,
  covered,
  navigate,
}: {
  tiles: ServiceTile[];
  subscription: MySubscription | null;
  progress: MyProgress | null;
  covered: boolean;
  navigate: NavigateFunction;
}) {
  if (tiles.length === 0) return null;
  return (
    <>
      <div className="t2-hm-svc-head">
        <span className="t2-hm-svc-title">خدماتك</span>
      </div>
      <div className="t2-hm-tiles">
        {tiles.map((tile) => {
          const tag = tileTag(tile, subscription, progress);
          const ok = tile.destination === "/subscription" && covered;
          const body = (
            <>
              <span className="t2-hm-tile-top">
                <span className={`t2-hm-tile-icon${ok ? " ok" : ""}`}>
                  <Icon name={serviceIcon(tile.icon)} fill />
                </span>
                {tag ? (
                  <span className={`t2-hm-tile-tag ${tag.tone}`} dir={tag.ltr ? "ltr" : undefined}>
                    {tag.text}
                  </span>
                ) : null}
              </span>
              <span>
                <span className="t2-hm-tile-title">{tile.title}</span>
                {tile.subtitle && tile.status !== "soon" && !tile.is_new ? (
                  <span className="t2-hm-tile-sub">{tile.subtitle}</span>
                ) : null}
              </span>
            </>
          );
          return tileOpenable(tile) ? (
            <button key={tile.id} type="button" className="t2-hm-tile" onClick={() => navigate(tile.destination!)}>
              {body}
            </button>
          ) : (
            <div key={tile.id} className="t2-hm-tile">
              {body}
            </div>
          );
        })}
      </div>
    </>
  );
}

function tileTag(
  tile: ServiceTile,
  subscription: MySubscription | null,
  progress: MyProgress | null,
): { text: string; tone: string; ltr?: boolean } | null {
  if (tile.status === "soon") return { text: "قريباً", tone: "soon" };
  if (tile.is_new) return { text: "جديد", tone: "new" };
  if (tile.destination === "/subscription" && subscription?.is_active) {
    return { text: countDays(subscription.days_remaining), tone: "ok" };
  }
  if (tile.destination === "/account/missions" && progress?.enabled && progress.missions_total > 0) {
    return {
      text: `${digits(String(progress.missions_done))}/${digits(String(progress.missions_total))}`,
      tone: "",
      ltr: true,
    };
  }
  return null;
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
