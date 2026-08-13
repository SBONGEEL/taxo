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

export type SplashStatus = "slow" | "offline" | null;

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

/** **يميّز الانقطاعَ من البطء فعلاً** (§7.8): نصّان مختلفان لحالين مختلفين.
 *
 * «لا يوجد اتصال» يقول لصاحبه: افتح الشبكة. و«الشبكة ضعيفة — جارٍ المحاولة»
 * يقول: لا تفعل شيئاً، نحن نحاول. ونصٌّ واحدٌ للحالين يجعل أحدَ الجوابين خطأً
 * دائماً — والمستخدمُ يفتح إعداداتِ شبكةٍ تعمل، أو ينتظر شبكةً مقطوعة.
 */
export function setSplashStatus(status: SplashStatus): void {
  const note = part("tx-note");
  const retry = part("tx-retry");
  const loading = part("tx-loading");
  if (!note || !retry) return;

  if (status === null) {
    note.hidden = true;
    retry.hidden = true;
    return;
  }

  note.textContent =
    status === "offline"
      ? "لا يوجد اتصال بالإنترنت"
      : "الشبكة ضعيفة — جارٍ المحاولة";
  note.hidden = false;
  // زرُّ المحاولة مع الانقطاع وحده: مع البطء نحن نحاول أصلاً، وزرٌّ يقول
  // «أعد المحاولة» بينما المحاولةُ جارية يدعو إلى ضغطٍ لا يفعل شيئاً
  retry.hidden = status !== "offline";
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
