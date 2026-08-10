/** التقييم — **اختياري ويلي الدفع** (SPEC القسم 5.9/11.5).
 *
 * ومرةً واحدة لكل طرف: القيد `(ride_id, rater_type)` في القاعدة، فالثانية
 * ترتدّ بخطأٍ صريح تعرضه الشاشة بدل أن تخترع منعاً من عندها.
 */

import { motion } from "framer-motion";
import { Star } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { listRideRatings, rateRide } from "@/api/endpoints";
import { Button } from "@/components/ui/Button";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { Screen } from "@/components/ui/Screen";
import { cn } from "@/lib/utils";

export function RatingScreen() {
  const { rideId = "" } = useParams();
  const navigate = useNavigate();

  const [stars, setStars] = useState(0);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    listRideRatings(rideId)
      .then((entries) => {
        const mine = entries.find((entry) => entry.rater_type === "rider");
        if (mine) {
          setStars(mine.stars);
          setComment(mine.comment ?? "");
          setDone(true);
        }
      })
      .catch(() => undefined);
  }, [rideId]);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await rateRide(rideId, stars, comment);
      setDone(true);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر إرسال التقييم");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen title="تقييم الرحلة" back="/">
      <div className="space-y-6">
        <p className="text-center text-muted">كيف كانت رحلتك مع الكبتن؟</p>

        <div className="flex justify-center gap-2" role="radiogroup" aria-label="عدد النجوم">
          {[1, 2, 3, 4, 5].map((value) => (
            <motion.button
              key={value}
              type="button"
              role="radio"
              aria-checked={stars === value}
              aria-label={`${value} من 5`}
              whileTap={{ scale: 0.88 }}
              disabled={done}
              onClick={() => setStars(value)}
              className="p-1 disabled:opacity-70"
            >
              <Star
                className={cn(
                  "size-9 transition",
                  value <= stars ? "fill-brand text-brand" : "text-line",
                )}
              />
            </motion.button>
          ))}
        </div>

        <div>
          <label className="label" htmlFor="comment">
            ملاحظة (اختيارية)
          </label>
          <textarea
            id="comment"
            className="field min-h-24 resize-none"
            maxLength={500}
            value={comment}
            disabled={done}
            onChange={(event) => setComment(event.target.value)}
            placeholder="ما الذي أعجبك أو يمكن تحسينه؟"
          />
        </div>

        <ErrorNote message={error} />
        {done ? <SuccessNote message="شكراً — وصلنا تقييمك." /> : null}

        {done ? (
          <Button size="lg" onClick={() => navigate("/", { replace: true })}>
            العودة للرئيسية
          </Button>
        ) : (
          <>
            <Button size="lg" loading={busy} disabled={stars === 0} onClick={submit}>
              إرسال التقييم
            </Button>
            <Button
              variant="ghost"
              className="w-full"
              onClick={() => navigate("/", { replace: true })}
            >
              تخطّي
            </Button>
          </>
        )}
      </div>
    </Screen>
  );
}
