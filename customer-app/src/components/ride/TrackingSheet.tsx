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
import { Car, Phone, Share2, Star, X } from "lucide-react";
import { useState } from "react";

import { ApiError } from "@/api/client";
import { cancelRide } from "@/api/endpoints";
import type { Ride } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { Sheet } from "@/components/ui/Sheet";
import { RIDE_STATUS_LABEL, VEHICLE_LABEL } from "@/lib/labels";
import { formatDistance, formatMoney } from "@/lib/utils";

const CANCELLABLE = new Set(["requested", "searching", "accepted", "arrived"]);

/** «مشاركة الرحلة» (SPEC القسم 11.4) — نصٌّ يُرسل عبر ورقة مشاركة النظام.
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

  const searching = ride.status === "requested" || ride.status === "searching";
  const afterAccept = ride.status === "accepted" || ride.status === "arrived";

  async function cancel() {
    setBusy(true);
    setError(null);
    try {
      await cancelRide(ride.id);
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
      <div className="space-y-4 pb-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-lg font-semibold text-ink">{RIDE_STATUS_LABEL[ride.status]}</p>
            <p className="text-sm text-muted">
              {searching
                ? "نعرض طلبك على أقرب الكباتن — قد يستغرق دقيقتين"
                : ride.status === "in_progress"
                  ? `المسافة المقدّرة ${formatDistance(ride.distance_km)}`
                  : ride.dropoff_address ?? "في الطريق إلى وجهتك"}
            </p>
          </div>
          <div className="text-end">
            <p className="text-xs text-muted">السعر المقدّر</p>
            <p className="font-bold text-ink">
              {formatMoney(ride.estimated_fare, ride.currency)}
            </p>
          </div>
        </div>

        {searching ? <SearchingPulse /> : null}

        {ride.driver ? (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex items-center gap-3 rounded-2xl border border-line bg-bg p-3"
          >
            <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-brand/20 text-lg font-bold text-ink">
              {ride.driver.name.slice(0, 1)}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate font-semibold text-ink">{ride.driver.name}</p>
              <p className="flex items-center gap-1 text-sm text-muted">
                <Star className="size-3.5 fill-brand text-brand" />
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
              <div className="shrink-0 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-center">
                <p className="text-xs text-muted">اللوحة</p>
                <p dir="ltr" className="font-bold text-ink">
                  {ride.driver.vehicle.plate_number}
                </p>
              </div>
            ) : (
              <Car className="size-6 text-muted" />
            )}
          </motion.div>
        ) : null}

        <ErrorNote message={error} />

        <div className="flex gap-2">
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
            <Share2 className="size-4" />
            {copied ? "نُسخت التفاصيل" : "مشاركة الرحلة"}
          </Button>

          {CANCELLABLE.has(ride.status) ? (
            <Button
              variant="ghost"
              className="text-danger"
              onClick={() => setConfirming(true)}
              disabled={busy}
            >
              <X className="size-4" />
              إلغاء
            </Button>
          ) : null}
        </div>

        {confirming ? (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            className="space-y-3 rounded-xl border border-danger/40 bg-danger/5 p-3"
          >
            <p className="text-sm text-ink">
              {afterAccept
                ? "الكبتن في طريقه إليك — قد تُطبَّق رسوم إلغاء."
                : "سيتوقف البحث عن كبتن. متأكد؟"}
            </p>
            <div className="flex gap-2">
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
          <p className="flex items-center justify-center gap-2 text-sm text-muted">
            <Phone className="size-4" />
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
    <div className="flex items-center justify-center py-2">
      <span className="relative flex size-12 items-center justify-center">
        <span className="absolute inline-flex size-12 rounded-full bg-brand/40 animate-pulse-ring" />
        <span
          className="absolute inline-flex size-12 rounded-full bg-brand/30 animate-pulse-ring"
          style={{ animationDelay: "0.6s" }}
        />
        <Car className="relative size-6 text-ink" />
      </span>
    </div>
  );
}
