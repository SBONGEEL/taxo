/** الأزرار — بقيم `design/DESIGN.md` §2.1 حرفاً بحرف.
 *
 * أربعة أنواعٍ لا خامس لها في التصميم: أساسيٌّ بتعبئة `--acc`، وثانويٌّ
 * محدَّد، وخطرٌ أحمر، ونصّيٌّ بلا إطار. وكلُّ زرٍّ أساسي **بعرضٍ كامل
 * وتوسيطِ نص**؛ وزرّان جنباً إلى جنب يُقسمان بـ`flex` لا بعرضٍ ثابت.
 *
 * ولا حالةَ تركيزٍ مرسومة في التصميم، فالحلقةُ هنا أخفُّ ما يفي بالوصول
 * (`ring-ink/40`) بلا إدخال لونٍ ليس في اللوحة.
 */

import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "danger" | "ghost";
type Size = "lg" | "md" | "sm";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  children: ReactNode;
}

const VARIANTS: Record<Variant, string> = {
  primary: "bg-brand text-brand-ink font-bold",
  secondary: "border border-line text-ink font-semibold",
  danger: "bg-danger text-white font-bold",
  ghost: "text-muted font-semibold",
};

// المقاسات الثلاثة من §2.1: (نصف القطر، الحشوة، مقاس الخط).
// **ونصفُ القطر نُعِّم في §10.3 (2026-08-13)**: ١٤ · ١٦ · ١٨ — سلّمٌ واحدٌ
// في التطبيقين، فالزرُّ الصغيرُ هنا أخو الصغيرِ هناك.
// الحشوة متساويةُ الجوانب كما في التصميم (`padding:16px` لا `16px 24px`)
const SIZES: Record<Size, string> = {
  lg: "rounded-18 p-16 text-15",
  md: "rounded-16 p-15 text-15",
  sm: "rounded-14 p-13 text-13.5",
};

export function Button({
  variant = "primary",
  size = "lg",
  loading = false,
  disabled,
  className,
  children,
  ...rest
}: Props) {
  return (
    <button
      type="button"
      disabled={disabled || loading}
      className={cn(
        "w-full text-center transition-opacity",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ink/40",
        "disabled:opacity-50",
        SIZES[size],
        VARIANTS[variant],
        className,
      )}
      {...rest}
    >
      {loading ? "…" : children}
    </button>
  );
}
