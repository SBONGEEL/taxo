/**
 * **حالُ «وجهتي» في صفحة الميزات الجديدة** (٢٠٢٦-١١-١٦) — كان `?? 0` يجعل الدولةَ التي لا صفَّ لها في «قواعد التوزيع» تُقرأ
 * «مطفأة»، **فيُعرض قرارٌ لم يُتّخذ**. والقيمةُ المخزّنةُ تُعرض كما هي، والغائبةُ تُقال غائبة.
 *
 * **ملفٌّ بلا React** — ليُقاس بـ`node --test` وحدَه (`tests/destination-status.test.ts`).
 */
export type DestinationTone = "ok" | "muted" | "warn";

export interface DestinationStatus {
  label: string;
  tone: DestinationTone;
}

/** `null` ⇐ لا صفَّ لهذه الدولة في قواعد التوزيع، فالخلفيّةُ تعمل بافتراضها (`dispatch_settings.DEFAULTS`)؛ وإلا العددُ المخزّن (`0` يطفئها). */
export function destinationStatus(uses: number | null | undefined): DestinationStatus {
  if (uses === null || uses === undefined) return { label: "غيرُ مضبوطة — يعمل افتراضُ الخلفيّة", tone: "warn" };
  if (uses > 0) return { label: `مفعّلة — ${uses} في اليوم`, tone: "ok" };
  return { label: "مطفأة (0)", tone: "muted" };
}
