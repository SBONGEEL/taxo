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
 *
 * **وما نُزل بلغ من موضعٍ آخر** (§٦١-د/و): الأماكنُ المحفوظةُ في البحث وفي «حسابي»، وآخرُ الرحلات و«أعِد الرحلة» في «رحلاتي»
 * وتفاصيلها، والإحالةُ في «حسابي»، والرصيدُ في «المحفظة»، **والخريطةُ الكاملةُ بلمسة البطاقة** بدل زرِّ «توسيع».
 */

import type { ReactNode } from "react";
import type { MyReferrals, PromoBanner, Ride, SavedPlace, ServiceTile, Wallet } from "@/api/types";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { PhonePendingNotice } from "@/components/PhonePendingNotice";
import { PromoBanners } from "@/components/home/PromoBanners";
import { useExpandable } from "@/components/home/MapCard";
import { useScheduledRides } from "@/lib/bookings";
import { useSession } from "@/lib/session";
import { useWomenService } from "@/lib/women";
import { Wordmark } from "@/taxo2";

import { PROMO_SKIN_T2 } from "./StorefrontT2";
import "@/taxo2";
import "./t2.css";

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

export function RiderHomeT2({
  name,
  unread,
  nearby,
  onOpenNotifications,
  onOpenAccount,
  onAskDestination,
  banners,
  map,
  area = null,
  onChangePickup,
  onWomenRide,
}: RiderHomeProps) {
  const navigate = useNavigate();
  const women = useWomenService();
  const scheduled = useScheduledRides();
  const { user } = useSession();

  // **رسالةُ «قريباً»** — تُقال ثمّ تختفي، ولا تفتح شيئاً
  const [notice, setNotice] = useState<string | null>(null);
  useEffect(() => {
    if (!notice) return;
    const id = window.setTimeout(() => setNotice(null), 2600);
    return () => window.clearTimeout(id);
  }, [notice]);
  const soon = (what: string) => setNotice(`${what} — قريباً`);

  /** **«نسائية» كما تعمل الخدمةُ اليوم**: من عُرضت عليها تبدأ طلبَها بـ«كبتنة فقط»، ومن لم تُعلن جنسها تُعلنه في «بياناتي»
   *  (بابُ اليوم نفسُه)، ومن أعلن غيرَ ذلك تُقال له العلّة. */
  function openWomen() {
    if (women.available) onWomenRide?.();
    else if (!user?.gender) navigate("/account/profile");
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
        <button type="button" className="t2-home-ride" onClick={() => soon("طرد")}>
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
        <button type="button" className="t2-svc soon" onClick={() => soon("بالساعة")}>
          <span className="t2-icon t2-svc-icon" aria-hidden="true">timer</span>
          <span className="t2-svc-title">بالساعة</span>
          <span className="t2-svc-badge soon">قريباً</span>
        </button>
      </div>

      {/* **الحسابُ المحدود يُقال في كلِّ فتحة** (قرارُ المالك ٢٠٢٦-٠٨-٣١) — ويظهر بشرطه وحدَه */}
      <PhonePendingNotice variant="t2" />
      <PromoBanners banners={banners} skin={PROMO_SKIN_T2} />

      {notice ? (
        <div className="t2-toast" role="status" aria-live="polite">
          {notice}
        </div>
      ) : null}
    </div>
  );
}
