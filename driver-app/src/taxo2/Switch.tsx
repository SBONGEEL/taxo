/** المفتاحُ بشكل اللوحة (٤٨×٢٨) — **مرئيٌّ وحدَه** (`aria-hidden`).
 *
 * **والزرُّ الذي يحمله هو المفتاحُ عند قارئ الشاشة** (`role="switch"` و`aria-checked`) — فلا يُعلَن مفتاحان لفعلٍ واحد.
 */
export function Switch({ on }: { on: boolean }) {
  return (
    <span className={on ? "t2-switch on" : "t2-switch"} aria-hidden="true">
      <span className="t2-switch-knob" />
    </span>
  );
}
