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

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";

import { changePaymentMethod, declareHandover, getMyUnconfirmed } from "@/api/endpoints";
import type {
  CountryConfig,
  PaymentMethod,
  RidePayments,
  RiderUnconfirmed,
  RiderUnconfirmedItem,
} from "@/api/types";
import { useSession } from "@/lib/session";

/** القنواتُ التي **تكتبها المنصّةُ عن الراكب** ولا يختارها أحد: خصمُ الكوبون
 *  (12-ز) وخصمُ المشاركة (12-ي). كلتاهما تتحمّلها الشركةُ وتُنشأ عند الإنهاء.
 *
 *  **وقائمةٌ لا قيمةٌ واحدة** لأن ما يجمعها مفهومٌ لا اسم: كُتب هذا أصلاً
 *  `Exclude<PaymentMethod, "promo">` وكان صحيحاً بقناةٍ واحدة، ثم أضافت 12-ي
 *  `share` فصارت **تظهر خياراً في مُنتقي الدفع** — أي زرٌّ يعد الراكبَ بأن
 *  يدفع بخصمٍ تتحمّله الشركة. وأمسكه المصرّفُ عند `CTA` لا في متصفح، لأن
 *  `Record<PayableMethod, …>` يفرض عضواً لكلِّ قيمة.
 *
 *  **والمشوارُ الثابتُ ثالثُها** (§٦٣-ج/٦): مالُ الراكب نفسِه لكنه دُفع مقدّماً مع الاشتراك، **وتكتبه المنصّةُ عند الاكتمال** —
 *  قرارُ شراءٍ لا قناةٌ تُختار في الرحلة (`PLATFORM_WRITTEN_METHODS` في الخلفية).
 */
type PlatformWrittenMethod = "promo" | "share" | "commute";

/** ما يجوز لصاحب الحساب اختياره. */
export type PayableMethod = Exclude<PaymentMethod, PlatformWrittenMethod>;

/** **وبلا أيقونة**: كانت أيقونةُ `lucide` لكلِّ قناةٍ هنا، ويقرؤها وجهُ المنتقي القائم وحدَه — **ونُزع** (§٦٢/٣)، فرموزُ
 *  الهوية في `PAY_ICON_T2` (`components/payment/PaymentPicker.tsx`). وحقلٌ لا يقرؤه أحدٌ في `lib/` يُنزع (`check:readers`). */
export interface PaymentChannel {
  method: PayableMethod;
  /** المفتاح الذي يحكم القناة — والكاش بلا مفتاح لأنه يعمل بلا إعداد. */
  feature?: string;
  hint: string;
}

/** الترتيب مقصود: المحفظة أولاً وكليك ثانياً (SPEC القسم 6.2). */
export const PAYMENT_CHANNELS: PaymentChannel[] = [
  { method: "wallet", feature: "wallet_enabled", hint: "خصمٌ فوري من رصيدك" },
  { method: "cliq", feature: "cliq_enabled", hint: "حوّل على alias الكبتن" },
  { method: "card", feature: "card_enabled", hint: "بطاقة أو محفظة الهاتف" },
  { method: "cash", hint: "سلّم المبلغ للكبتن" },
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

// ═══ المدفوعاتُ غيرُ المؤكَّدة (`design/PAYMENTS-UNCONFIRMED.md`، SPEC §٦٤-ز) ═══════════════════════════════════════════
//
// **والطريقةُ تُرسل مع الطلب الآن حيث المفتاحُ مشتعل** (§٢-١) — فالقاعدةُ أعلاه («لا يُرسل إلى الخلفية») **صادقةٌ في السوق
// المطفأ وحدَه**. وما زال التفضيلُ لا يُقيّد صاحبَه: «غيّر طريقة الدفع» بابُه بعد الرحلة.

/** **مفتاحُ المسار كلِّه** — مطفأً لا صفحةَ ولا شريطَ ولا طريقةَ تُرسل مع الطلب، والتطبيقُ كما كان حرفاً. */
export const UNCONFIRMED_FLAG = "unconfirmed_payments_enabled";

/** **ما بيد الراكب أن يفعله** — وهو وحدَه ما يفتح الصفحةَ عند الفتح (§٦). **وما سواه شريطٌ لا صفحة**: «بانتظار تأكيد الكبتن —
 *  لا يلزمك شيء»، **ونزاعُ كليك** بيد فريق TAXO (لا «سأدفع الآن» فوق حوالةٍ قيل إنها خرجت — `change_method` يردّه). */
export function needsRider(item: RiderUnconfirmedItem): boolean {
  if (item.state === "awaiting_you" || item.state === "payment_due") return true;
  return item.state === "disputed" && item.method === "cash";
}


/** **جوابٌ واحدٌ لقارئين** — الصفحةُ وشريطُ الرئيسية ونقرةُ الإشعار. **ونداءٌ لكلِّ قارئٍ يفترق جوابُه عن أخيه** بين لحظتين:
 *  الشريطُ يقول «تأكيدٌ ينتظرك» والصفحةُ فارغة.
 *
 *  **ومختومٌ بصاحبه** (`owner` = `users.id`): المخزنُ عمرُ الوحدة لا عمرُ الجلسة — **والخروجُ لا يعيد تحميلَ الصفحة**
 *  (`session.tsx::signOut` يضع `user` فارغاً وحسب). فحسابٌ ثانٍ يدخل على الجهاز نفسِه كان يرى ما ينتظر الأوّلَ في شريطه،
 *  **ويبقى يراه إن سقط نداؤه** (الخطأُ صامت). **فلا يُقرأ الجوابُ إلا لمن سُئل له** (`useUnconfirmed`). */
let held: { owner: string; data: RiderUnconfirmed } | null = null;
/** **آخرُ سؤال** — جوابُ سؤالٍ أقدمَ يصل بعد أحدثَ منه لا يكتب فوقه (حسابٌ خرج ونداؤه في الطريق، أو فعلٌ تلاه فعل). */
let asked = 0;
const listeners = new Set<() => void>();

function subscribeUnconfirmed(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** يُسأل البابُ ثانيةً **لصاحبه** ويُبلَّغ كلُّ قارئ — **بعد كلِّ فعلٍ** (إقرارٌ · تبديلٌ) لا بحسابٍ في الشاشة: الحالُ من الخلفية
 *  وحدَها. */
export async function refreshUnconfirmed(owner: string): Promise<RiderUnconfirmed> {
  const ticket = ++asked;
  const data = await getMyUnconfirmed();
  if (ticket === asked) {
    held = { owner, data };
    for (const listener of listeners) listener();
  }
  return data;
}

/** **ما ينتظر الراكبَ** — `null` حتى يصل، **وحيث المفتاحُ مطفأٌ لا نداءَ أصلاً**، **ولا جوابَ حسابٍ آخر** (`held.owner`).
 *
 *  ويُسأل البابُ عند كلِّ تركيب، **وعند عودة التطبيق إلى الواجهة** (`visibilitychange` — قاعدةُ `useWeeklyCashback` في
 *  `lib/bookings.ts`): التطبيقُ في الخلفية لا يُغلق، فمن عاد إليه من تذكيرٍ أو بعد ساعاتٍ يرى ما صار لا ما كان. */
export function useUnconfirmed(enabled: boolean): RiderUnconfirmed | null {
  const { user } = useSession();
  const owner = user?.id ?? null;
  const value = useSyncExternalStore(subscribeUnconfirmed, () =>
    held !== null && held.owner === owner ? held.data : null,
  );
  useEffect(() => {
    if (!enabled || owner === null) return;
    const read = () => {
      refreshUnconfirmed(owner).catch(() => undefined);
    };
    read();
    const onVisible = () => {
      if (document.visibilityState === "visible") read();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [enabled, owner]);
  return enabled ? value : null;
}

/** **«عند كلِّ فتح» — مرّةً للفتحة لا لكلِّ عودةٍ إلى الرئيسية** (§٦): الصفحةُ تُعرض بعد الترحيب أوّلَ ما تُرسم الرئيسية،
 *  و«لاحقاً» يُخفيها لهذه الفتحة وحدَها — **والفتحةُ عمرُ التطبيق في الذاكرة**، فتعود في التالية حتى تُحسم.
 *
 *  **ولكلِّ حسابٍ فتحتُه**: حسابٌ ثانٍ يدخل في العمر نفسِه لم يرَ صفحتَه بعد — وكان يجدها «مُستهلَكة» بفتحة الأوّل. */
const openedFor = new Set<string>();

export function claimLaunchOpening(owner: string): boolean {
  if (openedFor.has(owner)) return false;
  openedFor.add(owner);
  return true;
}

/** **«سلّمتُ المبلغ»** — ثمّ يُسأل البابُ ثانيةً فتنتقل البطاقةُ إلى «بانتظار تأكيد الكبتن».
 *
 *  **وسقوطُ السؤال بعد إقرارٍ نجح لا يُقال سقوطاً للإقرار**: الإقرارُ كُتب، وجملةُ «تعذّر تسجيل الإقرار» فوقه تدعو إلى ضغطةٍ ثانية
 *  على ما سُجّل — فيُبلع خطؤه كما في `changeUnconfirmedMethod`. */
export async function declareCashHandover(owner: string, paymentId: string): Promise<void> {
  await declareHandover(paymentId);
  await refreshUnconfirmed(owner).catch(() => undefined);
}

/** **«غيّر طريقة الدفع» / «سأدفع الآن»** — بحمل الدفع حرفاً، ومفتاحُ عدم التكرار من الشاشة (ضغطتان لا تفتحان دفعتين). */
export async function changeUnconfirmedMethod(
  owner: string,
  paymentId: string,
  method: PayableMethod,
  idempotencyKey: string,
  extras: { save_card?: boolean; saved_card_id?: string } = {},
): Promise<RidePayments> {
  const state = await changePaymentMethod(paymentId, method, idempotencyKey, extras);
  await refreshUnconfirmed(owner).catch(() => undefined);
  return state;
}
