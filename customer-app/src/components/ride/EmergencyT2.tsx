/** **زرُّ الطوارئ** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٧) — في الرحلة الجارية.
 *
 * **ضغطةٌ تفتح ولا تُرسل**: صفٌّ أحمرُ يفتح لوحةً فيها أمران — «نبّه فريق TAXO الآن» (تنبيهٌ عاجلٌ في اللوحة بموقعك والطرفين) و«اتّصل
 * بالطوارئ» (رقمُ الدولة من اللوحة، `tel:` مباشرة). **فلا تنبيهَ كاذبٌ من لمسةٍ عابرة**، ولا انتظارَ شبكةٍ قبل الاتّصال بالشرطة.
 * **والموقعُ من الجهاز بمهلة ثلاث ثوانٍ** — وبدونه يأخذ الخادمُ موقعَ السيارة في الرحلة.
 */

import { useEffect, useState } from "react";

import { pressEmergency, supportContacts } from "@/api/endpoints";
import { ApiError } from "@/api/client";
import type { CountryCode } from "@/api/types";
import { tr } from "@/lib/i18n";
import { useBubbleAction } from "@/lib/bubble-actions";

import "./emergency.css";
import { Icon } from "@/taxo2";

function here(): Promise<{ lat: number; lng: number } | null> {
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      resolve(null);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (spot) => resolve({ lat: spot.coords.latitude, lng: spot.coords.longitude }),
      () => resolve(null),
      { enableHighAccuracy: true, timeout: 3_000, maximumAge: 30_000 },
    );
  });
}

export function EmergencyRowT2({ rideId, country }: { rideId: string; country: CountryCode }) {
  const [open, setOpen] = useState(false);
  // **الطوارئُ من الفقاعة إن تعذّر نداؤها** (SPEC §١١٠) — الورقةُ نفسُها
  useBubbleAction("emergency", () => setOpen(true));
  const [number, setNumber] = useState<string | null>(null);
  const [state, setState] = useState<"idle" | "sending" | "sent">("idle");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || number !== null) return;
    supportContacts(country)
      .then((row) => setNumber(row.emergency_number))
      .catch(() => undefined);
  }, [open, number, country]);

  async function alertTeam() {
    setState("sending");
    setError(null);
    try {
      const spot = await here();
      const sent = await pressEmergency({ app: "rider", ride_id: rideId, ...(spot ?? {}) });
      if (sent.emergency_number) setNumber(sent.emergency_number);
      setState("sent");
    } catch (caught) {
      setState("idle");
      setError(caught instanceof ApiError ? caught.message : tr("تعذّر إرسال التنبيه — اتّصل بالطوارئ مباشرة"));
    }
  }

  return (
    <div className="t2-sos">
      <button type="button" className="t2-trk-rowbtn t2-sos-row" aria-expanded={open} onClick={() => setOpen(!open)}>
        <Icon name="shield" />
        <span className="t2-trk-rowbtn-text">{tr("طوارئ")}</span>
        <Icon name={open ? "expand_more" : "chevron_left"} className="t2-trk-rowbtn-go" />
      </button>
      {open ? (
        <div className="t2-sos-panel" role="group" aria-label={tr("طوارئ")}>
          {state === "sent" ? (
            <p className="t2-sos-sent">{tr("وصل التنبيه — فريق TAXO يتابع رحلتك الآن.")}</p>
          ) : (
            <button type="button" className="t2-sos-alert" disabled={state === "sending"} onClick={() => void alertTeam()}>
              {state === "sending" ? tr("يُرسل…") : tr("نبّه فريق TAXO الآن")}
            </button>
          )}
          {number ? (
            <a className="t2-sos-call" href={`tel:${number}`}>
              <Icon name="call" />
              {tr("اتّصل بالطوارئ")} <span dir="ltr">{number}</span>
            </a>
          ) : null}
          {error ? <p className="t2-sos-error">{error}</p> : null}
        </div>
      ) : null}
    </div>
  );
}
