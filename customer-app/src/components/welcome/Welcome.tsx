/** «نقطة اللقاء» — ترحيبُ الراكب عند كلِّ فتحة، **وهو شاشةُ الإقلاع نفسُها** (TAXO 2.0، قرارُ المالك ٢٠٢٦-١٠-٠٤ و§٦٢/١ و/١٠).
 *
 * **من التصميم لا من الذوق**: Claude Design «TAXO 2.0 - Welcome» (R0 · R1) — مسارُ الكبتن الحقيقيُّ من العبدلي إلى شارع الرينبو،
 * والكاميرا، والتوقيتُ ومنحنياتُه منقولةٌ من شيفرة اللوحة نفسِها (`welcome.css` يقول كيف).
 *
 * **ثلاثةُ أطوارٍ ثمّ فرعان:**
 * - **أوّلَ فتحةٍ على الجهاز لمن لم يدخل**: المقدّمةُ كاملة (٤٫٢ث).
 * - **وما بعدها**: تكوُّنُ الـX وتجمّعُ الحروف **بإيقاع المقدّمة نفسِه** (١٫٤ث) **ثمّ وقفةٌ على الشعار مكتملاً** — **كان ٠٫٨ث ثمّ يذوب
 *   فلا تُرى الحركة** (عطبُ §٦٢/٥)، فصار حدّاً أدنى يُرى فيه.
 * - **ثمّ ينتظر الإقلاع** إن لم يكتمل — وحالُ الشبكة مرسومةٌ عليه (`lib/splash.ts`): **هو شاشةُ الإقلاع**، فلا شاشةَ قبله ولا بعده.
 * - **داخلٌ ⇒ يذوب وحدَه** · **غيرُ داخل ⇒ «أهلاً وسهلاً» وزرّان: «حساب جديد» و«دخول»** (§٦١/٤ و§٦٢/١١) إلى شاشتيهما.
 * - **«تقليلُ الحركة»**: الإطارُ الأخيرُ مباشرة (`welcome.css`) — **والوقفةُ نفسُها باقية** فيُرى ولا يومض.
 *
 * **ويتبع مظهرَ التطبيق** (§٦٢/٨): رُسم بالحجر للراكب، **وفي الداكن يُرسم بإسفلت الهوية وخريطة الليل** — لا شاشةَ بمظهرٍ غير مظهر
 * صاحبها. **و«كلُّ فتحة» إقلاعٌ لا عودةٌ من الخلفية**: رجوعٌ من واتساب في منتصف رحلةٍ لا يُقابَل بشاشةٍ تحجبها.
 */

import { useEffect, useLayoutEffect, useState } from "react";

import { removeBootFrame, retrySplash, splashText, useSplashStatus } from "@/lib/splash";
import { useTheme } from "@/lib/theme";

import "@/taxo2";
import "./welcome.css";

// ── من اللوحة حرفاً ─────────────────────────────────────────────────────────
// مسارُ الكبتن الفعليّ من العبدلي إلى شارع الرينبو — إحداثياتُ إطار 390×844
const HD =
  "M122.45 359.03L125.67 360.81L128.9 361.99L131.89 362.64L135.69 363.12L139.24 363.01L142.71 362.72L151.83 361.28L158.27 360.5L171.72 357.17L173.79 357.47L178.99 358.79L194.4 365.45L198.93 366.7L201.02 366.77L204.74 365.92L212.49 366.66L224.24 368.04L227.26 368.56L231.95 370.45L249.95 387.94L250.76 389.26L257.01 395.46L258.46 397.41L260.38 402.18L262.55 426.13L265.9 438.02L265.79 438.96L266.16 442.18L259.24 443.04L256.35 442.96L252.97 441.81L245.82 437.59L243.91 436.94L241.62 436.89L238.83 437.75L236.97 438.86L233.32 441.72L230.71 444.54L225.56 449.11L222.84 450.66L219.23 451.48L215.27 451.97L211.71 451.21L202.86 449.98L201.51 449.85L199.49 449.98L196.49 451.25L189.74 454.89L186.59 456.23L182.49 457.71L178.01 458.92L177.82 459.94L178.02 461.13L190.48 467.45L199.96 471.14";
const LABELS: Array<[string, number, number]> = [
  ["جبل عمّان", 159.5, 449.9],
  ["اللويبدة", 222.9, 402.4],
  ["العبدلي", 141, 353],
];
/** طولُ المقدّمة حتى إطارها الأخير — ما بعده في اللوحة رجوعٌ إلى أوّل الحلقة. */
const INTRO_MS = 4200;
/** **تكوُّنُ الـX وتجمّعُ الحروف بإيقاع المقدّمة** (٢٫٧ث ← ٤٫١ث فيها) — كان ٠٫٨ث فيمضي قبل أن يُرى (§٦٢/٥). */
const BRIEF_MS = 1400;
/** **الوقفةُ على الشعار مكتملاً** قبل أن يمضي — حدُّ العرض الأدنى بعد الحركة، **وهي نفسُها مع «تقليل الحركة»**. */
const HOLD_MS = 600;
/** الذوبانُ — `welcome.css` (`.rw.is-leaving`). */
const LEAVE_MS = 350;
/** «اللقاء: نبضتان واهتزازةٌ خفيفةٌ واحدة» — 2.6ث في اللوحة. */
const MEET_MS = 2600;
const SEEN_KEY = "taxo.welcome.seen";

type Phase = "intro" | "brief" | "hold" | "welcome" | "leaving";
export type WelcomeNext = "/login" | "/register";

/** سهمُ `arrow_back` من Material Symbols Rounded — شكلُه نفسُه بلا خطٍّ كامل. وفي الواجهة العربية يشير يساراً: «إلى الأمام». */
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

function reducedMotion(): boolean {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** قياسُ المسرح: إطارُ اللوحة 390×844 **يُغطّي** الشاشة كما تُغطّيها الخريطة. */
function useStageScale(): number {
  const [scale, setScale] = useState(() => Math.max(window.innerWidth / 390, window.innerHeight / 844));
  useEffect(() => {
    const measure = () => setScale(Math.max(window.innerWidth / 390, window.innerHeight / 844));
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);
  return scale;
}

export function Welcome({
  booted,
  signedIn,
  returning,
  reopened = false,
  onDone,
}: {
  /** `/config` والجلسةُ وصلا — **وقبله يبقى الترحيبُ شاشةَ الإقلاع**. */
  booted: boolean;
  /** داخلٌ بعد الإقلاع ⇒ يمضي بنفسه. */
  signedIn: boolean;
  /** **ما يُعرف قبل الإقلاع**: رمزٌ محفوظٌ أو بصمةٌ مسلَّحة — يختار الطورَ الأوّل وحدَه (المقدّمةُ لمن لم يدخل قطّ). */
  returning: boolean;
  /** عودةٌ من «الدخول» أو «التسجيل» بسهم الرجوع ⇒ «أهلاً وسهلاً» مباشرة بلا حركة. */
  reopened?: boolean;
  onDone: (next?: WelcomeNext) => void;
}) {
  const scale = useStageScale();
  const { dark } = useTheme();
  const [phase, setPhase] = useState<Phase>(() =>
    reopened ? "welcome" : !returning && !seenBefore() ? "intro" : "brief",
  );
  const [next, setNext] = useState<WelcomeNext | undefined>();
  const splash = useSplashStatus();

  // **يحلّ محلَّ إطار الإقلاع في الإطار نفسِه** — قبل الرسم لا بعده، فلا ومضةَ بينهما
  useLayoutEffect(() => removeBootFrame(), []);

  // **المقدّمةُ والـX يمضيان بأنفسهما** — والمدّةُ نفسُها مكتوبةٌ هنا وفي CSS؛ و`animationend` لا يُعتمد عليه مع «تقليل الحركة»
  useEffect(() => {
    if (phase !== "intro" && phase !== "brief") return;
    const reduced = reducedMotion();
    const span = reduced ? 0 : phase === "intro" ? INTRO_MS : BRIEF_MS;
    const timers: number[] = [];
    if (phase === "intro" && !reduced) {
      // اهتزازةٌ خفيفةٌ واحدة لحظةَ اللقاء — حيث يتيحها الجهاز، وبلا شكوى حيث لا
      timers.push(window.setTimeout(() => navigator.vibrate?.(12), MEET_MS));
    }
    timers.push(
      window.setTimeout(() => {
        if (phase === "intro") markSeen();
        setPhase("hold");
      }, span),
    );
    return () => timers.forEach((id) => window.clearTimeout(id));
  }, [phase]);

  // **الوقفةُ ثمّ الفرع — ولا فرعَ قبل الإقلاع**: الترحيبُ باقٍ على الشعار وحالُ الشبكة تحته حتى يصل `/config` والجلسة
  const [held, setHeld] = useState(false);
  useEffect(() => {
    if (phase !== "hold") return;
    const id = window.setTimeout(() => setHeld(true), HOLD_MS);
    return () => window.clearTimeout(id);
  }, [phase]);
  useEffect(() => {
    if (phase !== "hold" || !held || !booted) return;
    setPhase(signedIn ? "leaving" : "welcome");
  }, [phase, held, booted, signedIn]);

  // **صاحبُ البصمة يُعرف بعد الإقلاع بلحظة** — فإن عُرف والترحيبُ على «أهلاً وسهلاً» قبل أن يلمس شيئاً، يمضي كما يمضي الداخل
  useEffect(() => {
    if (signedIn && phase === "welcome" && !reopened) setPhase("leaving");
  }, [signedIn, phase, reopened]);

  useEffect(() => {
    if (phase !== "leaving") return;
    const id = window.setTimeout(() => onDone(next), LEAVE_MS);
    return () => window.clearTimeout(id);
  }, [phase, onDone, next]);

  const skip = () => {
    if (phase !== "intro") return;
    markSeen();
    setPhase("hold");
  };
  const go = (to: WelcomeNext) => {
    if (phase !== "welcome") return;
    setNext(to);
    setPhase("leaving");
  };

  const animating = phase === "intro" ? "rw-intro" : phase === "brief" ? "rw-brief" : "";
  const settled = phase === "welcome" || (phase === "leaving" && next !== undefined);
  const waiting = phase === "hold" && held && !booted && splash.status;

  return (
    <div
      className={["t2", "rw", animating, settled ? "is-settled" : "", phase === "leaving" ? "is-leaving" : ""]
        .filter(Boolean)
        .join(" ")}
      onClick={phase === "intro" ? skip : undefined}
      role="presentation"
    >
      <div className="rw-stage" style={{ ["--rw-scale" as string]: String(scale) }}>
        <div className="rw-cam">
          <img src={dark ? "/welcome/amman-night.svg" : "/welcome/amman-day.svg"} alt="" />
          {LABELS.map(([text, x, y]) => (
            <span key={text} className="rw-label" style={{ left: x, top: y }}>
              {text}
            </span>
          ))}
          {phase === "intro" ? (
            <>
              <svg className="rw-trail" width="390" height="844" viewBox="0 0 390 844" aria-hidden="true">
                <path d={HD} fill="none" stroke="var(--rw-trail)" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" pathLength={1} />
                <path d={HD} fill="none" stroke="var(--t2-accent)" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round" pathLength={1} />
              </svg>
              <div className="rw-car" style={{ offsetPath: `path('${HD}')` }}>
                <span />
                <span />
              </div>
            </>
          ) : null}
        </div>

        {/* **صنفٌ واحدٌ لا «static» معه**: كان `rw-veil static` — و`.static` صنفُ Tailwind (`position: static`) يغلب
            `position: absolute` فينهار الغطاءُ إلى صفرٍ وتظهر الخريطةُ بكامل حدّتها بعد المقدّمة (قِيس بالأنماط المحسوبة، ٢٠٢٦-١٠-٠٥) */}
        <div className="rw-veil" />

        {phase === "intro" ? (
          <>
            <span className="rw-halo" />
            <span className="rw-dot" />
            <span className="rw-ping p1" />
            <span className="rw-ping p2" />
          </>
        ) : null}

        <div className="rw-logo-layer">
          {phase === "intro" || phase === "brief" ? (
            <div className="rw-xmark" aria-hidden="true">
              <span><i /></span>
              <span><i /></span>
            </div>
          ) : null}
          <div className="rw-word" dir="ltr" aria-label="TAXO">
            TA
            <span className="rw-xb" aria-hidden="true">
              <span />
              <span />
            </span>
            O
          </div>
        </div>

        {settled ? (
          <div className="rw-copy">
            <h1 className="rw-rise d1">أهلاً وسهلاً</h1>
            <p className="rw-origin rw-rise d2">حللتَ أهلاً، ووطئتَ سهلاً.</p>
            <p className="rw-explain rw-rise d3">جئتَ بين أهلك، وطريقك سهل — هكذا نريد أن تكون كل رحلة.</p>
          </div>
        ) : null}
      </div>

      {/* **حالُ الإقلاع على الترحيب نفسِه** — ثلاثةُ نصوصٍ لثلاثةِ أشياءَ تُعرف، والرمزُ لما لا يُعرف سببُه */}
      {waiting && splash.status ? (
        <div className="rw-status" role="status">
          <p>{splashText(splash.status)}</p>
          {splash.code ? <p className="rw-status-code" dir="ltr">{splash.code}</p> : null}
          {splash.status !== "slow" ? (
            <button type="button" onClick={retrySplash}>
              إعادة المحاولة
            </button>
          ) : null}
        </div>
      ) : null}

      {/* **ذكرُ الخريطة ما دامت معروضة** — شرطُ الرخصة لا زينة (§61-أ، `welcome.css`) */}
      <span className="rw-credit" dir="ltr">
        © OpenStreetMap · Copernicus DEM · Open-Meteo
      </span>

      {phase === "intro" ? <span className="rw-skip">المس الشاشة للتخطّي</span> : null}

      {settled ? (
        <div className="rw-actions rw-rise">
          <button type="button" className="rw-btn primary" onClick={() => go("/register")}>
            <span>حساب جديد</span>
            <ArrowBack />
          </button>
          <button type="button" className="rw-btn secondary" onClick={() => go("/login")}>
            دخول
          </button>
        </div>
      ) : null}
    </div>
  );
}
