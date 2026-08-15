import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const button = cva(
  "inline-flex items-center justify-center gap-8 font-semibold " +
    "transition active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50 " +
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand",
  {
    variants: {
      variant: {
        primary: "bg-brand text-brand-ink hover:brightness-95",
        secondary: "bg-surface text-ink border border-line hover:bg-surface-2",
        ghost: "text-ink hover:bg-surface-2",
        danger: "bg-danger text-white hover:brightness-95",
      },
      size: {
        // نصفُ القطر يتبع المقاس (§10.3) — سلّمٌ واحدٌ في التطبيقين
        sm: "h-36 rounded-14 px-12 text-14",
        md: "h-44 rounded-16 px-16 text-16",
        lg: "h-54 w-full rounded-18 px-24 text-18",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof button> {
  asChild?: boolean;
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild, loading, children, disabled, ...props }, ref) => {
    // **`Slot` يقبل ابناً واحداً بالضبط** — و`React.Children.only` يعدّ
    // `{null}` ابناً. فسطرُ التحميل بجانب `children` يجعلهما اثنين، فيرمي
    // Radix استثناءً **غيرَ ملتقَط** (لا حدودَ خطأٍ في هذا التطبيق) ⇒ **شاشةٌ
    // بيضاء**. وكان يقع على شاشتين ماليّتين: الدفعُ بكليك وشحنُ المحفظة.
    //
    // **ولا سطرَ تحميلٍ مع `asChild` أصلاً**: الابنُ رابطٌ يفتح تطبيقَ البنك،
    // ولا حالةَ «جارٍ» له — فالحذفُ هنا ليس تنازلاً عن ميزة.
    if (asChild) {
      return (
        <Slot
          ref={ref}
          className={cn(button({ variant, size }), className)}
          {...props}
        >
          {children}
        </Slot>
      );
    }

    return (
      <button
        ref={ref}
        className={cn(button({ variant, size }), className)}
        disabled={disabled || loading}
        {...props}
      >
        {loading ? <Loader2 className="size-20 animate-spin" /> : null}
        {children}
      </button>
    );
  },
);
Button.displayName = "Button";
