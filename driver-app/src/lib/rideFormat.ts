/** صياغةُ ما يخصّ الرحلة للعرض — مشتركةٌ بين السجل والتفاصيل.
 *
 * **لا حسابَ مالياً هنا**: المبالغ تصل نصّاً من `NUMERIC(12,3)` وتُعرض كما
 * هي بتبديل خاناتٍ فقط. وما يُحسب في هذا الملف تواريخُ ونصوصُ حالات لا أرقام.
 */

import type {
  Currency,
  GenderPreference,
  PaymentMethod,
  Ride,
  RideStatus,
  VehicleCategory, RideCategoryFace } from "@/api/types";
import { currencyLabel, currencyName, digits,
  DISPLAY_LOCALE,
} from "@/lib/utils"; import { tr } from "@/lib/i18n";

/** **يُقرأ من `currencyLabel` ولا يُكتب هنا** (2026-09-07): البيتُ نزل إلى
 *  `@/lib/utils` كي يقرأه صندوقُ اللافتات المتطابقُ بايتاً في التطبيقين،
 *  **وهذا الاسمُ باقٍ لأن ثلاثين قارئاً يستوردونه**.
 *
 *  **ويُقرأ لحظةَ القراءة لا لحظةَ التحميل** (SPEC §٧٣-ج/١٢): كان جدولاً يُبنى حين تُحمَّل الوحدة — **قبل أن تصل `/config`** —
 *  والعلاماتُ اليومَ تأتي منها، **فجدولٌ يُبنى مبكّراً يُرسم رموزاً خاماً**. فصار وكيلاً يسأل السجلَّ عند كلِّ قراءة. */
export const CURRENCY_LABEL: Record<Currency, string> = new Proxy({} as Record<Currency, string>, {
  get: (_, code) => currencyLabel(String(code)),
});

/** الاسمُ الكامل — تحت الرقم الكبير حيث يتسع المكان لكلمة. **ومن السجلِّ نفسِه** لا جدولٍ ثانٍ. */
export const CURRENCY_FULL: Record<Currency, string> = new Proxy({} as Record<Currency, string>, {
  get: (_, code) => currencyName(String(code)),
});

/** تفضيلُ جنس الركاب كما يُقرأ في الشاشات — مصدرٌ واحد للثلاث. */
export const PREFERENCE_LABEL: Record<GenderPreference, string> = {
  female: tr("النساء فقط"),
  male: tr("الرجال فقط"),
  any: tr("الجميع"),
};

export const CATEGORY_LABEL: Record<VehicleCategory, string> = {
  economy: tr("اقتصادي"),
  comfort: tr("مريح"),
};

/** **الفئاتُ الجديدةُ تُسمّى من `/config`** (SPEC §٦٧) — تُضاف إلى الجداول أعلاه **ولا تمسّ المدمجتين**: «اقتصادي» و«مريح» تبقيان بنصّهما
 *  اليومَ حرفاً. ويُستدعى حين تصل الإعدادات (`ConfigProvider`)، فكلُّ شاشةٍ تقرأ الجدولَ نفسَه بلا بابٍ ثانٍ. */
export function registerCategoryFaces(faces: RideCategoryFace[]): void {
  for (const face of faces) {
    if (face.key === "economy" || face.key === "comfort") continue;
    CATEGORY_LABEL[face.key] = face.name;
  }
}

export const METHOD_LABEL: Record<PaymentMethod, string> = {
  cash: tr("كاش"),
  wallet: tr("محفظة"),
  card: tr("بطاقة"),
  cliq: tr("كليك"),
  // خصمُ كوبونٍ تدفعه الشركة (12-ز): يُقيَّد للكبتن كأي دفعةٍ تمرّ بالمنصة
  promo: tr("خصم كوبون"),
  // خصمُ المشاركة (12-ي) — تتحمّله الشركة، فلا يَنقص ما يقبضه الكبتن
  share: tr("خصم مشاركة"),
  // **المشوارُ الثابت** (§٦٣-ج/٦) — دفعه الراكبُ مقدّماً مع اشتراكه، ويُقيَّد للكبتن كأيِّ دفعةٍ تمرّ بالمنصة
  commute: tr("اشتراك المشوار"),
};

export const RIDE_STATUS_LABEL: Record<RideStatus, string> = {
  requested: tr("بانتظار كبتن"),
  searching: tr("نبحث عن كبتن"),
  accepted: tr("مقبولة"),
  arrived: tr("الكبتن وصل"),
  at_stop: tr("وقوفٌ عند محطة"),
  in_progress: tr("جارية"),
  completed: tr("مكتملة"),
  cancelled_by_rider: tr("ألغاها الراكب"),
  cancelled_by_driver: tr("ألغيتَها"),
  no_driver_found: tr("لم يُقبل الطلب"),
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

  const time = digits(at.toLocaleTimeString(DISPLAY_LOCALE, {
    hour: "numeric",
    minute: "2-digit",
  }));
  const sameDay = (a: Date, b: Date) => a.toDateString() === b.toDateString();

  if (sameDay(at, today)) return tr("اليوم {0}", { 0: time });
  if (sameDay(at, yesterday)) return tr("أمس {0}", { 0: time });
  return `${digits(at.toLocaleDateString(DISPLAY_LOCALE, { day: "numeric", month: "long" }))} ${time}`;
}

/** **سطرُ «تقريب» في تفصيل الأجرة** (SPEC §٧٠-ج/٤) — مبلغُه **كما كتبته الخلفية** (`fare_lines`)، و`null` حين لا سطر: سوقٌ مطفأ،
 *  أو فرقٌ صفريّ، أو رحلةٌ لم تنتهِ. **وهو للكبتن أو عليه** (قرارُ المالك ٢٠٢٦-١٠-٠٩): موجبٌ زاد ما قبضه، وسالبٌ نقصه — فالإشارةُ
 *  تُرسم محرفَ طرحٍ (`−`) كما يرسمها تطبيقُ الراكب، **ولا حسابَ هنا**: تبديلُ خاناتٍ ومحرفٍ لا غير. */
export function roundingLine(ride: Pick<Ride, "fare_lines">): string | null {
  // **و`?.` لرحلةٍ محفوظةٍ من نسخةٍ أقدم** — تمثيلٌ بلا الحقل لا يُسقط شاشةَ المال، يُقرأ «لا سطر»
  const line = ride.fare_lines?.find((entry) => entry.kind === "rounding");
  if (!line) return null;
  const negative = line.amount.trimStart().startsWith("-");
  return `${negative ? "−" : ""}${digits(line.amount.replace("-", "").trim())}`;
}

/** المسافة بمنزلةٍ واحدة: `5.700` تُقرأ مبلغاً و`5.7` تُقرأ مسافة.
 *
 * وقصٌّ نصّي لا قسمةٌ ولا `toFixed`: لا رقمَ من الخلفية يمر بـ`Number`. */
export function trimDistance(value: string): string {
  const [whole, fraction = ""] = value.split(".");
  const first = fraction.slice(0, 1);
  return digits(first && first !== "0" ? `${whole}.${first}` : whole);
}


/** وقتُ حجزٍ كما يقرؤه الكبتن: ساعةٌ ودقيقةٌ بأرقامٍ عربية، ويومٌ إن لم يكن اليوم.
 *
 * **والأرقامُ عربيةٌ هنا لأنها كمّية لا معرِّف** (قاعدةُ `Cards.tsx`): الساعةُ
 * تُقرأ ولا تُطابق حرفاً بحرفٍ كلوحةٍ أو مرجعِ حوالة.
 */
export function bookedTime(iso: string): string {
  const date = new Date(iso);
  const time = digits(date.toLocaleTimeString(DISPLAY_LOCALE, {
    hour: "2-digit",
    minute: "2-digit",
  }));
  const sameDay = new Date().toDateString() === date.toDateString();
  if (sameDay) return time;
  const day = digits(date.toLocaleDateString(DISPLAY_LOCALE, { weekday: "long" }));
  return `${day} ${time}`;
}
