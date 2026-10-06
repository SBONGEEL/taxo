/** رسائل الحال: خطأ، نجاح، وانتظار — **بلغة TAXO 2.0**.
 *
 * **نصُّ الخطأ هو ما قالته الخلفية** (`{code, message}` بالعربية) — لا تخترع الواجهة عبارةً لخطأٍ سُمّي أصلاً. وشكلُها بلاغُ
 * الهوية (`.t2-callout`): أيقونةُ معناه ممتلئةً ونصٌّ على خافتِ لونه — **سطرٌ يُقرأ لا لونٌ يُلمح**.
 */

import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import { Icon } from "@/taxo2";

function Note({
  message,
  tone,
}: {
  message: string | null | undefined;
  tone: "danger" | "ok" | "warn";
}) {
  if (!message) return null;
  const icon = { danger: "error", ok: "check_circle", warn: "warning" }[tone];
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={cn("ad-note", tone)}
    >
      <Icon name={icon} fill />
      <span>{message}</span>
    </div>
  );
}

export const ErrorNote = ({
  message,
}: {
  message: string | null | undefined;
}) => <Note message={message} tone="danger" />;

export const SuccessNote = ({
  message,
}: {
  message: string | null | undefined;
}) => <Note message={message} tone="ok" />;

/** مؤشّرُ الانتظار: حلقةٌ بحافّةٍ خافتةٍ وقمّةٍ بالجمر — **وتقف لمن طلب تقليلَ الحركة** (`kit.css`). */
export function Spinner({ className }: { className?: string }) {
  return (
    <span
      aria-label="جارٍ التحميل"
      role="status"
      className={cn("ad-spin", className)}
    />
  );
}

/** لا شيء بعد — وليس عطلاً. عنوانٌ وسطرُ سببٍ، بلا رسمٍ ولا زرّ: القوائم
 * الفارغة في هذا التطبيق تمتلئ بالعمل لا بضغطة. */
export function EmptyNote({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="ad-empty">
      <p className="ad-empty-title">{title}</p>
      <p className="ad-empty-hint">{hint}</p>
    </div>
  );
}

export function CenteredMessage({ children }: { children: ReactNode }) {
  return <div className="ad-centered">{children}</div>;
}
