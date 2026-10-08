/** **بالساعة** (§٦٣-ج/٥) — وجوهُها في تطبيق الكبتن: **سطرُها قبل البدء** (الساعاتُ وكيلومتراتُها ومن أين يُدفع المحجوز)، **وعدّادُها
 * أثناء الرحلة** (الوقتُ الباقي من الساعات والكيلومتراتُ المشمولة)، **وبطاقةُ نقد المحجوز** حين يُدفع نقداً عند البدء.
 *
 * **لا لوحةَ لها في Claude Design** — فتُركَّب من عُدّة الهوية: شريطُ المحطات والوقفة (`t2-rd-strip`) للسطر والعدّاد بنبرة تنبيهه،
 * **وزرُّ الفعل** (`t2-rd-btn`) لتأكيد الاستلام. وشارةُ «بالساعة» على العرض في بيتها (`OfferT2`).
 *
 * **ولا مالَ يُحسب هنا** (§14): الكيلومتراتُ المشمولةُ من الرحلة (`hourly_included_km`)، ومبلغُ المحجوز من دفعته كما فتحتها الخلفيةُ
 * عند البدء — **والتأكيدُ هو بابُ الكاش القائم نفسُه** (`POST /payments/{id}/confirm`). وما يُحسب وقتٌ: الباقي من «البدء + الساعات».
 */

import { useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { confirmPayment, getRidePayments } from "@/api/endpoints";
import type { Payment, Ride } from "@/api/types";
import { refreshAfterConfirm } from "@/lib/attention";
import { digits } from "@/lib/utils";
import { Icon } from "@/taxo2";

/** «ساعة واحدة · ساعتان · 3 ساعات · 11 ساعة» — **العربيةُ تعدّ بالمثنّى والجمع**، والخاناتُ لاتينية (§20). */
export function hoursLabel(count: number): string {
  if (count === 1) return "ساعة واحدة";
  if (count === 2) return "ساعتان";
  if (count <= 10) return `${digits(count)} ساعات`;
  return `${digits(count)} ساعة`;
}

/** **رحلةُ ساعاتٍ بلا وجهة** — الطلبُ أرسل نقطةَ الانطلاق نفسَها وجهةً (عقدُ `HourlyIn`)، فالوجهاتُ يقولها الراكب. */
export function noDestination(ride: Ride): boolean {
  return ride.pickup.lat === ride.dropoff.lat && ride.pickup.lng === ride.dropoff.lng;
}

/** «1:59:30» أو «59:30» — ساعةٌ رقميّةٌ بخاناتٍ لاتينية، والساعاتُ حين تبلغ واحدةً وحدَها. */
function clockText(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  const h = Math.floor(whole / 3600);
  const m = Math.floor((whole % 3600) / 60);
  const s = whole % 60;
  const pad = (value: number) => String(value).padStart(2, "0");
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

/** **سطرُ الساعات قبل البدء** (C06) — «بالساعة · 3 ساعات · حتى 45 كم»، **ومن أين يُدفع المحجوزُ عند البدء**: نقدٌ يستلمه هو
 *  بنبرة النجاح (مالٌ في اليد)، أو محفظةُ الراكب. **فيعرف قبل أن يضغط «ابدأ» ما الذي سيقع عند الضغط.** */
export function HourlyPlanT2({ ride }: { ride: Ride }) {
  if (ride.ride_type !== "hourly" || ride.hourly_hours === null) return null;
  return (
    <div className="t2-rd-strip t2-hr-plan">
      <div className="t2-rd-strip-row">
        <span className="t2-rd-strip-label">بالساعة</span>
        <span className="t2-rd-strip-min">
          {hoursLabel(ride.hourly_hours)}
          {ride.hourly_included_km !== null ? ` · حتى ${digits(ride.hourly_included_km)} كم` : ""}
        </span>
      </div>
      {ride.hourly_prepay_method ? (
        <p className={ride.hourly_prepay_method === "cash" ? "t2-fo-payer ok" : "t2-fo-payer"}>
          <Icon name={ride.hourly_prepay_method === "cash" ? "payments" : "account_balance_wallet"} />
          <span>
            {ride.hourly_prepay_method === "cash"
              ? "تستلم الساعاتِ المحجوزة نقداً عند البدء"
              : "تُدفع الساعاتُ المحجوزة من محفظة الراكب عند البدء"}
          </span>
        </p>
      ) : null}
    </div>
  );
}

/** **عدّادُ الساعات أثناء الرحلة** (C07) — «الوقتُ الباقي 1:59:30 / ساعتان» و«الكيلومترات المشمولة: 30»، **ثمّ «وقتٌ زائد» بنبرة
 *  التنبيه** حين تنفد الساعات. **يتقدّم كلَّ ثانيةٍ محلّياً من البدء المقيس** (`started_at`) كعدّاد الوقفة — **والمستهلَكُ من
 *  الكيلومترات لا يُرسم**: حسابُه حيّاً يحتاج نقاطَ المسار كلَّ ثوانٍ (§٦٣-ج/٥، «ما لا يُبنى في هذه الدفعة»)، ويُرى في ملخّص الإنهاء. */
export function HourlyMeterT2({ ride }: { ride: Ride }) {
  const [now, setNow] = useState(() => Date.now());
  const running = ride.ride_type === "hourly" && ride.started_at !== null && ride.hourly_hours !== null;
  useEffect(() => {
    if (!running) return;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [running]);
  if (!running || ride.started_at === null || ride.hourly_hours === null) return null;
  const started = new Date(ride.started_at).getTime();
  if (Number.isNaN(started)) return null;
  const left = Math.round((started + ride.hourly_hours * 3_600_000 - now) / 1000);
  const over = left > 0 ? 0 : Math.floor(-left / 60);
  return (
    <div className={left > 0 ? "t2-rd-strip t2-hr-meter" : "t2-rd-strip t2-hr-meter warn"} role="timer">
      <div className="t2-rd-strip-row">
        {left > 0 ? (
          <>
            <span className="t2-rd-strip-label">الوقتُ الباقي</span>
            <span className="t2-hr-clock" dir="ltr">
              {clockText(left)}
            </span>
            <span className="t2-rd-strip-min">/ {hoursLabel(ride.hourly_hours)}</span>
          </>
        ) : (
          <span className="t2-rd-strip-label t2-hr-over">وقتٌ زائد · {digits(over)} د</span>
        )}
        {ride.hourly_included_km !== null ? (
          <span className="t2-rd-strip-end">الكيلومترات المشمولة: {digits(ride.hourly_included_km)}</span>
        ) : null}
      </div>
      {left > 0 ? null : (
        <p className="t2-rd-strip-warn">ما زاد على الساعات يُحسب على الراكب بالتعرفة العاديّة عند الإنهاء.</p>
      )}
    </div>
  );
}

/** **بطاقةُ نقد المحجوز** (C07) — رحلةُ ساعاتٍ تُدفع نقداً عند البدء: البدءُ فتح دفعةَ كاشٍ معلَّقةً بمبلغ الساعات المحجوزة،
 *  **فتُقرأ من دفعات الرحلة** (`GET /rides/{id}/payments`) **وتُؤكَّد بباب الكاش القائم** — كما يؤكّد الكبتنُ أيَّ كاشٍ في التحصيل.
 *  **والمبلغُ مبلغُ الدفعة كما فتحتها الخلفية** لا ساعاتٌ تُضرب في سعر. ودفعةٌ أُكّدت تختفي البطاقةُ بعدها؛ ولا شيءَ يُرسم قبل أن تُقرأ. */
export function HourlyCashCardT2({ ride, currencyLabel }: { ride: Ride; currencyLabel: string }) {
  const due =
    ride.ride_type === "hourly" &&
    ride.hourly_prepay_method === "cash" &&
    (ride.status === "in_progress" || ride.status === "at_stop");
  const [pending, setPending] = useState<Payment | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!due) {
      setPending(null);
      return;
    }
    let live = true;
    // **قبل الإنهاء لا كاشَ معلَّقاً على الرحلة إلا المحجوز** — دفعةُ ما زاد يفتحها الإنهاءُ نفسُه
    getRidePayments(ride.id)
      .then((state) => {
        if (!live) return;
        setPending(state.payments.find((row) => row.method === "cash" && row.status === "pending") ?? null);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [due, ride.id]);

  if (!due || !pending) return null;

  async function confirm() {
    if (!pending) return;
    setBusy(true);
    setError(null);
    try {
      await confirmPayment(pending.id);
      refreshAfterConfirm();
      setPending(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر تأكيد الدفعة");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="t2-rd-strip t2-hr-cash">
      <div className="t2-hr-cash-title">
        <Icon name="payments" />
        {/* **الرقمُ وحدَه يسارياً** — والعلامةُ بعده في سياق السطر العربيّ: «16.000 د.أ» لا «د.أ 16.000» */}
        <span>
          استلم <b dir="ltr">{digits(pending.amount)}</b> {currencyLabel} نقداً — الساعاتُ المحجوزة
        </span>
      </div>
      <p className="t2-hr-cash-note">يبقى معك ولا يمرّ بمحفظتك، وتأكيدُك هو ما يُثبّته. وما زاد يُحصَّل عند الإنهاء.</p>
      {error ? (
        <p className="t2-note danger t2-rd-error">
          <Icon name="error" fill />
          {error}
        </p>
      ) : null}
      <button type="button" className="t2-rd-btn t2-hr-cash-btn" disabled={busy} onClick={() => void confirm()}>
        استلمتُ {digits(pending.amount)} {currencyLabel}
      </button>
    </div>
  );
}
