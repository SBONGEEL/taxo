/** **لونُ سيارة الكبتن على سيارة TAXO** (أمرُ المالك ٢١/١١، SPEC §١١١) — خالصةٌ بلا React، فتُختبر في `tests/car-paint.test.ts`.
 *
 *  **اللونُ نصٌّ حرٌّ لا تعداد** (`vehicles.color` — `VEHICLE_COLORS` اقتراحاتٌ وحدَها)، فيُقرأ بكلماته العربيّة والفرنسيّة والإنجليزيّة
 *  بعد نزع التشكيل؛ **وما لا يُعرف لا يُخمَّن**: تبقى السيارةُ بيضاءَ كما رُسمت، واسمُ اللون مكتوبٌ بجانبها كما كتبه.
 *
 *  **والطلاءُ قناعٌ لكلِّ سيارة** (`public/cars/<key>-paint-<day|night>.webp` — الهيكلُ الأبيضُ وحدَه، لا الزجاجُ ولا اللمسةُ البرتقاليّة)
 *  يُضرب فيه اللونُ (`mix-blend-mode: multiply`)، فيبقى الظلُّ والانعكاس. **وسيارتا «المميّزة» السوداء والنساءِ بلونيهما**: هويّتا فئتين
 *  لا طلاءٌ أبيض — فلا قناعَ لهما. */

const PAINTABLE: ReadonlySet<string> = new Set(["economy", "comfort", "hatchback", "suv", "family", "van", "city_taxi"]);

/** الكلماتُ بعد نزع التشكيل والهمزات — **الأطولُ أوّلاً** فـ«رمادي غامق» لا تُقرأ «أحمر» بحرفٍ عارض. */
const PAINTS: ReadonlyArray<readonly [RegExp, string]> = [
  [/ابيض|white|blanc|لؤلؤي|pearl/, ""],
  [/اسود|black|noir/, "#2b2e33"],
  [/فضي|silver|argent/, "#b9bec6"],
  [/رمادي|رصاصي|gr[ae]y|gris/, "#7d838c"],
  [/كحلي|navy|marine/, "#22355e"],
  [/ازرق|نيلي|blue|bleu/, "#2f5fae"],
  [/خمري|نبيتي|عنابي|maroon|bordeaux|burgundy/, "#6e1f2a"],
  [/احمر|red|rouge/, "#b8262b"],
  [/اخضر|زيتي|green|vert/, "#2f7a4a"],
  [/بني|brown|marron/, "#6b4a33"],
  [/ذهبي|gold|or|doré/, "#c9a45a"],
  [/بيج|beige|كريمي|cream/, "#d8c7a3"],
  [/برتقالي|orange/, "#e8692e"],
  [/اصفر|yellow|jaune/, "#e9c33a"],
];

function normalize(text: string): string {
  return text
    .toLowerCase()
    .replace(/[ً-ٰٟـ]/g, "")
    .replace(/[أإآ]/g, "ا")
    .replace(/ى/g, "ي")
    .trim();
}

/** لونُ الطلاء — `null` حيث لا يُعرف اللونُ أو كان أبيض (السيارةُ كما رُسمت) أو كانت السيارةُ ليست بيضاءَ الهيكل. */
export function paintFor(carKey: string, color: string | null | undefined): string | null {
  if (!color || !PAINTABLE.has(carKey)) return null;
  const text = normalize(color);
  for (const [pattern, hex] of PAINTS) if (pattern.test(text)) return hex || null;
  return null;
}
