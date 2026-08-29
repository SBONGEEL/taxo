/** **بطاقةُ مطالبةٍ يدويّةٍ بكليك — بيتٌ واحدٌ لغرضين** (2026-08-30).
 *
 * **ولمَ استُخرجت**: صار للمطالبة اليدوية غرضان — اشتراكٌ ودَين — **وشاشتان
 * تنسخان الرسمَ نفسَه تفترقان أول تعديل**. وهو «موضعان يحسبان شيئاً واحداً»
 * بعينه، وقد وقع في هذا المشروع مراراً.
 *
 * **والمختلفُ بينهما جملةٌ واحدة**: ماذا يعني «مؤكَّد» — اشتراكٌ فُعِّل، أم
 * دَينٌ نقص. فتُمرَّر نصّاً ولا يُنسخ ملفّ.
 */

import type { Currency } from "@/api/types";
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
  const statusText: Record<CliqClaimLike["status"], string> = {
    created: "بانتظار التأكيد",
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
        <div dir="ltr" className="mt-2 select-all text-22 font-bold text-ink">
          {claim.alias}
        </div>

        {/* **المرجعُ هو ما يُطابَق به** — ولذلك يُعرض قابلاً للنسخ ويُقال لمَ */}
        <div className="mt-14 text-12 text-muted">اكتب هذا المرجع في التحويل</div>
        <div dir="ltr" className="mt-2 select-all text-15 font-bold text-ink">
          {claim.cart_id}
        </div>
      </section>

      <section className="mb-12 rounded-20 border border-line bg-surface p-20">
        <div className="flex items-baseline justify-between">
          <span className="text-12.5 text-muted">حال الطلب</span>
          <span className={`text-13.5 font-bold ${STATUS_TONE[claim.status]}`}>
            {statusText[claim.status]}
          </span>
        </div>

        {claim.status === "created" ? (
          <p className="mt-10 text-11.5 leading-note text-muted">
            ستتم المراجعة خلال {digits(String(claim.review_min_minutes))} إلى{" "}
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
