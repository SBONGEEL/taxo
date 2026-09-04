/** **أللنطاق سجلٌّ أصلاً؟** — العمودُ الذي كان ناقصاً في فحص الغلاف.
 *
 * ## العلّةُ مقيسةٌ لا مفترضة (٢٠٢٦-٠٩-٠٤)
 *
 * `check-apk.mjs` يقارن `server.url` **بالجدول** ويسأل «أهما من قناةٍ
 * واحدة؟» — **ولا يسأل هل النطاقُ موجود**. فبقي `channels.json` يقول
 * `panel.tajora.ly` و`dev-panel.tajora.ly` لغلاف المشرف **وهما بلا سجلِّ
 * DNS البتّة**، والحارسُ أخضرُ لأن الطرفين متّسقان مع بعضهما.
 *
 * **والثمنُ كان حزمةً تُبنى وتُوقَّع وتُثبَّت وتفتح صفحةً غيرَ موجودة** —
 * `capacitor.config.ts` يضع `server.url = shellUrl`، **فلا شيءَ من الشاشات
 * داخل الحزمة**. ولا يظهر ذلك في بناءٍ ولا في توقيعٍ ولا في تثبيت: يظهر
 * على شاشة الهاتف، بعد أن يكون كلُّ شيءٍ «أخضر».
 *
 * **والصوابُ المقيس** (من `cloudflared/config.prod.yml` و`config.docker.yml`
 * و`tools/check-served.mjs` معاً): `admin.tajora.ly` و`dev-admin.tajora.ly`.
 * **و`panel` لا يرد في أيِّ ملفِّ نفقٍ في المشروع.**
 *
 * ## ولمَ لا يُقاس بشاهدٍ خارجيّ
 *
 * **حارسٌ يصيح حيث لا خطر يُطفأ** — ومن بنى بلا شبكةٍ سيرى كلَّ نطاقٍ
 * «ميّتاً». **فالشاهدُ الجدولُ نفسُه**: تُسأل النطاقاتُ كلُّها، **وسقوطُ
 * جميعِها يعني أن السائلَ بلا شبكةٍ لا أن النطاقاتِ زالت** — فيُقال «لم
 * يُقس» ولا يُقرأ سكوتُه سلامة. **وسقوطُ بعضها مع نجاح بعضٍ هو الخبر.**
 *
 * **ولا شاهدَ من خارج المشروع** (`cloudflare.com` مثلاً): تبعيّةٌ على طرفٍ
 * ثالثٍ في حارسٍ يوقف البناء، **وسقوطُه يوقفنا لسببٍ ليس منّا**.
 *
 * ## وما لا يقيسه — يُقال
 *
 * **يقيس أن للاسم سجلّاً، لا أن الخادمَ يجيب.** نطاقٌ يحلّ ويعطي `502`
 * يمرّ من هنا — وذاك عمودُ `check:served` و`check-apk` لا هذا. **وحارسٌ
 * تُوسَّع دعواه فوق نطاقه هو الشكلُ الخامسَ عشر.**
 */

import { lookup } from "node:dns/promises";
import { allPairs } from "./channels.mjs";

/** كلُّ مضيفٍ مُصرَّحٍ في الجدول — الغلافُ والـAPI معاً، بلا تكرار. */
export function hostsOfTable() {
  const seen = new Map();
  for (const pair of allPairs()) {
    for (const [what, url] of [["الغلاف", pair.shellUrl], ["الـAPI", pair.apiBase]]) {
      const host = new URL(url).host;
      if (!seen.has(host)) seen.set(host, []);
      seen.get(host).push(`${pair.channel}/${pair.app} ${what}`);
    }
  }
  return seen;
}

/** يسأل DNS عن كلِّ مضيفٍ في الجدول.
 *
 * @returns `{ measured, dead, alive, total }` — و`measured=false` تعني أن
 *   **السائلَ** بلا شبكة، لا أن النطاقاتِ زالت.
 */
export async function resolveTable() {
  const hosts = hostsOfTable();
  const alive = [];
  const dead = [];
  await Promise.all(
    [...hosts.keys()].map(async (host) => {
      try {
        await lookup(host);
        alive.push(host);
      } catch {
        dead.push(host);
      }
    }),
  );
  return {
    measured: alive.length > 0,
    alive: alive.sort(),
    dead: dead.sort(),
    total: hosts.size,
    whereUsed: hosts,
  };
}

/** يطبع الحكمَ ويعيد عددَ الأحمر — **صفرٌ حين لم يُقس**, ويقول ذلك. */
export async function reportTable(prefix = "  ") {
  const result = await resolveTable();
  if (!result.measured) {
    console.log(
      `${prefix}· نطاقاتُ الجدول **لم تُقس** — لا واحدَ من ${result.total} حلّ، ` +
        `فالسائلُ بلا شبكة. **ولا يُقرأ سكوتُه سلامة.**`,
    );
    return 0;
  }
  if (result.dead.length === 0) {
    console.log(`${prefix}✓ ${result.total} نطاقاً مُصرَّحاً في \`channels.json\` لكلٍّ سجلُّ DNS`);
    return 0;
  }
  console.error("");
  console.error(`${prefix}✗ **نطاقٌ مُصرَّحٌ في \`channels.json\` بلا سجلِّ DNS** — والحزمةُ`);
  console.error(`${prefix}  تُبنى وتُوقَّع وتُثبَّت ثمّ تفتح صفحةً غيرَ موجودة، لأن`);
  console.error(`${prefix}  \`server.url\` يعني أن الشاشاتِ تُحمَّل من الشبكة لا من الحزمة.`);
  for (const host of result.dead) {
    console.error(`${prefix}    ${host} ← ${result.whereUsed.get(host).join(" · ")}`);
  }
  console.error(`${prefix}  والحيُّ منها: ${result.alive.join(" · ")}`);
  console.error(`${prefix}  يُصحَّح الاسمُ في \`channels.json\`، أو يُنشأ السجلُّ ومعه مدخلُه في`);
  console.error(`${prefix}  \`cloudflared/config*.yml\` — **والاسمُ الذي لا يرد في أيِّ ملفِّ نفقٍ**`);
  console.error(`${prefix}  **هو الخطأُ غالباً، لا السجلُّ الناقص.**`);
  return result.dead.length;
}
