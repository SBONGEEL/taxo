/** **أربعةُ اتّجاهاتٍ للأيقونات — A/B/C/D** (أمرُ المالك ٢٠٢٦-١١-١٦، `design/OWNER-ICONS-REDO-2026-11-16.md`).
 *
 * **رسمٌ أصيلٌ لـTAXO** — لا مقتبسٌ من تطبيقٍ ولا مكتبة. والهندسةُ واحدةٌ للأربعة (شبكةُ ٤٨)، **والاتّجاهُ يختلف في الإظهار**:
 *   A ثلاثيُّ الأبعاد الناعم · B الزجاج · C ثنائيُّ اللون الجريء · D المرسومُ الملوّن.
 * فالمقارنةُ بين الأربعة **مقارنةُ أسلوبٍ لا مقارنةُ أشكال** — وما يختاره المالكُ يُطبَّق على كلِّ الأيقونات بالقواعد نفسِها.
 *
 * `render(style, name, { dark, cut, uid })` يعيد نصَّ SVG كاملاً بـ`viewBox="0 0 48 48"`. و`cut` لونُ الثقوب (لونُ السطح تحته).
 * **ومعرِّفاتُ التدرّجات فريدةٌ لكلِّ نسخة** (`uid`) — فأيقونتان في الصفحة لا تتشاركان تدرّجاً.
 */

export const ORANGE = "#f05a28";
const ORANGE_DEEP = "#b8401a";

/* ── الهندسة: كلُّ أيقونةٍ أجزاءٌ بأدوار — body · back · detail · glass · accent · accent2 · cut · shadow */
const G = {
  economy: [
    { role: "accent", d: "M18.5 6.5h11a1.5 1.5 0 0 1 1.5 1.5v4h-14v-4a1.5 1.5 0 0 1 1.5-1.5z", d2: "#ffc93c" },
    { role: "detail", d: "M9 34h8v5a2.5 2.5 0 0 1-2.5 2.5h-3A2.5 2.5 0 0 1 9 39zM31 34h8v5a2.5 2.5 0 0 1-2.5 2.5h-3A2.5 2.5 0 0 1 31 39z", d2: "#2b2d42" },
    { role: "body", d: "M8 26.5l4.2-11.2A4.5 4.5 0 0 1 16.4 12h15.2a4.5 4.5 0 0 1 4.2 3.3L40 26.5V34a3 3 0 0 1-3 3H11a3 3 0 0 1-3-3z", d2: "#ffc93c" },
    { role: "glass", d: "M15 15.8h18l2.6 8.4H12.4z", d2: "#9ad7f5" },
    { role: "accent2", d: "M11 29.5a3 3 0 1 0 6 0a3 3 0 1 0-6 0zM31 29.5a3 3 0 1 0 6 0a3 3 0 1 0-6 0z", d2: "#ffffff" },
    { role: "detail", d: "M20 30h8a1.2 1.2 0 0 1 0 2.4h-8a1.2 1.2 0 0 1 0-2.4z", d2: "#2b2d42" },
  ],
  comfort: [
    { role: "detail", d: "M7 34h8v5a2.5 2.5 0 0 1-2.5 2.5h-3A2.5 2.5 0 0 1 7 39zM33 34h8v5a2.5 2.5 0 0 1-2.5 2.5h-3A2.5 2.5 0 0 1 33 39z", d2: "#2b2d42" },
    { role: "body", d: "M4.5 27l5.4-10.3A5 5 0 0 1 14.3 14h19.4a5 5 0 0 1 4.4 2.7L43.5 27v7a3 3 0 0 1-3 3h-33a3 3 0 0 1-3-3z", d2: "#2ec4b6" },
    { role: "glass", d: "M13 17h22l3.6 8H9.4z", d2: "#bfe9ff" },
    { role: "accent2", d: "M8 29h7.5a1.6 1.6 0 0 1 0 3.2H9.6A1.6 1.6 0 0 1 8 30.6zM32.5 29H40v1.6a1.6 1.6 0 0 1-1.6 1.6h-5.9a1.6 1.6 0 0 1 0-3.2z", d2: "#ffffff" },
    { role: "detail", d: "M19 30h10a1.3 1.3 0 0 1 0 2.6H19a1.3 1.3 0 0 1 0-2.6z", d2: "#1b5e58" },
    { role: "accent", d: "M40 4l1.3 3.2L44.5 8.5l-3.2 1.3L40 13l-1.3-3.2L35.5 8.5l3.2-1.3z", d2: "#ffc93c" },
  ],
  wallet: [
    { role: "back", d: "M11.5 6.5h20a3 3 0 0 1 3 3V20h-26V9.5a3 3 0 0 1 3-3z", d2: "#4ade80" },
    { role: "body", d: "M6 16.5a5 5 0 0 1 5-5h26a5 5 0 0 1 5 5v19a5 5 0 0 1-5 5H11a5 5 0 0 1-5-5z", d2: "#8e6cef" },
    { role: "detail", d: "M28 22.5h14v10H33a5 5 0 0 1 0-10z", d2: "#6a4fd1" },
    { role: "accent", d: "M31 27.5a2.6 2.6 0 1 0 5.2 0a2.6 2.6 0 1 0-5.2 0z", d2: "#ffc93c" },
  ],
  pin: [
    { role: "shadow", d: "M15 43.5a9 2.4 0 1 0 18 0a9 2.4 0 1 0-18 0z" },
    { role: "body", d: "M24 42.5S9 29.6 9 19a15 15 0 0 1 30 0c0 10.6-15 23.5-15 23.5z", d2: "#ff5a5f" },
    { role: "cut", d: "M18 19a6 6 0 1 0 12 0a6 6 0 1 0-12 0z", d2: "#ffffff" },
  ],
  search: [
    { role: "accent", d: "M29.4 33.6l4.2-4.2 9.6 9.6a3 3 0 0 1 0 4.2 3 3 0 0 1-4.2 0z", d2: "#ffb703" },
    { role: "body", d: "M5.5 20.5a15 15 0 1 0 30 0a15 15 0 1 0-30 0z", d2: "#3a86ff" },
    { role: "glass", d: "M10.5 20.5a10 10 0 1 0 20 0a10 10 0 1 0-20 0z", d2: "#cdebff" },
  ],
  bell: [
    { role: "accent", d: "M19.5 39.5h9a4.5 4.5 0 0 1-9 0z", d2: ORANGE },
    { role: "body", d: "M24 5.5a3 3 0 0 1 3 3v1.3c5.2 1.3 9 6 9 11.6v8.1l3.6 4.6a1.6 1.6 0 0 1-1.3 2.6H9.7a1.6 1.6 0 0 1-1.3-2.6L12 29.5v-8.1c0-5.6 3.8-10.3 9-11.6V8.5a3 3 0 0 1 3-3z", d2: "#ffc93c" },
    { role: "accent2", d: "M32 11a5.5 5.5 0 1 0 11 0a5.5 5.5 0 1 0-11 0z", d2: "#ff3b5c" },
  ],
  options: [
    { role: "detail", d: "M6 11h36a2.2 2.2 0 0 1 0 4.4H6A2.2 2.2 0 0 1 6 11zM6 21.8h36a2.2 2.2 0 0 1 0 4.4H6a2.2 2.2 0 0 1 0-4.4zM6 32.6h36a2.2 2.2 0 0 1 0 4.4H6a2.2 2.2 0 0 1 0-4.4z", d2: "#cbd5e1" },
    { role: "body", d: "M24.5 13.2a5.8 5.8 0 1 0 11.6 0a5.8 5.8 0 1 0-11.6 0z", d2: ORANGE },
    { role: "body", d: "M11 24a5.8 5.8 0 1 0 11.6 0a5.8 5.8 0 1 0-11.6 0z", d2: "#3a86ff" },
    { role: "body", d: "M28.5 34.8a5.8 5.8 0 1 0 11.6 0a5.8 5.8 0 1 0-11.6 0z", d2: "#2ec4b6" },
  ],
  online: [
    { role: "body", d: "M14 13.5h20a10.5 10.5 0 0 1 0 21H14a10.5 10.5 0 0 1 0-21z", d2: "#22c55e", knob: true },
    { role: "knobs", d: "M26 24a8 8 0 1 0 16 0a8 8 0 1 0-16 0z", d2: "#ffffff" },
  ],
  home: [
    { role: "body", d: "M8 21.6L22 9.4a3 3 0 0 1 4 0l14 12.2V38a3 3 0 0 1-3 3H11a3 3 0 0 1-3-3z", d2: "#ff8a5b" },
    { role: "cut", d: "M20 41V31a4 4 0 0 1 8 0v10z", d2: "#8e6cef" },
  ],
  rides: [
    { role: "body", d: "M12 5.5h24a3 3 0 0 1 3 3v34l-4.5-2.8-4.5 2.8-4.5-2.8-4.5 2.8-4.5-2.8L12 42.5l-3-1.9V8.5a3 3 0 0 1 3-3z", d2: "#ffffff" },
    { role: "detail", d: "M15 14h18a1.6 1.6 0 0 1 0 3.2H15a1.6 1.6 0 0 1 0-3.2zM15 21h13a1.6 1.6 0 0 1 0 3.2H15a1.6 1.6 0 0 1 0-3.2zM15 28h9a1.6 1.6 0 0 1 0 3.2h-9a1.6 1.6 0 0 1 0-3.2z", d2: "#94a3b8" },
    { role: "accent", d: "M29 30.5a3.2 3.2 0 1 0 6.4 0a3.2 3.2 0 1 0-6.4 0z", d2: ORANGE },
  ],
  person: [
    { role: "body", d: "M7.5 41.5c0-9 7.4-14.5 16.5-14.5s16.5 5.5 16.5 14.5a1.5 1.5 0 0 1-1.5 1.5H9a1.5 1.5 0 0 1-1.5-1.5z", d2: "#3a86ff" },
    { role: "body", d: "M15.5 14.5a8.5 8.5 0 1 0 17 0a8.5 8.5 0 1 0-17 0z", d2: "#ffc9a0" },
  ],
};

/** الثمانيةُ المطلوبةُ بترتيب الأمر، وثلاثُ أخواتٍ للشريط السفليّ ليُرى الشريطُ عائلةً واحدة */
export const SAMPLE = ["economy", "comfort", "wallet", "pin", "search", "bell", "options", "online"];
export const SAMPLE_LABEL = {
  economy: "اقتصاديّة", comfort: "مريحة", wallet: "المحفظة", pin: "دبّوسُ الموقع",
  search: "البحث", bell: "الإشعارات", options: "خيارات", online: "متّصل",
};
export const BAR = ["home", "rides", "wallet", "person"];

/** اسمُ Material في التطبيق ⇐ اسمُ الأيقونة هنا (للحقن على الشاشة الحقيقيّة) */
export const APP_NAME = {
  local_taxi: "economy", directions_car: "comfort", account_balance_wallet: "wallet", location_on: "pin",
  search: "search", notifications: "bell", tune: "options", home: "home", receipt_long: "rides", person: "person",
  my_location: "pin", place: "pin",
};

export const STYLES = {
  A: { key: "A", name: "ثلاثيُّ الأبعاد الناعم", hint: "مستديرةٌ لامعةٌ بضوءٍ وظلٍّ ناعمَين، كأشياءَ صغيرةٍ حقيقيّة" },
  B: { key: "B", name: "الزجاج", hint: "زجاجٌ شبهُ شفّافٍ بتوهّجٍ ولمعان — فاخرٌ في الداكن" },
  C: { key: "C", name: "ثنائيُّ اللون الجريء", hint: "أشكالٌ مملوءةٌ ببرتقاليّ TAXO ودرجةٍ ثانيةٍ للعمق" },
  D: { key: "D", name: "المرسومُ الملوّن", hint: "ودودةٌ ملوّنةٌ ذاتُ شخصيّة، بحدٍّ داكنٍ كالملصق" },
};

let counter = 0;

function shade(hex, f) {
  const n = parseInt(hex.slice(1), 16);
  const ch = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) =>
    Math.round(f >= 0 ? v + (255 - v) * f : v * (1 + f)),
  );
  return "#" + ch.map((v) => v.toString(16).padStart(2, "0")).join("");
}

/* ── A: ثلاثيُّ الأبعاد الناعم — جسمٌ بتدرّجٍ عموديّ، وبثقٌ تحته، ولمعةٌ في أعلاه، وظلٌّ ساقطٌ ناعم */
function renderA(parts, { dark, cut, uid }) {
  const defs = [];
  const body = [];
  const grad = (base, id) => {
    defs.push(`<linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${shade(base, 0.38)}"/><stop offset=".55" stop-color="${base}"/><stop offset="1" stop-color="${shade(base, -0.28)}"/></linearGradient>`);
    return `url(#${id})`;
  };
  defs.push(`<linearGradient id="${uid}hl" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".75"/><stop offset=".45" stop-color="#fff" stop-opacity="0"/></linearGradient>`);
  defs.push(`<filter id="${uid}sh" x="-30%" y="-30%" width="160%" height="170%"><feDropShadow dx="0" dy="${dark ? 2.6 : 2.2}" stdDeviation="2" flood-color="${dark ? "#000" : "#7a2c10"}" flood-opacity="${dark ? 0.55 : 0.28}"/></filter>`);
  const colorFor = (p) => {
    switch (p.role) {
      case "body": return p.d2 && ![ "#ffc93c", "#2ec4b6", "#8e6cef", "#ff5a5f", "#3a86ff", "#ff8a5b", "#ffc9a0", "#22c55e" ].includes(p.d2) ? p.d2 : ORANGE;
      case "back": return "#ffd8c7";
      case "detail": return dark ? "#3a3f48" : "#30343c";
      case "glass": return "#a9dcf7";
      case "accent": return "#ffc53d";
      case "accent2": return p.d2 === "#ff3b5c" ? "#ff3b5c" : "#fff4d6";
      case "cut": return "#fff6ef";
      case "knobs": return "#ffffff";
      default: return ORANGE;
    }
  };
  let i = 0;
  for (const p of parts) {
    if (p.role === "shadow") { body.push(`<path d="${p.d}" fill="#000" opacity="${dark ? 0.45 : 0.16}"/>`); continue; }
    let base = colorFor(p);
    if (p.role === "body" && parts.filter((q) => q.role === "body").length > 1 && p.d2 && p.d2 !== ORANGE) {
      base = p.d2 === "#ffc9a0" ? "#ffd2b0" : p.d2 === "#3a86ff" ? ORANGE : p.d2 === "#2ec4b6" ? "#ff9a6a" : base; // أخواتُ الجسم: الجمرُ ودرجاتُه
    }
    if (p.knob) base = "#ff7a45";
    const id = `${uid}g${i++}`;
    const big = p.role === "body" || p.role === "back" || p.role === "knobs";
    if (big) body.push(`<path d="${p.d}" transform="translate(0 1.8)" fill="${shade(base, -0.42)}"/>`);
    body.push(`<path d="${p.d}" fill="${grad(base, id)}"/>`);
    if (big || p.role === "accent" || p.role === "glass") body.push(`<path d="${p.d}" fill="url(#${uid}hl)"/>`);
  }
  return { defs, g: `<g filter="url(#${uid}sh)">${body.join("")}</g>` };
}

/* ── B: الزجاج — توهّجٌ ملوّنٌ خلفه، وجسمٌ نصفُ شفّافٍ بحدٍّ مضيء، ولمعةٌ مائلة */
function renderB(parts, { dark, uid }) {
  const defs = [
    `<filter id="${uid}bl" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="5"/></filter>`,
    `<linearGradient id="${uid}fill" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="${dark ? 0.34 : 0.62}"/><stop offset="1" stop-color="#fff" stop-opacity="${dark ? 0.06 : 0.18}"/></linearGradient>`,
    `<linearGradient id="${uid}edge" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".95"/><stop offset=".5" stop-color="#fff" stop-opacity=".25"/><stop offset="1" stop-color="#fff" stop-opacity=".6"/></linearGradient>`,
    `<linearGradient id="${uid}glow" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ff9a5c"/><stop offset="1" stop-color="${ORANGE}"/></linearGradient>`,
    `<linearGradient id="${uid}tint" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffb08a" stop-opacity="${dark ? 0.55 : 0.85}"/><stop offset="1" stop-color="${ORANGE}" stop-opacity="${dark ? 0.32 : 0.62}"/></linearGradient>`,
  ];
  const out = [];
  const main = parts.filter((p) => p.role === "body" || p.role === "back");
  // التوهّجُ خلف الزجاج — هو ما يجعل الشفافيةَ تُقرأ على السطح الأبيض
  for (const p of main) out.push(`<path d="${p.d}" fill="url(#${uid}glow)" opacity="${dark ? 0.9 : 0.75}" filter="url(#${uid}bl)" transform="translate(0 3)"/>`);
  for (const p of parts) {
    if (p.role === "shadow") continue;
    if (p.role === "body" || p.role === "back") {
      out.push(`<path d="${p.d}" fill="url(#${uid}tint)"/>`);
      out.push(`<path d="${p.d}" fill="url(#${uid}fill)" stroke="${dark ? `url(#${uid}edge)` : "#e8622f"}" stroke-opacity="${dark ? 1 : 0.55}" stroke-width="1.3"/>`);
    } else if (p.role === "glass" || p.role === "cut") {
      out.push(`<path d="${p.d}" fill="#fff" fill-opacity="${dark ? 0.22 : 0.55}" stroke="#fff" stroke-opacity=".8" stroke-width="1"/>`);
    } else if (p.role === "accent" || p.role === "accent2") {
      out.push(`<path d="${p.d}" fill="url(#${uid}glow)" stroke="#fff" stroke-opacity=".7" stroke-width=".9"/>`);
    } else if (p.role === "knobs") {
      out.push(`<path d="${p.d}" fill="#fff" fill-opacity=".92" stroke="#fff" stroke-width="1"/>`);
    } else {
      out.push(`<path d="${p.d}" fill="${dark ? "#fff" : "#c2461a"}" fill-opacity="${dark ? 0.45 : 0.55}"/>`);
    }
  }
  // اللمعةُ المائلة — شريطٌ أبيضُ رفيعٌ مقصوصٌ بالجسم
  const clipId = `${uid}clip`;
  defs.push(`<clipPath id="${clipId}">${main.map((p) => `<path d="${p.d}"/>`).join("")}</clipPath>`);
  out.push(`<g clip-path="url(#${clipId})"><path d="M-4 18L18 -4h7L3 18z" fill="#fff" opacity=".5"/></g>`);
  return { defs, g: out.join("") };
}

/* ── C: ثنائيُّ اللون الجريء — مملوءٌ بالجمر، والدرجةُ الثانيةُ ظلٌّ مزاحٌ للعمق، والتفاصيلُ قطعٌ بلون السطح */
function renderC(parts, { dark, cut }) {
  const out = [];
  const second = dark ? "#8f2f10" : "#ffb595";
  for (const p of parts) {
    if (p.role === "body" || p.role === "back") out.push(`<path d="${p.d}" transform="translate(2.2 2.2)" fill="${second}"/>`);
  }
  for (const p of parts) {
    switch (p.role) {
      case "shadow": out.push(`<path d="${p.d}" fill="${second}"/>`); break;
      case "back": out.push(`<path d="${p.d}" fill="${second}"/>`); break;
      case "body": out.push(`<path d="${p.d}" fill="${ORANGE}"/>`); break;
      case "detail": out.push(`<path d="${p.d}" fill="${p.d2 === "#cbd5e1" ? second : ORANGE_DEEP}"/>`); break;
      case "glass": case "cut": case "accent2": case "knobs": out.push(`<path d="${p.d}" fill="${cut}"/>`); break;
      case "accent": out.push(`<path d="${p.d}" fill="${ORANGE_DEEP}"/>`); break;
    }
  }
  return { defs: [], g: out.join("") };
}

/* ── D: المرسومُ الملوّن — ألوانُ الأجزاء، وحدٌّ داكنٌ واحدٌ كالملصق، ولمعةٌ بيضاءُ قصيرة */
function renderD(parts, { dark }) {
  const ink = dark ? "#f4efe6" : "#1f2433";
  const out = [];
  for (const p of parts) {
    if (p.role === "shadow") { out.push(`<path d="${p.d}" fill="${dark ? "#000" : "#1f2433"}" opacity="${dark ? 0.5 : 0.18}"/>`); continue; }
    const fill = p.d2 ?? ORANGE;
    out.push(`<path d="${p.d}" fill="${fill}" stroke="${ink}" stroke-width="2" stroke-linejoin="round"/>`);
  }
  return { defs: [], g: out.join("") };
}

const RENDER = { A: renderA, B: renderB, C: renderC, D: renderD };

/** SVG كاملٌ لأيقونةٍ بأسلوب. `cls` يُضاف إلى الجذر (لحركةٍ بـCSS). */
export function render(style, name, { dark = false, cut = dark ? "#171a1f" : "#ffffff", cls = "", size } = {}) {
  const parts = G[name];
  if (!parts) return "";
  const uid = `i${style}${++counter}_`;
  const { defs, g } = RENDER[style](parts, { dark, cut, uid });
  const sz = size ? ` width="${size}" height="${size}"` : "";
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"${sz} class="ix ix-${style} ix-${name} ${cls}" aria-hidden="true">${defs.length ? `<defs>${defs.join("")}</defs>` : ""}<g class="ix-root">${g}</g></svg>`;
}

/** الحركةُ — أيقونةٌ واحدةٌ لكلِّ اتّجاه، **`transform`/`opacity` وحدَهما** (القاعدةُ في `iconSet.ts`)، وتسكن بـ«تقليل الحركة». */
export const MOTION = {
  A: { icon: "economy", label: "السيّارةُ تنطلق" },
  B: { icon: "bell", label: "الجرسُ يرنّ ويتوهّج" },
  C: { icon: "pin", label: "الدبّوسُ يسقط" },
  D: { icon: "online", label: "المفتاحُ يتّصل" },
};

export const MOTION_CSS = `
.ix .ix-root{transform-box:fill-box;transform-origin:50% 100%}
@keyframes ixDrive{0%{transform:translateX(-14%) scaleY(1)}35%{transform:translateX(0) scaleY(.94)}50%{transform:translateX(0) scaleY(1.04)}65%,100%{transform:translateX(0) scaleY(1)}}
.ix-anim.ix-A.ix-economy .ix-root{animation:ixDrive 1.6s cubic-bezier(.3,1.4,.5,1) infinite}
@keyframes ixRing{0%,60%,100%{transform:rotate(0)}10%{transform:rotate(14deg)}20%{transform:rotate(-12deg)}30%{transform:rotate(9deg)}40%{transform:rotate(-6deg)}50%{transform:rotate(3deg)}}
@keyframes ixGlow{0%,100%{opacity:.85}15%{opacity:1}}
.ix-anim.ix-B.ix-bell .ix-root{transform-origin:50% 12%;animation:ixRing 1.8s ease-in-out infinite,ixGlow 1.8s ease-in-out infinite}
@keyframes ixDrop{0%{transform:translateY(-55%);opacity:0}35%{transform:translateY(0);opacity:1}48%{transform:translateY(-10%)}60%,100%{transform:translateY(0)}}
.ix-anim.ix-C.ix-pin .ix-root{animation:ixDrop 1.7s cubic-bezier(.4,0,.2,1) infinite}
@keyframes ixKnob{0%,15%{transform:translateX(-16px)}45%,85%{transform:translateX(0)}100%{transform:translateX(-16px)}}
@keyframes ixTrack{0%,15%{opacity:.35}45%,85%{opacity:1}100%{opacity:.35}}
.ix-anim.ix-D.ix-online .ix-root > path:nth-child(1){animation:ixTrack 2.2s ease-in-out infinite}
.ix-anim.ix-D.ix-online .ix-root > path:nth-child(2){transform-box:fill-box;animation:ixKnob 2.2s cubic-bezier(.5,1.5,.5,1) infinite}
@media (prefers-reduced-motion: reduce){.ix-anim .ix-root,.ix-anim .ix-root > path{animation:none!important}}
`;
