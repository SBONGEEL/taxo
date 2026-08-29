/** **شاشةُ دفع اشتراكٍ بكليك — تحصيلٌ يدويٌّ يُقال صراحةً** (قرارُ المالك
 * 2026-08-29).
 *
 * **ولا يُدّعى أنها بوّابةٌ آلية**: لا حسمَ يقع لحظةَ الضغط، ولا إشعارَ من
 * بنكٍ يصل الخلفية. **مشرفٌ يقرأ كشفَه ويؤكّد** — والشاشةُ تقول ذلك بنصِّها،
 * فمن ظنّها آليّةً ينتظر ما لا يأتي ويعيد الدفع.
 *
 * **والمبلغُ مكتوبٌ سلفاً ولا يُدخله أحد**: سعرُ العرض محسوباً في الخلفية
 * (§14) — لا يكتبه الكبتنُ ولا تحسبه الشاشة.
 *
 * **وتعمل بلا صورة** (قرارُ المالك): `qr_url` قد تكون `null` — فتُعرض
 * **الحسابُ والمبلغُ والمرجع** وسطرٌ يقول إن الرمزَ لم يُرفع بعد. **ولا تسقط
 * الشاشةُ على حقلٍ فارغ**، وباركودٌ لا يعمل أسوأُ من غيابه.
 *
 * **وجملةُ الانتظار من اللوحة لا من هنا**: «تتم المراجعة خلال {min} إلى {max}
 * دقائق» — **وعدٌ لمن يدفع**، ويومَ تكثر الطلباتُ ولا تلحق المراجعةُ **يُعدَّل
 * الرقمان بلا نشر**.
 */

import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { listMyCliqClaims } from "@/api/endpoints";
import type { CliqSubscriptionClaim } from "@/api/types";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { useGoBack } from "@/lib/back";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { digits } from "@/lib/utils";

const STATUS_TEXT: Record<CliqSubscriptionClaim["status"], string> = {
  created: "بانتظار التأكيد",
  paid: "مؤكَّد — اشتراكك فُعِّل",
  failed: "مرفوض",
  cancelled: "مُلغاة",
};

const STATUS_TONE: Record<CliqSubscriptionClaim["status"], string> = {
  created: "text-warn",
  paid: "text-ok",
  failed: "text-danger",
  cancelled: "text-muted",
};

export function CliqSubscriptionScreen() {
  const goBack = useGoBack("/subscription");
  const { claimId } = useParams<{ claimId: string }>();
  const [claim, setClaim] = useState<CliqSubscriptionClaim | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const rows = await listMyCliqClaims();
    setClaim(rows.find((row) => row.id === claimId) ?? rows[0] ?? null);
  }, [claimId]);

  useEffect(() => {
    load().catch((caught: unknown) =>
      setError(caught instanceof ApiError ? caught.message : "تعذّرت القراءة"),
    );
  }, [load]);

  // **يُستعلَم كلَّ ١٥ ثانية ما دامت معلّقة** — والتحصيلُ يدويّ، فالانتظارُ
  // دقائق. **ويتوقف عند أيِّ حالٍ نهائية** فلا نداءٌ بلا سبب
  useEffect(() => {
    if (!claim || claim.status !== "created") return;
    const timer = window.setInterval(() => void load().catch(() => undefined), 15000);
    return () => window.clearInterval(timer);
  }, [claim, load]);

  return (
    <div className="scr h-full bg-bg px-16 pb-12 pt-safe">
      <div className="mb-16 mt-6 flex items-center gap-10">
        <button
          type="button"
          onClick={() => goBack()}
          aria-label="رجوع"
          className="pressable text-18 text-muted"
        >
          →
        </button>
        <h1 className="text-20 font-bold text-ink">الدفع بكليك</h1>
      </div>

      <ErrorNote message={error} />
      {claim === null && !error ? <Spinner className="mx-auto" /> : null}

      {claim ? (
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
                لم يُرفع رمز الاستجابة بعد — حوّل إلى الحساب أدناه يدويّاً من
                تطبيق بنكك.
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
                {STATUS_TEXT[claim.status]}
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
              تلقائياً. ولا تعِد التحويل — يكفي واحد، وتجد حال طلبك هنا وفي
              شاشة الاشتراك.
            </p>
          </section>
        </>
      ) : null}
    </div>
  );
}
