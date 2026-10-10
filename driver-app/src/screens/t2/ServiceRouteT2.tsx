/** **بلاطةُ خدمةٍ تفتح ما يفعله الكبتنُ بها** (أمرُ المالك ٢٠٢٦-١٠-١٠، SPEC §٧٢) — `/services/<خدمة>` عنوانٌ واحدٌ في التطبيقين، وكلٌّ يفتح شاشتَه.
 *
 * - **المطار** ⇐ الإعدادات: مفتاحُ «طلبات المطار» هناك (بشرط سوقه).
 * - **الطرد** ⇐ «الطرود»: كيف تصل، وما سلّمه منها.
 * - **الرحلاتُ بموعد** ⇐ «الحجز المضمون»: عروضُ الحجوز في فئة مركبته.
 * - **بين المدن** ⇐ رحلاتُه التي يعلنها.
 * - **العروض** ⇐ خططُ الاشتراك وعروضُها.
 *
 * **وحالُ البلاطة من مفتاح السوق في الخلفية** (`storefront.tiles_for`): مطفأةٌ تُرسم «قريباً» ولا تُنقر، فلا يصل أحدٌ إلى هنا لخدمةٍ مطفأة
 * إلا بعنوانٍ يكتبه بيده — **فيقع على الشاشة نفسِها وهي تقول حالَها**. وخدمةٌ لا يعرفها التطبيقُ تعود إلى «خدماتك».
 */

import { Navigate, useParams } from "react-router-dom";

import { ParcelsT2Screen } from "./ParcelsT2";

/** **المقاصدُ المبنيّة** — ومرآتُها في الخلفية `storefront.SERVICE_ROUTES` (أدوارُ الكبتن). */
export const DRIVER_SERVICE_TARGETS: Record<string, string> = {
  airport: "/account/settings",
  bookings: "/guarantees",
  intercity: "/intercity",
  offers: "/subscription/plans",
};

export function ServiceRouteT2() {
  const { service = "" } = useParams();
  if (service === "parcel") return <ParcelsT2Screen />;
  return <Navigate to={DRIVER_SERVICE_TARGETS[service] ?? "/services"} replace />;
}
