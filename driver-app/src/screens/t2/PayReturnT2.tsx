/** **العودةُ من صفحة الوسيط للكبتن** (SPEC §٧٣-هـ المرحلة ٣) — `/wallet/pay/return?r=<الطلب>`، **بقطع شاشات مال الكبتن** (رأسُ C10،
 * وزرُّ C21).
 *
 * **العودةُ ليست تأكيداً**: الوسيطُ يعيد المتصفّحَ إلى هنا في الحالين، **والخادمُ وحدَه يسأله عن الحقيقة** (`refresh`). فتسأل الشاشةُ
 * حتى يُحسم الطلب — ثمّ تقف وتعرض زرّاً. **والاشتراكُ يُقال اشتراكاً**: دفعتُه شحنٌ ثمّ شراءٌ في معاملةٍ واحدة على الخادم.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { cancelPaymentRequest, getMySubscription, refreshPaymentRequest } from "@/api/endpoints";
import type { MyPaymentRequest } from "@/api/types";
import { useGoBack } from "@/lib/back";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { digits, formatAmount } from "@/lib/utils";
import { Celebrate, Icon } from "@/taxo2";
import { CARD_PAGE_MINUTES, openedRequest, settledReturn } from "@/lib/pay-return";
import { announceFrameReturn } from "@/lib/sofizpay-cvv";

import "./money.css";
import { SupportLine } from "./PayDz";
import "./payrequest.css"; import { tr } from "@/lib/i18n";

/** **كم مرّةً تسأل وحدَها** قبل أن تترك السؤالَ لزرّ — ثلاثُ ثوانٍ بينها */
const AUTO_TRIES = 10;
const EVERY_MS = 3000;
/** **ثمّ يسأل أبطأ ربعَ ساعة** (البطاقةُ المصرفية، أمرُ المالك ٢٠٢٦-١١-٢٣: «A late IPN means keep checking») — كلَّ عشرين ثانية */
const SLOW_TRIES = 45;
const SLOW_EVERY_MS = 20_000;

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
  // **وسيطٌ يعيد بلا `r`** (Digistore24: صفحةُ شكرٍ واحدة) — الطلبُ الذي فُتحت صفحتُه من هذا الجهاز، يُقرأ قبل أن يُنسى
  const [stored] = useState(() => openedRequest());
  const requestId = params.get("r") ?? stored;
  const [ends, setEnds] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
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
    settledReturn();
    // **داخل إطارنا؟** (§٨٥/٩) — يُبلَغ الأبُ فيأخذ صاحبَه إلى هنا خارجَ الإطار
    announceFrameReturn(requestId);
    void ask();
  }, [ask, requestId]);
  const cardLeft = useCardPageLeft(request?.created_at);

  const pending = request === null || request.status === "pending";
  const card = request?.gateway_name === "البطاقة المصرفية";
  useEffect(() => {
    if (!pending || error) return;
    const slow = card && tries.current >= AUTO_TRIES;
    if (tries.current >= AUTO_TRIES + (card ? SLOW_TRIES : 0)) return;
    const timer = window.setTimeout(() => {
      tries.current += 1;
      void ask();
    }, slow ? SLOW_EVERY_MS : EVERY_MS);
    return () => window.clearTimeout(timer);
  }, [pending, error, request, ask, card]);

  const subscription = request?.purpose === "subscription";
  // **تاريخُ انتهاء الاشتراك** على شاشة النجاح (أمرُ المالك ٢٠٢٦-١١-٢٣) — من الخادم كما هو، بأرقامٍ لاتينيّة
  useEffect(() => {
    if (!subscription || request?.status !== "approved") return;
    let alive = true;
    getMySubscription()
      .then((mine) => {
        if (!alive || !mine.coverage_until) return;
        const at = new Date(mine.coverage_until);
        setEnds(digits(`${at.getFullYear()}/${String(at.getMonth() + 1).padStart(2, "0")}/${String(at.getDate()).padStart(2, "0")}`));
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [subscription, request?.status]);

  async function cancelIt() {
    if (!requestId) return;
    setCancelling(true);
    try {
      setRequest(await cancelPaymentRequest(requestId));
      setError(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : tr("تعذّر الإلغاء — أعد المحاولة"));
    } finally {
      setCancelling(false);
    }
  }
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
          <Celebrate />
          <Icon name="check_circle" />
          <h2 className="t2-pr-done-title">
            {subscription ? (card ? tr("تم الدفع وتفعيل اشتراكك") : tr("فُعّل اشتراكك")) : tr("شُحن رصيدك")}
          </h2>
          <p className="t2-pr-done-text">
            {subscription
              ? tr("دُفع {0} {1} وبدأ اشتراكك.", { 0: formatAmount(credited, request.currency), 1: CURRENCY_LABEL[request.currency] })
              : tr("أُضيف {0} {1} إلى محفظتك.", { 0: formatAmount(credited, request.currency), 1: CURRENCY_LABEL[request.currency] })}
          </p>
          {subscription && ends ? <p className="t2-pr-done-text">{tr("اشتراكك فعّال حتى {0}", { 0: ends })}</p> : null}
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
            {request?.phase === "processing" ? tr("وصل دفعُك ويُعالَج") : card ? tr("جارٍ تأكيد الدفع…") : tr("ننتظر تأكيد الدفع")}
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
      {/* **«لم أدفع — ألغِ هذه الدفعة»** (البطاقةُ المصرفية) — لمن عاد ولم يدفع: لا شيءَ يُقيَّد، **وإن وصل دفعُه بعدُ قُيِّد** (الخادمُ يقبل
          المتأخّرَ الموقَّع) */}
      {pending && card && request && request.phase !== "processing" ? (
        <button type="button" className="t2-link t2-pr-gap" disabled={cancelling} onClick={() => void cancelIt()}>
          {cancelling ? tr("جارٍ…") : tr("لم أدفع — ألغِ هذه الدفعة")}
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
      {/* **سطرُ Digistore24 على صفحة الشكر** — يشترطه لحفظ المنتج بنصّه الإنجليزيّ («The debit will be performed by Digistore24.com»)،
          والعائدُ منه يحمل `via=ds24` (رابطُ الشكر في منتجاته الثلاثة) */}
      {params.get("via") === "ds24" ? (
        <p className="t2-pr-done-text t2-pr-gap">
          {tr("يتمّ الخصمُ بواسطة Digistore24.com")}
          <br />
          <span lang="en" dir="ltr">
            The debit will be performed by Digistore24.com
          </span>
        </p>
      ) : null}
      {/* **سطرُ الدعم** (SPEC §٨٢-أ/٧) — ولا قناةَ دعمٍ في تطبيق الكبتن غيرُ «أرسل ملاحظة» */}
      <SupportLine to="/account/feedback" />
    </div>
  );
}
