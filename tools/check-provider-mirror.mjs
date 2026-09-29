/** **مرآةُ حقول العقود المنشورة في `/config`** — يستدعيه `check:config` في التطبيقين.
 *
 * ## الثغرةُ التي سدّها (٢٠٢٦-٠٩-٢٩)
 *
 * `check:config` يقرأ حقولَ الحمولات **في العمق صفراً وحدَه** — و`providers`
 * قاموسٌ متداخلٌ فكان خارجَه كلُّه. **فحقلٌ يُضاف إلى عقدٍ ويُنشر لا مرآةَ له
 * ولا صوت**: يصل ويُرمى، أو يُقرأ `undefined` ويُظنّ غياباً. ووقع السؤالُ مع
 * `ios_public_token` (SPEC §58) — حقلٌ **يُقرأ وحدَه على iOS بلا رجوع**، فخطأُ
 * اسمه خريطةٌ غائبةٌ على كلِّ iPhone.
 *
 * ## ما يقيسه
 *
 * لكلِّ مزوّدٍ **مكتوبٍ نوعُه** في `providers` بـ`api/types.ts`: حقولُه =
 * حقولُ `ProviderSpec` ذاتُ `expose_to_clients=True` في `registry.py` — **في
 * الاتجاهين**: منشورٌ بلا مرآة، ومرآةٌ لما لا يُنشر.
 *
 * ## وما لا يقيسه — يُقال
 *
 * **المزوّدَ الذي لا نوعَ له** في التطبيق (قاموسٌ مفتوح): لا مرآةَ تُقارَن، ولا
 * يُخترع لها. **ولا الأنواعَ نفسَها**: الاسمُ لا النوع — كأخيه `check:config`.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

/** `{mapbox: ["public_token", …], …}` — الحقولُ المنشورةُ لكلِّ مزوّد. */
export function publishedProviderFields() {
  const registry = readFileSync(join(ROOT, "backend/app/services/providers/registry.py"), "utf8");
  const enums = readFileSync(join(ROOT, "backend/app/models/enums.py"), "utf8");
  const enumBlock = enums.slice(enums.indexOf("class ProviderKey("));
  const value = (member) => enumBlock.match(new RegExp(`^\\s+${member} = "([^"]+)"`, "m"))?.[1];

  const out = {};
  const specs = [...registry.matchAll(/ProviderKey\.([A-Z_]+): ProviderSpec\(/g)];
  specs.forEach((m, i) => {
    const block = registry.slice(m.index, specs[i + 1]?.index ?? registry.length);
    const fields = block
      .split("ProviderField(")
      .slice(1)
      .filter((chunk) => /expose_to_clients=True/.test(chunk.split(/\)\s*,/)[0] ?? chunk))
      .map((chunk) => chunk.match(/key="([^"]+)"/)?.[1])
      .filter(Boolean);
    const key = value(m[1]);
    if (key && fields.length) out[key] = fields;
  });
  return out;
}

/** مزوّدو `providers` المكتوبةُ أنواعُهم في `types.ts` وحقولُهم. */
export function mirroredProviderFields(typesSource) {
  const start = typesSource.indexOf("providers:");
  if (start === -1) return {};
  const out = {};
  for (const m of typesSource.slice(start).matchAll(/^\s+([a-z_]+)\?:\s*\{([^{}]*)\}/gm)) {
    // حدُّ الكتلة: أوّلُ واجهةٍ تالية
    if (typesSource.slice(start, start + m.index).includes("export interface")) break;
    out[m[1]] = [...m[2].replace(/\/\*[\s\S]*?\*\//g, "").matchAll(/([a-z_]+)\?\s*:/g)].map((f) => f[1]);
  }
  return out;
}

export function providerMirrorProblems(typesSource) {
  const published = publishedProviderFields();
  const mirrored = mirroredProviderFields(typesSource);
  const problems = [];
  for (const [provider, fields] of Object.entries(mirrored)) {
    const sent = published[provider] ?? [];
    const missing = sent.filter((f) => !fields.includes(f));
    const invented = fields.filter((f) => !sent.includes(f));
    if (missing.length) problems.push(`providers.${provider} لا يعكس ما يُنشر: ${missing.join(", ")}`);
    if (invented.length) problems.push(`providers.${provider} يَعِد بما لا يُنشر: ${invented.join(", ")}`);
  }
  return { problems, checked: Object.values(mirrored).flat().length };
}
