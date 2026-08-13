/** ترتيبُ الشاشات — منه يُعرف «تقدّمٌ» من «رجوع»، لا من نوع التنقّل وحدَه.
 *
 * `useNavigationType()` يعرف `POP` من `PUSH`، وهو صحيحٌ في نصف الحالات فقط:
 * شاشةٌ تعود إلى أبيها بـ`navigate("/account")` بعد حفظٍ تُقرأ **تقدّماً** وهي
 * رجوع، وتبويبٌ يُضغط من الشريط السفلي `PUSH` دائماً مهما كان موضعُه. فالنتيجةُ
 * انزلاقٌ يخالف ما يراه الإصبع — وهو أسوأُ من غياب الحركة: يقول «دخلتَ» حيث خرج.
 *
 * فالاتجاهُ يُقاس من **موضع المسار في التطبيق**: تبويبُه أولاً ثم عمقُه تحته.
 * والأعمقُ تقدّمٌ، والأضحلُ رجوع، والمتساويان يُحكَّم فيهما نوعُ التنقّل — وهي
 * الحالُ الوحيدة التي يعرفها السجلُّ وحدَه (رحلةٌ إلى أختها في القائمة نفسِها).
 *
 * **والترتيبُ مأخوذٌ من `TABS` نفسِها** لا من قائمةٍ ثانية: قائمتان لترتيبٍ واحد
 * تفترقان أوّلَ ما يُضاف تبويب — وهي القاعدةُ التي بُني عليها `BottomNav`.
 */

import { TABS } from "@/lib/tabs";

/** رتبةُ المسار: التبويبُ في المئات والعمقُ في الآحاد. */
export function routeRank(pathname: string): number {
  const tab = TABS.findIndex(
    (entry) => entry.to !== "/" && pathname.startsWith(entry.to),
  );
  const depth = pathname.split("/").filter(Boolean).length;
  return (tab === -1 ? 0 : tab) * 100 + depth;
}

/** `true` إن كان الانتقالُ رجوعاً — بالرتبة، وبالسجل حين تتساوى الرتبتان. */
export function isBackward(
  from: string,
  to: string,
  popped: boolean,
): boolean {
  const before = routeRank(from);
  const after = routeRank(to);
  if (after === before) return popped;
  return after < before;
}
