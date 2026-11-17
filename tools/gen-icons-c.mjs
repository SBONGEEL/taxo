// يولّد taxo2/glyphsC.ts من design/icons-c/set.mjs — المصدرُ واحد، والنسخُ الثلاثُ بايتاً
import { writeFileSync } from "node:fs";
const root = process.argv[2];
const m = await import(`${root}/design/icons-c/set.mjs`);
const CLS = { body: "b", back: "k", detail: "d", cut: "c", ground: "g" };
function inner(parts) {
  const out = [];
  for (const p of parts) if (p.role === "body") out.push(`<path class="k" transform="translate(2 2)" d="${p.d}"/>`);
  for (const p of parts) out.push(`<path class="${CLS[p.role]}" d="${p.d}"/>`);
  return out.join("");
}
const all = { ...m.VEHICLES, ...m.GLYPHS };
const lines = Object.keys(all).map((k) => `  ${k}: ${JSON.stringify(inner(all[k]))},`);
const src = `/** **أيقوناتُ TAXO بالنمط C** (قرارُ المالك ١٧/١١/٢٠٢٦: «معتمدة»، \`design/OWNER-2026-11-17-DECISIONS.md\` ٢) — **مولَّدةٌ لا مكتوبة**:
 *  \`node tools/gen-icons-c.mjs\` من \`design/icons-c/set.mjs\` (المصدرُ الواحد واللوحةُ التي رآها المالك)، **ومنسوخةٌ بايتاً في التطبيقين واللوحة**.
 *
 *  ٣٦ رسماً على شبكة ٤٨: **٨ مركباتٍ بثلاثة أرباع** (\`VEHICLES_C\`، للفئات) و**٢٨ أيقونة**، ومعها **علامةُ الخريطة** تتّجه شمالاً وتُدار مع الطريق.
 *  الأدوارُ أصنافٌ لا ألوان (\`glyphs.css\`): \`b\` البرتقاليّ · \`k\` الدرجةُ الثانية (والظلُّ المزاح) · \`d\` الداكن · \`c\` لونُ السطح · \`g\` ظلُّ الأرض —
 *  **فتتبدّل في الداكن وعلى الأزرار البرتقاليّة** بلا نسخةٍ ثانية. خلف \`icons_v2\`، **وما ليس هنا يبقى من الخطّ القديم كما كان**. */

export const GLYPHS_C: Readonly<Record<string, string>> = {
${lines.join("\n")}
};

/** المركباتُ — تُرسم بدل أيقونة الفئة حيث يُطلب رسمُها (\`art\`) */
export const VEHICLES_C: ReadonlySet<string> = new Set(${JSON.stringify(Object.keys(m.VEHICLES))});

/** علامةُ الخريطة — سيّارةٌ من فوق **تتّجه شمالاً**، وتُدار بزاوية الطريق (\`smoothBearing\`) */
export const MARKER_C = ${JSON.stringify(inner(m.MARKER))};

/** **دورانٌ ناعمٌ مع الطريق** — بأقصر قوس (فلا تلفّ ٣٥٠° حين تعبر الشمال)، ويقترب بنسبة \`k\` في كلِّ تحديث */
export function smoothBearing(current: number, target: number, k = 0.18): number {
  const delta = ((((target - current) % 360) + 540) % 360) - 180;
  return (current + delta * k + 360) % 360;
}
`;
for (const app of ["customer-app", "driver-app", "admin-panel"]) writeFileSync(`${root}/${app}/src/taxo2/glyphsC.ts`, src);
console.log(Object.keys(all).length, "icons + marker");
