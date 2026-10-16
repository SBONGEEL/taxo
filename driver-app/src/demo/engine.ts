/** **محرّكُ العرض لتطبيق الكبتن — خادمٌ في الهاتف لوضع الضيف** (أمرُ المالك ٢٠٢٦-١٠-١٥، SPEC §٧٦-ن/٢).
 *
 * **كلُّ نداءٍ في وضع الضيف يُجاب من هنا** (`api/client.ts` يحوّله قبل الشبكة): الكبتنُ الضيفُ يتّصل، **وتصله طلباتٌ محاكاة** كلَّ بضع
 * ثوانٍ في عمّان، يقبل فيقترب على الخريطة، ويصل وينطلق وينهي، ويؤكّد استلامَ النقد، ويرى أرباحَ عرض — **ولا راكبَ حقيقيّاً، ولا رحلةَ تُكتب،
 * ولا مالَ يُمسّ، ولا موقعَ يُبثّ إلى الخادم** (خدمةُ الاستقبال الأصليّةُ لا تبدأ في العرض — `lib/online-service.ts`).
 *
 * **والمالُ للعرض بأرقامٍ ثابتة لا محسوبة** — §14 يحصر حسابَ المال في الخلفية، وفي العرض لا خلفيةَ ولا مال.
 */

import { leaveDemo } from "@/demo/mode";
import { tr } from "@/lib/i18n";
import { zeroAmount } from "@/lib/utils";
import type {
  AppConfig,
  Coordinates,
  CountryCode,
  Currency,
  DriverProfile,
  DriverWallet,
  Earnings,
  MySubscription,
  Payment,
  Ride,
  RideListItem,
  RidePayments,
  Storefront,
  SubscriptionPlan,
  User,
  UserNotification,
  WalletTransaction,
} from "@/api/types";

/** **العبدلي، عمّان** — مدينةُ العرض */
export const DEMO_CENTER: Coordinates = { lat: 31.9632, lng: 35.9106 };
const COUNTRY: CountryCode = "JO";
const CURRENCY: Currency = "JOD";
/** **الصفرُ بعملته** (`check:market-literals`) */
const ZERO = zeroAmount(CURRENCY);
const ME = "demo-guest-captain";

const DEMO_FEATURES: Record<string, boolean> = {
  wallet_enabled: true,
  tips_enabled: true,
  eta_enabled: true,
  next_instruction_enabled: true,
  driver_map_nearby_enabled: true,
  airport_enabled: true,
  parcel_enabled: true,
  hourly_enabled: true,
  intercity_enabled: false,
  guaranteed_booking_enabled: false,
  scheduled_rides_enabled: false,
  trip_chat_enabled: true,
  ride_calls_enabled: false,
  ride_code_enabled: false,
  driver_advances_enabled: false,
  driver_levels_enabled: false,
  vehicle_skins_enabled: false,
  subscription_offers_enabled: false,
  delivery_enabled: false,
  unconfirmed_payments_enabled: false,
  cliq_enabled: false,
  card_enabled: false,
  payment_requests_enabled: true,
};

/** **أجرُ العرض — نصوصٌ ثابتةٌ لا حساب** */
const DEMO_FARES = ["1.750", "2.250", "3.250", "2.750"];
const DEMO_BALANCE = "18.400";
const PICKUPS: Array<[string, string, number, number, number, number]> = [
  ["بوليفارد العبدلي", "شارع الرينبو", 31.9652, 35.9089, 31.9513, 35.9246],
  ["جبل اللويبدة", "مكة مول", 31.9605, 35.9205, 31.9757, 35.8411],
  ["جبل القلعة", "الدوّار السابع", 31.9545, 35.9349, 31.9563, 35.8467],
  ["الشميساني", "مطار الملكة علياء الدولي", 31.9741, 35.8963, 31.7226, 35.9932],
];

const now = () => new Date().toISOString();
const ago = (minutes: number) => new Date(Date.now() - minutes * 60_000).toISOString();
let counter = 0;
const id = (prefix: string) => `${prefix}-${Date.now().toString(36)}-${(counter += 1)}`;

const user: User = {
  id: ME,
  phone: null,
  name: tr("كبتن ضيف"),
  role: "driver",
  roles: ["driver"],
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

let categories: string[] = ["economy", "comfort"];
let online = false;
let offer: Ride | null = null;
let active: Ride | null = null;
const history: Ride[] = [];
const payments = new Map<string, Payment[]>();
let notificationsRead = false;
let marketing = false;

// ── موقعُ الكبتن — يُعطى للتطبيق بدل GPS في العرض ────────────────────────────────────────

let position: Coordinates = DEMO_CENTER;
type PositionListener = (where: Coordinates) => void;
const positionListeners = new Set<PositionListener>();
export function demoPosition(): Coordinates {
  return position;
}
export function onDemoPosition(listener: PositionListener): () => void {
  positionListeners.add(listener);
  return () => positionListeners.delete(listener);
}
function moveTo(where: Coordinates) {
  position = where;
  for (const listener of positionListeners) listener(where);
}

// ── المقبس ──────────────────────────────────────────────────────────────────────────────────

export type DemoEvent = { type: string; [key: string]: unknown };
type Listener = (event: DemoEvent) => void;
const listeners = new Set<Listener>();
let offerTimer: number | null = null;
let timers: number[] = [];
const later = (ms: number, run: () => void) => timers.push(window.setTimeout(run, ms));

function emit(event: DemoEvent) {
  for (const listener of listeners) listener(event);
}

/** **مقبسُ العرض** — «متّصل» فوراً، **وطلبٌ محاكى كلَّ بضع ثوانٍ** ما دام الكبتنُ مستقبِلاً بلا رحلة */
export function demoSubscribe(listener: Listener): () => void {
  listeners.add(listener);
  online = true;
  window.setTimeout(() => listener({ type: "connected", active_ride: active }), 50);
  scheduleOffer(5000);
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) {
      online = false;
      if (offerTimer !== null) window.clearTimeout(offerTimer);
      offerTimer = null;
    }
  };
}

function scheduleOffer(ms: number) {
  if (offerTimer !== null) window.clearTimeout(offerTimer);
  offerTimer = window.setTimeout(() => {
    offerTimer = null;
    if (!online || active || offer) return;
    offer = makeRide(history.length + counter);
    const offered = offer;
    emit({ type: "ride_offer", ride: offered, distance_to_pickup_km: 0.8, expires_in_seconds: 25 });
    later(25_000, () => {
      if (offer?.id === offered.id) {
        offer = null;
        emit({ type: "offer_expired", ride_id: offered.id });
        scheduleOffer(6000);
      }
    });
  }, ms);
}

function distanceKm(a: Coordinates, b: Coordinates): number {
  const rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad;
  const dLng = (b.lng - a.lng) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(h));
}

function makeRide(seed: number): Ride {
  const [from, to, plat, plng, dlat, dlng] = PICKUPS[seed % PICKUPS.length];
  const fare = DEMO_FARES[seed % DEMO_FARES.length];
  const pickup = { lat: plat, lng: plng };
  const dropoff = { lat: dlat, lng: dlng };
  const km = distanceKm(pickup, dropoff);
  return {
    id: id("demo-ride"),
    rider_id: "demo-rider",
    status: "searching",
    country_code: COUNTRY,
    vehicle_category: categories[0] ?? "economy",
    currency: CURRENCY,
    pickup,
    pickup_address: tr(from),
    dropoff,
    dropoff_address: tr(to),
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
    scheduled_for: null,
    share_discount_percent: "0",
    share_group_id: null,
    share_seat: 1,
    stops: [],
    open_pause: null,
    pause_charge: ZERO,
    pause_price_per_min: ZERO,
    pause_max_minutes: 0,
    current_fare: fare,
    fare_lines: [{ kind: "base", amount: fare }],
    start_code_required: false,
    for_other: false,
    payer: "requester",
    passenger_name: tr("راكبٌ تجريبيّ"),
    passenger_phone: null,
    airport: false,
    ride_type: "standard",
    recipient_name: null,
    recipient_phone: null,
    recipient_address: null,
    parcel_fetch: false,
    parcel_item: null,
    hourly_hours: null,
    hourly_included_km: null,
    hourly_prepay_method: null,
    commute: false,
    payment_method_hint: "cash",
    current_leg: 0,
    waiting_charge: ZERO,
    stop_free_minutes: 0,
    stop_price_per_min: ZERO,
    stop_max_wait_minutes: 0,
    stop_fee: ZERO,
    stops_charge: ZERO,
    created_at: now(),
    accepted_at: null,
    arrived_at: null,
    started_at: null,
    completed_at: null,
    cancelled_at: null,
  };
}

/** **يقود الكبتنُ المحاكى** من موضعه إلى الهدف خطوةً كلَّ ثانية — والتطبيقُ يرى موضعَه يتحرّك كما يرى GPS */
function drive(to: Coordinates, steps: number) {
  const from = position;
  for (let k = 1; k <= steps; k += 1) {
    const f = k / steps;
    later(k * 1000, () => moveTo({ lat: from.lat + (to.lat - from.lat) * f, lng: from.lng + (to.lng - from.lng) * f }));
  }
}

function change(patch: Partial<Ride>): Ride | null {
  if (!active) return null;
  active = { ...active, ...patch };
  return active;
}

// ── بيانٌ للعرض ─────────────────────────────────────────────────────────────────────────────

const profile = (): DriverProfile => ({
  driver: {
    id: "demo-driver",
    user_id: ME,
    status: "approved",
    cliq_alias: null,
    gender_preference: "any",
    auto_renew: false,
    accepts_airport: true,
    rating_avg: "4.90",
    is_online: online,
    current_ride_id: active?.id ?? null,
    inspection_at: null,
    inspection_place: null,
    inspection_passed_at: null,
    created_at: ago(60 * 24 * 30),
  },
  user,
  vehicles: [
    {
      id: "demo-vehicle",
      driver_id: "demo-driver",
      make: "Toyota",
      model: "Corolla",
      year: 2022,
      color: tr("أبيض"),
      plate_number: "00-00000",
      category: categories[0] ?? "economy",
      body_type: null,
      fuel: null,
      seats: 4,
      created_at: ago(60 * 24 * 30),
    },
  ],
  documents: [],
  commission_percent: "0",
});

const wallet = (): DriverWallet => ({
  owner_id: ME,
  owner_type: "driver",
  balance: DEMO_BALANCE,
  currency: CURRENCY,
  frozen: false,
  cancellation_debt: ZERO,
  pending_compensation: ZERO,
  available_for_withdrawal: ZERO,
  carrier_dues: ZERO,
  min_withdrawal_amount: "10.000",
  withdrawal_reserve_amount: ZERO,
  commission_this_month: ZERO,
  withdrawal_methods: [],
});

const transactions = (): WalletTransaction[] => [
  { id: "demo-tx-1", owner_id: ME, owner_type: "driver", type: "ride_earning", amount: "3.250", balance_after: DEMO_BALANCE, currency: CURRENCY, ride_id: null, reference: tr("أجرةٌ للعرض"), created_at: ago(90) },
];

const earnings = (period: Earnings["period"]): Earnings => ({
  period,
  from_at: ago(60 * 24 * (period === "today" ? 1 : period === "week" ? 7 : 30)),
  to_at: now(),
  currency: CURRENCY,
  wallet_earnings: "6.500",
  commission: ZERO,
  tips: "0.500",
  advance_repaid: ZERO,
  net: period === "today" ? "12.750" : period === "week" ? "84.250" : "312.500",
  directly_collected: "6.250",
  completed_rides: period === "today" ? 6 : period === "week" ? 41 : 152,
  days: [0, 1, 2, 3, 4, 5, 6].map((k) => ({
    day: new Date(Date.now() - (6 - k) * 86_400_000).toISOString().slice(0, 10),
    net: ["9.500", "14.250", "11.000", "16.750", "8.250", "12.000", "12.750"][k],
    peak_share: [0.2, 0.4, 0.3, 0.5, 0.1, 0.35, 0.45][k],
  })),
  change_percent: 8,
  online_minutes: 245,
});

const plans = (): SubscriptionPlan[] =>
  (
    [
      ["TAXO X1 — يومي", "daily", "1.500"],
      ["TAXO X7 — أسبوعي", "weekly", "8.000"],
      ["TAXO X30 — شهري", "monthly", "25.000"],
    ] as const
  ).map(([name, duration, price], k) => ({
    id: `demo-plan-${k}`,
    country_code: COUNTRY,
    name: tr(name),
    duration_type: duration,
    price,
    currency: CURRENCY,
    is_active: true,
    offer_name: null,
    offer_discount: null,
    price_after_discount: null,
    offer_ends_at: null,
    price_to_pay: price,
    exhausted_offer_name: null,
  }));

const subscription = (): MySubscription => ({
  is_active: true,
  coverage_until: new Date(Date.now() + 6 * 86_400_000).toISOString(),
  days_remaining: 6,
  current: {
    id: "demo-sub",
    plan_name: tr("TAXO X7 — أسبوعي"),
    duration_type: "weekly",
    starts_at: ago(60 * 24),
    expires_at: new Date(Date.now() + 6 * 86_400_000).toISOString(),
    amount_paid: "8.000",
    list_price: "8.000",
    discount_amount: ZERO,
    currency: CURRENCY,
    payment_method: "wallet",
    status: "active",
  },
  plans: plans(),
});

const storefront = (): Storefront => ({
  tiles: [],
  banners: [
    {
      id: "demo-banner",
      title: tr("أنت في وضع التجربة"),
      body: tr("اضغط «ابدأ الاستقبال» وستصلك طلباتٌ محاكاة — لا راكبَ حقيقيّ ولا مال."),
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
    title: tr("مرحباً بك يا كبتن"),
    body: tr("هذا وضعُ التجربة: الطلباتُ والأرباحُ للعرض."),
    data: null,
    read_at: notificationsRead ? now() : null,
    created_at: ago(2),
  },
];

function findRide(rideId: string): Ride | null {
  if (active?.id === rideId) return active;
  if (offer?.id === rideId) return offer;
  return history.find((ride) => ride.id === rideId) ?? null;
}

function ridePayments(ride: Ride): RidePayments {
  const list = payments.get(ride.id) ?? [];
  const settled = list.some((p) => p.status === "confirmed");
  return {
    ride_id: ride.id,
    currency: CURRENCY,
    final_fare: ride.final_fare,
    outstanding: settled ? ZERO : (ride.final_fare ?? ride.estimated_fare),
    settlement: settled ? "settled" : ride.status === "completed" ? "awaiting" : "not_due",
    payments: list,
  };
}

function listItem(ride: Ride): RideListItem {
  const settled = (payments.get(ride.id) ?? []).some((p) => p.status === "confirmed");
  return {
    ride,
    has_open_dispute: false,
    payment_methods: ["cash"],
    paid_amount: settled ? (ride.final_fare ?? ride.estimated_fare) : ZERO,
    settlement: settled ? "settled" : "awaiting",
  };
}

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
const PUBLIC_READS = [/^\/config$/, /^\/auth\/method$/, /^\/public\//];

export function demoRequest(
  method: string,
  rawPath: string,
  body: unknown,
  query: Record<string, unknown> = {},
): DemoAnswer {
  const path = rawPath.split("?")[0];
  const b = (body ?? {}) as Record<string, unknown>;
  if (method === "GET" && PUBLIC_READS.some((re) => re.test(path))) return { kind: "passthrough" };

  let m: RegExpMatchArray | null;
  const is = (verb: string, re: RegExp) => method === verb && (m = path.match(re)) !== null;

  if (is("GET", /^\/auth\/me$/)) return ok(user);
  if (is("PATCH", /^\/auth\/me$/)) return ok(Object.assign(user, b));
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
  if (is("GET", /^\/me\/notifications\/unread-count$/)) return ok({ unread: notificationsRead ? 0 : 1 });
  if (is("GET", /^\/me\/notifications$/)) return ok(notifications());
  if (is("POST", /^\/me\/notifications\/read$/)) {
    notificationsRead = true;
    return ok(undefined);
  }
  if (is("GET", /^\/me\/referrals$/)) return ok({ code: "DEMO-CAPTAIN", programs: [], paid_this_month: 0, total_rewarded: ZERO, referrals: [] });
  if (is("GET", /^\/account\/deletion$/))
    return ok({ requested_at: null, due_at: null, deferred_reason: null, blockers: [], rider_balance: ZERO, driver_balance: DEMO_BALANCE, forfeit_amount: null, currency: CURRENCY, is_driver: true, transfer_enabled: false });
  if (is("GET", /^\/map-places$/)) return ok([]);

  // الكبتن
  if (is("GET", /^\/drivers\/me$/)) return ok(profile());
  if (is("PATCH", /^\/drivers\/me$/)) return ok(profile());
  if (is("GET", /^\/drivers\/me\/documents$/)) return ok({ documents: [], missing_required: [], awaiting_upload: [], required: [] });
  if (is("GET", /^\/drivers\/me\/demand$/)) return ok({ high: true });
  if (is("GET", /^\/drivers\/me\/earnings$/)) return ok(earnings((query.period as Earnings["period"]) ?? "today"));
  if (is("GET", /^\/drivers\/me\/nearby$/)) return ok([]);
  if (is("GET", /^\/drivers\/me\/progress$/))
    return ok({ enabled: false, level: 1, max_level: 1, level_computed_at: null, level_effect_meters: 0, missions_done: 0, missions_total: 0, missions: [], badges: [] });
  if (is("GET", /^\/drivers\/me\/advances$/))
    return ok({ offered: false, eligible: false, requirements: [], cap: ZERO, currency: CURRENCY, debt: null, deduction_percent: 0, min_kept_amount: ZERO, term_days: 0 });
  if (is("GET", /^\/drivers\/me\/debt$/))
    return ok({ total: ZERO, pay_all_amount: ZERO, currency: CURRENCY, blocked: false, ceiling: null, cliq_alias: null, review_min_minutes: 0, review_max_minutes: 0, rows: [] });
  if (is("GET", /^\/drivers\/me\/payments\/unconfirmed$/)) return ok({ blocked: false, block_count: 0, block_hours: 0, items: [] });
  if (is("GET", /^\/drivers\/me\/(guarantee-offers|guarantees|commute-offers|commutes|intercity\/routes|intercity\/trips)$/)) return ok([]);
  // **حضورٌ لا يُبثّ** — الخادمُ لا يعرف أن ضيفاً «متّصل»
  if (is("POST", /^\/drivers\/me\/(online|offline|location|locations)$/)) return ok({ ok: true });
  if (is("POST", /^\/drivers\/me\/presence-token$/)) return unavailable();
  if (method !== "GET" && /^\/drivers\/me\//.test(path)) return unavailable();

  // الرحلات
  if (is("GET", /^\/rides\/me\/active$/)) return ok(active);
  if (is("GET", /^\/rides\/me$/)) return ok(history.map(listItem));
  if (is("POST", /^\/rides\/([^/]+)\/accept$/)) {
    if (!offer || offer.id !== m![1]) return { kind: "error", status: 409, code: "offer_gone", message: tr("انتهى هذا الطلب") };
    active = { ...offer, status: "accepted", accepted_at: now() };
    offer = null;
    drive(active.pickup, 10);
    return ok(active);
  }
  if (is("POST", /^\/rides\/([^/]+)\/decline$/)) {
    offer = null;
    scheduleOffer(6000);
    return ok(undefined);
  }
  if (is("POST", /^\/rides\/([^/]+)\/arrive$/)) {
    moveTo(active?.pickup ?? position);
    return ok(change({ status: "arrived", arrived_at: now() }));
  }
  if (is("POST", /^\/rides\/([^/]+)\/start$/)) {
    const ride = change({ status: "in_progress", started_at: now() });
    if (ride) drive(ride.dropoff, 20);
    return ok(ride);
  }
  if (is("POST", /^\/rides\/([^/]+)\/complete$/)) {
    if (!active) return unavailable();
    timers.forEach((t) => window.clearTimeout(t));
    timers = [];
    moveTo(active.dropoff);
    const done = change({ status: "completed", completed_at: now(), final_fare: active.estimated_fare, actual_distance_km: active.distance_km })!;
    // **دفعةٌ نقديّةٌ للعرض تنتظر تأكيدَ الكبتن** — كما يراها بعد رحلةٍ حقيقيّة
    payments.set(done.id, [
      {
        id: id("demo-pay"),
        ride_id: done.id,
        method: "cash",
        amount: done.final_fare ?? done.estimated_fare,
        currency: CURRENCY,
        status: "pending",
        confirmed_at: null,
        cliq_alias: null,
        cliq_reference: null,
        cliq_transfer_reference: null,
        cliq_confirmation_expires_at: null,
        dispute_reason: null,
        disputed_at: null,
        resolution: null,
        resolution_note: null,
        resolved_at: null,
        created_at: now(),
      },
    ]);
    history.unshift(done);
    active = null;
    scheduleOffer(15_000);
    return ok(done);
  }
  if (is("POST", /^\/rides\/([^/]+)\/cancel$/)) {
    const ride = change({ status: "cancelled_by_driver", cancelled_at: now() });
    if (ride) history.unshift(ride);
    active = null;
    scheduleOffer(8000);
    return ok(ride);
  }
  if (is("GET", /^\/rides\/([^/]+)\/payments$/)) {
    const ride = findRide(m![1]);
    return ride ? ok(ridePayments(ride)) : unavailable();
  }
  if (is("POST", /^\/payments\/([^/]+)\/confirm$/)) {
    for (const [rideId, list] of payments) {
      const payment = list.find((p) => p.id === m![1]);
      if (payment) {
        Object.assign(payment, { status: "confirmed", confirmed_at: now() });
        const ride = findRide(rideId);
        return ok(ride ? ridePayments(ride) : payment);
      }
    }
    return unavailable();
  }
  if (is("POST", /^\/rides\/([^/]+)\/ratings$/)) return ok({ id: id("demo-rating"), ride_id: m![1], rater_type: "driver", stars: Number(b.stars ?? 5), comment: (b.comment as string) ?? null });
  if (is("GET", /^\/rides\/([^/]+)\/ratings$/)) return ok([]);
  if (is("GET", /^\/rides\/([^/]+)\/(offer-route|approach)$/)) {
    const ride = findRide(m![1]);
    const target = ride ? (m![2] === "approach" && ride.status !== "in_progress" ? ride.pickup : ride.dropoff) : position;
    return ok({ points: [[position.lng, position.lat], [target.lng, target.lat]], duration_min: 3, distance_km: 1.1 });
  }
  if (is("GET", /^\/rides\/([^/]+)\/route$/)) {
    const ride = findRide(m![1]);
    return ok({ points: ride ? [[ride.pickup.lng, ride.pickup.lat], [ride.dropoff.lng, ride.dropoff.lat]] : [], truncated: false });
  }
  if (is("GET", /^\/rides\/([^/]+)\/chat$/))
    return ok({ ride_id: m![1], open: true, can_call: false, unread: 0, notice: tr("محادثةٌ تجريبيّة — الراكبُ محاكى ولا يقرؤها أحد."), max_chars: 300, messages: [], active_call: null });
  if (/^\/(rides\/[^/]+\/calls|calls\/)/.test(path)) return unavailable(tr("المكالماتُ غيرُ متاحةٍ في وضع التجربة."));
  if (method === "POST" && /^\/rides\//.test(path)) return unavailable();
  if (is("GET", /^\/rides\/([^/]+)$/)) {
    const ride = findRide(m![1]);
    return ride ? ok(ride) : { kind: "error", status: 404, code: "not_found", message: tr("الرحلةُ غيرُ موجودة") };
  }

  // المحفظةُ والاشتراك — **للعرض، لا يُشترى ولا يُسحب**
  if (is("GET", /^\/wallet\/me\/driver$/)) return ok(wallet());
  if (is("GET", /^\/wallet\/me\/transactions$/)) return ok(transactions());
  if (is("GET", /^\/wallet\/me\/withdrawals$/)) return ok([]);
  if (method === "POST" && /^\/wallet\//.test(path)) return unavailable(tr("في وضع التجربة لا يُسحب ولا يُحوَّل مالٌ حقيقيّ — الرصيدُ للعرض."));
  if (is("GET", /^\/subscriptions\/me$/)) return ok(subscription());
  if (is("GET", /^\/subscriptions\/me\/history$/)) return ok([subscription().current]);
  if (is("GET", /^\/subscriptions\/plans$/)) return ok(plans());
  if (is("GET", /^\/subscriptions\/cliq$/)) return ok([]);
  if (/^\/subscriptions/.test(path)) return unavailable(tr("الاشتراكُ في وضع التجربة للعرض — لا يُشترى ولا يُخصم شيء."));
  if (is("GET", /^\/payments\/cards$/)) return ok([]);
  if (is("GET", /^\/payment-requests\/(methods|me)$/)) return ok(m![1] === "me" ? [] : { currency: CURRENCY, methods: [], topup_choices: [] });
  if (/^\/(payment-requests|taxo-cards|payments)/.test(path)) return unavailable(tr("في وضع التجربة لا دفعَ حقيقيّ — لا Chargily ولا بطاقة."));
  if (is("GET", /^\/vehicle-skins\/(garage|store)$/)) return unavailable();

  return unavailable();
}

export function demoPatchConfig(config: AppConfig): AppConfig {
  const country = config.countries.find((c) => c.country_code === COUNTRY);
  if (country) {
    categories = country.vehicle_categories.length ? [...country.vehicle_categories] : categories;
    country.features = { ...country.features, ...DEMO_FEATURES };
  }
  return config;
}

export function demoReset() {
  timers.forEach((t) => window.clearTimeout(t));
  timers = [];
  if (offerTimer !== null) window.clearTimeout(offerTimer);
  offerTimer = null;
  online = false;
  offer = null;
  active = null;
  history.length = 0;
  payments.clear();
  position = DEMO_CENTER;
}
