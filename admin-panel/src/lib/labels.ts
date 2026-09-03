/** أسماءُ الحالات ونغماتُها — **بيتٌ واحدٌ لكلِّ تعداد** (2026-09-02).
 *
 * **العلّةُ مقيسةٌ في هذه الشجرة لا مفترضة**: `METHOD_LABEL` كان **مكتوباً
 * ثلاث مرّات** (المدفوعات · الرحلات · الاشتراكات) **وافترق فعلاً** — «كوبون»
 * في واحدة و«خصم كوبون» في الأخرى للقيمة نفسِها. وهو الشكلُ الثامن يُصنع
 * بيد: **موضعان ينشران الشيءَ نفسَه، وكلٌّ صحيحٌ منفرداً**.
 *
 * **وما جعله يستحقّ البيتَ الآن**: الملفُّ الشخصيُّ (§37) يعرض رحلاتِ الشخص
 * ودفعاتِه واشتراكَه ورسومَه في درجٍ واحد — **فنسخةٌ رابعةٌ كانت ستُولد**،
 * وتُفتح إلى جانبِ الأصل في الشاشة نفسِها فيُقرأ الاختلافُ عطباً في البيانات.
 *
 * **ولا نغمةَ تُخترع هنا**: خمسُ نغماتٍ في `DESIGN.md` §2.6، و`Badge` يأخذ
 * النغمةَ لا الحالة.
 *
 * ## وما لا يسكن هنا
 *
 * **ما ليس ترجمةَ تعداد**: `coverage()` في شاشة الاشتراكات تقرأ الساعةَ
 * وتقرّر — **وهي حسبةٌ لا اسم**، وموضعُها حيث تُقرأ. و`DURATION_DAYS` ثوابتُ
 * خلفيةٍ لا أسماءُ عرض.
 */

import type { Tone } from "@/components/ui/Badge";
import type {
  CancellationChargeStatus,
  SearchKind,
  PaymentMethod,
  PaymentStatus,
  RideStatus,
  SubscriptionDurationType,
  WalletTransactionType,
} from "@/api/types";

// ─────────────────────────────────────────────── الرحلة

export const RIDE_STATUS_LABEL: Record<RideStatus, string> = {
  requested: "مطلوبة",
  searching: "يُبحث عن سائق",
  accepted: "مقبولة",
  arrived: "وصل السائق",
  at_stop: "وقوفٌ عند محطة",
  in_progress: "جارية",
  completed: "مكتملة",
  cancelled_by_rider: "ألغاها الراكب",
  cancelled_by_driver: "ألغاها السائق",
  no_driver_found: "لم يُوجد سائق",
};

/** نغماتُ الحالات من `DESIGN.md` §2.6 — لا اجتهادَ في اللون. */
export const RIDE_STATUS_TONE: Record<RideStatus, Tone> = {
  requested: "warn",
  searching: "warn",
  accepted: "warn",
  arrived: "warn",
  at_stop: "warn",
  in_progress: "warn",
  completed: "ok",
  cancelled_by_rider: "danger",
  cancelled_by_driver: "danger",
  no_driver_found: "muted",
};

// ─────────────────────────────────────────────── الدفع

/** **الخريطةُ شاملةٌ للتعداد** فلا تظهر سلسلةٌ خام في شاشة — ولو كانت القيمةُ
 *  لا تقع في هذا السياق (لا تُشترى باقةٌ بكوبون). */
export const PAYMENT_METHOD_LABEL: Record<PaymentMethod, string> = {
  cash: "كاش",
  cliq: "كليك",
  card: "بطاقة",
  wallet: "محفظة",
  promo: "خصم كوبون",
  share: "خصم مشاركة",
};

export const PAYMENT_STATUS_LABEL: Record<PaymentStatus, string> = {
  pending: "بانتظار التأكيد",
  confirmed: "مؤكَّدة",
  failed: "فاشلة",
  disputed: "متنازَعٌ عليها",
  refunded: "مردودة",
};

export const PAYMENT_STATUS_TONE: Record<PaymentStatus, Tone> = {
  pending: "warn",
  confirmed: "ok",
  failed: "danger",
  disputed: "danger",
  refunded: "muted",
};

// ─────────────────────────────────────────────── الدفتر

/** أنواعُ قيود الدفتر — **بمرآةِ التعداد لا `Record<string, string>`**:
 *  الشكلُ الفضفاضُ يمرّر نوعاً جديداً بلا ترجمةٍ فيُعرض خاماً. */
export const WALLET_TX_LABEL: Record<WalletTransactionType, string> = {
  topup: "شحن",
  ride_payment: "دفع رحلة",
  ride_earning: "أرباح رحلة",
  commission: "عمولة",
  transfer_in: "تحويل وارد",
  transfer_out: "تحويل صادر",
  withdrawal: "سحب",
  refund: "استرداد",
  subscription_payment: "اشتراك",
  adjustment: "تسوية",
};

// ─────────────────────────────────────────────── الاشتراك

export const SUBSCRIPTION_DURATION_LABEL: Record<
  SubscriptionDurationType,
  string
> = {
  daily: "يومية",
  weekly: "أسبوعية",
  monthly: "شهرية",
};

// ─────────────────────────────────────────────── رسمُ الإلغاء

export const CHARGE_STATUS_LABEL: Record<CancellationChargeStatus, string> = {
  pending: "لم يُحصَّل",
  settled: "وصل الكبتن",
  waived: "أُعفي",
  written_off: "شُطب",
};

export const CHARGE_STATUS_TONE: Record<CancellationChargeStatus, Tone> = {
  pending: "warn",
  settled: "ok",
  waived: "muted",
  written_off: "muted",
};

// ─────────────────────────────────────────────── السلفة والمستحقّ

export type AdvanceStatus = "outstanding" | "repaid" | "written_off";

export const ADVANCE_STATUS_LABEL: Record<AdvanceStatus, string> = {
  outstanding: "قائمة",
  repaid: "سُدِّدت",
  written_off: "شُطبت",
};

export const ADVANCE_STATUS_TONE: Record<AdvanceStatus, Tone> = {
  outstanding: "warn",
  repaid: "ok",
  written_off: "muted",
};

export type DebtStatus = "outstanding" | "settled" | "written_off";

export const DEBT_STATUS_LABEL: Record<DebtStatus, string> = {
  outstanding: "قائم",
  settled: "سُدِّد",
  written_off: "شُطب",
};

export const DEBT_STATUS_TONE: Record<DebtStatus, Tone> = {
  outstanding: "warn",
  settled: "ok",
  written_off: "muted",
};

// ─────────────────────────────────────── البحثُ العامُّ في الرأس (§39٫١٢٫٤)

/** أصنافُ إصابة البحث العامّ — **وجهةٌ لا حال**.
 *
 * **ولمَ هي هنا وليست تعداداً**: لا جدولَ اسمُه «صنفُ إصابة» — الصنفُ يقول
 * **إلى أيِّ شاشةٍ يقفز الدرج**، وهو معنًى في الواجهة لا في القاعدة. ومكانُه
 * هذا الملفّ لأن **الاسمَ المعروضَ لا يُكتب في مكوّن**: من كتبه هناك كتب
 * ثانياً حين تُضاف شاشةُ بحثٍ أخرى فافترقا.
 */
export const SEARCH_KIND_LABEL: Record<SearchKind, string> = {
  user: "حساب",
  driver: "كبتن",
  ride: "رحلة",
  claim: "مطالبة",
};
