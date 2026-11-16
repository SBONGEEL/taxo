/** **احتفالٌ قصيرٌ عند نهاية الرحلة ونجاح الدفع** (SPEC §١٠٥/٣-ب) — قطعٌ صغيرةٌ تتطاير مرّةً من مركز الشاشة ثمّ تختفي (١٫٤ ثانية).
 *
 * **زينةٌ لا حاجز**: `pointer-events: none` فلا تحجب زرّاً، ولا تؤخّر شيئاً، **ولا تُرسم أصلاً** والمجموعةُ القديمةُ مشتعلة،
 * أو «تقليلُ الحركة» قائم، أو الهاتفُ ضعيف (`motionAllowed`).
 */
import { useEffect, useState } from "react";
import type { CSSProperties } from "react";

import { motionAllowed, useIconSetV2 } from "./iconSet";

const PIECES = Array.from({ length: 14 }, (_, i) => {
  const angle = (i / 14) * Math.PI * 2;
  const reach = 70 + (i % 3) * 26;
  return {
    x: Math.round(Math.cos(angle) * reach),
    y: Math.round(Math.sin(angle) * reach * 0.8 - 30),
    r: (i * 47) % 360,
    tone: i % 3,
    delay: (i % 4) * 30,
  };
});

export function Celebrate() {
  const v2 = useIconSetV2();
  const [show, setShow] = useState(true);
  useEffect(() => {
    const timer = window.setTimeout(() => setShow(false), 1400);
    return () => window.clearTimeout(timer);
  }, []);
  if (!v2 || !show || !motionAllowed()) return null;
  return (
    <div className="t2-celebrate" aria-hidden="true">
      <span className="t2-celebrate-ring" />
      {PIECES.map((piece, i) => (
        <span
          key={i}
          className={`t2-celebrate-bit tone-${piece.tone}`}
          style={{ "--x": `${piece.x}px`, "--y": `${piece.y}px`, "--r": `${piece.r}deg`, animationDelay: `${piece.delay}ms` } as CSSProperties}
        />
      ))}
    </div>
  );
}
