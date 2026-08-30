/** **الشاشة الرئيسة للراكب — من ملفّ التصميم `home Rider`.**
 *
 * **وصفحةٌ تُمرَّر لا خريطةٌ ملءَ الشاشة**: الخريطةُ بطاقةُ ١٧٠ في أعلاها وفي
 * قاعها «إلى أين؟»، وتحتها الأماكنُ والبلاطاتُ واللافتةُ والإحالةُ وآخرُ
 * الرحلات. **وطورُ الطلب يبقى كما هو** — من ضغط «إلى أين؟» رأى الخريطةَ ملءَ
 * الشاشة كما كانت.
 *
 * ## والأرقامُ من السوق الحيِّ لا من الرسم (قرارُ المالك 2026-08-30)
 *
 * التصميمُ ليبيٌّ بالكامل (`د.ل` · طرابلس · «واربح 2 د.ل») **وليبيا مغلقة**.
 * **فكلُّ رقمٍ هنا مقروءٌ من بابه**: الرصيدُ من `GET /wallet/me`، وجائزةُ
 * الإحالة من `GET /me/referrals`، والأجرةُ من صفِّ الرحلة. **ولا مبلغَ
 * مخبوزٌ في شاشة مالٍ** (§14).
 *
 * ## وثلاثةٌ لا تُرسم لأنها لا تُقاس
 *
 * 1. **«دقيقتان» في شارة الكباتن**: عددُ القريبين يُقرأ من `drivers`،
 *    **ومهلةُ الوصول لا تُحسب قبل أن تُعرف نقطةُ الالتقاط** — ورقمٌ يُرسم
 *    ولا يُقاس وعدٌ يعدّه صاحبُه ولا يجده. **فالشارةُ عددٌ بلا مهلة.**
 * 2. **«طرابلس» تحت الاسم**: لا حقلَ مدينةٍ في أيِّ حمولة، **ومدينةٌ تُخمَّن
 *    من إحداثيّةٍ حسابٌ في الجهاز**. فيُعرض **عنوانُ موقعه حين يُعرف** وإلا
 *    فلا سطر.
 * 3. **«المطار» ثالثَ الاختصارات**: الاثنان الأولان **أماكنُه المحفوظة**،
 *    **والمطارُ ليس مكاناً محفوظاً بل بلاطةُ خدمةٍ في الشبكة تحتها** — ورسمُه
 *    اختصاراً يفتح بابين لشيءٍ واحد (الشكلُ الثامن).
 */

import {
  Bell,
  Briefcase,
  Gift,
  House,
  MapPin,
  Star,
  Wallet as WalletIcon,
} from "lucide-react";
import type { ReactNode } from "react";

import type {
  MyReferrals,
  PromoBanner,
  Ride,
  SavedPlace,
  ServiceTile,
  Wallet,
} from "@/api/types";
import { PromoBanners } from "@/components/home/PromoBanners";
import { ServiceTiles } from "@/components/home/ServiceTiles";
import { formatMoney } from "@/lib/utils";

/** أيقونةُ المكان المحفوظ — **من عموده `icon` لا من نصِّ تسميته**: التسميةُ
 *  يكتبها صاحبُها بيده، **ومطابقةُ نصٍّ حرٍّ تُخطئ أوّلَ «بيت أمي»**. وهي
 *  الثلاثةُ نفسُها في `screens/Places.tsx` — ولو زادت رابعةٌ زادت هناك أوّلاً. */
const PLACE_MARK: Record<string, typeof House> = {
  home: House,
  work: Briefcase,
  star: Star,
};

interface Props {
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
}

/** تحيّةٌ بساعة الجهاز — **وهي الموضعُ الوحيد الذي تُقبل فيه**: لا موعدَ
 *  يترتّب عليها ولا نافذةَ تُقاس بها، **وساعةُ صاحبها أصدقُ من ساعتنا في
 *  قول «مساء»**. (ولافتةُ المحتوى بخلافها — نافذتُها في الخادم.) */
function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "صباح الخير";
  if (hour < 17) return "طاب يومك";
  return "مساء الخير";
}

export function RiderHome({
  name,
  place,
  unread,
  wallet,
  currency,
  nearby,
  onOpenNotifications,
  onOpenWallet,
  onOpenAccount,
  onAskDestination,
  places,
  onPickPlace,
  tiles,
  banners,
  referrals,
  onOpenReferrals,
  recent,
  onOpenRides,
  onRepeat,
  map,
}: Props) {
  // **أوّلُ برنامجٍ مشتعل** — و«لم يُحدَّد» تعني أن الصفَّ لا يُرسم أصلاً
  const program =
    referrals?.programs.find(
      (row) => row.enabled && row.reward_amount !== "0",
    ) ?? null;

  return (
    <div className="scr absolute inset-x-0 bottom-nav top-0 overflow-y-auto px-16 pb-18 pt-2">
      {/* ── الرأس: التحيّةُ والموقع · المحفظةُ · الجرس */}
      <div className="mb-12 flex items-center justify-between gap-8">
        <button
          type="button"
          onClick={onOpenAccount}
          className="pressable flex min-w-0 items-center gap-10 text-start"
        >
          <span className="flex size-38 shrink-0 items-center justify-center rounded-full border border-brand-brd bg-brand-soft text-15 font-bold text-ink">
            {name.slice(0, 1)}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-14 font-semibold text-ink">
              {greeting()}، {name}
            </span>
            {/* **ولا مدينةَ تُخمَّن**: يُعرض ما عُرف، وإلا فلا سطر */}
            {place ? (
              <span className="block truncate text-11.5 text-muted">
                {place}
              </span>
            ) : null}
          </span>
        </button>

        <div className="flex shrink-0 items-center gap-7">
          {/* **الرصيدُ برمز عملته لا بعلامتها** — `check:money` */}
          {wallet ? (
            <button
              type="button"
              onClick={onOpenWallet}
              className="pressable flex items-center gap-6 rounded-full border border-line bg-surface px-11 py-7 text-12.5 font-semibold text-ink"
            >
              <WalletIcon className="size-15 text-muted" />
              {formatMoney(wallet.balance, currency)}
            </button>
          ) : null}
          <button
            type="button"
            onClick={onOpenNotifications}
            aria-label="الإشعارات"
            className="ctl relative size-33"
          >
            <Bell className="size-17" />
            {/* **نقطةٌ لا رقم** — السؤالُ هنا «هل ثمّ جديد؟» لا «كم» */}
            {unread ? (
              <span className="absolute end-6 top-5 block size-7 rounded-full bg-danger" />
            ) : null}
          </button>
        </div>
      </div>

      {/* ── الخريطةُ بطاقةً: شارةُ القريبين فوق، و«إلى أين؟» في القاع */}
      <div className="relative mb-10 h-170 overflow-hidden rounded-16 border border-line">
        {map}
        {/* **عددٌ بلا مهلة** — والمهلةُ لا تُقاس قبل نقطة الالتقاط */}
        {nearby > 0 ? (
          <span className="pointer-events-none absolute end-10 top-10 rounded-full border border-line bg-surface px-10 py-4 text-10.5 font-semibold text-ink">
            {nearby === 1
              ? "كبتن قريب"
              : nearby === 2
                ? "كبتنان قريبان"
                : `${nearby} كباتن قريبون`}
          </span>
        ) : null}
        <button
          type="button"
          onClick={onAskDestination}
          className="pressable absolute inset-x-10 bottom-10 flex items-center justify-center gap-7 rounded-13 bg-brand p-13 text-14.5 font-bold text-brand-ink"
        >
          <MapPin className="size-17" />
          إلى أين؟ اطلب رحلة
        </button>
      </div>

      {/* ── اختصاراتُ أماكنه المحفوظة — **ولا صفَّ بلا أماكن** */}
      {places.length > 0 ? (
        <div className="mb-12 flex gap-8">
          {places.slice(0, 3).map((saved) => {
            const Icon = PLACE_MARK[saved.icon] ?? Star;
            return (
              <button
                key={saved.id}
                type="button"
                onClick={() => onPickPlace(saved)}
                className="pressable flex min-w-0 flex-1 items-center justify-center gap-6 rounded-12 border border-line bg-surface p-9 text-12 font-medium text-ink"
              >
                <Icon className="size-15 shrink-0 text-muted" />
                <span className="truncate">{saved.label}</span>
              </button>
            );
          })}
        </div>
      ) : null}

      <ServiceTiles tiles={tiles} />
      <PromoBanners banners={banners} />

      {/* ── صفُّ الإحالة — **يظهر بجائزةٍ مقروءةٍ أو لا يظهر**: «ادعُ صديقاً
          واربح» بلا مبلغٍ دعوةٌ بلا وعد، **والمبلغُ المخبوز يمنعه §14** */}
      {program ? (
        <button
          type="button"
          onClick={onOpenReferrals}
          className="pressable mb-14 flex w-full items-center gap-10 rounded-14 border border-line bg-surface px-13 py-12 text-start"
        >
          <Gift className="size-19 shrink-0 text-muted" />
          <span className="min-w-0 flex-1 text-12.5 font-medium text-ink">
            ادعُ صديقاً واربح {formatMoney(program.reward_amount, currency)}
          </span>
          <span className="shrink-0 text-11.5 font-bold text-ink">مشاركة</span>
        </button>
      ) : null}

      {/* ── آخرُ رحلاتك — **ولا يُرسم العنوانُ فوق فراغ** */}
      {recent.length > 0 ? (
        <>
          <div className="mb-8 flex items-baseline justify-between">
            <span className="text-13.5 font-bold text-ink">آخر رحلاتك</span>
            <button
              type="button"
              onClick={onOpenRides}
              className="text-11.5 text-muted underline"
            >
              الكل
            </button>
          </div>
          <div className="hsc flex gap-8 overflow-x-auto">
            {recent.map((ride) => (
              <button
                key={ride.id}
                type="button"
                onClick={() => onRepeat(ride)}
                className="pressable min-w-176 shrink-0 rounded-14 border border-line bg-surface px-12 py-11 text-start"
              >
                <div className="text-11 text-muted">
                  {/* **الأجرةُ النهائيةُ إن كانت** — و`estimated` قبلها تقديرٌ
                      لا محصَّل، **ولا يُعرض تقديرٌ في موضع محصَّل** */}
                  {formatMoney(ride.final_fare, ride.currency)}
                </div>
                <div className="my-5 line-clamp-2 text-12.5 text-ink">
                  {ride.pickup_address ?? "نقطة الانطلاق"} ←{" "}
                  {ride.dropoff_address ?? "الوجهة"}
                </div>
                <div className="text-11.5 font-bold text-ink">أعِد الرحلة</div>
              </button>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}
