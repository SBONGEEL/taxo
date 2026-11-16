/** **مجموعةُ الأيقونات الجديدة تغطّي كلَّ ما يُرسم** (SPEC §١٠٥/٣) — ولا يبقى اسمٌ يُرسم من الخطِّ القديم والمجموعةُ مشتعلة.
 *
 * **ولمَ من `index.html` في التطبيقات الثلاثة**: المقتطَعُ هناك هو قائمةُ ما يُرسم فعلاً (`check:taxo2` يحرس أنّ كلَّ اسمٍ في الشيفرة فيه)،
 * فاسمٌ يُضاف إليه بلا رسمٍ هنا يُسقط هذا الاختبار. */
import { readFileSync } from "node:fs";
import { test } from "node:test";
import assert from "node:assert/strict";

import { CAR_ART, GLYPHS } from "../src/taxo2/glyphs.ts";

const names = new Set<string>();
for (const app of ["customer-app", "driver-app", "admin-panel"]) {
  const html = readFileSync(new URL(`../../${app}/index.html`, import.meta.url), "utf8");
  for (const name of /icon_names=([^&"]+)/.exec(html)?.[1].split(",") ?? []) names.add(name);
}

test("كلُّ أيقونةٍ في مقتطَع الخطّ لها رسمٌ في المجموعة الجديدة", () => {
  assert.ok(names.size > 100, `قُرئ ${names.size} اسماً فقط — المقتطَعُ تغيّر موضعُه`);
  const missing = [...names].filter((name) => !GLYPHS[name]);
  assert.deepEqual(missing, []);
});

test("كلُّ رسمٍ عناصرُ مغلقةٌ داخل الشبكة", () => {
  for (const [name, body] of Object.entries({ ...GLYPHS, ...CAR_ART })) {
    const open = (body.match(/<(path|circle|rect)\b/g) ?? []).length;
    const closed = (body.match(/\/>/g) ?? []).length;
    assert.equal(open, closed, name);
    assert.ok(!/NaN|undefined/.test(body), name);
  }
});

test("لكلِّ رسمِ فئةٍ أيقونةٌ باسمه — فالمجموعةُ تُطفأ إلى الأيقونة لا إلى نصّ", () => {
  for (const name of Object.keys(CAR_ART)) assert.ok(GLYPHS[name], name);
});
