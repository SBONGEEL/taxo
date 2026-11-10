/** **الطلبُ بالصوت** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٠، SPEC §٩٧/١٠).
 *
 * نافذةُ التعرّف الصوتيّ في الهاتف نفسِه (`SpeechInputPlugin`) تعيد نصّاً يُكتب في «إلى أين؟»، **والوجهةُ تُختار من النتائج
 * وتُؤكَّد في ورقة الطلب** — فلا حجزَ بلا تأكيد. **ولا صوتَ يصلنا ولا يُحفظ**. والمفتاحُ `voice_order_enabled` لكلِّ سوق،
 * **وغلافٌ أقدمُ بلا الملحق لا زرَّ فيه**.
 */

import { Capacitor, registerPlugin } from "@capacitor/core";

import { language } from "@/lib/i18n";

export const VOICE_FLAG = "voice_order_enabled";

const plugin = registerPlugin<{ listen(options: { language: string; prompt: string }): Promise<{ text: string }> }>("SpeechInput");

export function voiceAvailable(): boolean {
  return Capacitor.isNativePlatform() && Capacitor.getPlatform() === "android" && Capacitor.isPluginAvailable("SpeechInput");
}

/** **ما قاله** بلغة التطبيق ولهجة سوقه («ar-JO» · «fr-DZ»)، أو نصٌّ فارغٌ إن أُلغيت النافذة. */
export async function listen(country: string, prompt: string): Promise<string> {
  const tag = `${language === "fr" ? "fr" : "ar"}-${country}`;
  const { text } = await plugin.listen({ language: tag, prompt });
  return (text ?? "").trim();
}
