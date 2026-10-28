/** **العودةُ من صفحة الوسيط** (SPEC §٧٣-هـ المرحلة ٣) — `/wallet/pay/return?r=<الطلب>`، **بقطع شاشات المال نفسِها** (R16).
 *
 * **العودةُ ليست تأكيداً**: الوسيطُ يعيد المتصفّحَ إلى هنا في الحالين، **والخادمُ وحدَه يسأله عن الحقيقة** (`refresh`). فتسأل الشاشةُ
 * حتى يُحسم الطلب — ثمّ تقف وتعرض زرّاً، **ولا تقول «شُحن» قبل أن يقوله الخادم**.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { readPendingRide } from "@/lib/ride-topup";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { refreshPaymentRequest } from "@/api/endpoints";
import type { MyPaymentRequest } from "@/api/types";
import { useGoBack } from "@/lib/back";
import { play } from "@/lib/sound";
import { formatMoney } from "@/lib/utils";
import { Icon } from "@/taxo2";
import { CARD_PAGE_MINUTES, settledReturn } from "@/lib/pay-return";

import { BannerT2, BusyLabel, HeadT2 } from "./MoneyT2";
import { SupportLine } from "./PayDz";
import "./payrequest.css"; import { tr } from "@/lib/i18n";

/** **كم مرّةً تسأل وحدَها** قبل أن تترك السؤالَ لزرّ — ثلاثُ ثوانٍ بينها */
const AUTO_TRIES = 10;
const EVERY_MS = 3000;

/** **ما بقي من صفحة البطاقة** (SPEC §٨٤) — من فتح الدفعة، بالدقائق والثواني؛ و`null` حين انقضت */
function useCardPageLeft(createdAt: string | undefined): string | null {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);
  if (!createdAt) return null;
  const left = new Date(createdAt).getTime() + CARD_PAGE_MINUTES * 60_000 - now;
  if (left <= 0) return null;
  const seconds = Math.floor(left / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

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
      // **طلبُ رحلةٍ ينتظر هذا الشحن** (§٨٨/١) — الرئيسيةُ ترسله بسعره المثبَّت حين يغطّيه الرصيد
      if (row.status === "approved" && readPendingRide()) {
        navigate("/", { replace: true });
        return;
      }
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
    settledReturn();
    void ask();
  }, [ask]);
  const cardLeft = useCardPageLeft(request?.created_at);

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
          {/* **ما بقي من صفحة البطاقة** (SPEC §٨٤) — يُقال لمن لم يصل دفعُه بعد */}
          {request?.phase !== "processing" && cardLeft ? (
            <p className="t2-pr-done-text">
              {tr("صفحة البطاقة تنتهي خلال {0} تقريباً — أكمل الدفع هناك، أو ابدأ دفعةً جديدةً بعد انتهائها.", { 0: cardLeft })}
            </p>
          ) : null}
        </section>
      )}
      <BannerT2 tone="danger" message={error} />
      <div className="t2-m-actions">
        {/* **«حاول مرّةً أخرى» بالمبلغ والطريقة نفسَيهما** (§٧٦-ع/٢، المشكلة ٩) */}
        {request &&
        (request.status === "cancelled" ||
          request.status === "rejected" ||
          (request.phase === "unconfirmed" && tries.current >= AUTO_TRIES)) ? (
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
          className={
            request &&
            (request.status === "cancelled" ||
              request.status === "rejected" ||
              (request.phase === "unconfirmed" && tries.current >= AUTO_TRIES))
              ? "t2-button t2-m-cta"
              : "t2-button primary t2-m-cta"
          }
          onClick={() => navigate("/wallet", { replace: true })}
        >
          {tr("إلى المحفظة")}
        </button>
      </div>
      {/* **سطرُ الدعم** (SPEC §٨٢-أ/٧) */}
      <SupportLine to="/account/help" />
    </div>
  );
}
