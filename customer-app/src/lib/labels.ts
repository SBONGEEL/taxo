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
  at_stop: "وقوفٌ عند محطة",
  in_progress: "الرحلة جارية",
  completed: "انتهت الرحلة",
  cancelled_by_rider: "ألغيتَ الرحلة",
  cancelled_by_driver: "ألغى الكبتن الرحلة",
  no_driver_found: "لم نجد كبتناً متاحاً",
};

/** مرآةُ `ACTIVE_RIDER_STATUSES` في `models/ride.py` — و**نقصُها يُنهي رحلةً
 * جارية في الواجهة وحدها**: حالةٌ غائبة عن هذه القائمة تُقرأ «انتهت»، فتظهر
 * ورقةُ الخاتمة والرحلةُ ما زالت تسير. وقع ذلك فعلاً مع `at_stop` وكشفه
 * الفحصُ البصري وحده — `check:enums` لا يرى مصفوفةً، يرى اتحادات. */
export const ACTIVE_RIDE_STATUSES: RideStatus[] = [
  "requested",
  "searching",
  "accepted",
  "arrived",
  "in_progress",
  "at_stop",
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
  // خصمُ كوبونٍ (12-ز) — **تدفعه الشركة** لا الراكب، فيقرؤه صفَّاً في إيصاله
  promo: "خصم كوبون",
  // خصمُ المشاركة (12-ي) — تدفعه الشركةُ كذلك، **وقناةٌ مستقلةٌ عن الكوبون**
  // كي لا يُقرأ خصمُ مشاركةٍ «خصم كوبون» على رحلةٍ بلا كوبون
  share: "خصم مشاركة",
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
  // البقشيش (12-و): الراكبُ يرى `tip_payment` في كشفه، و`tip` لا يقع له —
  // لكنه في التعداد فيُسمّى، فلا تظهر سلسلةٌ خامٌ في كشفٍ يوماً
  tip: "بقشيش وارد",
  tip_payment: "بقشيش للكبتن",
  // **والستّةُ الباقيةُ تُسمّى وإن لم تقع للراكب** — للعلّة نفسِها
  // المكتوبة فوق: **لا تظهر سلسلةٌ خامٌ في كشفٍ يوماً**. وثلاثٌ منها
  // تخصّ الكبتن وحدَه، **وتُسمّى بلغة الراكب لا بلغة الدفتر**.
  cancellation_fee: "رسم إلغاء",
  cancellation_compensation: "تعويض إلغاء",
  advance: "سلفة",
  advance_repayment: "سداد سلفة",
  skin_purchase: "شراء زينة مركبة",
  referral_bonus: "حافز دعوة صديق",
};

export const TOPUP_STATUS_LABEL: Record<string, string> = {
  pending: "بانتظار مراجعة الإدارة",
  confirmed: "مؤكد",
  rejected: "مرفوض",
};
