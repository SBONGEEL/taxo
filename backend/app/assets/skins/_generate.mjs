/** مولّدُ رسومات المركبات — **قالبٌ واحدٌ لا ستَّ عشرةَ رسمةً بيد**.
 *
 * **والعلّةُ شرطُ المالك نفسُه**: «أسلوبٌ موحّدٌ صارم — نفسُ المنظور والنِسب
 * ومصدرِ الإضاءة عبر المجموعة كلِّها». ورسمُ ستَّ عشرةَ مركبةً واحدةً واحدةً
 * يجعل الاتساقَ **ذاكرةً تُستدعى**، وهي تُنسى عند السابعة — والقالبُ يجعله
 * **بناءً**: زاويةُ الإضاءة رقمٌ واحدٌ في ملفٍّ واحد، والنِسبُ مشتقّةٌ من
 * هيكلٍ واحد. وهي قاعدةُ المشروع نفسُها: **ما لا يُطبَّق يُنسى**.
 *
 * **ولا يُشغَّل في وقت التشغيل**: يُشغَّل بيدٍ فيكتب `*.svg` و`manifest.json`،
 * **وهي المُودَعة**. فالخادمُ يخدم ملفاتٍ ساكنةً لا ناتجَ سكربت، ولا تدخل
 * `node` صورةَ الخلفية.
 *
 *     node backend/app/assets/skins/_generate.mjs
 *
 * **والمُخرَجُ يمرّ بقائمة سماح `skin_artwork.sanitize_svg`** — لا `script`
 * ولا `use` ولا `image` ولا مرجعَ خارجيّ. و`tests/test_skin_artwork.py`
 * يقيس ذلك على **كلِّ ملفٍّ في المجلَّد**، فرسمةٌ تُضاف يوماً بيدٍ وتخالف
 * القائمةَ تُسقط المجموعة.
 */

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));

// ══════════════════════════════════════════════════ ألوانٌ وحساب

const hex = (n) => Math.max(0, Math.min(255, Math.round(n))).toString(16).padStart(2, "0");
const parse = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
const mix = (c, target, t) => {
  const [r, g, b] = parse(c);
  const [tr, tg, tb] = target;
  return `#${hex(r + (tr - r) * t)}${hex(g + (tg - g) * t)}${hex(b + (tb - b) * t)}`;
};
const lighten = (c, t) => mix(c, [255, 255, 255], t);
const darken = (c, t) => mix(c, [0, 0, 0], t);

/** **الإضاءةُ النسبيّة** (BT.709) — تُقاس ولا تُقدَّر بالعين.
 *
 *  **والعلّةُ قِيست في أوّل تصيير**: «فحمُ الليل» و«سُهيلُ الليل» يُرسمان على
 *  سطحٍ داكن (`--sur` = `#0d1014`)، **وحرفُهما كان `darken(body, .68)`** —
 *  أي أدكنَ من الهيكل الداكن أصلاً، فيذوب الحرفُ في الخلفية وتضيع السيارة.
 *  وهي قاعدةُ المشروع نفسُها: **لونٌ ثابتٌ يذوب في إحدى السمتين مهما حُسن
 *  اختيارُه** — فالحرفُ يُشتقّ من الهيكل لا يُكتب رقماً واحداً للمجموعة. */
const luma = (c) => {
  const [r, g, b] = parse(c);
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
};
/** حرفُ الهيكل: أدكنُ منه إن كان فاتحاً، **وأفتحُ منه إن كان داكناً**. */
const edge = (c) => (luma(c) < 0.34 ? lighten(c, 0.30) : darken(c, 0.66));

/** **مصدرُ الإضاءة رقمٌ واحدٌ للمجموعة كلِّها** — أعلى-يسار، ٢٥° عن العمود.
 *  تغييرُه هنا يغيّر ستَّ عشرةَ مركبةً معاً، وهذا هو الغرض. */
const LIGHT = { top: 0.34, upper: 0.14, lower: 0.30, bottom: 0.52 };

/** زجاجٌ داكنٌ واحدٌ للمجموعة — سيارةٌ بزجاجٍ أفتحَ تبدو من طقمٍ آخر. */
const GLASS = { top: "#39424e", mid: "#1b222b", bottom: "#0d1116" };

// ══════════════════════════════════════════════════ الهياكلُ الستة
//
// **النِسبُ مشتقّةٌ من هيكلٍ واحد**: الأرضُ عند 184، ومركزا العجلتين 104 و300،
// وقاعُ الهيكل 150 — فما يتغيّر بين هيكلٍ وآخر هو **الخطُّ العلويُّ وحده**.
// وبهذا لا تستطيع مركبةٌ أن تقف على أرضٍ أخرى أو تحمل عجلاتٍ في غير موضعها.

const GROUND = 184;
const SILL = 150;
const FRONT_X = 104;
const REAR_X = 300;

/** الخطُّ العلويُّ لكلِّ هيكل — من مقدّمة الصادم إلى مؤخّرته. */
const SHELLS = {
  sedan: {
    tire: 38,
    top:
      "M 16 140 C 16 126 24 117 42 113 L 114 99 L 160 60 " +
      "L 248 60 L 298 100 L 372 106 C 386 108 391 117 391 133 L 391 150",
    glass: "M 126 97 L 166 67 L 242 67 L 286 97 Z",
    pillar: 202,
    belt: "M 30 116 L 116 100 L 300 102 L 380 108",
    lampFront: "M 18 118 L 40 114 L 41 126 L 19 129 Z",
    lampRear: "M 389 120 L 370 118 L 369 130 L 388 132 Z",
  },
  coupe: {
    tire: 38,
    top:
      "M 16 141 C 16 127 24 118 42 114 L 108 101 L 152 66 " +
      "C 176 55 232 55 262 70 L 314 103 L 374 108 C 387 110 391 118 391 134 L 391 150",
    glass: "M 122 99 L 160 71 C 180 62 226 62 250 74 L 294 99 Z",
    pillar: 196,
    belt: "M 30 117 L 110 101 L 316 105 L 382 110",
    lampFront: "M 18 119 L 42 114 L 43 126 L 19 130 Z",
    lampRear: "M 389 121 L 368 119 L 367 131 L 388 133 Z",
  },
  hatch: {
    tire: 36,
    top:
      "M 18 139 C 18 125 26 116 44 112 L 112 98 L 156 60 " +
      "L 268 60 L 320 108 C 336 112 346 118 348 134 L 348 150",
    glass: "M 124 96 L 162 67 L 262 67 L 306 100 Z",
    pillar: 208,
    belt: "M 32 115 L 114 99 L 314 104 L 344 116",
    lampFront: "M 20 117 L 44 113 L 45 125 L 21 128 Z",
    lampRear: "M 347 122 L 330 118 L 328 130 L 345 134 Z",
  },
  suv: {
    tire: 44,
    top:
      "M 14 132 C 14 118 22 109 40 105 L 106 92 L 146 50 " +
      "L 286 50 L 330 96 L 378 102 C 390 104 394 112 394 128 L 394 150",
    glass: "M 118 90 L 152 57 L 280 57 L 318 92 Z",
    pillar: 216,
    belt: "M 28 108 L 108 93 L 324 98 L 386 104",
    lampFront: "M 16 110 L 42 106 L 43 119 L 17 122 Z",
    lampRear: "M 392 114 L 372 112 L 371 125 L 391 127 Z",
  },
  van: {
    tire: 38,
    top:
      "M 14 130 C 14 112 22 100 38 94 L 92 60 C 100 48 112 42 128 42 " +
      "L 366 42 C 382 42 392 52 392 68 L 392 150",
    glass: "M 104 92 L 132 56 L 360 56 L 360 92 Z",
    pillar: 200,
    belt: "M 26 100 L 98 92 L 366 94",
    lampFront: "M 16 106 L 40 100 L 42 113 L 18 118 Z",
    lampRear: "M 390 100 L 372 100 L 372 116 L 390 116 Z",
  },
  pickup: {
    tire: 44,
    top:
      "M 14 132 C 14 118 22 109 40 105 L 104 92 L 144 50 " +
      "L 244 50 L 252 96 L 258 96 L 258 78 L 388 78 " +
      "C 393 78 394 84 394 92 L 394 150",
    glass: "M 116 90 L 150 57 L 238 57 L 244 90 Z",
    pillar: 194,
    belt: "M 28 108 L 106 93 L 250 96",
    lampFront: "M 16 110 L 42 106 L 43 119 L 17 122 Z",
    lampRear: "M 392 92 L 374 92 L 374 106 L 392 106 Z",
  },
};

/** قاعُ الهيكل مع قوسَي العجلتين — **مشتقٌّ لا مكتوب**، فلا تنحرف عجلةٌ عن أرضها. */
function underside(shell) {
  // **قوسُ العجلة نصفُ قطرِ الإطار + ٦** — فيعلو الإطارَ بهامشٍ ثابتٍ في
  // المجموعة كلِّها. و`sweep-flag = 0` هو ما يجعل القوسَ يعلو **إلى داخل
  // الهيكل**: في فضاء SVG المحورُ الرأسيُّ إلى أسفل، فـ`1` يرسم القوسَ
  // **تحت** الخطّ — أي حفرةً في الأرض بدل بيتٍ للعجلة.
  const arch = shell.tire + 6;
  return (
    ` L ${REAR_X + arch} ${SILL}` +
    ` A ${arch} ${arch} 0 0 0 ${REAR_X - arch} ${SILL}` +
    ` L ${FRONT_X + arch} ${SILL}` +
    ` A ${arch} ${arch} 0 0 0 ${FRONT_X - arch} ${SILL}` +
    ` L 16 ${SILL} Z`
  );
}

// ══════════════════════════════════════════════════ العجلة

function wheel(cx, cy, r, id) {
  const rim = (r * 0.66).toFixed(1);
  const dish = (r * 0.58).toFixed(1);
  const hub = (r * 0.17).toFixed(1);
  const spokeLen = (r * 0.5).toFixed(1);
  const spokes = [];
  for (let i = 0; i < 5; i += 1) {
    const a = (i * 72 - 90) * (Math.PI / 180);
    spokes.push(
      `<line x1="${cx}" y1="${cy}" x2="${(cx + Math.cos(a) * spokeLen).toFixed(1)}"` +
        ` y2="${(cy + Math.sin(a) * spokeLen).toFixed(1)}"/>`,
    );
  }
  return (
    `<g>` +
    `<circle cx="${cx}" cy="${cy}" r="${r}" fill="url(#tire-${id})"/>` +
    `<circle cx="${cx}" cy="${cy}" r="${(r * 0.82).toFixed(1)}" fill="#0a0d11" opacity=".55"/>` +
    `<circle cx="${cx}" cy="${cy}" r="${rim}" fill="url(#rim-${id})"/>` +
    `<circle cx="${cx}" cy="${cy}" r="${dish}" fill="#11161c" opacity=".45"/>` +
    `<g stroke="url(#rim-${id})" stroke-width="${(r * 0.13).toFixed(1)}" stroke-linecap="round">` +
    spokes.join("") +
    `</g>` +
    `<circle cx="${cx}" cy="${cy}" r="${hub}" fill="url(#rim-${id})"/>` +
    `<circle cx="${cx}" cy="${cy}" r="${(r * 0.07).toFixed(1)}" fill="#0b0e11"/>` +
    `</g>`
  );
}

// ══════════════════════════════════════════════════ رسمةُ المتجر

function storeSvg(car) {
  const shell = SHELLS[car.shell];
  const id = car.key;
  const body = car.body;
  const cy = GROUND - shell.tire;
  const path = shell.top + underside(shell);

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 210" width="512" height="512" preserveAspectRatio="xMidYMid meet">
<title>${car.name}</title>
<defs>
<linearGradient id="body-${id}" x1="0.18" y1="0" x2="0.62" y2="1">
<stop offset="0" stop-color="${lighten(body, LIGHT.top)}"/>
<stop offset="0.34" stop-color="${lighten(body, LIGHT.upper)}"/>
<stop offset="0.62" stop-color="${darken(body, LIGHT.lower)}"/>
<stop offset="1" stop-color="${darken(body, LIGHT.bottom)}"/>
</linearGradient>
<linearGradient id="glass-${id}" x1="0.1" y1="0" x2="0.7" y2="1">
<stop offset="0" stop-color="${GLASS.top}"/>
<stop offset="0.45" stop-color="${GLASS.mid}"/>
<stop offset="1" stop-color="${GLASS.bottom}"/>
</linearGradient>
<linearGradient id="tire-${id}" x1="0.2" y1="0" x2="0.8" y2="1">
<stop offset="0" stop-color="#3a4048"/>
<stop offset="0.5" stop-color="#1b1f25"/>
<stop offset="1" stop-color="#0a0c0f"/>
</linearGradient>
<linearGradient id="rim-${id}" x1="0.15" y1="0" x2="0.85" y2="1">
<stop offset="0" stop-color="${lighten(car.rim, 0.5)}"/>
<stop offset="0.45" stop-color="${car.rim}"/>
<stop offset="1" stop-color="${darken(car.rim, 0.55)}"/>
</linearGradient>
<radialGradient id="shade-${id}" cx="0.5" cy="0.5" r="0.5">
<stop offset="0" stop-color="#000000" stop-opacity="0.55"/>
<stop offset="0.62" stop-color="#000000" stop-opacity="0.20"/>
<stop offset="1" stop-color="#000000" stop-opacity="0"/>
</radialGradient>
<linearGradient id="gloss-${id}" x1="0" y1="0" x2="1" y2="0">
<stop offset="0" stop-color="#ffffff" stop-opacity="0"/>
<stop offset="0.28" stop-color="#ffffff" stop-opacity="0.52"/>
<stop offset="0.72" stop-color="#ffffff" stop-opacity="0.30"/>
<stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
</linearGradient>
<linearGradient id="floor-${id}" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="#000000" stop-opacity="0"/>
<stop offset="1" stop-color="#000000" stop-opacity="0.42"/>
</linearGradient>
<clipPath id="clip-${id}"><path d="${path}"/></clipPath>
<clipPath id="glassclip-${id}"><path d="${shell.glass}"/></clipPath>
</defs>

<ellipse cx="204" cy="${GROUND + 4}" rx="182" ry="15" fill="url(#shade-${id})"/>

${wheel(FRONT_X, cy, shell.tire, id)}
${wheel(REAR_X, cy, shell.tire, id)}

<path d="${path}" fill="url(#body-${id})"/>

<!-- **كلُّ ما يُرسم على الهيكل يُقصّ به** — وبغير هذا القصِّ يطفو المصباحُ
     خارجَ حرف الهيكل، ويقف عمودُ السقف فوقه عصاً معلَّقة. وقد وقع الاثنان
     مقيسَين في أوّل تصيير، ولم يظهرا في المصدر بحال. -->
<g clip-path="url(#clip-${id})">
<path d="M 0 ${SILL - 34} L 400 ${SILL - 40} L 400 ${SILL + 6} L 0 ${SILL + 6} Z" fill="url(#floor-${id})"/>
<ellipse cx="150" cy="${SILL - 66}" rx="180" ry="30" fill="#ffffff" opacity="0.10"/>
<path d="${shell.belt}" fill="none" stroke="url(#gloss-${id})" stroke-width="3.2" stroke-linecap="round"/>
<path d="${shell.lampFront}" fill="#f4f7fb" opacity="0.95"/>
<path d="${shell.lampRear}" fill="#e5534b" opacity="0.95"/>
<rect x="${shell.pillar + 26}" y="${SILL - 42}" width="20" height="5" rx="2.5" fill="${darken(body, 0.52)}"/>
<rect x="${shell.pillar - 50}" y="${SILL - 42}" width="20" height="5" rx="2.5" fill="${darken(body, 0.52)}"/>
</g>

<path d="${shell.glass}" fill="url(#glass-${id})"/>
<g clip-path="url(#glassclip-${id})">
<rect x="${shell.pillar}" y="30" width="7" height="90" fill="${darken(body, 0.3)}"/>
<path d="M 96 40 L 150 40 L 250 130 L 196 130 Z" fill="#ffffff" opacity="0.09"/>
</g>
<path d="${shell.glass}" fill="none" stroke="${edge(body)}" stroke-width="2.4" stroke-linejoin="round" opacity="0.75"/>
<path d="${path}" fill="none" stroke="${edge(body)}" stroke-width="2.2" stroke-linejoin="round"/>
</svg>
`;
}

// ══════════════════════════════════════════════════ رسمةُ الخريطة
//
// **علويّةٌ مبسّطةٌ بنفس ألوان رسمة المتجر** — والشرطُ «مقروءةٌ عند ٣٢ بكسل»:
// فالتفاصيلُ تسقط ويبقى **الظلُّ الخارجيُّ وحدٌّ داكن**. وبلا الحدِّ تذوب
// السيارةُ الداكنةُ في خريطةٍ داكنة وتختفي — وذلك عطبٌ لا يُرى إلا على خريطة.
//
// **ومربَّعُ الإطار مركزُه مركزُ الدوران**: العلامةُ تدور مع الاتجاه، ورسمةٌ
// إطارُها غيرُ مركزيٍّ تدور حول نقطةٍ خارجَ السيارة فتقفز.

const TOPS = {
  sedan: { w: 40, nose: 10, tail: 8, cabin: [30, 68] },
  coupe: { w: 39, nose: 13, tail: 9, cabin: [32, 66] },
  hatch: { w: 39, nose: 10, tail: 5, cabin: [30, 70] },
  suv: { w: 45, nose: 8, tail: 6, cabin: [28, 72] },
  van: { w: 45, nose: 6, tail: 4, cabin: [24, 78] },
  pickup: { w: 44, nose: 8, tail: 4, cabin: [28, 58] },
};

function mapSvg(car) {
  const t = TOPS[car.shell];
  const id = car.key;
  const body = car.body;
  const x0 = 50 - t.w / 2;
  const x1 = 50 + t.w / 2;
  const [c0, c1] = t.cabin;

  // الهيكل: أنفٌ مستدقٌّ وذيلٌ أقلُّ استدقاقاً — فيُقرأ الاتجاهُ عند ٣٢ بكسل
  const shell =
    `M ${x0 + t.nose} 8 ` +
    `Q 50 4 ${x1 - t.nose} 8 ` +
    `L ${x1} 26 L ${x1} 74 L ${x1 - t.tail} 92 ` +
    `Q 50 96 ${x0 + t.tail} 92 ` +
    `L ${x0} 74 L ${x0} 26 Z`;

  const bed =
    car.shell === "pickup"
      ? `<rect x="${x0 + 3}" y="60" width="${t.w - 6}" height="30" rx="3" fill="${darken(body, 0.5)}"/>`
      : "";

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="128" height="128" preserveAspectRatio="xMidYMid meet">
<title>${car.name}</title>
<defs>
<linearGradient id="m-body-${id}" x1="0" y1="0.1" x2="1" y2="0.9">
<stop offset="0" stop-color="${lighten(body, LIGHT.top)}"/>
<stop offset="0.45" stop-color="${body}"/>
<stop offset="1" stop-color="${darken(body, LIGHT.lower)}"/>
</linearGradient>
<linearGradient id="m-glass-${id}" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="${GLASS.top}"/>
<stop offset="1" stop-color="${GLASS.bottom}"/>
</linearGradient>
</defs>
<path d="${shell}" fill="#000000" opacity="0.22" transform="translate(2.5,3)"/>
<!-- **هالةٌ ثم حرفٌ داكن** — لا حرفٌ واحد: علامةٌ داكنةُ الهيكل بحرفٍ داكن
     **تختفي على خريطةٍ داكنة**، وفاتحةٌ بحرفٍ فاتحٍ تختفي على فاتحة. والهالةُ
     الفاتحةُ تحت الحرفِ الداكن تُقرأ على السمتين معاً — وهي ما تفعله تسمياتُ
     الخرائط نفسُها. **ولا تتبع سمةَ التطبيق**: الخريطةُ ليست CSS. -->
<path d="${shell}" fill="none" stroke="#f2f0eb" stroke-width="7" stroke-linejoin="round" opacity="0.62"/>
<path d="${shell}" fill="url(#m-body-${id})" stroke="#0b0e11" stroke-width="2.6" stroke-linejoin="round"/>
${bed}
<path d="M ${x0 + 6} ${c0} L ${x1 - 6} ${c0} L ${x1 - 9} ${c0 + 11} L ${x0 + 9} ${c0 + 11} Z" fill="url(#m-glass-${id})"/>
<rect x="${x0 + 6}" y="${c0 + 13}" width="${t.w - 12}" height="${c1 - c0 - 22}" rx="3" fill="${lighten(body, 0.1)}"/>
<path d="M ${x0 + 9} ${c1 - 8} L ${x1 - 9} ${c1 - 8} L ${x1 - 6} ${c1} L ${x0 + 6} ${c1} Z" fill="url(#m-glass-${id})"/>
<rect x="${x0 - 4.5}" y="${c0 + 1}" width="5" height="8" rx="2.5" fill="${darken(body, 0.4)}"/>
<rect x="${x1 - 0.5}" y="${c0 + 1}" width="5" height="8" rx="2.5" fill="${darken(body, 0.4)}"/>
<rect x="${x0 + 4}" y="9" width="8" height="4.5" rx="2" fill="#f4f7fb" opacity="0.95"/>
<rect x="${x1 - 12}" y="9" width="8" height="4.5" rx="2" fill="#f4f7fb" opacity="0.95"/>
<rect x="${x0 + 4}" y="87" width="8" height="4" rx="2" fill="#e5534b" opacity="0.95"/>
<rect x="${x1 - 12}" y="87" width="8" height="4" rx="2" fill="#e5534b" opacity="0.95"/>
</svg>
`;
}

// ══════════════════════════════════════════════════ المجموعة
//
// **الأسماءُ عربيةٌ لها شخصية** — لا أرقامَ ولا رموز: كبتنٌ يقتني «تاجَ
// الصحراء» يذكره، ومن يقتني «مركبة ٧» لا يذكر شيئاً.
//
// **والتوزيعُ على العادية والمميزة** كما طُلب. `rare`/`legendary` **بلا رسمٍ
// اليوم** — ويُقال ذلك ولا يُشحن كتالوجٌ يعد بندرةٍ لا رسمَ لها.

const CARS = [
  // ── العادية: تُوهب ولا تُباع، وتُنشر على الخريطة الحرّة ──────────────
  { key: "sedan-ash", name: "الرماديُّ الأمين", rarity: "common", shell: "sedan", body: "#8b949e", rim: "#c9d1d9",
    note: "مركبةُ الهدية والبديلِ المنشور — أوّلُ ما يراه كبتنٌ لم يشترِ شيئاً" },
  { key: "sedan-pearl", name: "لؤلؤةُ الصباح", rarity: "common", shell: "sedan", body: "#e8e6df", rim: "#b8bec7" },
  { key: "sedan-graphite", name: "فحمُ الليل", rarity: "common", shell: "sedan", body: "#3a4149", rim: "#9aa4ae" },
  { key: "hatch-olive", name: "زيتونةُ الشمال", rarity: "common", shell: "hatch", body: "#6b7a4a", rim: "#b9c0c8" },
  { key: "hatch-cobalt", name: "زُرقةُ العقبة", rarity: "common", shell: "hatch", body: "#2f5f9e", rim: "#c2cad3" },
  { key: "sedan-sand", name: "رملُ البادية", rarity: "common", shell: "sedan", body: "#c8a97a", rim: "#b5bcc4" },
  { key: "suv-clay", name: "طينُ البتراء", rarity: "common", shell: "suv", body: "#a8603f", rim: "#aeb6bf" },
  { key: "van-linen", name: "كتّانُ المدينة", rarity: "common", shell: "van", body: "#dcdad2", rim: "#a9b0b8" },

  // ── المميزة: تُباع، ومنها ما لا يُنشر قبل القبول ─────────────────────
  { key: "coupe-gold", name: "النسرُ الذهبي", rarity: "premium", shell: "coupe", body: "#c9971f", rim: "#f0e2b0" },
  { key: "suv-crown", name: "تاجُ الصحراء", rarity: "premium", shell: "suv", body: "#8f6b2a", rim: "#e6d6a8" },
  { key: "coupe-crimson", name: "جمرةُ الغروب", rarity: "premium", shell: "coupe", body: "#a32b28", rim: "#d8dee6" },
  { key: "suv-emerald", name: "زمرّدةُ الوادي", rarity: "premium", shell: "suv", body: "#1d6b52", rim: "#cfd7e0" },
  { key: "sedan-midnight", name: "سُهيلُ الليل", rarity: "premium", shell: "sedan", body: "#1e2a44", rim: "#d4dae2" },
  { key: "pickup-copper", name: "نُحاسُ الجنوب", rarity: "premium", shell: "pickup", body: "#9b5a2b", rim: "#c8cfd8" },
  { key: "coupe-silver", name: "فضّةُ العاصمة", rarity: "premium", shell: "coupe", body: "#aeb7c0", rim: "#eef1f5" },
  // **نسائيةٌ بالوسم لا باللون وحده**: `is_feminine` صفةُ صفٍّ يضبطها المشرف،
  // والرسمةُ هنا تُهيّئها ولا تقرّرها
  { key: "suv-rose", name: "وردةُ الشام", rarity: "premium", shell: "suv", body: "#b2517c", rim: "#f1dbe6", feminine: true },
];

// ══════════════════════════════════════════════════ الكتابة

mkdirSync(HERE, { recursive: true });
const manifest = [];
for (const car of CARS) {
  writeFileSync(join(HERE, `${car.key}-store.svg`), storeSvg(car), "utf8");
  writeFileSync(join(HERE, `${car.key}-map.svg`), mapSvg(car), "utf8");
  manifest.push({
    key: car.key,
    name: car.name,
    rarity: car.rarity,
    shell: car.shell,
    body: car.body,
    ...(car.feminine ? { feminine: "1" } : {}),
    ...(car.note ? { note: car.note } : {}),
  });
}
writeFileSync(
  join(HERE, "manifest.json"),
  JSON.stringify(manifest, null, 2) + "\n",
  "utf8",
);
console.log(`✓ ${CARS.length} مركبةً × ٢ رسمة + manifest.json في ${HERE}`);
