/** **قسيمةُ مطالبةٍ يدويّةٍ بكليك — بيتٌ واحدٌ لغرضين** (2026-08-30) — TAXO 2.0 «C21 · C22» (`design/t2-new/captain/`).
 *
 * **ولمَ استُخرجت**: صار للمطالبة اليدوية غرضان — اشتراكٌ ودَين — **وشاشتان تنسخان الرسمَ نفسَه تفترقان أول تعديل**. وهو «موضعان
 * يحسبان شيئاً واحداً» بعينه، وقد وقع في هذا المشروع مراراً.
 *
 * **والمختلفُ بينهما جملةٌ واحدة**: ماذا يعني «مؤكَّد» — اشتراكٌ فُعِّل، أم دَينٌ نقص. فتُمرَّر نصّاً ولا يُنسخ ملفّ.
 *
 * ## وستّةٌ زِيدت 2026-09-01 (قرارُ المالك)
 *
 * **٢) زرُّ نسخٍ للمرجع وللحساب** — والحسابُ يُكتب بيده اليوم. **ويقول «نُسخ»**: من لا يرى أثراً يضغط مرّتين ولا يدري أنُسخ أم لا.
 *
 * **٣) وملاحظةُ المرجع تكبر وتبرز** — **فهي التي تربط تحويلَه بطلبه**، وبلاها لا يعرف المشرفُ من دفع.
 *
 * **٤) وزرُّ «تمّ الدفع» يُفتح بعد النسخ** — **والنسخُ ليس دفعاً**: من حوّل من جهازٍ آخر ولم ينسخ يبقى الزرُّ مغلقاً عليه، **فتحته جملةٌ
 * تقول لماذا**. **وزرٌّ مغلقٌ صامتٌ يُقرأ عطباً في التطبيق.**
 *
 * **٥) وبعد الضغط تتبدّل الحال** وتظهر مدّةُ المراجعة **من الحقلين لا من نصّ**. **وضغطةٌ ثانيةٌ لا تُنشئ طلباً ثانياً ولا تصيح** —
 * الخلفيةُ تختم مرّةً، والشاشةُ تقول إن الطلبَ مسجَّل.
 *
 * **والمنطقُ هو هو حرفاً**. **وما تغيّر طبقةُ العرض**: قسيمةٌ بسطح البطاقة ورقمِ C09، **والمرجعُ بالجمر الخافت وحافّته** (أبرزُ ما
 * في الشاشة)، وزرُّ الجمر، وبطاقةُ الحال بنبرتها — وأيقوناتُ الهوية مكانَ أيقونات المكتبة القديمة.
 */

import { useState } from "react";

import { ApiError } from "@/api/client";
import { declareCliqPaid } from "@/api/endpoints";
import type { Currency } from "@/api/types";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { digits } from "@/lib/utils";
import { Icon } from "@/taxo2";

import "@/screens/t2/money.css";

export interface CliqClaimLike {
  id: string;
  cart_id: string;
  amount: string;
  currency: Currency;
  status: "created" | "paid" | "failed" | "cancelled";
  failure_reason: string | null;
  qr_url: string | null;
  alias: string;
  review_min_minutes: number;
  review_max_minutes: number;
  /** **لحظةُ قوله «حوّلتُ»** — و`null` تعني «لم يقل بعد». */
  declared_paid_at: string | null;
}

/** نبرةُ الحال — كما كانت: المعلّقةُ كهرمان، والمؤكَّدةُ خضراء، والمرفوضةُ حمراء، والملغاةُ خافتة. */
const STATUS_TONE: Record<CliqClaimLike["status"], "warn" | "ok" | "danger" | "plain"> = {
  created: "warn",
  paid: "ok",
  failed: "danger",
  cancelled: "plain",
};

export function CliqClaimView({
  claim,
  paidText,
}: {
  claim: CliqClaimLike;
  /** ماذا يعني «مؤكَّد» هنا — وهو الفرقُ الوحيدُ بين الغرضين. */
  paidText: string;
}) {
  const [copied, setCopied] = useState<"ref" | "alias" | null>(null);
  const [refCopied, setRefCopied] = useState(false);
  const [declaredAt, setDeclaredAt] = useState(claim.declared_paid_at);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const declared = declaredAt !== null;

  async function copy(value: string, which: "ref" | "alias") {
    // **ولا يُبتلع الفشلُ صامتاً**: متصفّحٌ يمنع الحافظة يترك المستخدمَ أمام
    // زرٍّ لا يفعل شيئاً — فيُقال، ويبقى النصُّ قابلاً للتحديد باليد
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      setError("تعذّر النسخ — حدّد المرجع بإصبعك وانسخه");
      return;
    }
    setCopied(which);
    if (which === "ref") setRefCopied(true);
    window.setTimeout(() => setCopied(null), 2_000);
  }

  async function declare() {
    setBusy(true);
    setError(null);
    try {
      const answer = await declareCliqPaid(claim.cart_id);
      // **الختمُ من الخلفية لا من الشاشة**: هي التي تعرف أوقعَ الختمُ الآن
      // أم كان واقعاً — **وضغطةٌ ثانيةٌ تُعيد الوقتَ الأوّل ولا تُنشئ ثانياً**
      setDeclaredAt(answer.declared_paid_at);
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر تسجيل الدفع",
      );
    } finally {
      setBusy(false);
    }
  }

  const statusText: Record<CliqClaimLike["status"], string> = {
    created: declared ? "بانتظار التأكيد" : "لم يُسجَّل الدفع بعد",
    paid: paidText,
    failed: "مرفوض",
    cancelled: "مُلغاة",
  };

  return (
    <>
      <section className="t2-clq-slip">
        <span className="t2-clq-k">المبلغ المطلوب</span>
        <span className="t2-clq-amount">
          <span className="t2-clq-num" dir="ltr">
            {digits(claim.amount)}
          </span>
          <span className="t2-clq-cur">{CURRENCY_LABEL[claim.currency]}</span>
        </span>

        {/* **الرمزُ إن رُفع، وإلا سطرٌ يقول ما جرى** — ولا مربّعٌ فارغ */}
        {claim.qr_url ? (
          <img src={claim.qr_url} alt="رمز كليك" className="t2-clq-qr" />
        ) : (
          <p className="t2-clq-noqr">
            لم يُرفع رمز الاستجابة بعد — حوّل إلى الحساب أدناه يدويّاً من تطبيق
            بنكك.
          </p>
        )}

        <span className="t2-clq-k t2-clq-to">حوّل إلى حساب كليك</span>
        <span className="t2-clq-alias-row">
          <span dir="ltr" className="t2-clq-alias">
            {claim.alias}
          </span>
          <button
            type="button"
            aria-label="انسخ حساب كليك"
            onClick={() => void copy(claim.alias, "alias")}
            className={copied === "alias" ? "t2-clq-copy done" : "t2-clq-copy"}
          >
            <Icon name={copied === "alias" ? "check" : "content_copy"} />
            {copied === "alias" ? "نُسخ" : "انسخ"}
          </button>
        </span>

        {/* **المرجعُ هو ما يُطابَق به — ولذلك يكبر ويبرز** (قرارُ المالك): بلاه لا يعرف المشرفُ من دفع، فهو أهمُّ ما في الشاشة
            لا سطرٌ تحت الحساب */}
        <div className="t2-clq-ref">
          <p className="t2-clq-ref-title">
            اكتب هذا المرجع في خانة الملاحظة عند التحويل
          </p>
          <p dir="ltr" className="t2-clq-ref-code">
            {claim.cart_id}
          </p>
          <button
            type="button"
            aria-label="انسخ المرجع"
            onClick={() => void copy(claim.cart_id, "ref")}
            className={
              copied === "ref" ? "t2-clq-ref-copy done" : "t2-clq-ref-copy"
            }
          >
            <Icon name={copied === "ref" ? "check" : "content_copy"} />
            {copied === "ref" ? "نُسخ" : "انسخ المرجع"}
          </button>
          <p className="t2-clq-ref-hint">
            بلا هذا المرجع لا يُعرف أنّ الحوالة منك — فيتأخّر تأكيدها.
          </p>
        </div>
      </section>

      {/* ─────────────── «تمّ الدفع» — يُفتح بعد النسخ */}
      {claim.status === "created" && !declared ? (
        <section className="t2-clq-declare">
          <button
            type="button"
            className="t2-clq-cta"
            disabled={!refCopied || busy}
            onClick={() => void declare()}
          >
            {busy ? "…" : "تمّ الدفع"}
          </button>
          {!refCopied ? (
            // **ولا زرَّ مغلقٌ صامت**: من لا يعرف لماذا أُغلق يقرؤه عطباً
            <p className="t2-clq-why">
              انسخ المرجع أوّلاً — ثم أخبرنا أنك حوّلت.
            </p>
          ) : null}
        </section>
      ) : null}

      {error ? (
        <p className="t2-note danger t2-clq-error" role="alert">
          <Icon name="error" fill />
          {error}
        </p>
      ) : null}

      <section className="t2-clq-status">
        <div className="t2-clq-status-top">
          <span className="t2-clq-status-k">حال الطلب</span>
          <span className={`t2-clq-state ${STATUS_TONE[claim.status]}`}>
            {statusText[claim.status]}
          </span>
        </div>

        {/* **ومدّةُ المراجعة من الحقلين لا من نصّ** — ولا تُقال قبل أن يقول إنه حوّل: من لم يحوّل لا تجري عليه مدّة */}
        {claim.status === "created" && declared ? (
          <p className="t2-clq-line">
            سجّلنا دفعك. ستتم المراجعة خلال{" "}
            {digits(String(claim.review_min_minutes))} إلى{" "}
            {digits(String(claim.review_max_minutes))} دقائق.
          </p>
        ) : null}

        {/* **ما ينقص يُقال بعينه** — «وصل ٥ من ٧٫٢» أنفعُ من «مرفوض» */}
        {claim.failure_reason ? (
          <p className="t2-clq-line warn">{claim.failure_reason}</p>
        ) : null}

        {/* **يُقال إن التحصيل يدويّ** — فلا يُنتظر ما لا يأتي */}
        <p className="t2-clq-manual">
          التحصيل يدويّ: يراجع مشرفٌ وصولَ المبلغ ثم يؤكّده، ولا يُخصم شيءٌ
          تلقائياً. ولا تعِد التحويل — يكفي واحد، وتجد حال طلبك هنا.
        </p>
      </section>
    </>
  );
}
