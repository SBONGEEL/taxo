/** إغلاقُ حساب الراكب — **طلبٌ يُراجَع لا مفتاحٌ يُرفع** (٢٠٢٦-٠٩-٠٧).
 *
 * ## العلّةُ شرطُ متجرٍ، والشكلُ قرارُ مالك
 *
 * **«If your app allows users to create an account, you must also provide an
 * option to request account deletion»** — ولم يكن للراكب مسار، **وهو ما كان
 * يمنع إقفال نموذج أمان البيانات**.
 *
 * **والبابُ بابُ الكبتن نفسُه** (`‎/account/deactivation`) لا ثانٍ بجانبه:
 * بابان يفعلان الشيءَ نفسَه يفترقان أوّلَ تعديل.
 *
 * ## وثلاثةُ أشياءَ تقولها الشاشةُ صراحةً لأنها **فعلٌ لا رجعةَ فيه**
 *
 * ١. **ما يُحذف بالاسم** — بطاقاتٌ وأماكنُ وتسجيلُ أجهزة، **لا «بياناتُك»**:
 *    من قرأ كلمةً عامّةً لا يعرف ما فقد حتى يفقده.
 * ٢. **وما يبقى بعلّته** — الدفترُ وشواهدُ الرحلات، **وفيها حقُّ طرفٍ آخر**
 *    شارك الرحلة. **وإخفاءُ ذلك يجعل «حذفاً» كلمةً تكذب.**
 * ٣. **وأنه طلبٌ يُراجَع** — زرٌّ يقول «أغلِق» ثم لا يُغلق فوراً يُقرأ عطباً.
 *
 * **ولا يُقال «ولا تسجيلَ بالرقم نفسه» وإن كان واقعاً اليوم** (قرارُ المالك
 * ٢٠٢٦-٠٩-٠٧): **حرقُ الرقم أبداً ليس سياسةً أرادها أحد** — والسجلُّ محفوظٌ
 * بمعرّفه لا برقمه. **والمنعُ المكتوبُ هو منعُ فتحِ طلبٍ ثانٍ** ما دام الأول
 * قيد المراجعة، وهو ما يحرسه فهرسٌ جزئيٌّ في القاعدة فعلاً.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  cancelDeactivation,
  getDeactivationState,
  requestDeactivation,
} from "@/api/endpoints";
import type { DeactivationState } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { Field } from "@/components/ui/Field";
import { useGoBack } from "@/lib/back";
import { cn } from "@/lib/utils";

/** **نصُّ المانع هنا والرمزُ في الخلفية** — الخلفيةُ لا تعرف من يقرأ.
 *
 * **و`wallet_balance` للراكب وحدَه بحكم الخلفية**: الكبتنُ له مسارُ سحب،
 * **وهذا البابُ نفسُه هو ما يُطلق محتجَزَه** — فمانعٌ يفترض مخرجاً لا يملكه
 * صاحبُه يُبطل البابَ الذي بُني له.
 */
const BLOCKER_TEXT: Record<string, string> = {
  active_ride: "رحلةٌ جارية — أنهِها أولاً",
  open_dispute: "نزاعٌ مفتوحٌ على دفعة",
  unpaid_charge: "رسمُ إلغاءٍ مستحقٌّ عليك",
  wallet_balance: "رصيدٌ في محفظتك — أنفقه أو حوّله",
  unpaid_advance: "سلفةٌ غيرُ مسدَّدة",
};

const STATUS_TEXT: Record<string, { text: string; tone: string }> = {
  pending: { text: "طلبُك قيد المراجعة", tone: "text-warn" },
  approved: { text: "أُغلق حسابُك", tone: "text-danger" },
  rejected: { text: "رُفض طلبُك", tone: "text-danger" },
  cancelled: { text: "سحبتَ الطلب", tone: "text-muted" },
};

export function CloseAccountScreen() {
  const goBack = useGoBack("/account");
  const [state, setState] = useState<DeactivationState | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    getDeactivationState()
      .then(setState)
      .catch((caught) =>
        setError(caught instanceof ApiError ? caught.message : "تعذّر التحميل"),
      );
  }, []);

  useEffect(load, [load]);

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر التنفيذ");
    } finally {
      setBusy(false);
    }
  }

  if (!state) {
    return (
      <div className="h-full bg-bg px-16 pt-safe">
        {error ? <ErrorNote message={error} /> : <Spinner />}
      </div>
    );
  }

  const pending = state.request?.status === "pending";

  return (
    <div className="scr h-full bg-bg px-16 pb-nav pt-safe">
      <div className="mb-16 mt-6 flex items-center gap-10">
        <button
          type="button"
          onClick={() => goBack()}
          aria-label="رجوع"
          className="pressable text-18 text-muted"
        >
          →
        </button>
        <h1 className="text-20 font-bold text-ink">إغلاق الحساب</h1>
      </div>

      {state.request ? (
        <section className="mb-12 card p-15">
          <p
            className={cn(
              "text-13.5 font-semibold",
              STATUS_TEXT[state.request.status]?.tone ?? "text-ink",
            )}
          >
            {STATUS_TEXT[state.request.status]?.text ?? state.request.status}
          </p>
          {state.request.review_note ? (
            <p className="mt-6 text-11.5 leading-snug text-muted">
              {state.request.review_note}
            </p>
          ) : null}
          {pending ? (
            <Button
              className="mt-12"
              variant="secondary"
              size="sm"
              loading={busy}
              onClick={() => void run(cancelDeactivation)}
            >
              اسحب الطلب
            </Button>
          ) : null}
        </section>
      ) : null}

      {state.blockers.length > 0 ? (
        <section className="mb-12 rounded-18 border border-warn bg-surface p-15">
          <p className="mb-8 text-13.5 font-semibold text-warn">
            لا يمكن الإغلاق الآن
          </p>
          <ul className="space-y-6">
            {state.blockers.map((item) => (
              <li key={item} className="text-12 leading-snug text-muted">
                • {BLOCKER_TEXT[item] ?? item}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {!pending && state.request?.status !== "approved" ? (
        <>
          <section className="mb-12 card p-15">
            <p className="text-11.5 leading-note text-muted">
              طلبٌ يراجعه مشرف. ولا يمكنك فتحُ طلبٍ ثانٍ ما دام الأولُ قيد
              المراجعة — ويمكنك سحبُه في أيِّ وقتٍ قبل البتّ فيه.
            </p>

            <p className="mt-14 text-13 font-bold text-ink">يُحذف نهائياً</p>
            <ul className="mt-6 space-y-5">
              <li className="text-11.5 leading-note text-muted">
                • بطاقاتُك المحفوظة
              </li>
              <li className="text-11.5 leading-note text-muted">
                • أماكنُك المحفوظة — المنزل والعمل وغيرها
              </li>
              <li className="text-11.5 leading-note text-muted">
                • تسجيلُ أجهزتك، فلا تصلك إشعارات
              </li>
            </ul>

            <p className="mt-14 text-13 font-bold text-ink">يبقى محفوظاً</p>
            <ul className="mt-6 space-y-5">
              <li className="text-11.5 leading-note text-muted">
                • حركاتُ محفظتك وسجلُّ رحلاتك ودفعاتُها — سجلٌّ ماليٌّ لا يُمحى،
                وفيه حقُّ طرفٍ آخر شارك الرحلة
              </li>
              <li className="text-11.5 leading-note text-muted">
                • اسمُك ورقمُك عليها وحدَها، ليبقى السجلُّ معروفَ صاحبه
              </li>
            </ul>
          </section>

          <section className="card p-15">
            <Field
              label="سبب الإغلاق — اختياري"
              value={reason}
              disabled={busy || state.blockers.length > 0}
              onChange={(event) => setReason(event.target.value)}
            />
            <Button
              className="mt-12"
              variant="danger"
              loading={busy}
              disabled={state.blockers.length > 0}
              onClick={() =>
                void run(() => requestDeactivation(reason.trim() || undefined))
              }
            >
              أرسِل طلبَ الإغلاق
            </Button>
          </section>
        </>
      ) : null}

      {error ? (
        <div className="mt-12">
          <ErrorNote message={error} />
        </div>
      ) : null}
    </div>
  );
}
