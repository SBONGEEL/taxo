/** **صفحةُ التتبّع العامّة** «/t/:token» (§٦٣-ج/١) — يفتحها من أرسل إليه الطالبُ الرابط، **بلا دخولٍ ولا حساب**.
 *
 * **لا لوحةَ لها** — فتُركَّب من عُدّة TAXO 2.0 بلغة بطاقة الكبتن في R08: حالُ الرحلة سطراً، والخريطةُ بعلامة الكبتن،
 * والاسمُ والسيارةُ واللوحة. **وما يُعرض هو ما ينشره الباب وحدَه** (`PublicTrackOut`): لا رقمَ الطالب ولا محفظتَه ولا أجرةَ
 * ولا عنوان — **والصفحةُ لا تملك غيرَه لتسرّبه**.
 *
 * **تسأل كلَّ خمس ثوانٍ** (كاستطلاع شاشة الدفع) **وتتوقّف بنفسها**: عند «انتهت الرحلة» — الرابطُ يتوقّف بانتهائها ولا
 * يتغيّر جوابُه بعدها — **وعند ٤٠٤**: رمزٌ لا يُعرف لن يُعرف بعد خمس ثوانٍ. **وعطبُ الشبكة لا يوقفها**: يُقال ويُعاد السؤال.
 *
 * **والخريطةُ خريطةُ التطبيق نفسُها** (`MapView`) — توكنُها من `GET /config` العامّ (`anonymous`)، **فلا بابَ جديداً لها**.
 * **وبلا توكنٍ منشورٍ** يُعطى الموقعُ رابطاً إلى خرائط قوقل بدلها.
 *
 * **وتُرسم خارج الإقلاع كلِّه** (`App.tsx`): لا ترحيبَ ولا جلسةَ ولا حارسَ يحوّل الزائرَ إلى «الدخول».
 */

import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getPublicTrack } from "@/api/endpoints";
import type { PublicTrack } from "@/api/types";
import { MapView, type MapHandle } from "@/components/map/MapView";
import { useMapboxToken } from "@/lib/config";
import { PUBLIC_STATE_LINE, mapsUrl } from "@/lib/for-other";
import { removeBootFrame } from "@/lib/splash";
import { Icon } from "@/taxo2";

import "./t2.css";
import "./for-other.css";

/** دورةُ السؤال — **دورةُ بثِّ الكبتن نفسُها** تقريباً، فلا يُسأل أسرعَ ممّا يتغيّر الجواب. */
const POLL_MS = 5_000;

/** رمزٌ لكلِّ حال — من مقتطَع الخطّ القائم (`index.html`). */
const STATE_ICON: Record<PublicTrack["state"], string> = {
  searching: "search",
  coming: "local_taxi",
  arrived: "location_on",
  riding: "route",
  ended: "flag",
};

function StateCardT2({
  icon,
  tone,
  text,
}: {
  icon: string;
  tone?: "ended" | "danger";
  text: string;
}) {
  return (
    <div className="t2-pt-state" role="status">
      <span className={tone ? `t2-pt-state-icon ${tone}` : "t2-pt-state-icon"} aria-hidden="true">
        <Icon name={icon} />
      </span>
      <p className="t2-pt-state-text">{text}</p>
    </div>
  );
}

export function PublicTrackScreen() {
  const { token = "" } = useParams();
  const mapToken = useMapboxToken();
  const map = useRef<MapHandle>(null);
  const [track, setTrack] = useState<PublicTrack | null>(null);
  const [gone, setGone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // **إطارُ الإقلاع يُزال هنا** — يزيله الترحيبُ في كلِّ صفحةٍ غيرها، ولا ترحيبَ لزائرٍ بلا حساب (`lib/splash.ts`)
  useEffect(() => removeBootFrame(), []);

  useEffect(() => {
    let live = true;
    let timer: number | undefined;
    const controller = new AbortController();
    const poll = async () => {
      try {
        const next = await getPublicTrack(token, controller.signal);
        if (!live) return;
        setTrack(next);
        setError(null);
        // **انتهت ⇒ لا سؤالَ بعدها**: الجوابُ لا يتغيّر، والصفحةُ قد تبقى مفتوحةً في جيبٍ ساعات
        if (next.state === "ended") return;
      } catch (caught) {
        if (!live) return;
        // **٤٠٤ ⇒ رابطٌ لا يُعرف**، ولن يُعرف بعد خمس ثوانٍ — فلا يُعاد السؤال
        if (caught instanceof ApiError && caught.status === 404) {
          setGone(true);
          return;
        }
        setError(caught instanceof ApiError ? caught.message : "تعذّر الوصول — نعيد المحاولة");
      }
      timer = window.setTimeout(() => void poll(), POLL_MS);
    };
    void poll();
    return () => {
      live = false;
      controller.abort();
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [token]);

  // **الخريطةُ ساكنةٌ وتتبع الكبتن** — لا يحرّكها الزائر، فتنتقل هي إلى موضعه مع كلِّ جواب
  const position = track?.position ?? null;
  useEffect(() => {
    if (position) map.current?.flyTo(position);
    // النقطةُ بإحداثيّتيها لا بهويّة الكائن — كلُّ جوابٍ يحمل كائناً جديداً للموضع نفسِه
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [position?.lat, position?.lng]);

  return (
    <div className="t2 t2-page t2-pt">
      <div className="t2-head">
        <h1 className="t2-title">تتبّع الرحلة · TAXO</h1>
      </div>

      {gone ? (
        <StateCardT2 icon="error" tone="danger" text="الرابط غير صحيح أو انتهى" />
      ) : track === null ? (
        <StateCardT2 icon="hourglass_top" text={error ?? "نقرأ حال الرحلة…"} tone={error ? "danger" : undefined} />
      ) : (
        <>
          <StateCardT2
            icon={STATE_ICON[track.state]}
            tone={track.state === "ended" ? "ended" : undefined}
            text={PUBLIC_STATE_LINE[track.state]}
          />
          {/* **شريطٌ يتحرّك ولا يتقدّم** ما دام البحثُ جارياً — شريطُ R07 نفسُه */}
          {track.state === "searching" ? (
            <div className="t2-trk-bar" role="progressbar" aria-label="نبحث عن كبتن" aria-busy="true">
              <span />
            </div>
          ) : null}

          {position ? (
            mapToken ? (
              <div className="t2-pt-map">
                <MapView
                  ref={map}
                  token={mapToken}
                  center={position}
                  zoom={15}
                  driverLocation={{ lat: position.lat, lng: position.lng, heading: null }}
                  interactive={false}
                />
              </div>
            ) : (
              <a className="t2-button secondary t2-pt-maps" href={mapsUrl(position)} target="_blank" rel="noopener noreferrer">
                <Icon name="map" />
                افتح الموقع في الخرائط
              </a>
            )
          ) : null}

          {track.captain_name || track.vehicle ? (
            <div className="t2-pt-card">
              <span className="t2-pt-avatar" aria-hidden="true">
                <Icon name="person" />
              </span>
              <div className="t2-pt-card-main">
                {track.captain_name ? <div className="t2-trk-dname lg">{track.captain_name}</div> : null}
                {track.vehicle ? (
                  <div className="t2-trk-veh">
                    {track.vehicle.make} {track.vehicle.model} · {track.vehicle.color}
                  </div>
                ) : null}
              </div>
              {track.vehicle ? (
                <div dir="ltr" className="t2-trk-plate">
                  <span className="t2-trk-plate-no">{track.vehicle.plate_number}</span>
                </div>
              ) : null}
            </div>
          ) : null}

          {/* **عطبُ شبكةٍ بعد جوابٍ أوّل يُقال ولا يمحو ما عُرف** — والسؤالُ يُعاد */}
          {error ? (
            <p className="t2-note warn" role="alert">
              <Icon name="error" fill />
              {error}
            </p>
          ) : null}
        </>
      )}
    </div>
  );
}
