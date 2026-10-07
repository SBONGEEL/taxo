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
 * **والشكلُ طبقةٌ كاملة لا شاشةُ قائمة** (الحزمة ب، تصميمُ `payShow`): مبلغٌ كبيرٌ، ثم ما يشرحه، ثم زرٌّ واحد. وهذا الشكلُ
 * **يفترض أن القناةَ اختيرت قبل الرحلة** — وهو ما بنته ورقةُ التأكيد في الحزمة نفسِها.
 *
 * **وقائمةُ القنوات لم تُحذف، بل صارت خلف «طريقة أخرى»**، وهذا شرطُ القرار 3 لا زينة: التفضيلُ **لا يُقيّد صاحبَه عند الدفع**.
 * فمن اختار المحفظةَ قبل الرحلة ثم وجد رصيدَه لا يكفي يجد كلَّ قناةٍ متاحةٍ على بعد ضغطةٍ واحدة.
 *
 * **بلغة TAXO 2.0** (لوحاتُ `design/t2-new/rider/R19` · `R19b` · `R19c`): بنيةُ R10 — رأسٌ، وبطاقةُ الأجرة وحبّةُ القناة، والزرُّ
 * في القاع بالجمر («طلب / قبول» في الهوية)، **والبطاقةُ ورقةٌ** أختُ «طريقة الدفع». **والنداءاتُ والمفاتيحُ والاستطلاعُ والأصواتُ
 * حرفاً.**
 *
 * **ورحلةٌ لشخصٍ آخر** (§٦٣-ج/١): الطالبُ يدفع بالمحفظة أو البطاقة وحدهما، **وإن دفع الراكبُ نقداً فالشاشةُ حالٌ تُقرأ** —
 * «يدفعها الراكبُ نقداً للكبتن» — **بلا قناةٍ ولا زرِّ دفع**. **والطردُ الذي يدفعه مستلمُه مثلُها** (§٦٣-ج/٤): «يدفعها المستلمُ
 * نقداً للكبتن»؛ ومرسلُه الدافعُ يدفع بأيِّ قناةٍ كأيِّ رحلة.
 */

import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getRide, getRidePayments, payRide } from "@/api/endpoints";
import type { Ride, RidePayments } from "@/api/types";
import { CardChoice } from "@/components/payment/CardChoice";
import { CliqPanel } from "@/components/payment/CliqPanel";
import { PAY_ICON_T2, PaymentPicker } from "@/components/payment/PaymentPicker";
import { PaymentsList } from "@/components/payment/PaymentsList";
import { useGoBack } from "@/lib/back";
import { useCountryConfig } from "@/lib/config";
import { payerScope, usePayerPreference } from "@/lib/for-other";
import { PAYMENT_METHOD_LABEL } from "@/lib/labels";
import type { PayableMethod } from "@/lib/payment";
import { useRide } from "@/lib/ride";
import { useSession } from "@/lib/session";
import { play } from "@/lib/sound";
import {
  currencyLabel,
  currencyName,
  formatDistance,
  formatMoney,
  newIdempotencyKey,
} from "@/lib/utils";
import { Icon } from "@/taxo2";
import { BannerT2, BusyLabel, HeadT2, WaitT2 } from "@/screens/t2/MoneyT2";

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

/** سطورُ ما وقف الكبتنُ لأجله — **تُقرأ ولا تُحسب، وتصمت عند الصفر**.
 *
 * **القيمُ كما وصلت**: `stops_charge` مضروبٌ في الخلفية و`waiting_charge`
 * مجموعٌ فيها (§14) — فلا ضربَ هنا ولا جمع، والشاشةُ تعرض ما حُصِّل لا ما
 * تحسبه هي.
 *
 * **وصفرٌ لا يُرسم**: سطرٌ يقول «رسم الانتظار 0.000» يعلّم قارئَه أن يمرّ
 * على السطور بلا قراءة، فيمرّ على غير الصفر يومَ يقع.
 */
function stopBreakdown(
  ride: Ride | null,
): { label: string; value: string; strong: boolean }[] {
  if (!ride) return [];
  const rows: { label: string; value: string; strong: boolean }[] = [];
  if (Number(ride.stops_charge) > 0)
    rows.push({
      label: `رسم المحطات (${ride.stops.length})`,
      value: formatMoney(ride.stops_charge, ride.currency),
      strong: false,
    });
  if (Number(ride.waiting_charge) > 0)
    rows.push({
      label: "رسم الانتظار عند المحطات",
      value: formatMoney(ride.waiting_charge, ride.currency),
      strong: false,
    });
  if (Number(ride.pause_charge) > 0)
    rows.push({
      label: "رسم الوقفات أثناء الرحلة",
      value: formatMoney(ride.pause_charge, ride.currency),
      strong: false,
    });
  return rows;
}

export function PaymentScreen() {
  const { rideId = "" } = useParams();
  const navigate = useNavigate();
  // **أثناء القراءة رجوعٌ إلى حيث جئت** كما كان رأسُ شاشة الانتظار (`lib/back.ts`)، **وبعدها إلى الرئيسية** كما كانت الطبقة
  const goBack = useGoBack("/");
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
  //
  // **وفي رحلةٍ لغيره تضيق القنواتُ بالدافع** (§٦٣-ج/١، `usePayerPreference`): الطالبُ يدفع بالمحفظة أو البطاقة وحدهما
  // (والخلفيةُ ترفض غيرَهما `payer_method_mismatch`)، **وإن دفع الراكبُ نقداً فلا قناةَ يختارها أحدٌ هنا** — دفعتُه فتحتها
  // الخلفيةُ عند الإنهاء، **وكلُّ قناةٍ من هنا ترتدّ ٤٠٩**. فالشاشةُ تقول ذلك بدل زرٍّ يرتدّ.
  // **وطردٌ يدفعه مستلمُه** (§٦٣-ج/٤) **بالحكم نفسِه** — `payerScope` يمرّره، ومرسلُه الدافعُ لا يُضيَّق عليه
  const payer = ride ? payerScope(ride) : null;
  const passengerCash = payer === "passenger_cash";
  const recipientCash = payer === "recipient_cash";
  // **نقدٌ يسلّمه غيرُ صاحب الحساب** — الراكبُ الفعليُّ أو مستلمُ الطرد
  const cashByOther = passengerCash || recipientCash;
  const { available, resolved, choose } = usePayerPreference(country, payer);

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
   * **والدواءُ صار حقلاً في الردّ لا حساباً هنا** (2026-08-15): تجيب الخلفيةُ
   * بـ`settlement` من `services/settlement.py`، وكانت هذه الشاشةُ واحدةً من
   * أربعٍ تستنتج الجوابَ بحسابها الخاص — فأخطأت ثلاثٌ منها بثلاث طرق. ونصُّ
   * الشرح باقٍ فوق لأن الخطأ يعود بعودة الحساب، لا بعودة الحقل.
   */
  const settlement = state?.settlement ?? "not_due";
  const awaiting = (state?.payments ?? []).filter((row) => row.status === "pending");
  // **دفعةُ نقد الراكب الفعليّ أو المستلم** كما فتحتها الخلفيةُ عند الإنهاء (§٦٣-ج/١ و/٤) — مبلغُها يُقرأ ولا يُحسب
  const otherDue = cashByOther ? awaiting.find((row) => row.method === "cash") : undefined;
  const settled = settlement === "settled";
  const nothingToStart = settlement === "awaiting" || settlement === "disputed";

  /** **الشاشةُ تسأل ما دامت دفعةٌ تنتظر قولَ الكبتن** — وجدته تجربةُ المرحلة
   * ١٣ على الهاتفين: يضغط الكبتنُ «استلمت المبلغ» فلا يتغيّر في شاشة الراكب
   * شيءٌ أبداً — قِيس خمسَ عشرةَ ثانيةً بلا لمس — ويبقى مكتوباً «سلّم المبلغ
   * للكبتن» بعد أن سُلِّم وأُكِّد. ولا يعرف صاحبُها إلا إن أغلق التطبيق وفتحه،
   * وهو آخرُ ما يخطر لمن يقف أمام الكبتن.
   *
   * **وسؤالٌ كلَّ خمس ثوانٍ لا مقبسٌ جديد**: هذا سؤالٌ جوابُه واحد — «هل أكّد
   * بعد؟» — وعمرُه دقيقةٌ أو دقيقتان، وهو بعينه ما يبرّر استطلاعَ اللوحة كلَّ
   * خمس. **ويتوقف من نفسه** حين لا تبقى دفعةٌ منتظرة، فلا يعمل في شاشةٍ
   * اكتمل دفعُها ولا في جيبٍ مغلق.
   */
  useEffect(() => {
    if (awaiting.length === 0) return;
    const timer = window.setInterval(() => {
      void load().catch(() => undefined);
    }, 5_000);
    return () => window.clearInterval(timer);
  }, [awaiting.length, load]);

  /** **«نجح دفعٌ أو شحن»** (§٦١-ي/١٠) — **عند الانتقال إلى «مسدَّدة» لا عند فتح
   * شاشةٍ مسدَّدة**: من يعود إلى رحلةٍ دفعها أمس لا يُستقبَل بنغمة نجاح. والانتقالُ
   * يقع بعد الدفع بالمحفظة لحظتَه، أو حين يؤكّد الكبتنُ كاشاً أو كليك في الاستطلاع
   * أعلاه — **والحكمُ `settlement` من الخلفية** لا حسابٌ هنا (القسم 14). */
  const wasSettled = useRef<boolean | null>(null);
  useEffect(() => {
    if (state === null) return;
    if (wasSettled.current === false && settled) play("paid");
    wasSettled.current = settled;
  }, [state, settled]);

  /** سطورُ البطاقة (`payRows`) — **قراءةٌ لا حساب**.
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
        // **رسمُ إلغاءٍ سابق** (`CANCELLATION-FEE.md` §4/§5) — سطرٌ مستقلٌّ
        // **لا مضمومٌ إلى المتبقّي**: المتبقّي أجرةُ هذه الرحلة ومنها تُحسب
        // عمولةُ كبتنها ونصيبُه، وضمُّ الدَّين إليه يحسب عمولةً على مالٍ لا
        // يخصّه. وبلا سطرٍ يراه صاحبُه لا يعرف كم يسلّم نقداً — وهو بعينه
        // العطبُ الأول: رقمٌ يُقال له إنه مدينٌ به بلا بابٍ يدفع منه
        Number(state?.cancellation_debt ?? 0) > 0
          ? {
              label: "رسمُ إلغاءٍ سابق",
              value: formatMoney(state?.cancellation_debt, state?.currency),
              strong: false,
            }
          : null,
        // **ما يفسّر الأجرةَ من داخلها** (§5.10 و§5.10-ب/و): رسمُ المحطات
        // ورسمُ الانتظار والوقفات **داخلةٌ في `final_fare`** — فهذه السطور
        // **تفصيلٌ لا إضافة**، ولذلك تلي الأجرةَ ولا تُجمع عليها.
        //
        // **ومكانُها هنا بنصِّ المواصفة**: «ولا مفاجأةَ في شاشة الدفع» — وهي
        // الشاشةُ التي كانت تعرض رقماً يخالف المقدَّر بلا سببٍ ظاهر.
        ...stopBreakdown(ride),
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

  // **التحميلُ برأس الشاشة نفسِه**: طبقةٌ فارغةٌ بدوّامةٍ في منتصفها تُقرأ عطلاً، والانتقالُ إليها بعد لحظةٍ يومض
  if (loading) {
    return (
      <div className="t2 t2-m-stage">
        <HeadT2 title="الدفع" onBack={goBack} />
        <WaitT2 label="نقرأ حال الدفع…" />
      </div>
    );
  }

  return (
    <div className="t2 t2-m-stage">
      <HeadT2 title="الدفع" onBack={() => navigate("/")} />

      {/* **ما يُدفع الآن** (بطاقةُ R10): المتبقّي لا الأجرة — لأن ما يُسأل عنه الآن هو ما يُدفع الآن — والعملةُ باسمها، والقناةُ
          في حبّة R10 */}
      <div className="t2-m-card t2-m-due">
        <div className="t2-m-due-top">
          <div>
            <div className="t2-m-label">{nothingToStart ? "إجمالي الأجرة" : "المتبقي على هذه الرحلة"}</div>
            <div className="t2-m-amount">
              <span dir="ltr" className="t2-m-num xl">
                {formatMoney(nothingToStart ? (state?.final_fare ?? null) : (state?.outstanding ?? null))}
              </span>
              <span className="t2-m-cur">{currencyLabel(state?.currency)}</span>
            </div>
            <div className="t2-m-due-cur">{currencyName(state?.currency)}</div>
          </div>
          {nothingToStart || !resolved ? null : (
            <span className="t2-m-pill">
              <Icon name={PAY_ICON_T2[resolved.method]} />
              {PAYMENT_METHOD_LABEL[resolved.method]}
            </span>
          )}
        </div>
        {rows.length > 0 ? (
          <>
            <div className="t2-m-dash tight" aria-hidden="true" />
            <div className="t2-m-rows">
              {rows.map((row) => (
                <div key={row.label} className="t2-m-row">
                  <span className="t2-m-row-label">{row.label}</span>
                  <span className={row.strong ? "t2-m-row-value strong" : "t2-m-row-value"}>{row.value}</span>
                </div>
              ))}
            </div>
          </>
        ) : null}
      </div>

      <BannerT2 tone="danger" message={error} />

      {settled ? <BannerT2 tone="ok" message="اكتمل دفع هذه الرحلة — شكراً لك." /> : null}

      {/* **لم يبقَ ما يُبدأ من هنا، ولم يكتمل الدفعُ بعد.** فلا زرَّ دفعٍ (لا صفَّ جديد يُنشأ) ولا «شكراً» (المالُ لم يصل).
          والنصُّ يسمّي القناةَ والمبلغَ لأن «بانتظار التأكيد» وحدَها لا تقول لمن يقرؤها هل عليه أن يُخرج نقداً من جيبه الآن.
          **والنزاعُ لا يُقرأ «بانتظار التأكيد»**: صفُّه لا ينتظر ضغطةً من أحد بل قراراً من الإدارة */}
      {!settled && nothingToStart ? (
        <>
          {settlement === "disputed" ? (
            <div className="t2-callout danger t2-m-callout">
              <Icon name="gavel" />
              <div className="t2-callout-main">
                <p className="t2-callout-title">على دفعة هذه الرحلة نزاعٌ مفتوح</p>
                <p className="t2-callout-body">
                  تنظر فيه الإدارة، ولا يُطلب منك دفعٌ جديدٌ الآن. يصلك الجوابُ في الإشعارات.
                </p>
              </div>
            </div>
          ) : null}
          {/* **نقدُ الراكب الفعليّ أو المستلم لا يسلّمه صاحبُ الحساب** (§٦٣-ج/١ و/٤) — «سلّم كاشاً» أمرٌ لمن ليس هناك، فسطرُه أدناه */}
          {awaiting
            .filter((row) => !(cashByOther && row.method === "cash"))
            .map((row) => (
              <div key={row.id} className="t2-callout warn t2-m-callout">
                <Icon name="hourglass_top" />
                <div className="t2-callout-main">
                  <p className="t2-callout-title">
                    {row.method === "cash"
                      ? `سلّم ${formatMoney(row.amount, row.currency)} كاشاً للكبتن`
                      : `${formatMoney(row.amount, row.currency)} بقناة ${PAYMENT_METHOD_LABEL[row.method]} بانتظار التأكيد`}
                  </p>
                  <p className="t2-callout-body">يكتمل دفعُ الرحلة حين يؤكد الكبتن استلامها في تطبيقه.</p>
                </div>
              </div>
            ))}
        </>
      ) : null}

      {/* **يدفعها الراكبُ نقداً — حالٌ تُقرأ لا قناةٌ تُختار** (§٦٣-ج/١): دفعتُه تفتحها الخلفيةُ عند الإنهاء، **فلا زرَّ دفعٍ ولا
          «طريقة أخرى»** — كلُّ قناةٍ من هذا الحساب ترتدّ. **والمبلغُ مبلغُ دفعته كما فتحتها** حين تكون قد فُتحت */}
      {/* **ومستلمُ الطرد بالحال نفسِه** (§٦٣-ج/٤) — دفعتُه يفتحها الإنهاء، وصاحبُ الحساب لا يدفع شيئاً من هنا */}
      {cashByOther && !settled && settlement !== "disputed" ? (
        <div className="t2-callout t2-m-callout">
          <Icon name="payments" />
          <div className="t2-callout-main">
            <p className="t2-callout-title">
              {recipientCash ? "يدفعها المستلمُ نقداً للكبتن" : "يدفعها الراكبُ نقداً للكبتن"}
            </p>
            <p className="t2-callout-body">
              {otherDue ? `${formatMoney(otherDue.amount, otherDue.currency)} — ` : ""}
              لا شيءَ تدفعه من تطبيقك، ويكتمل دفعُ الرحلة حين يؤكد الكبتن استلامها.
            </p>
          </div>
        </div>
      ) : null}

      {/* صفحة دفع كليك داخل التطبيق (SPEC القسم 6.2 — المرحلة 9) */}
      {state?.cliq_charge ? <CliqPanel charge={state.cliq_charge} onSubmitted={setState} /> : null}

      {state && state.payments.length > 0 ? <PaymentsList payments={state.payments} /> : null}

      <div className="t2-m-push" />

      {settled || nothingToStart || cashByOther ? (
        <button type="button" className="t2-button primary t2-m-cta" onClick={() => navigate(`/rides/${rideId}/rate`)}>
          قيّم رحلتك
        </button>
      ) : resolved ? (
        <AnimatePresence mode="wait">
          <motion.div key={resolved.method} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
            {/* **الالتزامُ بالجمر** — «طلب / قبول» في الهوية */}
            <button
              type="button"
              className="t2-button action t2-m-cta"
              disabled={busy !== null}
              aria-busy={busy === resolved.method}
              onClick={() => (resolved.method === "card" ? setChoosingCard(true) : pay(resolved.method))}
            >
              <BusyLabel busy={busy === resolved.method}>{CTA[resolved.method].label}</BusyLabel>
            </button>

            {/* **المخرجُ الذي يمنع التفضيلَ من أن يصير قيداً** (القرار 3). ولا يظهر بقناةٍ واحدة: «طريقة أخرى» حيث لا أخرى
                وعدٌ يُخلَف */}
            {available.length > 1 ? (
              <button type="button" className="t2-m-link" onClick={() => setPicking(true)}>
                طريقة أخرى
              </button>
            ) : null}

            <p className="t2-m-fine">{CTA[resolved.method].note}</p>
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

      {picking && resolved ? (
        <PaymentPicker
          channels={available}
          selected={resolved.method}
          onSelect={choose}
          onClose={() => setPicking(false)}
        />
      ) : null}
    </div>
  );
}
