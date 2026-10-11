/** **ما يتشاركه حارسُ العربيّة وأداةُ اللفّ** (SPEC §٧٣-هـ المرحلة ٥) — تعريفٌ واحدٌ لـ«ما يُرسم» و«مفتاحِ القالب»، فلا يقيس الحارسُ بغير ما تلفّ به الأداة. */

/** **النصُّ كما يرسمه JSX** — قاعدةُ المسافات نفسُها (`cleanJSXElementLiteralChild`): السطورُ تُقصّ وتُوصل بمسافة. */
export function jsxRendered(raw) {
  const lines = raw.split(/\r\n|\n|\r/);
  let last = 0;
  lines.forEach((line, i) => {
    if (/[^ \t]/.test(line)) last = i;
  });
  let out = "";
  lines.forEach((line, i) => {
    let text = line.replace(/\t/g, " ");
    if (i !== 0) text = text.replace(/^[ ]+/, "");
    if (i !== lines.length - 1) text = text.replace(/[ ]+$/, "");
    if (text) {
      if (i !== last) text += " ";
      out += text;
    }
  });
  return out;
}

/** **مفتاحُ قالبٍ نصّيّ** — أجزاؤه الحرفيّةُ والمواضعُ `{0}` `{1}` مكانَ ما بينها. */
export function templateKey(node) {
  return node.head.text + node.templateSpans.map((span, i) => `{${i}}${span.literal.text}`).join("");
}
