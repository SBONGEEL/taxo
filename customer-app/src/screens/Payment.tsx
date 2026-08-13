/** شاشة الدفع: القنوات المتاحة **حسب الدولة** (SPEC القسم 11.5/6).
 *
 * ثلاث قواعد من SPEC تنعكس هنا حرفياً:
 *
 * - **المحفظة خياراً أول وكليك ثانياً** (القسم 6.2) — والترتيب في
 *   `lib/payment.ts::PAYMENT_CHANNELS`، وهو بيتُ القائمة الوحيد منذ الحزمة (ب).
 * - **القنوات تتبع مفاتيح الدولة**: الكاش وحده بلا مفتاح (إعدادُ ليبيا
 *   الافتراضي «كاش فقط»)، وما عداه يظهر إن كان مفتاحه مرفوعاً (القسم 4).
 * - **لا مبلغ يُرسل**: المبلغ هو المتبقي من `final_fare` تحسبه الخلفية
 *   (القسم 14). الشاشة تعرض `outstanding` وتختار قناةً لا غير.
 *
 * ومفتاحُ عدم التكرار يُولَّد **مرةً لكل محاولة قناة** ويُعاد استعماله في
 * إعادة المحاولة: ضغطتان لا تفتحان دفعتين (القسم 14).
 *
 * ---
 *
 * **والشكلُ طبقةٌ موسَّطة لا شاشةُ قائمة** (الحزمة ب، تصميمُ `payShow`): مبلغٌ
 * كبيرٌ في الوسط، ثم بطاقةُ صفوفٍ تشرحه، ثم زرٌّ واحد. وهذا الشكلُ **يفترض أن
 * القناةَ اختيرت قبل الرحلة** — وهو ما بنته ورقةُ التأكيد في الحزمة نفسِها،
 * ولذلك لم يُنقل الشكلُ في الحزمة (ج) مع أخته `rateShow`.
 *
 * **وقائمةُ القنوات لم تُحذف، بل صارت خلف «طريقة أخرى»**، وهذا شرطُ القرار 3
 * لا زينة: التفضيلُ **لا يُقيّد صاحبَه عند الدفع**. فمن اختار المحفظةَ قبل
 * الرحلة ثم وجد رصيدَه لا يكفي يجد كلَّ قناةٍ متاحةٍ على بعد ضغطةٍ واحدة —
 * وطبقةٌ بزرٍّ واحدٍ بلا مخرجٍ تجعل التفضيلَ قيداً، وهو ما رفضه القرار نصّاً.
 */

import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getRide, getRidePayments, payRide } from "@/api/endpoints";
import type { Ride, RidePayments } from "@/api/types";
import { CardChoice } from "@/components/payment/CardChoice";
import { CliqPanel } from "@/components/payment/CliqPanel";
import { PaymentPicker } from "@/components/payment/PaymentPicker";
import { PaymentsList } from "@/components/payment/PaymentsList";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { Screen } from "@/components/ui/Screen";
import { Stage } from "@/components/ui/Stage";
import { useCountryConfig } from "@/lib/config";
import { PAYMENT_METHOD_LABEL } from "@/lib/labels";
import { usePaymentPreference, type PayableMethod } from "@/lib/payment";
import { useRide } from "@/lib/ride";
import { useSession } from "@/lib/session";
import {
  currencyName,
  formatDistance,
  formatMoney,
  newIdempotencyKey,
} from "@/lib/utils";

/** نصُّ الزرِّ والملاحظةِ لكل قناة — **وما بعد الضغط لا اسمَ القناة**.
 *
 * الكاشُ وكليك لا تُنهي الضغطةُ فيهما شيئاً: تُنشئ صفَّ دفعةٍ `pending` ينتظر
 * كلمةَ الكبتن (`DIRECTLY_COLLECTED_METHODS` — المالُ لا يمرّ بالمنصّة أصلاً).
 * فزرٌّ يقول «ادفع» ثم لا يتغيّر شيءٌ في الشاشة يُقرأ عطلاً ويُضغط ثانيةً؛
 * وهذه هي بعينُها ملاحظةُ `payNoteCash` في التصميم.
 */
const CTA: Record<PayableMethod, { label: string; note: string }> = {
  wallet: {
    label: "ادفع من المحفظة",
    note: "يُخصم المبلغ فوراً من رصيدك، وإيصالك في سجل الرحلات.",
  },
  card: {
    label: "ادفع بالبطاقة",
    note: "تُفتح صفحةُ الدفع الآمنة لدى المزوّد ثم تعود إلى هنا.",
  },
  cliq: {
    label: "ادفع عبر كليك",
    note: "تُحوّل على alias الكبتن ثم تُدخل رقم الحوالة — ويؤكد استلامها في تطبيقه.",
  },
  cash: {
    label: "سأدفع كاشاً",
    note: "سلّم المبلغ للكبتن — سيؤكد استلامه في تطبيقه.",
  },
};

export function PaymentScreen() {
  const { rideId = "" } = useParams();
  const navigate = useNavigate();
  const { user } = useSession();
  const { refresh } = useRide();
  const country = useCountryConfig(user?.country_code);

  const [ride, setRideRow] = useState<Ride | null>(null);
  const [state, setState] = useState<RidePayments | null>(null);
  const [busy, setBusy] = useState<PayableMethod | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // البطاقة وحدها تحتاج خطوةً وسطى: أيُّ بطاقة، وهل تُحفظ (SPEC القسم 6.4)
  const [choosingCard, setChoosingCard] = useState(false);
  // «طريقة أخرى» — المخرجُ الذي يمنع التفضيلَ من أن يصير قيداً (القرار 3)
  const [picking, setPicking] = useState(false);
  // مفتاحٌ لكل قناة يعيش ما دامت الشاشة: إعادة المحاولة بنفس المفتاح لا تدفع
  // مرتين، وقناةٌ أخرى تحتاج مفتاحها الخاص لأن الأولى قد تكون سجّلت دفعة
  const keys = useRef(new Map<PayableMethod, string>());

  // **القناةُ المختارةُ قبل الرحلة هي ما تفتح عليه الشاشة** — والقائمةُ نفسُها
  // وراء «طريقة أخرى»، فالاختيارُ هنا يُحدّث التفضيلَ أيضاً: من بدّلها عند
  // الدفع بدّلها عن قصد، وتفضيلٌ لا يتعلّم من ذلك يُعاد تصحيحُه كلَّ رحلة
  const { available, resolved, choose } = usePaymentPreference(country);

  const load = useCallback(async () => {
    const [row, payments] = await Promise.all([
      getRide(rideId),
      getRidePayments(rideId),
    ]);
    setRideRow(row);
    setState(payments);
    return payments;
  }, [rideId]);

  useEffect(() => {
    load()
      .catch((caught: unknown) =>
        setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة حال الدفع"),
      )
      .finally(() => setLoading(false));
  }, [load]);

  /** **سؤالان لا سؤالٌ واحد** — وخلطُهما عطبٌ كان في هذه الشاشة منذ المرحلة 9.
   *
   * `outstanding` مجموعُ `OWING_PAYMENT_STATUSES` مطروحاً من `final_fare`،
   * و`pending` **داخلَ تلك المجموعة** — لأنها تجيب سؤالَ الخلفية: «هل بقي ما
   * يُنشأ له صفُّ دفعةٍ جديد؟» (أي حارسُ «لا تُدفع الرحلةُ مرتين»). وهو سؤالٌ
   * صحيحٌ لإخفاء الزرّ، **وليس** سؤالَ الراكب: «هل بقي عليّ شيءٌ أُسلّمه؟».
   *
   * فمن دفع بمحفظةٍ لا تغطّي الأجرة يكتب له `_pay_from_wallet` صفَّ محفظةٍ
   * `confirmed` وصفَّ كاشٍ `pending` بالباقي — فيصير `outstanding` صفراً بينما
   * في يده مالٌ لم يُسلَّم بعد. وكانت الشاشةُ تقول عندها «اكتمل دفع هذه الرحلة
   * — شكراً لك» بالأخضر، وتحتها مباشرةً «كاش ٢٫٤٨١ بانتظار التأكيد». شاشةٌ
   * تناقض قائمتَها بسطرين، ولا يُبلَّغ عن هذا لأنه لا خطأ فيه: **كِذبةٌ هادئة**.
   *
   * ولم يظهر قبل اليوم لأن بلوغَه يحتاج رحلةً حقيقيةً تُدفع بمحفظةٍ أقلَّ من
   * أجرتها — وهي الحالُ التي بَنَتها الحزمةُ (ب) لتفحص ملاحظةَ الدفع المختلط،
   * فوجدت أن ما تَعِد به الملاحظةُ تنقضه الشاشةُ التالية.
   */
  const nothingToStart = state !== null && Number(state.outstanding) <= 0;
  const awaiting = (state?.payments ?? []).filter((row) => row.status === "pending");
  const settled = nothingToStart && awaiting.length === 0;

  /** صفوفُ البطاقة (`payRows`) — **قراءةٌ لا حساب**.
   *
   * كلُّ قيمةٍ هنا حقلٌ جاء من الخلفية كما هو: الأجرةُ النهائية والمسافةُ
   * الفعلية. ولا صفَّ لـ«ما دُفع» لأن اشتقاقَه طرحٌ لمبلغين — وما دُفع مفصَّلٌ
   * أصلاً في `PaymentsList` صفَّاً صفَّاً بقناته وحاله، وهو الصدقُ الكامل.
   */
  const rows = useMemo(
    () =>
      [
        state?.final_fare
          ? {
              label: "الأجرة النهائية",
              value: formatMoney(state.final_fare, state.currency),
              strong: true,
            }
          : null,
        ride?.actual_distance_km
          ? {
              label: "المسافة الفعلية",
              value: formatDistance(ride.actual_distance_km),
              strong: false,
            }
          : null,
      ].filter((row): row is { label: string; value: string; strong: boolean } =>
        row !== null,
      ),
    [state, ride],
  );

  async function pay(
    method: PayableMethod,
    extras: { save_card?: boolean; saved_card_id?: string } = {},
  ) {
    setBusy(method);
    setError(null);
    try {
      const key =
        keys.current.get(method) ?? newIdempotencyKey(`pay-${method}-${rideId.slice(0, 8)}`);
      keys.current.set(method, key);

      const result = await payRide(rideId, method, key, extras);
      setState(result);
      setChoosingCard(false);
      void refresh();

      // البطاقة تعود برابط صفحة المزود — والعودة منها تسأل عن الحال (6.4).
      // وبطاقةٌ محفوظة تُحسم عند المزود بلا صفحة، فلا رابط يعود ولا توجيه
      const redirect = result.card_order?.redirect_url;
      if (method === "card" && redirect) {
        sessionStorage.setItem("taxo.card_return_ride", rideId);
        window.location.assign(redirect);
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر تنفيذ الدفع");
    } finally {
      setBusy(null);
    }
  }

  // **التحميلُ يبقى `Screen` لا `Stage`**: طبقةٌ موسَّطةٌ فارغةٌ بدوّامةٍ في
  // منتصف شاشةٍ سوداء تُقرأ عطلاً، والانتقالُ إليها بعد لحظةٍ يومض
  if (loading) {
    return (
      <Screen title="الدفع" back="/">
        <Spinner label="نقرأ حال الدفع…" />
      </Screen>
    );
  }

  return (
    <Stage onBack={() => navigate("/")}>
      <div className="space-y-18">
        {/* **الرأسُ الموسَّط** (`payShow`): عنوانٌ صغير، ثم الرقمُ كبيراً، ثم
            سطرٌ يسمّي العملةَ والقناةَ معاً. والرقمُ هو المتبقي لا الأجرة، لأن
            ما يُسأل عنه الآن هو ما يُدفع الآن */}
        <div className="text-center">
          <p className="text-13 text-muted">
            {nothingToStart ? "إجمالي الأجرة" : "المتبقي على هذه الرحلة"}
          </p>
          <p className="text-44 font-bold leading-hero text-ink">
            {formatMoney(
              nothingToStart ? (state?.final_fare ?? null) : (state?.outstanding ?? null),
              state?.currency,
            )}
          </p>
          <p className="mt-4 text-13 text-muted">
            {currencyName(state?.currency)}
            {nothingToStart || !resolved
              ? null
              : ` · ${PAYMENT_METHOD_LABEL[resolved.method]}`}
          </p>
        </div>

        {rows.length > 0 ? (
          <div className="card px-16 py-14">
            {rows.map((row) => (
              <div
                key={row.label}
                className="flex justify-between py-4 text-12.5 last:pb-0"
              >
                <span className="text-muted">{row.label}</span>
                <span className={row.strong ? "font-bold text-ink" : "text-ink"}>
                  {row.value}
                </span>
              </div>
            ))}
          </div>
        ) : null}

        <ErrorNote message={error} />

        {settled ? (
          <>
            <SuccessNote message="اكتمل دفع هذه الرحلة — شكراً لك." />
            <Button size="lg" onClick={() => navigate(`/rides/${rideId}/rate`)}>
              قيّم رحلتك
            </Button>
          </>
        ) : nothingToStart ? (
          <>
            {/* **لم يبقَ ما يُبدأ من هنا، ولم يكتمل الدفعُ بعد.** فلا زرَّ دفعٍ
                (لا صفَّ جديد يُنشأ) ولا «شكراً» (المالُ لم يصل). والنصُّ يسمّي
                القناةَ والمبلغَ لأن «بانتظار التأكيد» وحدَها لا تقول لمن يقرؤها
                هل عليه أن يُخرج نقداً من جيبه الآن أم ينتظر */}
            {awaiting.map((row) => (
              <div
                key={row.id}
                className="rounded-12 border border-warn bg-surface-2 px-14 py-12"
              >
                <p className="text-14 font-medium text-ink">
                  {row.method === "cash"
                    ? `سلّم ${formatMoney(row.amount, row.currency)} كاشاً للكبتن`
                    : `${formatMoney(row.amount, row.currency)} بقناة ${PAYMENT_METHOD_LABEL[row.method]} بانتظار التأكيد`}
                </p>
                <p className="mt-4 text-12 leading-snug text-muted">
                  يكتمل دفعُ الرحلة حين يؤكد الكبتن استلامها في تطبيقه.
                </p>
              </div>
            ))}
            <Button size="lg" onClick={() => navigate(`/rides/${rideId}/rate`)}>
              قيّم رحلتك
            </Button>
          </>
        ) : resolved ? (
          <AnimatePresence mode="wait">
            <motion.div
              key={resolved.method}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-12"
            >
              <Button
                size="lg"
                loading={busy === resolved.method}
                disabled={busy !== null}
                onClick={() =>
                  resolved.method === "card"
                    ? setChoosingCard(true)
                    : pay(resolved.method)
                }
              >
                {CTA[resolved.method].label}
              </Button>

              {/* **المخرجُ الذي يمنع التفضيلَ من أن يصير قيداً** (القرار 3).
                  ولا يظهر بقناةٍ واحدة: «طريقة أخرى» حيث لا أخرى وعدٌ يُخلَف */}
              {available.length > 1 ? (
                <button
                  type="button"
                  onClick={() => setPicking(true)}
                  className="block w-full text-center text-12.5 font-semibold text-muted"
                >
                  طريقة أخرى
                </button>
              ) : null}

              <p className="text-center text-11.5 leading-snug text-muted">
                {CTA[resolved.method].note}
              </p>
            </motion.div>
          </AnimatePresence>
        ) : null}

        {choosingCard && !nothingToStart ? (
          <CardChoice
            busy={busy === "card"}
            onPay={(extras) => pay("card", extras)}
            onCancel={() => setChoosingCard(false)}
          />
        ) : null}

        {/* صفحة دفع كليك داخل التطبيق (SPEC القسم 6.2 — المرحلة 9) */}
        {state?.cliq_charge ? (
          <CliqPanel charge={state.cliq_charge} onSubmitted={setState} />
        ) : null}

        {state && state.payments.length > 0 ? (
          <PaymentsList payments={state.payments} />
        ) : null}
      </div>

      {picking && resolved ? (
        <PaymentPicker
          channels={available}
          selected={resolved.method}
          onSelect={choose}
          onClose={() => setPicking(false)}
        />
      ) : null}
    </Stage>
  );
}
