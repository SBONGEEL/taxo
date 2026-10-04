/** «نقطة اللقاء» — ترحيبُ الكبتن عند كلِّ فتحة (TAXO 2.0، قرارُ المالك ٢٠٢٦-١٠-٠٤).
 *
 * **من التصميم لا من الذوق**: Claude Design «TAXO 2.0 - Welcome» (C0 · C1 · C2 ·
 * C3 · C4). القصةُ نفسُها من الجهة الأخرى — الكاميرا تتبعك أنت: سيارتُك تضيء في
 * العبدلي وتمضي على المسار الحقيقيّ، والراكبُ ينتظرك نابضاً في شارع الرينبو، ثمّ
 * يتكوّن الـX ويكتمل TAXO وتظهر «كبتن». **ومولّدُ المفاتيح (`tr`) منقولٌ من شيفرة
 * اللوحة**، مقصوصاً عند الإطار الأخير لأن الحلقةَ هناك للعرض.
 *
 * **وديناميكيٌّ بقرار المالك** (البندان ١٠ و١١):
 * - **داخلٌ**: تكوُّنُ الـX وحدَه ثمّ التطبيق — يظهر قليلاً ويمضي بنفسه.
 * - **غيرُ داخل**: أوّلَ فتحةٍ المقدّمةُ كاملة، وبعدها الـX وحدَه، ثمّ الشاشاتُ
 *   الثلاث («الرفيق قبل الطريق.» · «عمولة أقل بكثير من السوق.» · «وقتك بيدك.»)
 *   **بلا رقمٍ ولا نسبةٍ للعمولة، وبلا ذكرٍ لطريقة سحبٍ بعينها** — بنصِّ اللوحة.
 *   ثمّ «سجّل كشريك» يتمدّد ويصير بطاقةَ التسجيل، و«دخول» إلى شاشة الدخول.
 *
 * **وما لم يُبنَ من اللوحة — بعلّته، وينتظر تصحيحَه في Claude Design:**
 * - **«English»**: التطبيقُ عربيٌّ وحده (`DESIGN-DECISIONS` بند 18).
 * - **ما بعد «متابعة»**: خطواتُ التسجيل لم تُرسم بعد بما يطابق التطبيق (التأكيد
 *   والدولة والموافقة) — **فتُسلَّم البطاقةُ إلى شاشة التسجيل القائمة ومعها
 *   الرقم**، ولا نداءَ جديدَ ولا ترتيبَ جديد.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import { CountryPicker } from "@/components/CountryPicker";
import { useAuthCountry, usePhoneCountry } from "@/lib/config";
import { digitsOnly, looksComplete } from "@/lib/phone";

import "./welcome.css";

// ── من اللوحة حرفاً ─────────────────────────────────────────────────────────
const HD =
  "M122.45 359.03L125.67 360.81L128.9 361.99L131.89 362.64L135.69 363.12L139.24 363.01L142.71 362.72L151.83 361.28L158.27 360.5L171.72 357.17L173.79 357.47L178.99 358.79L194.4 365.45L198.93 366.7L201.02 366.77L204.74 365.92L212.49 366.66L224.24 368.04L227.26 368.56L231.95 370.45L249.95 387.94L250.76 389.26L257.01 395.46L258.46 397.41L260.38 402.18L262.55 426.13L265.9 438.02L265.79 438.96L266.16 442.18L259.24 443.04L256.35 442.96L252.97 441.81L245.82 437.59L243.91 436.94L241.62 436.89L238.83 437.75L236.97 438.86L233.32 441.72L230.71 444.54L225.56 449.11L222.84 450.66L219.23 451.48L215.27 451.97L211.71 451.21L202.86 449.98L201.51 449.85L199.49 449.98L196.49 451.25L189.74 454.89L186.59 456.23L182.49 457.71L178.01 458.92L177.82 459.94L178.02 461.13L190.48 467.45L199.96 471.14";
const P = HD.slice(1)
  .split("L")
  .map((s) => s.split(" ").map(Number) as [number, number]);
const CUM = P.reduce<number[]>(
  (acc, point, i) => (i === 0 ? [0] : [...acc, acc[i - 1] + Math.hypot(point[0] - P[i - 1][0], point[1] - P[i - 1][1])]),
  [],
);
const LEN = CUM[CUM.length - 1];
function at(f: number): [number, number] {
  const d = f * LEN;
  let i = 1;
  while (i < CUM.length - 1 && CUM[i] < d) i++;
  const t = (d - CUM[i - 1]) / (CUM[i] - CUM[i - 1] || 1);
  return [P[i - 1][0] + (P[i][0] - P[i - 1][0]) * t, P[i - 1][1] + (P[i][1] - P[i - 1][1]) * t];
}
const eio = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const S = P[0];
const E = P[P.length - 1];
const FX = 217.1;
const cam = (x: number, y: number, s: number) =>
  `translate(${(FX - s * x).toFixed(2)}px,${(360 - s * y).toFixed(2)}px) scale(${s})`;
const EZ = { o: "cubic-bezier(.2,.8,.2,1)", io: "cubic-bezier(.65,0,.35,1)" } as const;
type Pt = [number, string | number, (keyof typeof EZ)?];
const LB: Array<[string, number, number]> = [
  ["جبل عمّان", 159.5, 449.9],
  ["اللويبدة", 222.9, 402.4],
  ["العبدلي", 141, 353],
];

/** المقدّمةُ حتى إطارها الأخير — والـX وحدَه «من المرة الثانية». */
const INTRO_S = 4.4;
const BRIEF_MS = 800;
/** «تصل: نبضةٌ واهتزازة» — 2.8ث في اللوحة. */
const ARRIVE_MS = 2800;
const SEEN_KEY = "taxo.driver.welcome.seen";

/** **مولّدُ اللوحة (`tr`) مرّةً واحدةً لا حلقة**: نقاطٌ بعد `T` تُسقط، وتُثبَّت
 *  القيمةُ الأخيرة (`both`) — فيقف كلُّ شيءٍ في موضعه من إطار اللوحة الأخير. */
function buildIntro(T: number) {
  let css = "";
  let n = 0;
  const tr = (prop: string, pts: Pt[]) => {
    const name = `cw-k${n++}`;
    const p = pts.filter((pt) => pt[0] <= T).map((pt) => [...pt] as Pt);
    if (p[0][0] > 0) p.unshift([0, p[0][1]]);
    if (p[p.length - 1][0] < T) p.push([T, p[p.length - 1][1]]);
    css +=
      `@keyframes ${name}{` +
      p
        .map(([t, v, e]) => `${((t / T) * 100).toFixed(3)}%{${prop}:${v};animation-timing-function:${e ? EZ[e] : "linear"}}`)
        .join("") +
      "}";
    return `${name} ${T}s both`;
  };
  const t0 = 0.6;
  const dur = 2.2;
  const K = 14;
  const camPts: Pt[] = [
    [0, cam(S[0], S[1], 3)],
    [t0, cam(S[0], S[1], 3)],
  ];
  const disPts: Pt[] = [
    [0, "0%"],
    [t0, "0%"],
  ];
  const dashPts: Pt[] = [
    [0, 1],
    [t0, 1],
  ];
  for (let k = 1; k <= K; k++) {
    const e = eio(k / K);
    const p = at(e);
    const t = t0 + (dur * k) / K;
    camPts.push([t, cam(p[0], p[1], 3)]);
    disPts.push([t, `${(e * 100).toFixed(2)}%`]);
    dashPts.push([t, (1 - e).toFixed(4)]);
  }
  const cOp = tr("opacity", [[0, 0], [0.2, 0, "o"], [0.5, 1], [t0 + dur, 1, "o"], [t0 + dur + 0.25, 0]]);
  const cDis = tr("offset-distance", disPts);
  const draw = (a: number, b: number) => tr("transform", [[0, "scaleX(0)"], [a, "scaleX(0)", "o"], [b, "scaleX(1)"]]);
  const ping = (t: number) =>
    [
      tr("transform", [[0, "translate(-50%,-50%) scale(.3)"], [t, "translate(-50%,-50%) scale(.3)", "o"], [t + 1, "translate(-50%,-50%) scale(2.8)"]]),
      tr("opacity", [[0, 0], [t - 0.01, 0], [t, 0.85, "o"], [t + 1, 0]]),
    ].join(",");
  const anim = {
    cam: tr("transform", camPts),
    trailDash: tr("stroke-dashoffset", dashPts),
    trailOp: tr("opacity", [[0, 1], [2.85, 1, "o"], [3.5, 0], [6.8, 0]]),
    riderDot: tr("opacity", [[0, 0], [0.6, 0, "o"], [1.0, 1], [2.85, 1, "o"], [3.1, 0]]),
    car: `${cDis},${cOp}`,
    veil: tr("opacity", [[0, 1, "o"], [0.7, 0], [3.35, 0, "io"], [4.05, 0.84]]),
    ping1: ping(2.8),
    ping2: ping(3.05),
    xmark: [
      tr("transform", [[0, "scale(1)"], [3.25, "scale(1)", "io"], [3.75, "scale(2.4)"]]),
      tr("opacity", [[0, 0], [2.88, 0], [2.9, 1], [3.55, 1, "o"], [4.1, 0]]),
    ].join(","),
    bar1: draw(2.9, 3.2),
    bar2: draw(3.0, 3.3),
    word: [
      tr("opacity", [[0, 0], [3.55, 0, "o"], [4.05, 1]]),
      tr("letter-spacing", [[0, ".14em"], [3.55, ".14em", "o"], [4.3, "-.03em"]]),
    ].join(","),
    badge: [
      tr("opacity", [[0, 0], [3.85, 0, "o"], [4.25, 1]]),
      tr("transform", [[0, "translate(-50%,8px)"], [3.85, "translate(-50%,8px)", "o"], [4.3, "translate(-50%,0px)"]]),
    ].join(","),
  };
  return { css, anim };
}

/** «من المرة الثانية: لحظة تكوّن X فقط (0.8 ثانية)» — على الإطار الأخير. */
const BRIEF_CSS = `
@keyframes cw-bx{0%{transform:scale(1);opacity:1}37.5%{transform:scale(1);animation-timing-function:${EZ.io}}56.25%{opacity:1;animation-timing-function:${EZ.o}}68.75%{transform:scale(2.4)}87.5%,100%{transform:scale(2.4);opacity:0}}
@keyframes cw-bb1{0%{transform:scaleX(0);animation-timing-function:${EZ.o}}25%,100%{transform:scaleX(1)}}
@keyframes cw-bb2{0%,6.25%{transform:scaleX(0);animation-timing-function:${EZ.o}}31.25%,100%{transform:scaleX(1)}}
@keyframes cw-bw{0%,50%{opacity:0;letter-spacing:.14em;animation-timing-function:${EZ.o}}87.5%{opacity:1}100%{opacity:1;letter-spacing:-.03em}}
@keyframes cw-bbadge{0%,50%{opacity:0;transform:translate(-50%,8px);animation-timing-function:${EZ.o}}100%{opacity:1;transform:translate(-50%,0)}}
`;

/** سهمُ `arrow_back` من Material Symbols Rounded — شكلُه نفسُه بلا خطٍّ كامل. */
function ArrowBack() {
  return (
    <svg viewBox="0 -960 960 960" aria-hidden="true">
      <path d="M313-440l196 196q12 12 11.5 28T508-188q-12 11-28 11.5T452-188L188-452q-6-6-8.5-13t-2.5-15q0-8 2.5-15t8.5-13l264-264q11-11 27.5-11t28.5 11q12 12 12 28.5T508-715L313-520h447q17 0 28.5 11.5T800-480q0 17-11.5 28.5T760-440H313Z" />
    </svg>
  );
}

function seenBefore(): boolean {
  try {
    return localStorage.getItem(SEEN_KEY) === "1";
  } catch {
    return false;
  }
}
function markSeen(): void {
  try {
    localStorage.setItem(SEEN_KEY, "1");
  } catch {
    /* تخزينٌ محجوب: تُعاد المقدّمةُ كاملةً في الفتحة التالية — لا عطب */
  }
}

function useStageScale(): number {
  const [scale, setScale] = useState(1);
  useEffect(() => {
    const measure = () => setScale(Math.max(window.innerWidth / 390, window.innerHeight / 844));
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);
  return scale;
}

/** مواضعُ الخريطة في الشاشات الثلاث — من اللوحة: العبدلي، ثمّ اللويبدة، ثمّ البلد. */
const MAP_AT: Array<[number, number]> = [
  [-382.78, -1053.42],
  [-473.7, -907.2],
  [-789, -1026.9],
];

type Phase = "intro" | "brief" | "pages" | "entry" | "leaving";

export function Welcome({
  signedIn,
  onDone,
}: {
  signedIn: boolean;
  /** يُنادى حين ينتهي الترحيب — وإلى أين: التسجيلُ ومعه الرقم، أو الدخول. */
  onDone: (next?: { to: "/register" | "/login"; phone?: string }) => void;
}) {
  const scale = useStageScale();
  const [phase, setPhase] = useState<Phase>(() => (!signedIn && !seenBefore() ? "intro" : "brief"));
  const [page, setPage] = useState(0);
  const [pressed, setPressed] = useState(false);
  const [phone, setPhone] = useState("");
  const [next, setNext] = useState<{ to: "/register" | "/login"; phone?: string } | undefined>();
  const input = useRef<HTMLInputElement>(null);
  const drag = useRef<number | null>(null);
  const intro = useMemo(() => buildIntro(INTRO_S), []);

  const { country, countries, setCountry } = useAuthCountry();
  const { dialCode, nationalLength } = usePhoneCountry(country);

  useEffect(() => {
    if (phase !== "intro" && phase !== "brief") return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const span = reduced ? 0 : phase === "intro" ? INTRO_S * 1000 : BRIEF_MS;
    const timers: number[] = [];
    if (phase === "intro" && !reduced) {
      timers.push(window.setTimeout(() => navigator.vibrate?.(12), ARRIVE_MS));
    }
    timers.push(
      window.setTimeout(() => {
        if (phase === "intro") markSeen();
        setPhase(signedIn ? "leaving" : "pages");
      }, span + (signedIn ? 250 : 0)),
    );
    return () => timers.forEach((id) => window.clearTimeout(id));
  }, [phase, signedIn]);

  useEffect(() => {
    if (phase !== "leaving") return;
    const id = window.setTimeout(() => onDone(next), 300);
    return () => window.clearTimeout(id);
  }, [phase, onDone, next]);

  // **صاحبُ البصمة يُعرف بعد الإقلاع بلحظة** (`biometry` يُقاس ولا يُفترض) — فإن عُرف
  // والترحيبُ على أوّل صفحاته قبل أن يلمس شيئاً، يمضي كما يمضي الداخل
  useEffect(() => {
    if (signedIn && phase === "pages" && page === 0) setPhase("leaving");
  }, [signedIn, phase, page]);

  useEffect(() => {
    if (phase !== "entry") return;
    const id = window.setTimeout(() => input.current?.focus(), 520);
    return () => window.clearTimeout(id);
  }, [phase]);

  const leave = (target?: { to: "/register" | "/login"; phone?: string }) => {
    setNext(target);
    setPhase("leaving");
  };
  const skipIntro = () => {
    if (phase !== "intro") return;
    markSeen();
    setPhase(signedIn ? "leaving" : "pages");
  };
  const ready = dialCode !== null && looksComplete(phone, nationalLength);
  const onPages = phase === "pages" || phase === "entry";
  const [mx, my] = MAP_AT[page];

  return (
    <div
      className={[
        "cw",
        onPages ? `page-${page}` : "",
        phase === "entry" ? "is-card" : "",
        phase === "leaving" ? "is-leaving" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      onClick={phase === "intro" ? skipIntro : undefined}
      // **السحبُ لليسار ينقل إلى الشاشة التالية** (اللوحة) — واليمينُ يرجع
      onPointerDown={(event) => {
        if (phase === "pages") drag.current = event.clientX;
      }}
      onPointerUp={(event) => {
        if (phase !== "pages" || drag.current === null) return;
        const dx = event.clientX - drag.current;
        drag.current = null;
        if (dx < -40 && page < 2) setPage(page + 1);
        else if (dx > 40 && page > 0) setPage(page - 1);
      }}
      role="presentation"
    >
      <style>{phase === "intro" ? intro.css : phase === "brief" ? BRIEF_CSS : ""}</style>
      <div className="cw-stage" style={{ ["--cw-scale" as string]: String(scale) }}>
        {phase === "intro" ? (
          <div className="cw-cam" style={{ animation: intro.anim.cam }}>
            <img src="/welcome/amman-night.svg" alt="" />
            {LB.map(([text, x, y]) => (
              <span key={text} className="cw-maplabel" style={{ left: x, top: y }}>
                {text}
              </span>
            ))}
            <svg width="390" height="844" viewBox="0 0 390 844" style={{ position: "absolute", left: 0, top: 0, overflow: "visible", animation: intro.anim.trailOp }} aria-hidden="true">
              <path d={HD} fill="none" stroke="var(--ember)" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray="1 1" strokeDashoffset={1} style={{ animation: intro.anim.trailDash }} />
            </svg>
            {/* الراكبُ ينتظرك نابضاً في شارع الرينبو */}
            <span style={{ position: "absolute", left: E[0], top: E[1], width: 6, height: 6, borderRadius: "50%", border: ".45px solid #F2EFE8", boxSizing: "border-box", animation: "cw-pz 1.6s ease-out infinite" }} />
            <span style={{ position: "absolute", left: E[0], top: E[1], width: 5, height: 5, borderRadius: "50%", background: "#F2EFE8", border: ".9px solid #0E1013", boxSizing: "border-box", transform: "translate(-50%,-50%)", animation: intro.anim.riderDot }} />
            {/* سيارتُك بهالةٍ جمرية */}
            <div style={{ position: "absolute", left: 0, top: 0, width: 20, height: 20, borderRadius: "50%", background: "rgba(255,106,51,.14)", border: ".5px solid rgba(255,106,51,.6)", boxSizing: "border-box", offsetPath: `path('${HD}')`, offsetRotate: "auto", offsetAnchor: "center", offsetDistance: "0%", animation: intro.anim.car }} />
            <div style={{ position: "absolute", left: 0, top: 0, width: 10, height: 5.4, borderRadius: 2.2, background: "var(--ember)", border: ".7px solid #0E1013", boxSizing: "border-box", boxShadow: "0 .6px 1.6px rgba(0,0,0,.35)", offsetPath: `path('${HD}')`, offsetRotate: "auto", offsetAnchor: "center", offsetDistance: "0%", animation: intro.anim.car }}>
              <span style={{ position: "absolute", right: 1.3, top: 0.5, bottom: 0.5, width: 1.9, borderRadius: 0.7, background: "#0E1013" }} />
              <span style={{ position: "absolute", left: 0.9, top: 0.8, bottom: 0.8, width: 1.1, borderRadius: 0.5, background: "#0E1013", opacity: 0.55 }} />
            </div>
          </div>
        ) : (
          <>
            <img className="cw-map" src="/welcome/amman-night.svg" alt="" style={{ left: mx, top: my }} />
            <span className="cw-label" style={{ left: 95.7, top: 296 }}>جبل عمّان</span>
            <span className="cw-label" style={{ left: 285.9, top: 154 }}>اللويبدة</span>
          </>
        )}

        <div className="cw-veil-solid" style={phase === "intro" ? { animation: intro.anim.veil } : undefined} />
        <div className="cw-veil-grad" />
        <span className="cw-pin p1">اللويبدة</span>
        <span className="cw-pin p2">البلد</span>

        {phase === "intro" ? (
          <>
            <span className="cw-ping" style={{ position: "absolute", left: FX, top: 360, width: 40, height: 40, borderRadius: "50%", border: "2px solid #F2EFE8", boxSizing: "border-box", opacity: 0, animation: intro.anim.ping1 }} />
            <span className="cw-ping" style={{ position: "absolute", left: FX, top: 360, width: 40, height: 40, borderRadius: "50%", border: "2px solid var(--ember)", boxSizing: "border-box", opacity: 0, animation: intro.anim.ping2 }} />
          </>
        ) : null}

        <div className="cw-biglogo">
          {phase === "intro" || phase === "brief" ? (
            <div
              aria-hidden="true"
              style={{ position: "absolute", left: FX, top: 360, width: 0, height: 0, transformOrigin: "0 0", animation: phase === "intro" ? intro.anim.xmark : "cw-bx .8s both" }}
            >
              {(
                [
                  ["#F2EFE8", -50, phase === "intro" ? intro.anim.bar1 : "cw-bb1 .8s both"],
                  ["var(--ember)", 50, phase === "intro" ? intro.anim.bar2 : "cw-bb2 .8s both"],
                ] as const
              ).map(([color, rotate, animation]) => (
                <div key={rotate} style={{ position: "absolute", left: 0, top: 0, width: 26.67, height: 6.02, transform: `translate(-50%,-50%) rotate(${rotate}deg)` }}>
                  <div style={{ width: "100%", height: "100%", borderRadius: 3.44, background: color, transform: "scaleX(0)", animation }} />
                </div>
              ))}
            </div>
          ) : null}
          <div
            className="cw-word"
            dir="ltr"
            aria-label="TAXO"
            style={phase === "intro" ? { animation: intro.anim.word } : phase === "brief" ? { animation: "cw-bw .8s both" } : undefined}
          >
            TA
            <span className="cw-xb" aria-hidden="true">
              <span />
              <span />
            </span>
            O
          </div>
          <span
            className="cw-badge"
            style={phase === "intro" ? { animation: intro.anim.badge } : phase === "brief" ? { animation: "cw-bbadge .8s both" } : undefined}
          >
            كبتن
          </span>
        </div>

        {onPages ? (
          <>
            <div className={["cw-copy", "centered", page === 0 ? "" : "off-next"].join(" ")}>
              <h1>الرفيق قبل الطريق.</h1>
              <p>مثلٌ عربي: اختر رفيقك قبل أن تبدأ رحلتك. ونحن رفيقك من قبل أول رحلة.</p>
            </div>
            <div className={["cw-copy", page === 1 ? "" : page < 1 ? "off-prev" : "off-next"].join(" ")}>
              <div className="cw-pager" aria-hidden="true"><span /><span className="on" /><span /></div>
              <h1>عمولة أقل بكثير من السوق.</h1>
              <p>لأنك شريك في الطريق، لا مجرد سائق عليه.</p>
            </div>
            <div className={["cw-copy", page === 2 ? "" : "off-prev"].join(" ")}>
              <div className="cw-pager" aria-hidden="true"><span /><span /><span className="on" /></div>
              <h1>وقتك بيدك.</h1>
              <p>تختار باقتك وساعات عملك، وتسحب أرباحك من التطبيق.</p>
            </div>
          </>
        ) : null}
      </div>

      {onPages ? (
        <div className="cw-top">
          <span className="cw-mini" dir="ltr">
            TA
            <span className="cw-xb" aria-hidden="true">
              <span />
              <span />
            </span>
            O
          </span>
          <span className="cw-pill">كبتن</span>
          <span style={{ flex: 1 }} />
          {page === 1 ? (
            <button type="button" className="cw-textbtn" onClick={() => setPage(2)}>
              تخطَّ
            </button>
          ) : null}
        </div>
      ) : null}

      {phase === "intro" ? <span className="cw-skip">المس الشاشة للتخطّي</span> : null}

      {onPages && page < 2 ? (
        <div className="cw-actions">
          {page === 0 ? (
            <div className="cw-pager" aria-hidden="true"><span className="on" /><span /><span /></div>
          ) : null}
          <button type="button" className="cw-ember" onClick={() => setPage(page + 1)}>
            <span>التالي</span>
            <ArrowBack />
          </button>
          {page === 0 ? (
            <button type="button" className="cw-textbtn" style={{ fontSize: 14 }} onClick={() => setPage(2)}>
              تخطَّ
            </button>
          ) : null}
        </div>
      ) : null}

      {onPages && page === 2 ? (
        <>
          <button type="button" className="cw-login" onClick={() => phase === "pages" && leave({ to: "/login" })}>
            دخول
          </button>
          <div
            className={["cw-cta", pressed ? "is-pressed" : ""].filter(Boolean).join(" ")}
            role={phase === "pages" ? "button" : undefined}
            tabIndex={phase === "pages" ? 0 : -1}
            onClick={() => {
              if (phase !== "pages") return;
              setPressed(true);
              setPhase("entry");
            }}
          >
            <div className="cw-cta-label">
              <span>سجّل كشريك</span>
              <ArrowBack />
            </div>
            <form
              className="cw-card"
              onSubmit={(event) => {
                event.preventDefault();
                if (ready) leave({ to: "/register", phone });
              }}
            >
              <div className="cw-grab" aria-hidden="true" />
              <h2>رقم هاتفك</h2>
              <p className="cw-sub">نرسل لك رمز تحقق لتبدأ تسجيلك كشريك.</p>
              <div className="cw-picker">
                <CountryPicker country={country} countries={countries} onChange={setCountry} />
              </div>
              <label className="cw-field">
                <span className="cw-dial">+{dialCode ?? ""}</span>
                <span className="cw-sep" aria-hidden="true" />
                <input
                  ref={input}
                  name="phone"
                  inputMode="tel"
                  autoComplete="tel-national"
                  aria-label="رقم الهاتف"
                  value={phone}
                  disabled={dialCode === null}
                  maxLength={nationalLength + 4}
                  onChange={(event) => setPhone(digitsOnly(event.target.value))}
                />
              </label>
              <button type="submit" className="cw-go" disabled={!ready}>
                متابعة
              </button>
              <p className="cw-foot">بعدها: بياناتك، ثم مركبتك ووثائقك.</p>
            </form>
          </div>
        </>
      ) : null}
    </div>
  );
}
