/** صياغةُ ما يخصّ الرحلة للعرض — مشتركةٌ بين السجل والتفاصيل.
 *
 * **لا حسابَ مالياً هنا**: المبالغ تصل نصّاً من `NUMERIC(12,3)` وتُعرض كما
 * هي بتبديل خاناتٍ فقط. وما يُحسب في هذا الملف تواريخُ ونصوصُ حالات لا أرقام.
 */

import type {
  Currency,
  GenderPreference,
  PaymentMethod,
  RideStatus,
  VehicleCategory,
} from "@/api/types";
import { arabicDigits } from "@/lib/utils";

export const CURRENCY_LABEL: Record<Currency, string> = {
  JOD: "د.أ",
  LYD: "د.ل",
};

/** الاسمُ الكامل — تحت الرقم الكبير حيث يتسع المكان لكلمة. */
export const CURRENCY_FULL: Record<Currency, string> = {
  JOD: "دينار أردني",
  LYD: "دينار ليبي",
};

/** تفضيلُ جنس الركاب كما يُقرأ في الشاشات — مصدرٌ واحد للثلاث. */
export const PREFERENCE_LABEL: Record<GenderPreference, string> = {
  female: "النساء فقط",
  male: "الرجال فقط",
  any: "الجميع",
};

export const CATEGORY_LABEL: Record<VehicleCategory, string> = {
  economy: "اقتصادي",
  comfort: "مريح",
};

export const METHOD_LABEL: Record<PaymentMethod, string> = {
  cash: "كاش",
  wallet: "محفظة",
  card: "بطاقة",
  cliq: "كليك",
  // خصمُ كوبونٍ تدفعه الشركة (12-ز): يُقيَّد للكبتن كأي دفعةٍ تمرّ بالمنصة
  promo: "خصم كوبون",
};

export const RIDE_STATUS_LABEL: Record<RideStatus, string> = {
  requested: "بانتظار كبتن",
  searching: "نبحث عن كبتن",
  accepted: "مقبولة",
  arrived: "الكبتن وصل",
  at_stop: "وقوفٌ عند محطة",
  in_progress: "جارية",
  completed: "مكتملة",
  cancelled_by_rider: "ألغاها الراكب",
  cancelled_by_driver: "ألغيتَها",
  no_driver_found: "لم يُقبل الطلب",
};

/** لونُ الحالة — مكتملةٌ خضراء، وجاريةٌ برتقالية، وما عداها أحمر. */
export function statusTone(status: RideStatus): string {
  if (status === "completed") return "text-ok";
  if (status.startsWith("cancelled") || status === "no_driver_found")
    return "text-danger";
  return "text-warn";
}

/** «أمس ٧:٤٠ م» / «٩ أغسطس ٩:١٥ ص» — بالعربية وبأرقامها.
 *
 * الموضع `ar-EG` كما في `Subscription.tsx`: أسماءُ شهورٍ واحدة في التطبيق
 * كله أهمُّ من تفضيلٍ محلّي («آب» الشامية)، واختلافُها بين شاشتين يقرأ خللاً.
 */
export function formatWhen(iso: string): string {
  const at = new Date(iso);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);

  const time = at.toLocaleTimeString("ar-EG", {
    hour: "numeric",
    minute: "2-digit",
  });
  const sameDay = (a: Date, b: Date) => a.toDateString() === b.toDateString();

  if (sameDay(at, today)) return `اليوم ${time}`;
  if (sameDay(at, yesterday)) return `أمس ${time}`;
  return `${at.toLocaleDateString("ar-EG", { day: "numeric", month: "long" })} ${time}`;
}

/** المسافة بمنزلةٍ واحدة: `5.700` تُقرأ مبلغاً و`5.7` تُقرأ مسافة.
 *
 * وقصٌّ نصّي لا قسمةٌ ولا `toFixed`: لا رقمَ من الخلفية يمر بـ`Number`. */
export function trimDistance(value: string): string {
  const [whole, fraction = ""] = value.split(".");
  const first = fraction.slice(0, 1);
  return arabicDigits(first && first !== "0" ? `${whole}.${first}` : whole);
}


/** وقتُ حجزٍ كما يقرؤه الكبتن: ساعةٌ ودقيقةٌ بأرقامٍ عربية، ويومٌ إن لم يكن اليوم.
 *
 * **والأرقامُ عربيةٌ هنا لأنها كمّية لا معرِّف** (قاعدةُ `Cards.tsx`): الساعةُ
 * تُقرأ ولا تُطابق حرفاً بحرفٍ كلوحةٍ أو مرجعِ حوالة.
 */
export function bookedTime(iso: string): string {
  const date = new Date(iso);
  const time = date.toLocaleTimeString("ar", {
    hour: "2-digit",
    minute: "2-digit",
  });
  const sameDay = new Date().toDateString() === date.toDateString();
  if (sameDay) return time;
  const day = date.toLocaleDateString("ar", { weekday: "long" });
  return `${day} ${time}`;
}
