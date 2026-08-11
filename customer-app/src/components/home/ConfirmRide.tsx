/** تأكيد الطلب: الفئة، والسعر المقدَّر، وزرُّ الطلب (SPEC القسم 11.3).
 *
 * **السعر يأتي من `POST /rides/estimate` ولا يُحسب هنا أبداً** (القسم 14):
 * الواجهة تعرض ما قالته الخلفية بحروفه — لا ضربَ مسافةٍ في تعرفة، ولا حتى
 * جمعَ رسمٍ على مبلغ. وتبديلُ الفئة يعيد السؤال لأن التعرفة لكل فئة.
 *
 * **واختيارُ «كبتنة فقط» يقول ثمنَه قبل الضغط لا بعده** (المرحلة 10-ج):
 * الكبتنات أقل عدداً، فالانتظارُ أطول والبحثُ يتسع إلى ١٠كم. وقولُ ذلك هنا
 * يجعل الانتظار خياراً اختارته؛ والسكوتُ عنه يجعله عطلاً يُشتكى منه — ثم
 * «لم نجد كبتناً» بلا سبب.
 */

import { AnimatePresence, motion } from "framer-motion";
import { Car, CircleDot, Clock, MapPin, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { estimateRide } from "@/api/endpoints";
import type {
  Coordinates,
  GenderPreference,
  RideEstimate,
  VehicleCategory,
} from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { Sheet } from "@/components/ui/Sheet";
import { VEHICLE_HINT, VEHICLE_LABEL } from "@/lib/labels";
import { useWomenService } from "@/lib/women";
import { cn, formatDistance, formatDuration, formatMoney } from "@/lib/utils";

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
}: {
  pickup: Coordinates;
  pickupAddress: string | null;
  dropoff: Coordinates;
  dropoffAddress: string | null;
  categories: VehicleCategory[];
  onEditDestination: () => void;
  onRequest: (category: VehicleCategory, preference: GenderPreference) => void;
  requesting: boolean;
  requestError: string | null;
}) {
  const women = useWomenService();
  const [category, setCategory] = useState<VehicleCategory>(categories[0] ?? "economy");
  // يبدأ من افتراضي ملفها ثم تغيّره لهذه الرحلة وحدها
  const [preference, setPreference] = useState<GenderPreference>(
    women.defaultPreference,
  );
  const [estimate, setEstimate] = useState<RideEstimate | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    estimateRide({ pickup, dropoff, vehicle_category: category })
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
  }, [pickup, dropoff, category]);

  return (
    <Sheet>
      <div className="space-y-4 pb-4">
        {/* المسار: نقطتان وخطٌّ بينهما — أوضح من سطرين نصّيين */}
        <div className="flex gap-3">
          <div className="flex flex-col items-center pt-1.5">
            <CircleDot className="size-4 text-success" />
            <span className="my-1 h-6 w-px bg-line" />
            <MapPin className="size-4 text-danger" />
          </div>
          <div className="min-w-0 flex-1 space-y-3">
            <p className="truncate text-sm text-muted">
              {pickupAddress ?? "نقطة الانطلاق المحددة"}
            </p>
            <button
              type="button"
              onClick={onEditDestination}
              className="block w-full truncate text-start font-medium text-ink"
            >
              {dropoffAddress ?? "الوجهة المحددة"}
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          {categories.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setCategory(option)}
              className={cn(
                "rounded-xl border p-3 text-start transition",
                option === category
                  ? "border-brand bg-brand/10"
                  : "border-line bg-surface hover:bg-line/30",
              )}
            >
              <span className="flex items-center gap-2 font-medium text-ink">
                <Car className="size-4" />
                {VEHICLE_LABEL[option]}
              </span>
              <span className="mt-0.5 block text-xs text-muted">
                {VEHICLE_HINT[option]}
              </span>
            </button>
          ))}
        </div>

        {/* لا يظهر هذا الصف إلا لمن عُرضت عليها الخدمة — والقرارُ في
            `lib/women.ts` وحده */}
        {women.available ? (
          <div>
            <div className="grid grid-cols-2 gap-2">
              {(
                [
                  { value: "any", label: "أي كبتن" },
                  { value: "female", label: "كبتنة فقط" },
                ] as const
              ).map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setPreference(option.value)}
                  className={cn(
                    "rounded-xl border p-3 text-center text-sm font-medium transition",
                    option.value === preference
                      ? "border-brand bg-brand/10 text-ink"
                      : "border-line bg-surface text-muted hover:bg-line/30",
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
            {preference === "female" ? (
              <p className="mt-2 flex items-start gap-1.5 text-xs leading-relaxed text-muted">
                <Clock className="mt-0.5 size-3.5 shrink-0" />
                الكبتنات أقل عدداً، فقد ينتظر طلبك أطول — نوسّع البحث لمسافة
                أبعد قبل أن نعتذر.
              </p>
            ) : null}
          </div>
        ) : null}

        <div className="rounded-xl border border-line bg-bg px-4 py-3">
          <AnimatePresence mode="wait">
            {loading ? (
              <motion.div
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex items-center gap-2 text-sm text-muted"
              >
                <RefreshCw className="size-4 animate-spin" />
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
                  <p className="text-xs text-muted">السعر المقدّر</p>
                  <p className="text-2xl font-bold text-ink">
                    {formatMoney(estimate.estimated_fare, estimate.currency)}
                  </p>
                  {estimate.minimum_fare_applied ? (
                    <p className="mt-0.5 text-xs text-muted">طُبِّق الحد الأدنى للأجرة</p>
                  ) : null}
                </div>
                <div className="text-end text-sm text-muted">
                  <p>{formatDistance(estimate.distance_km)}</p>
                  <p>{formatDuration(estimate.duration_min)}</p>
                </div>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>

        <ErrorNote message={error ?? requestError} />

        <Button
          size="lg"
          loading={requesting}
          disabled={!estimate || loading}
          onClick={() => onRequest(category, preference)}
        >
          اطلب الرحلة
        </Button>

        <p className="text-center text-xs text-muted">
          السعر النهائي قد يتغيّر إن اختلف المسار الفعلي كثيراً عن المقدَّر.
        </p>
      </div>
    </Sheet>
  );
}
