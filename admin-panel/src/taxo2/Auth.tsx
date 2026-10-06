/** TAXO 2.0 — قطعُ شاشات الدخول والتسجيل والرمز (R02 · R03 · R04، وأخواتُها عند الكبتن C01 · C02).
 *
 * **عرضٌ وحدَه** (§٦٢/١٦): لا نداءَ ولا إعدادَ ولا جلسةَ هنا — الشاشةُ تملك المنطق، وهذه تملك الشكل. **فتُنسخ في التطبيقين
 * بايتاً** (`check:taxo2`) ولا تستورد شيئاً من تطبيقٍ بعينه. والمقاساتُ من اللوحة في `auth.css`.
 */
import { useEffect, useRef, useState } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";

import { Icon } from "./Icon";
import "./auth.css";

/** الصفحة — **من الحافة إلى الحافة، والمحتوى داخل المنطقة الآمنة** (§٦٢/٩). */
export function AuthPage({ children }: { children: ReactNode }) {
  return (
    <div className="t2 t2-auth">
      <div className="t2-auth-body">{children}</div>
    </div>
  );
}

/** الرأس: رجوعٌ دائريّ — **و«١ / ٢» ومسارُه** حين تكون الشاشةُ خطوةً من خطوات (R03 · R04). */
export function AuthTop({ onBack, step, total }: { onBack?: () => void; step?: number; total?: number }) {
  return (
    <div className="t2-auth-top">
      {onBack ? (
        <button type="button" className="t2-auth-back" onClick={onBack} aria-label="رجوع">
          <Icon name="arrow_forward" />
        </button>
      ) : null}
      {step && total ? (
        <>
          <div className="t2-auth-track" aria-hidden="true">
            {Array.from({ length: total }, (_, index) => (
              <span key={index} className={index < step ? "on" : undefined} />
            ))}
          </div>
          <span className="t2-auth-count" aria-label={`الخطوة ${step} من ${total}`}>
            {step} / {total}
          </span>
        </>
      ) : null}
    </div>
  );
}

/** العنوانُ وسطرُه — `step` يصغّره كما في R03 · R04. */
export function AuthTitle({ title, sub, step = false }: { title: string; sub?: ReactNode; step?: boolean }) {
  return (
    <>
      <h1 className={step ? "t2-auth-title step" : "t2-auth-title"}>{title}</h1>
      {sub ? <p className="t2-auth-sub">{sub}</p> : null}
    </>
  );
}

/** سطرُ الخطأ تحت الحقل — **سببُه بالعربية حيث وقع** (§٦٢/٢٠). */
export function AuthError({ message, id }: { message: string | null | undefined; id?: string }) {
  if (!message) return null;
  return (
    <p className="t2-auth-error" id={id} role="alert">
      <Icon name="error" />
      <span>{message}</span>
    </p>
  );
}

/** حقلٌ بعنوانه وسطرِ خطئه أو تلميحه. `children` هو الجوف (`AuthInput` · `AuthPhone` · `AuthSecret`). */
export function AuthBlock({
  label,
  htmlFor,
  error,
  hint,
  children,
}: {
  label: string;
  htmlFor?: string;
  error?: string | null;
  hint?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="t2-auth-block">
      <label className="t2-auth-label" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
      {error ? <AuthError message={error} /> : hint ? <p className="t2-auth-hint">{hint}</p> : null}
    </div>
  );
}

type InputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "className"> & { invalid?: boolean };

/** جوفٌ نصيّ. */
export function AuthInput({ invalid, ...input }: InputProps) {
  return (
    <div className={invalid ? "t2-auth-field error" : "t2-auth-field"}>
      <input aria-invalid={invalid || undefined} {...input} />
    </div>
  );
}

/** الهاتف: «+962 | 79 555 01» من اليسار كما رُسم، **وعلامةُ صحّةٍ حين يكتمل** (R03). */
export function AuthPhone({
  dial,
  valid,
  invalid,
  ...input
}: InputProps & { dial: string | null; valid?: boolean }) {
  return (
    <div className={invalid ? "t2-auth-field phone error" : "t2-auth-field phone"}>
      <span className="t2-auth-dial">+{dial ?? ""}</span>
      <span className="t2-auth-sep" aria-hidden="true" />
      <input inputMode="tel" autoComplete="tel-national" aria-invalid={invalid || undefined} {...input} />
      {valid ? <Icon name="check_circle" fill className="t2-auth-ok" /> : null}
    </div>
  );
}

/** كلمةُ المرور — **والعينُ تُظهرها وتخفيها** (R02 · R03). */
export function AuthSecret({ invalid, ...input }: InputProps) {
  const [shown, setShown] = useState(false);
  return (
    <div className={invalid ? "t2-auth-field secret error" : "t2-auth-field secret"}>
      <input
        type={shown ? "text" : "password"}
        className={shown ? "shown" : undefined}
        aria-invalid={invalid || undefined}
        dir="auto"
        {...input}
      />
      <button
        type="button"
        className="t2-auth-eye"
        onClick={() => setShown((value) => !value)}
        aria-label={shown ? "إخفاء كلمة المرور" : "إظهار كلمة المرور"}
      >
        <Icon name={shown ? "visibility_off" : "visibility"} />
      </button>
    </div>
  );
}

/** شروطُ الحقل كما تنشرها الخلفية — **علامةٌ لا لونٌ وحدَه**. */
export function AuthConditions({ items }: { items: Array<{ key: string; label: string; ok: boolean }> }) {
  if (!items.length) return null;
  return (
    <ul className="t2-auth-conds">
      {items.map((item) => (
        <li key={item.key} className={item.ok ? "ok" : undefined}>
          <Icon name={item.ok ? "check_circle" : "radio_button_unchecked"} />
          <span>{item.label}</span>
        </li>
      ))}
    </ul>
  );
}

/** اختيارٌ من خيارين أو أكثر — **والمختارُ بحافّةٍ مزدوجةٍ وعلامة**؛ و`women` يرسمه بالبرقوق (R03 «راكبة»). */
export function AuthChoice<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T | null;
  options: Array<{ value: T; label: string; women?: boolean }>;
  onChange: (next: T) => void;
  label: string;
}) {
  return (
    <div className="t2-auth-choice" role="group" aria-label={label}>
      {options.map((option) => {
        const on = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            className={option.women ? "women" : undefined}
            aria-pressed={on}
            onClick={() => onChange(option.value)}
          >
            {on ? <Icon name="check_circle" /> : null}
            <span>{option.label}</span>
          </button>
        );
      })}
    </div>
  );
}

/** سطرُ الخدمة النسائية تحت «راكبة» (R03). */
export function AuthWomenNote({ children }: { children: ReactNode }) {
  return (
    <div className="t2-auth-women">
      <Icon name="woman" />
      <span>{children}</span>
    </div>
  );
}

/** الموافقةُ على السياسات — **مربّعٌ يُضغط**، والوثيقتان تُفتحان فقرةً فقرة (§٣٤ و§٦١-أ). */
export function AuthConsent({
  checked,
  onToggle,
  docs,
}: {
  checked: boolean;
  onToggle: () => void;
  docs: Array<{ id: string; title: string; body: string }>;
}) {
  const [open, setOpen] = useState<string | null>(null);
  if (!docs.length) return null;
  const shown = docs.find((doc) => doc.id === open);
  return (
    <div className="t2-auth-consent">
      <button type="button" role="checkbox" aria-checked={checked} className="t2-auth-consent-row" onClick={onToggle}>
        <span className="t2-auth-box" aria-hidden="true">
          <Icon name="check" />
        </span>
        <span>قرأتُ ووافقتُ على الوثيقتين أدناه.</span>
      </button>
      <div className="t2-auth-docs">
        {docs.map((doc) => (
          <button key={doc.id} type="button" aria-expanded={open === doc.id} onClick={() => setOpen(open === doc.id ? null : doc.id)}>
            {doc.title}
          </button>
        ))}
      </div>
      {shown ? (
        <div className="t2-auth-doc">
          {shown.body.split(/\n{2,}/).map((para, index) => (para.trim() ? <p key={index}>{para.trim()}</p> : null))}
        </div>
      ) : null}
    </div>
  );
}

/** خاناتُ الرمز — **تعرض ما يُكتب في حقلٍ واحدٍ خلفها** فيبقى الملءُ الآليُّ من الرسالة (`one-time-code`) ولوحةُ مفاتيح النظام. */
export function AuthCode({
  length,
  value,
  onChange,
  invalid,
  disabled,
  autoFocus = true,
}: {
  length: number;
  value: string;
  onChange: (next: string) => void;
  invalid?: boolean;
  disabled?: boolean;
  autoFocus?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [focused, setFocused] = useState(false);
  useEffect(() => {
    if (autoFocus) input.current?.focus();
  }, [autoFocus]);
  const classes = ["t2-auth-code", length <= 4 ? "four" : null, invalid ? "error" : null].filter(Boolean).join(" ");
  return (
    <div className={classes} onClick={() => input.current?.focus()}>
      {Array.from({ length }, (_, index) => (
        <span key={index} className={focused && index === Math.min(value.length, length - 1) ? "at" : undefined} aria-hidden="true">
          {value[index] ?? ""}
        </span>
      ))}
      <input
        ref={input}
        inputMode="numeric"
        autoComplete="one-time-code"
        aria-label="رمز التحقق"
        aria-invalid={invalid || undefined}
        maxLength={length}
        value={value}
        disabled={disabled}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        onChange={(event) => onChange(event.target.value.replace(/\D/g, "").slice(0, length))}
      />
    </div>
  );
}

/** «أو» بين خطّين (R02). */
export function AuthOr() {
  return <div className="t2-auth-or">أو</div>;
}
