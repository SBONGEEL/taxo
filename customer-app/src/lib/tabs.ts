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

/** الشاشاتُ التي **تغطّي** الشريطَ — والباقي يُظهره.
 *
 * **قائمةُ منعٍ لا قائمةُ سماح**، وهذا اختيارٌ في اتجاه الخطأ لا في عدده: من
 * يضيف صفحةً تحت «حسابي» وينسى تسجيلَها **يجدها بالشريط كأخواتها** — وهو
 * الصواب (القرار 53: صفحاتُ النموذج الداخلية كلُّها `inset:0 0 nav`). ولو كانت
 * قائمةَ سماحٍ لخرجت الصفحةُ الجديدة بلا شريطٍ بلا أن يخطئ أحد.
 *
 * والثلاثةُ الأولى قبل الدخول، و`pay`/`rate` **طبقتان تغطّيان الشاشة** بحكم
 * التصميم (`payShow`/`rateShow` — القرار 53 نفسُه)، وعودةُ البطاقة صفحةُ
 * انتظارٍ لا مكانَ فيها للتنقل.
 */
const COVERING = [
  "/login",
  "/register",
  "/forgot-password",
  "/payments/card/return",
];

/** هل يظهر الشريطُ على هذا المسار؟ */
export function showsNav(pathname: string): boolean {
  if (COVERING.some((path) => pathname.startsWith(path))) return false;
  // `/rides/:id/pay` و`/rides/:id/rate` — طبقتان لا صفحتان
  return !/^\/rides\/[^/]+\/(pay|rate)$/.test(pathname);
}
