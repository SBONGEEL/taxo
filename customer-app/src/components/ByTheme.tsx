import type { ReactNode } from "react";

import { useTheme } from "@/lib/theme";

/** **المظهرُ المرسومُ أوّلاً** (§61-ب): لوحةُ الراكب نهاريّةٌ وحدَها حتى يُرسم الليليّ — فالشاشةُ
 *  الجديدةُ في النهاريّ، **والقائمةُ في الليليّ كما هي** حتى يُرسم. لا يُفقد شيءٌ ولا يُخترع.
 *
 *  **بيتٌ واحدٌ للقاعدة** — يقرؤه الموجّهُ (`App.tsx`) لشاشاتٍ كاملة، **والرئيسيةُ لأجزائها**: صفحتُها
 *  وأوراقُها تتبدّل بالمظهر وخريطتُها واحدة (`screens/Home.tsx`). */
export function ByTheme({ day, night }: { day: ReactNode; night: ReactNode }) {
  const { dark } = useTheme();
  return <>{dark ? night : day}</>;
}
