/** **بطاقةُ مطالبةٍ يدويّةٍ بكليك — بيتٌ واحدٌ لغرضين** (2026-08-30).
 *
 * **ولمَ استُخرجت**: صار للمطالبة اليدوية غرضان — اشتراكٌ ودَين — **وشاشتان
 * تنسخان الرسمَ نفسَه تفترقان أول تعديل**. وهو «موضعان يحسبان شيئاً واحداً»
 * بعينه، وقد وقع في هذا المشروع مراراً.
 *
 * **والمختلفُ بينهما جملةٌ واحدة**: ماذا يعني «مؤكَّد» — اشتراكٌ فُعِّل، أم
 * دَينٌ نقص. فتُمرَّر نصّاً ولا يُنسخ ملفّ.
 *
 * ## وستّةٌ زِيدت 2026-09-01 (قرارُ المالك)
 *
 * **٢) زرُّ نسخٍ للمرجع وللحساب** — والحسابُ يُكتب بيده اليوم. **ويقول
 * «نُسخ»**: من لا يرى أثراً يضغط مرّتين ولا يدري أنُسخ أم لا.
 *
 * **٣) وملاحظةُ المرجع تكبر وتبرز** — **فهي التي تربط تحويلَه بطلبه**،
 * وبلاها لا يعرف المشرفُ من دفع.
 *
 * **٤) وزرُّ «تمّ الدفع» يُفتح بعد النسخ** — **والنسخُ ليس دفعاً**: من حوّل
 * من جهازٍ آخر ولم ينسخ يبقى الزرُّ مغلقاً عليه، **فتحته جملةٌ تقول لماذا**.
 * **وزرٌّ مغلقٌ صامتٌ يُقرأ عطباً في التطبيق.**
 *
 * **٥) وبعد الضغط تتبدّل الحال** وتظهر مدّةُ المراجعة **من الحقلين لا من
 * نصّ**. **وضغطةٌ ثانيةٌ لا تُنشئ طلباً ثانياً ولا تصيح** — الخلفيةُ تختم
 * مرّةً، والشاشةُ تقول إن الطلبَ مسجَّل.
 */

import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { ApiError } from "@/api/client";
import { declareCliqPaid } from "@/api/endpoints";
import type { Currency } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { digits } from "@/lib/utils";

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

const STATUS_TONE: Record<CliqClaimLike["status"], string> = {
  created: "text-warn",
  paid: "text-ok",
  failed: "text-danger",
  cancelled: "text-muted",
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
      <section className="mb-12 rounded-20 border border-line bg-surface p-20 text-center">
        <div className="text-12 text-muted">المبلغ المطلوب</div>
        <div className="mt-4 text-34 font-bold leading-hero text-ink">
          {digits(claim.amount)} {CURRENCY_LABEL[claim.currency]}
        </div>

        {/* **الرمزُ إن رُفع، وإلا سطرٌ يقول ما جرى** — ولا مربّعٌ فارغ */}
        {claim.qr_url ? (
          <img
            src={claim.qr_url}
            alt="رمز كليك"
            className="mx-auto mt-16 w-full max-w-qr rounded-14 border border-line bg-white object-contain"
          />
        ) : (
          <p className="mt-12 rounded-14 border border-line bg-surface-2 px-14 py-12 text-11.5 leading-note text-muted">
            لم يُرفع رمز الاستجابة بعد — حوّل إلى الحساب أدناه يدويّاً من تطبيق
            بنكك.
          </p>
        )}

        <div className="mt-16 text-12 text-muted">حوّل إلى حساب كليك</div>
        <div className="mt-2 flex items-center justify-center gap-8">
          <span dir="ltr" className="select-all text-22 font-bold text-ink">
            {claim.alias}
          </span>
          <button
            type="button"
            aria-label="انسخ حساب كليك"
            onClick={() => void copy(claim.alias, "alias")}
            className="flex items-center gap-4 rounded-10 border border-line px-8 py-5 text-11 font-semibold text-muted"
          >
            {copied === "alias" ? (
              <>
                <Check className="size-13 text-ok" />
                نُسخ
              </>
            ) : (
              <>
                <Copy className="size-13" />
                انسخ
              </>
            )}
          </button>
        </div>

        {/* **المرجعُ هو ما يُطابَق به — ولذلك يكبر ويبرز** (قرارُ المالك):
            بلاه لا يعرف المشرفُ من دفع، فهو أهمُّ ما في الشاشة لا سطرٌ تحت
            الحساب */}
        <div className="mt-16 rounded-16 border border-accent bg-surface-2 p-14">
          <div className="text-13 font-bold text-ink">
            اكتب هذا المرجع في خانة الملاحظة عند التحويل
          </div>
          <div
            dir="ltr"
            className="mt-8 select-all break-all text-19 font-bold leading-tight text-ink"
          >
            {claim.cart_id}
          </div>
          <button
            type="button"
            aria-label="انسخ المرجع"
            onClick={() => void copy(claim.cart_id, "ref")}
            className="mt-10 flex w-full items-center justify-center gap-6 rounded-12 border border-line bg-surface py-10 text-12.5 font-bold text-ink"
          >
            {copied === "ref" ? (
              <>
                <Check className="size-15 text-ok" />
                نُسخ
              </>
            ) : (
              <>
                <Copy className="size-15" />
                انسخ المرجع
              </>
            )}
          </button>
          <p className="mt-8 text-11 leading-note text-muted">
            بلا هذا المرجع لا يُعرف أنّ الحوالة منك — فيتأخّر تأكيدها.
          </p>
        </div>
      </section>

      {/* ─────────────── «تمّ الدفع» — يُفتح بعد النسخ */}
      {claim.status === "created" && !declared ? (
        <section className="mb-12">
          <Button
            className="w-full"
            disabled={!refCopied}
            loading={busy}
            onClick={() => void declare()}
          >
            تمّ الدفع
          </Button>
          {!refCopied ? (
            // **ولا زرَّ مغلقٌ صامت**: من لا يعرف لماذا أُغلق يقرؤه عطباً
            <p className="mt-8 text-center text-11.5 leading-note text-muted">
              انسخ المرجع أوّلاً — ثم أخبرنا أنك حوّلت.
            </p>
          ) : null}
        </section>
      ) : null}

      {error ? (
        <p className="mb-12 rounded-14 border border-line bg-surface-2 px-14 py-10 text-11.5 leading-note text-danger">
          {error}
        </p>
      ) : null}

      <section className="mb-12 rounded-20 border border-line bg-surface p-20">
        <div className="flex items-baseline justify-between">
          <span className="text-12.5 text-muted">حال الطلب</span>
          <span className={`text-13.5 font-bold ${STATUS_TONE[claim.status]}`}>
            {statusText[claim.status]}
          </span>
        </div>

        {/* **ومدّةُ المراجعة من الحقلين لا من نصّ** — ولا تُقال قبل أن يقول
            إنه حوّل: من لم يحوّل لا تجري عليه مدّة */}
        {claim.status === "created" && declared ? (
          <p className="mt-10 text-11.5 leading-note text-muted">
            سجّلنا دفعك. ستتم المراجعة خلال{" "}
            {digits(String(claim.review_min_minutes))} إلى{" "}
            {digits(String(claim.review_max_minutes))} دقائق.
          </p>
        ) : null}

        {/* **ما ينقص يُقال بعينه** — «وصل ٥ من ٧٫٢» أنفعُ من «مرفوض» */}
        {claim.failure_reason ? (
          <p className="mt-10 text-11.5 leading-note text-warn">
            {claim.failure_reason}
          </p>
        ) : null}

        {/* **يُقال إن التحصيل يدويّ** — فلا يُنتظر ما لا يأتي */}
        <p className="mt-10 border-t border-line pt-10 text-11 leading-note text-muted">
          التحصيل يدويّ: يراجع مشرفٌ وصولَ المبلغ ثم يؤكّده، ولا يُخصم شيءٌ
          تلقائياً. ولا تعِد التحويل — يكفي واحد، وتجد حال طلبك هنا.
        </p>
      </section>
    </>
  );
}
