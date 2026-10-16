/** **محرّكُ العرض — خادمٌ في الهاتف لوضع الضيف** (أمرُ المالك ٢٠٢٦-١٠-١٥، SPEC §٧٦-ن/٢).
 *
 * **كلُّ نداءٍ في وضع الضيف يُجاب من هنا** (`api/client.ts` يحوّله قبل الشبكة) — فالشاشاتُ هي الشاشاتُ نفسُها وتعمل كما تعمل، **ولا شيءَ
 * يبلغ الخادم**: لا رحلةَ تُكتب، ولا كبتنَ حقيقيّاً يُعرض عليه طلب، ولا مالَ يُمسّ، ولا دفعَ يُطلق، ولا اتّصالَ ولا محادثةَ مع إنسان.
 *
 * - **المدينةُ للعرض عمّان** (`DEMO_CENTER`) — والخريطةُ تُرسم حيث كان الضيفُ في العالم.
 * - **الكبتنُ محاكى**: يقبل بعد ثوانٍ، ويقترب على الخريطة، ويصل، وينطلق، وينهي — بأحداث المقبس نفسِها (`demoSubscribe`).
 * - **والمالُ للعرض بأرقامٍ ثابتة لا محسوبة**: السعرُ من جدولٍ للعرض، والرصيدُ موسومٌ «للعرض» ولا يتغيّر — §14 يحصر حسابَ المال في
 *   الخلفية، **وفي العرض لا خلفيةَ ولا مال**، فلا شيءَ يُحسب هنا أصلاً.
 * - **وما لا يُحاكى يُردّ برسالةٍ واضحة** (`demo_unavailable`) لا بشاشةٍ فارغة.
 */

import { leaveDemo } from "@/demo/mode";
import { tr } from "@/lib/i18n";
import { zeroAmount } from "@/lib/utils";
import type {
  AppConfig,
  Booking,
  Commute,
  Coordinates,
  CountryCode,
  Currency,
  IntercityBooking,
  IntercityTrip,
  MapPlaceSpot,
  MyReferrals,
  NearbyDriver,
  PayMethods,
  Payment,
  PaymentMethod,
  Rating,
  Ride,
  RideDriver,
  RideEstimate,
  RideListItem,
  RidePayments,
  SavedPlace,
  Storefront,
  Tip,
  TipOptions,
  User,
  UserNotification,
  Wallet,
  WalletTransaction,
  WeeklyCashback,
} from "@/api/types";

/** **العبدلي، عمّان** — مدينةُ العرض */
export const DEMO_CENTER: Coordinates = { lat: 31.9632, lng: 35.9106 };
const COUNTRY: CountryCode = "JO";
const CURRENCY: Currency = "JOD";
/** **الصفرُ بعملته** (`check:market-literals`) */
const ZERO = zeroAmount(CURRENCY);
const ME = "demo-guest";
const CAPTAIN = "demo-captain";

/** **ما يُشعَل في العرض** — كلُّ خدمةٍ لها شاشةٌ مبنيّة، **ولا ما يحتاج إنساناً** (المكالمات) **ولا ما لم يُبنَ** (التوصيل). */
const DEMO_FEATURES: Record<string, boolean> = {
  wallet_enabled: true,
  wallet_transfer_enabled: true,
  women_service_enabled: true,
  multi_stop_enabled: true,
  tips_enabled: true,
  rider_referrals_enabled: true,
  scheduled_rides_enabled: true,
  ride_sharing_enabled: true,
  eta_enabled: true,
  ride_for_other_enabled: true,
  airport_enabled: true,
  parcel_enabled: true,
  parcel_fetch_enabled: true,
  hourly_enabled: true,
  rider_subscription_enabled: true,
  intercity_enabled: true,
  weekly_cashback_enabled: true,
  trip_chat_enabled: true,
  map_places_enabled: true,
  payment_requests_enabled: true,
  promo_codes_enabled: false,
  ride_code_enabled: false,
  ride_calls_enabled: false,
  delivery_enabled: false,
  unconfirmed_payments_enabled: false,
  cliq_enabled: false,
  card_enabled: false,
};

/** **أسعارُ العرض — نصوصٌ ثابتةٌ لا حساب** (بترتيب فئات السوق) */
const DEMO_FARES = ["1.750", "2.250", "3.250", "4.500", "6.000"];
const DEMO_BALANCE = "25.000";

const now = () => new Date().toISOString();
const ago = (minutes: number) => new Date(Date.now() - minutes * 60_000).toISOString();
let counter = 0;
const id = (prefix: string) => `${prefix}-${Date.now().toString(36)}-${(counter += 1)}`;

// ── الحالُ — في الذاكرة وحدَها، وتُمحى بإعادة التحميل أو الخروج ─────────────────────────────

const user: User = {
  id: ME,
  phone: null,
  name: tr("ضيف"),
  role: "rider",
  roles: ["rider"],
  country_code: COUNTRY,
  is_blocked: false,
  is_test: false,
  phone_verified: true,
  phone_pending: false,
  suspension: null,
  email: null,
  gender: null,
  gender_verified_at: null,
  ride_gender_preference: "any",
  created_at: now(),
};

let categories: string[] = ["economy", "comfort", "family", "vip"];
let active: Ride | null = null;
const history: Ride[] = [];
const payments = new Map<string, Payment[]>();
const ratings = new Map<string, Rating[]>();
const tips = new Map<string, Tip>();
const places: SavedPlace[] = [];
const bookings: Booking[] = [];
const commutes: Commute[] = [];
const seats: IntercityBooking[] = [];
const chats = new Map<string, Array<{ id: string; mine: boolean; body: string; created_at: string }>>();
let notificationsRead = false;
let marketing = false;

// ── المقبس — أحداثُه نفسُها، من هنا ────────────────────────────────────────────────────────

export type DemoEvent = { type: string; [key: string]: unknown };
type Listener = (event: DemoEvent) => void;
const listeners = new Set<Listener>();
let viewport: Coordinates = DEMO_CENTER;
let drift: number | null = null;

function emit(event: DemoEvent) {
  for (const listener of listeners) listener(event);
}

/** **مقبسُ العرض** — يُنادى من `lib/socket.ts` بدل `WebSocket`: «متّصل» فوراً، وسياراتٌ قريبة تتحرّك. */
export function demoSubscribe(listener: Listener): () => void {
  listeners.add(listener);
  window.setTimeout(() => listener({ type: "connected", active_ride: active }), 50);
  if (drift === null) {
    drift = window.setInterval(() => emit({ type: "nearby_drivers", drivers: nearby(viewport) }), 4000);
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && drift !== null) {
      window.clearInterval(drift);
      drift = null;
    }
  };
}

export function demoViewport(center: Coordinates) {
  viewport = center;
  emit({ type: "nearby_drivers", drivers: nearby(center) });
}

/** **سياراتٌ للعرض حول المركز** — مواضعُ تتبدّل قليلاً في كلِّ إطار */
function nearby(center: Coordinates): NearbyDriver[] {
  const t = Date.now() / 20_000;
  return [0, 1, 2, 3, 4].map((k) => ({
    ref: `demo-car-${k}`,
    lat: center.lat + Math.sin(t + k * 1.3) * 0.006,
    lng: center.lng + Math.cos(t + k * 1.7) * 0.007,
    heading: (k * 72 + Math.round(t * 40)) % 360,
    vehicle_category: categories[k % categories.length] ?? "economy",
    skin: null,
  }));
}

// ── الرحلة المحاكاة ─────────────────────────────────────────────────────────────────────────

function distanceKm(a: Coordinates, b: Coordinates): number {
  const rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad;
  const dLng = (b.lng - a.lng) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(h));
}

function fareFor(category: string): string {
  const index = Math.max(0, categories.indexOf(category));
  return DEMO_FARES[Math.min(index, DEMO_FARES.length - 1)] ?? DEMO_FARES[0];
}

const DRIVER = (category: string): RideDriver => ({
  id: CAPTAIN,
  name: tr("سامر — كبتن تجريبي"),
  rating_avg: "4.90",
  vehicle: { make: "Toyota", model: "Corolla", color: tr("أبيض"), plate_number: "00-00000", category },
  skin: null,
});

interface RideDraft {
  pickup: Coordinates;
  dropoff: Coordinates;
  vehicle_category: string;
  pickup_address?: string | null;
  dropoff_address?: string | null;
  ride_type?: Ride["ride_type"];
  payment_method?: PaymentMethod | null;
}

function makeRide(draft: RideDraft): Ride {
  const fare = fareFor(draft.vehicle_category);
  const km = distanceKm(draft.pickup, draft.dropoff);
  return {
    id: id("demo-ride"),
    rider_id: ME,
    status: "searching",
    country_code: COUNTRY,
    vehicle_category: draft.vehicle_category,
    currency: CURRENCY,
    pickup: draft.pickup,
    pickup_address: draft.pickup_address ?? tr("موقعي"),
    dropoff: draft.dropoff,
    dropoff_address: draft.dropoff_address ?? tr("الوجهة"),
    distance_km: km.toFixed(2),
    actual_distance_km: null,
    duration_min: Math.max(4, Math.round(km * 2.2)).toString(),
    estimated_fare: fare,
    final_fare: null,
    cancellation_fee: null,
    carried_cancellation_fee: null,
    commission_percent_at_ride: "0",
    cancelled_reason: null,
    gender_preference: "any",
    driver: null,
    share_discount_percent: "0",
    share_group_id: null,
    share_seat: 1,
    start_code_required: false,
    for_other: false,
    payer: "requester",
    passenger_name: null,
    passenger_phone: null,
    ride_type: draft.ride_type ?? "standard",
    recipient_name: null,
    recipient_phone: null,
    recipient_address: null,
    parcel_fetch: false,
    parcel_item: null,
    hourly_hours: null,
    hourly_included_km: null,
    hourly_prepay_method: null,
    commute: false,
    search_widened: false,
    payment_method_hint: draft.payment_method ?? "cash",
    fare_lines: [{ kind: "base", amount: fare }],
    stops: [],
    open_pause: null,
    pause_charge: ZERO,
    pause_price_per_min: ZERO,
    pause_max_minutes: 0,
    current_leg: 0,
    waiting_charge: ZERO,
    stop_free_minutes: 0,
    stop_price_per_min: ZERO,
    stop_max_wait_minutes: 0,
    stop_fee: ZERO,
    stops_charge: ZERO,
    rider_estimate: fare,
    created_at: now(),
    accepted_at: null,
    arrived_at: null,
    started_at: null,
    completed_at: null,
    cancelled_at: null,
  };
}

let timers: number[] = [];
function later(ms: number, run: () => void) {
  timers.push(window.setTimeout(run, ms));
}
function stopTimers() {
  timers.forEach((t) => window.clearTimeout(t));
  timers = [];
}

/** **يتحرّك الكبتنُ المحاكى من أ إلى ب** خطوةً كلَّ ثانية — بأحداث `driver_location` نفسِها */
function drive(from: Coordinates, to: Coordinates, steps: number, startAt: number, then: () => void) {
  for (let k = 1; k <= steps; k += 1) {
    const f = k / steps;
    const bend = Math.sin(f * Math.PI) * 0.0015;
    const point = { lat: from.lat + (to.lat - from.lat) * f + bend, lng: from.lng + (to.lng - from.lng) * f };
    const heading = (Math.atan2(to.lng - from.lng, to.lat - from.lat) * 180) / Math.PI;
    later(startAt + k * 1000, () => emit({ type: "driver_location", driver_id: CAPTAIN, lat: point.lat, lng: point.lng, heading }));
  }
  later(startAt + steps * 1000 + 300, then);
}

function update(patch: Partial<Ride>, event: string) {
  if (!active) return;
  active = { ...active, ...patch };
  emit({ type: event, ride: active });
}

function simulate(ride: Ride) {
  stopTimers();
  const start = { lat: ride.pickup.lat + 0.008, lng: ride.pickup.lng - 0.006 };
  later(4000, () => {
    update({ status: "accepted", driver: DRIVER(ride.vehicle_category), accepted_at: now() }, "driver_assigned");
    drive(start, ride.pickup, 12, 0, () => {
      update({ status: "arrived", arrived_at: now() }, "driver_arrived");
      later(6000, () => {
        update({ status: "in_progress", started_at: now() }, "ride_started");
        drive(ride.pickup, ride.dropoff, 20, 0, () => {
          if (!active) return;
          const fare = active.estimated_fare;
          update(
            { status: "completed", completed_at: now(), final_fare: fare, actual_distance_km: active.distance_km },
            "ride_completed",
          );
          const done = active;
          history.unshift(done);
          payments.set(done.id, []);
          active = null;
        });
      });
    });
  });
}

// ── بيانٌ للعرض ─────────────────────────────────────────────────────────────────────────────

const wallet = (): Wallet => ({
  owner_id: ME,
  owner_type: "rider",
  balance: DEMO_BALANCE,
  currency: CURRENCY,
  frozen: false,
  cancellation_debt: ZERO,
  pending_compensation: ZERO,
});

const transactions = (): WalletTransaction[] => [
  { id: "demo-tx-1", owner_id: ME, owner_type: "rider", type: "topup", amount: "20.000", balance_after: "20.000", currency: CURRENCY, ride_id: null, reference: tr("شحنٌ للعرض"), created_at: ago(60 * 26) },
  { id: "demo-tx-2", owner_id: ME, owner_type: "rider", type: "cashback", amount: "5.000", balance_after: DEMO_BALANCE, currency: CURRENCY, ride_id: null, reference: tr("كاش باك للعرض"), created_at: ago(60 * 3) },
];

const cashback = (): WeeklyCashback => ({
  enabled: true,
  days_required: 5,
  days_done: 2,
  days_left: 3,
  amount: "2.000",
  currency: CURRENCY,
  rode_today: false,
  friday: false,
});

const storefront = (): Storefront => ({
  tiles: (
    [
      ["airport", tr("المطار"), "flight"],
      ["parcel", tr("طرد"), "inventory_2"],
      ["hourly", tr("بالساعة"), "schedule"],
      ["fetch", tr("أغراضي"), "shopping_bag"],
      ["bookings", tr("رحلة بموعد"), "event"],
      ["intercity", tr("بين المدن"), "route"],
    ] as const
  ).map(([key, title, icon], k) => ({
    id: `demo-tile-${k}`,
    key,
    title,
    subtitle: null,
    icon,
    status: "active" as const,
    destination: `/services/${key}`,
    is_new: false,
  })),
  banners: [
    {
      id: "demo-banner",
      title: tr("أنت في وضع التجربة"),
      body: tr("جرّب كلَّ شيء — لا رحلةَ حقيقيّة ولا مال."),
      headline: null,
      icon: "science",
      link_kind: "none",
      link: null,
    },
  ],
  offer: null,
});

const notifications = (): UserNotification[] => [
  {
    id: "demo-n-1",
    kind: "demo",
    title: tr("مرحباً بك في TAXO"),
    body: tr("هذا وضعُ التجربة: الكبتنُ والرحلةُ والرصيدُ للعرض."),
    data: null,
    read_at: notificationsRead ? now() : null,
    created_at: ago(2),
  },
];

const referrals = (): MyReferrals => ({
  code: "DEMO-TAXO",
  programs: [],
  paid_this_month: 0,
  total_rewarded: ZERO,
  referrals: [],
});

const payMethods = (): PayMethods => ({
  currency: CURRENCY,
  methods: [
    {
      id: "demo-card",
      kind: "purchase_code",
      name: tr("بطاقة TAXO — للعرض"),
      account_holder: null,
      account_number: null,
      bank_name: null,
      instructions: tr("في وضع التجربة لا دفعَ حقيقيّ — أيُّ رمزٍ يُقبل للعرض ولا يتغيّر رصيد."),
      has_qr: false,
      requires_receipt: false,
      gateway: false,
      fee_payer: null,
    },
  ],
  topup_choices: ["5.000", "10.000", "20.000"],
});

const trips = (): IntercityTrip[] =>
  [
    ["عمّان", "إربد", 32.5556, 35.85, "3.000", "12.000"],
    ["عمّان", "العقبة", 29.5321, 35.0063, "9.000", "36.000"],
  ].map(([from, to, lat, lng, seat, car], k) => ({
    id: `demo-trip-${k}`,
    route: {
      id: `demo-route-${k}`,
      country_code: COUNTRY,
      from_city: tr(String(from)),
      to_city: tr(String(to)),
      from_lat: DEMO_CENTER.lat,
      from_lng: DEMO_CENTER.lng,
      from_point: tr("العبدلي"),
      to_lat: Number(lat),
      to_lng: Number(lng),
      to_point: tr("وسط المدينة"),
      price_car: String(car),
      price_seat: String(seat),
      is_active: true,
    },
    departs_at: new Date(Date.now() + (k + 1) * 3_600_000 * 5).toISOString(),
    seats_offered: 4,
    seats_booked: 1,
    min_seats: 2,
    price_car: String(car),
    price_seat: String(seat),
    currency: CURRENCY,
    status: "open",
    passengers: [],
  }));

function listItem(ride: Ride): RideListItem {
  const paid = (payments.get(ride.id) ?? []).length > 0;
  return {
    ride,
    has_open_dispute: false,
    payment_methods: paid ? ["cash"] : [],
    paid_amount: paid ? (ride.final_fare ?? ride.estimated_fare) : ZERO,
    settlement: paid ? "settled" : "due",
  };
}

function ridePayments(ride: Ride): RidePayments {
  const list = payments.get(ride.id) ?? [];
  const settled = list.length > 0;
  return {
    ride_id: ride.id,
    currency: CURRENCY,
    final_fare: ride.final_fare,
    outstanding: settled ? ZERO : (ride.final_fare ?? ride.estimated_fare),
    settlement: settled ? "settled" : ride.status === "completed" ? "due" : "not_due",
    cancellation_debt: ZERO,
    payments: list,
    cliq_charge: null,
    card_order: null,
  };
}

function findRide(rideId: string): Ride | null {
  if (active?.id === rideId) return active;
  return history.find((ride) => ride.id === rideId) ?? null;
}

/** **وجهاتُ العرض** — معالمُ معروفةٌ في عمّان، يجدها الضيفُ في البحث بأيِّ كلمة */
const SPOTS = (): MapPlaceSpot[] =>
  (
    [
      ["شارع الرينبو", "Rainbow Street", 31.9513, 35.9246],
      ["مكة مول", "Mecca Mall", 31.9757, 35.8411],
      ["جبل القلعة", "Amman Citadel", 31.9545, 35.9349],
      ["بوليفارد العبدلي", "Abdali Boulevard", 31.9652, 35.9089],
      ["مطار الملكة علياء الدولي", "Queen Alia Airport", 31.7226, 35.9932],
    ] as const
  ).map(([ar, en, lat, lng], k) => ({
    id: `demo-spot-${k}`,
    name_ar: tr(ar),
    name_en: en,
    category: "landmark",
    lat,
    lng,
    source: "place" as const,
    distance_m: null,
  }));

// ── المُوجِّه ───────────────────────────────────────────────────────────────────────────────

export type DemoAnswer =
  | { kind: "data"; data: unknown }
  | { kind: "passthrough" }
  | { kind: "error"; status: number; code: string; message: string };

const ok = (data: unknown): DemoAnswer => ({ kind: "data", data });
const unavailable = (message = tr("هذا غيرُ متاحٍ في وضع التجربة — سجّل حساباً لتجرّبه حقيقيّاً.")): DemoAnswer => ({
  kind: "error",
  status: 409,
  code: "demo_unavailable",
  message,
});

/** **ما يمرّ إلى الخادم في العرض** — قراءاتٌ عامّةٌ بلا حسابٍ ولا أثر (الإعداداتُ والسياساتُ والإصدار) */
const PUBLIC_READS = [/^\/config$/, /^\/auth\/method$/, /^\/public\//];

type Body = Record<string, unknown> | undefined;

export function demoRequest(
  method: string,
  rawPath: string,
  body: unknown,
  query: Record<string, unknown> = {},
): DemoAnswer {
  const path = rawPath.split("?")[0];
  const b = (body ?? {}) as Body & Record<string, unknown>;
  if (method === "GET" && PUBLIC_READS.some((re) => re.test(path))) return { kind: "passthrough" };

  let m: RegExpMatchArray | null;
  const is = (verb: string, re: RegExp) => method === verb && (m = path.match(re)) !== null;

  // الحساب
  if (is("GET", /^\/auth\/me$/)) return ok(user);
  if (is("PATCH", /^\/auth\/me$/)) return ok(Object.assign(user, b));
  // **الخروجُ من الحساب خروجٌ من العرض** — فلا تبقى شاشةُ الدخول تُجاب من هنا
  if (is("POST", /^\/auth\/(logout|sessions\/revoke-all)$/)) {
    leaveDemo();
    demoReset();
    return ok(undefined);
  }
  if (is("GET", /^\/auth\/test-markets$/)) return ok({ markets: [] });
  if (method === "POST" && /^\/auth\//.test(path)) return unavailable();
  if (is("PUT", /^\/me\/devices$/)) return ok({ id: "demo-device", device_id: "demo", platform: "web", is_active: true, last_seen_at: now(), created_at: now() });
  if (is("DELETE", /^\/me\/devices\//)) return ok(undefined);
  if (is("GET", /^\/me\/notification-preferences$/)) return ok({ marketing_push_enabled: marketing });
  if (is("PUT", /^\/me\/notification-preferences$/)) {
    marketing = Boolean(b.marketing_push_enabled);
    return ok({ marketing_push_enabled: marketing });
  }
  if (is("POST", /^\/telemetry\/errors$/)) return ok({ accepted: true });
  if (is("GET", /^\/storefront$/)) return ok(storefront());
  if (is("GET", /^\/account\/deletion$/))
    return ok({ requested_at: null, due_at: null, deferred_reason: null, blockers: [], rider_balance: DEMO_BALANCE, driver_balance: ZERO, forfeit_amount: null, currency: CURRENCY, is_driver: false, transfer_enabled: false });

  // الخريطة والأماكن
  if (is("GET", /^\/drivers\/nearby$/)) return ok(nearby(viewport));
  if (is("GET", /^\/map-places$/)) return ok(SPOTS());
  if (is("GET", /^\/map-places\/search$/)) {
    // **وجهاتٌ للعرض في عمّان** — الضيفُ في أيِّ بلدٍ لا يعرف أسماءَ شوارعها، فيجدها هنا مهما كتب
    const q = String(query.q ?? "").trim().toLowerCase();
    const hits = SPOTS().filter((spot) => spot.name_ar.includes(q) || (spot.name_en ?? "").toLowerCase().includes(q));
    return ok(hits.length ? hits : SPOTS());
  }
  if (is("GET", /^\/airports$/)) return ok([{ id: "demo-amm", name: tr("مطار الملكة علياء الدولي"), lat: 31.7226, lng: 35.9932 }]);
  if (is("GET", /^\/me\/places$/)) return ok(places);
  if (is("POST", /^\/me\/places$/)) {
    const place: SavedPlace = { id: id("demo-place"), label: String(b.label ?? ""), address: (b.address as string) ?? null, lat: Number(b.lat), lng: Number(b.lng), icon: String(b.icon ?? "star"), created_at: now() };
    places.push(place);
    return ok(place);
  }
  if (is("PATCH", /^\/me\/places\/([^/]+)$/)) {
    const place = places.find((p) => p.id === m![1]);
    return place ? ok(Object.assign(place, b)) : unavailable();
  }
  if (is("DELETE", /^\/me\/places\/([^/]+)$/)) {
    const at = places.findIndex((p) => p.id === m![1]);
    if (at >= 0) places.splice(at, 1);
    return ok(undefined);
  }

  // الرحلات
  if (is("GET", /^\/rides\/eta$/)) return ok({ enabled: true, categories: categories.map((key, k) => ({ vehicle_category: key, minutes: 3 + k })) });
  if (is("POST", /^\/rides\/estimate$/)) {
    const pickup = b.pickup as Coordinates;
    const dropoff = (b.dropoff as Coordinates) ?? pickup;
    const category = String(b.vehicle_category ?? categories[0]);
    const km = distanceKm(pickup, dropoff);
    const estimate: RideEstimate = {
      country_code: COUNTRY,
      vehicle_category: category,
      currency: CURRENCY,
      distance_km: km.toFixed(2),
      duration_min: Math.max(4, Math.round(km * 2.2)).toString(),
      estimated_fare: fareFor(category),
      priced_fare: fareFor(category),
      minimum_fare_applied: false,
      share_discount: null,
      share_fare: null,
      stop_fee: ZERO,
      stop_free_minutes: 3,
      stop_price_per_min: "0.050",
      stop_max_wait_minutes: 10,
      airport_fee: null,
      parcel_fee: b.is_parcel ? "0.500" : null,
      rugged_fee: null,
      parcel_terms: b.is_parcel ? [tr("الطردُ في العرض محاكاة — لا شيءَ يُنقل.")] : null,
      hourly_rate: "8.000",
      hourly_km_per_hour: 20,
      hourly_max_hours: 8,
    };
    return ok(estimate);
  }
  if (is("POST", /^\/rides$/)) {
    if (active) return { kind: "error", status: 409, code: "active_ride_exists", message: tr("لديك رحلةٌ تجريبيّةٌ جارية") };
    active = makeRide({
      pickup: b.pickup as Coordinates,
      dropoff: b.dropoff as Coordinates,
      vehicle_category: String(b.vehicle_category ?? categories[0]),
      pickup_address: (b.pickup_address as string) ?? null,
      dropoff_address: (b.dropoff_address as string) ?? null,
      ride_type: b.parcel ? "parcel" : b.hourly ? "hourly" : "standard",
      payment_method: (b.payment_method as PaymentMethod) ?? "cash",
    });
    simulate(active);
    return ok(active);
  }
  if (is("GET", /^\/rides\/me\/active$/)) return ok(active);
  if (is("GET", /^\/rides\/me\/summary$/)) return ok({ completed_rides: history.length, rating_avg: "5.00", ratings_count: 0 });
  if (is("GET", /^\/rides\/me$/)) return ok(history.map(listItem));
  if (is("POST", /^\/rides\/([^/]+)\/cancel$/)) {
    if (!active || active.id !== m![1]) return unavailable();
    stopTimers();
    const cancelled: Ride = { ...active, status: "cancelled_by_rider", cancelled_at: now() };
    history.unshift(cancelled);
    active = null;
    emit({ type: "ride_cancelled", ride: cancelled });
    return ok(cancelled);
  }
  if (is("GET", /^\/rides\/([^/]+)\/payments$/)) {
    const ride = findRide(m![1]);
    return ride ? ok(ridePayments(ride)) : unavailable();
  }
  if (is("POST", /^\/rides\/([^/]+)\/payments$/)) {
    const ride = findRide(m![1]);
    if (!ride) return unavailable();
    const payment: Payment = {
      id: id("demo-pay"),
      ride_id: ride.id,
      method: (b.method as PaymentMethod) ?? "cash",
      provider: null,
      provider_payment_id: null,
      amount: ride.final_fare ?? ride.estimated_fare,
      currency: CURRENCY,
      status: "confirmed",
      confirmed_by: CAPTAIN,
      confirmed_at: now(),
      transaction_id: null,
      cliq_alias: null,
      cliq_reference: null,
      cliq_transfer_reference: null,
      cliq_reference_at: null,
      dispute_reason: null,
      disputed_at: null,
      resolution: null,
      resolution_note: null,
      resolved_at: null,
      created_at: now(),
    };
    payments.set(ride.id, [payment]);
    return ok(ridePayments(ride));
  }
  if (is("GET", /^\/rides\/([^/]+)\/ratings$/)) return ok(ratings.get(m![1]) ?? []);
  if (is("POST", /^\/rides\/([^/]+)\/ratings$/)) {
    const rating: Rating = { id: id("demo-rating"), ride_id: m![1], rater_type: "rider", stars: Number(b.stars ?? 5), comment: (b.comment as string) ?? null, tags: (b.tags as Rating["tags"]) ?? [], created_at: now() };
    ratings.set(m![1], [rating]);
    return ok(rating);
  }
  if (is("GET", /^\/rides\/([^/]+)\/tip$/))
    return ok({ offered: true, currency: CURRENCY, presets: ["0.250", "0.500"], max_amount: "1.000", given: tips.get(m![1]) ?? null } satisfies TipOptions);
  if (is("POST", /^\/rides\/([^/]+)\/tip$/)) {
    const tip: Tip = { id: id("demo-tip"), ride_id: m![1], amount: String(b.amount ?? "0.250"), currency: CURRENCY, created_at: now() };
    tips.set(m![1], tip);
    return ok(tip);
  }
  if (is("GET", /^\/rides\/([^/]+)\/route-line$/)) {
    const ride = findRide(m![1]);
    return ok({ points: ride ? [[ride.pickup.lng, ride.pickup.lat], [ride.dropoff.lng, ride.dropoff.lat]] : [] });
  }
  if (is("GET", /^\/rides\/([^/]+)\/route$/)) {
    const ride = findRide(m![1]);
    return ok({ points: ride ? [[ride.pickup.lng, ride.pickup.lat], [ride.dropoff.lng, ride.dropoff.lat]] : [], truncated: false });
  }
  if (is("GET", /^\/rides\/([^/]+)\/approach$/)) {
    const ride = findRide(m![1]);
    return ok({ points: ride ? [[ride.pickup.lng - 0.006, ride.pickup.lat + 0.008], [ride.pickup.lng, ride.pickup.lat]] : [], duration_min: 3, distance_km: 1.1 });
  }
  if (is("GET", /^\/rides\/([^/]+)\/driver\/stats$/)) return ok({ completed_rides: 1240 });
  if (is("GET", /^\/rides\/([^/]+)\/start-code$/)) return { kind: "error", status: 404, code: "not_found", message: tr("لا رمزَ لهذه الرحلة") };
  if (is("POST", /^\/rides\/([^/]+)\/track-link$/)) return unavailable();
  if (is("GET", /^\/rides\/([^/]+)\/chat$/)) {
    const list = chats.get(m![1]) ?? [];
    return ok({
      ride_id: m![1],
      open: true,
      can_call: false,
      unread: 0,
      notice: tr("محادثةٌ تجريبيّة — الكبتنُ محاكى ولا يقرؤها أحد."),
      max_chars: 300,
      messages: list.map((msg) => ({ id: msg.id, ride_id: m![1], sender_role: msg.mine ? "rider" : "driver", mine: msg.mine, body: msg.body, created_at: msg.created_at, read_at: null })),
      active_call: null,
    });
  }
  if (is("POST", /^\/rides\/([^/]+)\/chat$/)) {
    const rideId = m![1];
    const list = chats.get(rideId) ?? [];
    const mine = { id: id("demo-msg"), mine: true, body: String(b.body ?? ""), created_at: now() };
    list.push(mine);
    chats.set(rideId, list);
    later(2500, () => list.push({ id: id("demo-msg"), mine: false, body: tr("وصلتني رسالتك — هذا ردٌّ تجريبيّ."), created_at: now() }));
    return ok({ id: mine.id, ride_id: rideId, sender_role: "rider", mine: true, body: mine.body, created_at: mine.created_at, read_at: null });
  }
  if (/^\/(rides\/[^/]+\/calls|calls\/)/.test(path)) return unavailable(tr("المكالماتُ غيرُ متاحةٍ في وضع التجربة."));
  if (is("GET", /^\/rides\/([^/]+)$/)) {
    const ride = findRide(m![1]);
    return ride ? ok(ride) : { kind: "error", status: 404, code: "not_found", message: tr("الرحلةُ غيرُ موجودة") };
  }

  // المحفظة والدفع — **للعرض، والرصيدُ لا يتغيّر**
  if (is("GET", /^\/wallet\/me$/)) return ok(wallet());
  if (is("GET", /^\/wallet\/me\/transactions$/)) return ok(transactions());
  if (is("GET", /^\/wallet\/me\/topups$/)) return ok([]);
  if (is("GET", /^\/wallet\/transfer\/recipient$/)) return ok({ phone: "+962790000000", name: tr("صديقٌ للعرض") });
  if (method === "POST" && /^\/wallet\//.test(path)) return unavailable(tr("في وضع التجربة لا يُشحن ولا يُحوَّل مالٌ حقيقيّ — الرصيدُ للعرض."));
  if (is("GET", /^\/payments\/cards$/)) return ok([]);
  if (is("GET", /^\/payments\/me\/unconfirmed$/)) return ok({ blocked: false, items: [] });
  if (is("GET", /^\/payment-requests\/methods$/)) return ok(payMethods());
  if (is("GET", /^\/payment-requests\/me$/)) return ok([]);
  if (is("POST", /^\/taxo-cards\/redeem$/)) return unavailable(tr("في وضع التجربة لا تُشحن بطاقة — الرصيدُ للعرض ولا يتغيّر."));
  if (/^\/payment-requests/.test(path)) return unavailable(tr("في وضع التجربة لا دفعَ حقيقيّ — لا Chargily ولا بطاقة."));

  // الخدمات
  if (is("GET", /^\/me\/cashback$/)) return ok(cashback());
  if (is("GET", /^\/me\/referrals$/)) return ok(referrals());
  if (is("GET", /^\/me\/notifications\/unread-count$/)) return ok({ unread: notificationsRead ? 0 : 1 });
  if (is("GET", /^\/me\/notifications$/)) return ok(notifications());
  if (is("POST", /^\/me\/notifications\/read$/)) {
    notificationsRead = true;
    return ok(undefined);
  }
  if (is("GET", /^\/me\/bookings$/)) return ok(bookings);
  if (is("POST", /^\/me\/bookings$/)) {
    const booking: Booking = {
      id: id("demo-booking"),
      status: "pending",
      scheduled_at: String(b.scheduled_at ?? now()),
      vehicle_category: String(b.vehicle_category ?? categories[0]),
      gender_preference: "any",
      payment_method_hint: "cash",
      pickup_lat: Number((b.pickup as Coordinates)?.lat ?? DEMO_CENTER.lat),
      pickup_lng: Number((b.pickup as Coordinates)?.lng ?? DEMO_CENTER.lng),
      pickup_address: (b.pickup_address as string) ?? null,
      dropoff_lat: Number((b.dropoff as Coordinates)?.lat ?? DEMO_CENTER.lat),
      dropoff_lng: Number((b.dropoff as Coordinates)?.lng ?? DEMO_CENTER.lng),
      dropoff_address: (b.dropoff_address as string) ?? null,
      estimated_fare_at_booking: fareFor(String(b.vehicle_category ?? categories[0])),
      currency: CURRENCY,
      ride_id: null,
      ride_status: null,
      awaiting_choice: false,
      cancelled_at: null,
      created_at: now(),
      guaranteed: false,
      guarantee_fee: null,
      guarantee_state: null,
      captain_name: null,
    };
    bookings.unshift(booking);
    return ok(booking);
  }
  if (is("DELETE", /^\/me\/bookings\/([^/]+)$/)) {
    const booking = bookings.find((x) => x.id === m![1]);
    if (booking) Object.assign(booking, { status: "cancelled", cancelled_at: now() });
    return ok(booking ?? null);
  }
  if (is("POST", /^\/me\/commutes\/quote$/))
    return ok({ discount_percent: "20", price_per_ride: "1.800", rides_total: 40, total: "72.000", ends_on: new Date(Date.now() + 30 * 86_400_000).toISOString().slice(0, 10), currency: CURRENCY });
  if (is("GET", /^\/me\/commutes$/)) return ok(commutes);
  if (method === "POST" && /^\/me\/commutes/.test(path)) return unavailable(tr("الاشتراكُ في وضع التجربة للعرض — لا يُشترى ولا يُخصم شيء."));
  if (is("GET", /^\/intercity\/trips$/)) return ok(trips());
  if (is("GET", /^\/intercity\/bookings$/)) return ok(seats);
  if (method === "POST" && /^\/intercity\//.test(path)) return unavailable(tr("الحجزُ بين المدن في وضع التجربة للعرض — لا مقعدَ يُحجز ولا مال."));

  return unavailable();
}

/** **إعداداتُ السوق للعرض** — الخدماتُ المبنيّةُ مشتعلةٌ لسوق العرض، **ويُحفظ ترتيبُ فئاته لأسعار العرض**. */
export function demoPatchConfig(config: AppConfig): AppConfig {
  const country = config.countries.find((c) => c.country_code === COUNTRY);
  if (country) {
    categories = country.vehicle_categories.length ? [...country.vehicle_categories] : categories;
    country.features = { ...country.features, ...DEMO_FEATURES };
  }
  return config;
}

/** **يُمحى العرضُ كلُّه** عند الخروج */
export function demoReset() {
  stopTimers();
  active = null;
  history.length = 0;
  payments.clear();
  ratings.clear();
  places.length = 0;
  bookings.length = 0;
  chats.clear();
}
