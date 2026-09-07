/** الشارة — `DESIGN.md` §2.6: قاعدةٌ واحدة تولّد كل شارات اللوحة.
 *
 * `padding:4px 10px; border-radius:99px; font-size:11px; font-weight:600;`
 * واللونُ يخصّ الحالةَ لا الشارة، فخريطةُ الحالات في الشاشة التي تعرفها
 * وهذا المكوّن يأخذ **النغمة** لا الحالة: خمسُ نغماتٍ في التصميم، وحالاتُ
 * الرحلة والدفع والاشتراك والتدقيق تتقاسمها.
 *
 * **والحدُّ بلونٍ كاملٍ لا بسدس شفافيةٍ كما يكتب التصميم** (`<اللون>33`):
 * اللوحةُ hex في متغيّر CSS، و`border-ok/20` لا يعمل عليها إطلاقاً (نفس ما
 * تصفه `CLAUDE.md` عن `bg-brand/40`). وهو ما تفعله `Feedback.tsx` منذ أول
 * شاشة، فالانحرافُ متسقٌ مع نفسه لا جديدٌ هنا.
 */

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export type Tone = "ok" | "warn" | "danger" | "muted" | "ink";

const TONES: Record<Tone, string> = {
  ok: "border-ok text-ok",
  warn: "border-warn text-warn",
  danger: "border-danger text-danger",
  muted: "border-line text-muted",
  ink: "border-line text-ink",
};

export function Badge({
  tone = "muted",
  children,
  className,
}: {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        // **`w-fit` لا `inline-block` وحدَه** (أُضيف 2026-09-07 بقياسٍ على
        // الشاشة): ابنٌ مباشرٌ لشبكةٍ **يُمَطّ إلى عرض العمود**، فتصير
        // الشارةُ شريطاً ونصُّها في طرفه. رُئي في شاشة الدفعات — والشارةُ
        // نفسُها في سجلّ الرحلات منكمشةٌ لأنها هناك داخل حاوية `flex`.
        //
        // **والعلاجُ في بيت الشارة لا في كلِّ موضع**: ٦٢ استعمالاً في اثني
        // عشر ملفّاً، **وإصلاحُ موضعٍ يترك أحدَ عشرَ يجدها غداً**.
        "inline-block w-fit rounded-full border bg-surface-2 px-10 py-4 text-11 font-semibold",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
