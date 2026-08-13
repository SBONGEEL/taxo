/** قنواتُ الدفع — **قائمةٌ واحدةٌ لشاشة الدفع ولورقة التأكيد معاً** (الحزمة ب).
 *
 * كانت `METHODS` تسكن `screens/Payment.tsx`، وقرارُ التصميم 3 يضع مُنتقيَ
 * الطريقة **قبل** الطلب أيضاً — فصار للقائمة قارئان. ونسخُها في الورقة يعني
 * قناةً تُضاف في مكانٍ وتُنسى في الآخر، فانتقلت إلى هنا بحالها: **الترتيب
 * والمفاتيحُ والنصوصُ الفرعية كما كانت**، والشاشةُ تستوردها.
 *
 * وثلاث قواعدَ لم تتغيّر بالنقل:
 *
 * - **الترتيب مقصود**: المحفظة أولاً وكليك ثانياً (SPEC القسم 6.2).
 * - **القنوات تتبع مفاتيح الدولة**: الكاش وحده بلا مفتاح — وهو ما يجعل
 *   إعدادَ ليبيا الافتراضي «كاش فقط» يعمل بلا حالةٍ خاصة.
 * - **و`promo` ليست قناةً يختارها أحد**: تكتبها المنصّةُ عند الإنهاء وتتحمّلها
 *   الشركة (12-ز). فهي في `PaymentMethod` ولا مكان لها هنا.
 *
 * ---
 *
 * **والتفضيلُ محلّيٌّ بالكامل** (قرار التصميم 3، و`DESIGN-DECISIONS.md` 51):
 * لا يُرسل إلى الخلفية، ولا عمودَ له على `rides`، ولا يُقيّد صاحبَه عند الدفع.
 * والسببُ في الخلفية لا في الذوق: صفوفُ `payments` تُنشأ **بعد** `completed`،
 * و`commission_settings.applies_to` تُقرأ وقت الدفع لأنها تتعلق بالقناة — فقناةٌ
 * تُجمَّد وقت الطلب تُجمِّد معها قاعدةَ عمولةٍ قبل أن تُعرف الأجرة.
 *
 * **وهو لكل جهاز لا لكل حساب** (قاعدةُ السِمة الوردية نفسُها): من يدفع كاشاً من
 * هاتفه ومحفظةً من جهازٍ آخر لا يُنقل تفضيلُه بينهما، ولا يستحق هذا صفّاً في
 * قاعدة البيانات.
 */

import { useCallback, useState } from "react";
import type { LucideIcon } from "lucide-react";
import { Banknote, CreditCard, Smartphone, Wallet } from "lucide-react";

import type { CountryConfig, PaymentMethod } from "@/api/types";

/** القنواتُ التي **تكتبها المنصّةُ عن الراكب** ولا يختارها أحد: خصمُ الكوبون
 *  (12-ز) وخصمُ المشاركة (12-ي). كلتاهما تتحمّلها الشركةُ وتُنشأ عند الإنهاء.
 *
 *  **وقائمةٌ لا قيمةٌ واحدة** لأن ما يجمعها مفهومٌ لا اسم: كُتب هذا أصلاً
 *  `Exclude<PaymentMethod, "promo">` وكان صحيحاً بقناةٍ واحدة، ثم أضافت 12-ي
 *  `share` فصارت **تظهر خياراً في مُنتقي الدفع** — أي زرٌّ يعد الراكبَ بأن
 *  يدفع بخصمٍ تتحمّله الشركة. وأمسكه المصرّفُ عند `CTA` لا في متصفح، لأن
 *  `Record<PayableMethod, …>` يفرض عضواً لكلِّ قيمة.
 */
type PlatformWrittenMethod = "promo" | "share";

/** ما يجوز لصاحب الحساب اختياره. */
export type PayableMethod = Exclude<PaymentMethod, PlatformWrittenMethod>;

export interface PaymentChannel {
  method: PayableMethod;
  icon: LucideIcon;
  /** المفتاح الذي يحكم القناة — والكاش بلا مفتاح لأنه يعمل بلا إعداد. */
  feature?: string;
  hint: string;
}

/** الترتيب مقصود: المحفظة أولاً وكليك ثانياً (SPEC القسم 6.2). */
export const PAYMENT_CHANNELS: PaymentChannel[] = [
  { method: "wallet", icon: Wallet, feature: "wallet_enabled", hint: "خصمٌ فوري من رصيدك" },
  { method: "cliq", icon: Smartphone, feature: "cliq_enabled", hint: "حوّل على alias الكبتن" },
  { method: "card", icon: CreditCard, feature: "card_enabled", hint: "بطاقة أو محفظة الهاتف" },
  { method: "cash", icon: Banknote, hint: "سلّم المبلغ للكبتن" },
];

/** قنواتُ هذه الدولة وحدها — والقناةُ الغائبةُ لا تُرسم معطّلةً بل تختفي. */
export function channelsFor(country: CountryConfig | null | undefined) {
  return PAYMENT_CHANNELS.filter(
    (channel) => !channel.feature || country?.features[channel.feature] === true,
  );
}

const KEY = "taxo.payment_preference";

function stored(): PayableMethod | null {
  const value = localStorage.getItem(KEY);
  return PAYMENT_CHANNELS.some((channel) => channel.method === value)
    ? (value as PayableMethod)
    : null;
}

/** التفضيلُ المحفوظ **مصفّىً بما تسمح به الدولة**.
 *
 * قناةٌ اختيرت في سوقٍ ثم أُطفئ مفتاحُها تبقى في `localStorage` بلا أن يراها
 * صاحبُها في أي شاشة — فتُعرض على الزرّ «بطاقة» ثم لا تجدها في شاشة الدفع.
 * وهذه هي قاعدةُ الخدمة النسائية بحرفها: **المفتاحُ الذي يخفي الشاشة يجب أن
 * يحكم ما تحمله أيضاً**، وإلا صار الوعدُ غيرَ ما يقع.
 *
 * ولذلك يعيد `resolved` أوّلَ قناةٍ متاحة حين لا يصلح المحفوظ: زرٌّ بلا قناةٍ
 * أسوأ من زرٍّ بقناةٍ لم تُختَر بعد.
 */
export function usePaymentPreference(country: CountryConfig | null | undefined) {
  const [preferred, setPreferred] = useState<PayableMethod | null>(stored);
  const available = channelsFor(country);

  const choose = useCallback((next: PayableMethod) => {
    localStorage.setItem(KEY, next);
    setPreferred(next);
  }, []);

  const resolved =
    available.find((channel) => channel.method === preferred) ?? available[0] ?? null;

  return { available, resolved, choose };
}
