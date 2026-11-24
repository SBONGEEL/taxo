/** **إشاراتُ الجهاز إلى اللوحة** (SPEC §١٠٣ B/17 و25) — موقعٌ مزيَّفٌ رُصد في آخر يوم، وجهازٌ معدَّل.
 *
 * **بلاغٌ لا حجب** (أمرُ المالك ١٨/١١): لا شيءَ هنا يوقف الاستقبال — المشرفُ يقرؤه في درج الكبتن والقرارُ له. **وكلُّ إشارةٍ خلف
 * مفتاحها**: مطفأً لا تُقرأ ولا تُرسل، **فلا يصل المشرفَ «لا» عن شيءٍ لم يُقس**. ويُرسل حين تتغيّر البصمةُ وحدَها.
 */
import { useEffect } from "react";
import { Capacitor } from "@capacitor/core";

import type { CountryCode } from "@/api/types";
import { reportDeviceSignals, type DeviceSignalsReport } from "@/api/endpoints";
import { useFeature } from "@/lib/config";
import { readDeviceSignals } from "@/lib/online-service";

const STORE = "taxo.device.signals";
const EVERY_MS = 10 * 60_000;

/** خالصة: ما يُرسل — المقيسُ خلف مفتاحه وحدَه، و`null` إن لم يُقس شيء. */
export function signalsPayload(
  read: { mock_location: boolean; rooted: boolean; emulator?: boolean },
  mockOn: boolean,
  rootOn: boolean,
  points = false,
): DeviceSignalsReport | null {
  const out: DeviceSignalsReport = {};
  // **ونقاطُ الالتزام المشتعلة تقرأ الثلاثة** (§١١٤-ب): «هاتفٌ حقيقيٌّ بلا موقعٍ مزيَّف» شرطُ يومها، فتُرسل ولو أُطفئ البلاغان
  if (mockOn || points) out.mock_location = read.mock_location;
  if (rootOn || points) out.rooted = read.rooted;
  if (points && typeof read.emulator === "boolean") out.emulator = read.emulator;
  return Object.keys(out).length ? out : null;
}

export function useDeviceSignals(country: CountryCode | undefined, points = false): void {
  const mockOn = useFeature(country, "mock_location_report");
  const rootOn = useFeature(country, "root_report");
  useEffect(() => {
    if (!(mockOn || rootOn || points) || !Capacitor.isNativePlatform() || !Capacitor.isPluginAvailable("OnlineService")) return;
    let stopped = false;
    const check = async () => {
      try {
        const payload = signalsPayload(await readDeviceSignals(), mockOn, rootOn, points);
        if (!payload || stopped) return;
        const key = JSON.stringify(payload);
        let last: string | null = null;
        try {
          last = localStorage.getItem(STORE);
        } catch {
          last = null;
        }
        if (last === key) return;
        await reportDeviceSignals(payload);
        try {
          localStorage.setItem(STORE, key);
        } catch {
          // لا مخزن — يُعاد البلاغُ في الدورة القادمة، ولا ضرر
        }
      } catch {
        // غلافٌ أقدمُ بلا `signals` أو شبكةٌ غائبة — لا شيءَ يُرسل
      }
    };
    void check();
    const timer = window.setInterval(() => void check(), EVERY_MS);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [mockOn, rootOn, points]);
}
