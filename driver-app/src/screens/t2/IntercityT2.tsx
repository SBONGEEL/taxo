/** **بين المدن** (SPEC §٦٣-ج/٧) — «أعلن رحلة» و«رحلاتُك» في صفحةٍ واحدة، **في المظهرين** — لا لوحةَ لها: أختُ «المشاوير الثابتة»
 * (`CommutesT2`) **بعُدّتها وأصنافها نفسِها** (`guarantees.css`): الرأس · عنوانُ القسم · البطاقة · الشارة · الأزرار · البلاغ · الفراغ،
 * **وحقلُ الموعد حقلُ الهوية** (`DateField`)، وتسميةُ الحقل بلغة حقول الكبتن (`fields.css`). **وتخطيطُ ما زاد في `intercity.css`**
 * بالرموز وحدَها.
 *
 * **الكبتنُ سيّدُ رحلته** (نصُّ المالك): يعلنها بمقاعدها وأقلِّ عددٍ ينطلق به، **ويلغيها قبل المهلة بلا أثر** ويُردّ للركّاب كاملاً،
 * وينطلق وينهي. **و«أعلن رحلة» خلف المفتاح، و«رحلاتُك» تُقرأ ولو أُطفئ** — ركّابٌ حجزوا ينتظرونه.
 *
 * **والأفعالُ أبوابُ الخلفية بحرفها، ورسائلُها كما ردّتها** (`useIntercityBoard`): بلا تصريحٍ «رحلاتُ بين المدن بتصريحٍ بعد فحص
 * مركبتك — راجع الدعم»، **ومهلةُ الإلغاء لا تُنشر فلا يُكتب رقمُها هنا** — «قبل المهلة» نصّاً، والخلفيةُ تقول ساعاتِها حين تفوت.
 * **ولا مالَ يُحسب هنا** (§14): السعران كما وصلا، ولا يُضربان في مقعد.
 */

import { useState, type ReactNode } from "react";

import type { IntercityRoute, IntercityTrip } from "@/api/types";
import { Spinner } from "@/components/ui/Feedback";
import { useGoBack } from "@/lib/back";
import { useCountryConfig } from "@/lib/config";
import { useIntercityBoard } from "@/lib/guarantees";
import { useSession } from "@/lib/session";
import { currencyLabel, digits, DISPLAY_LOCALE } from "@/lib/utils";
import { DateField, Icon } from "@/taxo2";

import { countSeats } from "./count";

import "./t2.css";
import "./guarantees.css";
import "./fields.css";
import "./intercity.css"; import { tr } from "@/lib/i18n";

/** **أقصى مقاعد الإعلان** — سيارةُ التصريح أربعةُ مقاعدَ على الأقل، **والخلفيةُ تعيد الفحصَ بمقاعد تصريحه** وترفض بنصّها. */
const MAX_SEATS = 4;

const STATUS: Record<IntercityTrip["status"], { text: string; chip: string }> = {
  open: { text: tr("مفتوحة"), chip: "t2-chip ok" },
  departed: { text: tr("انطلقت"), chip: "t2-chip warn" },
  completed: { text: tr("اكتملت"), chip: "t2-chip" },
  cancelled: { text: tr("أُلغيت"), chip: "t2-chip" },
};

/** «الخميس 8 أكتوبر · 07:30» — **الساعةُ بخاناتٍ لاتينيةٍ و24 ساعة** (§20)، بتوقيت الجهاز. */
function when(iso: string): { day: string; time: string } {
  const at = new Date(iso);
  return {
    day: digits(at.toLocaleDateString(DISPLAY_LOCALE, { weekday: "long", day: "numeric", month: "long" })),
    time: digits(at.toLocaleTimeString(DISPLAY_LOCALE, { hour: "2-digit", minute: "2-digit", hour12: false })),
  };
}

/** قيمةٌ لحقل `datetime-local` **بالوقت المحلّيّ لا UTC** — `toISOString` يعطي UTC فيرى صاحبُه ساعةً غيرَ ساعته. */
function localValue(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

export function IntercityT2Screen() {
  const goBack = useGoBack("/");
  const { enabled, routes, trips, error, busy, notes, posting, post, act } = useIntercityBoard();

  return (
    <div className="t2 t2-gu">
      <div className="t2-gu-scroll scr">
        <div className="t2-head">
          <button type="button" className="t2-back" aria-label={tr("رجوع")} onClick={() => goBack()}>
            <Icon name="arrow_forward" />
          </button>
          <h1 className="t2-title">{tr("بين المدن")}</h1>
        </div>
        <p className="t2-gu-lede">
          {tr("رحلتُك بين مدينتين — تعلنها بمقاعدها وأقلِّ عددٍ تنطلق به، فيحجز الركّابُ مقاعدَ من محافظهم أو السيارةَ كاملةً نقداً لك.")}{" "}
          <b>{tr("وتلتقيهم في نقطة التجمّع.")}</b>
        </p>

        {error ? (
          <p className="t2-note danger" role="alert">
            <Icon name="error" />
            {error}
          </p>
        ) : null}

        {trips === null ? (
          error ? null : (
            <div className="t2-gu-wait" aria-busy="true">
              <Spinner />
            </div>
          )
        ) : (
          <>
            {/* **الإعلانُ خلف المفتاح** — ومطفأً لا نموذجَ يَعِد بما سيُرفض */}
            {enabled ? (
              <section>
                <div className="t2-section">{tr("أعلن رحلة")}</div>
                <PostForm routes={routes ?? []} busy={busy === "post"} locked={busy !== null} note={posting} onPost={post} />
              </section>
            ) : null}

            <section>
              <div className="t2-section">
                {tr("رحلاتُك")}
                {trips.length > 0 ? (
                  <span className="t2-section-aside" dir="ltr">
                    {digits(String(trips.length))}
                  </span>
                ) : null}
              </div>
              {trips.length === 0 ? (
                <p className="t2-empty">
                  {enabled ? tr("لم تعلن رحلةً بعد. أعلنها أعلاه — وتظهر للركّاب في سوقك حتى موعدها.") : tr("لا رحلاتِ لك.")}
                </p>
              ) : (
                trips.map((trip) => (
                  <TripCard
                    key={trip.id}
                    trip={trip}
                    busy={busy === trip.id}
                    locked={busy !== null}
                    note={notes[trip.id]}
                    onAct={(kind) => act(trip, kind)}
                  />
                ))
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}

/** **العدّادُ بين حدّين** — «−  2  +». */
function Stepper({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
}) {
  return (
    <div className="t2-ict-stepper">
      <button
        type="button"
        className="t2-ict-step"
        aria-label={tr("{0}: أقل", { 0: label })}
        disabled={value <= min}
        onClick={() => onChange(Math.max(min, value - 1))}
      >
        <Icon name="remove" />
      </button>
      <span className="t2-ict-count" dir="ltr" aria-live="polite">
        {digits(String(value))}
      </span>
      <button
        type="button"
        className="t2-ict-step"
        aria-label={tr("{0}: أكثر", { 0: label })}
        disabled={value >= max}
        onClick={() => onChange(Math.min(max, value + 1))}
      >
        <Icon name="add" />
      </button>
    </div>
  );
}

/** **نموذجُ الإعلان** — المسارُ من مسارات سوقه بسعريه، والموعد، والمقاعدُ (١–٤)، وأقلُّ ما ينطلق به (١ إلى المقاعد). **والموعدُ
 *  لا يُقيَّد بالمهلة هنا**: لا تُنشر ساعاتُها، والخلفيةُ ترفض الأقربَ برسالةٍ تقول ساعاتِها. */
function PostForm({
  routes,
  busy,
  locked,
  note,
  onPost,
}: {
  routes: IntercityRoute[];
  busy: boolean;
  locked: boolean;
  note: { tone: "ok" | "danger"; text: string } | null;
  onPost: (body: { route_id: string; departs_at: string; seats: number; min_seats: number }) => Promise<boolean>;
}) {
  const [routeId, setRouteId] = useState<string | null>(null);
  const [at, setAt] = useState("");
  const [seats, setSeats] = useState(MAX_SEATS);
  const [minSeats, setMinSeats] = useState(1);
  const ready = routeId !== null && at !== "";
  // **عملةُ سوقه من الإعدادات** — المسارُ لا يحمل عملتَه، ومساراتُه كلُّها في سوقه
  const { user } = useSession();
  const cur = currencyLabel(useCountryConfig(user?.country_code)?.currency);

  if (routes.length === 0) {
    return <p className="t2-empty">{tr("لا مساراتٍ مفعّلةً في سوقك بعد — يضيفها TAXO بين المدن بسعري المقعد والسيارة.")}</p>;
  }

  return (
    <div className="t2-gu-card t2-ict-form">
      <span className="t2-fld-label">{tr("المسار")}</span>
      <div className="t2-ict-routes" role="radiogroup" aria-label={tr("المسار")}>
        {routes.map((route) => {
          const on = route.id === routeId;
          return (
            <button
              key={route.id}
              type="button"
              role="radio"
              aria-checked={on}
              className={on ? "t2-ict-route on" : "t2-ict-route"}
              onClick={() => setRouteId(route.id)}
            >
              <span className="t2-ict-route-name">
                {tr("من")}{" "}{route.from_city}{" "}{tr("إلى")}{" "}{route.to_city}
              </span>
              <span className="t2-ict-route-meta">{route.from_point}</span>
              <span className="t2-ict-route-meta">
                <b dir="ltr">{digits(route.price_seat)}</b> {cur}{" "}{tr("للمقعد ·")}{" "}<b dir="ltr">{digits(route.price_car)}</b> {cur}{" "}{tr("للسيارة")}
              </span>
            </button>
          );
        })}
      </div>

      <label className="t2-fld-label t2-ict-gap" htmlFor="intercity-at">
        {tr("موعد الانطلاق")}
      </label>
      <DateField
        id="intercity-at"
        kind="datetime-local"
        value={at}
        min={localValue(new Date())}
        onChange={setAt}
        label={tr("موعد الانطلاق")}
      />

      <div className="t2-ict-row">
        <span className="t2-ict-row-label">
          <Icon name="group" />
          {tr("المقاعد")}
        </span>
        <Stepper
          label={tr("المقاعد")}
          value={seats}
          min={1}
          max={MAX_SEATS}
          onChange={(next) => {
            setSeats(next);
            // **أقلُّ ما ينطلق به لا يزيد على المقاعد** — شرطُ الخلفية نفسُه، فلا يُترك رقمٌ سيُرفض
            setMinSeats((current) => Math.min(current, next));
          }}
        />
      </div>
      <div className="t2-ict-row">
        <span className="t2-ict-row-label">
          <Icon name="flag" />
          {tr("أقلُّ عددٍ أنطلق به")}
        </span>
        <Stepper label={tr("أقلُّ عددٍ أنطلق به")} value={minSeats} min={1} max={seats} onChange={setMinSeats} />
      </div>
      <p className="t2-fld-hint">
        {tr("إن لم يبلغه المحجوزُ قبل المهلة أُلغيت الرحلةُ وحدَها، وعاد إلى كلِّ راكبٍ مالُه كاملاً — بلا أثرٍ عليك.")}
      </p>

      {note ? (
        <p className={note.tone === "ok" ? "t2-note t2-gu-done" : "t2-note danger"} role={note.tone === "ok" ? "status" : "alert"}>
          <Icon name={note.tone === "ok" ? "check_circle" : "error"} />
          {note.text}
        </p>
      ) : null}

      <button
        type="button"
        className="t2-button action t2-gu-go t2-ict-post"
        disabled={!ready || locked}
        aria-busy={busy}
        onClick={() => {
          if (routeId === null || at === "") return;
          void onPost({ route_id: routeId, departs_at: new Date(at).toISOString(), seats, min_seats: minSeats }).then((ok) => {
            if (ok) setAt("");
          });
        }}
      >
        {busy ? tr("نرسل…") : tr("أعلن الرحلة")}
      </button>
    </div>
  );
}

/** **بطاقةُ الرحلة** — الموعدُ والحال · المسارُ بنقطتي التجمّع · المقاعدُ والسعران كما وصلا · **الركّابُ حين يصلون** (أسماءٌ قبل
 *  الانطلاق بساعة، وأرقامٌ تُطلب بلمسةٍ عند الانطلاق) · الأفعال. **والإلغاءُ بتأكيدٍ تحت البطاقة**: فعلٌ يردّ المالَ إلى كلِّ راكبٍ لا
 *  يقع بلمسةٍ واحدة. */
function TripCard({
  trip,
  busy,
  locked,
  note,
  onAct,
}: {
  trip: IntercityTrip;
  busy: boolean;
  locked: boolean;
  note?: { tone: "ok" | "danger"; text: string };
  onAct: (kind: "cancel" | "depart" | "complete") => void;
}) {
  const [asking, setAsking] = useState(false);
  const status = STATUS[trip.status];
  const slot = when(trip.departs_at);
  const cur = currencyLabel(trip.currency);
  const live = trip.status === "open" || trip.status === "departed";

  let actions: ReactNode = null;
  if (trip.status === "open") {
    actions = asking ? (
      <div className="t2-callout t2-ict-ask" role="alert">
        <Icon name="error" />
        <div className="t2-callout-main">
          <p className="t2-callout-title">{tr("ألغِ الرحلة؟")}</p>
          <p className="t2-callout-body">{tr("قبل المهلة بلا أثرٍ عليك، ويُردّ لكلِّ راكبٍ مالُه كاملاً.")}</p>
          <div className="t2-gu-actions t2-ict-ask-actions">
            <button
              type="button"
              className="t2-button secondary t2-ict-destroy"
              disabled={locked}
              aria-busy={busy}
              onClick={() => {
                setAsking(false);
                onAct("cancel");
              }}
            >
              {tr("نعم، ألغِها")}
            </button>
            <button type="button" className="t2-button secondary" onClick={() => setAsking(false)}>
              {tr("تراجع")}
            </button>
          </div>
        </div>
      </div>
    ) : (
      <>
        <div className="t2-gu-actions">
          <button type="button" className="t2-button action" disabled={locked} aria-busy={busy} onClick={() => onAct("depart")}>
            {busy ? tr("نرسل…") : tr("انطلقتُ")}
          </button>
          <button type="button" className="t2-button secondary" disabled={locked} onClick={() => setAsking(true)}>
            {tr("ألغِ الرحلة")}
          </button>
        </div>
        <p className="t2-gu-hint center">{tr("«ألغِ الرحلة» قبل المهلة بلا أثر، ويُردّ للركّاب كاملاً.")}</p>
      </>
    );
  } else if (trip.status === "departed") {
    actions = (
      <button
        type="button"
        className="t2-button action t2-gu-go"
        disabled={locked}
        aria-busy={busy}
        onClick={() => onAct("complete")}
      >
        {busy ? tr("نرسل…") : tr("وصلتُ — أنهِ الرحلة")}
      </button>
    );
  }

  return (
    <article className={trip.status === "departed" ? "t2-gu-card asking" : "t2-gu-card"}>
      <div className="t2-gu-top">
        <span className="t2-gu-when">
          <Icon name="route" />
          {slot.day}{" "}
          <span dir="ltr" className="t2-gu-time">
            {slot.time}
          </span>
        </span>
        <span className={status.chip}>{status.text}</span>
      </div>
      <div className="t2-gu-route">
        <span className="t2-gu-dot" aria-hidden="true" />
        <span className="t2-gu-place">
          {trip.route.from_city} — {trip.route.from_point}
        </span>
        <span className="t2-gu-dot to" aria-hidden="true" />
        <span className="t2-gu-place strong">
          {trip.route.to_city} — {trip.route.to_point}
        </span>
      </div>
      <div className="t2-gu-money">
        <span>
          {tr("محجوزٌ")}{" "}<b dir="ltr">{digits(String(trip.seats_booked))}</b>{" "}{tr("من")}{" "}{countSeats(trip.seats_offered)}{" "}{tr("· وأقلُّ ما تنطلق به")}{" "}
          <b dir="ltr">{digits(String(trip.min_seats))}</b>
        </span>
        <span className="t2-gu-fee">
          <b dir="ltr">{digits(trip.price_seat)}</b> {cur}{" "}{tr("للمقعد ·")}{" "}<b dir="ltr">{digits(trip.price_car)}</b> {cur}{" "}{tr("للسيارة")}
        </span>
      </div>

      {/* **الركّابُ كما ينشرهم الباب**: الاسمُ قبل الانطلاق بساعة، والرقمُ عند الانطلاق وحدَه — فلا يُطلب ما لم يصل */}
      {trip.passengers.length > 0 ? (
        <ul className="t2-ict-people" aria-label={tr("الركّاب")}>
          {trip.passengers.map((person, index) => (
            <li key={`${person.name}-${index}`} className="t2-ict-person">
              <Icon name="person" />
              <span className="t2-ict-person-name">{person.name}</span>
              <span className="t2-ict-person-seats">{countSeats(person.seats)}</span>
              {person.phone ? (
                <a className="t2-ict-call" href={`tel:${person.phone}`} aria-label={tr("اتصل بـ{0}", { 0: person.name })}>
                  <Icon name="call" />
                  <span dir="ltr">{person.phone}</span>
                </a>
              ) : null}
            </li>
          ))}
        </ul>
      ) : live && trip.seats_booked > 0 ? (
        <p className="t2-gu-hint">{tr("تظهر أسماءُ ركّابك قبل الانطلاق بساعة، وأرقامُهم حين تنطلق.")}</p>
      ) : null}

      {actions}
      {note ? (
        <p className={note.tone === "ok" ? "t2-note t2-gu-done" : "t2-note danger"} role={note.tone === "ok" ? "status" : "alert"}>
          <Icon name={note.tone === "ok" ? "check_circle" : "error"} />
          {note.text}
        </p>
      ) : null}
    </article>
  );
}
