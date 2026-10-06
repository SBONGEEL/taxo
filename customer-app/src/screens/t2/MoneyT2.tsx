/** **قطعُ شاشات المال في TAXO 2.0** — الرأس، والبلاغ، والورقةُ فوق الشاشة، وبطاقةُ المبلغ (`design/t2-new/rider/R16–R21`).
 *
 * **عرضٌ وحدَه** (§٦٢/١٦): لا نداءَ هنا ولا قرار — الشاشةُ تملك المنطقَ، وهذه تملك الشكل، **فلا يفترق شكلُ الشحن عن التحويل عن الدفع**.
 * والأصنافُ في `money.css` بالرموز وحدَها.
 */

import { createPortal } from "react-dom";
import type { ReactNode } from "react";

import { currencyLabel } from "@/lib/utils";
import { Icon } from "@/taxo2";

import { SheetT2 } from "./SheetT2";
import "./t2.css";
import "./money.css";

/** رأسُ الشاشة الداخلية — رجوعٌ دائريٌّ والعنوان (R13 · R14). وبلا `onBack` عنوانٌ وحدَه (نتيجةُ الدفع: لا رجوعَ منها). */
export function HeadT2({ title, onBack }: { title: string; onBack?: () => void }) {
  if (!onBack) {
    return (
      <div className="t2-m-stage-title">
        <h1 className="t2-title">{title}</h1>
      </div>
    );
  }
  return (
    <div className="t2-head">
      <button type="button" className="t2-back" aria-label="رجوع" onClick={onBack}>
        <Icon name="arrow_forward" />
      </button>
      <h1 className="t2-title">{title}</h1>
    </div>
  );
}

/** **ما لا حقلَ له سطرٌ فوق الزرّ** (§٦٢/٢٠) — بنبرة الخطأ أو النجاح، والنصُّ كما جاء من الخلفية. */
export function BannerT2({ tone, message }: { tone: "danger" | "ok"; message: string | null | undefined }) {
  if (!message) return null;
  return (
    <div className={`t2-m-banner ${tone}`} role={tone === "danger" ? "alert" : "status"}>
      <Icon name={tone === "danger" ? "error" : "check_circle"} />
      <span>{message}</span>
    </div>
  );
}

/** **ورقةٌ فوق الشاشة** — ظلٌّ يُغلق بالضغط، والورقةُ ملتصقةٌ بالقاع (R06) وتعلو لوحةَ المفاتيح (`--vv-bottom`).
 *
 * **وتُنقل إلى `body`** كمنتقي الدفع: الشاشةُ داخل انتقالٍ يحمل `transform`، و`fixed` تحته يُقاس عليه لا على الشاشة.
 * **و`onClose: null`** يُبقي الظلَّ بلا فعل — ورقةٌ تُغلق وهي تنتظر جوابَ مالٍ تُخفي ما ينتظره صاحبُها.
 */
export function SheetModalT2({
  onClose,
  footer,
  children,
}: {
  onClose: (() => void) | null;
  footer?: ReactNode;
  children: ReactNode;
}) {
  return createPortal(
    <>
      <button
        type="button"
        aria-label="إغلاق"
        className="t2 t2-m-scrim"
        disabled={!onClose}
        onClick={onClose ?? undefined}
      />
      <div className="t2-m-modal">
        <SheetT2 footer={footer}>{children}</SheetT2>
      </div>
    </>,
    document.body,
  );
}

/** **بطاقةُ المبلغ** — بطاقةُ الأجرة في R10: التسميةُ، والرقمُ بخطِّ الأرقام، والعملةُ. **والحقلُ يقبل الخاناتِ والنقطةَ وحدَها**
 *  كما كان (`[^\d.]` يُنزع) — والمبلغُ نصٌّ يُرسل كما كُتب، والخلفيةُ هي التي تحكم. */
export function AmountCardT2({
  id,
  label,
  value,
  onChange,
  currency,
  disabled,
  children,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (next: string) => void;
  currency: string | null | undefined;
  disabled?: boolean;
  children?: ReactNode;
}) {
  return (
    <div className="t2-m-card t2-m-amount-card">
      <label className="t2-m-label" htmlFor={id}>
        {label}
      </label>
      <div className="t2-m-amount">
        <input
          id={id}
          className="t2-m-amount-input"
          inputMode="decimal"
          dir="ltr"
          autoComplete="off"
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value.replace(/[^\d.]/g, ""))}
        />
        <span className="t2-m-cur">{currencyLabel(currency)}</span>
      </div>
      {children}
    </div>
  );
}

/** المبالغُ السريعة تحت خطٍّ متقطّع — خياراتُ البقشيش في R10. `label` يرسم القيمةَ (بعملتها أو بلا). */
export function QuickAmountsT2({
  amounts,
  value,
  onPick,
  label,
}: {
  amounts: readonly string[];
  value: string;
  onPick: (next: string) => void;
  label: (amount: string) => string;
}) {
  return (
    <>
      <div className="t2-m-dash" aria-hidden="true" />
      <div className="t2-m-quick">
        {amounts.map((amount) => (
          <button
            key={amount}
            type="button"
            aria-pressed={value === amount}
            className={value === amount ? "t2-m-chip on" : "t2-m-chip"}
            onClick={() => onPick(amount)}
          >
            {label(amount)}
          </button>
        ))}
      </div>
    </>
  );
}

/** نصُّ زرٍّ ينتظر جوابَ الخلفية — **حلقةٌ صغيرةٌ بجانب النصّ** (كما كان زرُّ اللغة السابقة يُري دوّامتَه)، والزرُّ نفسُه يُعطَّل. */
export function BusyLabel({ busy, children }: { busy: boolean; children: ReactNode }) {
  return (
    <>
      {busy ? <span className="t2-m-btn-spin" aria-hidden="true" /> : null}
      {children}
    </>
  );
}

/** دائرةُ الانتظار — بلونَي الهوية، وتقف مع «تقليل الحركة». */
export function WaitT2({ label }: { label?: string }) {
  return (
    <div className="t2-m-wait" role="status" aria-live="polite" aria-label={label ? undefined : "لحظة…"}>
      <span className="t2-m-spin" aria-hidden="true" />
      {label ? <span>{label}</span> : null}
    </div>
  );
}
