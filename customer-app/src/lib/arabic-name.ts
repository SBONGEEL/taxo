/**
 * **الجزءُ العربيُّ وحدَه من اسمٍ مزدوج** — قاعدةُ اسم الشارع (`places-search/server.py` ‏`_arabic_part`) على **كلِّ أسماء الخريطة**
 * (أمرُ المالك ٢٠٢٦-١١-٢٠ الثالث §١): رآه على S21 — «Alamina Hospital - مشفى الآمنة» يُرسم باللغتين.
 *
 * **ويُقسم الاسمُ عند فاصلٍ إن بدأ أحدُ طرفيه بحرفٍ عربيٍّ والآخرُ بحرفٍ لاتينيّ** — فيؤخذ العربيّ:
 * - «Alamina Hospital - مشفى الآمنة» ⇐ «مشفى الآمنة»؛ «مدرسة النور / Ecole Ennour» ⇐ «مدرسة النور».
 * - **والعربيُّ من الطرفين يبقى كاملاً**: «مصحة المتوسط - تاجوراء» اسمٌ واحدٌ كتبه أحدُهم هكذا، ولا يُقصّ.
 * - **وفاصلٌ داخلَ الاسم لا يقصّه**: «كاجوال للملابس : (2 / 3XL)» يبقى كاملاً — الطرفُ الآخرُ يبدأ برقمٍ لا بحرفٍ لاتينيّ
 *   (وُجد بعدِّ الدول الثلاث ٢٠/١١ قبل الرفع).
 * - **وما لا عربيَّ فيه يبقى كما هو** (الفرنسيُّ في الجزائر، أمرُ ٢٠/١١ الثاني §٤) — لا ترجمةَ ولا اسمَ مخترَع.
 *
 * والعربيُّ يُعرف **بالحرف الأوّل من الطرف** (U+0600–U+06FF) لأن تعابيرَ MapLibre لا تملك تعبيراً نمطيّاً — **وهذا حدُّه المكتوب**:
 * طرفٌ يبدأ بحرفٍ عربيٍّ ثمّ فيه لاتينيٌّ يُقرأ عربيّاً. والملفُّ نفسُه في التطبيقين (`customer-app` و`driver-app`).
 */
const SEPARATORS = [" - ", " – ", " — ", " / ", " | "];

const ARABIC_START = /^[؀-ۿ]/;
const LATIN_START = /^[A-Za-zÀ-ɏ]/;

/** للنصوص في الواجهة — نفسُ القاعدة التي يحسبها التعبيرُ أدناه في الخريطة. */
export function arabicPart(name: string | null | undefined): string {
  let text = (name ?? "").trim();
  for (const sep of SEPARATORS) {
    const at = text.indexOf(sep);
    if (at < 0) continue;
    const left = text.slice(0, at).trim();
    const right = text.slice(at + sep.length).trim();
    if (ARABIC_START.test(left) && LATIN_START.test(right)) text = left;
    else if (ARABIC_START.test(right) && LATIN_START.test(left)) text = right;
  }
  return text;
}

function between(first: unknown, low: string, high: string): unknown {
  return ["all", [">=", first, low], ["<=", first, high]];
}

function arabicStart(value: unknown): unknown {
  return between(["slice", value, 0, 1], "؀", "ۿ");
}

function latinStart(value: unknown): unknown {
  const first = ["slice", value, 0, 1];
  return ["any", between(first, "A", "Z"), between(first, "a", "z"), between(first, "À", "ɏ")];
}

/** **تعبيرُ MapLibre** يلفّ أيَّ تعبيرِ اسم — فاصلاً فاصلاً بالترتيب نفسِه الذي في `arabicPart`. */
export function arabicOnlyExpression(name: unknown): unknown {
  return SEPARATORS.reduce<unknown>((expr, sep, n) => {
    const s = `s${n}`;
    const i = `i${n}`;
    const left = ["slice", ["var", s], 0, ["var", i]];
    const right = ["slice", ["var", s], ["+", ["var", i], sep.length]];
    return [
      "let", s, ["to-string", expr],
      ["let", i, ["index-of", sep, ["var", s]],
        ["case",
          ["<", ["var", i], 0], ["var", s],
          ["all", arabicStart(left), latinStart(right)], left,
          ["all", arabicStart(right), latinStart(left)], right,
          ["var", s]]],
    ];
  }, name);
}
