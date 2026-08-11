import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { Loader2 } from "lucide-react";
import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const button = cva(
  "inline-flex items-center justify-center gap-8 rounded-12 font-semibold " +
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
        sm: "h-36 px-12 text-14",
        md: "h-44 px-16 text-16",
        lg: "h-54 px-24 text-18 w-full",
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
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        className={cn(button({ variant, size }), className)}
        disabled={disabled || loading}
        {...props}
      >
        {loading ? <Loader2 className="size-20 animate-spin" /> : null}
        {children}
      </Comp>
    );
  },
);
Button.displayName = "Button";
