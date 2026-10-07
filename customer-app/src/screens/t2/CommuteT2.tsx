/** **المشوارُ الثابت** (SPEC §٦٣-ج/٦) — اشتراكُ الراكب في تطبيقه: «مشوارٌ ثابت» (الخطّةُ فالسعرُ فالشراء) و«اشتراكاتي»، **في المظهرين**.
 *
 * **لا لوحةَ له في Claude Design** — فيُركَّب من عُدّة الهوية كما هي، **ولا شكلَ يُخترع**: رأسُ الشاشة الداخلية (`SubHeadT2`)، وبطاقةُ
 * المسار في ورقة الطلب (`t2-reqroute`) بزرّين، ومُنتقي الوجهة نفسُه (`DestinationSearch`) بعنوانه وصفِّ «موقعي الحالي»، وأزرارُ
 * «تفضيل الكبتن» للأيام (`t2-seg`)، وحقلُ التاريخ (`DateField`) — **وحقلُ الوقت بوجهه** (`.t2-date`): الحقلُ الأصليُّ يرسم خاناتِه
 * بلغة الجهاز، فالظاهرُ زرٌّ بأرقامٍ لاتينيةٍ والمنتقي منتقي النظام (علّةُ `DateField` نفسُها، §٦٢/٢٠). **و«اشتراكاتي» بطاقةُ «رحلاتي
 * المجدولة»** (R26، `t2-bk`)، والتأكيدُ ورقةُ الهوية (`DrawerT2`). **والتخطيطُ وحدَه في `commute.css`** بالرموز.
 *
 * **ولا مالَ يُحسب هنا** (§14): سعرُ الرحلة وعددُها والمجموعُ ونسبةُ الخصم وآخرُ يومٍ من التسعير في الخلفية، **والتسعيرُ يُسأل
 * كلّما تغيّرت الخطّة** (`useCommuteQuote`). وما يُعدّ هنا أيامٌ لا مال (`lib/bookings`).
 *
 * **ومطفأً لا يُشترى جديد** (`/account/commute` يعيد إلى «حسابي»)، **و«اشتراكاتي» تُقرأ ولو أُطفئ** — مالُ القائم مدفوع.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import type { Commute, CommutePlan, Coordinates } from "@/api/types";
import { DestinationSearch } from "@/components/home/DestinationSearch";
import { useGoBack } from "@/lib/back";
import {
  COMMUTE_DAYS,
  WORK_WEEK,
  clockOf,
  commuteDaysText,
  dayText,
  daysCount,
  isoDay,
  percentText,
  ridesCount,
  suspendableDays,
  useCommutePurchase,
  useCommuteQuote,
  useCommuteService,
  useMyCommutes,
} from "@/lib/bookings";
import { useMapboxToken } from "@/lib/config";
import { DEFAULT_CENTER, currentPosition, reverseGeocode, type Place } from "@/lib/geocode";
import { useSession } from "@/lib/session";
import { formatMoney } from "@/lib/utils";
import { DrawerT2 } from "@/screens/t2/DrawerT2";
import { BlankT2, LoaderT2, NoteT2, SubHeadT2 } from "@/screens/t2/KitT2";
import { DateField, Icon, Switch } from "@/taxo2";

import "./t2.css";
import "./account.css";
import "./commute.css";

interface Point {
  coordinates: Coordinates;
  address: string | null;
}

/** «HH:MM» ← «HH:MM:SS» كما تريده الخلفية. */
const wire = (clock: string) => `${clock}:00`;

/** **حقلُ الوقت بوجه حقل التاريخ** — زرٌّ بأرقامٍ لاتينيةٍ فوق حقلٍ أصليٍّ مخفيٍّ يفتح منتقيَ النظام (`showPicker`). **والقيمةُ
 *  24 ساعة** «07:30» كما يُكتب الموعدُ في كلِّ الشاشات (§20)، وحقلٌ أُفرغ لا يمحو ما كان. */
function TimeField({ value, onChange, label }: { value: string; onChange: (value: string) => void; label: string }) {
  const native = useRef<HTMLInputElement>(null);
  const open = () => {
    const input = native.current;
    if (!input) return;
    try {
      input.showPicker();
    } catch {
      input.focus();
    }
  };
  return (
    <span className="t2-date t2-cm-clock">
      <button type="button" className="t2-date-face" onClick={open} aria-label={`${label}: ${value}`}>
        <Icon name="schedule" />
        <span className="t2-date-value" dir="ltr">
          {value}
        </span>
      </button>
      <input
        ref={native}
        type="time"
        className="t2-date-native"
        tabIndex={-1}
        aria-hidden="true"
        value={value}
        step={300}
        onChange={(event) => {
          if (event.target.value) onChange(event.target.value.slice(0, 5));
        }}
      />
    </span>
  );
}

// ══════════════════════════════════════════════════════════════════ «مشوارٌ ثابت» — الخطّة والسعر والشراء

export function CommutePlanT2Screen() {
  const enabled = useCommuteService();
  const navigate = useNavigate();
  const goBack = useGoBack("/account");
  const { user } = useSession();
  const token = useMapboxToken();
  const country = user?.country_code ?? "JO";

  const [pickup, setPickup] = useState<Point | null>(null);
  const [dropoff, setDropoff] = useState<Point | null>(null);
  const [searching, setSearching] = useState<"pickup" | "dropoff" | null>(null);
  const [here, setHere] = useState<Coordinates | null>(null);
  const [hereError, setHereError] = useState<string | null>(null);
  const [weekdays, setWeekdays] = useState(WORK_WEEK);
  const [goTime, setGoTime] = useState("07:30");
  const [returnTime, setReturnTime] = useState<string | null>(null);
  // **من الغد على الأقل** (الخلفيةُ ترفض غيرَه)، **وإلى شهرٍ قادمٍ** — والغدُ أوّلُ ما يُعرض
  const { tomorrow, horizon } = useMemo(() => {
    const today = new Date();
    return {
      tomorrow: isoDay(new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1)),
      horizon: isoDay(new Date(today.getFullYear(), today.getMonth(), today.getDate() + 30)),
    };
  }, []);
  const [startsOn, setStartsOn] = useState(tomorrow);

  // **قربُ البحث من موقع الجهاز** — وبلا إذنٍ فعاصمةُ السوق
  useEffect(() => {
    let live = true;
    void currentPosition().then((point) => {
      if (live && point) setHere(point);
    });
    return () => {
      live = false;
    };
  }, []);

  // **الخطّةُ تامّةٌ أو لا تُسعَّر** — نقطتان ويومٌ واحدٌ على الأقل
  const plan: CommutePlan | null =
    pickup && dropoff && weekdays > 0
      ? {
          pickup: pickup.coordinates,
          dropoff: dropoff.coordinates,
          pickup_address: pickup.address,
          dropoff_address: dropoff.address,
          weekdays,
          go_time: wire(goTime),
          return_time: returnTime === null ? null : wire(returnTime),
          starts_on: startsOn,
        }
      : null;
  const { quote, loading, error } = useCommuteQuote(plan);
  const purchase = useCommutePurchase();

  if (!enabled) return <Navigate to="/account" replace />;

  const picked = (place: Place) => {
    const point = { coordinates: place.coordinates, address: place.address || place.name };
    if (searching === "pickup") setPickup(point);
    else setDropoff(point);
  };

  /** **«موقعي الحالي»** — موقعُ الجهاز بعنوانه من Mapbox، **وبلا إذنٍ يُقال ذلك** ويبقى البحث. */
  async function pickHere() {
    setHereError(null);
    const point = await currentPosition();
    if (!point) {
      setHereError("تعذّر تحديد موقعك — ابحث عن العنوان أو اختره من أماكنك.");
      return;
    }
    const address = token ? await reverseGeocode(token, point) : null;
    setPickup({ coordinates: point, address });
  }

  // ── بعد الشراء: ما جرى، وإلى «اشتراكاتي»
  if (purchase.bought) {
    const row = purchase.bought;
    return (
      <div className="t2 t2-page t2-cm pb-nav">
        <SubHeadT2 title="مشوارٌ ثابت" onBack={() => navigate("/account", { replace: true })} />
        <div className="t2-cm-done" role="status">
          <span className="t2-cm-done-icon" aria-hidden="true">
            <Icon name="check_circle" fill />
          </span>
          <h2 className="t2-cm-done-title">اشتركتَ في مشوارك الثابت</h2>
          <p className="t2-cm-done-body">
            خُصم <b className="t2-num">{formatMoney(row.amount_paid, row.currency)}</b> من محفظتك لـ{ridesCount(row.rides_total)}،
            تبدأ {dayText(row.starts_on)}. <b>ونبحث لك الآن عن كبتنٍ معتمدٍ</b> يعرف طريقك — تجده في «اشتراكاتي» حين يعتمده.
          </p>
        </div>
        <button
          type="button"
          className="t2-button primary t2-wide"
          onClick={() => navigate("/account/commutes", { replace: true })}
        >
          اشتراكاتي
        </button>
      </div>
    );
  }

  const toggleDay = (bit: number) => setWeekdays((mask) => mask ^ bit);
  const dayTotal = COMMUTE_DAYS.filter((day) => (weekdays & day.bit) !== 0).length;

  return (
    <div className="t2 t2-page t2-cm pb-nav">
      <SubHeadT2 title="مشوارٌ ثابت" onBack={goBack} />
      <p className="t2-cm-lede">
        مشوارُك اليوميُّ بسعرٍ مجمَّدٍ لشهرٍ كامل — <b>تدفعه مقدّماً من محفظتك</b>، ويعتمده كبتنٌ يعرف طريقك.
      </p>

      {/* **بطاقةُ المسار في ورقة الطلب** (R06) — «من» و«إلى» زرّان يفتحان المنتقي نفسَه */}
      <div className="t2-reqroute t2-cm-route">
        <span className="t2-route-from" aria-hidden="true" />
        <button type="button" className="t2-route-text t2-route-edit" onClick={() => setSearching("pickup")}>
          <span className="t2-route-label">من</span>
          <span className={pickup ? "t2-route-value" : "t2-route-value t2-cm-unset"}>
            {pickup ? (pickup.address ?? "موقعك على الخريطة") : "اختر نقطة الانطلاق"}
          </span>
        </button>
        <span />
        <span className="t2-route-join" aria-hidden="true" />
        <span />
        <span />
        <span className="t2-route-to" aria-hidden="true" />
        <button type="button" className="t2-route-text t2-route-edit" onClick={() => setSearching("dropoff")}>
          <span className="t2-route-label">إلى</span>
          <span className={dropoff ? "t2-route-value" : "t2-route-value t2-cm-unset"}>
            {dropoff ? (dropoff.address ?? "نقطة على الخريطة") : "اختر الوجهة"}
          </span>
        </button>
        <span />
      </div>
      {hereError ? <NoteT2 tone="warn">{hereError}</NoteT2> : null}

      <div className="t2-pick-head">
        <span className="t2-pick-title">أيامُ المشوار</span>
        <span className="t2-cm-aside">{dayTotal > 0 ? daysCount(dayTotal) : "اختر يوماً"}</span>
      </div>
      <div className="t2-seg t2-cm-days" role="group" aria-label="أيام المشوار">
        {COMMUTE_DAYS.map((day) => {
          const on = (weekdays & day.bit) !== 0;
          return (
            <button
              key={day.bit}
              type="button"
              aria-pressed={on}
              className={on ? "t2-seg-opt on" : "t2-seg-opt"}
              onClick={() => toggleDay(day.bit)}
            >
              {day.name}
            </button>
          );
        })}
      </div>

      <div className="t2-pick-head">
        <span className="t2-pick-title">الوقت</span>
      </div>
      <div className="t2-share t2-cm-times">
        <div className="t2-cm-time">
          <span className="t2-cm-time-label">
            <Icon name="route" />
            الذهاب
          </span>
          <TimeField value={goTime} onChange={setGoTime} label="وقت الذهاب" />
        </div>
        {/* **العودةُ اختياريّة** — بمفتاحٍ كصفِّ «حجزٌ مضمون»، **ورحلتان في اليوم بها** (التسعيرُ يعدّها) */}
        <button
          type="button"
          className="t2-cm-return"
          aria-pressed={returnTime !== null}
          onClick={() => setReturnTime((current) => (current === null ? "16:30" : null))}
        >
          <span className="t2-share-main">
            <span className="t2-share-title">رحلةُ عودة</span>
            <span className="t2-share-body">من الوجهة إلى نقطة الانطلاق في اليوم نفسِه</span>
          </span>
          <Switch on={returnTime !== null} />
        </button>
        {returnTime !== null ? (
          <div className="t2-cm-time">
            <span className="t2-cm-time-label">
              <Icon name="home" />
              العودة
            </span>
            <TimeField value={returnTime} onChange={setReturnTime} label="وقت العودة" />
          </div>
        ) : null}
      </div>

      <div className="t2-pick-head">
        <span className="t2-pick-title">يبدأ من</span>
        <span className="t2-cm-aside">شهرٌ من يوم البدء</span>
      </div>
      <DateField
        value={startsOn}
        onChange={(value) => {
          if (value) setStartsOn(value);
        }}
        label="يبدأ الاشتراك من"
        min={tomorrow}
        max={horizon}
      />

      {/* **السعرُ من الخلفية وحدَها** — والقديمُ يغيب ما دام الجديدُ يُحسب */}
      <div className="t2-share t2-cm-quote" aria-live="polite">
        <div className="t2-share-title">
          <Icon name="request_quote" />
          سعرُ اشتراكك
        </div>
        {plan === null ? (
          <p className="t2-share-body">
            {weekdays === 0 ? "اختر يوماً واحداً على الأقل." : "اختر نقطة الانطلاق والوجهة — ونحسب السعر."}
          </p>
        ) : loading ? (
          <p className="t2-share-body">نحسب…</p>
        ) : quote ? (
          <>
            <p className="t2-cm-quote-line">
              <b className="t2-num">{formatMoney(quote.price_per_ride, quote.currency)}</b> للرحلة · {ridesCount(quote.rides_total)} ·
              المجموع <b className="t2-num">{formatMoney(quote.total, quote.currency)}</b>
              <span className="t2-cm-saved"> — وفّرتَ {percentText(quote.discount_percent)}٪</span>
            </p>
            <p className="t2-share-body">
              من {dayText(startsOn)} إلى {dayText(quote.ends_on)} · السعرُ مجمَّدٌ للشهر كلِّه، لا ذروةَ ولا تغيّرَ في الطريق.
            </p>
          </>
        ) : (
          <p className="t2-share-body t2-cm-quote-error">{error}</p>
        )}
      </div>

      <p className="t2-sheet-fine">
        ما لا يُستعمل من رحلاتك يعود رصيداً في محفظتك عند نهاية الشهر — لا نقداً. ولك أن تعلّق يوماً فيُرحَّل إلى ما بعد آخر يوم.
      </p>

      {purchase.failure ? (
        <NoteT2 tone="danger">
          {purchase.failure.message}
          {purchase.failure.topup ? (
            <>
              {" "}
              <button type="button" className="t2-tlink accent t2-cm-topup" onClick={() => navigate("/wallet/topup")}>
                اشحن محفظتك
              </button>
            </>
          ) : null}
        </NoteT2>
      ) : null}

      <button
        type="button"
        className="t2-cta t2-cm-cta"
        disabled={plan === null || quote === null || loading || purchase.busy}
        aria-busy={purchase.busy}
        onClick={() => {
          if (plan) purchase.buy(plan);
        }}
      >
        <span>{purchase.busy ? "نرسل…" : "اشترك — من محفظتك"}</span>
        {quote && !loading ? <span className="t2-cta-price">{formatMoney(quote.total, quote.currency)}</span> : null}
      </button>

      <DestinationSearch
        open={searching !== null}
        onOpenChange={(open) => {
          if (!open) setSearching(null);
        }}
        token={token}
        country={country}
        near={here ?? DEFAULT_CENTER[country]}
        onPick={picked}
        title={searching === "pickup" ? "من أين تنطلق؟" : "إلى أين؟"}
        onHere={searching === "pickup" ? () => void pickHere() : undefined}
      />
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════ «اشتراكاتي»

const STATUS: Record<Commute["status"], { text: string; chip: string }> = {
  active: { text: "قائم", chip: "t2-chip ok" },
  ended: { text: "انتهى", chip: "t2-chip" },
  cancelled: { text: "أُلغي", chip: "t2-chip" },
};

type Asking = { kind: "suspend" | "cancel" | "release"; row: Commute };

export function CommutesT2Screen() {
  const service = useCommuteService();
  const navigate = useNavigate();
  const goBack = useGoBack("/account");
  const { rows, error, busy, notes, suspend, cancel, release } = useMyCommutes();
  const [asking, setAsking] = useState<Asking | null>(null);
  const [day, setDay] = useState<string | null>(null);

  const close = () => {
    setAsking(null);
    setDay(null);
  };
  const days = asking?.kind === "suspend" ? suspendableDays(asking.row) : [];

  return (
    <div className="t2 t2-page t2-cm pb-nav">
      <SubHeadT2 title="اشتراكاتي" onBack={goBack} />

      {error ? (
        <NoteT2 tone="danger" lead>
          {error}
        </NoteT2>
      ) : null}
      {rows === null && !error ? <LoaderT2 /> : null}
      {rows?.length === 0 ? (
        <BlankT2
          icon="event_repeat"
          title="لا اشتراكاتِ بعد"
          hint={service ? "اشترك في مشوارك اليوميّ بسعرٍ مجمَّدٍ لشهر." : undefined}
        />
      ) : null}

      {(rows ?? []).map((row) => (
        <CommuteCard
          key={row.id}
          row={row}
          busy={busy === row.id}
          locked={busy !== null}
          note={notes[row.id]}
          onAsk={(kind) => setAsking({ kind, row })}
        />
      ))}

      {/* **بابُ الجديد خلف المفتاح وحدَه** — والقائمُ فوقه يُرى ولو أُطفئ */}
      {service ? (
        <button type="button" className="t2-button secondary t2-wide t2-cm-new" onClick={() => navigate("/account/commute")}>
          <Icon name="add" />
          اشترك في مشوارٍ ثابت
        </button>
      ) : null}

      <DrawerT2
        open={asking?.kind === "suspend"}
        onOpenChange={(open) => {
          if (!open) close();
        }}
        title="علّق يوماً"
      >
        <p className="t2-drawer-text">
          اختر يوماً قادماً — لا تُولَّد رحلتاه، <b>ويُرحَّل إلى ما بعد آخر يومٍ</b> في اشتراكك فلا تخسر رحلةً دفعتها.
        </p>
        {days.length === 0 ? (
          <p className="t2-empty t2-cm-nodays">لا يومَ قادماً من أيام مشوارك يُعلَّق الآن.</p>
        ) : (
          <div className="t2-cm-pick" role="radiogroup" aria-label="اليوم المعلَّق">
            {days.map((iso) => (
              <button
                key={iso}
                type="button"
                role="radio"
                aria-checked={day === iso}
                className={day === iso ? "t2-seg-opt on" : "t2-seg-opt"}
                onClick={() => setDay(iso)}
              >
                {dayText(iso)}
              </button>
            ))}
          </div>
        )}
        <div className="t2-drawer-actions">
          <button
            type="button"
            className="t2-button primary"
            disabled={day === null}
            onClick={() => {
              if (asking && day) suspend(asking.row, day);
              close();
            }}
          >
            {day ? `علّق ${dayText(day)}` : "اختر يوماً"}
          </button>
          <button type="button" className="t2-button t2-quiet" onClick={close}>
            تراجع
          </button>
        </div>
      </DrawerT2>

      <DrawerT2
        open={asking?.kind === "cancel" || asking?.kind === "release"}
        onOpenChange={(open) => {
          if (!open) close();
        }}
        title={asking?.kind === "release" ? "استبدل الكبتن؟" : "ألغِ الاشتراك؟"}
      >
        <p className="t2-drawer-text">
          {asking?.kind === "release"
            ? `نفكّ ${asking.row.captain_name ?? "كبتنَك"} عن مشوارك، ويعود مفتوحاً لكبتنٍ معتمدٍ آخر — ورحلاتُك تُعرض على الكباتن حتى يعتمده غيرُه.`
            : "تُلغى رحلاتُك القادمة، ويعود ما لم يُستعمل رصيداً في محفظتك — لا نقداً."}
        </p>
        <div className="t2-drawer-actions">
          <button
            type="button"
            className="t2-button t2-destroy"
            onClick={() => {
              if (asking?.kind === "release") release(asking.row);
              else if (asking) cancel(asking.row);
              close();
            }}
          >
            {asking?.kind === "release" ? "نعم، استبدله" : "نعم، ألغِ الاشتراك"}
          </button>
          <button type="button" className="t2-button t2-quiet" onClick={close}>
            تراجع
          </button>
        </div>
      </DrawerT2>
    </div>
  );
}

/** **بطاقةُ الاشتراك** (بطاقةُ R26): الحالُ والمدّة · المسار · الأيامُ والوقتان · «اكتمل 4 من 22» · السعر · الكبتن · المعلَّق ·
 *  الأفعال. **والقائمُ بجمرٍ خافت** كالحجز المنتظر، وما مضى أبيض. **ولا يُطرح رقمٌ من رقم**: الباقي يعود رصيداً ويُقرأ في المحفظة. */
function CommuteCard({
  row,
  busy,
  locked,
  note,
  onAsk,
}: {
  row: Commute;
  busy: boolean;
  locked: boolean;
  note?: { tone: "ok" | "danger"; text: string };
  onAsk: (kind: Asking["kind"]) => void;
}) {
  const status = STATUS[row.status];
  const active = row.status === "active";
  return (
    <article className={active ? "t2-bk pending t2-cm-card" : "t2-bk t2-cm-card"} aria-busy={busy}>
      <div className="t2-bk-top">
        <span className="t2-bk-when">
          <Icon name="event_repeat" />
          {dayText(row.starts_on, true)} — {dayText(row.ends_on, true)}
        </span>
        <span className={status.chip}>{status.text}</span>
      </div>
      <div className="t2-route">
        <span className="t2-dot" />
        <span className="t2-place">{row.pickup_address ?? "نقطة على الخريطة"}</span>
        <span className="t2-dot to" />
        <span className="t2-place strong">{row.dropoff_address ?? "نقطة على الخريطة"}</span>
      </div>
      <div className="t2-cm-meta">
        <span>{commuteDaysText(row.weekdays)}</span>
        <span>
          ذهاب <span dir="ltr">{clockOf(row.go_time)}</span>
          {row.return_time ? (
            <>
              {" "}
              · عودة <span dir="ltr">{clockOf(row.return_time)}</span>
            </>
          ) : null}
        </span>
      </div>
      <div className="t2-cm-facts">
        <span className="t2-cm-done-count">
          اكتملت <b>{row.rides_done}</b> من {ridesCount(row.rides_total)}
        </span>
        <span>
          <b className="t2-num">{formatMoney(row.price_per_ride, row.currency)}</b> للرحلة · دفعتَ{" "}
          <span className="t2-num">{formatMoney(row.amount_paid, row.currency)}</span> · وفّرتَ {percentText(row.discount_percent)}٪
        </span>
      </div>
      {/* **سطرُ الكبتن للقائم وحدَه** — اسمُه حين اعتمده أحد، و«نبحث…» ما دام مفتوحاً */}
      {active ? (
        <p className={row.captain_name ? "t2-cm-captain named" : "t2-cm-captain"}>
          <Icon name={row.captain_name ? "verified_user" : "search"} />
          {row.captain_name ? `كبتنُك: ${row.captain_name}` : "نبحث لك عن كبتنٍ معتمد"}
        </p>
      ) : null}
      {row.suspended_days.length > 0 ? (
        <p className="t2-cm-suspended">
          علّقتَ: {row.suspended_days.map((iso) => dayText(iso, true)).join(" · ")}
        </p>
      ) : null}
      {note ? <NoteT2 tone={note.tone}>{note.text}</NoteT2> : null}
      {active ? (
        <div className="t2-cm-actions">
          <button type="button" className="t2-tlink" disabled={locked} onClick={() => onAsk("suspend")}>
            علّق يوماً
          </button>
          {row.captain_name ? (
            <button type="button" className="t2-tlink" disabled={locked} onClick={() => onAsk("release")}>
              استبدل الكبتن
            </button>
          ) : null}
          <button type="button" className="t2-tlink destroy" disabled={locked} onClick={() => onAsk("cancel")}>
            ألغِ الاشتراك
          </button>
        </div>
      ) : null}
    </article>
  );
}
