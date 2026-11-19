/** **اسمُ المكان مختصراً بذكاء** (أمرُ المالك ٢٠٢٦-١١-١٩، ورقةُ «نبحث لك عن كبتن»).
 *
 *  كان سطرُ الوجهة «طرابلس، شعبية طرابلس، لـ…» — اسمُ البلد والشعبيّةُ والمدينةُ مكرّرةً تأكل السطرَ قبل أن يصل شيءٌ يدلّ.
 *  فالمختصرُ **الأجزاءُ المفيدةُ أوّلاً بترتيبها**: يُحذف اسمُ البلد، والإداريّاتُ («شعبية/محافظة/ولاية/بلدية/لواء…»)، والمكرَّر؛
 *  **والاسمُ الكاملُ يبقى** لمن يلمس السطر. **ولا يُخترع جزءٌ**: ما لم يكن في العنوان لا يظهر في المختصر.
 *
 *  ومعه `isGenericPlace` — عنوانٌ لا يزيد على مدينةٍ واحدة («طرابلس») لا يدلّ كبتناً على رصيف، فيُسأل عنه بإحداثيّتيه.
 *  بلا React ولا متصفّح — يُختبر بـ`node --test` (`tests/place-name.test.ts`).
 */

const COUNTRY_NAMES = new Set(["ليبيا", "الأردن", "الاردن", "المملكة الأردنية الهاشمية", "الجزائر", "Libya", "Jordan", "Algeria", "Algérie"]);
const ADMIN = /^(شعبية|شعبيه|محافظة|محافظه|ولاية|ولايه|بلدية|بلديه|لواء|قضاء|دائرة|دائره)\s/;

function parts(address: string): string[] {
  return address
    .replace(/,/g, "،")
    .split("،")
    .map((part) => part.trim())
    .filter(Boolean);
}

/** الأجزاءُ التي تدلّ — بلا بلدٍ ولا إداريّاتٍ ولا تكرار، بترتيبها في العنوان. */
export function usefulParts(address: string | null | undefined): string[] {
  if (!address) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const part of parts(address)) {
    if (COUNTRY_NAMES.has(part) || ADMIN.test(part)) continue;
    const key = part.replace(/\s+/g, " ");
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(part);
  }
  return out;
}

/** **المختصر**: أوّلُ جزأين مفيدين («تاجوراء، قرب مصحة ابن النفيس») — وما لا جزءَ مفيداً فيه يبقى كما هو ولا يُفرَّغ. */
export function shortPlace(address: string | null | undefined, keep = 2): string | null {
  if (!address) return null;
  const useful = usefulParts(address);
  if (!useful.length) return address.trim() || null;
  return useful.slice(0, keep).join("، ");
}

/** عنوانٌ لا يزيد على اسمٍ مفيدٍ واحد (المدينة وحدَها) — أو لا عنوانَ أصلاً. */
export function isGenericPlace(address: string | null | undefined): boolean {
  const useful = usefulParts(address);
  if (useful.length > 1) return false;
  // «قرب مصحة ابن النفيس» أو «شارع الشط» وحدَهما يدلّان — المدينةُ وحدَها لا تدلّ
  return !useful.length || !/^(قرب|شارع|طريق|دوار|دوّار|حي|حيّ|ساحة|جسر|مستشفى|مصحة|جامع|مسجد|جامعة|مدرسة)\s/.test(useful[0]);
}
