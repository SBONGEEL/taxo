/** **منطقُ شاشة التقييم في بيتٍ واحد** — النجومُ والملاحظةُ والإرسالُ، والبقشيشُ بخياره وإرساله.
 *
 * يقرؤه وجهان: **القائمُ** (`screens/Rating`) و**TAXO 2.0** «R10» (`screens/t2/RatingT2`) — **فلا يفترقان في تقييمٍ ولا في
 * بقشيش**. والنصُّ منقولٌ من `screens/Rating` **حرفاً بتعليقاته**، والعرضُ القائمُ لم يتغيّر فيه سطر.
 */

import { useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { addTip, getTipOptions, listRideRatings, rateRide } from "@/api/endpoints";
import type { RatingTag, TipOptions } from "@/api/types";

/** أقلُّ عددِ نجومٍ يُسأل عنده عن بقشيش — تضييقُ واجهةٍ لا قاعدةَ خلفية. */
export const TIP_MIN_STARS = 4;

export function useRating(rideId: string) {
  const [stars, setStars] = useState(0);
  const [comment, setComment] = useState("");
  // **وسومُ R10** (§٦٢-ج/٢٥) — تُرسل مع التقييم نفسِه
  const [tags, setTags] = useState<RatingTag[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);

  const [tip, setTip] = useState<TipOptions | null>(null);
  const [tipping, setTipping] = useState<string | null>(null);
  // المبلغُ المختار قبل الإرسال — و`null` يعني لم يُختر بعد
  const [chosenTip, setChosenTip] = useState<string | null>(null);

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
          setTags(mine.tags ?? []);
          setDone(true);
        }
      })
      .catch(() => undefined);
  }, [rideId]);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await rateRide(rideId, stars, comment, tags);
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

  return {
    stars,
    setStars,
    comment,
    setComment,
    tags,
    toggleTag: (tag: RatingTag) =>
      setTags((current) => (current.includes(tag) ? current.filter((item) => item !== tag) : [...current, tag])),
    error,
    done,
    busy,
    tip,
    setTip,
    tipping,
    chosenTip,
    setChosenTip,
    submit,
    sendTip,
  };
}
