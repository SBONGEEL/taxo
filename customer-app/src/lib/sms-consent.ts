/** **ملءُ رمز التحقّق من الرسالة القصيرة** (SPEC §١٠٣ B/23، خلف `sms_autofill` لدولة الرقم) — `SmsConsentPlugin.java`.
 *
 * النظامُ يسأل صاحبَ الهاتف قبل أن يُقرأ شيء، والرمزُ يُكتب في خاناته كما لو كتبه؛ **والكتابةُ باليد باقية**. ويستمع ما دامت
 * الخطوةُ تنتظر رمزاً برسالةٍ نصّيّة، ويسكت حين تُغادَر. **نسخةُ التطبيق الآخر حرفاً.**
 */
import { useEffect, useRef } from "react";
import { Capacitor, registerPlugin } from "@capacitor/core";

import { shellAllows } from "@/lib/shell-features";

const native = registerPlugin<{
  listen(options: { length: number }): Promise<{ code: string | null }>;
  stop(): Promise<void>;
}>("SmsConsent");

/** خالصة: أتشتعل الميزةُ لدولة هذا الرقم؟ — البادئةُ من `/config` لا من التطبيق. */
export function smsAutofillFor(
  e164: string,
  countries: readonly { dial_code: string; features: Record<string, boolean> }[] | undefined,
): boolean {
  const digits = e164.replace(/^\+/, "");
  const country = (countries ?? []).find((entry) => digits.startsWith(entry.dial_code.replace(/^\+/, "")));
  return country?.features.sms_autofill === true && shellAllows("sms_autofill");
}

export function useSmsConsent(on: boolean, length: number, onCode: (code: string) => void): void {
  const latest = useRef(onCode);
  latest.current = onCode;
  useEffect(() => {
    if (!on || !Capacitor.isNativePlatform() || !Capacitor.isPluginAvailable("SmsConsent")) return;
    let alive = true;
    void native
      .listen({ length })
      .then((answer) => {
        if (alive && answer.code) latest.current(answer.code);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
      void native.stop().catch(() => undefined);
    };
  }, [on, length]);
}
