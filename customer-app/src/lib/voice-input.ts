/** **الطلبُ بالصوت** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٠، SPEC §٩٧/١٠).
 *
 * نافذةُ التعرّف الصوتيّ في الهاتف نفسِه (`SpeechInputPlugin`) تعيد نصّاً يُكتب في «إلى أين؟»، **والوجهةُ تُختار من النتائج
 * وتُؤكَّد في ورقة الطلب** — فلا حجزَ بلا تأكيد. **ولا صوتَ يصلنا ولا يُحفظ**. والمفتاحُ `voice_order_enabled` لكلِّ سوق،
 * **وغلافٌ أقدمُ بلا الملحق لا زرَّ فيه**.
 */

import { Capacitor, registerPlugin } from "@capacitor/core";

import { language } from "@/lib/i18n";

export const VOICE_FLAG = "voice_order_enabled";
/** **«اطلب رحلة إلى سيتي مول»** (SPEC §١٠٣ C/36) — الجملةُ تُقرأ وجهةً: يُنزع فعلُ الطلب ويبقى المكان. خلف مفتاحه. */
export const VOICE_PHRASE_FLAG = "voice_ride_phrase";

/** أفعالُ الطلب في أوّل الجملة — **بلهجات الأسواق الثلاثة والفرنسيّة**؛ ويُنزع الأطولُ أوّلاً فلا يبقى «رحلة» بعد «اطلب». */
const LEADS = [
  "اطلب لي رحلة الى", "اطلب لي رحلة إلى", "اطلب رحلة الى", "اطلب رحلة إلى", "اطلب تاكسي الى", "اطلب تاكسي إلى",
  "بدي رحلة على", "بدي رحلة الى", "بدي رحلة إلى", "بدي اروح على", "بدي أروح على", "بدي اروح الى", "بدي أروح إلى",
  "خذني الى", "خذني إلى", "خذني على", "وصلني على", "وصلني الى", "وصلني إلى", "ودّيني على", "وديني على",
  "نحب نمشي الى", "نحب نمشي ل", "نحب نروح الى", "نحب نروح ل", "حابب نروح الى",
  "رحلة الى", "رحلة إلى", "الى", "إلى",
  "emmène-moi à", "emmene-moi a", "je veux aller à", "je veux aller a", "une course pour", "une course vers", "vers",
];
const SORTED_LEADS = [...LEADS].sort((a, b) => b.length - a.length);

/** خالصة: الجملةُ المنطوقة ⇐ اسمُ المكان. وما لا فعلَ في أوّله يبقى كما قيل — **فلا يُمحى اسمُ مكانٍ يبدأ بحرف جرّ مصادفة** إلا إن
 *  بقي بعده شيء. */
export function spokenDestination(text: string): string {
  let rest = text.trim().replace(/\s+/g, " ");
  const lower = rest.toLowerCase();
  for (const lead of SORTED_LEADS) {
    if (lower.startsWith(lead.toLowerCase() + " ")) {
      const place = rest.slice(lead.length).trim();
      if (place) rest = place;
      break;
    }
  }
  return rest.replace(/[.!؟?،,]+$/u, "").trim();
}

const plugin = registerPlugin<{ listen(options: { language: string; prompt: string }): Promise<{ text: string }> }>("SpeechInput");

export function voiceAvailable(): boolean {
  return Capacitor.isNativePlatform() && ["android", "ios"].includes(Capacitor.getPlatform()) && Capacitor.isPluginAvailable("SpeechInput");
}

/** **ما قاله** بلغة التطبيق ولهجة سوقه («ar-JO» · «fr-DZ»)، أو نصٌّ فارغٌ إن أُلغيت النافذة. */
export async function listen(country: string, prompt: string, phrase = false): Promise<string> {
  const tag = `${language === "fr" ? "fr" : "ar"}-${country}`;
  const { text } = await plugin.listen({ language: tag, prompt });
  const heard = (text ?? "").trim();
  return phrase ? spokenDestination(heard) : heard;
}
