/** **رقمٌ ينتظر إضافةَ ملفّ الراكب** — من زرِّ «كن راكباً» في تطبيق الكبتن إلى شاشة الدخول هنا (أمرُ المالك ٢٠٢٦-١١-٠٢).
 *
 * **ومن أين يأتي**: مبادلةُ رمز التبديل لحسابٍ بلا دور الراكب تُردّ `handoff_add_role` ومعها رقمُه ودولتُه
 * (`lib/handoff-listener.ts`) — فيُحفظان هنا، ويقرؤهما الدخولُ فيملأ الرقمَ ويقول لماذا، **وكلمةُ المرور تضيف الملفّ**
 * (SPEC §21.6). **ولا رمزَ تحقّقٍ يُرسل**: الحسابُ قائمٌ ورقمُه مُثبَتٌ منذ سجّل.
 *
 * **و`sessionStorage` لا `localStorage`**: نيّةُ جولةٍ واحدة — تموت بإغلاق التطبيق ولا تفاجئ صاحبَها بعد أسبوع.
 * **وكلُّ قراءةٍ وكتابةٍ في `try`**: مخزنٌ ممتلئٌ أو محجوبٌ لا يُسقط شاشةً — يبقى الدخولُ العاديُّ كما كان.
 * **ونسختُه في تطبيق الكبتن حرفاً** إلا اسمَ الملفّ في هذا التعليق.
 */

const KEY = "taxo.add-role";

export interface PendingAddRole {
  /** E.164 كما في الحساب — والدخولُ يحوّله إلى الرقم الوطنيّ بمفتاح الدولة. */
  phone: string;
  country: string;
  /** **لماذا جاء** — `registered`: رقمٌ له حسابٌ بدور هذا التطبيق نفسِه (فحصُ الرقم قبل الرمز، SPEC §٢٣.٢-أ)، فالدخولُ
   * وحده لا إضافة؛ وسكوتُه إضافةُ الملفّ كما كان. */
  reason?: "registered";
}

export function rememberAddRole(value: PendingAddRole): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(value));
  } catch {
    /* مخزنٌ محجوب — يبقى الدخولُ العاديّ */
  }
}

export function pendingAddRole(): PendingAddRole | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<PendingAddRole>;
    return typeof value.phone === "string" && typeof value.country === "string"
      ? { phone: value.phone, country: value.country, ...(value.reason === "registered" ? { reason: "registered" as const } : {}) }
      : null;
  } catch {
    return null;
  }
}

export function clearAddRole(): void {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* لا شيءَ يُمحى */
  }
}
