/** **العودةُ من صفحة الوسيط** (SPEC §٧٣-هـ المرحلة ٣) — `/wallet/pay/return?r=<الطلب>`، **بقطع شاشات المال نفسِها** (R16).
 *
 * **العودةُ ليست تأكيداً**: الوسيطُ يعيد المتصفّحَ إلى هنا في الحالين، **والخادمُ وحدَه يسأله عن الحقيقة** (`refresh`). فتسأل الشاشةُ
 * حتى يُحسم الطلب — ثمّ تقف وتعرض زرّاً، **ولا تقول «شُحن» قبل أن يقوله الخادم**.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { refreshPaymentRequest } from "@/api/endpoints";
import type { MyPaymentRequest } from "@/api/types";
import { useGoBack } from "@/lib/back";
import { play } from "@/lib/sound";
import { formatMoney } from "@/lib/utils";
import { Icon } from "@/taxo2";

import { BannerT2, BusyLabel, HeadT2 } from "./MoneyT2";
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
  const announced = useRef(false);

  const ask = useCallback(async () => {
    if (!requestId) return;
    setBusy(true);
    try {
      const row = await refreshPaymentRequest(requestId);
      setRequest(row);
      setError(null);
      if (row.status === "approved" && !announced.current) {
        announced.current = true;
        play("topup");
      }
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

  const credited = request ? (request.credited_amount ?? request.amount) : null;

  return (
    <div className="t2 t2-m-page">
      <HeadT2 title={tr("نتيجة الدفع")} onBack={goBack} />
      {!requestId ? (
        <BannerT2 tone="danger" message={tr("لا دفعةَ في هذا الرابط — افتح المحفظة وانظر طلباتك")} />
      ) : request && request.status === "approved" ? (
        <section className="t2-m-card t2-pr-done">
          <Icon name="check_circle" />
          <h2 className="t2-pr-done-title">{tr("شُحن رصيدك")}</h2>
          <p className="t2-pr-done-text">{tr("أُضيف")}{" "}{formatMoney(credited ?? "0", request.currency)}{" "}{tr("إلى محفظتك.")}</p>
        </section>
      ) : request && request.status === "cancelled" ? (
        // **الإلغاءُ ليس فشلاً** (§٧٦-ع/٢، المشكلة ٩) — كان بأيقونة خطأٍ حمراءَ لإلغاءٍ اختاره صاحبُه
        <section className="t2-m-card t2-pr-done neutral">
          <Icon name="block" />
          <h2 className="t2-pr-done-title">{tr("أُلغيت الدفعة")}</h2>
          <p className="t2-pr-done-text">
            {request.cancel_reason ? `${request.cancel_reason}. ` : ""}
            {tr("لم يُخصم منك شيء.")}
          </p>
        </section>
      ) : request && request.status !== "pending" ? (
        <section className="t2-m-card t2-pr-done">
          <Icon name="error" />
          <h2 className="t2-pr-done-title">{tr("لم تتمّ الدفعة")}</h2>
          <p className="t2-pr-done-text">
            {request.rejection_reason ? `${request.rejection_reason}. ` : ""}
            {tr("لم يُخصم منك شيء — حاول مرّةً أخرى أو اختر طريقةً أخرى.")}
          </p>
        </section>
      ) : (
        <section className="t2-m-card t2-pr-done" aria-live="polite">
          <Icon name="hourglass_top" />
          <h2 className="t2-pr-done-title">{tr("ننتظر تأكيد الدفع")}</h2>
          <p className="t2-pr-done-text">
            {tries.current >= AUTO_TRIES
              ? tr("لم يصل التأكيد بعد. إن كنت دفعت فسيُضاف وحدَه حين يصل — وتراه في طلبات المحفظة.")
              : tr("نسأل الوسيطَ عن دفعتك — لحظات.")}
          </p>
        </section>
      )}
      <BannerT2 tone="danger" message={error} />
      <div className="t2-m-actions">
        {/* **«حاول مرّةً أخرى» بالمبلغ والطريقة نفسَيهما** (§٧٦-ع/٢، المشكلة ٩) */}
        {request && (request.status === "cancelled" || request.status === "rejected") ? (
          <button
            type="button"
            className="t2-button primary t2-m-cta"
            onClick={() =>
              navigate("/wallet/pay", { replace: true, state: { amount: request.amount, methodId: request.provider_id ?? undefined } })
            }
          >
            {tr("حاول مرّةً أخرى")}
          </button>
        ) : null}
        {pending && requestId ? (
          <button type="button" className="t2-button t2-m-cta" disabled={busy} aria-busy={busy} onClick={() => void ask()}>
            <BusyLabel busy={busy}>{tr("تحقّق الآن")}</BusyLabel>
          </button>
        ) : null}
        <button
          type="button"
          className={request && (request.status === "cancelled" || request.status === "rejected") ? "t2-button t2-m-cta" : "t2-button primary t2-m-cta"}
          onClick={() => navigate("/wallet", { replace: true })}
        >
          {tr("إلى المحفظة")}
        </button>
      </div>
    </div>
  );
}
