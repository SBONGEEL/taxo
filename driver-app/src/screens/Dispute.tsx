/** فتح نزاع — TAXO 2.0 «C18» (`design/t2-new/captain/C18-*.dc.html`) — SPEC القسم 6.2، **في المظهرين والنسائيّ**.
 *
 * **على كليك وحدها**، وأسبابُه أسبابُ كليك لا أسبابُ الكاش: الراكب هنا *يقول* إنه حوّل، والحوالةُ إما لم تصل، أو وصلت ناقصةً، أو
 * وصلت باسمٍ لا يطابق ما اتُّفق عليه. أسبابُ التصميم القديم الثلاثة («لم يدفع إطلاقاً»، «نزل وغادر دون دفع») مكتوبةٌ لرحلة كاش لا
 * نزاعَ فيها أصلاً — انحرافٌ مسجّلٌ في `DESIGN-DECISIONS.md`.
 *
 * والسببُ نصٌّ حرّ في الخلفية (`reason: str`, 3–255): فالخياراتُ الثلاثة تُملي النص وحقلُ الملاحظة يُلحق به، ولا يذهب إلى الإدارة
 * رمزٌ بلا كلام.
 *
 * ومرجعُ الحوالة — ما ولّده TAXO وما أدخله الراكب — يُعرض هنا لا زينةً: به يبحث الكبتن في كشف حسابه قبل أن يفتح نزاعاً لم يقع.
 *
 * **والمنطقُ هو هو حرفاً** (الطلبان، والنصُّ الواحد، والزرُّ معطَّلٌ حتى يُختار سبب). **وما تغيّر طبقةُ العرض**: بطاقةُ الدفعة بسطح
 * C08، **والأسبابُ صفوفُ «باقتك القادمة» في C10** (أقربُ اختيارٍ مرسوم)، والملاحظةُ حقلُ الدخول، والإرسالُ في القاع بلون الخطر كما كان.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { disputePayment, getRide, getRidePayments } from "@/api/endpoints";
import type { Payment, Ride } from "@/api/types";
import { Spinner } from "@/components/ui/Feedback";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { digits } from "@/lib/utils";
import { useGoBack } from "@/lib/back";
import { Icon } from "@/taxo2";

import { startOfToday, whenParts } from "./t2/when";

import "./t2/fields.css";
import "./t2/rides.css";

/** **مُصدَّرةٌ لـ«ركّابٌ ينتظرون تأكيدك»** (`screens/t2/UnconfirmedT2.tsx`، §٦٤-ز): «لم تصلني» هناك بالأسباب نفسِها حرفاً —
 *  أسبابٌ تُكتب مرّتين تفترق أوّلَ تعديل، والإدارةُ تقرأ النصَّ من البابين. */
export const CLIQ_DISPUTE_REASONS = [
  "لم تصلني الحوالة إطلاقاً",
  "وصلتني حوالة أقل من الأجرة",
  "المرجع الذي أدخله الراكب لا يطابق أي حوالة وصلتني",
];

export function DisputeScreen() {
  const { rideId = "" } = useParams();
  const navigate = useNavigate();
  const goBack = useGoBack();

  const [ride, setRide] = useState<Ride | null>(null);
  const [payment, setPayment] = useState<Payment | null>(null);
  const [reason, setReason] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    const [one, paid] = await Promise.all([
      getRide(rideId),
      getRidePayments(rideId),
    ]);
    setRide(one);
    setPayment(
      paid.payments.find(
        (row) => row.method === "cliq" && row.status === "pending",
      ) ?? null,
    );
  }, [rideId]);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة الدفعة",
      ),
    );
  }, [load]);

  async function submit() {
    if (!payment || !reason) return;
    setBusy(true);
    setError(null);
    try {
      // نصٌّ واحد يقرؤه إنسان: السبب المختار ثم ملاحظةُ الكبتن إن كتبها
      const text = note.trim() ? `${reason} — ${note.trim()}` : reason;
      await disputePayment(payment.id, text.slice(0, 255));
      navigate(`/rides/${rideId}`, { replace: true });
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر فتح النزاع",
      );
    } finally {
      setBusy(false);
    }
  }

  const head = (
    <div className="t2-head">
      <button
        type="button"
        className="t2-back"
        aria-label="رجوع"
        onClick={() => goBack()}
      >
        <Icon name="arrow_forward" />
      </button>
      <h1 className="t2-title">فتح نزاع</h1>
    </div>
  );

  if (!ride) {
    return (
      <div className="t2 t2-dsp">
        {head}
        {error ? (
          <p className="t2-note danger" role="alert">
            <Icon name="error" fill />
            {error}
          </p>
        ) : (
          <div className="t2-dsp-wait">
            <Spinner />
          </div>
        )}
      </div>
    );
  }

  const currency = CURRENCY_LABEL[ride.currency];
  const when = whenParts(ride.created_at, startOfToday());

  return (
    <div className="t2 t2-dsp scr">
      {head}

      <p className="t2-dsp-lede">
        افتح نزاعاً إن لم تصلك حوالة الرحلة. تفصله الإدارة: مدفوعة أو غير
        مدفوعة.
      </p>

      <div className="t2-dsp-card">
        <div className="t2-dsp-top">
          <span className="t2-dsp-when">
            {digits(when.day)} · <span dir="ltr">{digits(when.time)}</span>
          </span>
          <span className="t2-dsp-sum">
            <span className="t2-dsp-num" dir="ltr">
              {digits(payment?.amount ?? ride.final_fare ?? ride.current_fare)}
            </span>{" "}
            <span className="t2-dsp-cur">{currency}</span>
          </span>
        </div>
        {payment?.cliq_reference || payment?.cliq_transfer_reference ? (
          <div className="t2-dsp-refs">
            {payment?.cliq_reference ? (
              <>
                <span className="t2-dsp-ref-k">مرجع TAXO</span>
                <span className="t2-dsp-ref-v" dir="ltr">
                  {payment.cliq_reference}
                </span>
              </>
            ) : null}
            {payment?.cliq_transfer_reference ? (
              <>
                <span className="t2-dsp-ref-k">المرجع الذي أدخله الراكب</span>
                <span className="t2-dsp-ref-v" dir="ltr">
                  {payment.cliq_transfer_reference}
                </span>
              </>
            ) : null}
          </div>
        ) : null}
      </div>

      {payment === null ? (
        <p className="t2-note danger" role="alert">
          <Icon name="error" fill />
          لا دفعة كليك بانتظار تأكيدك على هذه الرحلة. النزاع متاح على دفعات كليك
          وحدها.
        </p>
      ) : (
        <div className="t2-dsp-form">
          <div
            className="t2-dsp-reasons"
            role="radiogroup"
            aria-label="سبب النزاع"
          >
            {CLIQ_DISPUTE_REASONS.map((option) => (
              <button
                key={option}
                type="button"
                role="radio"
                aria-checked={reason === option}
                className={
                  reason === option ? "t2-dsp-reason on" : "t2-dsp-reason"
                }
                onClick={() => setReason(option)}
              >
                <span className="t2-dsp-radio" aria-hidden="true" />
                <span>{option}</span>
              </button>
            ))}
          </div>

          <div className="t2-dsp-note">
            <label className="t2-fld-label" htmlFor="dispute-note">
              ملاحظة
            </label>
            <input
              id="dispute-note"
              className="t2-fld"
              placeholder="أضف تفصيلاً يساعد الإدارة…"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              maxLength={200}
            />
          </div>

          <div className="t2-dsp-push" />

          {error ? (
            <p className="t2-note danger" role="alert">
              <Icon name="error" fill />
              {error}
            </p>
          ) : null}

          <button
            type="button"
            className="t2-dsp-send"
            disabled={reason === null || busy}
            onClick={() => void submit()}
          >
            {busy ? "…" : "إرسال النزاع"}
          </button>

          <p className="t2-dsp-fine">
            المسار الفعلي مسجَّلٌ مع الرحلة، وتراه الإدارة حين تفصل في النزاع.
          </p>
        </div>
      )}
    </div>
  );
}
