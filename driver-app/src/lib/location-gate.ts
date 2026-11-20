/** **لا استقبالَ بلا موقع** (أمرُ المالك ٢٠٢٦-١١-٢٠، SPEC §١٠٩-ج) — زرُّ الاستقبال يسأل الجهازَ عن موقعه أوّلاً.
 *
 *  **العلّة**: كبتنٌ يتّصل بلا موقعٍ لا يدخل الفهرسَ الجغرافيّ، فلا يصله طلبٌ — **ويقرأ الصمتَ «لا طلبات اليوم»** (`socket.ts`
 *  يبتلع رفضَ الإذن بقصدٍ كي لا يسقط المقبس). فيُسأل قبل الاتصال، ويُقال السببُ بنصّ المالك وزرُّه بحسب السبب، **ويُعاد السؤالُ
 *  تلقائيّاً عند العودة من الإعدادات** — فإن وُجد الموقعُ أكمل الاتصالَ الذي طلبه، بلا نقرةٍ ثانية.
 *  **وطلبٌ واحدٌ في كلِّ مرّة** (`busy`): النقرُ المتكرّر لا يراكم أسئلةً للـGPS. */
import { useCallback, useEffect, useRef, useState } from "react";

import { locationCause, type LocationCause } from "@/lib/location-help";
import { readLocationSignals } from "@/lib/permissions-center";

type Probe = { ok: true } | { ok: false; code: number | null };

function probe(): Promise<Probe> {
  if (typeof navigator === "undefined" || !("geolocation" in navigator)) return Promise.resolve({ ok: false, code: null });
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      () => resolve({ ok: true }),
      // 1 = رفضُ الإذن · 2 = لا مصدرَ (GPS مطفأٌ غالباً) · 3 = مهلةٌ بلا قراءة (إشارةٌ ضعيفة)
      (error) => resolve({ ok: false, code: error.code }),
      { enableHighAccuracy: true, timeout: 10_000, maximumAge: 60_000 },
    );
  });
}

export function useLocationGate(onReady: () => void) {
  const [help, setHelp] = useState<LocationCause | null>(null);
  const [locating, setLocating] = useState(false);
  const busy = useRef(false);
  const ready = useRef(onReady);
  ready.current = onReady;

  const attempt = useCallback(async () => {
    if (busy.current) return;
    busy.current = true;
    setLocating(true);
    try {
      const fix = await probe();
      if (fix.ok) {
        setHelp(null);
        ready.current();
        return;
      }
      const signals = await readLocationSignals();
      setHelp(locationCause({ errorCode: fix.code, ...signals }));
    } finally {
      busy.current = false;
      setLocating(false);
    }
  }, []);

  // **إعادةُ المحاولة عند العودة من الإعدادات** — ما دامت الرسالةُ معروضةً وحدَها
  useEffect(() => {
    if (!help) return;
    const onVisible = () => {
      if (document.visibilityState === "visible") void attempt();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [help, attempt]);

  const dismiss = useCallback(() => setHelp(null), []);
  return { help, locating, attempt, dismiss };
}
