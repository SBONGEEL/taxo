/** **دفعُ الجزائر بأمان** (SPEC §٨٢، أمرُ المالك ٢٠٢٦-١٠-٢٢) — قطعٌ تشترك فيها شاشةُ الدفع وشاشةُ العودة والمحفظة.
 *
 * - **الوسيطُ متوقّف** (`payment_gateway_down`): يُقال بلغة الدافع — «الدفعُ الإلكترونيُّ متوقّفٌ مؤقّتاً لدى مزوّد الدفع» — ومعه «أعد
 *   المحاولة»، **وتحويلُ BaridiMob بديلاً إن كان مفعَّلاً**. ولا يُرسل الدافعُ إلى صفحةٍ معطوبة.
 * - **BaridiMob**: الـRIP مجمَّعاً ويُنسخ كاملاً، واسما صاحب الحساب (العربيُّ واللاتينيُّ كما تعرضه بريدُ الجزائر) يُنسخان، والحدّان،
 *   وخطواتٌ قصيرة، **ومرجعُ TAXO** يُكتب في ملاحظة التحويل — وهو مرجعُ الطلب نفسِه (`TX-` وأوّلُ ستّةٍ من معرّفه).
 * - **أطوارُ الدفعة** (§٨٢-أ/٢): «قيد المعالجة» لا يُسأل صاحبُها أن يدفع ثانية، و«بانتظار الدفع» لا تحجب.
 * - **سطرُ الدعم**: «إن خُصم المبلغ من بطاقتك ولم تظهر الدفعة، تواصل مع الدعم» — وزرُّه.
 *
 * **والملفُّ نفسُه في التطبيقين** — والفرقُ صنفا البطاقة والعنوان يمرّان وسيطين.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import type { MyPaymentRequest, PayMethod } from "@/api/types";
import { tr } from "@/lib/i18n";
import { Icon } from "@/taxo2";

import "./paydz.css";

/** **معرّفُ طريقة BaridiMob** — كما في الخلفية (`services/transfers.CODE`) */
export const BARIDIMOB = "baridimob";

export function gatewayIsDown(caught: unknown): boolean {
  return caught instanceof ApiError && caught.code === "payment_gateway_down";
}

/** **مرجعُ TAXO** — كما تشتقّه الخلفية (`payment_requests.public_ref`): `TX-` وأوّلُ ستّةٍ من المعرّف بلا شرطات */
export function publicRef(requestId: string): string {
  return `TX-${requestId.replace(/-/g, "").slice(0, 6).toUpperCase()}`;
}

/** **معرّفُ الطلب من التطبيق** — منه مرجعُ TAXO قبل التحويل، وإرسالُه مرّتين طلبٌ واحد */
export function newRequestId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const hex = Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-4${hex.slice(13, 16)}-a${hex.slice(17, 20)}-${hex.slice(20)}`;
}

/** **تاريخُ اليوم محلّيّاً** (`YYYY-MM-DD`) — قيمةُ حقل التاريخ الافتراضيّة */
export function todayIso(): string {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** **RIP بريد الجزائر مجمَّعاً للقراءة** — ٣ · ٥ · ١٠ · ٢ (البنك · الوكالة · الحساب · المفتاح)؛ ويُنسخ بلا مسافات */
export function groupedRip(value: string): string {
  const digits = value.replace(/\D/g, "");
  if (digits.length !== 20) return value;
  return `${digits.slice(0, 3)} ${digits.slice(3, 8)} ${digits.slice(8, 18)} ${digits.slice(18)}`;
}

/** **طورُ الدفعة كما يراه صاحبُها** (§٨٢-أ/٢) */
export function phaseLabel(row: MyPaymentRequest): string | null {
  if (row.status !== "pending") return null;
  if (row.phase === "processing") return tr("قيد المعالجة");
  if (row.phase === "unconfirmed") return tr("بانتظار الدفع");
  return tr("قيد المراجعة");
}

function CopyRow({ label, value, shown, ltr, labelClass }: { label: string; value: string; shown?: string; ltr?: boolean; labelClass: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      /* الحافظةُ ممنوعة — النصُّ مرئيٌّ يُنسخ باليد */
    }
  }
  return (
    <div className="t2-pr-line">
      <span className={labelClass}>{label}</span>
      <span className="t2-pr-value">
        <span dir={ltr ? "ltr" : undefined} className={ltr ? "t2-pr-number" : "t2-pr-text"}>
          {shown ?? value}
        </span>
        <button type="button" className="t2-pr-copy" onClick={() => void copy()} aria-label={tr("نسخ {0}", { 0: label })}>
          <Icon name={copied ? "check" : "content_copy"} />
        </button>
      </span>
    </div>
  );
}

/** **إلى أين تحوّل في BaridiMob** — ومرجعُ TAXO والخطوات */
export function BaridiMobDetails({
  method,
  reference,
  limits,
  cardClass,
  labelClass,
}: {
  method: PayMethod;
  reference: string;
  limits: string | null;
  cardClass: string;
  labelClass: string;
}) {
  return (
    <div className={`${cardClass} t2-pr-dest t2-dz`} role="group" aria-label={tr("إلى أين تحوّل")}>
      {method.account_number ? (
        <CopyRow label={tr("رقم RIP")} value={method.account_number} shown={groupedRip(method.account_number)} ltr labelClass={labelClass} />
      ) : null}
      {method.account_holder ? <CopyRow label={tr("باسم")} value={method.account_holder} labelClass={labelClass} /> : null}
      {method.account_holder_latin ? (
        <CopyRow label={tr("الاسم كما في BaridiMob")} value={method.account_holder_latin} ltr labelClass={labelClass} />
      ) : null}
      <CopyRow label={tr("مرجع TAXO")} value={reference} ltr labelClass={labelClass} />
      {limits ? <p className="t2-dz-limits">{limits}</p> : null}
      <ol className="t2-dz-steps">
        <li>{tr("افتح BaridiMob واختر «تحويل».")}</li>
        <li>{tr("أدخل رقم RIP أعلاه، وتأكّد أن الاسم الذي يظهر يطابق الاسم أعلاه.")}</li>
        <li>{tr("حوّل المبلغ نفسَه، واكتب مرجع TAXO في خانة الملاحظة إن وُجدت.")}</li>
        <li>{tr("صوّر الإيصال، ثمّ اكتب رقم التحويل وتاريخه أدناه وأرفق الصورة.")}</li>
      </ol>
      <p className="t2-dz-note">{tr("يُضاف المبلغ بعد أن يراجع فريقُ TAXO وصولَ التحويل — وتجد حالَه في المحفظة.")}</p>
    </div>
  );
}

/** **الوسيطُ متوقّف** — الرسالةُ و«أعد المحاولة» والبديلُ إن وُجد */
export function GatewayDownNote({
  busy,
  onRetry,
  onAlternative,
}: {
  busy: boolean;
  onRetry: () => void;
  onAlternative: (() => void) | null;
}) {
  return (
    <div className="t2-dz-down" role="alert">
      <span className="t2-dz-down-head">
        <Icon name="error" />
        {tr("الدفعُ الإلكترونيُّ متوقّفٌ مؤقّتاً لدى مزوّد الدفع. حاول مجدّداً بعد دقائق.")}
      </span>
      <span className="t2-dz-down-actions">
        <button type="button" className="t2-dz-btn" disabled={busy} onClick={onRetry}>
          {tr("أعد المحاولة")}
        </button>
        {onAlternative ? (
          <button type="button" className="t2-dz-btn" disabled={busy} onClick={onAlternative}>
            {tr("ادفع بتحويل BaridiMob")}
          </button>
        ) : null}
      </span>
    </div>
  );
}

/** **سطرُ الدعم** (§٨٢-أ/٧) — في صفحة دفع الجزائر ونتيجتها */
export function SupportLine({ to }: { to: string }) {
  const navigate = useNavigate();
  return (
    <div className="t2-dz-support">
      <span>{tr("إن خُصم المبلغ من بطاقتك ولم تظهر الدفعة، تواصل مع الدعم.")}</span>
      <button type="button" className="t2-dz-btn" onClick={() => navigate(to)}>
        <Icon name="headset_mic" />
        {tr("الدعم")}
      </button>
    </div>
  );
}
