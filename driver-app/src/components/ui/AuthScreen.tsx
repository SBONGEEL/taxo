/** قشرةُ شاشات ما قبل الدخول — `design/DESIGN.md` §1.4.
 *
 * حشوةُ التصميم `30px 28px` (والدخول `30px 28px 24px`)، والحركة
 * `fadein .3s`، وسهمُ الرجوع `→` في العربية بمقاس 18 ولون `--mut`.
 *
 * **وشريطُ الحالة (9:41 والبطارية) ليس هنا**: إطارُ عرضٍ في لوحة التصميم لا
 * جزءٌ من التطبيق (`DESIGN-DECISIONS.md` §رابعاً). ويحلّ محلّه `pt-safe`
 * فتنزل الشاشة تحت نتوء الهاتف الحقيقي.
 */

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface Props {
  onBack?: () => void;
  children: ReactNode;
  className?: string;
}

export function AuthScreen({ onBack, children, className }: Props) {
  return (
    <div
      className={cn(
        // حشوةُ التصميم `30px 28px 24px`؛ والعلويةُ تنزل تحت نتوء الهاتف حين
        // يكون أعمق من 30px — ولا تصغر عنها أبداً
        "scr flex h-full animate-fadein-slow flex-col px-28 pb-24",
        "pt-[max(30px,env(safe-area-inset-top))]",
        className,
      )}
    >
      {onBack ? (
        <button
          type="button"
          onClick={onBack}
          aria-label="رجوع"
          className="w-fit text-18 text-muted"
        >
          →
        </button>
      ) : null}
      {children}
    </div>
  );
}
