/** أسماءُ ما في الدفتر وحالاتِ السحب — مشتركةٌ بين المحفظة وطلبات السحب.
 *
 * **الإشارةُ تأتي من الخلفية لا من الواجهة**: قيدُ الدفتر يحمل إشارته في
 * `amount` نفسه (قيدُ CHECK يربط الإشارة بالنوع)، فالواجهة تقرأ أولَ محرفٍ
 * ولا تطرح ولا تجمع. ولا تُحسب هنا حصيلةٌ ولا رصيد: `balance_after` يأتي
 * محسوباً، والمجموعُ من الدفتر في الخلفية (القسم 14).
 */

import {
  ArrowLeftRight,
  Banknote,
  CalendarCheck,
  Car,
  Gift,
  Percent,
  Scale,
  Undo2,
  Wallet,
  type LucideIcon,
} from "lucide-react";

import type {
  WalletTransactionType,
  WithdrawalMethod,
  WithdrawalStatus,
} from "@/api/types";

export const TRANSACTION_LABEL: Record<WalletTransactionType, string> = {
  topup: "شحن رصيد",
  ride_payment: "دفع رحلة",
  ride_earning: "أرباح رحلة",
  commission: "عمولة المنصة",
  transfer_in: "تحويل وارد",
  transfer_out: "تحويل صادر",
  withdrawal: "سحب",
  refund: "استرجاع",
  subscription_payment: "اشتراك",
  adjustment: "تسوية",
  // البقشيش (12-و). و`tip_payment` لا يظهر في كشف الكبتن أبداً — هو خصمُ
  // الراكب — لكن الاتحادَ مرآةُ التعداد فيُسمّى، فلا تظهر سلسلةٌ خامٌ يوماً
  tip: "بقشيش",
  tip_payment: "بقشيش مدفوع",
  advance: "سلفة",
  advance_repayment: "اقتطاع سداد سلفة",
  cancellation_fee: "رسم إلغاء",
  cancellation_compensation: "تعويض إلغاء",
  referral_bonus: "مكافأة إحالة",
  skin_purchase: "شراء مركبة",
  // **الحجزُ المضمون** (§٦٣-ج/٣) — الرسمُ يصله والغرامةُ تخرج منه، والثلاثةُ الباقيةُ للراكب وتُسمّى للعلّة أعلاه
  guarantee_fee: "رسم حجز مضمون",
  guarantee_penalty: "غرامة اعتذار عن حجز مضمون",
  guarantee_hold: "رسم ضمان محفوظ",
  guarantee_refund: "ردّ رسم الضمان",
  guarantee_compensation: "تعويض حجز مضمون",
  // **المشوارُ الثابت** (§٦٣-ج/٦) — الحافزُ يصله لكلِّ رحلةٍ يقودها معتمداً، والاثنان الباقيان للراكب ويُسمّيان للعلّة أعلاه
  commute_incentive: "حافزُ المشوار الثابت",
  commute_prepay: "اشتراك المشوار الثابت",
  commute_credit: "رصيدُ أيامٍ لم تُستعمل",
  // **بين المدن** (§٦٣-ج/٧) — أجرةُ رحلته من مال المقاعد المحفوظ عند الإنهاء، والاثنان الباقيان للراكب ويُسمّيان للعلّة أعلاه
  intercity_earning: "أجرةُ رحلةٍ بين المدن",
  intercity_hold: "حجزُ مقعدٍ بين المدن",
  intercity_refund: "ردُّ حجزٍ بين المدن",
  // **الاسترداد الأسبوعي** (§٦٣-ج/٨) — للراكب وحدَه من TAXO، ويُسمّى للعلّة أعلاه
  cashback: "الاسترداد الأسبوعي",
  // **التقريب** (§٧٠-ج/٦) — زائدُ «سدّد كلَّه» (الدَّين بكليك أو السلفة) يعود إلى محفظته: دفع المبلغَ مقرَّباً للأعلى، والفرقُ له.
  // **واسمُه اسمُ الخلفية** (`finance_summary`: «تقريب») — والإشارةُ على المبلغ تقول اتجاهَه
  rounding: "تقريب",
};

/** أيقونةُ كل نوع — lucide لا محرفاً يونيكودياً (قرار `DESIGN-DECISIONS` 19).
 *
 * والأيقونةُ تصف **مصدر القيد** لا اتجاهه: الاتجاهُ مكتوبٌ بالإشارة واللون
 * على المبلغ نفسه، وتكرارُه في مربّعٍ ثانٍ يشغل مكاناً بلا معلومة. */
export const TRANSACTION_ICON: Record<WalletTransactionType, LucideIcon> = {
  topup: Wallet,
  ride_payment: Car,
  ride_earning: Car,
  commission: Percent,
  transfer_in: ArrowLeftRight,
  transfer_out: ArrowLeftRight,
  withdrawal: Banknote,
  refund: Undo2,
  subscription_payment: CalendarCheck,
  adjustment: Scale,
  tip: Gift,
  tip_payment: Gift,
  // **والأيقونةُ تصف مصدرَ القيد لا اتجاهَه** (القاعدةُ أعلاه): السلفةُ
  // ومَردُّها من بابٍ واحد، والإلغاءُ ورسمُه كذلك.
  advance: Banknote,
  advance_repayment: Banknote,
  cancellation_fee: Scale,
  cancellation_compensation: Scale,
  referral_bonus: Gift,
  skin_purchase: Car,
  // **والحجزُ المضمون من بابٍ واحد** — الرسمُ وغرامتُه وردُّه
  guarantee_fee: CalendarCheck,
  guarantee_penalty: CalendarCheck,
  guarantee_hold: CalendarCheck,
  guarantee_refund: CalendarCheck,
  guarantee_compensation: CalendarCheck,
  // **والمشوارُ الثابتُ من بابٍ واحد** — الحافزُ والمقدَّمُ وما عاد منه
  commute_incentive: CalendarCheck,
  commute_prepay: CalendarCheck,
  commute_credit: CalendarCheck,
  // **وبين المدن رحلةٌ** — أيقونةُ أجرة الرحلة لأجرته، والمقعدُ وردُّه بالأيقونة نفسِها
  intercity_earning: Car,
  intercity_hold: Car,
  intercity_refund: Car,
  // **والاسترداد الأسبوعيُّ حافزٌ من TAXO** — أيقونةُ المكافأة كالإحالة
  cashback: Gift,
  // **والتقريبُ زائدُ سدادٍ يعود** — أيقونةُ الردّ كالاسترجاع
  rounding: Undo2,
};

export const WITHDRAWAL_STATUS_LABEL: Record<WithdrawalStatus, string> = {
  pending: "معلّق",
  approved: "موافَق عليه",
  paid: "مدفوع",
  rejected: "مرفوض",
};

/** «معلّق» و«موافَق عليه» كلاهما يحجز المبلغ ولم يُدفع بعد. */
export function withdrawalTone(status: WithdrawalStatus): string {
  if (status === "paid") return "text-ok";
  if (status === "rejected") return "text-danger";
  return "text-warn";
}

export const WITHDRAWAL_METHOD_LABEL: Record<WithdrawalMethod, string> = {
  cliq: "كليك",
  bank: "حوالة بنكية",
};

/** قيدٌ يزيد الرصيد أم ينقصه — من إشارة المبلغ لا من جدولٍ ثانٍ يخالفها. */
export function isDebit(amount: string): boolean {
  return amount.trimStart().startsWith("-");
}

/** المبلغ بلا إشارته — الإشارةُ تُرسم محرفاً مستقلاً في اتجاهٍ ثابت. */
export function unsigned(amount: string): string {
  return amount.replace(/^\s*-/, "");
}
