/** **قطعٌ صغيرةٌ تتكرّر في شاشات «حسابي» الداخلية وأوراق الطلب** (R22–R29) — عرضٌ وحدَه، بأصناف `taxo2` و`kit.css`.
 *
 * **ولا تحلّ محلَّ نظام التصميم**: الرأسُ رأسُ R13 · R14 بأصنافه (`.t2-head` · `.t2-back` · `.t2-title`)، والملاحظةُ سطرُ الخطأ في
 * اللوحة (`.t2-note`)؛ وما هنا يجمعها كي لا تُكتب في ثماني شاشاتٍ ثمانيَ مرّات.
 */
import type { ReactNode } from "react";

import { Icon } from "@/taxo2";
import "./kit.css";

/** رأسُ الشاشة الداخلية — رجوعٌ دائريٌّ ٤٤ والعنوان (R13 · R14). */
export function SubHeadT2({ title, onBack }: { title: string; onBack: () => void }) {
  return (
    <div className="t2-head">
      <button type="button" className="t2-back" aria-label="رجوع" onClick={onBack}>
        <Icon name="arrow_forward" />
      </button>
      <h1 className="t2-title">{title}</h1>
    </div>
  );
}

/** سطرُ الحال بلون معناه — **الخطأُ يُعلَن** (`role="alert"`) والنجاحُ بعلامته. */
export function NoteT2({
  tone,
  lead = false,
  children,
}: {
  tone: "danger" | "warn" | "ok" | "plain";
  /** فوق محتوى الشاشة مباشرةً (تحت الرأس) — بلا هامشٍ علويّ. */
  lead?: boolean;
  children: ReactNode;
}) {
  const classes = ["t2-note", tone === "ok" ? "t2-ok" : tone === "plain" ? null : tone, lead ? "t2-lead" : null]
    .filter(Boolean)
    .join(" ");
  return (
    <p className={classes} role={tone === "danger" ? "alert" : undefined}>
      {tone === "plain" ? null : <Icon name={tone === "ok" ? "check_circle" : "error"} />}
      <span>{children}</span>
    </p>
  );
}

/** الفراغ — دائرةُ أيقونةٍ وعنوانٌ وتلميح. */
export function BlankT2({ icon, title, hint }: { icon: string; title: string; hint?: string }) {
  return (
    <div className="t2-blank">
      <span className="t2-blank-icon">
        <Icon name={icon} />
      </span>
      <p className="t2-blank-title">{title}</p>
      {hint ? <p className="t2-blank-hint">{hint}</p> : null}
    </div>
  );
}

/** الانتظار — حلقةٌ بقوسٍ من الجمر، **تُعلَن ولا تُقرأ نصّاً** (`role="status"`). */
export function LoaderT2({ small = false }: { small?: boolean }) {
  return <span className={small ? "t2-loader sm" : "t2-loader"} role="status" aria-label="جارٍ التحميل" />;
}
