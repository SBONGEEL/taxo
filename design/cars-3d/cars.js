// استوديو سيارات TAXO — **مصدرٌ واحدٌ لكلِّ صورة سيارة** (أمرُ المالك ٢٠٢٦-١١-٢٠ الثامن).
// نماذجُ أصيلةٌ تُبنى بالمعادلات (لا طرازَ حقيقيّاً ولا شعار)، وتُصوَّر بـthree.js (MIT) بإضاءة استوديو على خلفيّةٍ شفّافة.
import * as THREE from "./node_modules/three/build/three.module.js";

const ORANGE = { day: 0xf05a28, night: 0xff6a33 };
const PLUM = { day: 0x9c2c6e, night: 0xf08cc0 };

// ─────────────────────────────────────────────── مواصفاتُ الفئات (بالمتر، تقريبيّة، أصيلة)
// top: نقاطُ خطِّ أعلى الهيكل [u, y] — u من -1 (الخلف) إلى +1 (الأمام)
// cabin: [uFrontBase, uRoofStart, uRoofEnd, uRearBase, roofY]
export const SPECS = {
  economy: { L: 4.45, W: 1.82, clear: 0.17, R: 0.353, wb: 0.60, pw: 5, belt: 0.94,
    top: [[-1, 0.80], [-0.86, 0.90], [-0.6, 0.93], [0.25, 0.95], [0.6, 0.84], [0.86, 0.71], [1, 0.6]],
    cabin: [0.36, 0.10, -0.30, -0.66, 1.45], body: "white" },
  comfort: { L: 4.75, W: 1.86, clear: 0.16, R: 0.369, wb: 0.62, pw: 5, belt: 0.95,
    top: [[-1, 0.82], [-0.86, 0.92], [-0.6, 0.95], [0.25, 0.96], [0.6, 0.85], [0.86, 0.72], [1, 0.6]],
    cabin: [0.34, 0.06, -0.36, -0.74, 1.42], body: "white", darkRims: true },
  vip: { L: 5.05, W: 1.9, clear: 0.15, R: 0.385, wb: 0.64, pw: 5, belt: 0.98,
    top: [[-1, 0.86], [-0.86, 0.95], [-0.6, 0.98], [0.25, 0.99], [0.6, 0.88], [0.86, 0.76], [1, 0.64]],
    cabin: [0.32, 0.04, -0.34, -0.66, 1.47], body: "black" },
  hatchback: { L: 4.1, W: 1.8, clear: 0.17, R: 0.342, wb: 0.64, pw: 7, belt: 0.95,
    top: [[-1, 0.92], [-0.6, 0.95], [0.25, 0.96], [0.6, 0.86], [0.86, 0.74], [1, 0.63]],
    cabin: [0.34, 0.08, -0.62, -0.96, 1.5], body: "white" },
  suv: { L: 4.7, W: 1.92, clear: 0.24, R: 0.407, wb: 0.62, pw: 7, belt: 1.12,
    top: [[-1, 1.08], [-0.6, 1.11], [0.25, 1.12], [0.62, 1.05], [0.88, 0.96], [1, 0.86]],
    cabin: [0.36, 0.12, -0.70, -0.97, 1.72], body: "white", cladding: true },
  family: { L: 4.95, W: 1.92, clear: 0.17, R: 0.374, wb: 0.66, pw: 8, belt: 1.05,
    top: [[-1, 1.02], [-0.6, 1.05], [0.3, 1.05], [0.66, 0.98], [0.9, 0.86], [1, 0.76]],
    cabin: [0.50, 0.24, -0.82, -0.985, 1.80], body: "white" },
  van: { L: 5.3, W: 2.0, clear: 0.19, R: 0.385, wb: 0.68, pw: 9, belt: 1.1,
    top: [[-1, 1.08], [-0.6, 1.1], [0.42, 1.1], [0.74, 1.02], [0.92, 0.9], [1, 0.8]],
    cabin: [0.60, 0.36, -0.90, -0.99, 2.05], body: "white" },
  // **لمتجر المركبات** (العاديّة والمميّزة): كوبيه منخفضةٌ ببابين، وبيك أب بقمرةٍ قصيرةٍ وصندوق
  coupe: { L: 4.4, W: 1.86, clear: 0.14, R: 0.374, wb: 0.60, pw: 5, belt: 0.88,
    top: [[-1, 0.76], [-0.86, 0.86], [-0.6, 0.89], [0.25, 0.9], [0.6, 0.79], [0.86, 0.67], [1, 0.57]],
    cabin: [0.30, 0.0, -0.36, -0.80, 1.30], body: "white" },
  pickup: { L: 5.1, W: 1.94, clear: 0.24, R: 0.407, wb: 0.66, pw: 7, belt: 1.12,
    top: [[-1, 1.1], [-0.6, 1.12], [0.25, 1.12], [0.62, 1.05], [0.88, 0.96], [1, 0.86]],
    cabin: [0.40, 0.18, -0.10, -0.20, 1.80], body: "white", cladding: true, bed: true },
  city_taxi: { base: "economy", sign: true },
  women: { base: "economy", accent: "plum" },
};

function spec(key) {
  const s = SPECS[key];
  return s.base ? { ...SPECS[s.base], ...s } : s;
}

// ─────────────────────────────────────────────── أدواتُ الشكل
function profile(points, u) {
  // **استيفاءٌ تكعيبيٌّ رتيب** (Fritsch–Carlson) بين نقاط [u, y] — منحنىً متّصلُ الميل بلا تموّج
  const n = points.length;
  if (u <= points[0][0]) return points[0][1];
  if (u >= points[n - 1][0]) return points[n - 1][1];
  const d = [];
  for (let i = 0; i < n - 1; i++) d.push((points[i + 1][1] - points[i][1]) / (points[i + 1][0] - points[i][0]));
  const m = [d[0]];
  for (let i = 1; i < n - 1; i++) m.push(d[i - 1] * d[i] <= 0 ? 0 : (d[i - 1] + d[i]) / 2);
  m.push(d[n - 2]);
  for (let i = 0; i < n - 1; i++) {
    if (d[i] === 0) { m[i] = 0; m[i + 1] = 0; continue; }
    const a = m[i] / d[i], b = m[i + 1] / d[i];
    const h = a * a + b * b;
    if (h > 9) { const t = 3 / Math.sqrt(h); m[i] = t * a * d[i]; m[i + 1] = t * b * d[i]; }
  }
  let i = 0;
  while (u > points[i + 1][0]) i++;
  const [x0, y0] = points[i];
  const [x1, y1] = points[i + 1];
  const hh = x1 - x0;
  const t = (u - x0) / hh;
  const t2 = t * t, t3 = t2 * t;
  return (2 * t3 - 3 * t2 + 1) * y0 + (t3 - 2 * t2 + t) * hh * m[i] + (-2 * t3 + 3 * t2) * y1 + (t3 - t2) * hh * m[i + 1];
}

const spow = (v, e) => Math.sign(v) * Math.pow(Math.abs(v), e);

function makeBody(s) {
  const half = s.L / 2;
  const wheelX = s.wb * half; // مراكزُ العجلات على ±wheelX
  const archR = s.R * 1.1;
  const widthAt = (u) => {
    const base = Math.pow(Math.max(0, 1 - Math.pow(Math.abs(u), s.pw)), 1 / s.pw);
    const taper = u > 0 ? 1 - 0.06 * u * u : 1 - 0.03 * u * u;
    return (s.W / 2) * base * taper;
  };
  const topAt = (u) => profile(s.top, u);
  const bottomAt = (u) => {
    const x = u * half;
    let b = s.clear + (Math.abs(u) > 0.82 ? (Math.abs(u) - 0.82) * 0.5 : 0);
    for (const cx of [wheelX, -wheelX]) {
      const d = (x - cx) / archR;
      if (Math.abs(d) < 1) b = Math.max(b, s.R + archR * Math.sqrt(1 - d * d) * 0.98);
    }
    return b;
  };
  // نقطةٌ على سطح الهيكل: u على الطول، θ حول المقطع (0 = الجانب +z، π/2 = الأعلى)
  const point = (u, theta) => {
    const w = widthAt(u);
    const top = topAt(u);
    // **الشكلُ من قاعدةٍ اسميّة، والأقواسُ قصٌّ فوقها** — فلا تنتفخ الواجهةُ فوق العجلات
    const bot = s.clear + (Math.abs(u) > 0.8 ? (Math.abs(u) - 0.8) * 0.45 : 0);
    const yc = (top + bot) / 2;
    const h = (top - bot) / 2;
    const c = Math.cos(theta);
    const sn = Math.sin(theta);
    const n = 2 / 5.2;
    const z = w * spow(c, n) * (1 - 0.1 * Math.max(0, sn) * Math.max(0, sn)) * (1 - 0.07 * Math.max(0, -sn) * Math.max(0, -sn));
    const y = Math.max(yc + h * spow(sn, n), Math.min(bottomAt(u), top - 0.05));
    return new THREE.Vector3(u * half, y, z);
  };
  return { point, widthAt, topAt, bottomAt, wheelX, archR, half };
}

function loft(fn, nu, nv, closedV = true) {
  // سطحٌ من مقاطع: fn(i/nu, j/nv) → Vector3
  const pos = [];
  const idx = [];
  const cols = closedV ? nv : nv + 1;
  for (let i = 0; i <= nu; i++) {
    for (let j = 0; j < cols; j++) {
      const p = fn(i / nu, j / nv);
      pos.push(p.x, p.y, p.z);
    }
  }
  for (let i = 0; i < nu; i++) {
    for (let j = 0; j < (closedV ? nv : nv); j++) {
      const a = i * cols + j;
      const b = i * cols + ((j + 1) % cols);
      const c = (i + 1) * cols + j;
      const d = (i + 1) * cols + ((j + 1) % cols);
      idx.push(a, c, b, b, c, d);
    }
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

function cosineU(t) {
  // توزيعٌ أكثفُ عند الطرفين (الأنف والذيل)
  return -Math.cos(t * Math.PI);
}

// ─────────────────────────────────────────────── بناءُ السيارة
export function buildCar(key, opts = {}) {
  const s = spec(key);
  const theme = opts.theme ?? "day";
  const accentHex = (s.accent === "plum" ? PLUM : ORANGE)[theme];
  const bodyHex = opts.bodyColor ?? (s.body === "black" ? 0x16181d : 0xf3f4f6);
  const dark = new THREE.Color(bodyHex).getHSL({ h: 0, s: 0, l: 0 }).l < 0.35;
  const group = new THREE.Group();
  const B = makeBody(s);

  const bodyMat = new THREE.MeshPhysicalMaterial({
    color: bodyHex, roughness: dark ? 0.16 : 0.2, metalness: dark ? 0.4 : 0.08,
    clearcoat: 1, clearcoatRoughness: 0.06,
  });
  const glassMat = new THREE.MeshPhysicalMaterial({
    color: 0x0b0d12, roughness: 0.06, metalness: 0.3, clearcoat: 1, clearcoatRoughness: 0.03,
  });
  const accentMat = new THREE.MeshStandardMaterial({
    color: accentHex, emissive: accentHex, emissiveIntensity: theme === "night" ? 1.4 : 0.55, roughness: 0.35, metalness: 0.2,
  });
  const lightMat = new THREE.MeshBasicMaterial({ color: new THREE.Color(accentHex).multiplyScalar(theme === "night" ? 2.6 : 1.7), toneMapped: false });
  const tireMat = new THREE.MeshStandardMaterial({ color: 0x15161a, roughness: 0.85 });
  const rimMat = new THREE.MeshPhysicalMaterial({
    color: dark || s.darkRims ? 0x2b2e35 : 0xf2f3f5, roughness: 0.2, metalness: 0.4, clearcoat: 0.6,
  });
  const wellMat = new THREE.MeshBasicMaterial({ color: 0x050608 });

  // الهيكل
  const body = new THREE.Mesh(loft((a, b) => B.point(cosineU(a), b * Math.PI * 2), 120, 72), bodyMat);
  group.add(body);

  // إطارٌ سفليٌّ داكنٌ حول الأقواس والأسفل — هويّةُ الـSUV
  if (s.cladding) {
    const clad = new THREE.MeshStandardMaterial({ color: 0x1d1f24, roughness: 0.7, metalness: 0.05 });
    const g = loft((a, b) => {
      const p = B.point(cosineU(a) * 0.985, Math.PI + 0.42 + b * (Math.PI - 0.84));
      return new THREE.Vector3(p.x, p.y, p.z * 1.012);
    }, 120, 30, false);
    group.add(new THREE.Mesh(g, clad));
  }

  // صندوقُ البيك أب: أرضيّةٌ داكنةٌ غائرةٌ خلف القمرة
  if (s.bed) {
    const u0 = -0.93, u1 = -0.24;
    const y = B.topAt((u0 + u1) / 2);
    const bed = new THREE.Mesh(new THREE.BoxGeometry((u1 - u0) * B.half, 0.03, B.widthAt(-0.6) * 1.62),
      new THREE.MeshStandardMaterial({ color: 0x1b1d22, roughness: 0.8 }));
    bed.position.set(((u0 + u1) / 2) * B.half, y + 0.005, 0);
    group.add(bed);
  }

  // الزجاجُ والسقف (قبّةٌ زجاجيّةٌ داكنة)
  const [uF, uR1, uR2, uB, roofY] = s.cabin;
  const roofAt = (u) => {
    if (u >= uR1) return profile([[uR1, roofY], [uF, B.topAt(uF) - 0.02]], u > uF ? uF : u);
    if (u <= uR2) return profile([[uB, B.topAt(uB) - 0.02], [uR2, roofY]], u < uB ? uB : u);
    const t = (u - uR2) / (uR1 - uR2);
    return roofY + 0.015 * Math.sin(t * Math.PI);
  };
  const cab = loft((a, b) => {
    const u = uB + (uF - uB) * (0.5 - 0.5 * Math.cos(a * Math.PI));
    const base = B.topAt(u) - 0.05;
    const top = Math.max(roofAt(u), base + 0.012);
    const w = B.widthAt(u) * 0.84;
    const th = b * Math.PI; // نصفُ مقطع (الأعلى) من +z إلى -z
    const c = Math.cos(th);
    const sn = Math.sin(th);
    const n = 2 / 4.2;
    const z = w * spow(c, n) * (1 - 0.2 * sn);
    const y = base + (top - base) * spow(sn, n);
    return new THREE.Vector3(u * B.half, y, z);
  }, 90, 40, false);
  group.add(new THREE.Mesh(cab, glassMat));

  // العجلات
  const wheelGeoTire = new THREE.CylinderGeometry(s.R, s.R, 0.23, 48, 1, false);
  wheelGeoTire.rotateX(Math.PI / 2);
  const tireEdge = new THREE.TorusGeometry(s.R - 0.035, 0.035, 12, 48);
  const rimGeo = new THREE.CylinderGeometry(s.R * 0.74, s.R * 0.74, 0.02, 48);
  rimGeo.rotateX(Math.PI / 2);
  const rimDish = new THREE.SphereGeometry(s.R * 0.74, 32, 12, 0, Math.PI * 2, 0, 0.42);
  rimDish.rotateX(Math.PI / 2);
  const hubGeo = new THREE.CylinderGeometry(s.R * 0.16, s.R * 0.16, 0.03, 32);
  hubGeo.rotateX(Math.PI / 2);
  const wellGeo = new THREE.CircleGeometry(B.archR * 0.98, 48);
  const track = s.W / 2 - 0.125;
  for (const x of [B.wheelX, -B.wheelX]) {
    for (const side of [1, -1]) {
      const w = new THREE.Group();
      w.add(new THREE.Mesh(wheelGeoTire, tireMat));
      const e1 = new THREE.Mesh(tireEdge, tireMat); e1.position.z = 0.1; w.add(e1);
      const e2 = new THREE.Mesh(tireEdge, tireMat); e2.position.z = -0.1; w.add(e2);
      const rim = new THREE.Mesh(rimGeo, rimMat); rim.position.z = 0.115 * side; w.add(rim);
      const dish = new THREE.Mesh(rimDish, rimMat);
      dish.scale.set(1, 1, 0.12); dish.position.z = 0.115 * side; if (side < 0) dish.rotation.y = Math.PI; w.add(dish);
      const hub = new THREE.Mesh(hubGeo, accentMat); hub.position.z = 0.142 * side; w.add(hub);
      w.position.set(x, s.R, side * track);
      group.add(w);
      const well = new THREE.Mesh(wellGeo, wellMat);
      well.position.set(x, s.R + 0.02, side * (track - 0.13));
      if (side < 0) well.rotation.y = Math.PI;
      group.add(well);
    }
  }

  // شريطُ الضوء الأماميّ — يلتفّ حول الأنف
  const lightTheta = 0.62;
  const front = [];
  for (let i = 0; i <= 26; i++) front.push(B.point(0.80 + (i / 26) * 0.199, Math.PI - lightTheta));
  const frontR = [];
  for (let i = 26; i >= 0; i--) frontR.push(B.point(0.80 + (i / 26) * 0.199, lightTheta));
  const fpts = front.concat(frontR.slice(1)).map((p) => {
    const n = p.clone(); n.y += 0.004; n.x += 0.006; return n;
  });
  const frontCurve = new THREE.CatmullRomCurve3(fpts);
  group.add(new THREE.Mesh(new THREE.TubeGeometry(frontCurve, 160, 0.02, 10, false), lightMat));
  // **الوهجُ ملتصقٌ بالشريط** — غلافان شفّافان حوله، لا بقعةٌ على الأرض تُقرأ وسخاً على الخلفيّات الشفّافة
  for (const [r, o] of theme === "night" ? [[0.045, 0.32], [0.085, 0.12]] : [[0.04, 0.16]]) {
    group.add(new THREE.Mesh(new THREE.TubeGeometry(frontCurve, 160, r, 12, false), new THREE.MeshBasicMaterial({
      color: new THREE.Color(accentHex).multiplyScalar(1.4), transparent: true, opacity: o, depthWrite: false, toneMapped: false,
    })));
  }

  // ضوءٌ خلفيٌّ رفيع
  const rear = [];
  for (let i = 0; i <= 20; i++) rear.push(B.point(-0.86 - (i / 20) * 0.139, Math.PI - 0.7));
  const rearR = [];
  for (let i = 20; i >= 0; i--) rearR.push(B.point(-0.86 - (i / 20) * 0.139, 0.7));
  const rearMat = new THREE.MeshBasicMaterial({ color: new THREE.Color(0xd8322a).multiplyScalar(1.4), toneMapped: false });
  group.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(rear.concat(rearR.slice(1))), 120, 0.011, 8, false), rearMat));

  // الخطُّ البرتقاليُّ الرفيع على الجانبين
  for (const th of [0.32, Math.PI - 0.32]) {
    const pts = [];
    for (let i = 0; i <= 60; i++) {
      const u = -0.78 + (i / 60) * 1.5;
      const p = B.point(u, th);
      p.z += Math.sign(p.z) * 0.004;
      pts.push(p);
    }
    group.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 120, 0.0075, 8, false), accentMat));
  }

  // المرايا البرتقاليّة
  const mirrorGeo = new THREE.SphereGeometry(0.07, 24, 16);
  for (const side of [1, -1]) {
    const m = new THREE.Mesh(mirrorGeo, accentMat);
    const u = uF - 0.03;
    m.scale.set(1.25, 0.75, 0.6);
    m.position.set(u * B.half, B.topAt(u) + 0.02, side * (B.widthAt(u) * 0.8 + 0.06));
    group.add(m);
  }

  // لمسةُ السقف: زعنفةٌ صغيرةٌ برتقاليّة — أو لافتةُ تاكسي المدينة مضيئة
  if (s.sign) {
    const signGeo = new THREE.BoxGeometry(0.42, 0.13, 0.2, 4, 4, 4);
    const sign = new THREE.Mesh(signGeo, new THREE.MeshStandardMaterial({ color: accentHex, emissive: accentHex, emissiveIntensity: theme === "night" ? 1.5 : 0.6, roughness: 0.3 }));
    sign.position.set(((uR1 + uR2) / 2) * B.half, roofY + 0.07, 0);
    group.add(sign);
  } else {
    const fin = new THREE.Mesh(new THREE.SphereGeometry(0.09, 20, 12), accentMat);
    fin.scale.set(1.5, 0.45, 0.32);
    fin.position.set((uR2 + 0.02) * B.half, roofAt(uR2 + 0.02) - 0.005, 0);
    group.add(fin);
  }

  group.userData = { spec: s, accentHex, B };
  return group;
}

// ─────────────────────────────────────────────── المشهد والتصوير
function radialTexture(stops) {
  const c = document.createElement("canvas");
  c.width = c.height = 256;
  const g = c.getContext("2d");
  const grd = g.createRadialGradient(128, 128, 0, 128, 128, 128);
  for (const [o, col] of stops) grd.addColorStop(o, col);
  g.fillStyle = grd;
  g.fillRect(0, 0, 256, 256);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function envMap(renderer, theme, view) {
  const scene = new THREE.Scene();
  const room = new THREE.Mesh(new THREE.BoxGeometry(30, 16, 30), new THREE.MeshBasicMaterial({ color: theme === "night" ? 0x14161b : 0x3a3d44, side: THREE.BackSide }));
  room.position.y = 6;
  scene.add(room);
  const panel = (w, h, pos, rot, color, k) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: new THREE.Color(color).multiplyScalar(k), side: THREE.DoubleSide }));
    m.position.set(...pos);
    m.rotation.set(...rot);
    scene.add(m);
  };
  // **من الأعلى لا لوحةَ فوق الكاميرا**: كانت تنعكس مستطيلاً رماديّاً على السقف الزجاجيّ
  if (view === "top") panel(26, 3, [0, 13.5, -9], [Math.PI / 2, 0, 0], 0xffffff, 2.0);
  else panel(14, 6, [0, 13.5, 0], [Math.PI / 2, 0, 0], 0xffffff, theme === "night" ? 2.2 : 4.2);
  panel(10, 3, [0, 6, -14.5], [0, 0, 0], 0xffffff, theme === "night" ? 1.2 : 2.6);
  panel(3, 8, [14.5, 6, 0], [0, -Math.PI / 2, 0], 0xffffff, theme === "night" ? 1.0 : 2.4);
  panel(3, 8, [-14.5, 6, 4], [0, Math.PI / 2, 0], 0xffffff, theme === "night" ? 0.9 : 2.0);
  panel(8, 2, [6, 2, 14.5], [0, Math.PI, 0], theme === "night" ? 0xff6a33 : 0xffd9c8, theme === "night" ? 1.4 : 1.2);
  const pm = new THREE.PMREMGenerator(renderer);
  const rt = pm.fromScene(scene, 0.035);
  pm.dispose();
  return rt.texture;
}

let renderer = null;
const envCache = {};

export async function shoot({ key, view = "three-quarter", theme = "day", bodyColor, width = 1600, height = 1000 }) {
  if (!renderer) {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(1);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.22;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  }
  renderer.setSize(width, height, false);
  renderer.setClearColor(0x000000, 0);
  const scene = new THREE.Scene();
  scene.environment = envCache[theme + view] ??= envMap(renderer, theme, view);

  const car = buildCar(key, { theme, bodyColor });
  car.traverse((o) => { if (o.isMesh) { o.castShadow = true; } });
  scene.add(car);
  const s = car.userData.spec;
  const accent = car.userData.accentHex;

  const key1 = new THREE.DirectionalLight(0xffffff, theme === "night" ? 0.9 : 1.6);
  key1.position.set(2, 9, 3);
  key1.castShadow = true;
  key1.shadow.mapSize.set(2048, 2048);
  key1.shadow.radius = 9;
  key1.shadow.camera.left = -4; key1.shadow.camera.right = 4; key1.shadow.camera.top = 4; key1.shadow.camera.bottom = -4;
  scene.add(key1);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x333333, theme === "night" ? 0.35 : 0.8));

  // الظلُّ الناعم: ظلٌّ مُلقى + ظلٌّ ملامسٌ تحت الهيكل
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(14, 14), new THREE.ShadowMaterial({ opacity: theme === "night" ? 0.35 : 0.22 }));
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);
  const contact = new THREE.Mesh(new THREE.PlaneGeometry(s.L * 1.18, s.W * 1.45), new THREE.MeshBasicMaterial({
    map: radialTexture([[0, "rgba(0,0,0,0.55)"], [0.55, "rgba(0,0,0,0.28)"], [1, "rgba(0,0,0,0)"]]), transparent: true, depthWrite: false,
  }));
  contact.rotation.x = -Math.PI / 2;
  contact.position.y = 0.002;
  scene.add(contact);

  // الوهجُ البرتقاليُّ من الأضواء — على الأرض أمام الأنف، وهالةٌ حول الشريط
  const col = new THREE.Color(accent);
  const rgb = `${Math.round(col.r * 255)},${Math.round(col.g * 255)},${Math.round(col.b * 255)}`;
  const glowK = theme === "night" ? 0.55 : 0.18;
  const floorGlow = new THREE.Mesh(new THREE.PlaneGeometry(1.5, s.W * 1.25), new THREE.MeshBasicMaterial({
    map: radialTexture([[0, `rgba(${rgb},${glowK})`], [0.5, `rgba(${rgb},${glowK * 0.35})`], [1, `rgba(${rgb},0)`]]),
    transparent: true, depthWrite: false,
  }));
  floorGlow.rotation.x = -Math.PI / 2;
  floorGlow.position.set(s.L / 2 + 0.3, 0.004, 0);
  // الوهجُ على الأرض يُقرأ بقعةً على الخلفيّات الشفّافة — فلا يُضاف
  const halo = new THREE.Sprite(new THREE.SpriteMaterial({
    map: radialTexture([[0, `rgba(${rgb},${glowK * 0.9})`], [0.4, `rgba(${rgb},${glowK * 0.25})`], [1, `rgba(${rgb},0)`]]),
    transparent: true, depthWrite: false,
  }));
  halo.scale.set(s.W * 1.25, 0.55, 1);
  const B = car.userData.B;
  halo.position.copy(B.point(0.995, Math.PI / 2 + 0.0)).add(new THREE.Vector3(0.12, -0.05, 0));
  // الهالةُ القديمةُ أُزيلت: الوهجُ صار حول الشريط نفسِه

  let camera;
  if (view === "top") {
    const span = s.L / 2 + 0.35;
    camera = new THREE.OrthographicCamera(-span * (width / height), span * (width / height), span, -span, 0.1, 50);
    camera.position.set(0, 20, 0);
    camera.up.set(1, 0, 0);
    camera.lookAt(0, 0, 0);
  } else {
    camera = new THREE.PerspectiveCamera(20, width / height, 0.1, 100);
    const az = THREE.MathUtils.degToRad(-36);
    const d = 15.5;
    camera.position.set(Math.cos(az) * d, 3.6, Math.sin(az) * d);
    camera.lookAt(0.25, 0.62, 0);
  }
  renderer.render(scene, camera);
  const url = renderer.domElement.toDataURL("image/png");
  scene.traverse((o) => { if (o.geometry) o.geometry.dispose(); });
  return url;
}

window.TAXO_CARS = { shoot, SPECS };
window.TAXO_READY = true;
