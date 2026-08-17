/** ما يراه الراكب بعد الطلب: البحث، ثم بطاقة الكبتن، ثم حالة الرحلة.
 *
 * (SPEC القسم 11.4) — بطاقة الكبتن تظهر **بعد القبول** وحده، وقبله مؤشرُ بحثٍ
 * حيّ: الراكب ينتظر على الشاشة والتوزيع يعرض على كبتنٍ بعد كبتن (القسم 5.3).
 *
 * **الإلغاء مجانيٌّ قبل القبول** وبعده رسمٌ (القسم 5)، فالتحذير يظهر عند
 * القبول لا قبله. والرسمُ نفسه لا يُعرض رقماً هنا: قيمته إعدادُ دولةٍ تقرأه
 * الخلفية عند الإلغاء، ورقمٌ نعرضه من عندنا قد يخالف ما يُخصم.
 */

import { motion } from "framer-motion";
import { Car, Clock, Phone, Share2, ShieldCheck, Star, X } from "lucide-react";
import { useState } from "react";
import { DriverAvatar } from "@/components/ride/DriverAvatar";

import { ApiError } from "@/api/client";
import { cancelRide } from "@/api/endpoints";
import type { Ride } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { PauseNotice } from "@/components/ride/PauseNotice";
import { StopProgress } from "@/components/ride/StopProgress";
import { Sheet } from "@/components/ui/Sheet";
import { RIDE_STATUS_LABEL, VEHICLE_LABEL } from "@/lib/labels";
import { cn, formatDistance, formatMoney } from "@/lib/utils";

const CANCELLABLE = new Set(["requested", "searching", "accepted", "arrived"]);

interface CancelReason {
  label: string;
  /** `undefined` = نصٌّ حر بلا أثرٍ على الرسوم؛ والمصنَّف يغيّر السلوك. */
  code?: "gender_mismatch";
}

/** أسبابُ الإلغاء كما في التصميم — والنصُّ الحرّ يصل الإدارة كما كُتب. */
const CANCEL_REASONS: CancelReason[] = [
  { label: "الكبتن تأخر" },
  { label: "غيّرت رأيي" },
  { label: "الكبتن ليس أنثى — عدم تطابق", code: "gender_mismatch" },
  { label: "عنوان الالتقاء خطأ" },
];

/** «أرسل تفاصيل رحلتك» (SPEC القسم 11.4) — نصٌّ يُرسل عبر ورقة مشاركة النظام.
 *
 * **وسُمّي بغير «مشاركة الرحلة» بعد 12-ي**: صارت المشاركةُ اسماً لشيءٍ آخر —
 * راكبٌ ثانٍ في السيارة — وشارةُ «رحلة مشتركة» تقف الآن على الورقة نفسِها فوق
 * هذا الزرِّ بالضبط. فكلمتان متجاورتان تعنيان أمرين مختلفين تجعلان من يضغط
 * يظنّ أنه يضيف راكباً أو يظنّ أن رحلتَه صارت مشتركةً بضغطة. والتسميةُ الجديدة
 * تقول ما يفعله الزرُّ فعلاً: يُرسل التفاصيل لمن ينتظره.
 *
 * **لا رابطَ تتبعٍ عام**: ذاك يحتاج رمزاً على `rides` يفتح الرحلة لمن لا
 * حساب له، وهو جدولٌ وعقدُ صلاحياتٍ لم يصفهما SPEC — وكل مسارٍ يلمس رحلةً
 * يتحقق من ملكيتها (القسم 14). فالمشاركة تحمل ما يطمئن المنتظِر فعلاً: اسم
 * الكبتن ولوحته والوجهة على الخريطة.
 */
async function shareRide(ride: Ride) {
  const destination = `https://maps.google.com/?q=${ride.dropoff.lat},${ride.dropoff.lng}`;
  const vehicle = ride.driver?.vehicle;
  const lines = [
    "أنا الآن في رحلة TAXO.",
    ride.driver ? `الكبتن: ${ride.driver.name}` : null,
    vehicle ? `المركبة: ${vehicle.make} ${vehicle.model} — لوحة ${vehicle.plate_number}` : null,
    `الوجهة: ${ride.dropoff_address ?? destination}`,
  ].filter(Boolean);

  const text = lines.join("\n");
  if (navigator.share) {
    await navigator.share({ title: "رحلتي على TAXO", text, url: destination }).catch(
      () => undefined,
    );
    return true;
  }
  await navigator.clipboard?.writeText(`${text}\n${destination}`).catch(() => undefined);
  return false;
}

export function TrackingSheet({
  ride,
  onChanged,
}: {
  ride: Ride;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [copied, setCopied] = useState(false);
  const [shareHintClosed, setShareHintClosed] = useState(false);
  const [reason, setReason] = useState<CancelReason | null>(null);

  const searching = ride.status === "requested" || ride.status === "searching";
  // «رحلةٌ نسائية» = ما طُلب فيها جنسٌ بعينه — وصفٌ للطلب لا لصاحبته
  const gendered = ride.gender_preference !== "any";
  const afterAccept = ride.status === "accepted" || ride.status === "arrived";

  async function cancel() {
    setBusy(true);
    setError(null);
    try {
      await cancelRide(ride.id, reason?.label, reason?.code);
      onChanged();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر إلغاء الرحلة");
    } finally {
      setBusy(false);
      setConfirming(false);
    }
  }

  return (
    <Sheet>
      <div className="space-y-16 pb-16">
        <div className="flex items-start justify-between gap-12">
          <div>
            <p className="text-18 font-semibold text-ink">{RIDE_STATUS_LABEL[ride.status]}</p>
            <p className="text-14 text-muted">
              {searching
                ? "نعرض طلبك على أقرب الكباتن — قد يستغرق دقيقتين"
                : ride.status === "in_progress"
                  ? `المسافة المقدّرة ${formatDistance(ride.distance_km)}`
                  : ride.dropoff_address ?? "في الطريق إلى وجهتك"}
            </p>
          </div>
          <div className="text-end">
            {/* شارةُ «رحلة نسائية» — وصفُ الطلب، وتطمينٌ بصريٌّ بأن الشرط
                الذي طلبته سارٍ فعلاً على هذه الرحلة (المرحلة 10-ج) */}
            {gendered ? (
              <span className="mb-6 inline-block rounded-full border border-brand-brd bg-brand-soft px-10 py-4 text-12 font-semibold text-brand">
                رحلة نسائية
              </span>
            ) : null}
            {/* شارةُ المشاركة (12-ي) — **وحالتان لا واحدة**: «انضم راكب» خبرٌ
                وقع، و«بانتظار شريك» حالٌ تنتظر. وخلطُهما يجعل الشارةَ تَعِد
                بمن لم يأتِ. **والسعرُ تحتها لا يتغيّر في الحالين**: الخصمُ
                محفوظٌ ولو لم يوجد شريك (قرارُ المالك الثالث)، فوعدٌ يُخلَف على
                شاشةٍ يقرؤها راكبٌ في الطريق أسوأُ من ألّا يُعرض */}
            {Number(ride.share_discount_percent) > 0 ? (
              <span className="mb-6 me-4 inline-block rounded-full border border-line bg-surface-2 px-10 py-4 text-12 font-semibold text-muted">
                {ride.share_group_id ? "رحلة مشتركة" : "بانتظار شريك"}
              </span>
            ) : null}
            <p className="text-12 text-muted">السعر المقدّر</p>
            <p className="font-bold text-ink">
              {formatMoney(ride.estimated_fare, ride.currency)}
            </p>
          </div>
        </div>

        {searching ? <SearchingPulse /> : null}

        {/* المحطاتُ وعدّادُ الانتظار — يظهران بمجرد وجود محطة، لا عند الوقوف
            وحده: الراكبُ يريد أن يرى أين هو من طريقه قبل أن يقف */}
        <StopProgress ride={ride} />
        {/* **الوقفةُ غير المخطَّطة تُعلن حين تنشأ** (§5.10-ب) — لا رقمٌ يظهر
            في الفاتورة آخرَ الرحلة */}
        <PauseNotice ride={ride} />

        {/* الانتظارُ الأطول قيل ثمنُه قبل الضغط (`ConfirmRide`)، ويُعاد قوله
            هنا لأن هذه هي اللحظة التي يُشعر فيها: دقيقةُ صمتٍ بلا سببٍ تُقرأ
            عطلاً، والسببُ المكتوب يجعلها انتظاراً مفهوماً (المرحلة 10-ج) */}
        {searching && gendered ? (
          <p className="flex items-start gap-8 rounded-12 border border-line bg-bg px-12 py-10 text-12 leading-relaxed text-muted">
            <Clock className="mt-2 size-14 shrink-0" />
            نبحث عن كبتنة متاحة. عددهنّ أقل، فقد يطول الانتظار قليلاً — ونوسّع
            دائرة البحث قبل أن نعتذر.
          </p>
        ) : null}

        {/* اقتراحُ المشاركة عند بدء رحلةٍ نسائية (المرحلة 10-ج). الزرُّ قائمٌ
            أسفل الورقة لكلِّ رحلة؛ وما يضيفه هذا الاقتراح **التوقيت**: لحظةَ
            تحرّك السيارة لا قبلها، ولمن طلبت الخدمة لا للجميع — واقتراحٌ
            يظهر لكل راكبٍ في كل رحلة يصير خلفيةً لا يراها أحد.
            ويُطوى بالضغط: تذكيرٌ لا يُطوى يصير مضايقة */}
        {ride.status === "in_progress" && gendered && !shareHintClosed ? (
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-start gap-12 rounded-12 border border-brand-brd bg-brand-soft p-12"
          >
            <ShieldCheck className="mt-2 size-16 shrink-0 text-ink" />
            <div className="min-w-0 flex-1">
              <p className="text-14 font-medium text-ink">
                شاركي رحلتك مع من تثقين
              </p>
              <p className="mt-2 text-12 leading-relaxed text-muted">
                نرسل اسم الكبتن ولوحة المركبة والوجهة — بلا موقعك اللحظي.
              </p>
              <div className="mt-8 flex gap-8">
                <Button
                  size="sm"
                  onClick={async () => {
                    const shared = await shareRide(ride);
                    if (!shared) {
                      setCopied(true);
                      window.setTimeout(() => setCopied(false), 2_500);
                    }
                    setShareHintClosed(true);
                  }}
                >
                  <Share2 className="size-16" />
                  مشاركة
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setShareHintClosed(true)}
                >
                  ليس الآن
                </Button>
              </div>
            </div>
          </motion.div>
        ) : null}

        {ride.driver ? (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-12 rounded-16 border border-line bg-bg p-12"
          >
            <DriverAvatar
              rideId={ride.id}
              name={ride.driver.name}
              className="size-48 text-18"
            />
            <div className="min-w-0 flex-1">
              <p className="truncate font-semibold text-ink">{ride.driver.name}</p>
              <p className="flex items-center gap-4 text-14 text-muted">
                <Star className="size-14 fill-brand text-brand" />
                {Number(ride.driver.rating_avg).toFixed(1)}
                {ride.driver.vehicle ? (
                  <>
                    <span aria-hidden>·</span>
                    <span className="truncate">
                      {ride.driver.vehicle.make} {ride.driver.vehicle.model} —{" "}
                      {VEHICLE_LABEL[ride.driver.vehicle.category]}
                    </span>
                  </>
                ) : null}
              </p>
            </div>
            {ride.driver.vehicle ? (
              <div className="shrink-0 rounded-8 border border-line bg-surface px-10 py-6 text-center">
                <p className="text-12 text-muted">اللوحة</p>
                <p dir="ltr" className="font-bold text-ink">
                  {ride.driver.vehicle.plate_number}
                </p>
              </div>
            ) : (
              <Car className="size-24 text-muted" />
            )}
          </motion.div>
        ) : null}

        <ErrorNote message={error} />

        <div className="flex gap-8">
          <Button
            variant="secondary"
            className="flex-1"
            onClick={async () => {
              const shared = await shareRide(ride);
              if (!shared) {
                setCopied(true);
                window.setTimeout(() => setCopied(false), 2_500);
              }
            }}
          >
            <Share2 className="size-16" />
            {copied ? "نُسخت التفاصيل" : "أرسل تفاصيل رحلتك"}
          </Button>

          {CANCELLABLE.has(ride.status) ? (
            <Button
              variant="ghost"
              className="text-danger"
              onClick={() => setConfirming(true)}
              disabled={busy}
            >
              <X className="size-16" />
              إلغاء
            </Button>
          ) : null}
        </div>

        {confirming ? (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="space-y-12 rounded-12 border border-danger bg-surface-2 p-12"
          >
            <p className="text-14 text-ink">
              {afterAccept
                ? "الكبتن في طريقه إليك — قد تُطبَّق رسوم إلغاء."
                : "سيتوقف البحث عن كبتن. متأكد؟"}
            </p>

            {/* أسبابٌ مصنَّفة تظهر **بعد الإسناد** وحده: قبله لا كبتن يُشتكى
                منه. و«ليس أنثى» لا تُعرض إلا على رحلةٍ طُلب فيها جنس — والخلفية
                ترفضها في غيرها، فعرضُها هناك يعلّم الضغط ثم الارتداد */}
            {afterAccept ? (
              <div className="flex flex-col gap-6">
                {CANCEL_REASONS.filter(
                  (option) => option.code !== "gender_mismatch" || gendered,
                ).map((option) => (
                  <button
                    key={option.label}
                    type="button"
                    onClick={() => setReason(option)}
                    className={cn(
                      "pressable rounded-12 border px-12 py-10 text-start text-14 transition",
                      reason?.label === option.label
                        ? "border-brand-brd bg-brand-soft font-semibold text-brand"
                        : "border-line bg-surface text-ink",
                    )}
                  >
                    {option.label}
                  </button>
                ))}
                {reason?.code === "gender_mismatch" ? (
                  <p className="rounded-12 border border-brand-brd bg-brand-soft p-12 text-12 leading-relaxed text-ink">
                    بلا رسوم إلغاء على أيٍّ من الطرفين. ويُسجَّل بلاغٌ على
                    الحساب الآخر، وتكرارُ البلاغات يوسم الحساب للمراجعة.
                  </p>
                ) : null}
              </div>
            ) : null}

            <div className="flex gap-8">
              <Button variant="danger" className="flex-1" loading={busy} onClick={cancel}>
                نعم، ألغِ الرحلة
              </Button>
              <Button variant="secondary" onClick={() => setConfirming(false)}>
                تراجع
              </Button>
            </div>
          </motion.div>
        ) : null}

        {ride.status === "arrived" ? (
          <p className="flex items-center justify-center gap-8 text-14 text-muted">
            <Phone className="size-16" />
            الكبتن ينتظرك في نقطة الانطلاق
          </p>
        ) : null}
      </div>
    </Sheet>
  );
}

/** مؤشر البحث الحي (SPEC القسم 11.4) — حلقةٌ تتمدّد لا شريطُ تقدّمٍ كاذب:
 * لا نعرف كم يبقى، وشريطٌ يتقدّم يَعِد بما لا نملكه. */
function SearchingPulse() {
  return (
    <div className="flex items-center justify-center py-8">
      <span className="relative flex size-48 items-center justify-center">
        <span className="absolute inline-flex size-48 rounded-full bg-brand-soft animate-pulse-ring" />
        <span
          className="absolute inline-flex size-48 rounded-full bg-brand-soft animate-pulse-ring"
          style={{ animationDelay: "0.6s" }}
        />
        <Car className="relative size-24 text-ink" />
      </span>
    </div>
  );
}
