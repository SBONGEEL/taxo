/** قارئُ `channels.json` — **بابٌ واحدٌ لكلِّ من يحتاج قيمةَ قناة**.
 *
 * **ولا قيمةَ افتراضيةَ للقناة**: `TAXO_CHANNEL` غيرُ مضبوطٍ **يوقف** ولا
 * يقع على «عامّ» ولا على «تجريبيّ». وهي القاعدةُ التي أنشأت هذا الملفَّ
 * أصلاً — **بناءٌ ينجح بقناةٍ لم يقصدها أحدٌ أخطرُ من بناءٍ يسقط**، لأن
 * الأولَ يُشحن والثاني يُقرأ.
 */
import { readFileSync } from "node:fs";

const ROOT = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");

export const TABLE = JSON.parse(readFileSync(`${ROOT}/channels.json`, "utf8"));

export const CHANNEL_NAMES = Object.keys(TABLE.channels);
export const APP_NAMES = Object.keys(TABLE.baseAppId);

/** يحلّ قناةً وتطبيقاً إلى القيم الأربع — ويرمي بنصٍّ يُقرأ لا برمزِ خطأ. */
export function resolve(channelName, app) {
  const channel = TABLE.channels[channelName];
  if (!channel) {
    throw new Error(
      `قناةٌ غيرُ معروفة: «${channelName ?? "(غيرُ مضبوطة)"}» — والمعروفُ: ${CHANNEL_NAMES.join(" · ")}.\n` +
        `  تُضبط بـ TAXO_CHANNEL، ولا افتراضَ لها.`,
    );
  }
  const perApp = channel.apps[app];
  const base = TABLE.baseAppId[app];
  if (!perApp || !base) {
    throw new Error(`تطبيقٌ غيرُ معروف: «${app}» — والمعروفُ: ${APP_NAMES.join(" · ")}.`);
  }
  return {
    channel: channelName,
    label: channel.label,
    app,
    apiBase: channel.apiBase,
    shellUrl: perApp.shellUrl,
    appName: perApp.appName,
    appIdSuffix: channel.appIdSuffix,
    appId: `${base}${channel.appIdSuffix}`,
    // **خاصٌّ: لا يُنشر على صفحة التحميل** (قرارُ المالك 2026-09-01) —
    // تطبيقُ مشرفٍ يُثبَّت باليد، فلا يُنزّله أحدٌ ولا يُرى.
    // **والقيمةُ من الجدول لا من اسم التطبيق**: شرطٌ مكتوبٌ في `channels.json`
    // يُقرأ، **واستنتاجٌ من الاسم يسقط أوّلَ تطبيقٍ خاصٍّ ثانٍ**.
    private: perApp.private === true,
  };
}

/** القناةُ من البيئة — **أو وقوفٌ باسمها**. */
export function fromEnv(app) {
  return resolve((process.env.TAXO_CHANNEL ?? "").trim(), app);
}

/** **أهذا أمرُ Capacitor لـiOS؟** — والجوابُ من نصِّ الأمر نفسِه.
 *
 * **iOS تُجمَّع شاشاتُه داخل الحزمة** (قرارُ المالك 2026-09-29): لا
 * `server.url`، والأصلُ `capacitor://localhost`، والحزمةُ تخاطب `apiBase`
 * مباشرةً. **وأندرويد يبقى غلافاً حول النطاق** كما كان.
 *
 * **ولمَ من `argv` لا من متغيّرِ بيئة**: الأداةُ تقيّم `capacitor.config.ts`
 * في عمليّتها هي، **فالمنصّةُ مكتوبةٌ في الأمر** (`cap sync ios`) — ومتغيّرٌ
 * ثانٍ يُنسى فيقع iOS على غلافٍ بلا أن يقول أحدٌ شيئاً. **و`cap sync` بلا
 * منصّةٍ يكتب الغلافَ في iOS أيضاً** — وذاك ما يمسكه `tools/check-ios.mjs`
 * بعد كلِّ مزامنة، **فهذا الاستنتاجُ ليس الحارس**.
 */
export function isIosCommand(argv = process.argv) {
  return argv.slice(2).includes("ios");
}

/** كلُّ الأزواج (قناة × تطبيق) — يقرؤها الحارسُ ليعرف ما هو متّسق. */
export function allPairs() {
  return CHANNEL_NAMES.flatMap((c) => APP_NAMES.map((a) => resolve(c, a)));
}
