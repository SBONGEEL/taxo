/** الرئيسية — TAXO 2.0 «R05» (Claude Design «Rider»)، **مطابقةٌ للتصميم** (§٦١-د) — **في المظهرين**: رُسمت نهاريّاً، والليليُّ برموز إسفلت الهوية نفسِها (§٦٢/٣).
 *
 * **وجهٌ لا منطق**: الشاشةُ (`screens/Home.tsx`) تمرّر الشيءَ نفسَه للوجهين (`RiderHomeProps`)، والخريطةُ عقدةٌ واحدة،
 * والتوسيعُ وزرُّ الجهاز الخلفيُّ من `useExpandable`، واللافتاتُ من `PromoBanners` بجلدها.
 *
 * **والقيمُ الحيّةُ من بياناتٍ حقيقيةٍ أو لا شيء** (§٦١-د/د): شارةُ الموقع اسمُ منطقة نقطة الانطلاق من Mapbox (`area`)، وعددُ
 * الكباتن حولك من `GET /drivers/nearby`، والحرفُ من الحساب. **و«يصل خلال 3 د» وشارةُ «3 د» لا مصدرَ لهما اليوم** — فلا
 * يُرسم مكانَهما شيء (أُبلغ المالك). **و«30%» في اللافتة لا عمودَ لها في صفوف اللافتات** — فلا رقمَ هناك (أُبلغ).
 *
 * **والبلاطاتُ الأربعُ كما رُسمت** (§٦١-د/أ–ج): «المطار» بـ«جديد» و«طرد» و«بالساعة» **رسالةُ «قريباً» عند اللمس ولا شيءَ غيرُها**،
 * و«مجدولة» رحلاتُه المجدولة (بمفتاح سوقها)، و«نسائية» **تبدأ الطلبَ بـ«كبتنة فقط» وهي تغيّره بنفسها** — كما تعمل الخدمةُ اليوم.
 * **و«طرد» حيث مفتاحُه مشتعلٌ تبدأ طلبَ طرد** (§٦٣-ج/٤، `onParcel`) — ومطفأً «قريباً» كما كانت. **و«بالساعة» مثلُها**
 * (§٦٣-ج/٥، `onHourly`): مشتعلاً تبدأ طلبَ ساعاتٍ بلا شارة «قريباً»، ومطفأً كما رُسمت.
 *
 * **وما نُزل بلغ من موضعٍ آخر** (§٦١-د/و): الأماكنُ المحفوظةُ في البحث وفي «حسابي»، وآخرُ الرحلات و«أعِد الرحلة» في «رحلاتي»
 * وتفاصيلها، والإحالةُ في «حسابي»، والرصيدُ في «المحفظة»، **والخريطةُ الكاملةُ بلمسة البطاقة** بدل زرِّ «توسيع».
 *
 * **ونارُ «الاسترداد الأسبوعي» تحت صفِّ الخدمات** (§٦٣-ج/٨، `CashbackChipT2`) — **لا لوحةَ لها**، فتُركَّب من عُدّة الهوية: بطاقةٌ
 * بسطح البلاطات ودائرةُ أيقونةٍ بالجمر، وورقةُ `DrawerT2` للشرح. **وحيث المفتاحُ مطفأٌ أو المبلغُ صفرٌ لا يُرسم منها شيء.**
 */

import type { ReactNode } from "react";
import type {
  MyReferrals,
  PromoBanner,
  Ride,
  RiderUnconfirmed,
  SavedPlace,
  ServiceTile,
  Wallet,
  WeeklyCashback,
} from "@/api/types";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { PhonePendingNotice } from "@/components/PhonePendingNotice";
import { PromoBanners } from "@/components/home/PromoBanners";
import { useExpandable } from "@/components/home/MapCard";
import { fastestMinutes, type CategoryMinutes } from "@/lib/arrival";
import { cashbackDaysText, useScheduledRides, useWeeklyCashback } from "@/lib/bookings";
import { useHourly } from "@/lib/hourly";
import { VEHICLE_LABEL } from "@/lib/labels";
import { useParcel } from "@/lib/parcel";
import { useSession } from "@/lib/session";
import { formatMoney } from "@/lib/utils";
import { useWomenService } from "@/lib/women";
import { Wordmark } from "@/taxo2";

import { DrawerT2 } from "./DrawerT2";
import { PROMO_SKIN_T2 } from "./StorefrontT2";
import { DeclareGenderSheetT2 } from "./WomenServiceT2";
import { UnconfirmedStripT2 } from "./UnconfirmedT2";
import "@/taxo2";
import "./t2.css";
import "./cashback.css";

/** خصائصُ الرئيسية (R05) — **كانت في الوجه القديم** (`components/home/RiderHome.tsx`) ونُزع (§٦٢/٣). */
export interface RiderHomeProps {
  name: string;
  /** عنوانُ موقعه إن عُرف — **ولا مدينةَ تُخمَّن**. */
  place: string | null;
  unread: boolean;
  wallet: Wallet | null;
  /** **رمزُ العملة لا علامتُها** — `formatMoney` يحلّها، **وحلُّها هنا ثانيةً
   *  يطبعها مرّتين** (`check:money`). */
  currency: string;
  /** عددُ الكباتن القريبين — **بلا مهلةٍ لا تُقاس**. */
  nearby: number;
  /** **دقائقُ أقرب كبتنٍ لكلِّ فئة** (§٦٢-ج/١٠) — «اقتصادي يصل خلال 3 د» تحت «إلى أين؟» وشارةُ «3 د»؛ و`null` حيث المفتاحُ مطفأ. */
  eta?: CategoryMinutes | null;
  onOpenNotifications: () => void;
  onOpenWallet: () => void;
  onOpenAccount: () => void;
  onAskDestination: () => void;
  places: SavedPlace[];
  onPickPlace: (place: SavedPlace) => void;
  tiles: ServiceTile[];
  banners: PromoBanner[];
  referrals: MyReferrals | null;
  onOpenReferrals: () => void;
  recent: Ride[];
  onOpenRides: () => void;
  onRepeat: (ride: Ride) => void;
  /** الخريطةُ بطاقةً — تُمرَّر كما هي فلا تُبنى مرّتين. */
  map: ReactNode;
  /** اسمُ منطقة نقطة الانطلاق لشارة الرأس (`null` = لا شارة)، وفتحُ دبوس الانطلاق من الشارة، وبدءُ الطلب بـ«كبتنة فقط» (§٦١-د). */
  area?: string | null;
  onChangePickup?: () => void;
  onWomenRide?: () => void;
  /** **بدءُ طلب طرد** (§٦٣-ج/٤) — منتقي الوجهة ثمّ ورقتُه؛ والبلاطةُ لا تناديه إلا حيث المفتاحُ مشتعل. */
  onParcel?: () => void;
  /** **بدءُ طلب ساعات** (§٦٣-ج/٥) — منتقي الوجهة بـ«بلا وجهة» ثمّ ورقتُها؛ والبلاطةُ لا تناديه إلا حيث المفتاحُ مشتعل. */
  onHourly?: () => void;
  /** **ما ينتظر تأكيدَه** (`design/PAYMENTS-UNCONFIRMED.md` §٦) — شريطُ «تأكيدٌ ينتظرك» أعلى الرئيسية؛ و`null` حيث المفتاحُ مطفأ. */
  unconfirmed?: RiderUnconfirmed | null;
  onOpenUnconfirmed?: () => void;
}


/** «كم كبتناً حولك» بعربيةٍ تُقرأ — **العددُ وحدَه بلا مهلة**. **وبيتُها هنا لـR05 وR07 معاً** («6 كباتن حولك الآن» أثناء البحث). */
export function nearbyLabel(count: number): string {
  if (count === 1) return "كبتن حولك";
  if (count === 2) return "كبتنان حولك";
  if (count <= 10) return "كباتن حولك";
  return "كبتناً حولك";
}

/** **الخريطةُ بطاقةً** — والعقدةُ هي هي في الحالين. **ولا زرَّ «توسيع»** كما رُسمت: **لمسةُ البطاقة تفتحها** (§٦١-د/و). */
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
      {!open ? (
        <>
          <button type="button" className="t2-home-map-tap" onClick={() => setOpen(true)} aria-label="فتح الخريطة" />
          {nearby > 0 ? (
            <span className="t2-home-near">
              {nearby > 2 ? <span className="t2-num">{nearby}</span> : null}
              {nearbyLabel(nearby)}
            </span>
          ) : null}
        </>
      ) : (
        <>
          <button type="button" className="t2-home-close" onClick={() => setOpen(false)} aria-label="إغلاق الخريطة">
            <span className="t2-icon" aria-hidden="true">close</span>
          </button>
          {/* **وزرُّ العمل في متناوله وهي مفتوحة** — فلا يُغلقها ليطلب */}
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

/** **سطرُ الحال تحت الأيام** — بترتيبه: ركب اليومَ (ولا جمعةَ تُقال لمن ركب)، ثمّ الجمعة، ثمّ الدعوة. **ومن الخلفية كلُّه** (`rode_today` ·
 *  `friday` بيوم السوق)، لا من ساعة الجهاز. */
function cashbackLine(cashback: WeeklyCashback): string {
  if (cashback.rode_today) return "ركبتَ اليوم — نارُك مشتعلة";
  if (cashback.friday) return "الجمعةُ لا تُحسب";
  return "رحلةٌ اليوم تُبقيها مشتعلة";
}

/** **نارُ «الاسترداد الأسبوعي»** (§٦٣-ج/٨) — الأيامُ الباقية والمبلغُ المنتظَر وسطرُ الحال، **ولمستُها تفتح شرحَ القاعدة بكلماتٍ بسيطة**.
 *  **والنارُ بثلاث نبرات**: مشتعلةٌ بالجمر لمن ركب اليوم، وجمرٌ خافتٌ لمن لم يركب بعد، ورماديّةٌ يومَ الجمعة (لا تُطلب ولا تقطع).
 *  **ولا مالَ يُحسب هنا** — المبلغُ كما أرسلته الخلفيةُ مجمَّداً على السلسلة. */
function CashbackChipT2({ cashback }: { cashback: WeeklyCashback }) {
  const [open, setOpen] = useState(false);
  const left = cashback.days_left ?? 0;
  const done = cashback.days_done ?? 0;
  const required = cashback.days_required ?? 0;
  const money = cashback.amount && cashback.currency ? formatMoney(cashback.amount, cashback.currency) : null;
  const tone = cashback.rode_today ? "lit" : cashback.friday ? "rest" : "wait";

  return (
    <>
      <button type="button" className={`t2-cbk ${tone}`} onClick={() => setOpen(true)}>
        <span className="t2-cbk-fire" aria-hidden="true">
          <span className="t2-icon fill">local_fire_department</span>
        </span>
        <span className="t2-cbk-text">
          <span className="t2-cbk-top">
            <span className="t2-cbk-days">{cashbackDaysText(left)}</span>
            {money ? (
              <span className="t2-cbk-money">
                <b className="t2-num">{money}</b> تنتظرك
              </span>
            ) : null}
          </span>
          <span className="t2-cbk-sub">{cashbackLine(cashback)}</span>
        </span>
        <span className="t2-icon t2-cbk-more" aria-hidden="true">chevron_left</span>
      </button>

      <DrawerT2 open={open} onOpenChange={setOpen} title="الاسترداد الأسبوعي">
        {/* **الأيامُ خاناتٌ لا نسبة** — ما أنجزه بالجمر وما بقي بحافّة، من عددين أرسلتهما الخلفية */}
        <div className="t2-cbk-track" role="img" aria-label={`أنجزتَ ${done} من ${required}`}>
          {Array.from({ length: required }, (_, index) => (
            <span key={index} className={index < done ? "t2-cbk-seg on" : "t2-cbk-seg"} />
          ))}
        </div>
        <div className="t2-cbk-track-note">
          <span>
            أنجزتَ <b className="t2-num">{done}</b> من <b className="t2-num">{required}</b>
          </span>
          {money ? (
            <span className="t2-cbk-money">
              <b className="t2-num">{money}</b> تنتظرك
            </span>
          ) : null}
        </div>
        <p className="t2-drawer-text">
          رحلةٌ كلَّ يومٍ لأسبوع — الجمعةُ لا تُحسب، وفواتُ يومٍ يُعيد العدّ، والمبلغُ ينزل في محفظتك في اليوم الأخير.
        </p>
        <div className="t2-drawer-actions">
          <button type="button" className="t2-button t2-quiet" onClick={() => setOpen(false)}>
            فهمت
          </button>
        </div>
      </DrawerT2>
    </>
  );
}

export function RiderHomeT2({
  name,
  unread,
  nearby,
  eta = null,
  onOpenNotifications,
  onOpenAccount,
  onAskDestination,
  banners,
  map,
  area = null,
  onChangePickup,
  onWomenRide,
  onParcel,
  onHourly,
  unconfirmed = null,
  onOpenUnconfirmed,
}: RiderHomeProps) {
  const navigate = useNavigate();
  const women = useWomenService();
  // **«طرد» بمفتاح سوقه** (§٦٣-ج/٤) — مطفأً تبقى البلاطةُ «قريباً» كما رُسمت ولا يظهر شيءٌ جديد
  const parcel = useParcel();
  // **و«بالساعة» بمفتاح سوقها** (§٦٣-ج/٥) — بالحكم نفسِه
  const hourly = useHourly() && onHourly !== undefined;
  const scheduled = useScheduledRides();
  // **نارُ الاسترداد الأسبوعي** (§٦٣-ج/٨) — `null` حيث المفتاحُ مطفأٌ أو المبلغُ صفر، فلا يُرسم شيء
  const cashback = useWeeklyCashback();
  const { user } = useSession();
  // **«اقتصادي يصل خلال 3 د»** (§٦٢-ج/١٠): أوّلُ فئةٍ لها رقمٌ بترتيب الجواب، **وأسرعُها شارةُ «رحلة»**
  const heroEta = (() => {
    if (!eta) return null;
    const first = Object.entries(eta).find(([, value]) => typeof value === "number");
    return first ? { category: first[0] as keyof typeof VEHICLE_LABEL, minutes: first[1] as number } : null;
  })();
  const fastest = fastestMinutes(eta);

  // **رسالةُ «قريباً»** — تُقال ثمّ تختفي، ولا تفتح شيئاً
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => {
    if (!notice) return;
    const id = window.setTimeout(() => setNotice(null), 2600);
    return () => window.clearTimeout(id);
  }, [notice]);
  const soon = (what: string) => setNotice(`${what} — قريباً`);

  /** **«نسائية» كما تعمل الخدمةُ اليوم**: من عُرضت عليها تبدأ طلبَها بـ«كبتنة فقط»، **ومن لم تُعلن جنسها تُسأل هنا** (§٦٤-ج/٤-٢،
   *  `DeclareGenderSheetT2` — كانت تُرسل إلى «بياناتي» وهي تعرضه ولا تكتبه)، ومن أعلن غيرَ ذلك تُقال له العلّة. */
  const [declaring, setDeclaring] = useState(false);
  function openWomen() {
    if (women.available) onWomenRide?.();
    else if (!user?.gender) setDeclaring(true);
    else setNotice("الخدمة النسائية للراكبات");
  }

  return (
    <div className="t2 t2-page t2-home pb-nav">
      <div className="t2-home-head">
        <span className="t2-home-brand">
          <Wordmark size={15} />
        </span>
        {/* **اسمُ منطقة نقطة الانطلاق** — ولمستُه تفتح دبوسَ الانطلاق؛ وبلا اسمٍ معروفٍ لا شارة */}
        {area ? (
          <button type="button" className="t2-home-place" onClick={onChangePickup}>
            <span className="t2-icon fill" aria-hidden="true">location_on</span>
            <span className="t2-home-place-text">{area}</span>
            <span className="t2-icon t2-home-place-more" aria-hidden="true">expand_more</span>
          </button>
        ) : null}
        <span className="t2-home-spacer" />
        <button type="button" className="t2-home-bell" onClick={onOpenNotifications} aria-label="الإشعارات">
          <span className="t2-icon" aria-hidden="true">notifications</span>
          {unread ? <span className="t2-home-dot" /> : null}
        </button>
        {/* **البرقوقُ لصاحبة الخدمة النسائية** كما رُسمت — من حسابها لا من السِمة */}
        <button
          type="button"
          className={women.available ? "t2-avatar sm women" : "t2-avatar sm"}
          onClick={onOpenAccount}
          aria-label="حسابي"
        >
          {name.slice(0, 1)}
        </button>
      </div>

      {/* **«تأكيدٌ ينتظرك» في أعلى الرئيسية** (`design/PAYMENTS-UNCONFIRMED.md` §٦) — يفتح الصفحةَ التي أخفاها «لاحقاً»، **والحدُّ
          يُقال هنا بسببه المكتوب** (§٧: «السببُ مكتوبٌ في الرئيسية»). ولا شيءَ يُرسم بلا شيءٍ ينتظر أو والمفتاحُ مطفأ */}
      {onOpenUnconfirmed ? <UnconfirmedStripT2 data={unconfirmed} onOpen={onOpenUnconfirmed} /> : null}

      <button type="button" className="t2-home-hero" onClick={onAskDestination}>
        <span className="t2-home-hero-stripe" aria-hidden="true" />
        <span className="t2-home-hero-text">
          <span className="t2-home-hero-title">إلى أين؟</span>
          {heroEta ? (
            <span className="t2-home-hero-sub">
              {VEHICLE_LABEL[heroEta.category]} يصل خلال{" "}
              <b className="t2-home-hero-min" dir="ltr">
                {heroEta.minutes}
              </b>{" "}
              د
            </span>
          ) : null}
        </span>
        <span className="t2-home-hero-go" aria-hidden="true">
          <span className="t2-icon">arrow_back</span>
        </span>
      </button>

      <div className="t2-home-grid">
        <MapCardT2 map={map} nearby={nearby} onAskDestination={onAskDestination} />
        <button type="button" className="t2-home-ride" onClick={onAskDestination}>
          <span className="t2-icon" aria-hidden="true">local_taxi</span>
          <span className="t2-home-ride-label">رحلة</span>
          {/* **شارةُ «3 د»** — أسرعُ ما يصل من الفئات (§٦٢-ج/١٠) */}
          {fastest !== null ? (
            <span className="t2-home-ride-eta">
              <b dir="ltr">{fastest}</b> د
            </span>
          ) : null}
        </button>
        <button
          type="button"
          className="t2-home-ride"
          onClick={() => (parcel && onParcel ? onParcel() : soon("طرد"))}
        >
          <span className="t2-icon" aria-hidden="true">package_2</span>
          <span className="t2-home-ride-label">طرد</span>
        </button>
      </div>

      <div className="t2-svc-row">
        <button type="button" className="t2-svc" onClick={() => soon("المطار")}>
          <span className="t2-icon t2-svc-icon" aria-hidden="true">flight_takeoff</span>
          <span className="t2-svc-title">المطار</span>
          <span className="t2-svc-badge new">جديد</span>
        </button>
        <button
          type="button"
          className="t2-svc"
          onClick={() => (scheduled ? navigate("/account/bookings") : soon("الرحلات المجدولة"))}
        >
          <span className="t2-icon t2-svc-icon" aria-hidden="true">event_upcoming</span>
          <span className="t2-svc-title">مجدولة</span>
        </button>
        {/* **حيث الخدمةُ مطفأةٌ لا يظهر شيءٌ منها** — قاعدةُ اليوم (`lib/women.ts`) */}
        {women.enabled ? (
          <button type="button" className="t2-svc women" onClick={openWomen}>
            <span className="t2-icon t2-svc-icon" aria-hidden="true">woman</span>
            <span className="t2-svc-title">نسائية</span>
          </button>
        ) : null}
        {/* **مشتعلاً تبدأ الطلبَ ولا شارةَ «قريباً»** (§٦٣-ج/٥) — ومطفأً كما رُسمت حرفاً */}
        {hourly ? (
          <button type="button" className="t2-svc" onClick={onHourly}>
            <span className="t2-icon t2-svc-icon" aria-hidden="true">timer</span>
            <span className="t2-svc-title">بالساعة</span>
          </button>
        ) : (
          <button type="button" className="t2-svc soon" onClick={() => soon("بالساعة")}>
            <span className="t2-icon t2-svc-icon" aria-hidden="true">timer</span>
            <span className="t2-svc-title">بالساعة</span>
            <span className="t2-svc-badge soon">قريباً</span>
          </button>
        )}
      </div>

      {cashback ? <CashbackChipT2 cashback={cashback} /> : null}

      {/* **الحسابُ المحدود يُقال في كلِّ فتحة** (قرارُ المالك ٢٠٢٦-٠٨-٣١) — ويظهر بشرطه وحدَه */}
      <PhonePendingNotice variant="t2" />
      <PromoBanners banners={banners} skin={PROMO_SKIN_T2} />

      {notice ? (
        <div className="t2-toast" role="status" aria-live="polite">
          {notice}
        </div>
      ) : null}

      {/* **أعلنت أنها أنثى ⇒ صفحةُ الخدمة (RW1)** كبطاقة R15 بعينها — لا ورقةُ الطلب: تنبيهُ «تم تفعيل الوضع النسائي» يظهر لأوّل
          مرّةٍ مع الإعلان (`WomenModeNotice`)، **وفوق ورقةٍ مفتوحةٍ يغطّي حقلَ البحث فيها** حتى تُغلقه (قِيس بالمتصفّح). وفي RW1 لا
          ورقةَ تحته، وتقرأ ما الخدمةُ قبل طلبها الأوّل. ورجلٌ ⇒ «للراكبات» في الورقة ولا شيءَ بعدها */}
      {women.enabled ? (
        <DeclareGenderSheetT2 open={declaring} onOpenChange={setDeclaring} onFemale={() => navigate("/account/women")} />
      ) : null}
    </div>
  );
}
