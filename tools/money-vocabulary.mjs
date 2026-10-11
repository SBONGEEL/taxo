/** مفرداتُ المال من بيتها الواحد (`backend/app/core/money_wire.py`) — **بقارئٍ يعرف التعليقَ والنصّ**.
 *
 * **كان القارئُ منسوخاً في حارسين، وكلاهما يقطع الكتلةَ عند أوّل قوسٍ يغلق** (`STATE.md` §٧٣، البندُ المفتوح ١).
 * **وتعليقٌ فيه «(§٦٢-ب/٥٢)» قبل `"_revenue"`** أغلق الكتلةَ قبل أوانها — فلم يعرف `check:money-math` ولا
 * `check:money-visible` أنّ `_revenue` مال، **وكلاهما أخضر**: قائمةٌ تُقرأ ناقصةً لا تصيح، تُمرّر ما بعد القطع.
 *
 * **والعلاجُ قارئٌ واحدٌ لا تصحيحان**: نسختان من القارئ هما بعينهما ما جعل العطبَ يقع مرّتين. وهذا يمشي النصَّ حرفاً حرفاً:
 * **يتخطّى التعليقَ** (`#` إلى آخر السطر) **والنصَّ** في عدّ الأقواس، **ويوازن** `( [ {` حتى تُغلق الكتلةُ التي فُتحت —
 * فلا يقطعها قوسٌ في تعليق، ولا يزيد عليها نصٌّ بعدها.
 *
 * **وما لا يمسكه، ويقوله**: سلاسلُ بايثون الثلاثية والبادئاتُ (`r"…"`, `f"…"`) — والكتلُ الثلاثُ لا تحملها؛ فإن حملتها
 * يومًا **عاد القارئُ `null` لا قائمةً ناقصة**، والحارسُ يسقط بـ«لم تُقرأ» ولا يمضي أعمى.
 */

import { readFileSync } from "node:fs";

/** نصوصُ كتلةٍ بايثونيّة تُسنَد في أوّل سطرها: `NAME = (…)` أو `NAME = frozenset({…})` — أو `null` إن لم تُقرأ كاملة. */
export function pythonStrings(source, name) {
  const head = new RegExp(`^${name} = `, "m").exec(source);
  if (!head) return null;
  const out = [];
  let depth = 0;
  let opened = false;
  let i = head.index + head[0].length;
  while (i < source.length) {
    const c = source[i];
    if (c === "#") {
      const eol = source.indexOf("\n", i);
      i = eol < 0 ? source.length : eol;
      continue;
    }
    if (c === '"' || c === "'") {
      if (source.startsWith(c.repeat(3), i)) return null; // سلسلةٌ ثلاثيّة — لا تُقرأ تخميناً
      let j = i + 1;
      let text = "";
      while (j < source.length && source[j] !== c) {
        if (source[j] === "\n") return null; // نصٌّ لم يُغلق في سطره
        if (source[j] === "\\") {
          text += source[j + 1];
          j += 2;
          continue;
        }
        text += source[j];
        j += 1;
      }
      if (j >= source.length) return null;
      if (opened && depth > 0) out.push(text);
      i = j + 1;
      continue;
    }
    if ("([{".includes(c)) {
      depth += 1;
      opened = true;
    } else if (")]}".includes(c)) {
      depth -= 1;
      if (depth < 0) return null;
      if (opened && depth === 0) return out;
    } else if (c === "\n" && !opened) {
      return null; // إسنادٌ بلا قوسٍ في سطره — ليس كتلة
    }
    i += 1;
  }
  return null;
}

/** `{suffixes, names, notMoney}` من بيت المفردات — أو `null` إن لم تُقرأ كتلةٌ منها كاملة. */
export function moneyVocabulary(path) {
  const source = readFileSync(path, "utf8");
  const suffixes = pythonStrings(source, "MONEY_SUFFIXES");
  const names = pythonStrings(source, "MONEY_NAMES");
  const notMoney = pythonStrings(source, "NOT_MONEY");
  if (!suffixes?.length || !names?.length || notMoney === null) return null;
  return { suffixes, names: new Set(names), notMoney: new Set(notMoney) };
}
