/** التقييم — **اختياري ويلي الدفع** (SPEC القسم 5.9/11.5).
 *
 * ومرةً واحدة لكل طرف: القيد `(ride_id, rater_type)` في القاعدة، فالثانية
 * ترتدّ بخطأٍ صريح تعرضه الشاشة بدل أن تخترع منعاً من عندها.
 *
 * **والبقشيشُ هنا** (المرحلة 12-و، SPEC القسم 6.5) وشرطُ عرضه **أربعُ نجومٍ
 * فأكثر — تضييقٌ في هذه الشاشة لا قيدٌ في الخلفية**: الخلفيةُ تقبله على أي
 * رحلةٍ مكتملةٍ يملكها صاحبُها، ومن قيّم ثلاثاً وأراد أن يشكر الكبتن على حمل
 * حقيبةٍ لا يُردّ. والقاعدةُ هنا لأنها قاعدةُ **لحظةِ السؤال** لا قاعدةُ استحقاق:
 * لا يُسأل عن هديةٍ من كتب أنه غيرُ راضٍ.
 *
 * **وثلاثةُ شروطٍ للعرض تقرّرها الخلفيةُ لا هذه الشاشة** (`offered`): المفتاح،
 * والمحفظةُ — القناةُ الوحيدة — والمبالغُ المضبوطة. فلا زرَّ معطَّلاً يرفع
 * توقّعَ الكبتن ثم يخيّبه، ولا مبلغَ مكتوباً في كود التطبيق يخالف السوق الآخر.
 */

import { motion } from "framer-motion";
import { Star } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { addTip, getTipOptions, listRideRatings, rateRide } from "@/api/endpoints";
import type { TipOptions } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { Stage } from "@/components/ui/Stage";
import { cn, formatMoney } from "@/lib/utils";

/** أقلُّ عددِ نجومٍ يُسأل عنده عن بقشيش — تضييقُ واجهةٍ لا قاعدةَ خلفية. */
const TIP_MIN_STARS = 4;

export function RatingScreen() {
  const { rideId = "" } = useParams();
  const navigate = useNavigate();

  const [stars, setStars] = useState(0);
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const [tip, setTip] = useState<TipOptions | null>(null);
  const [tipping, setTipping] = useState<string | null>(null);

  useEffect(() => {
    // **الخلفيةُ تقول إن كان يُعرض** — ونداءٌ يفشل لا يُظهر خطأً: البقشيشُ
    // إضافةٌ على شاشة التقييم لا سببٌ لتعطيلها
    getTipOptions(rideId)
      .then(setTip)
      .catch(() => setTip(null));
  }, [rideId]);

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

  async function sendTip(amount: string) {
    setTipping(amount);
    setError(null);
    try {
      const given = await addTip(rideId, amount);
      setTip((current) => (current ? { ...current, given } : current));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر إرسال البقشيش");
    } finally {
      setTipping(null);
    }
  }

  return (
    <Stage onBack={() => navigate("/", { replace: true })}>
      <div className="space-y-24">
        <p className="text-center text-muted">كيف كانت رحلتك مع الكبتن؟</p>

        <div className="flex justify-center gap-8" role="radiogroup" aria-label="عدد النجوم">
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
              className="p-4 disabled:opacity-70"
            >
              <Star
                className={cn(
                  "size-36 transition",
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
            className="field min-h-82 resize-none"
            maxLength={500}
            value={comment}
            disabled={done}
            onChange={(event) => setComment(event.target.value)}
            placeholder="ما الذي أعجبك أو يمكن تحسينه؟"
          />
        </div>

        <ErrorNote message={error} />
        {done ? <SuccessNote message="شكراً — وصلنا تقييمك." /> : null}

        {tip?.given ? (
          <p className="text-center text-13 text-muted">
            شكرتَ الكبتن ببقشيش {formatMoney(tip.given.amount, tip.given.currency)}.
          </p>
        ) : tip?.offered && stars >= TIP_MIN_STARS ? (
          <div className="rounded-16 border border-line bg-surface p-16">
            <p className="text-14 font-medium text-ink">تشكر الكبتن ببقشيش؟</p>
            <p className="mt-4 text-12 leading-snug text-muted">
              يُخصم من محفظتك ويصل الكبتن كاملاً — بلا أي خصم.
            </p>
            <div className="mt-14 flex gap-8">
              {tip.presets.map((amount) => (
                <Button
                  key={amount}
                  variant="secondary"
                  className="flex-1"
                  loading={tipping === amount}
                  disabled={tipping !== null}
                  onClick={() => void sendTip(amount)}
                >
                  {formatMoney(amount, tip.currency)}
                </Button>
              ))}
              <Button
                variant="ghost"
                className="flex-1"
                disabled={tipping !== null}
                onClick={() => setTip({ ...tip, offered: false })}
              >
                بدون
              </Button>
            </div>
          </div>
        ) : null}

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
    </Stage>
  );
}
