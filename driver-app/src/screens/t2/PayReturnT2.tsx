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
import { digits } from "@/lib/utils";
import { Icon } from "@/taxo2";

import "./money.css";
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
              ? tr("دُفع {0} {1} وبدأ اشتراكك.", { 0: digits(credited), 1: CURRENCY_LABEL[request.currency] })
              : tr("أُضيف {0} {1} إلى محفظتك.", { 0: digits(credited), 1: CURRENCY_LABEL[request.currency] })}
          </p>
        </div>
      ) : request && request.status !== "pending" ? (
        <div className="t2-wdl-card t2-pr-done">
          <Icon name="error" />
          <h2 className="t2-pr-done-title">{tr("لم تتمّ الدفعة")}</h2>
          <p className="t2-pr-done-text">
            {request.rejection_reason ?? request.cancel_reason ?? tr("لم يُؤخذ منك شيء — أعد المحاولة أو اختر طريقةً أخرى.")}
          </p>
        </div>
      ) : (
        <div className="t2-wdl-card t2-pr-done" aria-live="polite">
          <Icon name="hourglass_top" />
          <h2 className="t2-pr-done-title">{tr("ننتظر تأكيد الدفع")}</h2>
          <p className="t2-pr-done-text">
            {tries.current >= AUTO_TRIES
              ? tr("لم يصل التأكيد بعد. إن كنت دفعت فسيُضاف وحدَه حين يصل — وتراه في طلبات المحفظة.")
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
      <button
        type="button"
        className="t2-clq-cta t2-pr-gap"
        onClick={() => navigate(subscription && request?.status === "approved" ? "/subscription" : "/wallet", { replace: true })}
      >
        {subscription && request?.status === "approved" ? tr("إلى اشتراكي") : tr("إلى المحفظة")}
      </button>
    </div>
  );
}
