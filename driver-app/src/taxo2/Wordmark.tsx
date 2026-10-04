/** العلامةُ النصية TAXO — بخطّ Unbounded 800، **والـX تقاطعُ مسارين مرسومان** (الهوية: «التقاطع»).
 *
 * القضيبُ الأوّلُ (−٥٠°) بلون الحروف، والثاني (+٥٠°) **بالجمر** — **أو بلون الخلفية المعاكس** حين تكون الخلفيةُ جمراً
 * («الـX وحده يأخذ لون الخلفية المعاكس»). **والنسبُ من اللوحة حرفاً**: في حرفٍ قياسُه ٣١ صندوقُ الـX ٢٥×٢٤ بهامشٍ ٢
 * وانخفاضٍ ٠٫٥، والقضيبُ ٣١×٧ بنصف قطرٍ ٤ — **وتُضرب كلُّها في `size ÷ 31`** كما تفعل اللوحة.
 *
 * **ويُقرأ «TAXO» كاملاً** (`role="img"`) — لا «TAO» يقرؤه قارئُ الشاشة من الحروف وحدها.
 */
export function Wordmark({
  size,
  cross = "var(--t2-accent)",
  className,
}: {
  /** حجمُ الخطّ بالبكسل — ٣١ في أيقونة التطبيق، ٦٤ في الترحيب، ١٢٨ في الهوية. */
  size: number;
  /** لونُ القضيب الثاني — الجمرُ افتراضاً. */
  cross?: string;
  className?: string;
}) {
  const k = size / 31;
  const bar = { width: 31 * k, height: 7 * k, borderRadius: 4 * k };
  return (
    <span
      dir="ltr"
      role="img"
      aria-label="TAXO"
      className={["t2-wordmark", className].filter(Boolean).join(" ")}
      style={{ fontSize: size }}
    >
      <span aria-hidden="true">TA</span>
      <span
        aria-hidden="true"
        className="t2-wordmark-x"
        style={{ width: 25 * k, height: 24 * k, margin: `0 ${2 * k}px`, verticalAlign: `${-0.5 * k}px` }}
      >
        <span style={{ ...bar, background: "currentColor", transform: "translate(-50%, -50%) rotate(-50deg)" }} />
        <span style={{ ...bar, background: cross, transform: "translate(-50%, -50%) rotate(50deg)" }} />
      </span>
      <span aria-hidden="true">O</span>
    </span>
  );
}
