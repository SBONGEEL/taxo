/** **منطقُ ورقة التأكيد في بيتٍ واحد** — التقديرُ والكوبونُ والمشاركةُ والدفعُ والحجز.
 *
 * يقرؤه وجهان: **القائمُ** (`ConfirmRide`) و**TAXO 2.0** «R06» (`screens/t2/ConfirmRideT2`) — **فلا يفترقان في طلبٍ
 * ولا في رقمٍ ولا في شرط**. والنصُّ منقولٌ من `ConfirmRide` **حرفاً بتعليقاته**، والعرضُ القائمُ لم يتغيّر فيه سطر
 * (قِيس: شجرتُه متطابقةٌ قبل النقل وبعده).
 */

import { useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { estimateRide, getWallet, validatePromo } from "@/api/endpoints";
import type {
  AppConfig,
  Coordinates,
  CountryConfig,
  GenderPreference,
  PromoPreview,
  RideEstimate,
  VehicleCategory,
} from "@/api/types";
import type { DraftStop } from "@/components/home/StopsEditor";
import { earliest, localInputValue, useScheduledRides } from "@/lib/bookings";
import { useMultiStop } from "@/lib/multistop";
import { usePaymentPreference } from "@/lib/payment";
import { usePromoCodes } from "@/lib/promo";
import { useSession } from "@/lib/session";
import { useRideSharing } from "@/lib/sharing";
import { useConfig } from "@/lib/config";
import { useWomenService } from "@/lib/women";
import { formatMoney } from "@/lib/utils";

/** نصٌّ لكل خيار — والثلاثةُ تقول أثرَه على الانتظار لا اسمَه.
 *
 * **والنطاقُ من الخلفية** (`/config` · `dispatch` — §٦٢-ب/٤٨): كان «10 كم بدل 7» مكتوباً هنا نسخةً من ثابتَي `geo` — **رقمان لشيءٍ
 * واحدٍ يفترقان أوّلَ تعديل**. **وقبل وصول الإعداد يُقال بلا رقم** — لا رقمَ يُخمَّن مكانه. */
export function preferenceNote(preference: GenderPreference, dispatch: AppConfig["dispatch"] | undefined): string {
  if (preference === "any") return "أي كبتن متاح — أسرع استجابة وأوسع نطاق.";
  if (preference === "female") {
    return dispatch
      ? `سيبحث النظام عن كبتنات فقط، ضمن نطاق ${dispatch.gendered_max_search_radius_km} كم بدل ${dispatch.max_search_radius_km} — قد يطول الانتظار.`
      : "سيبحث النظام عن كبتنات فقط، في نطاقٍ أوسع — قد يطول الانتظار.";
  }
  return dispatch
    ? `سيبحث النظام عن كبتنٍ رجل فقط، ضمن نطاق ${dispatch.gendered_max_search_radius_km} كم.`
    : "سيبحث النظام عن كبتنٍ رجل فقط، في نطاقٍ أوسع.";
}

/** «دقيقتان» لا «2 دقيقة» — **العربيةُ تعدّ بالمثنّى والجمع** (§17).
 *
 * وهو الدرسُ نفسُه الذي أنشأ `FEMININE_LABELS` في عقد الأخطاء: **نحوٌ مكسورٌ
 * في جملةِ مالٍ يُقرأ تطبيقاً مكسوراً**، فيُقرأ الرقمُ بعده بريبة. والسياساتُ
 * الواقعية بين دقيقةٍ وخمسَ عشرة، فالحالاتُ الأربعُ تغطّيها كلَّها.
 *
 * **والخاناتُ لاتينيةٌ بحكم §20** — التغييرُ في صيغة المعدود لا في شكل الرقم.
 */
export function freeMinutes(count: number): string {
  if (count === 1) return "الدقيقة الأولى";
  if (count === 2) return "أول دقيقتين";
  if (count <= 10) return `أول ${count} دقائق`;
  return `أول ${count} دقيقة`;
}

/** ما سيدفعه لو انتظر — **بالأرقام، وقبل أن يقبل السعر** (§5.10).
 *
 * **والنصُّ الذي كان هنا يقول إن للانتظار سعراً ولا يقوله**: «دقائقُ مجانية
 * ثم رسمٌ لكل دقيقة». وهو أسوأُ من الصمت بقدرٍ صغير — يُقرأ طمأنينةً
 * («شيءٌ يسير») ثم يظهر الرقمُ في شاشة الدفع.
 *
 * **والأرقامُ من التقدير لا من ثابتٍ هنا** (§14): تسعيرةُ الوقوف لكلِّ
 * (دولة × فئة)، وواجهةٌ تكتب رقماً من عندها تخالف الجدولَ يومَ يُعدَّل.
 * و`null` حين لا تقديرَ بعد — فلا يُرسم سطرٌ بمكان الأرقام فارغ.
 *
 * **والصفرُ يُقرأ «لا رسم» ويُقال صريحاً**: سوقٌ لم تُضبط فيه القيمةُ بعد
 * يجب ألّا يَعِد براحةٍ ولا يخوّف برسمٍ لا وجودَ له.
 */
export function waitingNote(estimate: RideEstimate | null): string | null {
  if (!estimate) return null;
  const free = estimate.stop_free_minutes;
  const perMin = Number(estimate.stop_price_per_min);
  if (perMin <= 0)
    return "يقف الكبتن عند كل محطة، ولا رسمَ على الانتظار في هذه السوق.";
  const price = formatMoney(estimate.stop_price_per_min, estimate.currency);
  const head =
    free > 0
      ? `يقف الكبتن عند كل محطة، و${freeMinutes(free)} عند كل واحدة مجاناً`
      : "يقف الكبتن عند كل محطة، والانتظار محسوبٌ من أول دقيقة";
  return `${head}، ثم ${price} لكل دقيقة — يظهر عدّادُه أمامك أثناء الوقوف.`;
}

export interface ConfirmRideProps {
  pickup: Coordinates;
  pickupAddress: string | null;
  dropoff: Coordinates;
  dropoffAddress: string | null;
  categories: VehicleCategory[];
  onEditDestination: () => void;
  onRequest: (
    category: VehicleCategory,
    preference: GenderPreference,
    promoCode?: string,
    sharing?: { share: boolean; shareGenderConfirmed: boolean },
  ) => void;
  requesting: boolean;
  requestError: string | null;
  stops: DraftStop[];
  onStopsChange: (next: DraftStop[]) => void;
  onAddStop: () => void;
  /** ارتدّ الطلبُ بتفضيلٍ نسائيٍّ لا تستطيع تغييره — الخدمةُ مطفأة فالمفتاح
   * مخفيّ. وهنا يُفتح لها الباب بدل رفضٍ مسدود. */
  blockedByPreference: boolean;
  onClearPreference: () => void;
  /** «حدّد موعداً» (12-ط) — يُمرَّر ما اختارته من فئةٍ وتفضيلٍ كما يُمرَّر للطلب
   *  الفوري، فالحجزُ نفسُ الطلب بموعدٍ لا طلبٌ آخر. */
  onSchedule: (
    category: VehicleCategory,
    preference: GenderPreference,
    when: string,
  ) => void;
  /** «رجوع» من التصميم — يترك التخطيطَ كلَّه ويعود إلى «إلى أين؟». */
  onBack: () => void;
  /** إعداداتُ دولة الحساب — منها تُقرأ قنواتُ الدفع المتاحة وعملتُها. */
  countryConfig: CountryConfig | null;
  /** **تفضيلٌ يُبدأ به هذا الطلبُ وحدَه** — بلاطةُ «نسائية» في رئيسية TAXO 2.0 تبدأه بـ«كبتنة فقط» (§٦١-د/ج)،
   *  **وهي تغيّره بنفسها** من المنتقي نفسِه. وبلا قيمةٍ يبدأ من افتراضي ملفها كما كان. */
  initialPreference?: GenderPreference;
  /** **فئةٌ يُبدأ بها** — «جدولي الرحلة لوقت لاحق» (RW3، §٦٢-ج/٢٣) تفتح الورقةَ بفئة الرحلة التي لم تجد كبتنة، **فلا تُبدَّل فئتُها
   *  بلا قولها**. وبلا قيمةٍ أوّلُ فئات السوق كما كان. */
  initialCategory?: VehicleCategory;
  /** **ومنتقي الموعد مفتوحاً** — الاختيارُ نفسُه في RW3 («جدولي») لا يُطلب ثانيةً بزرِّ «حدّد موعداً». حيث الحجوزُ مشتعلةٌ وحدَها. */
  initialScheduling?: boolean;
  /** **عنوانُ موقع الجهاز من Mapbox** — سطرُ «من» في «R06» حين لا `pickupAddress` (موقعُ الجهاز لا يُسمّى). للعرض وحدَه:
   *  **لا يُرسل مع الطلب**، والورقةُ القائمةُ لا تقرؤه. */
  pickupLine?: string | null;
  /** **دقائقُ أقرب كبتنٍ لكلِّ فئة** (§٦٢-ج/١٠، «· يصل خلال 3 د» في R06) — و`null`/غيابُها حيث المفتاحُ مطفأ. */
  eta?: Partial<Record<VehicleCategory, number>> | null;
}

export function useConfirmRide({
  pickup,
  dropoff,
  categories,
  stops,
  countryConfig,
  initialPreference,
  initialCategory,
  initialScheduling,
}: ConfirmRideProps) {
  const women = useWomenService();
  // الحجزُ (12-ط) — مفتاحُه يخفي الزرَّ كلَّه لا يعطّله
  const scheduled = useScheduledRides();
  // **ومفتوحاً من أوّله حين جاءت من «جدولي الرحلة لوقت لاحق»** (RW3) — بأقرب موعدٍ كما يفتحه زرُّه
  const [scheduling, setScheduling] = useState(Boolean(initialScheduling) && scheduled);
  const [when, setWhen] = useState(() => (initialScheduling && scheduled ? localInputValue(earliest()) : ""));
  // دولةُ الحساب — الكوبونُ per-country فالتحقّقُ يحملها
  const multiStop = useMultiStop();
  const [category, setCategory] = useState<VehicleCategory>(
    initialCategory && categories.includes(initialCategory) ? initialCategory : categories[0] ?? "economy",
  );
  // يبدأ من افتراضي ملفها ثم تغيّره لهذه الرحلة وحدها — **أو ممّا بدأته بلاطةُ «نسائية»، ولمن عُرضت عليها الخدمةُ وحدَها**
  const [preference, setPreference] = useState<GenderPreference>(
    women.available && initialPreference ? initialPreference : women.defaultPreference,
  );
  const { config } = useConfig();
  const [estimate, setEstimate] = useState<RideEstimate | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // **طريقةُ الدفع تفضيلٌ محلّي** (قرار 3): تُعرض هنا وتُمرَّر إلى شاشة الدفع،
  // ولا تُرسل مع الطلب ولا تُقيّد صاحبَها بعد الرحلة
  const { available: channels, resolved: payMethod, choose } =
    usePaymentPreference(countryConfig);
  const [pickingPay, setPickingPay] = useState(false);

  // الرصيدُ يُقرأ لسطرِ الملاحظة وحدَه (`walletSub` و`fareNote` في التصميم) —
  // **ولا يُحسب منه شيء**: المقارنةُ «هل يغطّي؟» عرضٌ لا قرارُ مال، والقرارُ
  // في `payments._pay_from_wallet` بعد الرحلة تحت قفل المحفظة
  const [balance, setBalance] = useState<string | null>(null);
  const walletOffered = channels.some((channel) => channel.method === "wallet");
  useEffect(() => {
    if (!walletOffered) return;
    let cancelled = false;
    // القراءةُ لا يحرسها `wallet_enabled` (يحرس الشحنَ والدفع)، وفشلُها يعني
    // سطرَ ملاحظةٍ أقل — لا شاشةَ خطأ فوق ورقةِ طلب
    getWallet()
      .then((row) => !cancelled && setBalance(row.balance))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [walletOffered]);

  // الكوبون (12-ز): `applied` هو ما قبلته الخلفيةُ — لا ما كتبه الراكب
  const promoEnabled = usePromoCodes();
  // المشاركة (12-ي): المفتاحُ يقول «تُعرض»، و`share_fare` هو الرقم — وغيابُه
  // يعني ألّا نسبةَ قُرِّرت، فيُخفى الصفُّ ولو كان المفتاح مشتعلاً
  const sharingEnabled = useRideSharing();
  const [share, setShare] = useState(false);
  // **موافقةٌ ثانيةٌ منفصلة** لا مدموجةٌ في الأولى (قرارُ المالك الرابع): من
  // حدّدت جنسَ الكبتن لا تُشارَك رحلتُها إلا باختيارٍ صريحٍ تختاره هي
  const [shareGendered, setShareGendered] = useState(false);
  const { user } = useSession();
  const country = user?.country_code ?? "JO";
  const [couponOpen, setCouponOpen] = useState(false);
  const [couponInput, setCouponInput] = useState("");
  const [applied, setApplied] = useState<PromoPreview | null>(null);
  const [couponError, setCouponError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  // **الخصمُ يُعاد التحقق منه إن تغيّر التقدير**: تبديلُ الفئة أو إضافةُ محطةٍ
  // يغيّر الأجرة، وخصمُ نسبةٍ محسوبٌ عليها — فرقمٌ قديمٌ يبقى معروضاً يكذب
  useEffect(() => {
    if (applied === null || estimate === null) return;
    let cancelled = false;
    validatePromo(applied.code, estimate.estimated_fare, country)
      .then((next) => !cancelled && setApplied(next))
      .catch(() => !cancelled && setApplied(null));
    return () => {
      cancelled = true;
    };
    // `applied.code` لا `applied`: الكائنُ يتبدّل بكل تحقّقٍ فتدور الحلقة
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [estimate?.estimated_fare, applied?.code]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    estimateRide({
      pickup,
      dropoff,
      vehicle_category: category,
      stops: stops.map((stop) => ({ lat: stop.lat, lng: stop.lng })),
    })
      .then((value) => !cancelled && setEstimate(value))
      .catch(
        (caught: unknown) =>
          !cancelled &&
          setError(caught instanceof ApiError ? caught.message : "تعذّر حساب السعر"),
      )
      .finally(() => !cancelled && setLoading(false));

    return () => {
      cancelled = true;
    };
    // المحطاتُ في التبعيات: إضافةُ محطةٍ أو ترتيبُها يغيّر المسار والرسم،
    // فيُعاد السؤال — ولا يُجمع فرقٌ في الواجهة
  }, [pickup, dropoff, category, stops]);

  async function apply() {
    if (!estimate) return;
    setChecking(true);
    setCouponError(null);
    try {
      // **الخلفيةُ تحسب الخصم** — والشاشةُ تعرض ما ردّته (القسم 14)
      setApplied(
        await validatePromo(couponInput.trim(), estimate.estimated_fare, country),
      );
      setCouponOpen(false);
    } catch (caught) {
      setCouponError(
        caught instanceof ApiError ? caught.message : "تعذّر التحقق من الرمز",
      );
    } finally {
      setChecking(false);
    }
  }

  // ما سيُدفع فعلاً: المخصومُ إن طُبِّق كوبون، وإلا المقدَّر. ولا جمعَ ولا ضربَ
  // هنا — كلا الرقمين جاء من الخلفية كما هو (القسم 14)
  // **المشاركةُ تُخفى ما دام لا سعرَ لها**: تبديلُ الفئة يعيد حساب التقدير،
  // وصفُّ خصمٍ بلا رقمٍ يَعِد بما لا يُعرض
  const shareOffered = sharingEnabled && estimate?.share_fare != null;
  const shareGuarded = preference !== "any";
  const shareReady = share && (!shareGuarded || shareGendered);
  const shownFare =
    (shareReady ? estimate?.share_fare : null) ??
    applied?.fare_after ??
    estimate?.estimated_fare ??
    null;

  /** ملاحظةُ المحفظة — وهي **وصفُ ما تفعله الخلفيةُ فعلاً**، لا وعدُ شاشة.
   *
   * `payments._pay_from_wallet` يخصم `min(balance, outstanding)` ويكتب الباقيَ
   * صفَّ **كاش**، ويرفض تماماً حين يكون الرصيد صفراً. فالسطران أدناه ترجمةُ
   * ذلك السلوك حرفاً بحرف — ولذلك لا وجودَ لقناةٍ اسمها «مختلط» في المُنتقي:
   * الخلطُ **نتيجةُ اختيار المحفظة** لا خياراً خامساً بجانبها (القرار 51).
   *
   * والمقارنةُ عرضٌ لا حساب: «هل يغطّي؟» سؤالُ نعم/لا، ولا يُشتقّ منه مبلغٌ
   * يُعرض — وهو الفرقُ الذي يُبقي القسم 14 قائماً (وسابقتُه `settled` في
   * `screens/Payment.tsx`). والصياغةُ تقديرٌ لا إخبار («ستُخصم» لا «خُصمت»)
   * كما يفرض القرار 3: الأجرةُ النهائيةُ تُحسب على المسار الفعلي.
   */
  const walletNote =
    payMethod?.method !== "wallet" || balance === null || shownFare === null
      ? null
      : Number(balance) <= 0
        ? "لا رصيد في محفظتك — اشحنها أو اختر طريقةً أخرى عند الدفع."
        : Number(balance) < Number(shownFare)
          ? "رصيدك لا يغطّي الأجرة المقدَّرة — سيُخصم منه ما يغطّيه ثم تدفع الباقي كاشاً للكبتن."
          : null;

  return {
    women,
    scheduled,
    scheduling,
    setScheduling,
    when,
    setWhen,
    multiStop,
    category,
    setCategory,
    preference,
    setPreference,
    preferenceNote: preferenceNote(preference, config?.dispatch),
    estimate,
    error,
    loading,
    channels,
    payMethod,
    choose,
    pickingPay,
    setPickingPay,
    balance,
    promoEnabled,
    share,
    setShare,
    shareGendered,
    setShareGendered,
    couponOpen,
    setCouponOpen,
    couponInput,
    setCouponInput,
    applied,
    setApplied,
    couponError,
    setCouponError,
    checking,
    apply,
    shareOffered,
    shareGuarded,
    shareReady,
    shownFare,
    walletNote,
  };
}
