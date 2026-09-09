/** **صفحةٌ منشورةٌ تعرض «لقطة لم تُلتقط بعد» عطبٌ يُرى** — فيُمنع النشر.
 *
 * ## العلّةُ مقيسةٌ لا مفترضة (٢٠٢٦-٠٩-٠٩)
 *
 * `taxo.tajora.ly` تعرض **سبعةَ مواضعَ** بنصّ «لقطة لم تُلتقط بعد»، منها
 * **أربعةٌ في قسمٍ عنوانُه «خمس محطات من الطلب إلى الدفع»** — فيقرأ الزائرُ
 * وعداً بخمسٍ ويرى واحدة.
 *
 * ## ولمَ المنعُ لا الإخفاء — **والعلّةُ مكتوبةٌ لأن الخيار كان قائماً**
 *
 * **الإخفاءُ يجعل الصفحةَ تكذب بالسكوت**: قسمٌ يعرض ثلاثاً من خمسٍ **ولا
 * شيءَ يقول إن اثنتين نقصتا** — والزائرُ لا يعرف أنه يرى نصفَ المنتج. وهي
 * «شرطٌ لا يتحقّق أبداً يُقرأ حراسةً وهو تعطيل».
 *
 * **والبطاقةُ الفارغةُ تقول الحقيقةَ وإن كانت قبيحة** — وقُبحُها هو ما يجعل
 * أحداً يصلحها. **فالحارسُ يمنع النشرَ ولا يستر النقص.**
 *
 * ## وما لا يقيسه — يُقال
 *
 * **يقيس أن لكلِّ موضعٍ ملفّاً، لا أن الملفَّ حديثٌ ولا أنه مقروء.** لقطةٌ
 * باليةٌ أو مشوَّشةٌ تمرّ من هنا — **وذاك شرطٌ بشريٌّ يبقى**، وقد وقع مقيساً:
 * `captain-home.png` كانت تعرض «عمولة TAXO 0%» والعمولةُ الحيّةُ 2٪.
 */

import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname } from "node:path";

const ROOT = dirname(fileURLToPath(new URL(".", import.meta.url))).replace(
  /[\\/]tools$/,
  "",
);

const PAGE = `${ROOT}/site/index.html`;
const SHOTS = `${ROOT}/site/assets-src/screens`;

if (!existsSync(PAGE)) {
  console.error(`\n✗ لم تُقرأ الصفحة: ${PAGE} — **صفرٌ مقروءٌ عطبٌ لا سلامة**.`);
  process.exit(1);
}

const html = readFileSync(PAGE, "utf8");

// كلُّ موضعٍ يعلن لقطةً — المعرّفُ هو اسمُ الملفّ المنتظَر
const slots = [...html.matchAll(/data-shot="([a-z0-9-]+)"/g)].map((m) => m[1]);
if (slots.length === 0) {
  console.error("\n✗ صفرُ موضعِ `data-shot` في الصفحة — **والصفرُ خبرٌ لا سلامة**.");
  process.exit(1);
}

const unique = [...new Set(slots)].sort();
const missing = unique.filter((id) => !existsSync(`${SHOTS}/${id}.png`));

// والنصُّ الصريحُ يُعدّ أيضاً: موضعٌ يعلن نقصَه بنفسه
const placeholders = (html.match(/لقطة لم تُلتقط بعد/g) || []).length;

console.log("");
console.log("  لقطاتُ الصفحة — أللموضعِ ملفّ؟");
console.log(
  `  · ${slots.length} موضعاً · ${unique.length} معرّفاً متميّزاً · ` +
    `${unique.length - missing.length} لها ملفّ`,
);

if (missing.length === 0 && placeholders === 0) {
  console.log(`  ✓ كلُّ موضعٍ في \`site/index.html\` له ملفٌّ في \`assets-src/screens\``);
  console.log("  · ولا يقيس أن اللقطةَ حديثةٌ ولا أن نصَّها مقروء — شرطٌ بشريٌّ يبقى");
  process.exit(0);
}

console.error("");
// **ولا يُعلَن عنوانٌ لا مصداقَ له** (صُحّح ٢٠٢٦-٠٩-٠٩): كان الحارسُ يطبع
// «موضعٌ بلا لقطة» ثم قائمةً فارغةً حين يكون النقصُ في النصِّ وحدَه — **فيتّهم
// بغير علّته**، ومن يقرأ يبحث عن ملفٍّ ناقصٍ لا وجودَ له.
if (missing.length > 0) {
  console.error("  ✗ **موضعٌ بلا لقطة — والصفحةُ المنشورةُ تعلن نقصَها للزائر**");
} else {
  console.error("  ✗ **الملفّاتُ كلُّها موجودة، والصفحةُ ما زالت تقول «لم تُلتقط»**");
  console.error("      البطاقةُ نصٌّ لا صورة — تُستبدل بوسم `<img>` يشير إلى اللقطة.");
}
for (const id of missing) {
  const where = slots.filter((s) => s === id).length;
  console.error(`      ${id}  ← ${where} موضعاً · يُنتظَر: site/assets-src/screens/${id}.png`);
}
if (placeholders > 0) {
  console.error(`  · و${placeholders} موضعاً يحمل نصَّ «لقطة لم تُلتقط بعد» صراحةً`);
}
console.error("");
console.error("  **ولا يُخفى الفارغُ**: قسمٌ عنوانُه «خمس محطات» يعرض ثلاثاً");
console.error("  **يكذب بالسكوت**، والبطاقةُ الفارغةُ تقول الحقيقةَ وإن قبُحت.");
console.error("  تُلتقط اللقطةُ من التطبيق الحيّ وتُوضع في `assets-src/screens/`.");
process.exit(missing.length || 1);
