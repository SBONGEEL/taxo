/** **اللوحةُ عربيّةٌ وحدَها** (SPEC §٧٣-هـ المرحلة ٥، أمرُ المالك) — و`tr` هنا تعيد النصَّ العربيَّ كما هو.
 *
 * **ولمَ وُجدت إذن**: ملفّاتٌ منسوخةٌ بايتاً بين التطبيقات الثلاثة (نظامُ التصميم `src/taxo2/` وبوّابةُ التحديث — `check:taxo2` و`check:update-gate`)
 * **تنادي `tr`** في تطبيقَي الراكب والكبتن لتُترجم؛ فنسختُها هنا تناديها أيضاً، **والجوابُ هنا العربيّةُ حرفاً** — بالتوقيع نفسِه والاستبدالِ
 * نفسِه لـ`{0}` `{1}` كما في `customer-app/src/lib/i18n.ts`.
 */

export function tr(ar: string, vars?: Readonly<Record<string | number, unknown>>): string {
  if (!vars) return ar;
  return ar.replace(/\{(\w+)\}/g, (whole, key: string) => (key in vars ? String(vars[key]) : whole));
}
