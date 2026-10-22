/** **العودةُ من صفحة الوسيط للكبتن** (SPEC §٧٣-هـ المرحلة ٣) — `/wallet/pay/return?r=<الطلب>`، **بقطع شاشات مال الكبتن** (رأسُ C10،
 * وزرُّ C21).
 *
 * **العودةُ ليست تأكيداً**: الوسيطُ يعيد المتصفّحَ إلى هنا في الحالين، **والخادمُ وحدَه يسأله عن الحقيقة** (`refresh`). فتسأل الشاشةُ
 * حتى يُحسم الطلب — ثمّ تقف وتعرض زرّاً. **والاشتراكُ يُقال اشتراكاً**: دفعتُه شحنٌ ثمّ شراءٌ في معاملةٍ واحدة على الخادم.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { refreshPaymentRequest } from "@/api/endpoints";
import type { MyPaymentRequest } from "@/api/types";
import { useGoBack } from "@/lib/back";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { formatAmount } from "@/lib/utils";
import { Icon } from "@/taxo2";

import "./money.css";
import { SupportLine } from "./PayDz";
import "./payrequest.css"; import { tr } from "@/lib/i18n";

/** **كم مرّةً تسأل وحدَها** قبل أن تترك السؤالَ لزرّ — ثلاثُ ثوانٍ بينها */
const AUTO_TRIES = 10;
const EVERY_MS = 3000;

export function PayReturnT2Screen() {
  const goBack = useGoBack("/wallet");
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const requestId = params.get("r");
  const [request, setRequest] = useState<MyPaymentRequest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const tries = useRef(0);

  const ask = useCallback(async () => {
    if (!requestId) return;
    setBusy(true);
    try {
      setRequest(await refreshPaymentRequest(requestId));
      setError(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : tr("تعذّر السؤال عن الدفعة — أعد المحاولة"));
    } finally {
      setBusy(false);
    }
  }, [requestId]);

  useEffect(() => {
    void ask();
  }, [ask]);

  const pending = request === null || request.status === "pending";
  useEffect(() => {
    if (!pending || error || tries.current >= AUTO_TRIES) return;
    const timer = window.setTimeout(() => {
      tries.current += 1;
      void ask();
    }, EVERY_MS);
    return () => window.clearTimeout(timer);
  }, [pending, error, request, ask]);

  const subscription = request?.purpose === "subscription";
  const credited = request ? (request.credited_amount ?? request.amount) : "0";

  return (
    <div className="t2 t2-clq-page scr">
      <div className="t2-head">
        <button type="button" className="t2-back" aria-label={tr("رجوع")} onClick={() => goBack()}>
          <Icon name="arrow_forward" />
        </button>
        <h1 className="t2-title">{tr("نتيجة الدفع")}</h1>
      </div>

      {!requestId ? (
        <p className="t2-note danger" role="alert">
          <Icon name="error" fill />
          {tr("لا دفعةَ في هذا الرابط — افتح المحفظة وانظر طلباتك")}
        </p>
      ) : request && request.status === "approved" ? (
        <div className="t2-wdl-card t2-pr-done">
          <Icon name="check_circle" />
          <h2 className="t2-pr-done-title">{subscription ? tr("فُعّل اشتراكك") : tr("شُحن رصيدك")}</h2>
          <p className="t2-pr-done-text">
            {subscription
              ? tr("دُفع {0} {1} وبدأ اشتراكك.", { 0: formatAmount(credited, request.currency), 1: CURRENCY_LABEL[request.currency] })
              : tr("أُضيف {0} {1} إلى محفظتك.", { 0: formatAmount(credited, request.currency), 1: CURRENCY_LABEL[request.currency] })}
          </p>
        </div>
      ) : request && request.status === "cancelled" ? (
        // **الإلغاءُ ليس فشلاً** (§٧٦-ع/٢، المشكلة ٩) — كان بأيقونة خطأٍ لإلغاءٍ اختاره صاحبُه
        <div className="t2-wdl-card t2-pr-done neutral">
          <Icon name="block" />
          <h2 className="t2-pr-done-title">{tr("أُلغيت الدفعة")}</h2>
          <p className="t2-pr-done-text">
            {request.cancel_reason ? `${request.cancel_reason}. ` : ""}
            {subscription ? tr("لم يُخصم منك شيء ولم يتغيّر اشتراكك.") : tr("لم يُخصم منك شيء.")}
          </p>
        </div>
      ) : request && request.status !== "pending" ? (
        <div className="t2-wdl-card t2-pr-done">
          <Icon name="error" />
          <h2 className="t2-pr-done-title">{tr("لم تتمّ الدفعة")}</h2>
          <p className="t2-pr-done-text">
            {request.rejection_reason ? `${request.rejection_reason}. ` : ""}
            {tr("لم يُخصم منك شيء — حاول مرّةً أخرى أو اختر طريقةً أخرى.")}
          </p>
        </div>
      ) : (
        <div className="t2-wdl-card t2-pr-done" aria-live="polite">
          <Icon name="hourglass_top" />
          {/* **أطوارُ §٨٢-أ/٢**: «وصل ويُعالَج» لا يُسأل صاحبُه أن يدفع ثانية، و«لم نتأكّد» لا يحجبه */}
          <h2 className="t2-pr-done-title">
            {request?.phase === "processing" ? tr("وصل دفعُك ويُعالَج") : tr("ننتظر تأكيد الدفع")}
          </h2>
          <p className="t2-pr-done-text">
            {request?.phase === "processing"
              ? tr("يُضاف تلقائياً حين يكتمل — لا تدفع مرّةً أخرى لهذا.")
              : tries.current >= AUTO_TRIES
                ? tr("لم نتأكّد من دفعتك بعد. إن خُصم المبلغ فسيُضاف وحدَه حين يصل التأكيد — ويمكنك أن تدفع من جديد الآن.")
                : tr("نسأل الوسيطَ عن دفعتك — لحظات.")}
          </p>
        </div>
      )}

      {error ? (
        <p className="t2-note danger" role="alert">
          <Icon name="error" fill />
          {error}
        </p>
      ) : null}
      {pending && requestId ? (
        <button
          type="button"
          className="t2-button secondary t2-pr-gap-lg"
          disabled={busy}
          aria-busy={busy}
          onClick={() => void ask()}
        >
          {busy ? tr("يُسأل…") : tr("تحقّق الآن")}
        </button>
      ) : null}
      {/* **«حاول مرّةً أخرى» بالخطّة أو المبلغ والطريقةِ نفسِها** (§٧٦-ع/٢، المشكلة ٩) */}
      {request &&
      (request.status === "cancelled" ||
        request.status === "rejected" ||
        (request.phase === "unconfirmed" && tries.current >= AUTO_TRIES)) ? (
        <button
          type="button"
          className="t2-clq-cta t2-pr-gap"
          onClick={() =>
            subscription
              ? navigate("/subscription", { replace: true })
              : navigate("/wallet/pay", { replace: true, state: { amount: request.amount, methodId: request.provider_id ?? undefined } })
          }
        >
          {tr("حاول مرّةً أخرى")}
        </button>
      ) : null}
      {/* **والاشتراكُ يعود إلى الاشتراك في كلِّ حال** — كانت النتيجةُ تعيد إلى المحفظة وهو جاء من الاشتراك */}
      <button
        type="button"
        className={
          request &&
          (request.status === "cancelled" ||
            request.status === "rejected" ||
            (request.phase === "unconfirmed" && tries.current >= AUTO_TRIES))
            ? "t2-button secondary t2-pr-gap"
            : "t2-clq-cta t2-pr-gap"
        }
        onClick={() => navigate(subscription ? "/subscription" : "/wallet", { replace: true })}
      >
        {subscription ? tr("إلى اشتراكي") : tr("إلى المحفظة")}
      </button>
      {/* **سطرُ الدعم** (SPEC §٨٢-أ/٧) — ولا قناةَ دعمٍ في تطبيق الكبتن غيرُ «أرسل ملاحظة» */}
      <SupportLine to="/account/feedback" />
    </div>
  );
}
