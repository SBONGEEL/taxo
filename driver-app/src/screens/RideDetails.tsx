/** تفاصيل الرحلة — SPEC القسم 12/6، وشكلُها من `DESIGN.md` §5.3.
 *
 * ثلاثةُ أسئلةٍ يفتح الكبتن هذه الشاشة ليجيب عنها: **كم قبضتُ**، و**بأي
 * قناة**، و**هل وصلني المال فعلاً**. والثالثُ وحده يفتح باب النزاع.
 *
 * **والنزاع على كليك وحدها** (`payments.dispute_by_driver`): التحويل يقع
 * خارج التطبيق ولا API يشهد عليه، فبين «حوّلتُ» و«لم يصلني» فراغٌ يملؤه
 * إنسان. الكاش يقع يداً بيد فلا فراغ فيه، والمحفظة يشهد عليها الدفتر.
 * والتصميم يعرض زرَّ النزاع على رحلة الكاش بأسبابٍ نقدية — وهو انحرافٌ عن
 * الخلفية مسجّلٌ في `DESIGN-DECISIONS.md`، والزرُّ هنا مشروطٌ بدفعة كليك
 * تنتظر التأكيد.
 *
 * **ولا خطَّ مسارٍ فوق الخريطة**: `ride_route_points` يُسجَّل للخلفية —
 * لإعادة حساب `final_fare` ولدليل النزاع في اللوحة — ولا منفذَ يقرؤه
 * للكبتن. فالخريطة تعرض الدبوسين وحدهما، ولا تعد بمسارٍ لم يقله أحد.
 *
 * **ولا تفصيلَ تعرفةٍ سطراً سطراً**: التصميم يعرض «التعرفة الأساسية · لكل كم
 * · لكل دقيقة»، و`GET /config` لا ينشر أسعار `pricing_settings` — والواجهة
 * لا تضرب مسافةً في سعرٍ لتُخرج رقماً (القسم 14: الحساب في الخلفية حصراً).
 * فما يظهر ما قالته الخلفية: مقدَّرٌ، ومسافة، ومدّة، ونهائيّ، ونسبةُ عمولة.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import {
  confirmPayment,
  getRide,
  getRidePayments,
  listRideRatings,
} from "@/api/endpoints";
import type {
  Payment,
  PaymentStatus,
  Rating,
  Ride,
  RidePayments,
} from "@/api/types";
import { Button } from "@/components/ui/Button";
import { MapView } from "@/components/map/MapView";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { useMapboxToken } from "@/lib/config";
import {
  CURRENCY_LABEL,
  METHOD_LABEL,
  RIDE_STATUS_LABEL,
  formatWhen,
  statusTone,
  trimDistance,
} from "@/lib/rideFormat";
import { arabicDigits, cn } from "@/lib/utils";
import { useGoBack } from "@/lib/back";

/** نصُّ فصل الإدارة — `paid` تصف الواقعة لا الحالة الناتجة. */
const RESOLUTION_LABEL: Record<"paid" | "unpaid", string> = {
  paid: "فصلت الإدارة: المبلغ وصلك",
  unpaid: "فصلت الإدارة: المبلغ لم يصلك",
};

export function RideDetailsScreen() {
  const { rideId = "" } = useParams();
  const navigate = useNavigate();
  const goBack = useGoBack();
  const token = useMapboxToken();

  const [ride, setRide] = useState<Ride | null>(null);
  const [payments, setPayments] = useState<RidePayments | null>(null);
  const [ratings, setRatings] = useState<Rating[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);

  const load = useCallback(async () => {
    const [one, paid, rated] = await Promise.all([
      getRide(rideId),
      // رحلةٌ ألغيت قبل أي دفعة لا دفعاتِ لها، وليس ذلك عطلاً
      getRidePayments(rideId).catch(() => null),
      listRideRatings(rideId).catch(() => []),
    ]);
    setRide(one);
    setPayments(paid);
    setRatings(rated);
  }, [rideId]);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة الرحلة",
      ),
    );
  }, [load]);

  async function confirm(paymentId: string) {
    setConfirming(true);
    setError(null);
    try {
      await confirmPayment(paymentId);
      await load();
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر تأكيد الدفعة",
      );
    } finally {
      setConfirming(false);
    }
  }

  if (!ride) {
    return (
      <div className="flex h-full items-center justify-center bg-bg px-16">
        {error ? <ErrorNote message={error} /> : <Spinner />}
      </div>
    );
  }

  const currency = CURRENCY_LABEL[ride.currency];
  const rows = payments?.payments ?? [];
  // النزاع من دفعةٍ واحدة: كليك تنتظر تأكيده
  const disputable: Payment | undefined = rows.find(
    (payment) => payment.method === "cliq" && payment.status === "pending",
  );
  const disputed = rows.find((payment) => payment.status === "disputed");
  const resolved = rows.find(
    (payment) => payment.disputed_at !== null && payment.resolution !== null,
  );
  // تقييمُ الكبتن للراكب — لا تقييمُ الراكب له
  const mine = ratings.find((rating) => rating.rater_type === "driver");
  const commission = Number(ride.commission_percent_at_ride);

  return (
    <div className="scr h-full bg-bg pb-12">
      <div className="relative h-170">
        <MapView
          token={token}
          center={ride.pickup}
          pickup={ride.pickup}
          dropoff={ride.dropoff}
          fit
          className="absolute inset-0"
        />
        <button
          type="button"
          onClick={() => goBack()}
          aria-label="رجوع"
          className="pressable absolute start-14 top-14 flex size-34 items-center justify-center rounded-full border border-line bg-surface text-ink"
        >
          →
        </button>
      </div>

      <div className="p-16">
        <ErrorNote message={error} />

        <div className="mb-14 flex items-baseline justify-between">
          <div>
            <div className="text-12 text-muted">
              {formatWhen(ride.created_at)}
            </div>
            <div className="whitespace-nowrap text-26 font-bold text-ink">
              {arabicDigits(ride.final_fare ?? ride.estimated_fare)} {currency}
            </div>
          </div>
          <span
            className={cn(
              "shrink-0 rounded-full border border-line px-11 py-6 text-11.5 font-bold",
              statusTone(ride.status),
            )}
          >
            {RIDE_STATUS_LABEL[ride.status]}
          </span>
        </div>

        <div className="mb-16 grid grid-cols-[12px_minmax(0,1fr)] gap-x-10 gap-y-4">
          <span className="mx-auto mt-5 block size-8 rounded-full bg-ink" />
          <div className="text-12.5 text-ink">
            {ride.pickup_address ?? "نقطة الانطلاق"}
          </div>
          <span className="mx-auto block h-12 w-2 bg-line" />
          <span />
          <span className="mx-auto mt-2 block size-8 rounded-2 bg-muted" />
          <div className="text-12.5 text-muted">
            {ride.dropoff_address ?? "الوجهة"}
          </div>
        </div>

        <section className="mb-12 card p-15">
          <h2 className="mb-11 text-13 font-bold text-ink">تفصيل السعر</h2>
          <Row
            label="السعر المقدّر"
            value={`${arabicDigits(ride.estimated_fare)} ${currency}`}
          />
          {/* الفعليةُ تُسمّى فعلية: جدولٌ يخلط المقدَّر بالمحقَّق بلا اسمٍ
              يجعل الكبتن يحسب على رقمٍ لا يعرف مصدره */}
          <Row
            label={
              ride.actual_distance_km ? "المسافة الفعلية" : "المسافة المقدّرة"
            }
            value={`${trimDistance(ride.actual_distance_km ?? ride.distance_km)} كم`}
          />
          <Row
            label="المدّة المقدّرة"
            value={`${trimDistance(ride.duration_min)} دقيقة`}
          />
          <Row
            label="العمولة"
            value={
              commission === 0
                ? "٠٪ حالياً"
                : `${arabicDigits(String(commission))}٪`
            }
            tone="text-ok"
          />
          <Row
            label="السعر النهائي"
            value={`${arabicDigits(ride.final_fare ?? ride.estimated_fare)} ${currency}`}
            strong
            last
          />
        </section>

        {rows.length > 0 || mine ? (
          <section className="mb-12 card p-15">
            {rows.map((payment) => (
              <Row
                key={payment.id}
                label={`${METHOD_LABEL[payment.method]} · ${paymentStatusLabel(payment)}`}
                value={`${arabicDigits(payment.amount)} ${currency}`}
                tone={payment.status === "confirmed" ? "text-ink" : "text-warn"}
              />
            ))}
            {mine ? (
              <Row
                label="تقييمك للراكب"
                value={`★ ${arabicDigits(String(mine.stars))}`}
                tone="text-warn"
                last
              />
            ) : null}
          </section>
        ) : null}

        {resolved ? (
          <div className="rounded-15 border border-line bg-surface p-14 text-12.5 leading-snug text-muted">
            {resolved.resolution
              ? RESOLUTION_LABEL[resolved.resolution]
              : "فُصل النزاع"}
            {resolved.resolution_note ? ` — ${resolved.resolution_note}` : ""}
          </div>
        ) : disputed ? (
          <div className="rounded-15 border border-warn bg-surface p-14 text-12.5 leading-snug text-muted">
            نزاعك مفتوح وبانتظار فصل الإدارة. سيصلك إشعار بالنتيجة.
          </div>
        ) : disputable ? (
          <>
            {/* **الفعلُ الإيجابي أولاً**: من وصلته الحوالة يجد بابَه هنا لا في
                بطاقةٍ عابرة قد يكون أغلقها. وشاشةٌ تعرض «افتح نزاعاً» وحده
                تُملي على الكبتن الجوابَ الذي لم يقله */}
            <div className="flex gap-10">
              <Button
                className="flex-1"
                size="md"
                loading={confirming}
                onClick={() => void confirm(disputable.id)}
              >
                وصلتني
              </Button>
              <Button
                className="flex-1 border-danger text-danger"
                size="md"
                variant="secondary"
                disabled={confirming}
                onClick={() => navigate(`/rides/${ride.id}/dispute`)}
              >
                لم تصلني
              </Button>
            </div>
            {/* المهلةُ تُقال هنا أيضاً: من أغلق البطاقة لا يراها إلا هنا */}
            {disputable.cliq_confirmation_expires_at ? (
              <p className="mt-10 text-11.5 leading-note text-muted">
                إن لم تؤكّد أو ترفض حتى{" "}
                {formatWhen(disputable.cliq_confirmation_expires_at)} صارت
                الدفعة نزاعاً تفصل فيه الإدارة.
              </p>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}

/** والاسمُ يختلف بالقناة لا بالحال: `pending` على كليك والكاش انتظارُ قولِ
 * الكبتن، وعلى البطاقة انتظارُ جواب المزود. */
function paymentStatusLabel(payment: Payment): string {
  if (payment.status === "pending") {
    return payment.method === "cash" || payment.method === "cliq"
      ? "بانتظار تأكيدك"
      : "بانتظار الدفع";
  }
  return PAYMENT_STATUS_LABEL[payment.status];
}

const PAYMENT_STATUS_LABEL: Record<PaymentStatus, string> = {
  pending: "بانتظار الدفع",
  confirmed: "مؤكدة",
  failed: "فاشلة",
  refunded: "مستردّة",
  disputed: "في نزاع",
};

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
    <div className={cn("flex justify-between text-12.5", last ? "" : "mb-8")}>
      <span className="text-muted">{label}</span>
      <span className={cn(tone, strong ? "font-bold" : "font-medium")}>
        {value}
      </span>
    </div>
  );
}
