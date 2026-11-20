/** **أيقوناتُ شريط النظام تتبع مظهرَ التطبيق** (قِيس على S21 ٢٠٢٦-١١-٢٠): `EdgeToEdge` يلوّنها من وضع **الهاتف**، فاختيارُ «فاتح» على
 * هاتفٍ ليليٍّ يترك الساعةَ والبطاريّةَ بيضاءَ على أرضٍ فاتحة. **وغلافٌ أقدمُ بلا الملحق لا يتغيّر فيه شيء** — يُسأل أوّلاً ولا يُرمى
 * وعدٌ بلا ماسك (`check:native-calls`). نسخةُ التطبيق الآخر حرفاً.
 */
import { Capacitor, registerPlugin } from "@capacitor/core";

const bars = registerPlugin<{ setLight(options: { light: boolean }): Promise<void> }>("SystemBars");

export function syncSystemBars(dark: boolean): void {
  if (!Capacitor.isNativePlatform() || !Capacitor.isPluginAvailable("SystemBars")) return;
  bars.setLight({ light: !dark }).catch(() => {
    // غلافٌ بلا الملحق أو نافذةٌ زالت — الشريطُ يبقى كما كان، ولا أثرَ يُرى غيرُه
  });
}
