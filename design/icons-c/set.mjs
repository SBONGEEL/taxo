/** **أيقوناتُ TAXO بالنمط C — أشكالٌ جديدةٌ كلُّها** (أمرُ المالك ٢٠٢٦-١١-١٧، `design/OWNER-LIBYA-OPEN-2026-11-17.md`).
 *
 * اختار المالكُ **ألوانَ النمط C وتعبئتَه** (برتقاليُّ TAXO ممتلئ، ودرجةٌ ثانيةٌ مزاحةٌ للعمق، وتفاصيلُ بالبرتقاليّ الداكن، وثقوبٌ بلون السطح)،
 * **ورفض الأشكالَ القديمة** — فكلُّ ما هنا مرسومٌ من جديد على شبكة ٤٨، **أصيلٌ لـTAXO** لا مقتبسٌ من تطبيقٍ ولا مكتبة.
 * والمركباتُ **بزاوية ثلاثة أرباع**، ولكلِّ فئةٍ مركبتُها. وعلامةُ الخريطة سيّارةٌ من فوق، **تدور مع الطريق** (`MARKER` + `smoothBearing`).
 *
 * الأدوار: `body` برتقاليّ (ومعه ظلٌّ مزاحٌ بالدرجة الثانية) · `back` الدرجةُ الثانية · `detail` البرتقاليُّ الداكن · `cut` لونُ السطح · `ground` ظلُّ الأرض.
 * **`icons_v2` مطفأ** حتى يوافق المالكُ على اللوحة والتسجيل؛ وبعد الموافقة تُنقل الأشكالُ إلى `taxo2/glyphs.ts` في التطبيقين واللوحة.
 */

export const ORANGE = "#f05a28";
export const ORANGE_DEEP = "#b8401a";

const P = (role, d) => ({ role, d });
const circle = (cx, cy, r) => `M${cx - r} ${cy}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0z`;
const ellipse = (cx, cy, rx, ry) => `M${cx - rx} ${cy}a${rx} ${ry} 0 1 0 ${2 * rx} 0a${rx} ${ry} 0 1 0 ${-2 * rx} 0z`;
const rect = (x, y, w, h, r = 0) =>
  r ? `M${x + r} ${y}h${w - 2 * r}a${r} ${r} 0 0 1 ${r} ${r}v${h - 2 * r}a${r} ${r} 0 0 1 ${-r} ${r}h${-(w - 2 * r)}a${r} ${r} 0 0 1 ${-r} ${-r}v${-(h - 2 * r)}a${r} ${r} 0 0 1 ${r} ${-r}z`
    : `M${x} ${y}h${w}v${h}h${-w}z`;
const poly = (pts) => "M" + pts.map(([x, y]) => `${+x.toFixed(2)} ${+y.toFixed(2)}`).join("L") + "z";

/** ترسٌ بثمانية أسنانٍ مستديرة الطرف — يُحسب ولا يُرسم بيد */
function gear(cx, cy, rOut, rIn, teeth = 8) {
  const pts = [];
  const step = (Math.PI * 2) / teeth;
  for (let i = 0; i < teeth; i++) {
    const a = i * step - Math.PI / 2;
    for (const [da, r] of [[-0.3, rIn], [-0.17, rOut], [0.17, rOut], [0.3, rIn]]) {
      pts.push([cx + r * Math.cos(a + da * step * 1.6), cy + r * Math.sin(a + da * step * 1.6)]);
    }
  }
  return poly(pts);
}

function star(cx, cy, R, r, n = 5) {
  const pts = [];
  for (let i = 0; i < n * 2; i++) {
    const a = (i * Math.PI) / n - Math.PI / 2;
    const rad = i % 2 ? r : R;
    pts.push([cx + rad * Math.cos(a), cy + rad * Math.sin(a)]);
  }
  return poly(pts);
}

// ───────────────────────────── المركبات — ثلاثةُ أرباعٍ من الأمام-اليمين، الأرضُ عند ٣٧
const wheels = (xs, farX) => [
  ...(farX ? [P("detail", ellipse(farX, 34.6, 2.1, 3.4))] : []),
];
const nearWheels = (xs) => xs.flatMap((x) => [P("detail", circle(x, 33.6, 4.3)), P("cut", circle(x, 33.6, 1.7))]);
const ground = (x0 = 5, x1 = 44) => P("ground", ellipse((x0 + x1) / 2, 39.6, (x1 - x0) / 2, 2.1));

const HATCH = {
  side: "M4 33V26.6c0-1.6 1-2.6 2.6-2.9l4.6-.8 4.6-6.4c.8-1.1 1.9-1.6 3.2-1.6h9.6c1.3 0 2.4.6 3.1 1.6l3.4 5.4 1 .2V33z",
  roof: "M18.6 15.1l3.1-1.6h11.6l-1.8 3.2c-.7-1-1.8-1.6-3.1-1.6z",
  glass: "M31.6 16.7l1.7-3.2 4.8 3 3.4 7.7-6.4-2z",
  front: "M35.1 22.2l6.4 2c1.2.4 2 1.3 2 2.6v6.9l-8.4.4z",
  win: ["M16.9 17.2c.5-.6 1.1-.8 1.9-.8h3.6v5.8h-8.7z", "M24.4 16.4h3.7c.9 0 1.6.4 2.1 1.1l2.9 4.7h-8.7z"],
  lamp: "M38 27.2l4.3 1.2v1.8L38 29z",
};

function hatchback(extra = []) {
  return [
    ground(),
    ...wheels([], 40.9),
    P("body", HATCH.side), P("back", HATCH.roof), P("detail", HATCH.front),
    P("cut", HATCH.glass), ...HATCH.win.map((d) => P("cut", d)), P("cut", HATCH.lamp),
    ...nearWheels([12, 29.6]),
    ...extra,
  ];
}

const VAN = {
  side: "M4 33V14.2c0-1.8 1.4-3.2 3.2-3.2h23.5c1.2 0 2.3.6 2.9 1.6l4.4 7.6V33z",
  roof: "M7.2 11l2.8-2h25.6l-1.9 3.4c-.6-.9-1.7-1.4-2.8-1.4z",
  glass: "M33.6 12.5l2-3.5 4.3 2.6 4.1 9.9-6-1.8z",
  front: "M38 19.7l6 1.8c.6.2 1 .8 1 1.4V33l-7 .5z",
  lamp: "M39.6 26.5l4.2 1.1v1.8l-4.2-1z",
};
function van(windows, extra = []) {
  return [
    ground(4, 45),
    ...wheels([], 42.2),
    P("body", VAN.side), P("back", VAN.roof), P("detail", VAN.front), P("cut", VAN.glass), P("cut", VAN.lamp),
    ...windows.map((d) => P("cut", d)),
    ...nearWheels([11.5, 30]),
    ...extra,
  ];
}

export const VEHICLES = {
  // اقتصادي — هاتشباك قصيرةٌ بلافتةٍ على السقف
  local_taxi: hatchback([P("detail", rect(22.4, 10.1, 7.4, 3.6, 1.4)), P("cut", rect(24.2, 11.2, 3.8, 1.4, 0.6))]),
  // مريح — سيدانُ بصندوقٍ خلفيٍّ طويلٍ ونجمة
  directions_car: [
    ground(2, 45),
    P("detail", ellipse(41.2, 34.6, 2.1, 3.4)),
    P("body", "M2.5 33v-5.8c0-1.6 1.1-2.6 2.6-2.8l6.6-.9 4.6-6.6c.8-1.1 1.9-1.6 3.2-1.6h9c1.3 0 2.4.6 3.1 1.6l3.5 5.3 1.2.3V33z"),
    P("back", "M19.5 15.3l3.1-1.6h11l-1.8 3.2c-.7-1-1.8-1.6-3.1-1.6z"),
    P("detail", "M36.3 22.5l6 1.9c1.3.4 2.1 1.4 2.1 2.7V33.7l-8.1.4z"),
    P("cut", "M31.8 16.9l1.8-3.2 4.6 3 3.6 7.7-5.5-1.9z"),
    P("cut", "M17.8 17.4c.5-.6 1.1-.9 1.9-.9h3.5v5.9h-8.9z"), P("cut", "M25.2 16.5h3.4c.9 0 1.6.4 2.1 1.1l3.1 4.8h-8.6z"),
    P("cut", "M39 27.3l4.4 1.2v1.8L39 29.1z"),
    P("detail", rect(3.6, 26.6, 4.6, 1.6, 0.8)),
    ...nearWheels([11, 30.4]),
    P("detail", star(41.5, 9.5, 4.4, 1.9)),
  ],
  // كهربائيّة — هاتشباك ببرقٍ على الباب
  electric_car: hatchback([P("cut", "M22.4 23.8l-3 4.6h2.7l-1.6 3.8 5-5.3h-2.8l1.9-3.1z")]),
  // حافلةٌ صغيرةٌ للمطار — نوافذُ متتالية
  airport_shuttle: van([rect(7, 13.8, 6.3, 6, 1.4), rect(15.2, 13.8, 6.3, 6, 1.4), rect(23.4, 13.8, 6.3, 6, 1.4), "M31.6 13.8h.9c.6 0 1 .3 1.3.8l2.7 5.2h-4.9z"]),
  // ذوو الهمم — حافلةٌ صغيرةٌ وكرسيٌّ متحرّك
  accessible: van(
    [rect(7, 13.8, 6.3, 6, 1.4), "M31.6 13.8h.9c.6 0 1 .3 1.3.8l2.7 5.2h-4.9z"],
    [P("cut", circle(22.5, 14.6, 1.8)), P("cut", "M21.4 17.2h2.4v4.2h4l2 4.4-2 .9-1.5-3.1h-4.9z"), P("cut", "M19.4 20.4a4.6 4.6 0 1 0 6.9 5.3l-1.7-.6a2.8 2.8 0 1 1-4.3-3.2z")],
  ),
  // نقلٌ وطرود — صندوقٌ ومقصورة
  local_shipping: [
    ground(3, 45),
    P("detail", ellipse(42, 34.6, 2.1, 3.4)),
    P("body", rect(3, 9.5, 24, 23.5, 2.4)), P("back", "M5.2 9.5l2.6-2.2h21.8L27 9.5z"),
    P("detail", rect(7, 14, 16, 2.4, 1.2)), P("detail", rect(7, 19, 11, 2.4, 1.2)),
    P("body", "M27 33V18.4h5.6c1.1 0 2 .5 2.6 1.4l3.4 5.1V33z"),
    P("detail", "M38.6 24.9l5.3 1.7c.7.2 1.1.8 1.1 1.5V33.6l-6.4.4z"),
    P("cut", "M33.4 18.4l2.4-2.2 4 2.6 3.8 7.4-5-1.3z"), P("cut", "M29.2 20.5h3.3c.7 0 1.3.3 1.6.9l2.1 3.5h-7z"),
    P("cut", "M39.9 28.5l3.8 1v1.6l-3.8-.9z"),
    ...nearWheels([10, 32.6]),
  ],
  // حافلة — طويلةٌ بنوافذَ ممتدّةٍ وزجاجٍ أماميٍّ كبير
  directions_bus: [
    ground(2, 46),
    P("detail", ellipse(42.6, 34.6, 2.1, 3.4)),
    P("body", rect(2, 10, 35.5, 23, 3)), P("back", "M5 10l2.9-2.2h31.4L37.5 10z"),
    P("detail", "M37.5 10.4l6.6 2.4c.6.2.9.8.9 1.4V33.4l-7.5.4z"),
    P("cut", "M38.9 13.3l4.8 1.8v8.3l-4.8-1.4z"), P("cut", "M39.3 27.3l4 1.1v1.7l-4-1z"),
    P("cut", rect(4.6, 13.2, 6.4, 6.6, 1.4)), P("cut", rect(12.6, 13.2, 6.4, 6.6, 1.4)), P("cut", rect(20.6, 13.2, 6.4, 6.6, 1.4)), P("cut", rect(28.6, 13.2, 6.4, 6.6, 1.4)),
    P("detail", rect(2, 23.4, 35.5, 2.4)),
    ...nearWheels([9.5, 30]),
  ],
  // كابتنة للنساء — هاتشباك بقلبٍ على الباب
  woman: hatchback([P("cut", "M21.5 30.6l-3.6-3.5a2.2 2.2 0 0 1 3.1-3.1l.5.5.5-.5a2.2 2.2 0 0 1 3.1 3.1z")]),
};

// ───────────────────────────── الأيقونات — أشكالٌ جديدة
export const GLYPHS = {
  home: [
    P("detail", rect(31, 9.5, 5.4, 9, 1.4)),
    P("body", "M7.5 23.1L22.1 10.2a2.9 2.9 0 0 1 3.8 0L40.5 23.1V38a3.5 3.5 0 0 1-3.5 3.5H11A3.5 3.5 0 0 1 7.5 38z"),
    P("cut", "M19.5 41.5V31a4 4 0 0 1 4-4h1a4 4 0 0 1 4 4v10.5z"),
  ],
  receipt_long: [
    P("body", rect(9, 5.5, 30, 37, 6)),
    P("cut", circle(17.5, 14.5, 3.3)), P("cut", rect(23.5, 12.8, 10, 3.4, 1.7)),
    P("cut", rect(16.3, 20.2, 2.4, 2.4, 1.2)), P("cut", rect(16.3, 24.4, 2.4, 2.4, 1.2)),
    P("cut", "M17.5 29a4.4 4.4 0 0 1 4.4 4.4c0 3-4.4 6.6-4.4 6.6s-4.4-3.6-4.4-6.6A4.4 4.4 0 0 1 17.5 29z"),
    P("detail", "M19 33.3a1.5 1.5 0 1 0-3 0a1.5 1.5 0 1 0 3 0z"), P("cut", rect(23.5, 31.6, 10, 3.4, 1.7)),
  ],
  account_balance_wallet: [
    P("back", rect(11, 6.5, 25, 12, 3.5)),
    P("body", rect(5.5, 13, 37, 28, 6.5)),
    P("detail", "M30 21.5h12.5v11H30a5.5 5.5 0 0 1 0-11z"),
    P("cut", circle(30.5, 27, 2.3)),
  ],
  person: [
    P("body", circle(24, 15.5, 8)),
    P("body", "M8.5 39.5C8.5 31 15.4 26.5 24 26.5S39.5 31 39.5 39.5a2.5 2.5 0 0 1-2.5 2.5H11a2.5 2.5 0 0 1-2.5-2.5z"),
  ],
  notifications: [
    P("detail", "M19.4 37.8h9.2c-.3 3-2.1 5.2-4.6 5.2s-4.3-2.2-4.6-5.2z"),
    P("body", "M24 5.5c1.3 0 2.3 1 2.3 2.3v1.4c5.4 1.2 9 6 9 11.7v7.8l3.6 4.7c.9 1.2.1 2.9-1.4 2.9H10.5c-1.5 0-2.3-1.7-1.4-2.9l3.6-4.7v-7.8c0-5.7 3.6-10.5 9-11.7V7.8c0-1.3 1-2.3 2.3-2.3z"),
    P("detail", circle(36.5, 10.5, 5.2)), P("cut", circle(36.5, 10.5, 2)),
  ],
  search: [
    P("detail", "M29.8 33.3l3.5-3.5 9.4 9.4a2.5 2.5 0 0 1-3.5 3.5z"),
    P("body", circle(21, 21, 14.5)), P("cut", circle(21, 21, 9.2)),
    P("back", "M14.6 18.4a7 7 0 0 1 4-4.6l1 2.2a4.6 4.6 0 0 0-2.7 3.1z"),
  ],
  location_on: [
    P("ground", ellipse(24, 43.2, 8.5, 2)),
    P("body", "M24 42S10 30.4 10 19.6a14 14 0 0 1 28 0C38 30.4 24 42 24 42z"),
    P("cut", circle(24, 19.6, 5.6)),
  ],
  my_location: [
    P("detail", rect(22.4, 3.5, 3.2, 7, 1.6)), P("detail", rect(22.4, 37.5, 3.2, 7, 1.6)),
    P("detail", rect(3.5, 22.4, 7, 3.2, 1.6)), P("detail", rect(37.5, 22.4, 7, 3.2, 1.6)),
    P("body", circle(24, 24, 13)), P("cut", circle(24, 24, 8.4)), P("body", circle(24, 24, 4.4)),
  ],
  tune: [
    P("detail", rect(6, 11, 36, 4.4, 2.2)), P("detail", rect(6, 21.8, 36, 4.4, 2.2)), P("detail", rect(6, 32.6, 36, 4.4, 2.2)),
    P("body", circle(30, 13.2, 5.6)), P("cut", circle(30, 13.2, 2)),
    P("body", circle(16.5, 24, 5.6)), P("cut", circle(16.5, 24, 2)),
    P("body", circle(33, 34.8, 5.6)), P("cut", circle(33, 34.8, 2)),
  ],
  star: [P("body", star(24, 25, 19, 8.6)), P("cut", star(24, 25.6, 5.4, 2.6))],
  chat: [
    P("body", "M11 7h26a5 5 0 0 1 5 5v16a5 5 0 0 1-5 5H20.5L12 40.5V33h-1a5 5 0 0 1-5-5V12a5 5 0 0 1 5-5z"),
    P("cut", circle(16.5, 20, 2.5)), P("cut", circle(24, 20, 2.5)), P("cut", circle(31.5, 20, 2.5)),
  ],
  call: [
    P("body", "M14.6 7.6c2.2-.9 3.5-.2 4.3 1.6l3 6.3c.9 1.9.4 3.3-1.2 4.6l-2.2 1.8c2.2 4.6 5.4 7.8 10 10l1.8-2.2c1.3-1.6 2.7-2.1 4.6-1.2l6.3 3c1.8.8 2.5 2.1 1.6 4.3l-1.1 2.7C40.8 40.6 39 41.6 36.4 41.4 21.6 40.2 7.8 26.4 6.6 11.6 6.4 9 7.4 7.2 9.4 6.4z"),
    P("detail", "M29.5 5.5a14 14 0 0 1 13 13l-3.2.2a10.8 10.8 0 0 0-10-10zM28.6 11.4a8.2 8.2 0 0 1 8 8l-3.2.1a5 5 0 0 0-4.9-4.9z"),
  ],
  shield: [
    P("body", "M24 4.5l15 6v10.6c0 9.6-6.3 17.6-15 21.4C15.3 38.7 9 30.7 9 21.1V10.5z"),
    P("cut", "M16.6 23.5l2.7-2.7 3.4 3.4 6.8-6.8 2.7 2.7-9.5 9.5z"),
  ],
  schedule: [
    P("body", circle(24, 24, 18)),
    P("cut", rect(22.4, 12, 3.2, 13, 1.6)), P("cut", "M23 23.2l8.6 5-1.6 2.8-8.6-5z"), P("detail", circle(24, 24, 2.4)),
  ],
  history: [
    P("detail", "M5.5 10.5l9.8 1.1-6.7 7.3z"),
    P("body", "M24 6a18 18 0 1 1-17.2 23.4l4.3-1.3A13.5 13.5 0 1 0 12.5 15.6L8.6 13.4A18 18 0 0 1 24 6z"),
    P("body", rect(22.2, 14, 3.6, 12, 1.8)), P("body", "M23 23.6l7.6 4.4-1.8 3.1-7.6-4.4z"),
  ],
  credit_card: [
    P("body", rect(5.5, 10.5, 37, 27, 5)),
    P("detail", rect(5.5, 16, 37, 5.2)),
    P("cut", rect(10.5, 26, 9, 6.4, 1.6)), P("cut", rect(25, 28.2, 12.5, 2.6, 1.3)),
  ],
  payments: [
    P("back", rect(11, 8.5, 31, 20, 4)),
    P("body", rect(6, 15.5, 31, 21.5, 4)),
    P("cut", circle(21.5, 26.2, 5)), P("detail", circle(21.5, 26.2, 2)),
    P("cut", circle(11, 20.5, 1.6)), P("cut", circle(32, 32, 1.6)),
  ],
  redeem: [
    P("body", "M24 17c-3.4-6.6-9-9.8-11.2-6.6-1.9 2.8 1.6 6.6 11.2 6.6z"),
    P("body", "M24 17c3.4-6.6 9-9.8 11.2-6.6 1.9 2.8-1.6 6.6-11.2 6.6z"),
    P("body", rect(9, 23, 30, 19, 3.5)), P("detail", rect(7, 16.5, 34, 7.5, 2.5)),
    P("cut", rect(22, 23.6, 4, 18.4)),
  ],
  settings: [P("body", gear(24, 24, 19, 14.4, 8)), P("cut", circle(24, 24, 6.4))],
  help: [
    P("body", circle(24, 24, 18)),
    P("cut", "M18.6 19.2C18.6 14.6 21 12.6 24.4 12.6c3.6 0 5.9 2.2 5.9 5.4 0 2.6-1.4 3.9-3.3 5-1.1.6-1.5 1.2-1.5 2.4v1h-3.6v-1.3c0-2.4 1-3.6 2.8-4.6 1.4-.8 2-1.5 2-2.6 0-1.3-.9-2.2-2.4-2.2-1.6 0-2.4 1-2.4 3.1z"),
    P("cut", circle(24.1, 32.2, 2.3)),
  ],
  share: [
    P("detail", "M16.4 21.4l13.4-7.1 1.7 3.2-13.4 7.1zM18.1 23.3l13.4 7.1-1.7 3.2-13.4-7.1z"),
    P("body", circle(34.5, 13, 6.4)), P("body", circle(13.5, 24, 6.4)), P("body", circle(34.5, 35, 6.4)),
  ],
  flag: [
    P("detail", rect(9, 5.5, 3.6, 37, 1.8)),
    P("body", "M12.6 8h23.6c1.9 0 2.9 2 1.9 3.6L34.6 17l3.5 5.4c1 1.6 0 3.6-1.9 3.6H12.6z"),
    P("cut", rect(17, 13, 5, 3.6, 1)), P("cut", rect(22, 16.6, 5, 3.6, 1)), P("cut", rect(17, 20.2, 5, 3.6, 1)),
  ],
  close: [
    P("body", circle(24, 24, 18)),
    P("cut", "M17.6 15.4L24 21.8l6.4-6.4 2.2 2.2L26.2 24l6.4 6.4-2.2 2.2L24 26.2l-6.4 6.4-2.2-2.2 6.4-6.4-6.4-6.4z"),
  ],
  check_circle: [P("body", circle(24, 24, 18)), P("cut", "M15 24.4l2.6-2.6 4 4 9-9 2.6 2.6L21.6 31z")],
  arrow_forward: [P("body", "M27 9.5L41.5 24 27 38.5l-3.6-3.6 8.4-8.4H7v-5h24.8l-8.4-8.4z")],
  sell: [
    P("body", "M8 10.5A3.5 3.5 0 0 1 11.5 7h12.1c1 0 1.9.4 2.5 1l14.7 14.7a3.5 3.5 0 0 1 0 5L28.7 39.8a3.5 3.5 0 0 1-5 0L9 25.1a3.5 3.5 0 0 1-1-2.5z"),
    P("cut", circle(16, 15, 3.4)), P("detail", "M20.6 27.4l9-9 2.1 2.1-9 9z"),
  ],
  support_agent: [
    P("detail", "M10 24a14 14 0 0 1 28 0h-3.6a10.4 10.4 0 0 0-20.8 0z"),
    P("body", rect(6.5, 22, 8.5, 13, 3.6)), P("body", rect(33, 22, 8.5, 13, 3.6)),
    P("detail", "M37.2 35v1.6c0 3-2.4 5.4-5.4 5.4H26v-3.4h5.8c1.1 0 2-.9 2-2V35z"), P("body", rect(21, 36.5, 7.5, 6.5, 3.2)),
  ],
  local_gas_station: [
    P("body", rect(8, 7, 21, 35, 4)), P("cut", rect(12, 11.5, 13, 9, 2)),
    P("detail", "M29 18h4.6a3 3 0 0 1 3 3v12.4a1.6 1.6 0 0 0 3.2 0V16.6l-4.4-4.4 2.3-2.3 5 5c.6.6 1 1.4 1 2.3v16.2a5 5 0 0 1-10 0V21.4H29z"),
  ],
};

/** علامةُ الخريطة — سيّارةٌ من فوق، **تتّجه شمالاً** وتُدار بزاوية الطريق */
export const MARKER = [
  P("ground", ellipse(24, 25, 11.5, 20.5)),
  P("body", rect(14.5, 5, 19, 38, 8.5)),
  P("cut", "M17 15.2c4.6-2.6 9.4-2.6 14 0l-1 5.4c-4-1.5-8-1.5-12 0z"),
  P("detail", rect(18.4, 21.6, 11.2, 11, 3)),
  P("cut", "M18 34.2c4 1.3 8 1.3 12 0l.6 3.6c-4.4 1.6-8.8 1.6-13.2 0z"),
  P("cut", rect(16.6, 6.6, 3.6, 2.2, 1.1)), P("cut", rect(27.8, 6.6, 3.6, 2.2, 1.1)),
];

/** **دورانٌ ناعمٌ مع الطريق** — يأخذ الاتّجاهَ الجديد بأقصر قوس (فلا تلفّ السيّارةُ ٣٥٠° حين تعبر الشمال)،
 *  ويقترب منه بنسبةٍ في كلِّ إطار (`k`)، **ويتجاهل قفزاتِ GPS** تحت ٣ أمتار. يُنقل كما هو إلى `MapView` بعد موافقة المالك. */
export function smoothBearing(current, target, k = 0.18) {
  const delta = ((((target - current) % 360) + 540) % 360) - 180;
  return (current + delta * k + 360) % 360;
}
export function bearingBetween([lon1, lat1], [lon2, lat2]) {
  const toR = (d) => (d * Math.PI) / 180;
  const y = Math.sin(toR(lon2 - lon1)) * Math.cos(toR(lat2));
  const x = Math.cos(toR(lat1)) * Math.sin(toR(lat2)) - Math.sin(toR(lat1)) * Math.cos(toR(lat2)) * Math.cos(toR(lon2 - lon1));
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

/** الرسمُ بالنمط C — ظلٌّ مزاحٌ بالدرجة الثانية تحت كلِّ `body`، ثمّ الأجزاءُ بترتيبها */
export function renderC(parts, { dark = false, cut = dark ? "#171a1f" : "#ffffff", size, cls = "" } = {}) {
  const second = dark ? "#8f2f10" : "#ffb595";
  const groundFill = dark ? "#000000" : "#1f2433";
  const out = [];
  for (const p of parts) if (p.role === "body") out.push(`<path d="${p.d}" transform="translate(2 2)" fill="${second}"/>`);
  for (const p of parts) {
    const fill = { body: ORANGE, back: second, detail: ORANGE_DEEP, cut, ground: groundFill }[p.role];
    const op = p.role === "ground" ? ` opacity="${dark ? 0.45 : 0.12}"` : "";
    out.push(`<path d="${p.d}" fill="${fill}"${op}/>`);
  }
  const sz = size ? ` width="${size}" height="${size}"` : "";
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"${sz} class="ixc ${cls}" aria-hidden="true">${out.join("")}</svg>`;
}

/** الاسمُ العربيُّ لكلِّ أيقونةٍ في اللوحة */
export const LABELS = {
  local_taxi: "اقتصادي", directions_car: "مريح", electric_car: "كهربائيّة", airport_shuttle: "حافلة المطار", accessible: "ذوو الهمم",
  local_shipping: "طرود", directions_bus: "حافلة", woman: "كابتنة للنساء",
  home: "الرئيسيّة", receipt_long: "رحلاتي", account_balance_wallet: "المحفظة", person: "حسابي", notifications: "الإشعارات",
  search: "البحث", location_on: "الدبّوس", my_location: "موقعي", tune: "الخيارات", star: "التقييم", chat: "رسالة", call: "اتّصال",
  shield: "الأمان", schedule: "موعد", history: "السجلّ", credit_card: "بطاقة", payments: "نقداً", redeem: "هديّة", settings: "الإعدادات",
  help: "مساعدة", share: "مشاركة", flag: "الوجهة", close: "إغلاق", check_circle: "تمّ", arrow_forward: "رجوع", sell: "عرض",
  support_agent: "الدعم", local_gas_station: "وقود",
};
