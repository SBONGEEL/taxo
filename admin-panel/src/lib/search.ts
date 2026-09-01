/** بحثُ القوائم — **حالةٌ واحدةٌ تستعملها كلُّ شاشة** (قرارُ المالك 2026-09-01).
 *
 * **ولمَ خطّافٌ لا سطرٌ في كلِّ شاشة**: أربعَ عشرةَ قائمةً تكرّر المهلةَ
 * والتشذيبَ و«أثمّة بحثٌ قائم؟» — **وأولُ شاشةٍ تنسى التشذيب** تُرسل مسافةً
 * إلى الخادم فتعود بفراغٍ يُقرأ «لا نتائج».
 *
 * **والمهلةُ ٣٠٠ملّي**: نداءٌ لكلِّ ضغطةِ مفتاحٍ يُغرق الخادمَ، **وأقلُّ من
 * ذلك يُرسل نداءً لكلِّ حرفين**.
 *
 * **والمُرسَلُ `undefined` لا `""`**: `q=""` سلسلةٌ فارغةٌ على السلك، وهي
 * وإن كانت لا تغيّر النتيجة (يقيسه `tests/test_admin_search.py`) **تغيّر
 * الطلبَ نفسَه** — فالطلبُ بلا بحثٍ يبقى الطلبَ القديمَ حرفاً.
 */

import { useEffect, useState } from "react";

const DEBOUNCE_MS = 300;

export interface Search {
  /** ما يكتبه المشرفُ الآن — يُربط بالحقل. */
  text: string;
  setText: (next: string) => void;
  /** ما يُرسل للخادم بعد المهلة — **`undefined` حين لا بحث**. */
  term: string | undefined;
  /** أثمّة بحثٌ قائم؟ — **منه تُختار الحالُ الفارغة** في `Table`. */
  searching: boolean;
}

export function useSearch(): Search {
  const [text, setText] = useState("");
  const [term, setTerm] = useState("");

  useEffect(() => {
    const timer = window.setTimeout(() => setTerm(text.trim()), DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [text]);

  return { text, setText, term: term || undefined, searching: term.length > 0 };
}

/** الحالُ الفارغةُ حين لا يطابق البحثُ شيئاً — **نصٌّ واحدٌ لكلِّ القوائم**. */
export const NO_RESULTS = {
  title: "لا نتائج لبحثك",
  hint: "جرّب اسماً أقصر أو جزءاً من الرقم — والبحثُ يقرأ الجدولَ كلَّه لا الصفحةَ المعروضة.",
};
