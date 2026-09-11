/** جولةُ أذوناتِ أوّل فتح — **خطوةٌ بعد خطوة، ومن السجلِّ الواحد**.
 *
 * **وترتيبُها ونصوصُها أقرّهما المالكُ نصّاً** (٢٠٢٦-٠٩-١١): الموقع، ثمّ
 * الإشعارات، ثمّ استثناءُ توفير الطاقة، ثمّ الرسمُ فوق التطبيقات — **والموقعُ
 * في الخلفية خارجَ التتابع تماماً**.
 *
 * ## ولمَ الموقعُ الخلفيُّ خارجَها — **شرطُ النظام والمتجر معاً**
 *
 * **أندرويد يمنع طلبَه في الحوار نفسِه**: لا يُطلب `ACCESS_BACKGROUND_LOCATION`
 * إلا بعد منح «أثناء الاستخدام»، **وفي أندرويد 11+ لا حوارَ له أصلاً** — يُفتح
 * إعدادُ النظام ويختار المستخدم «السماح طوال الوقت» بيده.
 *
 * **وPlay يشترط إفصاحاً بارزاً قبله**، بنصِّ الكونسول الذي قُرئ حرفاً
 * (٢٠٢٦-٠٩-١١): «يجب أن يتضمّن الفيديو الإفصاح البارز الذي يظهر للمستخدمين
 * **قبل** عرض الطلب الذي يُظهر وقت تشغيل التطبيق». **فالشاشةُ هنا هي الإفصاحُ
 * نفسُه**، لا مقدّمةٌ له — ونبني ما تطلبه المراجعةُ لا ما تردّه.
 *
 * ## والرفضُ مرّتين يبدّل الزرَّ ولا يُلاحِق (شرطُ المالك)
 *
 * **أندرويد يقفل الحوارَ بعد رفضين** ولا يعرضه ثالثةً مهما نُودي — **فزرٌّ
 * يقول «اسمح» بعدها يكذب**. فيصير «فتح الإعدادات»، **ولا تُفتح شاشةُ نظامٍ من
 * تلقائها أبداً**: من رفض يرى ويمضي، وملاحقتُه تجعله يطفئ التطبيقَ لا الإذن.
 *
 * **والعدُّ يُحفظ**: الرفضُ الأولُ في جلسةٍ والثاني في أخرى **رفضان** — وذاكرةٌ
 * تُمحى بإغلاق التطبيق تعيد عرضَ حوارٍ لا يفتحه النظام.
 */

import { Geolocation } from "@capacitor/geolocation";

import {
  openAppSettings,
  openOverlaySettings,
  type PermissionStatus,
} from "@/lib/offer-alert";
import { requestNotificationPermission } from "@/lib/push";

/** **ما يفعله زرُّ الخطوة** — حوارُ نظامٍ، أو فتحُ إعدادٍ لا حوارَ له. */
export type StepKind = "dialog" | "settings";

export interface WalkStep {
  key: string;
  /** **يُقرأ بالاسم الصريح لا بمفتاحٍ متغيّر** — الشكلُ السادسَ عشر. */
  read: (status: PermissionStatus) => boolean;
  title: string;
  /** **الأثرُ بعينه لا «التطبيق يحتاج هذا»** — ونصُّه من `permission-rows`. */
  body: string;
  kind: StepKind;
  /** نصُّ الزرِّ في حاله الأولى. */
  cta: string;
  request: () => Promise<void>;
}

/** **الأربعُ في تتابعها** — والموقعُ الخلفيُّ ليس منها بقصد. */
export const WALK: WalkStep[] = [
  {
    key: "location",
    read: (s) => s.location,
    title: "الموقع",
    body: "بغيره لا تصلك طلبات: التوزيع يبحث عن أقرب كبتن إلى نقطة الانطلاق.",
    kind: "dialog",
    cta: "اسمح بالموقع",
    request: async () => {
      await Geolocation.requestPermissions();
    },
  },
  {
    key: "notifications",
    read: (s) => s.notifications,
    title: "الإشعارات",
    body: "بغيرها لا تصلك بطاقة الطلب وأنت خارج التطبيق.",
    kind: "dialog",
    cta: "اسمح بالإشعارات",
    request: async () => {
      await requestNotificationPermission();
    },
  },
  {
    // **لا حوارَ له بلا نيّةٍ خاصّة** — ولا تُضاف نيّةٌ أصليّةٌ لأجل جولة.
    // **فالزرُّ يفتح الإعداد**، والنصُّ يقول ما ينكسر بغيره.
    key: "batteryUnrestricted",
    read: (s) => s.batteryUnrestricted,
    title: "استثناء من توفير الطاقة",
    body: "بغيره يوقف النظام خدمة الموقع بعد دقائق من إطفاء الشاشة — فتبدو متصلاً وأنت غائب.",
    kind: "settings",
    cta: "افتح الإعدادات",
    request: openAppSettings,
  },
  {
    key: "overlay",
    read: (s) => s.overlay,
    title: "الرسم فوق التطبيقات",
    body: "به تظهر بطاقة الطلب فوق أي شاشة وأنت تقود. وبدونه يظهر إشعار يملأ الشاشة بدلاً منها.",
    kind: "settings",
    cta: "افتح الإعدادات",
    request: openOverlaySettings,
  },
];

/** **الإفصاحُ البارز** — شاشةٌ قائمةٌ بذاتها بعد التتابع، ولا تُعرض قبل منح
 *  الموقع العادي. ونصُّها هو ما يُصوَّر في فيديو Play. */
export const BACKGROUND_STEP: WalkStep = {
  key: "backgroundLocation",
  read: (s) => s.backgroundLocation,
  title: "TAXO يحتاج موقعك طوال الوقت",
  body:
    "حين تضغط «استقبال»، يبثّ TAXO موقعك إلى خادمنا والشاشة مطفأة — ليُعرض " +
    "عليك أقرب طلب، وليرى راكبك سيارتك على الخريطة حتى نهاية الرحلة. " +
    "ويتوقّف فور ضغطك «إيقاف الاستقبال».",
  kind: "settings",
  cta: "افتح الإعدادات واختر «السماح طوال الوقت»",
  request: openAppSettings,
};

//: **العدُّ يُحفظ ولا يُنسى بإغلاق التطبيق** — انظر ترويسة الملفّ.
const REFUSALS_KEY = "taxo.driver.permission.refusals";
const DONE_KEY = "taxo.driver.permission.walk.done";

export function refusalsOf(key: string): number {
  try {
    const raw = JSON.parse(localStorage.getItem(REFUSALS_KEY) ?? "{}") as Record<string, number>;
    return raw[key] ?? 0;
  } catch {
    return 0;
  }
}

export function noteRefusal(key: string): number {
  try {
    const raw = JSON.parse(localStorage.getItem(REFUSALS_KEY) ?? "{}") as Record<string, number>;
    const next = (raw[key] ?? 0) + 1;
    localStorage.setItem(REFUSALS_KEY, JSON.stringify({ ...raw, [key]: next }));
    return next;
  } catch {
    return 1;
  }
}

/** **حدُّ النظام: رفضان ثمّ لا حوار.** */
export const REFUSAL_LIMIT = 2;

export function walkDone(): boolean {
  try {
    return localStorage.getItem(DONE_KEY) === "1";
  } catch {
    return false;
  }
}

export function markWalkDone(): void {
  try {
    localStorage.setItem(DONE_KEY, "1");
  } catch {
    /* تخزينٌ ممنوعٌ لا يوقف الجولة — تُعرض مرّةً أخرى، ولا تنكسر شاشة */
  }
}
