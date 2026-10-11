/** النصوص العربية لقيم الـ enum القادمة من الخلفية.
 *
 * مكانٌ واحد: نفس الحالة تُعرض في شاشة التتبع وسجل الرحلات وتفاصيلها، ونصّان
 * مختلفان لحالةٍ واحدة يقرآن كحالتين.
 */

import type { PaymentRequestStatus } from "@/api/types";
import type {
  PaymentMethod,
  PaymentStatus,
  RideCategoryFace,
  RideStatus,
  VehicleCategory,
  WalletTransactionType,
} from "@/api/types"; import { tr } from "@/lib/i18n";

export const RIDE_STATUS_LABEL: Record<RideStatus, string> = {
  requested: tr("جارٍ إرسال الطلب"),
  searching: tr("نبحث عن كبتن"),
  accepted: tr("الكبتن في الطريق"),
  arrived: tr("وصل الكبتن"),
  at_stop: tr("وقوفٌ عند محطة"),
  in_progress: tr("الرحلة جارية"),
  completed: tr("انتهت الرحلة"),
  cancelled_by_rider: tr("ألغيتَ الرحلة"),
  cancelled_by_driver: tr("ألغى الكبتن الرحلة"),
  no_driver_found: tr("لم نجد كبتناً متاحاً"),
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
  economy: tr("اقتصادي"),
  comfort: tr("مريح"),
};

export const VEHICLE_HINT: Record<VehicleCategory, string> = {
  economy: tr("الخيار الأوفر"),
  comfort: tr("سيارة أوسع وأحدث"),
};

/** أيقونةُ الفئة في «اختر الفئة» (R06) — والجديدةُ من صفّها. */
export const CATEGORY_ICON: Record<VehicleCategory, string> = { economy: "local_taxi", comfort: "directions_car" };

/** **الفئاتُ الجديدةُ تُسمّى من `/config`** (SPEC §٦٧) — تُضاف إلى الجداول أعلاه **ولا تمسّ المدمجتين**: «اقتصادي» و«مريح» تبقيان بنصّهما
 *  اليومَ حرفاً. ويُستدعى حين تصل الإعدادات (`ConfigProvider`)، فكلُّ شاشةٍ تقرأ الجدولَ نفسَه بلا بابٍ ثانٍ. */
export function registerCategoryFaces(faces: RideCategoryFace[]): void {
  for (const face of faces) {
    if (face.key === "economy" || face.key === "comfort") continue;
    VEHICLE_LABEL[face.key] = face.name;
    VEHICLE_HINT[face.key] = face.description ? tr("{0} · {1} مقاعد", { 0: face.description, 1: face.seats }) : tr("{0} مقاعد", { 0: face.seats });
    CATEGORY_ICON[face.key] = face.icon;
  }
}

export const PAYMENT_METHOD_LABEL: Record<PaymentMethod, string> = {
  wallet: tr("المحفظة"),
  cliq: tr("كليك"),
  card: tr("بطاقة"),
  cash: tr("كاش"),
  // خصمُ كوبونٍ (12-ز) — **تدفعه الشركة** لا الراكب، فيقرؤه صفَّاً في إيصاله
  promo: tr("خصم كوبون"),
  // خصمُ المشاركة (12-ي) — تدفعه الشركةُ كذلك، **وقناةٌ مستقلةٌ عن الكوبون**
  // كي لا يُقرأ خصمُ مشاركةٍ «خصم كوبون» على رحلةٍ بلا كوبون
  share: tr("خصم مشاركة"),
  // **المشوارُ الثابت** (§٦٣-ج/٦) — مالُه هو دفعه مقدّماً مع الاشتراك، **فلا يُقرأ «خصماً»**: سطرُ إيصالٍ يقول من أين دُفعت
  commute: tr("اشتراك المشوار"),
};

export const PAYMENT_STATUS_LABEL: Record<PaymentStatus, string> = {
  pending: tr("بانتظار التأكيد"),
  confirmed: tr("مؤكدة"),
  failed: tr("فاشلة"),
  disputed: tr("قيد النزاع"),
  refunded: tr("مستردّة"),
  // **بدّلتَ طريقتَها** (§٦٤-ز) — صفٌّ باقٍ في الإيصال لا مالٌ ضاع، والجديدةُ تحته بقناتها
  voided: tr("بُدِّلت طريقتُها"),
};

export const TRANSACTION_LABEL: Record<WalletTransactionType, string> = {
  topup: tr("شحن رصيد"),
  ride_payment: tr("دفع رحلة"),
  ride_earning: tr("أرباح رحلة"),
  commission: tr("عمولة"),
  transfer_in: tr("تحويل وارد"),
  transfer_out: tr("تحويل صادر"),
  withdrawal: tr("سحب"),
  refund: tr("استرداد"),
  subscription_payment: tr("اشتراك"),
  adjustment: tr("تسوية"),
  // البقشيش (12-و): الراكبُ يرى `tip_payment` في كشفه، و`tip` لا يقع له —
  // لكنه في التعداد فيُسمّى، فلا تظهر سلسلةٌ خامٌ في كشفٍ يوماً
  tip: tr("بقشيش وارد"),
  tip_payment: tr("بقشيش للكبتن"),
  // **والستّةُ الباقيةُ تُسمّى وإن لم تقع للراكب** — للعلّة نفسِها
  // المكتوبة فوق: **لا تظهر سلسلةٌ خامٌ في كشفٍ يوماً**. وثلاثٌ منها
  // تخصّ الكبتن وحدَه، **وتُسمّى بلغة الراكب لا بلغة الدفتر**.
  cancellation_fee: tr("رسم إلغاء"),
  cancellation_compensation: tr("تعويض إلغاء"),
  advance: tr("سلفة"),
  advance_repayment: tr("سداد سلفة"),
  skin_purchase: tr("شراء زينة مركبة"),
  referral_bonus: tr("حافز دعوة صديق"),
  // **الحجزُ المضمون** (§٦٣-ج/٣) — الحفظُ والردُّ والتعويضُ تقع له، والاثنان الباقيان للكبتن ويُسمّيان للعلّة نفسِها
  guarantee_hold: tr("رسم حجز مضمون"),
  guarantee_refund: tr("ردّ رسم الضمان"),
  guarantee_compensation: tr("تعويض اعتذار الكبتن"),
  guarantee_fee: tr("رسم ضمان للكبتن"),
  guarantee_penalty: tr("غرامة اعتذار"),
  // **المشوارُ الثابت** (§٦٣-ج/٦) — المقدَّمُ وما عاد منه يقعان له، والحافزُ للكبتن ويُسمّى للعلّة أعلاه
  commute_prepay: tr("اشتراك المشوار الثابت"),
  commute_credit: tr("رصيدُ أيامٍ لم تُستعمل"),
  commute_incentive: tr("حافزُ المشوار الثابت"),
  // **بين المدن** (§٦٣-ج/٧) — المقعدُ وردُّه يقعان له، والأجرةُ للكبتن وتُسمّى للعلّة أعلاه
  intercity_hold: tr("حجزُ مقعدٍ بين المدن"),
  intercity_refund: tr("ردُّ حجزٍ بين المدن"),
  intercity_earning: tr("أجرةُ رحلةٍ بين المدن"),
  // **الاسترداد الأسبوعي** (§٦٣-ج/٨) — من TAXO له في اليوم الأخير من أسبوعه
  cashback: tr("الاسترداد الأسبوعي"),
  // **التقريب** (§٧٠-ج/٦) — زائدُ «سدّد كلَّه» يعود إلى المحفظة؛ يقع للكبتن ويُسمّى للعلّة أعلاه
  rounding: tr("تقريب"),
  // **بطاقةُ TAXO** (§٧٣-هـ المرحلة ٢) — اسمٌ مميَّزٌ في السجلّ بأمر المالك
  taxo_card: tr("شحن ببطاقة TAXO"),
};

export const TOPUP_STATUS_LABEL: Record<string, string> = {
  pending: tr("بانتظار مراجعة الإدارة"),
  confirmed: tr("مؤكد"),
  rejected: tr("مرفوض"),
};

/** **حالاتُ الدفعة في النظام الجديد** (SPEC §٧٣-هـ) — كما يقرؤها صاحبُها. */
export const PAYMENT_REQUEST_STATUS_LABEL: Record<PaymentRequestStatus, string> = {
  pending: tr("قيد المراجعة"),
  approved: tr("اعتُمدت"),
  rejected: tr("رُفضت"),
  refunded: tr("رُدّت"),
  cancelled: tr("أُلغيت"),
};
