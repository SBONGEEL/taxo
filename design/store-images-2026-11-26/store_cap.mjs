// لقطاتُ صور المتجر من البناءين المنشورين (driver.tajora.ly · app.tajora.ly — الرفع 19) بحسابَي الاختبار وحدَهما (أمرُ المالك ٢٦/١١).
// **لا كتابةَ تبلغ الإنتاج**: كلُّ POST/PATCH/PUT/DELETE يُجاب في المتصفّح، والمقبسُ محاكى؛ وGET يمرّ برمز حساب الاختبار
// إلا حالَ الرحلة (العرض، الملاحة، النهاية، CliQ) فمحاكاةٌ بأجرة الأردن الحقيقيّة (تقديرُ الراكب الاختباريّ: 3.200 / 6.200 لـ6.97 كم)
// ومقترحاتُ البقشيش الحقيقيّة (0.500 · 1.000). node store_cap.mjs <k|r> <out> [ar|fr] [dark|light]
import { createRequire } from 'module';
import fs from 'fs';
const require = createRequire('C:/Users/loly3/.claude/skills/video-studio/package.json');
const { chromium } = require('playwright');

const [MODE, OUT, LANG = 'ar', THEME = 'dark'] = process.argv.slice(2);
const K = MODE === 'k', fr = LANG === 'fr';
const S = 'C:/Users/loly3/AppData/Local/Temp/claude/2cccde71cb918853/1be46dcf-43b9-4d7a-8ee2-56b32aaa8a2d/scratchpad';
fs.mkdirSync(OUT, { recursive: true });
const TOKEN = fs.readFileSync(`${S}/${K ? '.cap_token' : '.rider_token'}`, 'utf8').trim();
const BASE = JSON.parse(fs.readFileSync(`${S}/store/base-ride.json`, 'utf8'));
const NOW = new Date().toISOString();
const RID = '00000000-0000-4000-8000-0000000000d1', DID = '00000000-0000-4000-8000-0000000000d2';
// نقطتان عامّتان في عمّان (الدوّار السابع ⇐ العبدلي) — لا عنوانُ أحد
const A = { lat: 31.9566, lng: 35.8556 }, B = { lat: 31.9622, lng: 35.9106 }, D0 = { lat: 31.9541, lng: 35.8519 };
const P_ADDR = fr ? '7e Cercle' : 'الدوّار السابع', D_ADDR = fr ? 'Abdali' : 'العبدلي';
const DRIVER_NAME = fr ? 'Karim' : 'كريم', RIDER_NAME = fr ? 'Sami' : 'سامي';
const VEH = { make: 'Toyota', model: 'Corolla', color: fr ? 'Blanc' : 'أبيض', plate_number: 'TST-0652', category: 'economy' };
const st = { ride: null, pay: K ? 'cash' : 'cliq', online: false, driverMe: null };
const LINE = [[35.8556, 31.9566], [35.8668, 31.9581], [35.8790, 31.9572], [35.8905, 31.9601], [35.9012, 31.9614], [35.9106, 31.9622]];
const APPROACH = [[D0.lng, D0.lat], [35.8531, 31.9549], [35.8545, 31.9558], [A.lng, A.lat]];
const T = (ar, f) => (fr ? f : ar);
const STEPS = [
  { text: T('تابع على الطريق', 'Continuez tout droit'), distance_m: 140, shape: [APPROACH[0], APPROACH[1]], maneuver: 'depart', modifier: null },
  { text: T('انعطف يميناً', 'Tournez à droite'), distance_m: 170, shape: [APPROACH[1], APPROACH[2]], maneuver: 'turn', modifier: 'right' },
  { text: T('انعطف يساراً نحو نقطة الالتقاء', 'Tournez à gauche vers le point de prise en charge'), distance_m: 120, shape: [APPROACH[2], APPROACH[3]], maneuver: 'turn', modifier: 'left' },
  { text: T('وصلت', 'Vous êtes arrivé'), distance_m: 0, shape: [APPROACH[3], APPROACH[3]], maneuver: 'arrive', modifier: null },
];
const TRIP_STEPS = [
  { text: T('تابع على الطريق', 'Continuez tout droit'), distance_m: 900, shape: [LINE[0], LINE[1]], maneuver: 'depart', modifier: null },
  { text: T('انعطف يميناً', 'Tournez à droite'), distance_m: 1400, shape: [LINE[1], LINE[2], LINE[3]], maneuver: 'turn', modifier: 'right' },
  { text: T('ابقَ يساراً', 'Restez à gauche'), distance_m: 2200, shape: [LINE[3], LINE[4], LINE[5]], maneuver: 'fork', modifier: 'left' },
  { text: T('وصلت إلى الوجهة', 'Vous êtes arrivé'), distance_m: 0, shape: [LINE[5], LINE[5]], maneuver: 'arrive', modifier: null },
];
const at = (s) => ['arrived', 'in_progress', 'completed'].includes(s);
const ride = (status) => ({
  ...BASE, id: RID, status, country_code: 'JO', vehicle_category: 'economy', currency: 'JOD', pickup: A, dropoff: B,
  pickup_address: P_ADDR, dropoff_address: D_ADDR, distance_km: '6.966', actual_distance_km: status === 'completed' ? '6.966' : null, duration_min: '18.47',
  estimated_fare: '3.200', current_fare: '3.200', rider_estimate: '3.200', waiting_charge: '0.000', stops_charge: '0.000', pause_charge: '0.000', share_discount_percent: '0.00', final_fare: status === 'completed' ? '3.200' : null, negotiated_fare: null, negotiation_offer: null,
  fare_lines: [{ kind: 'base', amount: '0.460', quantity: null }, { kind: 'distance', amount: '1.811', quantity: '6.966' }, { kind: 'time', amount: '0.924', quantity: '18.47' }],
  cancellation_fee: '0.000', carried_cancellation_fee: '0.000', commission_percent_at_ride: '0.00', cancelled_reason: null, cancelled_at: null,
  accepted_at: status === 'searching' ? null : NOW, arrived_at: at(status) ? NOW : null, started_at: ['in_progress', 'completed'].includes(status) ? NOW : null,
  completed_at: status === 'completed' ? NOW : null, passenger_name: RIDER_NAME, passenger_phone: null, for_other: false, payer: 'requester',
  payment_method_hint: st.pay, stops: [], open_pause: null, start_code_required: false, search_widened: false,
  driver: status === 'searching' ? null : { id: DID, name: DRIVER_NAME, rating_avg: '4.92', vehicle: VEH, skin: null, accepts_cliq: true },
});
const PAYMENT = (method, status) => ({ id: '00000000-0000-4000-8000-0000000000p1'.replace('p', 'a'), ride_id: RID, method, amount: '3.200', currency: 'JOD', status, confirmed_at: null,
  cliq_alias: method === 'cliq' ? 'TAXODEMO' : null, cliq_reference: method === 'cliq' ? 'TX4821' : null, cliq_transfer_reference: null, cliq_confirmation_expires_at: null,
  dispute_reason: null, disputed_at: null, resolution: null, resolution_note: null, resolved_at: null, created_at: NOW });
const PAYMENTS = () => ({ ride_id: RID, currency: 'JOD', final_fare: '3.200', outstanding: '3.200', settlement: 'due', cancellation_debt: '0.000',
  payments: [PAYMENT(st.pay, 'pending')], card_order: null,
  cliq_charge: st.pay === 'cliq' ? { payment_id: PAYMENT('cliq').id, alias: 'TAXODEMO', captain_name: DRIVER_NAME, reference: 'TX4821', amount: '3.200', currency: 'JOD', qr_payload: 'TAXODEMO|3.200|TX4821', deep_link: '', transfer_reference: null, transfer_reference_at: null } : null });
const DAYS = ['2026-11-20', '2026-11-21', '2026-11-22', '2026-11-23', '2026-11-24', '2026-11-25', '2026-11-26'];
const WEEK_NET = ['6.400', '9.600', '3.200', '12.800', '6.400', '9.600', '9.600'];
const EARN = (period) => {
  const week = period === 'week';
  const net = week ? '57.600' : '9.600';
  return { period: period || 'today', from_at: NOW, to_at: NOW, currency: 'JOD', wallet_earnings: net, commission: '0.000', tips: week ? '1.000' : '0.000', advance_repaid: '0.000',
    net, directly_collected: '0.000', earned: net, completed_rides: week ? 18 : 3, change_percent: null, online_minutes: week ? 1260 : 215,
    days: (week ? DAYS : DAYS.slice(-1)).map((day, i) => ({ day, net: week ? WEEK_NET[i] : net, peak_share: week ? Number(WEEK_NET[i]) / 12.8 : 1 })) };
};
const ESTIMATE = (cat) => ({ quote_id: 'store-quote-' + cat, locked_until: NOW, wallet_shortfall: null, country_code: 'JO', vehicle_category: cat, currency: 'JOD',
  distance_km: '6.966', duration_min: '18.47', estimated_fare: cat === 'comfort' ? '6.200' : '3.200', priced_fare: cat === 'comfort' ? '6.191' : '3.195',
  minimum_fare_applied: false, share_discount: null, share_fare: null, route: { points: LINE } });

const TX = (i, type, amount, after, ref, minsAgo) => ({ id: '00000000-0000-4000-8000-0000000001' + String(i).padStart(2, '0'), type, amount, balance_after: after, ride_id: type.startsWith('ride') ? RID : null, reference: ref, created_at: new Date(Date.now() - minsAgo * 60000).toISOString(), commission_percent: type === 'ride_earning' ? '0.00' : null, currency: 'JOD' });
const TXNS = () => K
  ? [TX(1, 'ride_earning', '3.200', '29.600', T('رحلة · الدوّار السابع ⇐ العبدلي', 'Course · 7e Cercle ⇒ Abdali'), 12), TX(2, 'ride_earning', '3.200', '26.400', T('رحلة', 'Course'), 74), TX(3, 'ride_earning', '3.200', '23.200', T('رحلة', 'Course'), 131), TX(4, 'tip', '1.000', '20.000', T('بقشيش من راكب', 'Pourboire'), 1440)]
  : [TX(1, 'ride_payment', '-3.200', '12.500', T('رحلة · الدوّار السابع ⇐ العبدلي', 'Course · 7e Cercle ⇒ Abdali'), 30), TX(2, 'topup', '10.000', '15.700', T('شحن ببطاقة TAXO', 'Recharge carte TAXO'), 1500)];
const placeName = (lat, lng) => (Math.hypot(lat - A.lat, lng - A.lng) < 0.012 ? T('الدوّار السابع، عمّان', '7e Cercle, Amman') : Math.hypot(lat - B.lat, lng - B.lng) < 0.012 ? T('العبدلي، عمّان', 'Abdali, Amman') : T('عمّان', 'Amman'));
const HITS = () => [[T('العبدلي', 'Abdali'), T('العبدلي، عمّان', 'Abdali, Amman'), B, 6900], [T('بوليفارد العبدلي', 'Boulevard Abdali'), T('العبدلي، عمّان', 'Abdali, Amman'), { lat: B.lat + 0.002, lng: B.lng + 0.001 }, 7100], [T('حديقة الحسين', 'Parc Al-Hussein'), T('عمّان', 'Amman'), { lat: 31.985, lng: 35.84 }, 4200]]
  .map(([name, address, c, d], i) => ({ id: 'store-hit-' + i, source: 'taxo', name, address, lat: c.lat, lng: c.lng, place_id: null, distance_m: d, category: null }));
const MBX = (url) => { const u = new URL(url); const rev = u.pathname.includes('/reverse'); const lat = Number(u.searchParams.get('latitude')), lng = Number(u.searchParams.get('longitude'));
  const one = (name, full, c, i) => ({ type: 'Feature', id: 'store-' + i, geometry: { type: 'Point', coordinates: [c.lng, c.lat] }, properties: { mapbox_id: 'store-' + i, name, full_address: full, place_formatted: full, coordinates: { latitude: c.lat, longitude: c.lng } } });
  return { type: 'FeatureCollection', features: rev ? [one(placeName(lat, lng).split(/[،,]/)[0], placeName(lat, lng), { lat, lng }, 0)] : HITS().map((h, i) => one(h.name, h.name + T('، ', ', ') + h.address, h, i)) }; };
const log = [], seen = new Set(), passed = [];
const realGet = {};
function mockGet(path, q) {
  if (path.endsWith('/rides/me/active')) return st.ride;
  if (path.endsWith(`/rides/${RID}`)) return st.ride;
  if (path.endsWith(`/rides/${RID}/payments`)) return PAYMENTS();
  if (path.endsWith(`/rides/${RID}/tip`)) return { offered: true, currency: 'JOD', presets: ['0.500', '1.000'], max_amount: '5.000', given: null };
  if (path.endsWith(`/rides/${RID}/offer-route`) || path.endsWith(`/rides/${RID}/approach`)) return { points: APPROACH, steps: STEPS, duration_min: 2, distance_km: 0.43 };
  if (path.endsWith(`/rides/${RID}/route-line`)) return { points: LINE, steps: TRIP_STEPS, deviation_threshold_m: 60 };
  if (path.includes(`/rides/${RID}/`)) return {};
  if (path.endsWith('/pickup/suggestion')) return null;
  // **سجلُّ الرحلات** — رحلةُ عرضٍ واحدة (لا تاريخَ حسابِ الاختبار ولا عناوينه المخزَّنة)
  if (path.endsWith('/rides/me')) return [{ ride: { ...ride('completed'), id: '00000000-0000-4000-8000-0000000000e1', created_at: new Date(Date.now() - 86400000).toISOString() }, has_open_dispute: false, payment_methods: ['wallet'], paid_amount: '3.200', settlement: 'paid' }];
  if (path.endsWith('/places/reverse')) return { address: placeName(Number(q.get('lat')), Number(q.get('lng'))) };
  if (path.endsWith('/places/search')) return { items: HITS(), attribution: null, attribution_text: null };
  if (K && path.endsWith('/drivers/me/earnings')) return EARN(q.get('period'));
  if (K && path.endsWith('/drivers/me/earnings/weekly')) return { from_at: NOW, to_at: NOW, currency: 'JOD', earned: '57.600', previous_earned: '48.000', earned_change_percent: null, completed_rides: 18, previous_rides: 15, online_minutes: 1260, commission: '0.000', directly_collected: '0.000', best_day: '2026-11-23', best_day_net: '12.800', best_hours: [], rating_average: 4.92, rating_count: 14 };
  if (K && path.endsWith('/wallet/me/driver')) return { ...(st.walletReal || {}), balance: '29.600', available_for_withdrawal: '24.600', commission_this_month: '0.000', carrier_dues: '0.000', in_transit: '0.000', in_transit_releases: [], cancellation_debt: '0.000', pending_compensation: '0.000', currency: 'JOD', frozen: false, min_withdrawal_amount: '10.000', withdrawal_reserve_amount: '5.000', withdrawal_methods: ['cliq', 'bank'], earnings_hold_days: 0, owner_type: 'driver', owner_id: DID };
  if (path.endsWith('/wallet/me/transactions')) return TXNS();
  // **نقاطُ الالتزام بقيم الأردن الحقيقيّة** (10/يوم · 100 نقطة = 2.500 · النافذة 07:00–23:59 · 10 ساعات) وحالُها «جارٍ» للعرض
  if (K && path.endsWith('/drivers/me/commitment')) return { enabled: true, window_start: '07:00', window_end: '23:59', span_minutes: 600, max_break_minutes: 60, max_total_break_minutes: 120, points_per_day: 10, points_per_credit_unit: 100, credit_unit_value: '2.500', currency: 'JOD', points_balance: 0, credit_balance: '0.000', credit_value_of_points: '0.000', convertible_points: 0, today: { state: 'running', elapsed_minutes: 372, online_minutes: 340, breaks_used_minutes: 32, break_count: 1, current_break_minutes: 0, remaining_minutes: 228, can_restart: false, reason: null }, recent: [] };
  if (!K && path.endsWith('/wallet/me')) return { owner_id: 'rider', owner_type: 'rider', balance: '12.500', currency: 'JOD', frozen: false, cancellation_debt: '0.000', pending_compensation: '0.000' };
  return undefined;
}
function mockWrite(method, path, body) {
  if (path.endsWith('/auth/refresh')) return [200, { access_token: TOKEN, refresh_token: 'store-refresh', token_type: 'bearer', expires_in: 3600 }];
  if (path.endsWith('/drivers/me/online') || path.endsWith('/drivers/me/offline')) {
    st.online = path.endsWith('/online'); const d = st.driverMe?.driver || {}; return [200, { ...d, is_online: st.online }];
  }
  if (path.endsWith('/rides/estimate')) {
    const cat = body?.vehicle_category || 'economy';
    return ['economy', 'comfort'].includes(cat) ? [200, ESTIMATE(cat)] : [403, { detail: 'not_available' }];
  }
  if (/\/rides$/.test(path) && method === 'POST') { st.ride = ride('searching'); return [201, st.ride]; }
  const act = path.match(new RegExp(`/rides/${RID}/([a-z_-]+)$`));
  if (act) {
    const to = { accept: 'accepted', arrive: 'arrived', start: 'in_progress', complete: 'completed' }[act[1]];
    if (to) { st.ride = ride(to); return [200, st.ride]; }
    return [200, {}];
  }
  return [200, {}];
}

const b = await chromium.launch();
const DSF = 2.625;
const ctx = await b.newContext({
  viewport: { width: 412, height: 892 }, deviceScaleFactor: DSF, isMobile: true, hasTouch: true, colorScheme: THEME,
  locale: fr ? 'fr-FR' : 'ar-JO', timezoneId: 'Asia/Amman', geolocation: K ? { latitude: D0.lat, longitude: D0.lng, accuracy: 8 } : { latitude: A.lat, longitude: A.lng, accuracy: 8 }, permissions: ['geolocation'],
  userAgent: 'Mozilla/5.0 (Linux; Android 15; SM-G991N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36',
});
await ctx.addInitScript(([tok, k, lang, theme]) => {
  try {
    localStorage.setItem(k ? 'taxo.driver.access_token' : 'taxo.access_token', tok);
    localStorage.setItem(k ? 'taxo.driver.theme' : 'taxo.theme', theme);
    localStorage.setItem('taxo.lang', lang);
    for (const key of ['taxo.driver.welcome.seen', 'taxo.driver.welcome.intro.seen', 'taxo.welcome.seen', 'taxo.tour.v1', 'taxo.driver.permission.walk.done']) localStorage.setItem(key, key === 'taxo.tour.v1' ? 'done' : '1');
  } catch {}
}, [TOKEN, K, LANG, THEME]);
// **حارسٌ عامّ**: أيُّ كتابةٍ إلى أيِّ مضيفٍ غيرِ ما يُحاكى تُقطع (قياسُ Mapbox، تحليلات…) — ولا تبلغ أحداً
await ctx.route('**/*', async (route) => {
  const r = route.request(), u = new URL(r.url());
  if (u.hostname === 'api.tajora.ly') return route.fallback();
  if (r.method() !== 'GET' && r.method() !== 'HEAD' && r.method() !== 'OPTIONS') { log.push(`BLOCK ${r.method()} ${u.hostname}${u.pathname}`); return route.fulfill({ status: 204, body: '' }); }
  return route.fallback();
});
await ctx.route('https://api.mapbox.com/search/geocode/**', (route) => { log.push('MOCK GEOCODE ' + (route.request().url().includes('/reverse') ? 'reverse' : 'forward')); return route.fulfill({ status: 200, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body: JSON.stringify(MBX(route.request().url())) }); });
await ctx.route('https://api.tajora.ly/**', async (route) => {
  const r = route.request(), u = new URL(r.url()), m = r.method();
  const cors = { 'access-control-allow-origin': r.headers().origin || '*', 'access-control-allow-credentials': 'true', 'access-control-allow-headers': r.headers()['access-control-request-headers'] || '*', 'access-control-allow-methods': 'GET,POST,PATCH,PUT,DELETE,OPTIONS' };
  if (m === 'OPTIONS') return route.fulfill({ status: 204, headers: cors });
  if (m === 'GET') {
    const mocked = mockGet(u.pathname, u.searchParams);
    if (mocked !== undefined) {
      const key = `MOCK GET ${u.pathname}`; if (!seen.has(key)) { seen.add(key); log.push(key); }
      return route.fulfill({ status: 200, contentType: 'application/json', headers: cors, body: JSON.stringify(mocked) });
    }
    const resp = await route.fetch();
    passed.push(`${resp.status()} ${u.pathname}`);
    if (!/json/.test(resp.headers()['content-type'] || '')) return route.fulfill({ response: resp, headers: { ...resp.headers(), ...cors } });
    let text = await resp.text();
    if (resp.status() === 200 && /json/.test(resp.headers()['content-type'] || '')) {
      try {
        const j = JSON.parse(text);
        if (u.pathname.endsWith('/drivers/me')) st.driverMe = j;
        if (fr) { if (j && j.language) j.language = 'fr'; if (j?.user?.language) j.user.language = 'fr'; text = JSON.stringify(j); }
        realGet[u.pathname] = text.slice(0, 1200);
      } catch {}
    }
    return route.fulfill({ status: resp.status(), headers: { ...resp.headers(), ...cors }, body: text });
  }
  let body = null; try { body = r.postDataJSON(); } catch {}
  const [status, out] = mockWrite(m, u.pathname, body);
  log.push(`MOCK ${m} ${u.pathname} -> ${status}`);
  if (u.pathname.endsWith('/telemetry/errors')) log.push('TELEMETRY ' + JSON.stringify(body).slice(0, 600));
  return route.fulfill({ status, contentType: 'application/json', headers: cors, body: JSON.stringify(out) });
});
let ws = null;
await ctx.routeWebSocket(/wss?:\/\/api\.tajora\.ly\//, (w) => { ws = w; log.push('MOCK WS ' + new URL(w.url()).pathname); w.onMessage(() => {}); w.send(JSON.stringify({ type: 'connected', active_ride: st.ride })); });
const send = (o) => ws?.send(JSON.stringify(o));
const p = await ctx.newPage();
p.on('pageerror', (e) => log.push('PAGEERROR ' + e.message.slice(0, 200)));
async function shot(name, wait = 1200) {
  await p.waitForTimeout(wait);
  await p.screenshot({ path: `${OUT}/${name}.png` });
  const txt = await p.evaluate(() => document.body.innerText).catch(() => '');
  console.log(`[${name}] ${p.url().replace(/^https:\/\/[^/]+/, '')}\n   ${txt.replace(/\n+/g, ' | ').slice(0, 700)}`);
}
const nav = async (path, wait = 2500) => { await p.evaluate((x) => { history.pushState({}, '', x); dispatchEvent(new PopStateEvent('popstate')); }, path); await p.waitForTimeout(wait); };
const click = async (re, timeout = 6000) => { const l = p.getByRole('button', { name: re }).first(); try { await l.click({ timeout }); return true; } catch { console.log('NOBTN', String(re)); return false; } };
const clickText = async (re, timeout = 6000) => { try { await p.getByText(re).first().click({ timeout }); return true; } catch { console.log('NOTEXT', String(re)); return false; } };

try {
  if (K) {
    await p.goto('https://driver.tajora.ly/', { waitUntil: 'networkidle', timeout: 90000 });
    await p.waitForTimeout(5000);
    await shot('k-home', 1500);
    console.log('BANNER', await p.evaluate(() => { const e = document.querySelector('[data-testid="launch-banner"]'); if (!e) return 'none'; e.scrollIntoView({ block: 'center' }); return e.innerText.slice(0, 160); }));
    await shot('k-banner', 900);
    await p.evaluate(() => { scrollTo(0, 0); document.querySelectorAll('*').forEach((e) => { if (e.scrollTop) e.scrollTop = 0; }); });
    await clickText(fr ? /Commencer|recevoir|Passer en ligne/i : /ابدأ الاستقبال/);
    await shot('k-online', 3000);
    st.ride = null;
    send({ type: 'ride_offer', ride: { ...ride('searching'), driver: null }, distance_to_pickup_km: 0.43, expires_in_seconds: 25 });
    await shot('k-offer', 3000);
    await click(fr ? /Accepter/ : /قبول/);
    await shot('k-nav', 4500);
    st.ride = ride('arrived'); send({ type: 'driver_arrived', ride: st.ride }); await shot('k-arrived', 2500);
    st.ride = ride('in_progress'); send({ type: 'ride_started', ride: st.ride }); await shot('k-trip', 4000);
    { const knob = p.locator('.t2-rd-swipe-knob').first();
      await knob.press('Enter').catch((e) => console.log('NOKNOB', e.message.slice(0, 60)));
      await p.waitForTimeout(900);
      if (!/تم الاستلام|Reçu/.test(await p.evaluate(() => document.body.innerText))) {
        const bx = await knob.boundingBox().catch(() => null);
        if (bx) { await p.mouse.move(bx.x + bx.width / 2, bx.y + bx.height / 2); await p.mouse.down(); await p.mouse.move(bx.x - 330, bx.y + bx.height / 2, { steps: 14 }); await p.mouse.up(); }
        await p.waitForTimeout(900);
      }
      await click(/تأكيد|نعم|إنهاء|Confirmer|Terminer/, 2500); }
    await shot('k-collect', 3500);
    await nav('/wallet/earnings', 3500); await shot('k-earn', 1500); await clickText(fr ? /^Semaine$/ : /^الأسبوع$/); await shot('k-earn-week', 2000);
    await nav('/wallet', 3500); await shot('k-wallet', 1500);
  } else {
    await p.goto('https://app.tajora.ly/', { waitUntil: 'networkidle', timeout: 90000 });
    await p.waitForTimeout(5000);
    await shot('r-home', 1500);
    await p.evaluate(() => { const e = [...document.querySelectorAll('section, div')].find((x) => /الخيار الأوفر|Le plus économique/.test(x.innerText || '') && x.getBoundingClientRect().height < 600); if (e) e.scrollIntoView({ block: 'center' }); }); await shot('r-cats', 1200);
    await p.evaluate(() => { scrollTo(0, 0); document.querySelectorAll('*').forEach((e) => { if (e.scrollTop) e.scrollTop = 0; }); }); await p.waitForTimeout(600);
    await clickText(fr ? /Où allez-vous/ : /إلى أين؟/); await shot('r-where', 2000); await p.locator('.t2-picking-search').first().click({ timeout: 6000 }).catch(() => console.log('NOSEARCHBTN')); await p.waitForTimeout(1200);
    const inp = p.locator('input').last();
    await inp.fill(fr ? 'Abdali' : 'العبدلي').catch(() => console.log('NOINPUT')); await shot('r-results', 3500);
    await clickText(fr ? /Abdali/ : /العبدلي/);
    await shot('r-confirm', 4500);
    const cta = () => p.locator('.t2-cta, [class*="t2-cta"], button[class*="cta"]').last().click({ timeout: 6000 }).catch(() => console.log('NOCTA'));
    await cta(); await shot('r-classes', 3000);
    await cta(); await shot('r-search', 3000);
    st.ride = ride('accepted'); send({ type: 'driver_assigned', ride: st.ride }); await shot('r-found0', 2500);
    const path = [[35.8519, 31.9541], [35.8531, 31.9549], [35.8540, 31.9554], [35.8545, 31.9558]];
    for (const [lng, lat] of path) { send({ type: 'driver_location', driver_id: DID, lat, lng, heading: 60 }); await p.waitForTimeout(900); }
    await shot('r-found', 2000);
    st.ride = ride('in_progress'); send({ type: 'ride_started', ride: st.ride });
    for (const [lng, lat] of [[35.8668, 31.9581], [35.8730, 31.9577], [35.8790, 31.9572]]) { send({ type: 'driver_location', driver_id: DID, lat, lng, heading: 85 }); await p.waitForTimeout(900); }
    await shot('r-trip', 2500);
    st.ride = ride('completed'); send({ type: 'ride_completed', ride: st.ride }); await shot('r-done', 4000);
    await nav(`/rides/${RID}/rate`, 3500); await p.locator('.t2-r10-star').nth(4).click({ timeout: 6000 }).catch(() => console.log('NOSTAR')); await shot('r-rate', 2000);
    await nav(`/rides/${RID}/pay`, 3500); await shot('r-pay', 1500);
    await nav('/wallet', 3500); await shot('r-wallet', 1500);
  }
} catch (e) { console.log('STOP', e.message.split('\n')[0]); await shot('stopped', 300).catch(() => {}); }
fs.writeFileSync(`${OUT}/log.txt`, [...log, '--- passed GETs', ...passed].join('\n'));
fs.writeFileSync(`${OUT}/realget.json`, JSON.stringify(realGet, null, 1));
console.log('errors', log.filter((l) => l.startsWith('PAGEERROR')).slice(0, 4));
console.log('writes answered locally:', log.filter((l) => /^MOCK (POST|PATCH|PUT|DELETE)/.test(l)).length, '· blocked third-party writes:', log.filter((l) => l.startsWith('BLOCK')).length, '· GETs passed:', passed.length);
await b.close();
