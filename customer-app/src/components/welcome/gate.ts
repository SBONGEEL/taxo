/** **العودةُ إلى الترحيب** — سهمُ الرجوع في «الدخول» و«التسجيل» يعود إلى «أهلاً وسهلاً» (R02 ← R01 في اللوحة).
 *
 * الترحيبُ فوق المسارات لا مساراً بينها (`App.tsx`)، **فلا يُرجَع إليه بالتاريخ** — يُطلب من هنا، فيعود بلا مقدّمةٍ إلى زرّيه.
 */
type Listener = () => void;

let requests = 0;
const listeners = new Set<Listener>();

export function reopenWelcome(): void {
  requests += 1;
  for (const listener of listeners) listener();
}

export function subscribeWelcome(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function welcomeRequests(): number {
  return requests;
}

/** **أمرئيٌّ الترحيبُ الآن؟** — يقرؤه زرُّ الرجوع الأصليّ (`lib/hardware-back.ts`): من الدخول والتسجيل يعود إليه، ومنه يُغلَق التطبيق. */
let open = true;

export function setWelcomeOpen(value: boolean): void {
  open = value;
}

export function isWelcomeOpen(): boolean {
  return open;
}

/** **شاشتا الدخول — جذرُ من لم يدخل** (بعد الترحيب): الرجوعُ منهما إلى الترحيب لا خروج. */
export const AUTH_ROOTS: readonly string[] = ["/login", "/register"];
