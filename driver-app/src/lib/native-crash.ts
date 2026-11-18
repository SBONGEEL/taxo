/** **تعطّلُ أندرويد الأصليّ يصل اللوحة** (SPEC §١٠٣ C/41، خلف `native_crash_reports`) — `NativeCrashPlugin.java`.
 *
 * ما حفظه الغلافُ عند تعطّلٍ سابق (اسمُ الاستثناء وإطاراتُ المكدَّس، **بلا نصِّ رسالة**) يُرسل بباب تقارير الأعطال القائم
 * (`reportNativeCrash`) — **بسقف الجلسة ومفتاح «إرسال تقارير الأعطال» نفسيهما**. ومطفأً يبقى محفوظاً في الهاتف حتى يُشعل أو يُكتب فوقه.
 * **نسخةُ التطبيق الآخر حرفاً.**
 */
import { useEffect } from "react";
import { Capacitor, registerPlugin } from "@capacitor/core";

import { useFeature } from "@/lib/config";
import { reportNativeCrash } from "@/lib/crash-reports";
import type { CountryCode } from "@/api/types";

const plugin = registerPlugin<{ take(): Promise<{ name?: string; stack?: string; at?: number }> }>("NativeCrash");

export function useNativeCrashReports(country: CountryCode | undefined): void {
  const on = useFeature(country, "native_crash_reports");
  useEffect(() => {
    if (!on || !Capacitor.isNativePlatform() || !Capacitor.isPluginAvailable("NativeCrash")) return;
    void plugin
      .take()
      .then((crash) => {
        if (crash.name) reportNativeCrash(crash.name, crash.stack ?? "", crash.at ?? null);
      })
      .catch(() => undefined);
  }, [on]);
}
