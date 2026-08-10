/** هيكل الشاشات غير الخريطية: عنوانٌ ورجوعٌ ومحتوى يتمرّر.
 *
 * السهم `ChevronRight` لا `ChevronLeft`: في واجهةٍ عربية «رجوع» يشير يميناً.
 */

import { ChevronRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Screen({
  title,
  back = true,
  action,
  children,
  className,
}: {
  title: string;
  back?: boolean | string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const navigate = useNavigate();

  return (
    <div className="flex h-full flex-col bg-bg">
      <header className="sticky top-0 z-10 flex items-center gap-2 border-b border-line bg-surface/95 px-3 pb-3 pt-safe backdrop-blur">
        {back ? (
          <button
            type="button"
            onClick={() => (typeof back === "string" ? navigate(back) : navigate(-1))}
            className="rounded-full p-2 text-ink transition hover:bg-line/50"
            aria-label="رجوع"
          >
            <ChevronRight className="size-5" />
          </button>
        ) : (
          <span className="w-2" />
        )}
        <h1 className="flex-1 truncate text-lg font-semibold text-ink">{title}</h1>
        {action}
      </header>

      <main className={cn("flex-1 overflow-y-auto px-4 py-4 pb-safe", className)}>
        {children}
      </main>
    </div>
  );
}
