/** **وصلُ طبقة المحادثة والمكالمة بتطبيق الكبتن** (SPEC §٦٦) — ما يخصّ الكبتنَ وحدَه، والطبقةُ نفسُها في `lib/comms.tsx`.
 *
 * - **الطرفُ الآخر «الراكب» وحدَه** — لا اسمَ ولا صورة (§٦١-ز: «لا يرى الكبتنُ اسمَ الراكب»)، فلا `peer`: الطبقةُ ترسم الكلمة.
 * - **والمقبسُ مقبسُ الاستقبال** (`online`) — **وبلاه لا مكالمة**: الإشارةُ تصل منه وحدَه، وفتحُه يعني «ابدأ الاستقبال» فلا
 *   يُفتح من هنا. **والمحادثةُ تعمل بلاه** (REST)، وتُسأل كلَّ خمس ثوانٍ وهي مفتوحة.
 * - **والبلاغُ الصغيرُ بلاغُ التطبيق بصوته** (`presentNotice`) — وفيه `firstSighting`: إشعارُ «مكالمةٌ فائتة» على المقبس لا يُرسم
 *   ثانيةً بعد أن قالتها الطبقة.
 * - **ونقرةُ الإشعار** في `PushRouter` (`App.tsx`) — تسأل `routeCommsPush` قبل وجهتها العامّة.
 */

import { useCallback } from "react";
import type { ReactNode } from "react";

import { presentNotice } from "@/components/PushNotices";
import { CommsProvider } from "@/lib/comms";
import { useRide } from "@/lib/ride";
import { CommsLayerT2 } from "@/screens/t2/CommsT2";

export function RideComms({ children }: { children: ReactNode }) {
  const { ride, online } = useRide();
  const toast = useCallback((title: string, body?: string) => presentNotice({ title, body }), []);
  return (
    <CommsProvider side="driver" ride={ride} peer={null} live={online} toast={toast}>
      {children}
      <CommsLayerT2 />
    </CommsProvider>
  );
}
