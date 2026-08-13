/** تبويباتُ الشريط السفلي — **بيتٌ واحدٌ لها**.
 *
 * كانت مسطورةً في `BottomNav.tsx` وحدَه، ثم صار لها قارئٌ ثانٍ: اتجاهُ انتقال
 * الشاشات (`lib/nav-order.ts`) يُقاس بترتيب التبويب. وقائمتان لترتيبٍ واحد
 * تفترقان أوّلَ ما يُضاف تبويبٌ خامس — فتُضاء حبّةٌ في مكانٍ وينزلق الانتقالُ
 * إلى غيره.
 */

import { Clock, Home, User, Wallet } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface Tab {
  to: string;
  label: string;
  icon: LucideIcon;
}

export const TABS: Tab[] = [
  { to: "/", label: "الرئيسية", icon: Home },
  { to: "/rides", label: "رحلاتي", icon: Clock },
  { to: "/wallet", label: "المحفظة", icon: Wallet },
  { to: "/account", label: "حسابي", icon: User },
];
