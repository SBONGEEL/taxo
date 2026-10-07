/** الرحلات المجدولة — مفتاحُها وأزمنتُها (12-ط).
 *
 * **والحدُّ الأدنى مكرَّرٌ هنا بقصد**: الخلفيةُ ترفض ما هو أقرب من نصف ساعة
 * (`MIN_LEAD_MINUTES`)، والشاشةُ تمنع اختيارَه أصلاً — فحقلٌ يقبل ما تعرف
 * الشاشةُ أنه سيُرفض يعلّم صاحبَه أن يجرّب ثم يُخطئ. والرفضُ في الخلفية هو
 * الحارس، وهذا راحةٌ لا حراسة.
 *
 * **والمشوارُ الثابتُ هنا أيضاً** (§٦٣-ج/٦): اشتراكٌ تُولَّد رحلاتُه حجوزاً مجدولةً (`ride_bookings.commute_id`) —
 * فهو حجزٌ يتكرّر، وبيتُه بيتُ الحجوز. **و«بين المدن» بعده** (§٦٣-ج/٧، آخرَ الملف): مقاعدُ تُحجز في رحلةٍ أعلنها كبتنٌ لموعدٍ
 * قادم — حجزٌ كذلك، وبيتُه هنا.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  bookIntercity,
  buyCommute,
  cancelCommute,
  cancelIntercityBooking,
  listIntercityBookings,
  listIntercityTrips,
  listMyCommutes,
  quoteCommute,
  releaseCommuteCaptain,
  suspendCommuteDay,
} from "@/api/endpoints";
import type {
  Commute,
  CommutePlan,
  CommuteQuote,
  IntercityBooking,
  IntercityRoute,
  IntercityTrip,
} from "@/api/types";
import { useSession } from "@/lib/session";
import { useFeature } from "@/lib/config";
import { DISPLAY_LOCALE, digits } from "@/lib/utils";

export const MIN_LEAD_MINUTES = 30;
export const MAX_HORIZON_DAYS = 30;

export function useScheduledRides(): boolean {
  const { user } = useSession();
  return useFeature(user?.country_code, "scheduled_rides_enabled");
}

/** **الحجزُ المضمون** (§٦٣-ج/٣) — مفتاحُه يُخفي الخيارَ كلَّه لا يعطّله. **ولا رسمَ يُقرأ هنا**: لا بابَ عامٌّ ينشره قبل
 *  الحجز، **وصفرُه في السوق يُرفض من الخلفية** (`guaranteed_booking_unavailable`) فيُقال نصُّها تحت الزرّ. */
export function useGuaranteedBooking(): boolean {
  const { user } = useSession();
  return useFeature(user?.country_code, "guaranteed_booking_enabled");
}

/** **ساعتان قبل الموعد على الأقلّ** — مرآةُ `guarantees.MIN_LEAD` في الخلفية: ليتّسع لقبول كبتنٍ وتأكيدِه قبل الموعد
 *  بساعة. **ومكرَّرةٌ هنا بقصد** كحدِّ نصف الساعة أعلاه: الشاشةُ تعطّل ما تعرف أنه سيُرفض، **والرفضُ في الخلفية هو الحارس**. */
export const GUARANTEE_MIN_LEAD_MINUTES = 120;

/** أيتّسع الموعدُ المختارُ لحجزٍ مضمون؟ — `when` بصيغة `datetime-local` (وقتٌ محلّيٌّ بلا منطقة). */
export function guaranteeLeadOk(when: string): boolean {
  const at = new Date(when).getTime();
  return Number.isFinite(at) && at - Date.now() >= GUARANTEE_MIN_LEAD_MINUTES * 60_000;
}

/** قيمةٌ لحقل `datetime-local` — **بالوقت المحلي لا UTC**: الحقلُ يعرض ما
 *  يُعطى كما هو، و`toISOString` يعطي UTC فيرى صاحبُه ساعةً غيرَ ساعته. */
export function localInputValue(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

export function earliest(): Date {
  return new Date(Date.now() + MIN_LEAD_MINUTES * 60_000);
}

export function latest(): Date {
  return new Date(Date.now() + MAX_HORIZON_DAYS * 86_400_000);
}

// ═══════════════════════════════════════════════════════════ المشوارُ الثابت (§٦٣-ج/٦)
//
// **مطفأً لا يُشترى جديد، والقائمُ يُرى** (قاعدةُ `lib/parcel.ts`): المفتاحُ يحكم بابَ الشراء وحدَه، **و«اشتراكاتي» تُقرأ ولو أُطفئ**
// — مالُ القائم مدفوعٌ ومحفوظ، وشاشةٌ تختفي بإطفاءٍ تُخفي مالَ صاحبها عنه.
//
// **ولا مالَ يُحسب هنا** (§14): سعرُ الرحلة وعددُها والمجموعُ ونسبةُ الخصم وآخرُ يوم — كلُّها من التسعير في الخلفية. **وما يُعدّ هنا
// أيامٌ لا مال**: أيُّ الأيام القادمة من أيام المشوار يجوز تعليقُه — والخلفيةُ تعيد الفحصَ وترفض بنصّها.

export function useCommuteService(): boolean {
  const { user } = useSession();
  return useFeature(user?.country_code, "rider_subscription_enabled");
}

/** **أيامُ الأسبوع بترتيبه هنا — الأحدُ أوّلاً** — وبتُّ كلٍّ في قناع الخلفية (ترتيبُ `weekday()`: الإثنين 1 … الأحد 64). */
export const COMMUTE_DAYS: ReadonlyArray<{ bit: number; name: string }> = [
  { bit: 64, name: "الأحد" },
  { bit: 1, name: "الاثنين" },
  { bit: 2, name: "الثلاثاء" },
  { bit: 4, name: "الأربعاء" },
  { bit: 8, name: "الخميس" },
  { bit: 16, name: "الجمعة" },
  { bit: 32, name: "السبت" },
];

/** **الأحدُ إلى الخميس** — أسبوعُ العمل في السوقين، وأوّلُ ما تبدأ به الخطّة. */
export const WORK_WEEK = 64 | 1 | 2 | 4 | 8;

/** بتُّ اليوم في القناع — `getDay()` يبدأ بالأحد صفراً، والقناعُ بالإثنين. */
function dayBit(date: Date): number {
  return 1 << ((date.getDay() + 6) % 7);
}

/** «الأحد · الثلاثاء · الخميس» بترتيب الأسبوع هنا — **والمتتاليةُ مدىً** «الأحد إلى الخميس» (خمسةُ أسماءٍ تلتفّ سطرين على البطاقة،
 *  قِيس)، و«كلَّ يوم» للسبعة. */
export function commuteDaysText(mask: number): string {
  const picked = COMMUTE_DAYS.filter((day) => (mask & day.bit) !== 0);
  if (picked.length === COMMUTE_DAYS.length) return "كلَّ يوم";
  const first = COMMUTE_DAYS.indexOf(picked[0]);
  const run = picked.length >= 3 && picked.every((day, index) => COMMUTE_DAYS[first + index] === day);
  return run ? `${picked[0].name} إلى ${picked[picked.length - 1].name}` : picked.map((day) => day.name).join(" · ");
}

/** «يومٌ واحد · يومان · 3 أيام · 7 أيام» — **العربيةُ تعدّ بالمثنّى والجمع** (قاعدةُ `hoursLabel`). */
export function daysCount(count: number): string {
  if (count === 1) return "يومٌ واحد";
  if (count === 2) return "يومان";
  return `${count} أيام`;
}

/** «رحلة واحدة · رحلتان · 3 رحلات · 22 رحلة» — **والتمييزُ بآخر خانتين** (قاعدةُ `ridesLabel` في التتبّع). */
export function ridesCount(count: number): string {
  if (count === 1) return "رحلة واحدة";
  if (count === 2) return "رحلتان";
  const tail = count % 100;
  return `${count} ${tail >= 3 && tail <= 10 ? "رحلات" : "رحلة"}`;
}

/** «07:30» من «07:30:00» — **الساعةُ كما كُتبت بساعة السوق**، بخاناتٍ لاتينية (§20). */
export function clockOf(time: string): string {
  return time.slice(0, 5);
}

/** «YYYY-MM-DD» **بالتاريخ المحلّيّ لا UTC** — `toISOString` يُزيح اليومَ قرب منتصف الليل (علّةُ `localInputValue`). */
export function isoDay(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** تاريخٌ «YYYY-MM-DD» **يومٌ محلّيٌّ لا لحظةٌ بتوقيتٍ عالميّ** — `new Date("2026-10-08")` منتصفُ ليلٍ بتوقيت غرينتش. */
function dayOf(iso: string): Date {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, month - 1, day);
}

/** «الخميس 8 أكتوبر» — أو «8 أكتوبر» بلا اسم اليوم (`short`)؛ وأسماءُ الشهور عربيةٌ والخاناتُ لاتينية (`DISPLAY_LOCALE`). */
export function dayText(iso: string, short = false): string {
  return digits(
    dayOf(iso).toLocaleDateString(
      DISPLAY_LOCALE,
      short ? { day: "numeric", month: "long" } : { weekday: "long", day: "numeric", month: "long" },
    ),
  );
}

/** «10» من «10.00» — **النسبةُ نصٌّ من الخلفية تُقصّ أصفارُ كسرها ولا تُحسب**؛ و«7.5» تبقى. */
export function percentText(value: string): string {
  return value.includes(".") ? value.replace(/0+$/, "").replace(/\.$/, "") : value;
}

/** **الأيامُ التي يجوز تعليقُها** — قادمةٌ (من الغد)، ومن أيام المشوار، وفي مدّته، وليست معلَّقةً قبلُ. **راحةٌ لا حراسة**: الخلفيةُ
 *  تعيد الفحصَ بيوم السوق وتعدّ الحدَّ (`commute_max_suspend_days`) وترفض بنصّها. */
export function suspendableDays(commute: Commute, today = new Date()): string[] {
  const tomorrow = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1);
  const start = dayOf(commute.starts_on);
  const cursor = start > tomorrow ? start : tomorrow;
  const end = dayOf(commute.ends_on);
  const out: string[] = [];
  while (cursor <= end && out.length < 31) {
    const iso = isoDay(cursor);
    if ((commute.weekdays & dayBit(cursor)) !== 0 && !commute.suspended_days.includes(iso)) out.push(iso);
    cursor.setDate(cursor.getDate() + 1);
  }
  return out;
}

/** **تسعيرُ الخطّة كلّما تغيّرت** — بمهلةٍ كالبحث، **والقديمُ يغيب ما دام الجديدُ يُحسب**: سعرُ أيامٍ قديمةٍ تحت أيامٍ جديدةٍ يكذب.
 *  و`plan` `null` ما دامت ناقصةً (بلا نقطتين أو بلا يوم) — فلا نداء. **ورفضُه بنصّ الخلفية** (مطفأ · بدءٌ ليس بعد اليوم · …). */
export function useCommuteQuote(plan: CommutePlan | null): {
  quote: CommuteQuote | null;
  loading: boolean;
  error: string | null;
} {
  const key = plan ? JSON.stringify(plan) : null;
  const [answer, setAnswer] = useState<{ key: string; quote: CommuteQuote | null; error: string | null } | null>(null);

  useEffect(() => {
    if (key === null) return;
    let live = true;
    const timer = window.setTimeout(() => {
      quoteCommute(JSON.parse(key) as CommutePlan)
        .then((quote) => {
          if (live) setAnswer({ key, quote, error: null });
        })
        .catch((caught: unknown) => {
          if (live) setAnswer({ key, quote: null, error: caught instanceof ApiError ? caught.message : "تعذّر حساب السعر" });
        });
    }, 400);
    return () => {
      live = false;
      window.clearTimeout(timer);
    };
  }, [key]);

  const current = key !== null && answer?.key === key ? answer : null;
  return { quote: current?.quote ?? null, loading: key !== null && current === null, error: current?.error ?? null };
}

/** **الشراء من المحفظة** — بالخطّة نفسِها التي سُعِّرت، والسعرُ يُعاد حسابُه في الخلفية لا يُرسل. **ورصيدٌ لا يكفي يُقال ومعه بابُ
 *  الشحن** (`topup`) — رفضٌ بلا مخرجٍ ليس رفضاً. */
export function useCommutePurchase(): {
  busy: boolean;
  failure: { message: string; topup: boolean } | null;
  bought: Commute | null;
  buy: (plan: CommutePlan) => void;
} {
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<{ message: string; topup: boolean } | null>(null);
  const [bought, setBought] = useState<Commute | null>(null);

  const buy = useCallback((plan: CommutePlan) => {
    setBusy(true);
    setFailure(null);
    buyCommute(plan)
      .then(setBought)
      .catch((caught: unknown) =>
        setFailure({
          message: caught instanceof ApiError ? caught.message : "تعذّر الاشتراك — حاول ثانية",
          topup: caught instanceof ApiError && caught.code === "insufficient_balance",
        }),
      )
      .finally(() => setBusy(false));
  }, []);

  return { busy, failure, bought, buy };
}

/** **أيملك اشتراكاً ولو انتهى؟** — يُسأل في «حسابي» **ولو أُطفئت الخدمة**: صفُّ «اشتراكاتي» يظهر لمن له مالٌ فيها. وتعثّرُ القراءة
 *  صمتٌ لا خطأ: الصفُّ إضافةٌ على «حسابي»، والشاشةُ نفسُها تقول خطأها إن فُتحت. */
export function useHasCommutes(): boolean {
  const [has, setHas] = useState(false);
  useEffect(() => {
    let live = true;
    listMyCommutes()
      .then((rows) => {
        if (live) setHas(rows.length > 0);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);
  return has;
}

/** **«اشتراكاتي» وأفعالُها** — القائمة، **وكلُّ فعلٍ يعيد الاشتراكَ من الخلفية فيُستبدل في مكانه** (لا قراءةَ ثانية)، **وجوابُه تحت
 *  بطاقته** لا في رأس الصفحة: من علّق يوماً في الثالثة يقرأ ما جرى حيث ضغط. والرفضُ بنصّ الخلفية كما ردّته. */
export function useMyCommutes() {
  const [rows, setRows] = useState<Commute[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, { tone: "ok" | "danger"; text: string }>>({});

  useEffect(() => {
    let live = true;
    listMyCommutes()
      .then((list) => {
        if (live) setRows(list);
      })
      .catch((caught: unknown) => {
        if (live) setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة اشتراكاتك");
      });
    return () => {
      live = false;
    };
  }, []);

  const run = useCallback(async (row: Commute, call: () => Promise<Commute>, done: (next: Commute) => string) => {
    setBusy(row.id);
    setNotes((current) => {
      const next = { ...current };
      delete next[row.id];
      return next;
    });
    try {
      const next = await call();
      setRows((current) => (current ?? []).map((item) => (item.id === next.id ? next : item)));
      setNotes((current) => ({ ...current, [row.id]: { tone: "ok", text: done(next) } }));
    } catch (caught) {
      const text = caught instanceof ApiError ? caught.message : "تعذّر الإرسال — حاول ثانية";
      setNotes((current) => ({ ...current, [row.id]: { tone: "danger", text } }));
    } finally {
      setBusy(null);
    }
  }, []);

  return {
    rows,
    error,
    busy,
    notes,
    /** **اليومُ يُرحَّل إلى ما بعد آخر يوم** — فيُقال الموعدُ الجديدُ كما ردّته الخلفية. */
    suspend: (row: Commute, day: string) =>
      void run(
        row,
        () => suspendCommuteDay(row.id, day),
        (next) => `علّقنا ${dayText(day)} — وامتدّ اشتراكُك إلى ${dayText(next.ends_on)}.`,
      ),
    /** **ما لم يُستعمل يعود رصيداً لا نقداً** — والمبلغُ في كشف المحفظة بقيده (`commute_credit`)، لا يُحسب هنا. */
    cancel: (row: Commute) =>
      void run(row, () => cancelCommute(row.id), () => "أُلغي الاشتراك — وعاد ما لم يُستعمل رصيداً في محفظتك."),
    release: (row: Commute) =>
      void run(row, () => releaseCommuteCaptain(row.id), () => "فككنا الكبتن — ونبحث لك عن كبتنٍ معتمدٍ آخر."),
  };
}

// ═══════════════════════════════════════════════════════════ بين المدن (§٦٣-ج/٧)
//
// **مطفأً لا تُتصفَّح رحلةٌ ولا يُحجز مقعد، والقائمُ يُرى** (قاعدةُ المشوار أعلاه): المفتاحُ يحكم بابَ التصفّح والحجز وحدَه، **و«حجوزاتي
// بين المدن» تُقرأ ولو أُطفئ** — المالكُ يراجع القانونَ قبل الإشعال، وإطفاءٌ بعده لا يُخفي عن راكبٍ مقعداً دفع ثمنَه.
//
// **ولا مالَ يُحسب هنا** (§14): سعرُ المقعد وسعرُ السيارة مجمَّدان على الرحلة، **ومبلغُ الحجز من الخلفية** (`amount`) — لا يُضرب سعرٌ
// في عددٍ ولو بدا بديهياً. **وما يُعدّ هنا مقاعدُ لا مال**: المتاحُ فرقُ عددين أرسلتهما الخلفية، والخلفيةُ تعيد العدَّ تحت قفل الرحلة.

export function useIntercityService(): boolean {
  const { user } = useSession();
  return useFeature(user?.country_code, "intercity_enabled");
}

/** **المقاعدُ المتاحة** — المعروضةُ ناقصاً المحجوزة، **عددان من الخلفية**؛ وصفرٌ لا سالب. راحةٌ لا حراسة: الحجزُ يُعاد عدُّه هناك. */
export function seatsLeft(trip: IntercityTrip): number {
  return Math.max(0, trip.seats_offered - trip.seats_booked);
}

/** «مقعدٌ واحد · مقعدان · 3 مقاعد · 11 مقعداً» — **العربيةُ تعدّ بالمثنّى والجمع** (قاعدةُ `ridesCount`). */
export function seatsCount(count: number): string {
  if (count === 1) return "مقعدٌ واحد";
  if (count === 2) return "مقعدان";
  const tail = count % 100;
  return `${count} ${tail >= 3 && tail <= 10 ? "مقاعد" : "مقعداً"}`;
}

/** «07:30» — **ساعةُ الانطلاق بتوقيت الجهاز و24 ساعة** كما يُكتب الموعدُ في كلِّ الشاشات (§20)، بخاناتٍ لاتينية. */
export function tripClock(iso: string): string {
  return digits(new Date(iso).toLocaleTimeString(DISPLAY_LOCALE, { hour: "2-digit", minute: "2-digit", hour12: false }));
}

/** «الخميس 8 أكتوبر» — يومُ الانطلاق **بالتاريخ المحلّيّ** (علّةُ `isoDay`). */
export function tripDay(iso: string): string {
  return dayText(isoDay(new Date(iso)));
}

/** **رحلاتُ مسارٍ واحدٍ في يومٍ واحد** — كما تُعرض: المسارُ عنواناً واليومُ بجانبه، والرحلاتُ تحته بساعاتها. */
export interface TripGroup {
  key: string;
  route: IntercityRoute;
  day: string;
  trips: IntercityTrip[];
}

/** **التجميعُ بالمسار واليوم بترتيب الخلفية** — الرحلاتُ تصل الأقربَ انطلاقاً أوّلاً، فأوّلُ مجموعةٍ أقربُ رحلة، **ولا ترتيبَ
 *  ثانٍ يُخترع هنا**. واليومُ يومُ الجهاز لا UTC (رحلةُ ٠١:٠٠ بعمّان يومُها يومُها). */
export function groupTrips(trips: IntercityTrip[]): TripGroup[] {
  const groups = new Map<string, TripGroup>();
  for (const trip of trips) {
    const day = isoDay(new Date(trip.departs_at));
    const key = `${trip.route.id}:${day}`;
    const group = groups.get(key);
    if (group) group.trips.push(trip);
    else groups.set(key, { key, route: trip.route, day: dayText(day), trips: [trip] });
  }
  return [...groups.values()];
}

/** **الرحلاتُ المفتوحة** — تُسأل حيث المفتاحُ مشتعلٌ وحدَه (مطفأً جوابُها ٤٠٣ سلفاً)، **وتُعاد بعد كلِّ حجز**: المحجوزُ يتغيّر بحجزك
 *  وبحجز غيرك، ورقمٌ قديمٌ تحت زرِّ «احجز» يَعِد بمقعدٍ ذهب. والرفضُ بنصّ الخلفية. */
export function useIntercityTrips(enabled: boolean): {
  trips: IntercityTrip[] | null;
  error: string | null;
  reload: () => void;
} {
  const [trips, setTrips] = useState<IntercityTrip[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [round, setRound] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    let live = true;
    listIntercityTrips()
      .then((rows) => {
        if (!live) return;
        setTrips(rows);
        setError(null);
      })
      .catch((caught: unknown) => {
        if (live) setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة رحلات بين المدن");
      });
    return () => {
      live = false;
    };
  }, [enabled, round]);

  return { trips, error, reload: useCallback(() => setRound((value) => value + 1), []) };
}

/** **الحجز** — مقاعدُ من المحفظة أو السيارةُ كاملةً نقداً، **والمبلغُ يعود من الخلفية** (`booked.amount`) فيُقال كما حُسب. **ورصيدٌ
 *  لا يكفي يُقال ومعه بابُ الشحن** (`topup`) — رفضٌ بلا مخرجٍ ليس رفضاً (قاعدةُ `useCommutePurchase`). */
export function useIntercityBooking(): {
  busy: boolean;
  failure: { message: string; topup: boolean } | null;
  booked: IntercityBooking | null;
  book: (trip: IntercityTrip, seats: number, wholeCar: boolean) => Promise<boolean>;
  reset: () => void;
} {
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<{ message: string; topup: boolean } | null>(null);
  const [booked, setBooked] = useState<IntercityBooking | null>(null);

  const book = useCallback(async (trip: IntercityTrip, seats: number, wholeCar: boolean) => {
    setBusy(true);
    setFailure(null);
    try {
      setBooked(await bookIntercity({ trip_id: trip.id, seats, whole_car: wholeCar }));
      return true;
    } catch (caught) {
      setFailure({
        message: caught instanceof ApiError ? caught.message : "تعذّر الحجز — حاول ثانية",
        topup: caught instanceof ApiError && caught.code === "insufficient_balance",
      });
      return false;
    } finally {
      setBusy(false);
    }
  }, []);

  const reset = useCallback(() => {
    setFailure(null);
    setBooked(null);
  }, []);

  return { busy, failure, booked, book, reset };
}

/** **أله حجزٌ بين المدن ولو انتهى؟** — يُسأل في «حسابي» **ولو أُطفئت الخدمة** (علّةُ `useHasCommutes`)، وتعثّرُه صمت. */
export function useHasIntercityBookings(): boolean {
  const [has, setHas] = useState(false);
  useEffect(() => {
    let live = true;
    listIntercityBookings()
      .then((rows) => {
        if (live) setHas(rows.length > 0);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, []);
  return has;
}

/** **«حجوزاتي بين المدن»** — القائمة، **والإلغاءُ يعيد الحجزَ من الخلفية فيُستبدل في مكانه** وجوابُه تحت بطاقته (قاعدةُ
 *  `useMyCommutes`). **والمبلغُ العائدُ لا يُحسب هنا**: ما عاد إلى المحفظة هو `amount` الحجز كما هو، وقيدُه في كشفها. */
export function useMyIntercityBookings() {
  const [rows, setRows] = useState<IntercityBooking[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, { tone: "ok" | "danger"; text: string }>>({});

  useEffect(() => {
    let live = true;
    listIntercityBookings()
      .then((list) => {
        if (live) setRows(list);
      })
      .catch((caught: unknown) => {
        if (live) setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة حجوزاتك");
      });
    return () => {
      live = false;
    };
  }, []);

  const cancel = useCallback(async (row: IntercityBooking) => {
    setBusy(row.id);
    setNotes((current) => {
      const next = { ...current };
      delete next[row.id];
      return next;
    });
    try {
      const next = await cancelIntercityBooking(row.id);
      setRows((current) => (current ?? []).map((item) => (item.id === next.id ? next : item)));
      setNotes((current) => ({
        ...current,
        [row.id]: {
          tone: "ok",
          text:
            next.payment === "wallet"
              ? "أُلغي الحجز — وعاد مالُك كاملاً إلى محفظتك."
              : "أُلغي حجزُ السيارة — ولم تدفع شيئاً.",
        },
      }));
    } catch (caught) {
      const text = caught instanceof ApiError ? caught.message : "تعذّر الإلغاء — حاول ثانية";
      setNotes((current) => ({ ...current, [row.id]: { tone: "danger", text } }));
    } finally {
      setBusy(null);
    }
  }, []);

  return { rows, error, busy, notes, cancel: (row: IntercityBooking) => void cancel(row) };
}
