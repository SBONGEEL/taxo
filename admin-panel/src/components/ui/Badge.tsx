/** الشارة — **`.t2-chip` من نظام التصميم** (حالٌ في كلمة): حبّةٌ بخلفيةِ معناها الخافتة ونصِّه.
 *
 * واللونُ يخصّ الحالةَ لا الشارة، فخريطةُ الحالات في الشاشة التي تعرفها وهذا المكوّن يأخذ **النغمة** لا الحالة: خمسُ نغمات،
 * وحالاتُ الرحلة والدفع والاشتراك والتدقيق تتقاسمها. **و`ink` نصٌّ كاملٌ على الغائر** — للأدوار والأوسام لا للأحوال.
 */

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export type Tone = "ok" | "warn" | "danger" | "muted" | "ink";

const TONES: Record<Tone, string> = {
  ok: "ok",
  warn: "warn",
  danger: "danger",
  muted: "",
  ink: "ink",
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
        // **`w-fit` في الصنف نفسِه** (`kit.css` — أُضيف 2026-09-07 بقياسٍ على الشاشة): ابنٌ مباشرٌ لشبكةٍ **يُمَطّ إلى عرض
        // العمود**، فتصير الشارةُ شريطاً ونصُّها في طرفه. **والعلاجُ في بيت الشارة لا في كلِّ موضع**: ٦٢ استعمالاً.
        "t2-chip ad-chip",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
