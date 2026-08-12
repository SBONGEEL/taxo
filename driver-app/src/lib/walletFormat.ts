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
