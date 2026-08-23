/** تأكيد الطلب: الفئة، والسعر المقدَّر، وزرُّ الطلب (SPEC القسم 11.3).
 *
 * **السعر يأتي من `POST /rides/estimate` ولا يُحسب هنا أبداً** (القسم 14):
 * الواجهة تعرض ما قالته الخلفية بحروفه — لا ضربَ مسافةٍ في تعرفة، ولا حتى
 * جمعَ رسمٍ على مبلغ. وتبديلُ الفئة يعيد السؤال لأن التعرفة لكل فئة.
 *
 * **ورسمُ الانتظار يُقال قبل الطلب بأرقامه** (المرحلة 12-ب، §5.10): لا يدخل
 * التقدير لأنه لا يُعرف قبل أن يقع، **فيُقال سعرُه** — فيكون معلوماً ولو لم
 * يكن مقدَّراً.
 *
 * **وهذا السطرُ كان يقول عكسَ ما يقول اليوم، والتصحيحُ يُقرأ لا يُمحى**
 * (2026-08-21): كان مكتوباً أن التسعيرة «لا تُنشر» فيتعذّر قولُ الرقم قبل
 * الطلب، **وكان ذلك صحيحاً ثم صار خطأً**: `POST /rides/estimate` صار يحمل
 * `stop_fee` و`stop_free_minutes` و`stop_price_per_min` — ومحلُّها التقديرُ
 * لا `GET /config` لأن الأربعة لكلِّ (دولة × فئة)، **والتقديرُ وحدَه يعرف
 * الفئةَ المختارة**. فالنصُّ الوصفيُّ («دقائقُ مجانية ثم رسمٌ لكل دقيقة»)
 * صار جملةً بأرقامها، ومن يقبل السعر يعرف ما يدفعه لو انتظر.
 *
 * **والكوبونُ يُتحقق منه في الخلفية لا هنا** (المرحلة 12-ز، القسم 6.6): الشاشةُ
 * ترسل الرمزَ إلى `POST /rides/promo/validate` وتعرض ما ردّته — لا تضرب نسبةً
 * في تقدير. ثم يُرسل الرمزُ **مع الطلب** فتُجمَّد قاعدتُه على الرحلة، والخصمُ
 * النهائي يُحسب على الأجرة الفعلية عند الإنهاء. فما يُعرض هنا **عرضٌ لا
 * التزام**، والسطرُ يقولها.
 *
 * **واختيارُ «كبتنة فقط» يقول ثمنَه قبل الضغط لا بعده** (المرحلة 10-ج):
 * الكبتنات أقل عدداً، فالانتظارُ أطول والبحثُ يتسع إلى ١٠كم. وقولُ ذلك هنا
 * يجعل الانتظار خياراً اختارته؛ والسكوتُ عنه يجعله عطلاً يُشتكى منه — ثم
 * «لم نجد كبتناً» بلا سبب.
 */

import { AnimatePresence, motion } from "framer-motion";
import {
  CalendarClock,
  Car,
  ChevronLeft,
  CircleDot,
  Clock,
  MapPin,
  RefreshCw,
  TicketPercent,
  Users,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { estimateRide, getWallet, validatePromo } from "@/api/endpoints";
import type {
  Coordinates,
  CountryConfig,
  GenderPreference,
  PromoPreview,
  RideEstimate,
  VehicleCategory,
} from "@/api/types";
import { StopsEditor, type DraftStop } from "@/components/home/StopsEditor";
import { PaymentPicker } from "@/components/payment/PaymentPicker";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { Sheet } from "@/components/ui/Sheet";
import { PAYMENT_METHOD_LABEL, VEHICLE_HINT, VEHICLE_LABEL } from "@/lib/labels";
import { usePaymentPreference } from "@/lib/payment";
import { useMultiStop } from "@/lib/multistop";
import { usePromoCodes } from "@/lib/promo";
import { useRideSharing } from "@/lib/sharing";
import {
  earliest,
  latest,
  localInputValue,
  useScheduledRides,
} from "@/lib/bookings";
import { useSession } from "@/lib/session";
import { useWomenService } from "@/lib/women";
import { cn, formatDistance, formatDuration, formatMoney } from "@/lib/utils";

/** نصٌّ لكل خيار — والثلاثةُ تقول أثرَه على الانتظار لا اسمَه. */
const PREFERENCE_NOTE: Record<GenderPreference, string> = {
  female: "سيبحث النظام عن كبتنات فقط، ضمن نطاق 10 كم بدل 7 — قد يطول الانتظار.",
  male: "سيبحث النظام عن كبتنٍ رجل فقط، ضمن نطاق 10 كم.",
  any: "أي كبتن متاح — أسرع استجابة وأوسع نطاق.",
};

/** «دقيقتان» لا «2 دقيقة» — **العربيةُ تعدّ بالمثنّى والجمع** (§17).
 *
 * وهو الدرسُ نفسُه الذي أنشأ `FEMININE_LABELS` في عقد الأخطاء: **نحوٌ مكسورٌ
 * في جملةِ مالٍ يُقرأ تطبيقاً مكسوراً**، فيُقرأ الرقمُ بعده بريبة. والسياساتُ
 * الواقعية بين دقيقةٍ وخمسَ عشرة، فالحالاتُ الأربعُ تغطّيها كلَّها.
 *
 * **والخاناتُ لاتينيةٌ بحكم §20** — التغييرُ في صيغة المعدود لا في شكل الرقم.
 */
function freeMinutes(count: number): string {
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
function waitingNote(estimate: RideEstimate | null): string | null {
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

export function ConfirmRide({
  pickup,
  pickupAddress,
  dropoff,
  dropoffAddress,
  categories,
  onEditDestination,
  onRequest,
  requesting,
  requestError,
  stops,
  onStopsChange,
  onAddStop,
  blockedByPreference,
  onClearPreference,
  onSchedule,
  onBack,
  countryConfig,
}: {
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
}) {
  const women = useWomenService();
  // الحجزُ (12-ط) — مفتاحُه يخفي الزرَّ كلَّه لا يعطّله
  const scheduled = useScheduledRides();
  const [scheduling, setScheduling] = useState(false);
  const [when, setWhen] = useState("");
  // دولةُ الحساب — الكوبونُ per-country فالتحقّقُ يحملها
  const multiStop = useMultiStop();
  const [category, setCategory] = useState<VehicleCategory>(categories[0] ?? "economy");
  // يبدأ من افتراضي ملفها ثم تغيّره لهذه الرحلة وحدها
  const [preference, setPreference] = useState<GenderPreference>(
    women.defaultPreference,
  );
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

  return (
    <Sheet
      footer={
        // **قدمٌ ثابتةٌ: المبلغُ والزرّ** (إذنُ المالك 2026-08-23). نُقلت كتلةُ
        // السعر من موضعها فوق صفِّ الدفع إلى هنا — **وهو التغييرُ الشكليُّ
        // الوحيدُ المأذونُ به في هذه الدفعة**. وعلّتُه أن السقفَ والتمريرَ
        // يجعلان كلَّ سطرٍ **قابلاً للبلوغ** ولا يجعلانه **مرئياً**، ومن يضغط
        // «اطلب» وقد مرّر الرقمَ خارج نظره يلتزم بمبلغٍ لا يقرؤه.
        <div className="space-y-12">
        <div className="rounded-12 border border-line bg-bg px-16 py-12">
          <AnimatePresence mode="wait">
            {loading ? (
              <motion.div
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex items-center gap-8 text-14 text-muted"
              >
                <RefreshCw className="size-16 animate-spin" />
                نحسب السعر المقدّر…
              </motion.div>
            ) : estimate ? (
              <motion.div
                key="estimate"
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="flex items-end justify-between"
              >
                <div>
                  <p className="text-12 text-muted">السعر المقدّر</p>
                  {applied ? (
                    // **الأصلُ مشطوبٌ والمخصومُ بارز**: رقمٌ واحدٌ بعد الخصم
                    // يخفي أن هناك خصماً، ورقمان بلا شطبٍ يُقرآن مبلغين
                    <p className="flex items-baseline gap-8">
                      <span className="text-24 font-bold text-ok">
                        {formatMoney(applied.fare_after, estimate.currency)}
                      </span>
                      <span className="text-14 text-muted line-through">
                        {formatMoney(estimate.estimated_fare, estimate.currency)}
                      </span>
                    </p>
                  ) : (
                    <p className="text-24 font-bold text-ink">
                      {formatMoney(estimate.estimated_fare, estimate.currency)}
                    </p>
                  )}
                  {estimate.minimum_fare_applied ? (
                    <p className="mt-2 text-12 text-muted">طُبِّق الحد الأدنى للأجرة</p>
                  ) : null}
                </div>
                <div className="text-end text-14 text-muted">
                  <p>{formatDistance(estimate.distance_km)}</p>
                  <p>{formatDuration(estimate.duration_min)}</p>
                </div>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>
        {/* **سطرُ الخطأ فوق الزرِّ مباشرةً** — لا في المنطقة الممرَّرة: من
            يضغط ويُرفَض يجب أن يقرأ السببَ في المكان الذي ضغط فيه. والشرطُ
            هو الشرطُ الأول نفسُه معكوساً، فالسلوكُ لم يتغيّر: اللوحةُ
            والسطرُ لا يجتمعان كما كانا في `if/else`. */}
        {blockedByPreference ? null : (
          <ErrorNote message={error ?? requestError} />
        )}
        {/* **السعرُ على الزرّ** (تصميمُ `requestLabel`): آخرُ ما تقع عليه العينُ
            قبل الضغط هو الرقم — ويختفي وحدَه ما دام يُحسب، فرقمٌ قديمٌ على زرِّ
            التزامٍ أسوأ من لا رقم. و«رجوع» بجانبه بثلثِ عرضه: مخرجٌ لا ندٌّ */}
        <div className="flex gap-8">
          <Button
            size="lg"
            className="w-auto flex-[3]"
            loading={requesting}
            disabled={!estimate || loading}
            onClick={() =>
              onRequest(category, preference, applied?.code, {
                share: shareReady,
                shareGenderConfirmed: shareReady && shareGuarded,
              })
            }
          >
            اطلب الرحلة
            {shownFare && !loading ? (
              <span className="font-medium">
                · {formatMoney(shownFare, estimate?.currency)}
              </span>
            ) : null}
          </Button>
          <button
            type="button"
            onClick={onBack}
            className="pressable flex-1 rounded-12 border border-line py-15 text-13 font-semibold text-muted transition hover:bg-surface-2"
          >
            رجوع
          </button>
        </div>
        </div>
      }
    >
      <div className="space-y-16 pb-16">
        {/* المسار: نقطتان وخطٌّ بينهما — أوضح من سطرين نصّيين */}
        <div className="flex gap-12">
          <div className="flex flex-col items-center pt-6">
            <CircleDot className="size-16 text-ok" />
            <span className="my-4 h-24 w-px bg-line" />
            <MapPin className="size-16 text-danger" />
          </div>
          <div className="min-w-0 flex-1 space-y-12">
            <p className="truncate text-14 text-muted">
              {pickupAddress ?? "نقطة الانطلاق المحددة"}
            </p>
            <button
              type="button"
              onClick={onEditDestination}
              className="pressable block w-full truncate text-start font-medium text-ink"
            >
              {dropoffAddress ?? "الوجهة المحددة"}
            </button>
          </div>
        </div>

        {/* لا يظهر شيءٌ من هذا حيث المفتاح مطفأ — لا زرٌّ معطّل ولا اعتذار */}
        {multiStop ? (
          <StopsEditor
            stops={stops}
            onChange={onStopsChange}
            onAdd={onAddStop}
            waitingNote={waitingNote(estimate)}
          />
        ) : null}

        <div className="grid grid-cols-2 gap-8">
          {categories.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setCategory(option)}
              className={cn(
                "pressable rounded-12 border p-12 text-start transition",
                option === category
                  ? "border-brand bg-brand-soft"
                  : "border-line bg-surface hover:bg-surface-2",
              )}
            >
              <span className="flex items-center gap-8 font-medium text-ink">
                <Car className="size-16" />
                {VEHICLE_LABEL[option]}
              </span>
              <span className="mt-2 block text-12 text-muted">
                {VEHICLE_HINT[option]}
              </span>
            </button>
          ))}
        </div>

        {/* لا يظهر هذا الصف إلا لمن عُرضت عليها الخدمة — والقرارُ في
            `lib/women.ts` وحده */}
        {women.available ? (
          <div>
            <p className="mb-8 text-12 text-muted">تفضيل الكبتن</p>
            <div className="grid grid-cols-3 gap-8">
              {(
                [
                  { value: "female", label: "إناث" },
                  { value: "male", label: "ذكور" },
                  { value: "any", label: "الجميع" },
                ] as const
              ).map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setPreference(option.value)}
                  className={cn(
                    "pressable rounded-12 border p-12 text-center text-14 font-medium transition",
                    option.value === preference
                      ? "border-brand bg-brand text-brand-ink"
                      : "border-line bg-surface text-muted hover:bg-surface-2",
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
            <p className="mt-8 flex items-start gap-6 text-12 leading-relaxed text-muted">
              {preference === "any" ? null : (
                <Clock className="mt-2 size-14 shrink-0" />
              )}
              {PREFERENCE_NOTE[preference]}
            </p>
          </div>
        ) : null}


        {/* **صفُّ طريقة الدفع** (تصميمُ الراكب، القراران 3 و26): يُعرض قبل
            الطلب لأن معرفةَ ما ستدفع به معلومةٌ صحيحةٌ ومفيدة، **ولا يُرسل مع
            الطلب** — فلا عمودَ له على `rides` ولا تجميدَ لقاعدة عمولةٍ قبل أن
            تُعرف الأجرة. ولا يظهر الصفُّ بقناةٍ واحدة: منتقٍ بخيارٍ وحيد
            يَعِد باختيارٍ لا وجودَ له */}
        {payMethod && channels.length > 1 ? (
          <button
            type="button"
            onClick={() => setPickingPay(true)}
            className="pressable flex w-full items-center gap-9 rounded-13 border border-line bg-surface px-13 py-11 text-start"
          >
            <payMethod.icon className="size-16 shrink-0 text-muted" />
            <span className="min-w-0 flex-1 truncate text-12.5 font-semibold text-ink">
              {PAYMENT_METHOD_LABEL[payMethod.method]}
            </span>
            <ChevronLeft className="size-16 shrink-0 text-muted" />
          </button>
        ) : null}

        {/* **صفُّ المشاركة** (12-ي): مفتاحٌ واحدٌ ومعه الرقمُ الذي يوفّره —
            «شارك» بلا رقمٍ كلمةٌ لا عرض. ويُخفى كلُّه حيث لا مشاركة، فمفتاحٌ
            معطّلٌ يَعِد بما لا يقع.
            **والموافقةُ الثانيةُ تظهر بشرطها**: طلبٌ بتفضيلٍ نسائيٍّ لا يُشارَك
            إلا باختيارٍ صريح — والسطرُ يقول ماذا يعني قبل أن تختاره، لا بعده. */}
        {shareOffered ? (
          <div className="rounded-12 border border-line bg-surface p-12">
            <label className="flex items-center gap-10">
              <input
                type="checkbox"
                className="size-16 shrink-0 accent-brand"
                checked={share}
                onChange={(event) => {
                  setShare(event.target.checked);
                  // موافقةٌ أُعطيت ثم أُطفئ المفتاحُ لا تبقى محفوظةً لمرةٍ ثانية
                  if (!event.target.checked) setShareGendered(false);
                }}
              />
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-6 text-14 font-medium text-ink">
                  <Users className="size-16 text-muted" />
                  شارك الرحلة ووفّر
                </span>
                <span className="mt-2 block text-11.5 leading-snug text-muted">
                  قد ينضم راكبٌ آخر في طريقك، وتدفع{" "}
                  {formatMoney(estimate!.share_fare!, estimate?.currency)} بدل{" "}
                  {formatMoney(estimate!.estimated_fare, estimate?.currency)} —
                  وتصل متأخراً قليلاً. والسعرُ لك حتى لو لم يوجد شريك.
                </span>
              </span>
            </label>

            {share && shareGuarded ? (
              <label className="mt-10 flex items-start gap-10 rounded-12 border border-brand-brd bg-brand-soft p-10">
                <input
                  type="checkbox"
                  className="mt-2 size-16 shrink-0 accent-brand"
                  checked={shareGendered}
                  onChange={(event) => setShareGendered(event.target.checked)}
                />
                <span className="text-11.5 leading-snug text-ink">
                  طلبكِ يحدّد جنس الكبتن. أوافق على أن تشاركني الرحلةَ{" "}
                  <b>راكبةٌ أخرى</b> — ولن يُضاف راكبٌ من غير ذلك.
                </span>
              </label>
            ) : null}
          </div>
        ) : null}

        {/* ورقةُ الكوبون (12-ز) — وتُخفى كلُّها حيث المفتاح مطفأ: زرٌّ يقول
            «كوبون» في سوقٍ لا كوبوناتَ فيه يفتح حقلاً لا رمزَ يُقبل فيه */}
        {promoEnabled ? (
          <div className="rounded-12 border border-line bg-surface p-12">
            {applied ? (
              <div className="flex items-center justify-between gap-8">
                <span className="flex items-center gap-8 text-14 font-medium text-ok">
                  <TicketPercent className="size-16" />
                  خصم مُطبَّق — {formatMoney(applied.discount, applied.currency)}
                </span>
                <button
                  type="button"
                  aria-label="أزل الكوبون"
                  onClick={() => {
                    setApplied(null);
                    setCouponInput("");
                    setCouponError(null);
                  }}
                  className="pressable text-muted"
                >
                  <X className="size-16" />
                </button>
              </div>
            ) : couponOpen ? (
              <div className="space-y-8">
                <label className="text-12 text-muted" htmlFor="promo">
                  رمز الكوبون
                </label>
                <div className="flex gap-8">
                  <input
                    id="promo"
                    dir="ltr"
                    autoFocus
                    maxLength={32}
                    placeholder="WELCOME"
                    className="field flex-1 uppercase"
                    value={couponInput}
                    onChange={(event) => setCouponInput(event.target.value)}
                  />
                  <Button
                    size="md"
                    className="w-auto px-16"
                    loading={checking}
                    disabled={couponInput.trim().length < 2 || !estimate}
                    onClick={() => void apply()}
                  >
                    تطبيق
                  </Button>
                </div>
                <ErrorNote message={couponError} />
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setCouponOpen(true)}
                className="pressable flex w-full items-center gap-8 text-14 font-medium text-ink"
              >
                <TicketPercent className="size-16 text-muted" />
                عندي كوبون خصم
              </button>
            )}
          </div>
        ) : null}

        {blockedByPreference ? (
          <div className="rounded-12 border border-warn bg-surface-2 px-14 py-12">
            <p className="text-14 font-medium text-ink">
              خدمة الكبتنات غير مفعّلة في بلدك الآن
            </p>
            <p className="mt-4 text-12 leading-relaxed text-muted">
              في حسابك تفضيلٌ محفوظ بطلب كبتنة، ولا يمكن تنفيذه هنا — فتُرفض كل
              رحلة. أعِد التفضيل إلى «أي كبتن» لتتمكّني من الطلب، ويبقى بإمكانك
              تغييره متى عادت الخدمة.
            </p>
            <button
              type="button"
              onClick={onClearPreference}
              className="pressable mt-10 w-full rounded-12 border border-line bg-surface py-10 text-14 font-medium text-ink"
            >
              اقبل أي كبتن
            </button>
          </div>
        ) : null}
        {/* **وسطرُ الخطأ انتقل إلى القدم فوق الزرّ** (قرارُ المالك 2026-08-23):
            خطأٌ عن زرٍّ يجب أن يُرى مع الزرّ — ومن يضغط «اطلب» وسببُ الرفض
            ممرَّرٌ خارج نظره يعيد الضغطَ على ما لن ينجح. **ولوحةُ
            `blockedByPreference` بقيت هنا**: هي شرحٌ وزرُّ علاجٍ لا سطرَ خطأ
            عن هذا الزرّ، ونقلُها إلى القدم يبتلع القدمَ كلَّها. */}

        {/* ملاحظةُ الدفع المختلط (`fareNote` في التصميم) — تحت الزرّ لا فوقه
            لأنها تصف ما سيقع بعد الضغط، وتظهر بشرطها وحده: صندوقٌ رماديٌّ دائم
            يُقرأ زينةً ثم لا يُقرأ حين يعني شيئاً */}
        {walletNote ? (
          <p className="rounded-12 border border-brand-brd bg-brand-soft px-13 py-10 text-11.5 leading-snug text-muted">
            {walletNote}
          </p>
        ) : null}


        {/* **حدّد موعداً** (12-ط) — وتُخفى كلُّها حيث المفتاح مطفأ. وهي زرٌّ
            ثانويٌّ لا مساوٍ للأول: الطلبُ الفوريُّ هو الغالب، وزرّان متساويان
            يجعلان أحدَهما يُضغط بالخطأ */}
        {scheduled ? (
          scheduling ? (
            <div className="space-y-8 rounded-12 border border-line bg-surface p-12">
              <label className="text-12 text-muted" htmlFor="booking-when">
                موعد الانطلاق
              </label>
              <input
                id="booking-when"
                type="datetime-local"
                className="field w-full"
                value={when}
                min={localInputValue(earliest())}
                max={localInputValue(latest())}
                onChange={(event) => setWhen(event.target.value)}
              />
              <p className="text-11 leading-snug text-muted">
                نبدأ البحث عن كبتنٍ قبل موعدك بعشر دقائق.{" "}
                <b className="text-ink">والسعر يُحسب عند التنفيذ</b> — الرقمُ
                أعلاه تقديرُ اليوم.
              </p>
              <div className="flex gap-8">
                <Button
                  size="md"
                  className="flex-1"
                  disabled={!when}
                  onClick={() => onSchedule(category, preference, when)}
                >
                  ثبّت الحجز
                </Button>
                <button
                  type="button"
                  onClick={() => setScheduling(false)}
                  className="pressable rounded-13 border border-line px-16 text-13 text-muted"
                >
                  إلغاء
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => {
                setWhen(localInputValue(earliest()));
                setScheduling(true);
              }}
              className="pressable flex w-full items-center justify-center gap-8 rounded-13 border border-line py-12 text-13.5 font-semibold text-ink"
            >
              <CalendarClock className="size-16 text-muted" />
              حدّد موعداً
            </button>
          )
        ) : null}

        <p className="text-center text-12 text-muted">
          السعر النهائي قد يتغيّر إن اختلف المسار الفعلي كثيراً عن المقدَّر.
        </p>
      </div>

      {pickingPay && payMethod ? (
        <PaymentPicker
          channels={channels}
          selected={payMethod.method}
          onSelect={choose}
          onClose={() => setPickingPay(false)}
          walletHint={
            balance === null
              ? null
              : `الرصيد: ${formatMoney(balance, estimate?.currency ?? countryConfig?.currency)}`
          }
        />
      ) : null}
    </Sheet>
  );
}
