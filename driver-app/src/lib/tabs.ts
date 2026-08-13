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
  { to: "/rides", label: "الرحلات", icon: Clock },
  { to: "/wallet", label: "المحفظة", icon: Wallet },
  { to: "/account", label: "حسابي", icon: User },
];

/** الشاشاتُ التي تُظهر الشريط — **قائمةُ سماحٍ هنا لا منع**، على عكس تطبيق
 * الراكب، وليس هذا تناقضاً بل فرقاً في النموذجين: صفحاتُ الكبتن الداخلية
 * (السحب، الأرباح، المركبة، البطاقات، الإحالة، النزاع) **تغطّي الشاشة** كلَّها
 * في تصميمه، بينما صفحاتُ الراكب الداخلية تُبقيه (القرار 53). فالافتراضُ في كلٍّ
 * منهما هو ما يقوله نموذجُه، والقائمةُ تصف الفرقَ بدل أن تخفيه.
 */
const WITH_NAV = ["/", "/rides", "/wallet", "/account", "/subscription"];

export function showsNav(pathname: string): boolean {
  return WITH_NAV.includes(pathname);
}
