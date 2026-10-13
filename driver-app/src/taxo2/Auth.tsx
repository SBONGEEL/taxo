/** TAXO 2.0 — قطعُ شاشات الدخول والتسجيل والرمز (R02 · R03 · R04، وأخواتُها عند الكبتن C01 · C02).
 *
 * **عرضٌ وحدَه** (§٦٢/١٦): لا نداءَ ولا إعدادَ ولا جلسةَ هنا — الشاشةُ تملك المنطق، وهذه تملك الشكل. **فتُنسخ في التطبيقين
 * بايتاً** (`check:taxo2`) ولا تستورد شيئاً من تطبيقٍ بعينه. والمقاساتُ من اللوحة في `auth.css`.
 */
import { useEffect, useRef, useState } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";

import { Flag } from "./Flag";
import { Icon } from "./Icon";
import "./auth.css"; import { tr } from "@/lib/i18n";

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
        <button type="button" className="t2-auth-back" onClick={onBack} aria-label={tr("رجوع")}>
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
          <span className="t2-auth-count" aria-label={tr("الخطوة {0} من {1}", { 0: step, 1: total })}>
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

/** الهاتف: «+962 | 79 555 01» من اليسار كما رُسم، **وعلامةُ صحّةٍ حين يكتمل** (R03).
 *
 * **ومع `country` يصير المفتاحُ زرَّ مُختار الدولة** (SPEC §٧٤-أ/٤، لوحةُ «تسجيل — حقل الهاتف»): العلمُ والمفتاحُ وسهمٌ، **ولمسةٌ
 * تفتح ورقةَ الدول** (`AuthCountrySheet`). وبلاه كما كان حرفاً — حقولُ الهاتف خارج المصادقة (التحويل · «اطلب لغيرك») لم تتغيّر.
 */
export function AuthPhone({
  dial,
  valid,
  invalid,
  country,
  ...input
}: InputProps & {
  dial: string | null;
  valid?: boolean;
  country?: { code: string; name: string; onOpen: () => void; disabled?: boolean };
}) {
  return (
    <div className={invalid ? "t2-auth-field phone error" : "t2-auth-field phone"}>
      {country ? (
        <button
          type="button"
          className="t2-auth-country"
          onClick={country.onOpen}
          disabled={country.disabled}
          aria-haspopup="dialog"
          aria-label={tr("الدولة: {0}، +{1} — غيّرها", { 0: country.name, 1: dial ?? "" })}
        >
          <Flag code={country.code} label={country.name} size={26} />
          <span className="t2-auth-dial">+{dial ?? ""}</span>
          <Icon name="expand_more" />
        </button>
      ) : (
        <span className="t2-auth-dial">+{dial ?? ""}</span>
      )}
      <span className="t2-auth-sep" aria-hidden="true" />
      <input inputMode="tel" autoComplete="tel-national" aria-invalid={invalid || undefined} {...input} />
      {valid ? <Icon name="check_circle" fill className="t2-auth-ok" /> : null}
    </div>
  );
}

/** دولةٌ في ورقة المُختار — **`soon` رماديّةٌ لا تُختار** («قريباً»)، والمخفيّةُ لا تصل هنا أصلاً (يصفّيها المُنادي). */
export type AuthCountryOption = { code: string; name: string; dial: string; soon?: boolean };

/** **ورقةُ الدول** (لوحاتُ «تسجيل — ورقة الدول» · «دخول — كلُّ دولة» · «وضعُ النساء» · الفرنسيّة): العلمُ والاسمُ والمفتاح، والمختارةُ
 * بحافّةٍ مزدوجةٍ وعلامة، والمغلقةُ في التسجيل «قريباً» بحافّةٍ متقطّعة. **تُغلق بالظلّ وبـEscape، واختيارٌ يغلقها.**
 */
export function AuthCountrySheet({
  open,
  title,
  sub,
  note,
  options,
  value,
  onPick,
  onClose,
}: {
  open: boolean;
  title: string;
  sub?: string;
  note?: ReactNode;
  options: AuthCountryOption[];
  value: string;
  onPick: (code: string) => void;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="t2 t2-country">
      <button type="button" className="t2-country-scrim" aria-label={tr("إغلاق")} onClick={onClose} />
      <div className="t2-country-sheet" role="dialog" aria-modal="true" aria-label={title}>
        <span className="t2-country-handle" aria-hidden="true" />
        <h2 className="t2-country-title">{title}</h2>
        {sub ? <p className="t2-country-sub">{sub}</p> : null}
        <div className="t2-country-list">
          {options.map((option) => {
            const on = option.code === value;
            return (
              <button
                key={option.code}
                type="button"
                className={option.soon ? "soon" : undefined}
                aria-pressed={on}
                disabled={option.soon}
                onClick={() => onPick(option.code)}
              >
                <Flag code={option.code} label={option.name} size={30} muted={option.soon} />
                <span className="t2-country-name">{option.name}</span>
                <span className="t2-country-dial" dir="ltr">
                  +{option.dial}
                </span>
                {option.soon ? <span className="t2-country-soon">{tr("قريباً")}</span> : null}
                {on && !option.soon ? <Icon name="check_circle" fill className="t2-country-on" /> : null}
              </button>
            );
          })}
        </div>
        {note ? <p className="t2-country-note">{note}</p> : null}
      </div>
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
        aria-label={shown ? tr("إخفاء كلمة المرور") : tr("إظهار كلمة المرور")}
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
        <span>{tr("قرأتُ ووافقتُ على الوثيقتين أدناه.")}</span>
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
        aria-label={tr("رمز التحقق")}
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
  return <div className="t2-auth-or">{tr("أو")}</div>;
}
