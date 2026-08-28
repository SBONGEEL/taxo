/** الشاشة الترحيبية: إزالتُها وحالاتُ الشبكة عليها — `DESIGN.md` §7.5/§7.8.
 *
 * العقدةُ تعيش في `index.html` لا في React (لتُرسم قبل الحزمة)، فكلُّ ما هنا
 * لمسٌ مباشرٌ للـDOM — وهو الاستثناءُ الوحيد في هذا التطبيق، ومحصورٌ في هذا
 * الملف.
 */

const FADE_MS = 200;

/** **أقلُّ ما تبقاه الشاشة**: زمنُ اكتمال رسم `TAXO` (510ms تأخيرُ الـ`O` +
 * 520ms رسمُها = 1030). فيكتمل الخطُّ براحةٍ ولا تُقطع الكلمةُ في منتصفها.
 *
 * **ولا يزيد الانتظارُ على الحركة نفسِها** (قرارُ المالك): هذا سقفٌ لا هدف —
 * من كان تطبيقُه جاهزاً عند 200ms ينتظر حتى 1030 ولا شيءَ بعدها، ومن تأخّر
 * تُغطّيه الـ`O` بدورانها. أي أن الشاشةَ **تملأ انتظاراً ولا تصنعه**.
 */
const MIN_HOLD_MS = 1030;

export type SplashStatus = "slow" | "offline" | "unreachable" | null;

let done = false;
let retryHandler: (() => void) | null = null;

function node(): HTMLElement | null {
  return document.getElementById("splash");
}

function part(name: string): HTMLElement | null {
  return node()?.querySelector<HTMLElement>(`.${name}`) ?? null;
}

/** يربط زرَّ «إعادة المحاولة» بمن يملك إعادةَ القراءة. */
export function onSplashRetry(handler: () => void): void {
  retryHandler = handler;
  const button = part("tx-retry");
  if (!button || button.dataset.bound === "1") return;
  button.dataset.bound = "1";
  button.addEventListener("click", () => retryHandler?.());
}

/** **ثلاثةُ نصوصٍ لثلاثةِ أشياءَ تُعرف — ولا رابعَ يُدَّعى** (قرارُ المالك
 * 2026-08-28).
 *
 * `offline` **حقيقةٌ يملكها المتصفّح** (`navigator.onLine === false`): «افتح
 * الشبكة» فعلٌ صحيح. و`slow` **حقيقةٌ عن الزمن لا عن السبب**: مضت المهلةُ
 * ولم يصل جواب، فيُقال «لم يصل الجواب بعد» — لا «الشبكة ضعيفة».
 *
 * **و`unreachable` هو ما أُصلح**: كان أيُّ فشلٍ في `GET /config` يُرسم
 * «الشبكة ضعيفة» — **فتُسمّى علّةٌ لا تُعرف**. والفشلُ قد يكون خادماً يردّ
 * ٥٠٠، أو حجباً من الوسيط، أو عقداً منتهياً، أو DNS. **وقد كذبت على المالك
 * ثلاثَ مرّاتٍ في أسبوعٍ وشبكتُه سليمةٌ في الثلاث** — وأسوأُ من الصمت أن
 * يُوجَّه القارئُ إلى الاتجاه الخطأ فيفتش في شبكته.
 *
 * **فيقول ما يعرفه**: «تعذّر الوصول» — واقعةٌ لا تفسير. **ومعه رمزٌ فنّيٌّ
 * قصير** يُقرأ عند الشكوى فيعرف من يسمعه أين ينظر، **ولا يُترجَم ولا
 * يُفسَّر** للقارئ لأنه ليس له.
 *
 * **وقاعدةُ هذا الملفّ**: إعلانٌ لا يعرف الصفُّ جوابَه لا يُكتب.
 */
export function setSplashStatus(status: SplashStatus, code?: string): void {
  const note = part("tx-note");
  const retry = part("tx-retry");
  const loading = part("tx-loading");
  const codeLine = part("tx-code");
  if (!note || !retry) return;

  if (status === null) {
    note.hidden = true;
    retry.hidden = true;
    if (codeLine) codeLine.hidden = true;
    return;
  }

  note.textContent =
    status === "offline"
      ? "لا يوجد اتصال بالإنترنت"
      : status === "unreachable"
        ? "تعذّر الوصول إلى الخدمة"
        : "لم يصل الجواب بعد — جارٍ المحاولة";
  note.hidden = false;

  // **الرمزُ يظهر مع ما لا يُعرف سببُه وحدَه**: مع الانقطاع السببُ معروفٌ
  // ومكتوب، ورمزٌ تحته ضجيجٌ يُخيف بلا أن يفيد
  if (codeLine) {
    codeLine.textContent = status === "unreachable" && code ? code : "";
    codeLine.hidden = !codeLine.textContent;
  }
  // زرُّ المحاولة مع الانقطاع وحده: مع البطء نحن نحاول أصلاً، وزرٌّ يقول
  // «أعد المحاولة» بينما المحاولةُ جارية يدعو إلى ضغطٍ لا يفعل شيئاً
  // زرُّ المحاولة مع ما لا يُعالج نفسَه: الانقطاعُ وتعذّرُ الوصول
  retry.hidden = status === "slow";
  // سطرُ «جارٍ التحميل…» للحركة المخفَّضة وحدها، ويختفي حين يحلّ نصٌّ أدقّ منه
  if (loading) loading.style.display = "none";
}

/** تُزال حين يجهز التطبيق — وبعد أن يكتمل رسمُ الكلمة (§7.5). */
export function hideSplash(): void {
  if (done) return;
  done = true;

  const wait = Math.max(0, MIN_HOLD_MS - performance.now());
  window.setTimeout(() => {
    const element = node();
    if (!element) return;
    element.classList.add("is-gone");
    // تُحذف بعد الذوبان لا تُخفى: عقدةٌ `fixed` باقيةٌ فوق كل شيء تبتلع اللمس
    window.setTimeout(() => element.remove(), FADE_MS);
  }, wait);
}
