/** **وضعُ الضيف — حالُه على الجهاز** (أمرُ المالك ٢٠٢٦-١٠-١٥، SPEC §٧٦-ن/أ).
 *
 * **صندوقُ عرضٍ لا عملياتٌ حقيقيّة**: من بدأه يجد التطبيقَ كلَّه يعمل، **وكلُّ نداءٍ يُجاب من محرّك العرض في الهاتف نفسِه**
 * (`demo/engine.ts`) — لا رحلةَ تُكتب، ولا كبتنَ حقيقيّاً يُبلغ، ولا مالَ يُمسّ، ولا دفعَ يُطلق. **والخادمُ لا يعرف منه إلا اثنين**: أنه
 * بدأ (`POST /guest/sessions` — بحدٍّ لكلِّ جهازٍ وعنوان) وما كتبه في «أرسل ملاحظة» (`POST /guest/feedback`).
 *
 * **ولا يصير الضيفُ حساباً**: الخروجُ يمحو العرضَ كلَّه ويعيد الترحيب — والتسجيلُ هو التسجيلُ المعتاد بالتحقّق من الرقم.
 */

const KEY = "taxo.demo";

interface DemoState {
  /** رمزُ `guest` من الخادم — لا يفتح إلا «أرسل ملاحظة» */
  token: string;
  started_at: string;
}

function read(): DemoState | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as DemoState) : null;
  } catch {
    return null;
  }
}

/** **أفي وضع الضيف؟** — يُقرأ في كلِّ نداء: الخروجُ يسري في النداء التالي بلا إعادة تحميل. */
export function demoActive(): boolean {
  return read() !== null;
}

export function guestToken(): string | null {
  return read()?.token ?? null;
}

export function enterDemo(token: string): void {
  try {
    localStorage.setItem(KEY, JSON.stringify({ token, started_at: new Date().toISOString() } satisfies DemoState));
  } catch {
    // **بلا تخزين** (نافذةٌ خاصّة) — لا عرضَ يُحفظ، والزرُّ يقول ذلك برسالته
    throw new Error("storage");
  }
}

/** **الخروجُ يمحو العرضَ كلَّه** — لا شيءَ منه يبقى على الجهاز ولا يُنقل إلى حساب. */
export function leaveDemo(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // لا شيء
  }
}
