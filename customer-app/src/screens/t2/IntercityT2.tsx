/** **بين المدن** (SPEC §٦٣-ج/٧) — وجهاه في تطبيق الراكب: «بين المدن» (الرحلاتُ المفتوحةُ فالحجز) و«حجوزاتي بين المدن»، **في المظهرين**.
 *
 * **لا لوحةَ له في Claude Design** — فيُركَّب من عُدّة الهوية كما هي، **ولا شكلَ يُخترع**: رأسُ الشاشة الداخلية (`SubHeadT2`)، ورأسُ
 * «اختر الفئة» عنواناً للمسار ويومِه (`t2-pick-head`)، **وبطاقةُ «رحلاتي المجدولة» للرحلة والحجز** (R26، `t2-bk`)، وورقةُ الهوية
 * للحجز (`DrawerT2`) فيها **بطاقتا «من يدفع» في الطرد** (`t2-cats t2-fo-payers`) لمقاعدَ أو سيارةٍ كاملة، وزرُّ «+» في بطاقة المسار
 * لخطوتي العدّاد (`t2-route-add`)، وزرُّ الطلب (`t2-cta`). **والتخطيطُ وحدَه في `intercity.css`** بالرموز.
 *
 * **ولا مالَ يُحسب هنا** (§14): «سعرُ المقعد» و«سعرُ السيارة» كما وصلا على الرحلة، **ومبلغُ الحجز `amount` من الخلفية بعده** — لا
 * يُضرب سعرُ المقعد في عددها ولو على زرّ. وما يُعدّ هنا مقاعد (`lib/bookings`).
 *
 * **ومطفأً لا تُتصفَّح رحلةٌ ولا يُحجز** (`/account/intercity` يعيد إلى «حسابي»)، **و«حجوزاتي بين المدن» تُقرأ ولو أُطفئ** — مالُ
 * القائم مدفوع.
 */

import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import type { IntercityBooking, IntercityTrip } from "@/api/types";
import { useGoBack } from "@/lib/back";
import {
  groupTrips,
  seatsCount,
  seatsLeft,
  tripClock,
  tripDay,
  useHasIntercityBookings,
  useIntercityBooking,
  useIntercityService,
  useIntercityTrips,
  useMyIntercityBookings,
} from "@/lib/bookings";
import { formatMoney } from "@/lib/utils";
import { DrawerT2 } from "@/screens/t2/DrawerT2";
import { BlankT2, LoaderT2, NoteT2, SubHeadT2 } from "@/screens/t2/KitT2";
import { Icon } from "@/taxo2";

import "./t2.css";
import "./account.css";
import "./for-other.css";
import "./intercity.css";

/** «مقعدٌ واحدٌ متاح · مقعدان متاحان · 3 مقاعد متاحة · 11 مقعداً متاحاً» — **والصفرُ «اكتملت المقاعد»** لا «0 مقاعد». */
function leftText(count: number): string {
  if (count <= 0) return "اكتملت المقاعد";
  if (count === 1) return "مقعدٌ واحدٌ متاح";
  if (count === 2) return "مقعدان متاحان";
  return count <= 10 ? `${count} مقاعد متاحة` : `${count} مقعداً متاحاً`;
}

/** «احجز مقعداً · احجز مقعدين · احجز 3 مقاعد» — **المقاعدُ مفعولٌ به بعد الفعل** فتُنصب (لا «احجز مقعدان»). */
function bookLabel(count: number): string {
  if (count === 1) return "احجز مقعداً";
  if (count === 2) return "احجز مقعدين";
  return count <= 10 ? `احجز ${count} مقاعد` : `احجز ${count} مقعداً`;
}

// ══════════════════════════════════════════════════════════════════ «بين المدن» — الرحلاتُ المفتوحةُ والحجز

export function IntercityT2Screen() {
  const enabled = useIntercityService();
  const navigate = useNavigate();
  const goBack = useGoBack("/account");
  const { trips, error, reload } = useIntercityTrips(enabled);
  const hasBookings = useHasIntercityBookings();
  const [picked, setPicked] = useState<IntercityTrip | null>(null);

  if (!enabled) return <Navigate to="/account" replace />;

  const groups = trips ? groupTrips(trips) : [];

  return (
    <div className="t2 t2-page t2-ic pb-nav">
      <SubHeadT2 title="بين المدن" onBack={goBack} />
      <p className="t2-ic-lede">
        رحلاتٌ بين المدن يعلنها كباتنُ بتصريحٍ بعد فحص مركباتهم. <b>احجز مقعداً من محفظتك</b>، أو السيارةَ كاملةً نقداً للكبتن —
        وتلتقيه في نقطة التجمّع.
      </p>

      {/* **«حجوزاتي» تحت المدخل نفسِه** — لمن له حجزٌ، فيجد ما حجزه حيث حجزه */}
      {hasBookings ? (
        <button
          type="button"
          className="t2-button secondary t2-wide t2-ic-mine"
          onClick={() => navigate("/account/intercity/bookings")}
        >
          <Icon name="event_upcoming" />
          حجوزاتي بين المدن
        </button>
      ) : null}

      {error ? (
        <NoteT2 tone="danger" lead>
          {error}
        </NoteT2>
      ) : null}
      {trips === null && !error ? <LoaderT2 /> : null}
      {trips?.length === 0 ? (
        <BlankT2 icon="route" title="لا رحلاتَ معلَنةً الآن" hint="يعلن الكباتنُ رحلاتِهم قبل موعدها — عُد لاحقاً." />
      ) : null}

      {groups.map((group) => (
        <section key={group.key} className="t2-ic-group">
          <div className="t2-pick-head">
            <span className="t2-pick-title">
              من {group.route.from_city} إلى {group.route.to_city}
            </span>
            <span className="t2-ic-aside">{group.day}</span>
          </div>
          {group.trips.map((trip) => (
            <TripCard key={trip.id} trip={trip} onBook={() => setPicked(trip)} />
          ))}
        </section>
      ))}

      <BookSheet
        trip={picked}
        onClose={() => setPicked(null)}
        onBooked={reload}
        onMine={() => navigate("/account/intercity/bookings")}
      />
    </div>
  );
}

/** **بطاقةُ الرحلة** (بطاقةُ R26): الساعةُ والمتاح · المسارُ بنقطتي التجمّع · السعران كما وصلا · «احجز». **والممتلئةُ تبقى في
 *  مكانها بزرٍّ معطَّلٍ يقول لمَ** — اختفاؤها يجعل من رآها قبل دقيقةٍ يظنّها أُلغيت. */
function TripCard({ trip, onBook }: { trip: IntercityTrip; onBook: () => void }) {
  const left = seatsLeft(trip);
  return (
    <article className="t2-bk t2-ic-card">
      <div className="t2-bk-top">
        <span className="t2-bk-when">
          <Icon name="schedule" />
          <span dir="ltr">{tripClock(trip.departs_at)}</span>
        </span>
        <span className={left > 0 ? "t2-chip ok" : "t2-chip"}>{leftText(left)}</span>
      </div>
      <div className="t2-route">
        <span className="t2-dot" />
        <span className="t2-place">
          {trip.route.from_city} — {trip.route.from_point}
        </span>
        <span className="t2-dot to" />
        <span className="t2-place strong">
          {trip.route.to_city} — {trip.route.to_point}
        </span>
      </div>
      <p className="t2-ic-prices">
        <b className="t2-num">{formatMoney(trip.price_seat, trip.currency)}</b> للمقعد ·{" "}
        <b className="t2-num">{formatMoney(trip.price_car, trip.currency)}</b> للسيارة
      </p>
      <button type="button" className="t2-button primary t2-wide t2-ic-book" disabled={left === 0} onClick={onBook}>
        {left === 0 ? "اكتملت المقاعد" : "احجز"}
      </button>
    </article>
  );
}

/** **ورقةُ الحجز** — مقاعدُ (١ إلى المتاح) تُدفع من المحفظة، **أو السيارةُ كاملةً نقداً للكبتن حين لا مقعدَ محجوزٌ بعد** (شرطُ
 *  الخلفية نفسُه، فلا يُعرض خيارٌ سيُرفض). **والزرُّ يقول ما يُحجز لا ما يُدفع**: المبلغُ يُقال بعد الحجز كما حسبته الخلفية. */
function BookSheet({
  trip,
  onClose,
  onBooked,
  onMine,
}: {
  trip: IntercityTrip | null;
  onClose: () => void;
  onBooked: () => void;
  onMine: () => void;
}) {
  const navigate = useNavigate();
  const { busy, failure, booked, book, reset } = useIntercityBooking();
  const [seats, setSeats] = useState(1);
  const [wholeCar, setWholeCar] = useState(false);

  const close = () => {
    reset();
    setSeats(1);
    setWholeCar(false);
    onClose();
  };

  const left = trip ? seatsLeft(trip) : 0;
  // **السيارةُ كاملةً لرحلةٍ لم يُحجز فيها مقعد** — والخلفيةُ ترفض غيرَها ٤٠٩ برسالتها على أيِّ حال
  const carOpen = trip !== null && trip.seats_booked === 0;
  const car = wholeCar && carOpen;

  return (
    <DrawerT2
      open={trip !== null}
      onOpenChange={(open) => {
        if (!open) close();
      }}
      title={trip ? `من ${trip.route.from_city} إلى ${trip.route.to_city}` : undefined}
    >
      {trip && booked ? (
        <BookedNote booked={booked} onMine={onMine} onDone={close} />
      ) : trip ? (
        <>
          <p className="t2-drawer-text">
            {tripDay(trip.departs_at)} · الساعة <span dir="ltr">{tripClock(trip.departs_at)}</span> — تلتقي الكبتنَ في{" "}
            <b>{trip.route.from_point}</b>.
          </p>

          <div className="t2-cats t2-fo-payers t2-ic-choice" role="radiogroup" aria-label="ما تحجز">
            <button
              type="button"
              role="radio"
              aria-checked={!car}
              className={!car ? "t2-cat on" : "t2-cat"}
              onClick={() => setWholeCar(false)}
            >
              <span className="t2-cat-icon">
                <Icon name="group" />
              </span>
              <span className="t2-cat-main">
                <span className="t2-cat-name">مقاعد — يُدفع من محفظتك</span>
                <span className="t2-cat-hint">
                  {formatMoney(trip.price_seat, trip.currency)} للمقعد، ويعود كاملاً إن ألغيتَ قبل الانطلاق
                </span>
              </span>
            </button>
            {carOpen ? (
              <button
                type="button"
                role="radio"
                aria-checked={car}
                className={car ? "t2-cat on" : "t2-cat"}
                onClick={() => setWholeCar(true)}
              >
                <span className="t2-cat-icon">
                  <Icon name="directions_car" />
                </span>
                <span className="t2-cat-main">
                  <span className="t2-cat-name">السيارةُ كاملة — نقداً للكبتن</span>
                  <span className="t2-cat-hint">
                    {formatMoney(trip.price_car, trip.currency)} تسلّمه للكبتن بيدك عند الانطلاق
                  </span>
                </span>
              </button>
            ) : null}
          </div>

          {/* **العدّادُ بين حدّين**: مقعدٌ على الأقل، ولا فوق المتاح — والخلفيةُ تعيد العدَّ تحت قفل الرحلة وترفض بنصّها */}
          {!car ? (
            <div className="t2-share t2-ic-seats">
              <span className="t2-ic-seats-label">
                <Icon name="group" />
                المقاعد
              </span>
              <div className="t2-ic-stepper">
                <button
                  type="button"
                  className="t2-route-add t2-ic-step"
                  aria-label="مقعدٌ أقل"
                  disabled={seats <= 1}
                  onClick={() => setSeats((value) => Math.max(1, value - 1))}
                >
                  <Icon name="remove" />
                </button>
                <span className="t2-ic-count" dir="ltr" aria-live="polite">
                  {seats}
                </span>
                <button
                  type="button"
                  className="t2-route-add t2-ic-step"
                  aria-label="مقعدٌ أكثر"
                  disabled={seats >= left}
                  onClick={() => setSeats((value) => Math.min(left, value + 1))}
                >
                  <Icon name="add" />
                </button>
              </div>
            </div>
          ) : null}

          <p className="t2-sheet-fine">
            {car
              ? "لا يُخصم شيءٌ من محفظتك — والسيارةُ لك وحدَك، فلا يُحجز فيها مقعدٌ لغيرك."
              : "يُخصم ثمنُ المقاعد من محفظتك لحظةَ الحجز، ويعود كاملاً إن ألغيتَ قبل الانطلاق أو أُلغيت الرحلة."}
          </p>

          {failure ? (
            <NoteT2 tone="danger">
              {failure.message}
              {failure.topup ? (
                <>
                  {" "}
                  <button type="button" className="t2-tlink accent t2-ic-topup" onClick={() => navigate("/wallet/topup")}>
                    اشحن محفظتك
                  </button>
                </>
              ) : null}
            </NoteT2>
          ) : null}

          <div className="t2-drawer-actions">
            <button
              type="button"
              className="t2-cta"
              disabled={busy || (!car && left === 0)}
              aria-busy={busy}
              onClick={() => {
                void book(trip, seats, car).then((ok) => {
                  if (ok) onBooked();
                });
              }}
            >
              <span>{busy ? "نرسل…" : car ? "احجز السيارة — نقداً" : bookLabel(seats)}</span>
            </button>
          </div>
        </>
      ) : null}
    </DrawerT2>
  );
}

/** **بعد الحجز** — ما جرى **بمبلغ الخلفية** (`amount`) ومن أين يُدفع، وأين يلتقي الكبتن، وإلى «حجوزاتي». */
function BookedNote({ booked, onMine, onDone }: { booked: IntercityBooking; onMine: () => void; onDone: () => void }) {
  const trip = booked.trip;
  const amount = formatMoney(booked.amount, trip.currency);
  return (
    <>
      <div className="t2-ic-done" role="status">
        <span className="t2-ic-done-icon" aria-hidden="true">
          <Icon name="check_circle" fill />
        </span>
        <p className="t2-ic-done-title">{booked.whole_car ? "حُجزت السيارةُ كاملة" : `حُجز لك ${seatsCount(booked.seats)}`}</p>
        <p className="t2-ic-done-body">
          {booked.payment === "wallet" ? (
            <>
              خُصم <b className="t2-num">{amount}</b> من محفظتك.
            </>
          ) : (
            <>
              تدفع <b className="t2-num">{amount}</b> نقداً للكبتن عند الانطلاق.
            </>
          )}{" "}
          تلتقي الكبتنَ في <b>{trip.route.from_point}</b> {tripDay(trip.departs_at)} الساعة{" "}
          <span dir="ltr">{tripClock(trip.departs_at)}</span>.
        </p>
      </div>
      <div className="t2-drawer-actions">
        <button type="button" className="t2-button primary" onClick={onMine}>
          حجوزاتي بين المدن
        </button>
        <button type="button" className="t2-button t2-quiet" onClick={onDone}>
          تمّ
        </button>
      </div>
    </>
  );
}

// ══════════════════════════════════════════════════════════════════ «حجوزاتي بين المدن»

const BOOKING_STATUS: Record<IntercityBooking["status"], { text: string; chip: string }> = {
  booked: { text: "محجوز", chip: "t2-chip ok" },
  completed: { text: "اكتملت", chip: "t2-chip" },
  refunded: { text: "عاد مالُك", chip: "t2-chip" },
  cancelled: { text: "أُلغي", chip: "t2-chip" },
};

/** **حالُ الرحلة حين لا تكفي حالُ الحجز** — حجزٌ قائمٌ في رحلةٍ انطلقت يُقال (فلا يُبحث عن زرِّ الإلغاء)، **وحجزٌ عاد مالُه لأن
 *  الرحلةَ أُلغيت يُقال سببُه** — كبتنٌ ألغى، أو لم يبلغ المحجوزُ حدَّه عند المهلة. */
function tripNote(row: IntercityBooking): string | null {
  if (row.trip.status === "departed" && row.status === "booked") return "انطلقت الرحلة";
  if (row.trip.status === "cancelled") return "أُلغيت الرحلة — ولا شيءَ عليك";
  return null;
}

export function IntercityBookingsT2Screen() {
  const service = useIntercityService();
  const navigate = useNavigate();
  const goBack = useGoBack("/account");
  const { rows, error, busy, notes, cancel } = useMyIntercityBookings();
  const [asking, setAsking] = useState<IntercityBooking | null>(null);

  return (
    <div className="t2 t2-page t2-ic pb-nav">
      <SubHeadT2 title="حجوزاتي بين المدن" onBack={goBack} />

      {error ? (
        <NoteT2 tone="danger" lead>
          {error}
        </NoteT2>
      ) : null}
      {rows === null && !error ? <LoaderT2 /> : null}
      {rows?.length === 0 ? (
        <BlankT2
          icon="route"
          title="لا حجوزاتِ بعد"
          hint={service ? "احجز مقعداً في رحلةٍ بين المدن يعلنها كبتنٌ بتصريح." : undefined}
        />
      ) : null}

      {(rows ?? []).map((row) => (
        <BookingCard
          key={row.id}
          row={row}
          busy={busy === row.id}
          locked={busy !== null}
          note={notes[row.id]}
          onCancel={() => setAsking(row)}
        />
      ))}

      {/* **بابُ الجديد خلف المفتاح وحدَه** — والقائمُ فوقه يُرى ولو أُطفئ */}
      {service ? (
        <button type="button" className="t2-button secondary t2-wide t2-ic-new" onClick={() => navigate("/account/intercity")}>
          <Icon name="route" />
          الرحلاتُ المفتوحة
        </button>
      ) : null}

      <DrawerT2
        open={asking !== null}
        onOpenChange={(open) => {
          if (!open) setAsking(null);
        }}
        title="ألغِ الحجز؟"
      >
        <p className="t2-drawer-text">
          {asking?.payment === "wallet"
            ? "يعود مالُك كاملاً إلى محفظتك، ويعود مقعدُك متاحاً لغيرك."
            : "لم تدفع شيئاً بعد — يُلغى حجزُ السيارة وتعود متاحةً لغيرك."}
        </p>
        <div className="t2-drawer-actions">
          <button
            type="button"
            className="t2-button t2-destroy"
            onClick={() => {
              if (asking) cancel(asking);
              setAsking(null);
            }}
          >
            نعم، ألغِ الحجز
          </button>
          <button type="button" className="t2-button t2-quiet" onClick={() => setAsking(null)}>
            تراجع
          </button>
        </div>
      </DrawerT2>
    </div>
  );
}

/** **بطاقةُ الحجز** (بطاقةُ R26): اليومُ والساعة والحال · المسارُ بنقطتي التجمّع · المقاعدُ أو السيارة **ومبلغُ الخلفية ومن أين
 *  يُدفع** · «ألغِ الحجز» ما دامت الرحلةُ مفتوحة. **والقائمُ بجمرٍ خافت** كالحجز المنتظر، وما مضى أبيض. */
function BookingCard({
  row,
  busy,
  locked,
  note,
  onCancel,
}: {
  row: IntercityBooking;
  busy: boolean;
  locked: boolean;
  note?: { tone: "ok" | "danger"; text: string };
  onCancel: () => void;
}) {
  const status = BOOKING_STATUS[row.status];
  const live = row.status === "booked";
  const why = tripNote(row);
  return (
    <article className={live ? "t2-bk pending t2-ic-card" : "t2-bk t2-ic-card"} aria-busy={busy}>
      <div className="t2-bk-top">
        <span className="t2-bk-when">
          <Icon name="event_upcoming" />
          {tripDay(row.trip.departs_at)} · <span dir="ltr">{tripClock(row.trip.departs_at)}</span>
        </span>
        <span className={status.chip}>{status.text}</span>
      </div>
      <div className="t2-route">
        <span className="t2-dot" />
        <span className="t2-place">
          {row.trip.route.from_city} — {row.trip.route.from_point}
        </span>
        <span className="t2-dot to" />
        <span className="t2-place strong">
          {row.trip.route.to_city} — {row.trip.route.to_point}
        </span>
      </div>
      <div className="t2-ic-facts">
        <span>{row.whole_car ? "السيارةُ كاملة" : seatsCount(row.seats)}</span>
        <span>
          <b className="t2-num">{formatMoney(row.amount, row.trip.currency)}</b> ·{" "}
          {row.payment === "wallet" ? "من محفظتك" : "نقداً للكبتن"}
        </span>
      </div>
      {why ? <p className="t2-ic-trip-note">{why}</p> : null}
      {note ? <NoteT2 tone={note.tone}>{note.text}</NoteT2> : null}
      {/* **الإلغاءُ ما دامت الرحلةُ مفتوحة** — وبعد الانطلاق ترفضه الخلفيةُ ٤٠٩، فلا يُرسم زرٌّ سيرتدّ */}
      {live && row.trip.status === "open" ? (
        <div className="t2-ic-actions">
          <button type="button" className="t2-tlink destroy" disabled={locked} onClick={onCancel}>
            ألغِ الحجز
          </button>
        </div>
      ) : null}
    </article>
  );
}
