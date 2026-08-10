/** النصوص العربية لقيم الـ enum القادمة من الخلفية.
 *
 * مكانٌ واحد: نفس الحالة تُعرض في شاشة التتبع وسجل الرحلات وتفاصيلها، ونصّان
 * مختلفان لحالةٍ واحدة يقرآن كحالتين.
 */

import type {
  PaymentMethod,
  PaymentStatus,
  RideStatus,
  VehicleCategory,
  WalletTransactionType,
} from "@/api/types";

export const RIDE_STATUS_LABEL: Record<RideStatus, string> = {
  requested: "جارٍ إرسال الطلب",
  searching: "نبحث عن كبتن",
  accepted: "الكبتن في الطريق",
  arrived: "وصل الكبتن",
  in_progress: "الرحلة جارية",
  completed: "انتهت الرحلة",
  cancelled_by_rider: "ألغيتَ الرحلة",
  cancelled_by_driver: "ألغى الكبتن الرحلة",
  no_driver_found: "لم نجد كبتناً متاحاً",
};

export const ACTIVE_RIDE_STATUSES: RideStatus[] = [
  "requested",
  "searching",
  "accepted",
  "arrived",
  "in_progress",
];

export const VEHICLE_LABEL: Record<VehicleCategory, string> = {
  economy: "اقتصادي",
  comfort: "مريح",
};

export const VEHICLE_HINT: Record<VehicleCategory, string> = {
  economy: "الخيار الأوفر",
  comfort: "سيارة أوسع وأحدث",
};

export const PAYMENT_METHOD_LABEL: Record<PaymentMethod, string> = {
  wallet: "المحفظة",
  cliq: "كليك",
  card: "بطاقة",
  cash: "كاش",
};

export const PAYMENT_STATUS_LABEL: Record<PaymentStatus, string> = {
  pending: "بانتظار التأكيد",
  confirmed: "مؤكدة",
  failed: "فاشلة",
  disputed: "قيد النزاع",
  refunded: "مستردّة",
};

export const TRANSACTION_LABEL: Record<WalletTransactionType, string> = {
  topup: "شحن رصيد",
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

export const TOPUP_STATUS_LABEL: Record<string, string> = {
  pending: "بانتظار مراجعة الإدارة",
  confirmed: "مؤكد",
  rejected: "مرفوض",
};
