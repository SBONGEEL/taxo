/** شاشة التحصيل — SPEC القسم 12/4 و6/1، وشكلُها من `DESIGN.md` §5.3.
 *
 * **أخطرُ شاشةٍ في التطبيق، والخطرُ فيها التباسٌ واحد**: بين «هذا ما تقبضه
 * بيدك الآن» و«هذا ما دخل محفظتك». الرقمان يبدوان واحداً وليسا واحداً، والخلطُ
 * بينهما يجعل الكبتن يظن أنه قُيّد له ما لم يُقيَّد، أو ينتظر في محفظته مالاً
 * هو في جيبه أصلاً.
 *
 * والفرقُ قاعدةٌ في القاعدة لا تفصيلُ عرض (`models/payment.py`):
 *
 * | القناة | أين المال | محفظة الكبتن |
 * |---|---|---|
 * | كاش، كليك | **في يد الكبتن** — لا يمر بالمنصة | لا `ride_earning` إطلاقاً |
 * | محفظة، بطاقة | مرّ بالمنصة | `ride_earning` كامل الأجرة |
 *
 * **والعمولة تُخصم من محفظته في الحالتين** حين يكون نطاقُها `all_rides` —
 * فرحلةُ الكاش قد **تُنقص** رصيدَه لا تزيده. ولذلك تقول الشاشة أين المال
 * صراحةً في كل حال، ولا تكتفي برقمٍ كبير.
 *
 * وما تعرضه ليس حساباً من عندها: `final_fare` و`outstanding` من
 * `GET /payments/rides/{id}/payments` — التسعير في الخلفية حصراً (القسم 14).
 * ولا تضرب هذه الشاشة رقماً في رقم: نسبةُ العمولة تُعرض نسبةً، ومبلغُها يخرج
 * من الدفتر لا من ضربٍ في الواجهة.
 *
 * **وتنتظر دفعةً ولا تُنشئ واحدة**: القناة قرارُ الراكب (القسم 6)، وتأكيدُ
 * الكبتن هو ما يُثبّت دفعة الكاش.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { confirmPayment, getRidePayments } from "@/api/endpoints";
import type { Payment, PaymentMethod, Ride, RidePayments } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { METHOD_LABEL, trimDistance } from "@/lib/rideFormat";
import { digits } from "@/lib/utils";

/** ما لا يمر بالمنصة فيبقى في يد الكبتن (`DIRECTLY_COLLECTED_METHODS`).
 *
 * **وانتظارُ تأكيده حالُه `pending`** لا حالٌ باسمه: `PaymentStatus` خمسُ قيم،
 * والذي يفرّق «دفعةٌ تنتظر المزود» عن «دفعةٌ تنتظر قولي» هو **القناة**. */
const IN_HAND: ReadonlySet<PaymentMethod> = new Set(["cash", "cliq"]);

interface Props {
  ride: Ride;
  currencyLabel: string;
  currencyFull: string;
  onDone: () => void;
}

export function CollectScreen({
  ride,
  currencyLabel,
  currencyFull,
  onDone,
}: Props) {
  const [state, setState] = useState<RidePayments | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setState(await getRidePayments(ride.id));
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة الدفعة",
      );
    }
  }, [ride.id]);

  useEffect(() => {
    void load();
    // الراكب قد يختار قناته بعد أن فتح الكبتن هذه الشاشة، ولا حدثَ لذلك على
    // المقبس — فالسؤال يتكرر بهدوء حتى تظهر دفعة
    const timer = window.setInterval(() => void load(), 5_000);
    return () => window.clearInterval(timer);
  }, [load]);

  if (!state) {
    return (
      <div className="flex h-full items-center justify-center bg-bg">
        <Spinner />
      </div>
    );
  }

  // دفعةٌ بيده تنتظر تأكيده — وهي وحدها ما يُقبض الآن
  const pending: Payment | undefined = state.payments.find(
    (payment) => payment.status === "pending" && IN_HAND.has(payment.method),
  );
  // ما مرّ بالمنصة فعلاً وقُيّد له (محفظة أو بطاقة)
  const credited = state.payments.filter(
    (payment) => payment.status === "confirmed" && !IN_HAND.has(payment.method),
  );
  // ما قُبض بيده وأُكِّد سلفاً — يبقى معه ولا يُقيَّد
  const kept = state.payments.filter(
    (payment) => payment.status === "confirmed" && IN_HAND.has(payment.method),
  );

  const commission = Number(ride.commission_percent_at_ride);
  const mixed = credited.length > 0 && (pending || kept.length > 0);

  // الرقم الكبير وما يصفه — **لا رقمَ بلا وصف**
  const headline = pending
    ? { caption: "تقبض الآن من الراكب", amount: pending.amount, hand: true }
    : kept.length > 0
      ? { caption: "قبضتَه نقداً", amount: kept[0].amount, hand: true }
      : credited.length > 0
        ? {
            caption: "أُضيف إلى محفظتك",
            amount: credited[0].amount,
            hand: false,
          }
        : {
            caption: "الأجرة النهائية",
            amount: state.final_fare ?? ride.estimated_fare,
            hand: false,
          };

  const method = pending?.method ?? kept[0]?.method ?? credited[0]?.method;

  return (
    <div className="scr flex h-full flex-col justify-center bg-bg px-26 pb-safe pt-safe">
      <div className="mb-22 text-center">
        <div className="mb-6 text-13 text-muted">{headline.caption}</div>
        <div className="text-44 font-bold leading-hero text-ink">
          {digits(headline.amount)}
        </div>
        <div className="mt-4 text-13 text-muted">
          {currencyFull}
          {method ? ` · ${METHOD_LABEL[method]}` : ""}
        </div>
      </div>

      <div className="mb-18 card px-16 py-14">
        <Row label="السعر المقدّر" value={digits(ride.estimated_fare)} />
        {ride.actual_distance_km ? (
          <Row
            label="المسافة الفعلية"
            value={`${trimDistance(ride.actual_distance_km)} كم`}
          />
        ) : null}
        <Row
          label="السعر النهائي"
          value={`${digits(state.final_fare ?? ride.estimated_fare)} ${currencyLabel}`}
          strong
        />

        {/* الفصلُ الصريح **حين يكون هناك ما يُفصل**: في الدفع المختلط شقٌّ
            بيدك وشقٌّ في محفظتك. أما رحلةُ الكاش الخالصة فرقمُها الكبير هو
            نفسه، وتكرارُه سطراً يقرأ كأنه مبلغٌ ثانٍ */}
        {mixed ? (
          <Row
            label="تقبضه بيدك"
            value={`${digits(pending?.amount ?? kept[0]?.amount ?? "0")} ${currencyLabel}`}
            tone="text-ink"
            strong
          />
        ) : null}
        {credited.length > 0 ? (
          <Row
            label="قُيّد في محفظتك"
            value={`${digits(credited[0].amount)} ${currencyLabel}`}
            tone="text-ok"
            strong
          />
        ) : null}

        <Row
          label="العمولة"
          value={
            commission === 0
              ? "0٪ حالياً"
              : `${digits(String(commission))}٪`
          }
          tone="text-ok"
          last
        />
      </div>

      <ErrorNote message={error} />

      <Button
        className="mt-12"
        loading={busy}
        onClick={() => {
          if (!pending) {
            onDone();
            return;
          }
          setBusy(true);
          setError(null);
          confirmPayment(pending.id)
            .then(onDone)
            .catch((caught) =>
              setError(
                caught instanceof ApiError
                  ? caught.message
                  : "تعذّر تأكيد الدفعة",
              ),
            )
            .finally(() => setBusy(false));
        }}
      >
        {pending
          ? pending.method === "cliq"
            ? "وصلتني الحوالة"
            : "استلمت المبلغ كاش"
          : "إنهاء"}
      </Button>

      <p className="mt-12 text-center text-11.5 leading-snug text-muted">
        {pending
          ? "هذا المبلغ يبقى معك ولا يمر بمحفظتك. وتأكيدك هو ما يُثبّته — إن لم يصلك فافتح نزاعاً من تفاصيل الرحلة."
          : headline.hand
            ? "هذا المبلغ بقي معك ولم يمر بمحفظتك."
            : credited.length > 0
              ? "المال وصل قبل إنهائك الرحلة — قيدُ أرباحك في المحفظة تلقائي."
              : "لم يختر الراكب طريقة الدفع بعد — ستظهر الدفعة هنا وفي سجل رحلاتك."}
        {commission > 0
          ? " والعمولة تُخصم من رصيد محفظتك، لا من هذا المبلغ."
          : ""}
      </p>
    </div>
  );
}

function Row({
  label,
  value,
  tone = "text-ink",
  strong = false,
  last = false,
}: {
  label: string;
  value: string;
  tone?: string;
  strong?: boolean;
  last?: boolean;
}) {
  return (
    <div className={`flex justify-between text-12.5 ${last ? "" : "mb-8"}`}>
      <span className="text-muted">{label}</span>
      <span className={`${tone} ${strong ? "font-bold" : "font-medium"}`}>
        {value}
      </span>
    </div>
  );
}
