/** **C08 — إنهاءُ الرحلة والتحصيل** (TAXO 2.0، الليليُّ المرسوم وحدَه — §٦١-د).
 *
 * **أين المالُ الآن يُصنَّف في بيته الواحد** (`collectView` في `screens/Collect`)، **والدفعاتُ تُقرأ بخطّافها**
 * (`useCollectScreen` — وتُعاد كلَّ خمس ثوانٍ حتى يختار الراكبُ قناته)، **والتقييمُ بخطّافه** (`useRateRider`). فلا مبلغَ يُحسب
 * هنا (§14): الأجرةُ والدفعاتُ كما وصلت، والطرحُ المرسومُ («−1.000» ثمّ «المتبقي كاش») **عرضٌ لمبلغين من الخلفية لا حساب**.
 *
 * **والتقييمُ في الشاشة نفسِها كما رُسم** — نجومُه اختياريّةٌ كما كانت («تخطي» في الشاشة القائمة ⇐ ألّا تُختار نجمة):
 * الزرُّ يؤكّد الدفعةَ التي بيده إن كانت (`POST /payments/{id}/confirm`) ثمّ يرسل التقييمَ إن اختير (`POST /ratings`) —
 * **الطلبان نفسُهما بترتيبهما**، والشاشتان القائمتان صارتا واحدة.
 *
 * **وما رسمته اللوحةُ ولا بابَ له** (§٦١-د/د): «0% — مشترك» و«0.000» ⇐ **«عمولة أقل بكثير من السوق»** بلا نسبةٍ ولا رقم
 * (التصحيحات §١) · **«تُضاف 3.750 د.أ كاملة إلى أرباحك»**: مبلغٌ يُطرح منه شيءٌ أو وعدٌ مطلق — والسطرُ القائمُ الذي يقول أين
 * المالُ في موضعه · **«لم أستلم المبلغ — افتح نزاعاً»**: النزاعُ على كليك وحدها (`Dispute.tsx`)، **ولا نزاعَ على كاش** · اسمُ الراكب.
 *
 * **ورحلةٌ لشخصٍ آخر** (§٦٣-ج/١): نقدُ الراكب الفعليّ دفعةُ كاشٍ تفتحها الخلفيةُ عند الإنهاء — **فيمرّ بالتأكيد القائم كما هو**؛
 * **ودفعُ صاحب الطلب لا يُقبض هنا**، فيُقال «لا تستلم شيئاً» ما دامت دفعتُه لم تصل.
 *
 * **والطردُ الذي يدفعه مستلمُه** (§٦٣-ج/٤) **بالتأكيد القائم نفسِه** — دفعتُه يفتحها الإنهاء — **وعنوانُه «استلم من المستلم»**:
 * «حصّل من الراكب» تُرسله إلى من ليس في السيارة.
 *
 * **ورحلةُ المشوار الثابت** (§٦٣-ج/٦) «مدفوعة من اشتراك الراكب — لا تستلم شيئاً»: دفعتُها بقناة الاشتراك تكتبها الخلفيةُ عند الإنهاء.
 */

import { useState } from "react";

import { ApiError } from "@/api/client";
import { confirmPayment } from "@/api/endpoints";
import type { Ride } from "@/api/types";
import { Spinner } from "@/components/ui/Feedback";
import { refreshAfterConfirm } from "@/lib/attention";
import { useCoverNav } from "@/lib/navCover";
import { METHOD_LABEL, roundingLine, trimDistance } from "@/lib/rideFormat";
import { play } from "@/lib/sound";
import { DISPLAY_LOCALE, digits } from "@/lib/utils";
import { collectView, useCollectScreen } from "@/screens/Collect";
import { useRateRider } from "@/screens/RateRider";
import { Icon } from "@/taxo2"; import { tr } from "@/lib/i18n";

export function CollectT2Screen({
  ride,
  currencyLabel,
  onDone,
}: {
  ride: Ride;
  currencyLabel: string;
  onDone: () => void;
}) {
  // **الزرُّ في قاع الشاشة حيث يطفو الشريط** — والرحلةُ صارت `null` فلا يُخفيه شيءٌ غيرُ هذا (`lib/navCover`)
  useCoverNav(true);
  const { state, error, setError, busy, setBusy } = useCollectScreen(ride);
  const rate = useRateRider(ride, onDone);
  // **دفعةٌ أُكّدت لا تُؤكَّد ثانيةً** إن سقط التقييمُ بعدها — فالضغطةُ التاليةُ ترسل التقييمَ وحدَه
  const [confirmedId, setConfirmedId] = useState<string | null>(null);

  if (!state) {
    return (
      <div className="t2 t2-co">
        <div className="t2-co-loading">
          <Spinner />
        </div>
      </div>
    );
  }

  const { pending, credited, kept, commission, mixed, headline } = collectView(state, ride);
  // **وقبل النهائيّة عدّادُ الخلفية مقرَّباً** (`current_fare`، SPEC §٧٠-ج/٤) — لا المقدَّرةُ الدقيقة
  const final = state.final_fare ?? ride.current_fare;
  // **وفرقُ التقريب سطرٌ بذاته** (§٧٠-ج/٤) — من `fare_lines` كما كتبته الخلفية، له أو عليه
  const rounding = roundingLine(ride);
  const rest = pending ?? kept[0];

  async function finish() {
    setError(null);
    if (pending && pending.id !== confirmedId) {
      setBusy(true);
      try {
        await confirmPayment(pending.id);
        refreshAfterConfirm();
        // **نغمةُ التحصيل عند وقوعه لا عند فتح الشاشة** — كما في الشاشة القائمة
        play("collected");
        setConfirmedId(pending.id);
      } catch (caught) {
        setError(caught instanceof ApiError ? caught.message : tr("تعذّر تأكيد الدفعة"));
        setBusy(false);
        return;
      }
      setBusy(false);
    }
    if (rate.stars > 0) await rate.submit();
    else onDone();
  }

  // «سيتي مول · 10:26 ص · 6.8 كم» — الوجهةُ بأوّل مقطعٍ منها، ووقتُ الإنهاء، والمسافةُ الفعليةُ حين تُقاس
  const place = (ride.dropoff_address ?? tr("الوجهة")).split("،")[0];
  const time = ride.completed_at
    ? digits(new Date(ride.completed_at).toLocaleTimeString(DISPLAY_LOCALE, { hour: "numeric", minute: "2-digit" }))
    : null;
  const sub = [place, time, ride.actual_distance_km ? tr("{0} كم", { 0: trimDistance(ride.actual_distance_km) }) : null]
    .filter(Boolean)
    .join(" · ");

  // **العنوانُ الكبيرُ بالجمر حين يكون المالُ بيده** — وما دخل محفظتَه أو لم يُعرف بعدُ على السطح: «حصّل» على مالٍ لا
  // يُحصَّل تُقرأ أمراً بقبض ما قُبض
  const inHand = pending !== undefined || headline.hand;
  // **رحلةُ المشوار الثابت** (§٦٣-ج/٦) — دفعها الراكبُ مقدّماً مع اشتراكه، **وتُسوّى من المحفوظ عند الإنهاء** فتُقيَّد له كأيِّ
  // أجرة: «حصّل» أو «أُضيف» وحدها لا تقول إن الراكبَ لا يُطالَب بشيء — فتُقال صريحةً. ومن الصفّ لا من المفتاح
  const commute = ride.commute;
  // **ومن مستلم الطرد** (§٦٣-ج/٤) — دفعتُه نقدٌ فتحه الإنهاء، ويُسلَّم عند التسليم لا من راكب
  const caption = commute
    ? tr("مدفوعة من اشتراك الراكب — لا تستلم شيئاً")
    : pending
      ? ride.payer === "recipient_cash"
        ? tr("استلم من المستلم")
        : tr("حصّل من الراكب {0}", { 0: METHOD_LABEL[pending.method] })
      : headline.caption;
  const creditedFirst = credited[0];
  const split =
    mixed && creditedFirst && rest
      ? creditedFirst.method === "wallet"
        ? tr("دفع الراكب {0} {1} من محفظته، وقُيّدت في محفظتك. والباقي {2}.", { 0: digits(creditedFirst.amount), 1: currencyLabel, 2: METHOD_LABEL[rest.method] })
        : tr("دُفع {0} {1} ({2}) وقُيّد في محفظتك. والباقي {3}.", { 0: digits(creditedFirst.amount), 1: currencyLabel, 2: METHOD_LABEL[creditedFirst.method], 3: METHOD_LABEL[rest.method] })
      : null;

  // **رحلةٌ لغيره يدفعها صاحبُ الطلب** (§٦٣-ج/١) — من تطبيقه بمحفظةٍ أو بطاقة، **فلا مالَ يُقبض هنا أبداً**: ما دامت دفعتُه لم
  // تصل يُقال ذلك بنبرة التنبيه بدل «لم يختر الراكب طريقة الدفع» — وهي تأمر ضمناً بانتظار مالٍ من يد الراكب الذي في السيارة
  const byRequester = ride.for_other && ride.payer === "requester" && !pending && !headline.hand && credited.length === 0;

  // **سطرُ «أين المال» بنصّه من الشاشة القائمة** — والنصُّ هناك في JSX، فيُكتب هنا بحرفه (`screens/Collect.tsx`)
  const note =
    (commute
      ? credited.length > 0
        ? tr("سعرُها المجمَّد دُفع من اشتراك الراكب وقُيّد في محفظتك — لا نقدَ ولا قناة.")
        : tr("سعرُها المجمَّد يُدفع من اشتراك الراكب ويُقيَّد في محفظتك — ستظهر الدفعةُ هنا وفي سجل رحلاتك.")
      : byRequester
      ? tr("يدفعها صاحبُ الطلب من تطبيقه — لا تستلم شيئاً.")
      : pending
        ? tr("هذا المبلغ يبقى معك ولا يمر بمحفظتك. وتأكيدك هو ما يُثبّته — إن لم يصلك فافتح نزاعاً من تفاصيل الرحلة.")
        : headline.hand
          ? tr("هذا المبلغ بقي معك ولم يمر بمحفظتك.")
          : credited.length > 0
            ? tr("المال وصل قبل إنهائك الرحلة — قيدُ أرباحك في المحفظة تلقائي.")
            : tr("لم يختر الراكب طريقة الدفع بعد — ستظهر الدفعة هنا وفي سجل رحلاتك.")) +
    (commission > 0 ? tr(" والعمولة تُخصم من رصيد محفظتك، لا من هذا المبلغ.") : "");

  const working = busy || rate.busy;
  const message = error ?? rate.error;

  return (
    <div className="t2 t2-co">
      <div className="t2-co-head">
        <span className="t2-co-done" aria-hidden="true">
          <Icon name="check" />
        </span>
        <div>
          <div className="t2-co-title">{tr("اكتملت الرحلة")}</div>
          <div className="t2-co-sub">{sub}</div>
        </div>
      </div>

      <div className={`t2-co-card${inHand ? "" : " calm"}`}>
        {inHand ? <span className="t2-co-stripe" aria-hidden="true" /> : null}
        <div className="t2-co-caption">{caption}</div>
        <div className="t2-co-amount">
          <span className="t2-co-amount-num" dir="ltr">
            {digits(headline.amount)}
          </span>
          <span className="t2-co-amount-cur">{currencyLabel}</span>
        </div>
        {split ? <div className="t2-co-split">{split}</div> : null}
      </div>

      <div className="t2-co-rows">
        {/* **المقدَّرُ حين يخالف النهائيَّ وحدَه** — والمساويه سطرٌ يكرّر رقماً (الشاشةُ القائمةُ تعرضهما دائماً) */}
        {ride.estimated_fare !== final ? (
          <>
            <span className="t2-co-k">{tr("السعر المقدّر")}</span>
            <span className="t2-co-v" dir="ltr">
              {digits(ride.estimated_fare)}
            </span>
          </>
        ) : null}
        {rounding !== null ? (
          <>
            <span className="t2-co-k">{tr("تقريب")}</span>
            <span className="t2-co-v" dir="ltr">
              {rounding}
            </span>
          </>
        ) : null}
        <span className="t2-co-k">{tr("الأجرة النهائية")}</span>
        <span className="t2-co-v" dir="ltr">
          {digits(final)}
        </span>
        {mixed
          ? credited.map((payment) => (
              <Row
                key={payment.id}
                label={payment.method === "wallet" ? tr("من محفظة الراكب") : METHOD_LABEL[payment.method]}
                value={`−${digits(payment.amount)}`}
              />
            ))
          : null}
        {mixed && rest ? (
          <Row label={tr("المتبقي {0}", { 0: METHOD_LABEL[rest.method] })} value={digits(rest.amount)} strong />
        ) : null}
        {/* **ما قُيّد له ولا شيءَ بيده** — سطرُ الشاشة القائمة بنبرته («قُيّد في محفظتك») */}
        {!mixed && creditedFirst ? (
          <Row label={tr("قُيّد في محفظتك")} value={digits(creditedFirst.amount)} ok />
        ) : null}
        {/* **«عمولة أقل بكثير من السوق» — بلا نسبةٍ ولا رقم** (التصحيحات §١) */}
        <span className="t2-co-k">
          {tr("عمولة")}<span className="t2-co-pill">{tr("أقل بكثير من السوق")}</span>
        </span>
        <span />
      </div>

      <p className={byRequester ? "t2-co-note warn" : "t2-co-note"}>
        <Icon name="info" />
        <span>{note}</span>
      </p>

      {/* **التقييمُ اختياريّ** — ونجمةٌ تُضغط ثانيةً تُلغى. وترتيبُها ترتيبُ الصفّ العربيّ كما رُسم (الأولى في البداية) */}
      <div className="t2-co-rate">
        <span className="t2-co-rate-title">{tr("قيّم الراكب")}</span>
        <span className="t2-co-stars">
          {[1, 2, 3, 4, 5].map((value) => (
            <button
              key={value}
              type="button"
              aria-label={tr("{0} نجوم", { 0: value })}
              aria-pressed={value <= rate.stars}
              className={`t2-co-star${value <= rate.stars ? " on" : ""}`}
              onClick={() => rate.setStars(value === rate.stars ? 0 : value)}
            >
              <Icon name="star" fill={value <= rate.stars} />
            </button>
          ))}
        </span>
      </div>

      <div className="t2-co-gap" />

      {message ? (
        <p className="t2-note danger t2-co-error">
          <Icon name="error" fill />
          {message}
        </p>
      ) : null}

      <button type="button" className="t2-co-btn" onClick={() => void finish()} disabled={working}>
        {pending && pending.id !== confirmedId
          ? pending.method === "cliq"
            ? tr("وصلتني الحوالة")
            : tr("استلمتُ {0} {1}", { 0: digits(pending.amount), 1: currencyLabel })
          : rate.stars > 0
            ? tr("إرسال التقييم")
            : tr("إنهاء")}
      </button>
    </div>
  );
}

function Row({ label, value, strong = false, ok = false }: { label: string; value: string; strong?: boolean; ok?: boolean }) {
  return (
    <>
      <span className={`t2-co-k${strong ? " strong" : ""}`}>{label}</span>
      <span className={`t2-co-v${strong ? " strong" : ""}${ok ? " ok" : ""}`} dir="ltr">
        {value}
      </span>
    </>
  );
}
