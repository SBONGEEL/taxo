/** إلغاءُ تفعيل الحساب (البند ١٣) — طلبٌ يُراجَع لا مفتاحٌ يُرفع.
 *
 * **وموضعُها «حسابي» لا «الإعدادات»**: الإعداداتُ كلُّها تخصّ **الجهاز**
 * (أصواتٌ ومظهر)، وهذا يخصّ **الحساب** — نفسُ قاعدةِ الفصل في تطبيق الراكب.
 *
 * وثلاثةُ أشياءَ تقولها الشاشةُ صراحةً، وكلٌّ منها يمنع سوءَ فهمٍ يكلّف تذكرة:
 *
 * ١. **المحتجَزُ برقمه**: من يرى رصيداً لا يستطيع سحبَه كلَّه يستحق أن يعرف كم
 *    منه ولماذا — لا جملةً عامة عن «رصيدٍ غير متاح».
 * ٢. **والموانعُ كلُّها معاً** لا أوّلُها: من أزال مانعاً ثم صُدم بثانٍ يقرأ
 *    الرفضَ مماطلة.
 * ٣. **وأنه طلبٌ يُراجَع**: زرٌّ يقول «أغلِق حسابي» ثم لا يُغلقه فوراً يُقرأ
 *    عطباً. فالنصُّ يقول إن مشرفاً ينظر فيه، وإن الرصيد يُصرف بعد الموافقة.
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
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { useGoBack } from "@/lib/back";
import { digits, cn } from "@/lib/utils";
import type { Currency } from "@/api/types";

/** **نصُّ المانع من الواجهة والرمزُ من الخلفية** — نفسُ قاعدةِ بناء نصِّ
 *  الإشعار من `data`: الخلفيةُ لا تعرف من يقرأ. */
const BLOCKER_TEXT: Record<string, string> = {
  active_ride: "لديك رحلةٌ جارية — أنهِها أولاً",
  open_dispute: "عليك نزاعٌ مفتوح لم يُحسم بعد",
  unpaid_advance: "عليك سلفةٌ غيرُ مسدَّدة",
};

const STATUS_TEXT: Record<string, { text: string; tone: string }> = {
  pending: { text: "طلبُك قيد المراجعة", tone: "text-warn" },
  approved: { text: "أُلغي تفعيلُ حسابك", tone: "text-danger" },
  rejected: { text: "رُفض طلبُك", tone: "text-danger" },
  cancelled: { text: "عدلتَ عن الطلب", tone: "text-muted" },
};

export function DeactivationScreen() {
  const goBack = useGoBack();
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
  const currency = CURRENCY_LABEL[state.currency as Currency] ?? state.currency;
  const reserve = Number(state.reserve_amount);

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
        <h1 className="text-20 font-bold text-ink">إلغاء تفعيل الحساب</h1>
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
              تراجَع عن الطلب
            </Button>
          ) : null}
        </section>
      ) : null}

      {reserve > 0 ? (
        <section className="mb-12 card p-15">
          <p className="text-13.5 font-semibold text-ink">الرصيد المحتجَز</p>
          <p className="mt-4 text-18 font-bold text-ink">
            {digits(state.reserve_amount)}{" "}
            <span className="text-12 font-medium text-muted">{currency}</span>
          </p>
          <p className="mt-6 text-11.5 leading-snug text-muted">
            يبقى في محفظتك ولا يدخل المتاح للسحب. ويُصرف كاملاً بعد الموافقة على
            إلغاء التفعيل.
          </p>
        </section>
      ) : null}

      {state.blockers.length > 0 ? (
        <section className="mb-12 rounded-18 border border-warn bg-surface p-15">
          <p className="mb-8 text-13.5 font-semibold text-warn">
            لا يمكن الطلبُ الآن
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
        <section className="card p-15">
          <p className="mb-4 text-13.5 font-semibold text-ink">طلبُ الإغلاق</p>
          <p className="mb-12 text-11.5 leading-snug text-muted">
            يراجعه مشرفٌ قبل التنفيذ. وبعد الموافقة تتوقف الطلبات ويُصرف رصيدُك
            كاملاً — ولا يعود حسابُك للعمل إلا باعتمادٍ جديد.
          </p>
          <Field
            label="السبب (اختياري)"
            value={reason}
            disabled={busy || state.blockers.length > 0}
            onChange={(event) => setReason(event.target.value)}
          />
          <Button
            className="mt-12"
            variant="danger"
            loading={busy}
            disabled={state.blockers.length > 0}
            onClick={() => void run(() => requestDeactivation(reason.trim() || undefined))}
          >
            أرسِل طلبَ الإغلاق
          </Button>
        </section>
      ) : null}

      {error ? (
        <div className="mt-12">
          <ErrorNote message={error} />
        </div>
      ) : null}
    </div>
  );
}
