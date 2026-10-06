/** الأزرار — **بلغة TAXO 2.0** («المكوّنات الأساسية» في الهوية): أساسيٌّ وثانويٌّ بحافّة، وخطرٌ، ونصّيّ.
 *
 * **والأساسيُّ يتبع المظهر كما في الهوية**: حبرٌ على الحجر، **وجمرٌ على الإسفلت** (§٦٢-ب/٧ — «الحبرُ على الداكن لا يُرى»)
 * — من `--acc` الذي يربطه `index.css` برمز المظهر. **والخطرُ بحافّته وخافتِه** لا بتعبئةٍ حمراء: الأبيضُ على أحمر الإسفلت دون
 * ٤٫٥:١، وزرٌّ يوقف حساباً أو يرفض مالاً **يُقرأ تحذيراً قبل أن يُقرأ أمراً**.
 *
 * **والمقاساتُ ثلاثة** (`lg` ٥٤ · `md` ٤٨ · `sm` ٤٠ — و٤٤ على الهاتف هدفَ لمسٍ كاملاً)، **وكلُّ زرٍّ بعرضٍ كاملٍ افتراضاً** كما كان،
 * والمستدعي يضيّقه بصنفه (`flex-1` · `w-auto`). **وأصنافُ المستدعي تغلب** (`border-danger text-danger`): ملفُّ الأصناف يُحمَّل
 * قبل أدوات Tailwind (`main.tsx`).
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
  primary: "ad-btn-primary",
  secondary: "ad-btn-secondary",
  danger: "ad-btn-danger",
  ghost: "ad-btn-ghost",
};

const SIZES: Record<Size, string> = {
  lg: "ad-btn-lg",
  md: "ad-btn-md",
  sm: "ad-btn-sm",
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
      className={cn("ad-btn", SIZES[size], VARIANTS[variant], className)}
      {...rest}
    >
      {loading ? "…" : children}
    </button>
  );
}
