/** الرئيسية — TAXO 2.0 «R05» (Claude Design «Rider»)، **مطابقةٌ للتصميم** (§٦١-د) — **في المظهرين**: رُسمت نهاريّاً، والليليُّ برموز إسفلت الهوية نفسِها (§٦٢/٣).
 *
 * **وجهٌ لا منطق**: الشاشةُ (`screens/Home.tsx`) تمرّر الشيءَ نفسَه للوجهين (`RiderHomeProps`)، والخريطةُ عقدةٌ واحدة،
 * والتوسيعُ وزرُّ الجهاز الخلفيُّ من `useExpandable`، واللافتاتُ من `PromoBanners` بجلدها.
 *
 * **والقيمُ الحيّةُ من بياناتٍ حقيقيةٍ أو لا شيء** (§٦١-د/د): شارةُ الموقع اسمُ منطقة نقطة الانطلاق من Mapbox (`area`)، وعددُ
 * الكباتن حولك من `GET /drivers/nearby`، والحرفُ من الحساب. **و«يصل خلال 3 د» وشارةُ «3 د» لا مصدرَ لهما اليوم** — فلا
 * يُرسم مكانَهما شيء (أُبلغ المالك). **و«30%» في اللافتة من حقلها `headline`** (§٦٢-ج/٢٦، «الرقم الكبير» في اللوحة) — وبلا رقمٍ لا موضعَ يُحجز.
 *
 * **والبلاطاتُ الأربعُ كما رُسمت** (§٦١-د/أ–ج): «المطار» بـ«جديد» و«طرد» و«بالساعة» **رسالةُ «قريباً» عند اللمس ولا شيءَ غيرُها**،
 * و«مجدولة» رحلاتُه المجدولة (بمفتاح سوقها)، و«نسائية» **تبدأ الطلبَ بـ«كبتنة فقط» وهي تغيّره بنفسها** — كما تعمل الخدمةُ اليوم.
 * **و«طرد» حيث مفتاحُه مشتعلٌ تبدأ طلبَ طرد** (§٦٣-ج/٤، `onParcel`) — ومطفأً «قريباً» كما كانت. **و«بالساعة» مثلُها**
 * (§٦٣-ج/٥، `onHourly`): مشتعلاً تبدأ طلبَ ساعاتٍ بلا شارة «قريباً»، ومطفأً كما رُسمت. **و«المطار» مثلُهما** (§٦٣-ج/٢،
 * `onAirport`): مشتعلاً يفتح البحثَ وفيه «مطار» — وكانت «قريباً» دائماً والخدمةُ مبنيّة (قِيس على S21 ٢٠٢٦-١٠-٠٨).
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
  VehicleCategory,
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
import { BecomeDriverButton } from "@/components/t2/BecomeButton";
import { PromoBanners } from "@/components/home/PromoBanners";
import { useExpandable } from "@/components/home/MapCard";
import { fastestMinutes, type CategoryMinutes } from "@/lib/arrival";
import { cashbackDaysText, useIntercityService, useScheduledRides, useWeeklyCashback } from "@/lib/bookings";
import { arabicPart } from "@/lib/arabic-name";
import { useFeature } from "@/lib/config";
import { useHourly } from "@/lib/hourly";
import { VEHICLE_LABEL } from "@/lib/labels";
import { useParcel, useParcelFetch } from "@/lib/parcel";
import { useSession } from "@/lib/session";
import { useTheme } from "@/lib/theme";
import { formatMoney } from "@/lib/utils";
import { useWomenService } from "@/lib/women";
import { Icon, Wordmark } from "@/taxo2";
import { carKey, carSrc, carSrcSet } from "@/taxo2/cars";
import { spansLast } from "@/lib/home-cars-core";
import { AddWidgetCard } from "@/components/t2/AddWidgetCard";

import { DrawerT2 } from "./DrawerT2";
import { HomeCategoriesT2, HomeSearchT2, type QuickChip } from "./HomeCarsT2";
import { PROMO_SKIN_T2 } from "./StorefrontT2";
import { DeclareGenderSheetT2 } from "./WomenServiceT2";
import { UnconfirmedStripT2 } from "./UnconfirmedT2";
import "@/taxo2";
import "./t2.css";
import "./home-kit.css";
import "./cashback.css"; import { tr } from "@/lib/i18n";
import { REFRESH_LABEL } from "@/lib/location-help";

/** خصائصُ الرئيسية (R05) — **كانت في الوجه القديم** (`components/home/RiderHome.tsx`) ونُزع (§٦٢/٣). */
export interface RiderHomeProps {
  /** **الموقعُ مرفوضٌ أو GPS مطفأ** (أمرُ المالك ٢٠٢٦-١١-١٩/٥) — رسالةٌ قصيرةٌ بزرٍّ يفتح إعدادَ الموقع (`null` في المتصفّح: لا صفحةَ
   *  إعدادٍ يفتحها) وزرِّ الاختيار على الخريطة. و`null` كلُّه حين الموقعُ معروف. */
  /** **«لم نتمكن من تحديد موقعك»** (SPEC §١٠٩-ج) — النصُّ بسببه، و«تحديث الموقع الحالي» بحالة تحميل، والزرُّ الثاني بحسب السبب */
  locationOff?: {
    message: string;
    action: { label: string; onPress: () => void } | null;
    refreshing: boolean;
    onRefresh: () => void;
    onPickOnMap: () => void;
  } | null;
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
  /** **اقتراحُ الوجهة الذكيّ** (SPEC §١٠٣ C/35) — من وجهاته هو في هذا الهاتف؛ `null` حيث المفتاحُ مطفأٌ أو لا نمط. */
  suggestion?: { address: string; onPick: () => void } | null;
  /** **«إلى أين؟» يفتح الخريطةَ بدبوس** (أمرُ المالك ٢٠٢٦-١١-٠٢، SPEC §٩٣-أ) — والبحثُ رابطٌ في ورقة الدبوس؛ وغيابُه يُبقي البحث. */
  onPickOnMap?: () => void;
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
  /** **أزرارُ الخريطة المفتوحة** (أمرُ المالك ١٨/١١ السابع): «الازدحام» و«أضف مكاناً» — تظهر والخريطةُ مفتوحةٌ وحدَها */
  mapTools?: ReactNode;
  /** اسمُ منطقة نقطة الانطلاق لشارة الرأس (`null` = لا شارة)، وفتحُ دبوس الانطلاق من الشارة، وبدءُ الطلب بـ«كبتنة فقط» (§٦١-د). */
  area?: string | null;
  onChangePickup?: () => void;
  onWomenRide?: () => void;
  /** **بدءُ طلب طرد** (§٦٣-ج/٤) — منتقي الوجهة ثمّ ورقتُه؛ والبلاطةُ لا تناديه إلا حيث المفتاحُ مشتعل. */
  onParcel?: () => void;
  /** **بدءُ طلب ساعات** (§٦٣-ج/٥) — منتقي الوجهة بـ«بلا وجهة» ثمّ ورقتُها؛ والبلاطةُ لا تناديه إلا حيث المفتاحُ مشتعل. */
  onHourly?: () => void;
  /** **بدءُ «أحضر غرضي»** (§٧٢-ج/١، لوحتُه R1) — «أين غرضك؟» ثمّ ورقتُه؛ والبلاطةُ لا تُرسم إلا حيث مفتاحُه مشتعل. */
  onFetch?: () => void;
  /** **بدءُ رحلةٍ إلى المطار** (§٦٣-ج/٢) — منتقي الوجهة وفيه «مطار»؛ ورسمُ المطار يُحسب في الخلفية حين تقع الوجهةُ في مضلّعه. */
  onAirport?: () => void;
  /** **ما ينتظر تأكيدَه** (`design/PAYMENTS-UNCONFIRMED.md` §٦) — شريطُ «تأكيدٌ ينتظرك» أعلى الرئيسية؛ و`null` حيث المفتاحُ مطفأ. */
  unconfirmed?: RiderUnconfirmed | null;
  onOpenUnconfirmed?: () => void;
  /** **الرئيسيّةُ الجديدة** (أمرُ المالك ٢١/١١ الثاني، SPEC §١١١، مفتاحُ `home_cars` «سيارات الرئيسية») — «إلى أين؟» وشرائحُه، ودوّارُ فئات
   *  الدولة المشتعلة، وشبكةُ الخدمات؛ و`null` حيث المفتاحُ مطفأ **فتبقى الرئيسيّةُ كما كانت قبلها حرفاً**. */
  homeCars?: {
    categories: VehicleCategory[];
    selected: VehicleCategory;
    onPick: (category: VehicleCategory) => void;
    /** مقاعدُ كلِّ فئةٍ من صفّها في `/config` */
    seats: Partial<Record<VehicleCategory, number>>;
    /** **شرائحُ أماكنَ حقيقيّة** (`quickChips`) ولمستُها تختار الوجهة */
    chips: QuickChip[];
    onChip: (chip: QuickChip) => void;
  } | null;
}


/** «كم كبتناً حولك» بعربيةٍ تُقرأ — **العددُ وحدَه بلا مهلة**. **وبيتُها هنا لـR05 وR07 معاً** («6 كباتن حولك الآن» أثناء البحث). */
/** **اختصارٌ ذكيٌّ لاسم المنطقة لا حرفٌ واحد** (أمرُ المالك ٢٠٢٦-١١-٢٠ الثالث §١): الكلمةُ الإداريّةُ في أوّله تُحذف لأن الشارةَ تقول
 *  «أين» لا «أيُّ تقسيم» («شعبية طرابلس» ⇐ «طرابلس»، «ولاية وهران» ⇐ «وهران»)، والمزدوجُ يُعرض عربيُّه، ولا يُكتب حرفٌ لم يكن في
 *  الاسم. **والاسمُ كاملاً في `title` و`aria-label`** — قارئُ الشاشة يقرؤه بلا اختصار. */
const AREA_PREFIX = /^(?:شعبية|شعبيّة|بلدية|بلديّة|ولاية|محافظة|لواء|قضاء|دائرة)\s+/;
export function shortArea(area: string): string {
  const name = arabicPart(area).trim();
  const bare = name.replace(AREA_PREFIX, "").trim();
  return bare || name;
}

export function nearbyLabel(count: number): string {
  if (count === 1) return tr("كبتن حولك");
  if (count === 2) return tr("كبتنان حولك");
  if (count <= 10) return tr("كباتن حولك");
  return tr("كبتناً حولك");
}

/** **الخريطةُ بطاقةً** — والعقدةُ هي هي في الحالين. **ولا زرَّ «توسيع»** كما رُسمت: **لمسةُ البطاقة تفتحها** (§٦١-د/و). */
function MapCardT2({
  map,
  nearby,
  onAskDestination,
  tools,
}: {
  map: RiderHomeProps["map"];
  nearby: number;
  onAskDestination: () => void;
  tools?: ReactNode;
}) {
  const [open, setOpen] = useExpandable();
  return (
    <div className={open ? "t2-home-map open" : "t2-home-map"}>
      {map}
      {!open ? (
        <>
          <button type="button" className="t2-home-map-tap" onClick={() => setOpen(true)} aria-label={tr("فتح الخريطة")} />
          {nearby > 0 ? (
            <span className="t2-home-near">
              {nearby > 2 ? <span className="t2-num">{nearby}</span> : null}
              {nearbyLabel(nearby)}
            </span>
          ) : null}
        </>
      ) : (
        <>
          {tools ? <div className="t2-map-tools">{tools}</div> : null}
          <button type="button" className="t2-home-close" onClick={() => setOpen(false)} aria-label={tr("إغلاق الخريطة")}>
            <Icon name="close" />
          </button>
          {/* **وزرُّ العمل في متناوله وهي مفتوحة** — فلا يُغلقها ليطلب */}
          <div className="t2-home-map-action">
            <button type="button" className="t2-button action" onClick={onAskDestination}>
              {tr("إلى أين؟ اطلب رحلة")}
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
  if (cashback.rode_today) return tr("ركبتَ اليوم — نارُك مشتعلة");
  if (cashback.friday) return tr("الجمعةُ لا تُحسب");
  return tr("رحلةٌ اليوم تُبقيها مشتعلة");
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
          <Icon name="local_fire_department" fill />
        </span>
        <span className="t2-cbk-text">
          <span className="t2-cbk-top">
            <span className="t2-cbk-days">{cashbackDaysText(left)}</span>
            {money ? (
              <span className="t2-cbk-money">
                <b className="t2-num">{money}</b>{" "}{tr("تنتظرك")}
              </span>
            ) : null}
          </span>
          <span className="t2-cbk-sub">{cashbackLine(cashback)}</span>
        </span>
        <Icon name="chevron_left" className="t2-cbk-more" />
      </button>

      <DrawerT2 open={open} onOpenChange={setOpen} title={tr("الاسترداد الأسبوعي")}>
        {/* **الأيامُ خاناتٌ لا نسبة** — ما أنجزه بالجمر وما بقي بحافّة، من عددين أرسلتهما الخلفية */}
        <div className="t2-cbk-track" role="img" aria-label={tr("أنجزتَ {0} من {1}", { 0: done, 1: required })}>
          {Array.from({ length: required }, (_, index) => (
            <span key={index} className={index < done ? "t2-cbk-seg on" : "t2-cbk-seg"} />
          ))}
        </div>
        <div className="t2-cbk-track-note">
          <span>
            {tr("أنجزتَ")}{" "}<b className="t2-num">{done}</b>{" "}{tr("من")}{" "}<b className="t2-num">{required}</b>
          </span>
          {money ? (
            <span className="t2-cbk-money">
              <b className="t2-num">{money}</b>{" "}{tr("تنتظرك")}
            </span>
          ) : null}
        </div>
        <p className="t2-drawer-text">
          {tr("رحلةٌ كلَّ يومٍ لأسبوع — الجمعةُ لا تُحسب، وفواتُ يومٍ يُعيد العدّ، والمبلغُ ينزل في محفظتك في اليوم الأخير.")}
        </p>
        <div className="t2-drawer-actions">
          <button type="button" className="t2-button t2-quiet" onClick={() => setOpen(false)}>
            {tr("فهمت")}
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
  onPickOnMap,
  banners,
  map,
  mapTools,
  area = null,
  onChangePickup,
  onWomenRide,
  onParcel,
  onHourly,
  onFetch,
  onAirport,
  unconfirmed = null,
  onOpenUnconfirmed,
  suggestion = null,
  locationOff = null,
  homeCars = null,
}: RiderHomeProps) {
  const navigate = useNavigate();
  const women = useWomenService();
  const { dark, setChoice: setThemeChoice } = useTheme();
  // **«طرد» بمفتاح سوقه** (§٦٣-ج/٤) — مطفأً تبقى البلاطةُ «قريباً» كما رُسمت ولا يظهر شيءٌ جديد
  const parcel = useParcel();
  // **و«بالساعة» بمفتاح سوقها** (§٦٣-ج/٥) — بالحكم نفسِه
  const { user } = useSession();
  const hourly = useHourly() && onHourly !== undefined;
  // **و«أغراضي» (أحضر غرضي) بمفتاحها** (§٧٢-ج/١) — **مطفأةً لا تُرسم أصلاً**: لا «قريباً» لخدمةٍ جديدة (§٧٢-أ/٢)
  const fetchOn = useParcelFetch() && onFetch !== undefined;
  // **«تسوّق» — بابُ TAXO MARKET** (§٧٢-هـ، لوحتُه E1): شريطٌ تحت صفّ الخدمات **بمفتاح التوصيل** — مطفأً (وهو مطفأٌ حتى يُبنى) «قريباً»
  // والنقرُ يقول «قريباً» ولا شيءَ غيرَه؛ ومشتعلاً يفتح `/services/market`
  const market = useFeature(user?.country_code, "delivery_enabled");
  // **«أضف ودجت TAXO لشاشتك»** (أمرُ المالك ٢١/١١ الثالث، البند ٣) — خلف مفتاح الودجات لدولته
  const widgetsPlus = useFeature(user?.country_code, "rider_widgets_plus");
  // **و«المطار» بمفتاح سوقه** (§٦٣-ج/٢، صفُّه في جدول الخدمات: «يفتحها حين يُشعَل وإلا قريباً») — قِيس على S21 ٢٠٢٦-١٠-٠٨:
  // البلاطةُ كانت «قريباً» دائماً والخدمةُ مشتعلةٌ ومبنيّة، فلا بابَ إليها من الرئيسية
  const airport = useFeature(user?.country_code, "airport_enabled") && onAirport !== undefined;
  const scheduled = useScheduledRides();
  // **نارُ الاسترداد الأسبوعي** (§٦٣-ج/٨) — `null` حيث المفتاحُ مطفأٌ أو المبلغُ صفر، فلا يُرسم شيء
  const cashback = useWeeklyCashback();
  // **«اقتصادي يصل خلال 3 د»** (§٦٢-ج/١٠): أوّلُ فئةٍ لها رقمٌ بترتيب الجواب، **وأسرعُها شارةُ «رحلة»**
  const heroEta = (() => {
    if (!eta) return null;
    const first = Object.entries(eta).find(([, value]) => typeof value === "number");
    return first ? { category: first[0] as keyof typeof VEHICLE_LABEL, minutes: first[1] as number } : null;
  })();
  const fastest = fastestMinutes(eta);
  // **«إلى أين؟» دبوسٌ على الخريطة، و«رحلة» بين المدن** (أمرُ المالك ٢٠٢٦-١١-٠٢، SPEC §٩٣-أ). **وحيث «بين المدن» مطفأةٌ يبقى «رحلة»
  // طلبَ رحلةٍ كما كان** — بابٌ يعمل لا يُحجب بـ«قريباً» لأن خدمةً أخرى لم تُشعَل
  const whereTo = onPickOnMap ?? onAskDestination;
  const intercity = useIntercityService();

  // **رسالةُ «قريباً»** — تُقال ثمّ تختفي، ولا تفتح شيئاً
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => {
    if (!notice) return;
    const id = window.setTimeout(() => setNotice(null), 2600);
    return () => window.clearTimeout(id);
  }, [notice]);
  const soon = (what: string) => setNotice(tr("{0} — قريباً", { 0: what }));

  /** **شبكةُ الخدمات في الرئيسيّة الجديدة** (الجزء ٢/٤) — **الحيّةُ وحدَها** بأفعالها القائمة نفسِها؛ ولا «قريباً» فيها. */
  const services: ServiceItem[] = [
    {
      key: "ride",
      big: true,
      name: tr("رحلة"),
      sub: intercity ? tr("بين المدن") : tr("سيارة إلى وجهتك"),
      art: { car: homeCars?.selected ?? "economy" },
      eta: fastest !== null && !intercity ? fastest : null,
      onPress: intercity ? () => navigate("/account/intercity") : onAskDestination,
    },
    ...(parcel && onParcel
      ? [{ key: "parcel", big: true, name: tr("طرد"), sub: tr("أرسل غرضاً مع كبتن"), art: { img: "parcel" }, onPress: onParcel }]
      : []),
    ...(airport && onAirport ? [{ key: "airport", name: tr("المطار"), sub: tr("رحلتك إلى المطار"), art: { img: "airport" }, onPress: onAirport }] : []),
    ...(scheduled
      ? [{ key: "scheduled", name: tr("مجدولة"), sub: tr("رحلاتك المحجوزة"), art: { img: "scheduled" }, onPress: () => navigate("/account/bookings") }]
      : []),
    ...(women.enabled
      ? [{ key: "women", name: tr("نسائية"), sub: tr("كبتنة لرحلتك"), art: { icon: "woman" }, onPress: openWomen, tone: "women" as const }]
      : []),
    ...(hourly && onHourly ? [{ key: "hourly", name: tr("بالساعة"), sub: tr("سيارة بالساعة"), art: { img: "hourly" }, onPress: onHourly }] : []),
    ...(fetchOn && onFetch ? [{ key: "fetch", name: tr("أغراضي"), sub: tr("نُحضر غرضك إليك"), art: { img: "fetch" }, onPress: onFetch }] : []),
  ];

  /** **«نسائية» كما تعمل الخدمةُ اليوم**: من عُرضت عليها تبدأ طلبَها بـ«كبتنة فقط»، **ومن لم تُعلن جنسها تُسأل هنا** (§٦٤-ج/٤-٢،
   *  `DeclareGenderSheetT2` — كانت تُرسل إلى «بياناتي» وهي تعرضه ولا تكتبه)، ومن أعلن غيرَ ذلك تُقال له العلّة. */
  const [declaring, setDeclaring] = useState(false);
  function openWomen() {
    if (women.available) onWomenRide?.();
    else if (!user?.gender) setDeclaring(true);
    else setNotice(tr("الخدمة النسائية للراكبات"));
  }

  return (
    <div className={homeCars ? "t2 t2-page t2-home hm pb-nav" : "t2 t2-page t2-home pb-nav"}>
      <div className="t2-home-head">
        <span className="t2-home-brand">
          <Wordmark size={15} />
        </span>
        {/* **اسمُ منطقة نقطة الانطلاق** — ولمستُه تفتح دبوسَ الانطلاق؛ وبلا اسمٍ معروفٍ لا شارة */}
        {area ? (
          <button type="button" className="t2-home-place" onClick={onChangePickup} title={area} aria-label={area}>
            <Icon name="location_on" fill />
            <span className={shortArea(area).includes(" ") ? "t2-home-place-text two-words" : "t2-home-place-text"}>{shortArea(area)}</span>
            <Icon name="expand_more" className="t2-home-place-more" />
          </button>
        ) : null}
        <span className="t2-home-spacer" />
        {/* **النهاريُّ والليليُّ بلمسة** (أمرُ المالك ٢٠٢٦-١١-٠٢، SPEC §٩٣-ج) — الاختيارُ نفسُه الذي في «حسابي ← الإعدادات»
            (`taxo.theme`)، فيُحفظ ويُرى هناك؛ ووجهُه وجهُ الجرس بجانبه */}
        <button
          type="button"
          className="t2-home-bell t2-home-theme"
          onClick={() => setThemeChoice(dark ? "light" : "dark")}
          aria-label={dark ? tr("الوضع النهاري") : tr("الوضع الليلي")}
        >
          <Icon name={dark ? "light_mode" : "dark_mode"} />
        </button>
        <button type="button" className="t2-home-bell" onClick={onOpenNotifications} aria-label={tr("الإشعارات")}>
          <Icon name="notifications" />
          {unread ? <span className="t2-home-dot" /> : null}
        </button>
        {/* **البرقوقُ لصاحبة الخدمة النسائية** كما رُسمت — من حسابها لا من السِمة */}
        <button
          type="button"
          className={women.available ? "t2-avatar sm women" : "t2-avatar sm"}
          onClick={onOpenAccount}
          aria-label={tr("حسابي")}
        >
          {name.slice(0, 1)}
        </button>
      </div>

      {/* **«تأكيدٌ ينتظرك» في أعلى الرئيسية** (`design/PAYMENTS-UNCONFIRMED.md` §٦) — يفتح الصفحةَ التي أخفاها «لاحقاً»، **والحدُّ
          يُقال هنا بسببه المكتوب** (§٧: «السببُ مكتوبٌ في الرئيسية»). ولا شيءَ يُرسم بلا شيءٍ ينتظر أو والمفتاحُ مطفأ */}
      {onOpenUnconfirmed ? <UnconfirmedStripT2 data={unconfirmed} onOpen={onOpenUnconfirmed} /> : null}

      {locationOff ? (
        <div className="t2-location-off" role="status">
          <span className="t2-location-off-text">{tr(locationOff.message)}</span>
          <button
            type="button"
            className="t2-chip t2-location-refresh"
            onClick={locationOff.onRefresh}
            disabled={locationOff.refreshing}
            aria-busy={locationOff.refreshing}
          >
            <Icon name="my_location" />
            {locationOff.refreshing ? tr("جارٍ تحديد موقعك…") : tr(REFRESH_LABEL)}
          </button>
          {locationOff.action ? (
            <button type="button" className="t2-chip" onClick={locationOff.action.onPress}>
              {tr(locationOff.action.label)}
            </button>
          ) : null}
          <button type="button" className="t2-chip" onClick={locationOff.onPickOnMap}>
            {tr("اختر على الخريطة")}
          </button>
        </div>
      ) : null}

      {homeCars ? (
        <>
          <HomeSearchT2 onWhereTo={whereTo} eta={heroEta} chips={homeCars.chips} onChip={homeCars.onChip} suggestion={suggestion} />
          <HomeCategoriesT2
            categories={homeCars.categories}
            selected={homeCars.selected}
            eta={eta}
            seats={homeCars.seats}
            onPick={homeCars.onPick}
          />
          <HomeServicesT2 items={services} />
          <div className="hm-map">
            <MapCardT2 map={map} nearby={nearby} onAskDestination={whereTo} tools={mapTools} />
          </div>
          {/* **«تسوّق» حين يشتعل وحدَه** (الجزء ١/٤): كان يطلّ مقطوعاً بـ«قريباً» تحت شريط التنقّل — والرئيسيّةُ الجديدةُ لا تعرض «قريباً» */}
          {market ? (
            <button type="button" className="t2-promo t2-mk-strip" onClick={() => navigate("/services/market")}>
              <span className="t2-promo-row">
                <Icon name="shopping_bag" className="t2-mk-strip-icon" />
                <span className="t2-promo-text">
                  <span className="t2-promo-title">{tr("تسوّق — TAXO MARKET")}</span>
                  <span className="t2-promo-body">{tr("مطاعم ومتاجر قريبة، يوصلها كباتن TAXO.")}</span>
                </span>
              </span>
            </button>
          ) : null}
        </>
      ) : (
      <>
      <button type="button" className="t2-home-hero" onClick={whereTo}>
        <span className="t2-home-hero-stripe" aria-hidden="true" />
        <span className="t2-home-hero-text">
          <span className="t2-home-hero-title">{tr("إلى أين؟")}</span>
          {heroEta ? (
            <span className="t2-home-hero-sub">
              {VEHICLE_LABEL[heroEta.category]}{" "}{tr("يصل خلال")}{" "}
              <b className="t2-home-hero-min" dir="ltr">
                {heroEta.minutes}
              </b>{" "}
              {tr("د")}
            </span>
          ) : null}
        </span>
        <span className="t2-home-hero-go" aria-hidden="true">
          <Icon name="arrow_back" />
        </span>
      </button>

      {/* **اقتراحُ الوجهة** (SPEC §١٠٣ C/35) — لمسةٌ تختارها وجهةً كما يختار «أماكني» */}
      {suggestion ? (
        <div className="t2-home-places">
          <button type="button" className="t2-home-chip" onClick={suggestion.onPick}>
            <Icon name="auto_awesome" />
            <span>{tr("إلى {0}؟", { 0: suggestion.address })}</span>
          </button>
        </div>
      ) : null}

      <div className="t2-home-grid">
        <MapCardT2 map={map} nearby={nearby} onAskDestination={whereTo} tools={mapTools} />
        <button
          type="button"
          className="t2-home-ride"
          onClick={intercity ? () => navigate("/account/intercity") : onAskDestination}
        >
          <Icon name="local_taxi" />
          <span className="t2-home-ride-label">{tr("رحلة")}</span>
          {/* **شارةُ «3 د»** — أسرعُ ما يصل من الفئات (§٦٢-ج/١٠)؛ **ولا تُرسم والزرُّ «بين المدن»**: دقائقُ أقرب كبتنٍ لا تخصّ رحلةً بين مدينتين */}
          {fastest !== null && !intercity ? (
            <span className="t2-home-ride-eta">
              <b dir="ltr">{fastest}</b>{" "}{tr("د")}
            </span>
          ) : null}
        </button>
        <button
          type="button"
          className="t2-home-ride"
          onClick={() => (parcel && onParcel ? onParcel() : soon(tr("طرد")))}
        >
          <Icon name="package_2" />
          <span className="t2-home-ride-label">{tr("طرد")}</span>
        </button>
      </div>

      {/* **خمسُ بلاطاتٍ خمسةُ أعمدة** (لوحةُ «أحضر غرضي» R1) — لا بلاطةَ وحيدةٌ في صفٍّ ثانٍ */}
      <div className={3 + (women.enabled ? 1 : 0) + (fetchOn ? 1 : 0) === 5 ? "t2-svc-row five" : "t2-svc-row"}>
        <button type="button" className="t2-svc" onClick={() => (airport && onAirport ? onAirport() : soon(tr("المطار")))}>
          <Icon name="flight_takeoff" className="t2-svc-icon" />
          <span className="t2-svc-title">{tr("المطار")}</span>
          <span className="t2-svc-badge new">{tr("جديد")}</span>
        </button>
        <button
          type="button"
          className="t2-svc"
          onClick={() => (scheduled ? navigate("/account/bookings") : soon(tr("الرحلات المجدولة")))}
        >
          <Icon name="event_upcoming" className="t2-svc-icon" />
          <span className="t2-svc-title">{tr("مجدولة")}</span>
        </button>
        {/* **حيث الخدمةُ مطفأةٌ لا يظهر شيءٌ منها** — قاعدةُ اليوم (`lib/women.ts`) */}
        {women.enabled ? (
          <button type="button" className="t2-svc women" onClick={openWomen}>
            <Icon name="woman" className="t2-svc-icon" />
            <span className="t2-svc-title">{tr("نسائية")}</span>
          </button>
        ) : null}
        {/* **مشتعلاً تبدأ الطلبَ ولا شارةَ «قريباً»** (§٦٣-ج/٥) — ومطفأً كما رُسمت حرفاً */}
        {hourly ? (
          <button type="button" className="t2-svc" onClick={onHourly}>
            <Icon name="timer" className="t2-svc-icon" />
            <span className="t2-svc-title">{tr("بالساعة")}</span>
          </button>
        ) : (
          <button type="button" className="t2-svc soon" onClick={() => soon(tr("بالساعة"))}>
            <Icon name="timer" className="t2-svc-icon" />
            <span className="t2-svc-title">{tr("بالساعة")}</span>
            <span className="t2-svc-badge soon">{tr("قريباً")}</span>
          </button>
        )}
        {fetchOn ? (
          <button type="button" className="t2-svc" onClick={onFetch}>
            <Icon name="inventory_2" className="t2-svc-icon" />
            <span className="t2-svc-title">{tr("أغراضي")}</span>
          </button>
        ) : null}
      </div>

      <button
        type="button"
        className="t2-promo t2-mk-strip"
        onClick={() => (market ? navigate("/services/market") : soon(tr("تسوّق")))}
      >
        <span className="t2-promo-row">
          <Icon name="shopping_bag" className="t2-mk-strip-icon" />
          <span className="t2-promo-text">
            <span className="t2-promo-title">{tr("تسوّق — TAXO MARKET")}</span>
            <span className="t2-promo-body">{tr("مطاعم ومتاجر قريبة، يوصلها كباتن TAXO.")}</span>
          </span>
          {market ? null : <span className="t2-svc-badge soon t2-mk-strip-soon">{tr("قريباً")}</span>}
        </span>
      </button>
      </>
      )}

      <AddWidgetCard kind="request" enabled={widgetsPlus} body={tr("اطلب رحلتك من الشاشة الرئيسيّة بلمسة.")} variant="card" />
      {cashback ? <CashbackChipT2 cashback={cashback} /> : null}

      {/* **«كن سائقاً» شريطاً** (أمرُ المالك ٢٠٢٦-١١-٠٢، الثاني) — تحت الطلب والخدمات لا فوقها، والعريضُ أعلى «حسابي» */}
      <BecomeDriverButton compact />

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

interface ServiceItem {
  key: string;
  name: string;
  sub: string;
  big?: boolean;
  /** رسمُ الخدمة: سيارةُ TAXO للفئة، أو رسمٌ ثلاثيُّ الأبعاد من `public/svc/`، أو أيقونةٌ بالنمط C */
  art: { car?: VehicleCategory; img?: string; icon?: string };
  eta?: number | null;
  tone?: "women";
  onPress: () => void;
}

const SVC = `${import.meta.env.BASE_URL}svc/`;

function ServiceArt({ art, big }: { art: ServiceItem["art"]; big: boolean }) {
  if (art.car) {
    const key = carKey("local_taxi", art.car);
    return (
      <span className="hc-car" aria-hidden="true">
        <img className="d" src={carSrc(key, false)} srcSet={carSrcSet(key, false)} sizes="200px" alt="" decoding="async" loading="lazy" />
        <img className="n" src={carSrc(key, true)} srcSet={carSrcSet(key, true)} sizes="200px" alt="" decoding="async" loading="lazy" />
      </span>
    );
  }
  if (art.img) {
    const size = big ? 192 : 96;
    return (
      <img src={`${SVC}${art.img}-${size}.webp`} srcSet={`${SVC}${art.img}-96.webp 96w, ${SVC}${art.img}-192.webp 192w`} sizes={big ? "120px" : "40px"} alt="" decoding="async" loading="lazy" />
    );
  }
  return art.icon ? <Icon name={art.icon} fill /> : null;
}

/** **شبكةُ الخدمات بلا فراغ** — الكبيرتان أوّلُ صفّ (وإن غابت «طرد» امتدّت «رحلة»)، والبقيّةُ عمودان، **والفردُ يمدّ آخرَه** (`spansLast`). */
function HomeServicesT2({ items }: { items: ServiceItem[] }) {
  const big = items.filter((item) => item.big);
  const small = items.filter((item) => !item.big);
  const wideLast = spansLast(small.length);
  return (
    <section className="hm-svc" aria-label={tr("الخدمات")}>
      {big.map((item) => (
        <button
          key={item.key}
          type="button"
          className={big.length === 1 ? "hm-svc-big hm-svc-item-wide" : "hm-svc-big"}
          style={big.length === 1 ? { gridColumn: "1 / -1" } : undefined}
          onClick={item.onPress}
        >
          <span className="hm-svc-name">{item.name}</span>
          <span className="hm-svc-sub">{item.sub}</span>
          {typeof item.eta === "number" ? (
            <span className="hm-svc-eta">
              <b dir="ltr">{item.eta}</b>{" "}{tr("د")}
            </span>
          ) : null}
          <span className={item.art.img ? `hm-svc-art-big ${item.art.img}` : "hm-svc-art-big"} aria-hidden="true">
            <ServiceArt art={item.art} big />
          </span>
        </button>
      ))}
      {small.map((item, index) => (
        <button
          key={item.key}
          type="button"
          className={["hm-svc-item", item.tone, wideLast && index === small.length - 1 ? "wide" : null].filter(Boolean).join(" ")}
          onClick={item.onPress}
        >
          <span className="hm-svc-art" aria-hidden="true">
            <ServiceArt art={item.art} big={false} />
          </span>
          <span className="hm-svc-text">
            <span className="hm-svc-name">{item.name}</span>
            <span className="hm-svc-sub">{item.sub}</span>
          </span>
        </button>
      ))}
    </section>
  );
}
