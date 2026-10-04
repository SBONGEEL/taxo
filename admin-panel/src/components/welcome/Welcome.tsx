/** ترحيبُ اللوحة وتطبيقِ المشرف — **عند كلِّ فتحة** (TAXO 2.0، قرارُ المالك ٢٠٢٦-١٠-٠٤).
 *
 * **اللوحةُ بلا تصميمٍ بعد، ولا تأخذ إلا الترحيبَ وسلوكَ الدخول** (SPEC §61-٥). فالترحيبُ هنا
 * **تكوُّنُ الـX وحدَه** من «Welcome» بقيمه حرفاً — لا شاشةٌ مخترعة ولا نصٌّ جديد — ثمّ يمضي:
 * **الداخلُ** إلى حيث كان، **وغيرُ الداخل** إلى شاشة الدخول القائمة كما هي.
 *
 * **ولا يطلب شيئاً**: لا نداءَ ولا إذن. والسِمةُ سِمةُ اللوحة نفسِها (ليليٌّ افتراضاً، `lib/theme`).
 * و«تقليلُ الحركة» يعرض الإطارَ الأخيرَ ويمضي فوراً.
 */

import { useEffect, useState } from "react";

import "./welcome.css";

/** «لحظة تكوّن X (0.8 ثانية)» — ووقفةٌ قصيرةٌ على الشعار كما عند الداخل في التطبيقين. */
const BRIEF_MS = 800;
const HOLD_MS = 250;
const LEAVE_MS = 300;

/** المقياسان: الخريطةُ **تُغطّي** الشاشة، والشعارُ **يُحتوى** بنسبة إطار اللوحة 390×844. */
function useScales(): { cover: number; contain: number } {
  const [scales, setScales] = useState({ cover: 1, contain: 1 });
  useEffect(() => {
    const measure = () => {
      const w = window.innerWidth / 390;
      const h = window.innerHeight / 844;
      setScales({ cover: Math.max(w, h), contain: Math.min(w, h) });
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);
  return scales;
}

export function Welcome({ dark, onDone }: { dark: boolean; onDone: () => void }) {
  const { cover, contain } = useScales();
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const id = window.setTimeout(() => setLeaving(true), reduced ? 0 : BRIEF_MS + HOLD_MS);
    return () => window.clearTimeout(id);
  }, []);

  useEffect(() => {
    if (!leaving) return;
    const id = window.setTimeout(onDone, LEAVE_MS);
    return () => window.clearTimeout(id);
  }, [leaving, onDone]);

  return (
    <div
      className={["aw", dark ? "" : "day", leaving ? "is-leaving" : ""].filter(Boolean).join(" ")}
      role="presentation"
      aria-hidden="true"
    >
      <div className="aw-stage" style={{ ["--aw-scale" as string]: String(cover) }}>
        <div className="aw-cam">
          <img src={dark ? "/welcome/amman-night.svg" : "/welcome/amman-day.svg"} alt="" />
        </div>
        <div className="aw-veil" />
      </div>
      <div className="aw-stage" style={{ ["--aw-scale" as string]: String(contain) }}>
        <div className="aw-xmark">
          <span><i /></span>
          <span><i /></span>
        </div>
        <div className="aw-word" dir="ltr">
          TA
          <span className="aw-xb">
            <span />
            <span />
          </span>
          O
        </div>
      </div>
      {/* **ذكرُ الخريطة ما دامت معروضة** — شرطُ الرخصة لا زينة (§61-أ) */}
      <span className="aw-credit" dir="ltr">
        © OpenStreetMap · Copernicus DEM · Open-Meteo
      </span>
    </div>
  );
}
