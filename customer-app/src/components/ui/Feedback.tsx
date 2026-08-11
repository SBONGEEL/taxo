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
        "flex items-start gap-8 rounded-12 border border-danger bg-surface-2 px-12 py-10 text-14 text-danger",
        className,
      )}
    >
      <AlertTriangle className="mt-2 size-16 shrink-0" />
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
        "flex items-start gap-8 rounded-12 border border-ok bg-surface-2 px-12 py-10 text-14 text-ok",
        className,
      )}
    >
      <CheckCircle2 className="mt-2 size-16 shrink-0" />
      <span>{message}</span>
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-8 py-32 text-muted">
      <Loader2 className="size-20 animate-spin" />
      {label ? <span className="text-14">{label}</span> : null}
    </div>
  );
}

export function EmptyState({ title, hint }: { title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center gap-8 py-48 text-center">
      <Inbox className="size-32 text-muted" />
      <p className="font-medium text-ink">{title}</p>
      {hint ? <p className="text-14 text-muted">{hint}</p> : null}
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
    neutral: "bg-surface-2 text-muted",
    success: "bg-surface-2 text-ok",
    warning: "bg-brand-soft text-ink",
    danger: "bg-surface-2 text-danger",
  } as const;
  return (
    <span className={cn("rounded-full px-10 py-4 text-12 font-medium", tones[tone])}>
      {children}
    </span>
  );
}
