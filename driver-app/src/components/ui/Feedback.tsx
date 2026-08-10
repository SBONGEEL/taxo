/** رسائل الحال: خطأ، نجاح، وانتظار.
 *
 * **نصُّ الخطأ هو ما قالته الخلفية** (`{code, message}` بالعربية) — لا
 * تخترع الواجهة عبارةً لخطأٍ سُمّي أصلاً. وشكلُها من `DESIGN.md` §2.2:
 * بطاقةٌ بحدٍّ بلون الحالة وخلفية `--sur2`، بمقاس 12.5 وسطرٍ 1.7.
 */

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

function Note({
  message,
  tone,
}: {
  message: string | null | undefined;
  tone: "danger" | "ok" | "warn";
}) {
  if (!message) return null;
  const color = { danger: "border-danger text-danger", ok: "border-ok text-ok", warn: "border-warn text-warn" }[
    tone
  ];
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={cn(
        "rounded-12 border bg-surface-2 px-13 py-11 text-12.5 leading-note",
        color,
      )}
    >
      {message}
    </div>
  );
}

export const ErrorNote = ({ message }: { message: string | null | undefined }) => (
  <Note message={message} tone="danger" />
);

export const SuccessNote = ({ message }: { message: string | null | undefined }) => (
  <Note message={message} tone="ok" />
);

/** مؤشّرُ الانتظار من §2.10: حلقةٌ 34×34 بحدٍّ `--brd` وقمّةٍ `--tx`. */
export function Spinner({ className }: { className?: string }) {
  return (
    <span
      aria-label="جارٍ التحميل"
      role="status"
      className={cn(
        "block size-34 animate-spin rounded-full border-2 border-line border-t-ink",
        className,
      )}
    />
  );
}

export function CenteredMessage({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-16 px-28 text-center">
      {children}
    </div>
  );
}
