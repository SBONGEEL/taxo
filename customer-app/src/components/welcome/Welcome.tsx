/** «نقطة اللقاء» — ترحيبُ الراكب عند كلِّ فتحة (TAXO 2.0، قرارُ المالك ٢٠٢٦-١٠-٠٤).
 *
 * **من التصميم لا من الذوق**: Claude Design «TAXO 2.0 - Welcome» (R0 · R1 · R2)
 * — مسارُ الكبتن الحقيقيُّ من العبدلي إلى شارع الرينبو، والكاميرا، والتوقيتُ
 * ومنحنياتُه منقولةٌ من شيفرة اللوحة نفسِها (`welcome.css` يقول كيف).
 *
 * **وديناميكيٌّ بقرار المالك** (البندان ١٠ و١١):
 * - **داخلٌ**: تكوُّنُ الـX وحدَه ثمّ التطبيق — يظهر قليلاً ويمضي بنفسه.
 * - **غيرُ داخل**: أوّلَ فتحةٍ على الجهاز المقدّمةُ كاملة، وبعدها الـX وحدَه
 *   («من المرة الثانية: لحظة تكوّن X فقط»)، ثمّ «أهلاً وسهلاً» وزرُّ «تفضّل»
 *   الذي يتمدّد ويصير بطاقةَ الدخول.
 * - **«تقليلُ الحركة»**: الإطارُ الأخيرُ مباشرة (`welcome.css`).
 *
 * **و«كلُّ فتحة» إقلاعٌ لا عودةٌ من الخلفية**: الترحيبُ يُرسم مرّةً لكلِّ تحميلٍ
 * للتطبيق. ورجوعٌ من واتساب في منتصف رحلةٍ لا يُقابَل بشاشةٍ تحجب الرحلة.
 *
 * **وما لم يُبنَ من اللوحة — بعلّته، وينتظر تصحيحَه في Claude Design:**
 * - **«English»**: التطبيقُ عربيٌّ وحده — زرٌّ لا بابَ خلفه.
 * - **«بالمتابعة توافق على الشروط وسياسة الخصوصية»**: موافقةٌ مفترَضة، والمالكُ
 *   استبدلها بمربّعٍ يُضغط في التسجيل (٢٠٢٦-٠٩-٠٥، `PolicyConsent`) — فلا تُعاد.
 * - **ما بعد «متابعة»**: خطواتُ الدخول والتسجيل لم تُرسم بعد بما يطابق ما يطلبه
 *   التطبيق (التأكيد، والدولة، والموافقة، والبصمة) — **فتُسلَّم البطاقةُ إلى شاشة
 *   الدخول القائمة ومعها الرقم**. ولا نداءَ جديدَ ولا ترتيبَ جديد: الدخولُ يقع
 *   هناك بطلبه نفسِه.
 */

import { useEffect, useRef, useState } from "react";

import { useAuthCountry, usePhoneCountry } from "@/lib/config";
import { COUNTRY_LABEL, digitsOnly, looksComplete } from "@/lib/phone";

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
const BRIEF_MS = 800;
/** «اللقاء: نبضتان واهتزازةٌ خفيفةٌ واحدة» — 2.6ث في اللوحة. */
const MEET_MS = 2600;
const SEEN_KEY = "taxo.welcome.seen";

type Phase = "intro" | "brief" | "welcome" | "entry" | "leaving";

/** سهمُ `arrow_back` من Material Symbols Rounded — شكلُه نفسُه، بلا تحميل خطٍّ
 *  كاملٍ لأيقونةٍ واحدة. وفي الواجهة العربية يشير يساراً: «إلى الأمام». */
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

/** قياسُ المسرح: إطارُ اللوحة 390×844 **يُغطّي** الشاشة كما تُغطّيها الخريطة. */
function useStageScale(): number {
  const [scale, setScale] = useState(1);
  useEffect(() => {
    const measure = () =>
      setScale(Math.max(window.innerWidth / 390, window.innerHeight / 844));
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);
  return scale;
}

export function Welcome({
  signedIn,
  onDone,
}: {
  /** داخلٌ ⇒ يظهر قليلاً ويمضي. وغيرُ داخل ⇒ يقود إلى الخطوات. */
  signedIn: boolean;
  /** يُنادى حين ينتهي الترحيب — ومعه الرقمُ إن كُتب في البطاقة. */
  onDone: (phone?: string) => void;
}) {
  const scale = useStageScale();
  const [phase, setPhase] = useState<Phase>(() =>
    !signedIn && !seenBefore() ? "intro" : "brief",
  );
  const [pressed, setPressed] = useState(false);
  const [phone, setPhone] = useState("");
  const input = useRef<HTMLInputElement>(null);

  const { country, countries, setCountry } = useAuthCountry();
  const { dialCode, nationalLength } = usePhoneCountry(country);

  // **المقدّمةُ والـX يمضيان بأنفسهما** — ولا مؤقّتَ ثانٍ يخالف ما في CSS:
  // المدّةُ نفسُها مكتوبةٌ هنا وهناك، و`animationend` لا يُعتمد عليه مع
  // «تقليل الحركة» (المدّةُ 0.001ث قد لا تُطلق حدثاً في بعض المحرّكات).
  useEffect(() => {
    if (phase !== "intro" && phase !== "brief") return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const span = reduced ? 0 : phase === "intro" ? INTRO_MS : BRIEF_MS;
    const timers: number[] = [];
    if (phase === "intro" && !reduced) {
      // اهتزازةٌ خفيفةٌ واحدة لحظةَ اللقاء — حيث يتيحها الجهاز، وبلا شكوى حيث لا
      timers.push(window.setTimeout(() => navigator.vibrate?.(12), MEET_MS));
    }
    timers.push(
      window.setTimeout(() => {
        if (phase === "intro") markSeen();
        if (signedIn) {
          // **داخلٌ: يمضي بنفسه** — وقفةٌ قصيرةٌ على الشعار ثمّ يذوب
          setPhase("leaving");
        } else {
          setPhase("welcome");
        }
      }, span + (signedIn ? 250 : 0)),
    );
    return () => timers.forEach((id) => window.clearTimeout(id));
  }, [phase, signedIn]);

  useEffect(() => {
    if (phase !== "leaving") return;
    const id = window.setTimeout(() => onDone(phone || undefined), 300);
    return () => window.clearTimeout(id);
  }, [phase, onDone, phone]);

  // **صاحبُ البصمة يُعرف بعد الإقلاع بلحظة** (`biometry` يُقاس ولا يُفترض) — فإن عُرف
  // والترحيبُ ما زال على «أهلاً وسهلاً» قبل أن يلمس شيئاً، يمضي كما يمضي الداخل
  useEffect(() => {
    if (signedIn && phase === "welcome") setPhase("leaving");
  }, [signedIn, phase]);

  // **«يظهر حقلُ الهاتف مفعّلاً»** عند 0.48ث من اللمس
  useEffect(() => {
    if (phase !== "entry") return;
    const id = window.setTimeout(() => input.current?.focus(), 520);
    return () => window.clearTimeout(id);
  }, [phase]);

  const skip = () => {
    if (phase !== "intro") return;
    markSeen();
    setPhase(signedIn ? "leaving" : "welcome");
  };

  const open = () => {
    setPressed(true);
    setPhase("entry");
  };

  const ready = dialCode !== null && looksComplete(phone, nationalLength);
  const animating = phase === "intro" ? "rw-intro" : phase === "brief" ? "rw-brief" : "";

  return (
    <div
      className={["rw", animating, phase === "entry" ? "is-card" : "", phase === "leaving" ? "is-leaving" : ""]
        .filter(Boolean)
        .join(" ")}
      onClick={phase === "intro" ? skip : undefined}
      role="presentation"
    >
      <div className="rw-stage" style={{ ["--rw-scale" as string]: String(scale) }}>
        <div className="rw-cam">
          <img src="/welcome/amman-day.svg" alt="" />
          {LABELS.map(([text, x, y]) => (
            <span key={text} className="rw-label" style={{ left: x, top: y }}>
              {text}
            </span>
          ))}
          {phase === "intro" ? (
            <>
              <svg className="rw-trail" width="390" height="844" viewBox="0 0 390 844" aria-hidden="true">
                <path d={HD} fill="none" stroke="rgba(255,255,255,.95)" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" pathLength={1} />
                <path d={HD} fill="none" stroke="var(--ember)" strokeWidth="1.35" strokeLinecap="round" strokeLinejoin="round" pathLength={1} />
              </svg>
              <div className="rw-car" style={{ offsetPath: `path('${HD}')` }}>
                <span />
                <span />
              </div>
            </>
          ) : null}
        </div>

        <div className={phase === "intro" ? "rw-veil" : "rw-veil static"} />

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

        {phase === "welcome" || phase === "entry" ? (
          <div className="rw-copy rw-copy-out">
            <h1 className="rw-rise d1">أهلاً وسهلاً</h1>
            <p className="rw-origin rw-rise d2">حللتَ أهلاً، ووطئتَ سهلاً.</p>
            <p className="rw-explain rw-rise d3">
              جئتَ بين أهلك، وطريقك سهل — هكذا نريد أن تكون كل رحلة.
            </p>
          </div>
        ) : null}
      </div>

      {/* **ذكرُ الخريطة ما دامت معروضة** — شرطُ الرخصة لا زينة (§61-أ، `welcome.css`) */}
      <span className="rw-credit" dir="ltr">
        © OpenStreetMap · Copernicus DEM · Open-Meteo
      </span>

      {phase === "intro" ? <span className="rw-skip">المس الشاشة للتخطّي</span> : null}

      {phase === "welcome" || phase === "entry" ? (
        <div
          className={["rw-cta", "rw-rise", pressed ? "is-pressed" : ""].filter(Boolean).join(" ")}
          role={phase === "welcome" ? "button" : undefined}
          tabIndex={phase === "welcome" ? 0 : -1}
          onClick={phase === "welcome" ? open : undefined}
          onKeyDown={(event) => {
            if (phase === "welcome" && (event.key === "Enter" || event.key === " ")) open();
          }}
        >
          <div className="rw-cta-label">
            <span>تفضّل</span>
            <ArrowBack />
          </div>
          <form
            className="rw-card"
            onSubmit={(event) => {
              event.preventDefault();
              if (ready) setPhase("leaving");
            }}
          >
            <div className="rw-grab" aria-hidden="true" />
            <h2>رقم هاتفك</h2>
            <p className="rw-sub">لديك حساب؟ تدخل بكلمة المرور. جديد؟ ننشئ حسابك برمز تحقق.</p>
            {/* **سوقان أو أكثر ⇒ يُختار السوق** كما في شاشات المصادقة القائمة —
                اللوحةُ ترسم `+962` وحدَه، والتطبيقُ يحمل ما تنشره `/config` */}
            {countries.length > 1 ? (
              <div className="rw-countries">
                {countries.map((code) => (
                  <button
                    key={code}
                    type="button"
                    aria-pressed={code === country}
                    onClick={() => setCountry(code)}
                  >
                    {COUNTRY_LABEL[code]}
                  </button>
                ))}
              </div>
            ) : null}
            <label className="rw-field">
              <span className="rw-dial">+{dialCode ?? ""}</span>
              <span className="rw-sep" aria-hidden="true" />
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
            <button type="submit" className="rw-go" disabled={!ready}>
              متابعة
            </button>
          </form>
        </div>
      ) : null}
    </div>
  );
}
