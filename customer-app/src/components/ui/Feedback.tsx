/** رسائل الحالة: خطأٌ، ونجاحٌ، وفراغٌ، وانتظار.
 *
 * **نصّ الخطأ يأتي من الخلفية كما هو** (`{code, message}` عربيةٌ جاهزة —
 * `core/exceptions.py`). الواجهة لا تترجم ولا تُعيد الصياغة: رسالتان لخطأٍ
 * واحد تختلفان بين شاشتين تُربكان من يقرأ الاثنتين.
 */

import { AlertTriangle, CheckCircle2, Inbox, Loader2 } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function ErrorNote({
  message,
  className,
}: {
  message?: string | null;
  className?: string;
}) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-2 rounded-xl border border-danger/40 bg-danger/10 px-3 py-2.5 text-sm text-danger",
        className,
      )}
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0" />
      <span>{message}</span>
    </div>
  );
}

export function SuccessNote({
  message,
  className,
}: {
  message?: string | null;
  className?: string;
}) {
  if (!message) return null;
  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-xl border border-success/40 bg-success/10 px-3 py-2.5 text-sm text-success",
        className,
      )}
    >
      <CheckCircle2 className="mt-0.5 size-4 shrink-0" />
      <span>{message}</span>
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-8 text-muted">
      <Loader2 className="size-5 animate-spin" />
      {label ? <span className="text-sm">{label}</span> : null}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center gap-2 py-12 text-center">
      <Inbox className="size-8 text-muted" />
      <p className="font-medium text-ink">{title}</p>
      {hint ? <p className="text-sm text-muted">{hint}</p> : null}
    </div>
  );
}

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "success" | "warning" | "danger";
}) {
  const tones = {
    neutral: "bg-line/60 text-muted",
    success: "bg-success/15 text-success",
    warning: "bg-brand/20 text-ink",
    danger: "bg-danger/15 text-danger",
  } as const;
  return (
    <span className={cn("rounded-full px-2.5 py-1 text-xs font-medium", tones[tone])}>
      {children}
    </span>
  );
}
