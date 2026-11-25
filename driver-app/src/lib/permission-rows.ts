/** سجلُّ أذونات الكبتن — **بيتٌ واحدٌ لشاشة الأذونات ولتحذير الرئيسية**.
 *
 * **ولمَ نُقل من `screens/Permissions.tsx` ولم يُنسخ** (2026-09-11): صار
 * للأذونات قارئان — الشاشةُ التي يفتحها الكبتنُ باحثاً، **والتحذيرُ الذي
 * يراه في الرئيسية بلا أن يبحث**. ونسختان من الجدول تفترقان: يُصنَّف إذنٌ
 * مانعاً في موضعٍ وناصحاً في الآخر، **فيقرأ الكبتنُ حكمين لحالٍ واحدة**.
 * وهو «بابان ينشران الشيءَ نفسَه ويفترقان» بعينه.
 *
 * **والنصُّ هنا هو النصُّ المعروض** — لا يُعاد صوغُه في أيِّ سطح.
 */

import {
  openAppSettings,
  openFullScreenSettings,
  openOverlaySettings,
  type PermissionStatus,
} from "@/lib/offer-alert"; import { tr } from "@/lib/i18n";
import { centerAvailable, openPermission, type PermissionKey } from "@/lib/permissions-center";

/** **الصفحةُ الدقيقةُ إن حملها الغلاف** (SPEC §١٠٣/٢٨): ملحقُ `Permissions` يفتح صفحةَ الإشعارات أو البطارية نفسَها،
 *  **والغلافُ الأقدمُ يبقى على تفاصيل التطبيق** كما كان — لا يتغيّر عليه حرف. */
function exact(key: PermissionKey, fallback: () => Promise<void>): () => Promise<void> {
  return async () => {
    if (centerAvailable() && (await openPermission(key)) !== "none") return;
    await fallback();
  };
}

/** **مفتاحُ كلِّ صفٍّ في البلاغ** — بأسماء مركز الأذونات التي تقبلها الخلفية (`PERMISSION_KEYS`) */
export const REPORT_KEY: Record<string, PermissionKey> = {
  location: "location",
  notifications: "notifications",
  offerChannel: "notifications",
  backgroundLocation: "location_background",
  batteryUnrestricted: "battery",
  overlay: "overlay",
  fullScreenIntent: "full_screen",
};

export type Severity = "blocking" | "advisory";

export interface Row {
  key: string;
  /** **قراءةٌ بالاسم الصريح لا بمفتاحٍ متغيّر** — فحقلٌ يُحذف من العقد
   *  يُسقط `tsc` هنا، **ودليلٌ يقرأ بالفهرسة يمرّ عليه صامتاً**. وهو
   *  الشكلُ السادسَ عشر المسجَّل في `PATTERNS.md` بعينه. */
  read: (status: PermissionStatus) => boolean;
  label: string;
  /** **ما ينكسر بغيابه بعينه** — لا «التطبيق يحتاج هذا». */
  why: string;
  severity: Severity;
  open?: () => Promise<void>;
}

export const ROWS: Row[] = [
  {
    key: "location",
    read: (status) => status.location,
    label: tr("الموقع"),
    why: tr("بغيره لا تصلك طلبات: التوزيع يبحث عن أقرب كابتن إلى نقطة الانطلاق."),
    severity: "blocking",
    open: exact("location", openAppSettings),
  },
  {
    key: "notifications",
    read: (status) => status.notifications,
    label: tr("الإشعارات"),
    why: tr("بغيرها لا تصلك بطاقة الطلب وأنت خارج التطبيق."),
    severity: "blocking",
    open: exact("notifications", openAppSettings),
  },
  {
    key: "offerChannel",
    read: (status) => status.offerChannel,
    label: tr("قناة «طلبات الرحلات»"),
    why: tr("قناة الطلبات وحدها قد تكون مطفأة والإشعارات مفتوحة — فيصمت الطلب بلا سبب ظاهر."),
    severity: "blocking",
    open: exact("notifications", openAppSettings),
  },
  {
    key: "backgroundLocation",
    read: (status) => status.backgroundLocation,
    label: tr("الموقع في الخلفية"),
    why: tr("بغيره يتوقف بثّ موقعك حين تغلق التطبيق، فتخرج من التوزيع وأنت تعمل."),
    severity: "blocking",
    open: exact("location_background", openAppSettings),
  },
  {
    key: "batteryUnrestricted",
    read: (status) => status.batteryUnrestricted,
    label: tr("استثناء من توفير الطاقة"),
    why: tr("بغيره يوقف النظام خدمة الموقع بعد دقائق من إطفاء الشاشة — فتبدو متصلاً وأنت غائب."),
    severity: "blocking",
    open: exact("battery", openAppSettings),
  },
  {
    key: "overlay",
    read: (status) => status.overlay,
    label: tr("الرسم فوق التطبيقات"),
    why: tr("به تظهر بطاقة الطلب فوق أي شاشة وأنت تقود. وبدونه يظهر إشعار يملأ الشاشة بدلاً منها."),
    severity: "advisory",
    open: exact("overlay", openOverlaySettings),
  },
  {
    key: "fullScreenIntent",
    read: (status) => status.fullScreenIntent,
    label: tr("إشعار يملأ الشاشة"),
    why: tr("هو الطريق البديل حين لا تُمنح النافذة العائمة. وأندرويد الحديث ينزعه تلقائياً عن غير تطبيقات المكالمات، فيُمنح باليد."),
    severity: "advisory",
    open: exact("full_screen", openFullScreenSettings),
  },
];
