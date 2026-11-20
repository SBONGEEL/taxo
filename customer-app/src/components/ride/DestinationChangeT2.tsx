/** **«تعديل الوجهة»** (أمرُ المالك ٢٠٢٦-١١-٢٠، SPEC §١٠٩-أ) — زرٌّ في ورقة التتبّع، ثمّ البحثُ، ثمّ السعرُ الجديدُ بتأكيده.
 *
 *  **لا يتغيّر شيءٌ قبل «تأكيد»**: البحثُ يطلب سعراً من الخلفيّة (عرضٌ يعيش دقيقتين)، والبطاقةُ تقول السعرَ القديمَ والجديدَ والوجهةَ
 *  الجديدة، **و«إلغاء» أو تركُها حتى تنقضي = لا تغيير**. **والتأكيدُ يُرسل مرّةً واحدةً** (الزرُّ يُقفل حتى يعود الجواب)، وإن انقطعت
 *  الشبكةُ بعد الإرسال فإعادتُه تردّ الرحلةَ نفسَها ولا تطبّق مرّتين (الخلفيّة).
 *
 *  **والزرُّ لا يُرسم إلا حيث يفي البابُ** — نوعُ الرحلة ومفتاحُ طورها في دولتها (`lib/destination-change.ts`). */

import { useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { confirmDestination, declineDestination, quoteDestination } from "@/api/endpoints";
import type { DestinationChange, Ride } from "@/api/types";
import { DestinationSearch } from "@/components/home/DestinationSearch";
import { useFeature, useMapboxToken } from "@/lib/config";
import {
  canChangeDestination,
  DESTINATION_CHANGE_IN_RIDE_FLAG,
  DESTINATION_CHANGE_SEARCHING_FLAG,
} from "@/lib/destination-change";
import type { Place } from "@/lib/geocode";
import { tr } from "@/lib/i18n";
import { currencyLabel, formatAmount } from "@/lib/utils";
import { Icon } from "@/taxo2";

import "./destination-change.css";

function useCountdown(seconds: number | null): number | null {
  const [left, setLeft] = useState(seconds);
  useEffect(() => {
    setLeft(seconds);
    if (seconds === null) return;
    const started = Date.now();
    const id = window.setInterval(() => {
      setLeft(Math.max(0, seconds - Math.floor((Date.now() - started) / 1000)));
    }, 1000);
    return () => window.clearInterval(id);
  }, [seconds]);
  return left;
}

export function DestinationChangeT2({ ride, onChanged }: { ride: Ride; onChanged: () => void }) {
  const token = useMapboxToken();
  const searchingOn = useFeature(ride.country_code, DESTINATION_CHANGE_SEARCHING_FLAG);
  const inRideOn = useFeature(ride.country_code, DESTINATION_CHANGE_IN_RIDE_FLAG);
  const [searchOpen, setSearchOpen] = useState(false);
  const [quote, setQuote] = useState<DestinationChange | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const left = useCountdown(quote ? quote.expires_in_seconds : null);

  const allowed = canChangeDestination(ride, { searching: searchingOn, inRide: inRideOn });
  // **حالٌ تغيّرت تحت البطاقة** (انتهت الرحلةُ أو بدأت محطة) — تُطوى ولا يُضغط «تأكيد» على عرضٍ لن يُقبل
  useEffect(() => {
    if (!allowed) setQuote(null);
  }, [allowed]);
  if (!allowed) return null;

  async function pick(place: Place) {
    setSearchOpen(false);
    setBusy(true);
    setError(null);
    try {
      setQuote(
        await quoteDestination(ride.id, {
          lat: place.coordinates.lat,
          lng: place.coordinates.lng,
          address: place.address || place.name || null,
        }),
      );
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : tr("تعذّر حساب السعر الجديد — حاول مرة أخرى"));
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    if (!quote || busy) return;
    setBusy(true);
    setError(null);
    try {
      await confirmDestination(ride.id, quote.id);
      setQuote(null);
      onChanged();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : tr("تعذّر التأكيد — تحقّق من الاتصال ثم اضغط «تأكيد» مرة أخرى"));
      if (caught instanceof ApiError && caught.status === 409) setQuote(null);
    } finally {
      setBusy(false);
    }
  }

  async function dismiss() {
    const current = quote;
    setQuote(null);
    setError(null);
    // **الرفضُ يُكتب في تاريخ الرحلة** — وتعذُّرُه لا يغيّر شيئاً: العرضُ ينقضي وحدَه بعد دقيقتين
    if (current) await declineDestination(ride.id, current.id).catch(() => undefined);
  }

  const expired = quote !== null && left !== null && left <= 0;

  return (
    <>
      {quote ? (
        <div className="t2-dest-card" role="dialog" aria-label={tr("تأكيد الوجهة الجديدة")}>
          <div className="t2-dest-title">
            <Icon name="location_on" />
            {tr("الوجهة الجديدة")}
          </div>
          <p className="t2-dest-place">{quote.new_address ?? tr("نقطة على الخريطة")}</p>
          <div className="t2-dest-fares">
            <span className="t2-dest-old">
              {tr("السعر الحالي")}{" "}
              <span dir="ltr" className="t2-num">{formatAmount(quote.old_fare, quote.currency)}</span>{" "}
              {currencyLabel(quote.currency)}
            </span>
            <span className="t2-dest-new">
              {tr("السعر الجديد")}{" "}
              <span dir="ltr" className="t2-num">{formatAmount(quote.fare, quote.currency)}</span>{" "}
              {currencyLabel(quote.currency)}
            </span>
          </div>
          <p className="t2-dest-note">
            {expired
              ? tr("انتهت صلاحية السعر — اختر الوجهة مرة أخرى")
              : quote.phase === "in_ride"
                ? tr("السعر الجديد = ما قطعته حتى الآن + الطريق إلى الوجهة الجديدة. لا يتغيّر شيء حتى تضغط «تأكيد».")
                : tr("لا يتغيّر شيء حتى تضغط «تأكيد».")}
          </p>
          <div className="t2-dest-actions">
            <button
              type="button"
              className="t2-button primary"
              disabled={busy || expired}
              aria-busy={busy}
              onClick={() => void confirm()}
            >
              {busy ? tr("جارٍ التأكيد…") : tr("تأكيد")}
            </button>
            <button type="button" className="t2-srch-cancel" disabled={busy} onClick={() => void dismiss()}>
              {tr("إلغاء")}
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          className="t2-trk-rowbtn"
          disabled={busy}
          aria-busy={busy}
          onClick={() => setSearchOpen(true)}
        >
          <Icon name="location_on" />
          <span className="t2-trk-rowbtn-text">{busy ? tr("نحسب السعر الجديد…") : tr("تعديل الوجهة")}</span>
        </button>
      )}
      {error ? (
        <p className="t2-dest-error" role="alert">
          {error}
        </p>
      ) : null}
      <DestinationSearch
        open={searchOpen}
        onOpenChange={setSearchOpen}
        token={token}
        country={ride.country_code}
        near={ride.dropoff}
        onPick={(place) => void pick(place)}
        title={tr("إلى أين الآن؟")}
      />
    </>
  );
}
