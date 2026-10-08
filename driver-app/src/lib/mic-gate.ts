/** **بوّابةُ الميكروفون** — زرُّ «اتصال» لا يظهر إلا حيث يعمل الميكروفون (SPEC §٦٦-د/٨).
 *
 * **العلّةُ مقيسة** (٢٠٢٦-١٠-٠٨): لا `RECORD_AUDIO` في بيان أيٍّ من الحزم المثبَّتة — **فالويب‌فيو لا يبلغ الميكروفون فيها**،
 * و`getUserMedia` قائمةٌ في الغلاف وتُرفض عند النداء. **فزرٌّ يُرسم هناك يَعِد بمكالمةٍ لا تقع** — وهو «بابٌ بلا زرّ» مقلوباً:
 * زرٌّ بلا باب.
 *
 * **فثلاثةُ شروطٍ معاً**:
 * 1. `navigator.mediaDevices.getUserMedia` و`RTCPeerConnection` قائمتان؛
 * 2. **وفي الويب** (لا الغلاف) — المتصفّحُ يسأل عن الإذن بنفسه؛
 * 3. **أو في غلاف أندرويد يحمل علامةَ `CALLS_SHELL_MARK` في وكيل المستخدم** — والعلامةُ تُشحن مع الإذن نفسِه.
 *
 * **وiOS لا** — ولو حمل العلامة: البيانُ هناك يحتاج `NSMicrophoneUsageDescription` ولم يُضف، والمكالمةُ لم تُقَس عليه.
 *
 * **ونسخةٌ واحدةٌ في التطبيقين حرفاً** — يقيسها `tools/check-mic-gate.mjs` مع العلامة والبيان.
 */

import { Capacitor } from "@capacitor/core";
import { useEffect, useState } from "react";

/** **علامةُ الغلاف الذي يحمل `RECORD_AUDIO`** — يُلحقها الغلافُ بوكيل المستخدم (`capacitor.config.ts → android.appendUserAgent`).
 *
 *  **ولمَ علامةٌ لا رقمُ بناء** (قِيس ٢٠٢٦-١٠-٠٨ فسقط الرقم): `versionCode` عددُ إيداعاتِ **الفرع الذي بُنيت منه الحزمة**
 *  (`android/app/build.gradle → taxoVersionCode`) — **فرقمٌ واحدٌ لا يفصل «فيها الإذن» عن «ليس فيها»**: كُتب حدُّه ٧٥٩ وفرعُ إعادة
 *  التصميم بلغ ٧٦٣ و`master` ٧٦٢ **وليس في بيانَي أيٍّ منهما الإذن** — فحزمةٌ تُبنى من أيّهما اليوم تجتاز البوّابةَ ويَعِد الزرُّ بما
 *  لا يقع. **ولا رقمَ يُكتب صحيحاً قبل الدمج**: إيداعُ الدمج لم يقع، وكلُّ إيداعٍ يقع على الفرع قبله يزيحه.
 *
 *  **والعلامةُ تُشحن مع الإذن لا بعده**: `capacitor.config.ts` يُنسخ إلى داخل الحزمة عند كلِّ مزامنة (`assets/capacitor.config.json`)،
 *  **وهو والبيانُ في الإيداع نفسِه** — فحزمةٌ فيها العلامةُ فيها الإذن، وحزمةٌ قبلهما ليس فيها هذا ولا ذاك، **أيّاً كان فرعُها
 *  ورقمُها**. والتطابقُ لا يُترك وعداً: `tools/check-mic-gate.mjs` يُسقط الحرّاسَ إن افترق البيانُ عن العلامة في أيِّ تطبيق. */
export const CALLS_SHELL_MARK = "TAXOCalls/1";

let verdict: boolean | null = null;

/** **أتعمل المكالمةُ هنا؟** — يُسأل مرّةً ويُحفظ: الغلافُ لا يتغيّر والتطبيقُ حيّ. */
export function callsSupported(): boolean {
  verdict ??= (() => {
    if (typeof navigator === "undefined" || typeof navigator.mediaDevices?.getUserMedia !== "function") return false;
    if (typeof RTCPeerConnection === "undefined") return false;
    if (!Capacitor.isNativePlatform()) return true;
    if (Capacitor.getPlatform() !== "android") return false;
    // **لا علامةَ = لا وعد**: غلافٌ بُني قبل الإذن لا يحملها
    return navigator.userAgent.includes(CALLS_SHELL_MARK);
  })();
  return verdict;
}

/** الجوابُ لشاشة — **`false` حتى يُحسب**: زرٌّ يظهر ثمّ يختفي أسوأُ من زرٍّ يتأخّر لحظة. */
export function useCallsSupported(): boolean {
  const [supported, setSupported] = useState(false);
  useEffect(() => {
    setSupported(callsSupported());
  }, []);
  return supported;
}
