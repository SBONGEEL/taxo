/** حالُ الإقلاع على الترحيب — **الترحيبُ نفسُه شاشةُ الإقلاع** (§٦٢/١ و/١٠، ٢٠٢٦-١٠-٠٥).
 *
 * **كانت شاشتان**: «الترحيبية» القديمة في `index.html` (رسمُ TAXO وحلقتُه الدوّارة) حتى يصل `/config` والجلسة، **ثمّ** ترحيبُ
 * TAXO 2.0 — فرأى المالكُ الترحيبَ القديمَ في كلِّ فتحة. **وصار إطارٌ واحد**: أوّلُ إطارٍ من الترحيب الجديد في `index.html`
 * (الخريطةُ وغطاؤها، بمظهر الجهاز من أوّل رسم)، **يحلّ محلَّه الترحيبُ نفسُه** حين يُركَّب (`removeBootFrame`)، **ويبقى حتى
 * يكتمل الإقلاع** — وحالُ الشبكة تُرسم عليه.
 *
 * **ونصوصُ الحال كما كانت** (قرارُ المالك 2026-08-28): ثلاثةُ نصوصٍ لثلاثةِ أشياءَ تُعرف، ولا رابعَ يُدَّعى — `offline` حقيقةٌ
 * يملكها المتصفّح، و`slow` حقيقةٌ عن الزمن لا عن السبب، و`unreachable` «تعذّر الوصول» **ومعه رمزٌ فنّيٌّ قصير** لا يُترجَم.
 */
import { useSyncExternalStore } from "react";

export type SplashStatus = "slow" | "offline" | "unreachable" | null;

interface State {
  status: SplashStatus;
  code?: string;
}

let state: State = { status: null };
let retryHandler: (() => void) | null = null;
const listeners = new Set<() => void>();

function emit(next: State): void {
  state = next;
  for (const listener of listeners) listener();
}

/** يربط «إعادة المحاولة» بمن يملك إعادةَ القراءة (`lib/config.tsx`). */
export function onSplashRetry(handler: () => void): void {
  retryHandler = handler;
}

export function retrySplash(): void {
  retryHandler?.();
}

export function setSplashStatus(status: SplashStatus, code?: string): void {
  // **الرمزُ مع ما لا يُعرف سببُه وحدَه**: مع الانقطاع السببُ معروفٌ ومكتوب، ورمزٌ تحته ضجيجٌ يُخيف بلا أن يفيد
  emit({ status, code: status === "unreachable" ? code : undefined });
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** الحالُ كما يرسمها الترحيب. */
export function useSplashStatus(): State {
  return useSyncExternalStore(subscribe, () => state);
}

/** النصُّ لكلِّ حال — **واقعةٌ لا تفسير**. */
export function splashText(status: Exclude<SplashStatus, null>): string {
  return status === "offline"
    ? "لا يوجد اتصال بالإنترنت"
    : status === "unreachable"
      ? "تعذّر الوصول إلى الخدمة"
      : "لم يصل الجواب بعد — جارٍ المحاولة";
}

/** يُزيل إطارَ الإقلاع من `index.html` — **حين يُركَّب الترحيبُ فوقه بالرسم نفسِه**، فلا ومضةَ بينهما.
 *  تُحذف العقدةُ لا تُخفى: عقدةٌ `fixed` باقيةٌ فوق كلِّ شيءٍ تبتلع اللمس. */
export function removeBootFrame(): void {
  document.getElementById("boot")?.remove();
}
