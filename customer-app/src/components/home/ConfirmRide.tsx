/** تأكيد الطلب: الفئة، والسعر المقدَّر، وزرُّ الطلب (SPEC القسم 11.3).
 *
 * **السعر يأتي من `POST /rides/estimate` ولا يُحسب هنا أبداً** (القسم 14):
 * الواجهة تعرض ما قالته الخلفية بحروفه — لا ضربَ مسافةٍ في تعرفة، ولا حتى
 * جمعَ رسمٍ على مبلغ. وتبديلُ الفئة يعيد السؤال لأن التعرفة لكل فئة.
 *
 * **ورسمُ الانتظار يُقال قبل الطلب** (المرحلة 12-ب): لا يدخل التقدير لأنه لا
 * يُعرف قبل أن يقع، **فيُقال سعرُه** — فيكون معلوماً ولو لم يكن مقدَّراً.
 * والقيمُ من `GET /rides/estimate`؟ لا: من الرحلة بعد إنشائها. وقبلها من
 * تسعيرة الدولة المنشورة؟ لا تُنشر. فالسطرُ يُصاغ من **الرسوم المجمَّدة على
 * الرحلة** بعد الطلب، وقبله يقول ما يقع لا كم يكلّف — وهذا هو الصدق الممكن.
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
import { StopsEditor, type DraftStop } from "@/components/home/StopsEditor";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { Sheet } from "@/components/ui/Sheet";
import { VEHICLE_HINT, VEHICLE_LABEL } from "@/lib/labels";
import { useMultiStop } from "@/lib/multistop";
import { useWomenService } from "@/lib/women";
import { cn, formatDistance, formatDuration, formatMoney } from "@/lib/utils";

/** نصٌّ لكل خيار — والثلاثةُ تقول أثرَه على الانتظار لا اسمَه. */
const PREFERENCE_NOTE: Record<GenderPreference, string> = {
  female: "سيبحث النظام عن كبتنات فقط، ضمن نطاق ١٠ كم بدل ٧ — قد يطول الانتظار.",
  male: "سيبحث النظام عن كبتنٍ رجل فقط، ضمن نطاق ١٠ كم.",
  any: "أي كبتن متاح — أسرع استجابة وأوسع نطاق.",
};

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
  stops: DraftStop[];
  onStopsChange: (next: DraftStop[]) => void;
  onAddStop: () => void;
}) {
  const women = useWomenService();
  const multiStop = useMultiStop();
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

  return (
    <Sheet>
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
              className="block w-full truncate text-start font-medium text-ink"
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
            waitingNote={
              "يقف الكبتن عند كل محطة، وللانتظار دقائقُ مجانية ثم رسمٌ لكل دقيقة — يظهر عدّادُه أمامك أثناء الوقوف."
            }
          />
        ) : null}

        <div className="grid grid-cols-2 gap-8">
          {categories.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setCategory(option)}
              className={cn(
                "rounded-12 border p-12 text-start transition",
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
                    "rounded-12 border p-12 text-center text-14 font-medium transition",
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
                  <p className="text-24 font-bold text-ink">
                    {formatMoney(estimate.estimated_fare, estimate.currency)}
                  </p>
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

        <ErrorNote message={error ?? requestError} />

        <Button
          size="lg"
          loading={requesting}
          disabled={!estimate || loading}
          onClick={() => onRequest(category, preference)}
        >
          اطلب الرحلة
        </Button>

        <p className="text-center text-12 text-muted">
          السعر النهائي قد يتغيّر إن اختلف المسار الفعلي كثيراً عن المقدَّر.
        </p>
      </div>
    </Sheet>
  );
}
