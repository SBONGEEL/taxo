/** **بلاطةُ خدمةٍ تفتح ما يفعله الراكبُ بها** (أمرُ المالك ٢٠٢٦-١٠-١٠، SPEC §٧٢) — `/services/<خدمة>` عنوانٌ واحدٌ في التطبيقين، وكلٌّ يفتح شاشتَه.
 *
 * - **المطار · الطرد · بالساعة · «أحضر غرضي»** ⇐ الرئيسيةُ تبدأ طلبَها كما تبدؤه بلاطتُها (`state.start` في `Home.tsx`) — **وبشرطها نفسِه**: مفتاحُ
 *   السوق؛ ومطفأً تُفتح الرئيسيةُ ولا يبدأ شيء.
 * - **الرحلاتُ بموعد** ⇐ حجوزي · **بين المدن** ⇐ مقاعدي.
 *
 * **ومرآتُها في الخلفية** `storefront.SERVICE_ROUTES` (أدوارُ الراكب) — وخدمةٌ لا يعرفها التطبيقُ تعود إلى الرئيسية.
 */

import { Navigate, useParams } from "react-router-dom";

import { useFeature } from "@/lib/config";
import { useSession } from "@/lib/session";

export const RIDER_SERVICE_TARGETS: Record<string, string> = {
  bookings: "/account/bookings",
  intercity: "/account/intercity",
};

/** **ما يبدأ من الرئيسية** — ومفتاحُه في السوق. */
export const RIDER_SERVICE_STARTS: Record<string, string> = {
  airport: "airport_enabled",
  parcel: "parcel_enabled",
  hourly: "hourly_enabled",
  // **«أحضر غرضي»** (§٧٢-ج/١) — بلاطةُ «أغراضي» تبدؤه
  fetch: "parcel_fetch_enabled",
};

export function ServiceRouteT2() {
  const { service = "" } = useParams();
  const { user } = useSession();
  const flag = RIDER_SERVICE_STARTS[service];
  const on = useFeature(user?.country_code, flag ?? "");
  if (flag) return <Navigate to="/" replace state={on ? { start: service } : undefined} />;
  return <Navigate to={RIDER_SERVICE_TARGETS[service] ?? "/"} replace />;
}
