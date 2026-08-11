/** تقييم الراكب — SPEC القسم 5/9، وشكلُه من `DESIGN.md` §5.3.
 *
 * يلي التحصيلَ مباشرةً في تدفّق القسم 5. و**التقييم اختياري**: رحلةٌ بلا
 * تقييمٍ رحلةٌ مكتملة (`models/rating.py`)، فزرُّ «تخطي» ليس مهرباً بل مسارٌ
 * صحيح — ومن يفرض التقييم يحصل على نجومٍ عشوائية لا على رأي.
 *
 * ولا يُرسل التقييم مرتين: القيد الفريد `(ride_id, rater_type)` في القاعدة هو
 * الحارس، والواجهةُ تعرض رسالتَه إن وقع سباق.
 *
 * والشكل: صورةٌ رمزية 60، عنوان 19/700، نجومٌ 32 بفجوة 8 وهامش `24px 0 30px`
 * في صفٍّ `dir="ltr"` — النجومُ تُقرأ من اليسار في كل اللغات.
 */

import { useState } from "react";

import { ApiError } from "@/api/client";
import { rateRide } from "@/api/endpoints";
import type { Ride } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { cn } from "@/lib/utils";

interface Props {
  ride: Ride;
  onDone: () => void;
}

export function RateRiderScreen({ ride, onDone }: Props) {
  const [stars, setStars] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await rateRide(ride.id, stars);
      onDone();
    } catch (caught) {
      // «سبق أن قيّمت» ليست عطلاً يحبس الكبتن على الشاشة
      if (caught instanceof ApiError && caught.code === "already_rated") {
        onDone();
        return;
      }
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر إرسال التقييم",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col justify-center bg-bg px-28 pb-safe pt-safe text-center">
      <div className="mx-auto mb-14 flex size-60 items-center justify-center rounded-full border border-line bg-surface-2 text-19 font-bold text-ink">
        ر
      </div>
      <h1 className="text-19 font-bold text-ink">قيّم الراكب</h1>
      <p className="mt-4 text-12.5 text-muted">راكب هذه الرحلة</p>

      <div dir="ltr" className="mb-30 mt-24 flex justify-center gap-8">
        {[1, 2, 3, 4, 5].map((value) => (
          <button
            key={value}
            type="button"
            aria-label={`${value} نجوم`}
            onClick={() => setStars(value)}
            className={cn(
              "text-32 leading-hero",
              value <= stars ? "text-warn" : "text-line",
            )}
          >
            ★
          </button>
        ))}
      </div>

      <ErrorNote message={error} />

      <Button
        className="mt-12"
        loading={busy}
        disabled={stars === 0}
        onClick={() => void submit()}
      >
        إرسال
      </Button>
      <button
        type="button"
        onClick={onDone}
        className="mt-14 text-12.5 font-semibold text-muted"
      >
        تخطي
      </button>
    </div>
  );
}
