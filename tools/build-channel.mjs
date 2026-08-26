/** يبني تطبيقاً بقناةٍ — **ويشتقّ `VITE_API_BASE_URL` من `channels.json`**.
 *
 * **ولمَ غلافٌ لا سطرٌ في `package.json`؟** لأن `check:target` يقرأ
 * `process.env.VITE_API_BASE_URL` **قبل** `vite build`، وسكربتُ npm لا يستطيع
 * أن يضع متغيّراً في بيئة نفسِه على المنصّتين. فالغلافُ يضعه ثمّ ينادي
 * `npm run build` بالبيئة الموروثة — **فيبقى الحارسُ على حاله ولا يُمسّ**.
 *
 * **والقيمةُ لا تُكتب بيد**: هذا هو الفرقُ كلُّه. تحريرُ العنوان يدوياً هو
 * الطريقُ إلى ليلةٍ تُبنى فيها النسخةُ العامّةُ على عنوان جهازِ مطوّر.
 *
 *     TAXO_CHANNEL=public node tools/build-channel.mjs driver-app
 *     TAXO_CHANNEL=test   node tools/build-channel.mjs customer-app
 */
import { spawnSync } from "node:child_process";
import { fromEnv } from "./channels.mjs";

const app = process.argv[2];
if (!app) {
  console.error("الاستعمال: TAXO_CHANNEL=<public|test> node tools/build-channel.mjs <customer-app|driver-app>");
  process.exit(2);
}

let ch;
try {
  ch = fromEnv(app);
} catch (error) {
  console.error(`✗ ${error.message}`);
  process.exit(1);
}

const ROOT = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
console.log(
  `  قناة ${ch.channel} (${ch.label}) · ${ch.app}\n` +
    `    المعرّف : ${ch.appId}\n` +
    `    الغلاف  : ${ch.shellUrl}\n` +
    `    الـAPI  : ${ch.apiBase}`,
);

const result = spawnSync("npm", ["run", "build"], {
  cwd: `${ROOT}/${app}`,
  stdio: "inherit",
  shell: process.platform === "win32",
  env: { ...process.env, VITE_API_BASE_URL: ch.apiBase, TAXO_CHANNEL: ch.channel },
});
process.exit(result.status ?? 1);
