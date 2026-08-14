/** زرُّ الرجوع الأصليّ في أندرويد — يُربط بتاريخ الملاح لا بالخروج.
 *
 * **العطبُ الذي أنشأ هذا الملف** (رآه المالك على هاتفه): الرجوعُ من شاشة
 * الإشعارات كان **يخرج من التطبيق كلِّه**. والسببُ أن Capacitor بلا مستمعٍ
 * لهذا الزر يُسلّمه إلى سلوكه الافتراضي: إنهاءُ النشاط. فالتطبيقُ يُغلق من
 * أوّل رجوعٍ في أيِّ شاشةٍ داخلية — وهو أسوأُ من ألّا يعمل الزرُّ أصلاً،
 * لأن المستخدمَ يفقد مكانَه بلا إنذار.
 *
 * **والقاعدةُ واحدةٌ لكلِّ الشاشات لا استثناءَ لشاشة**: إن كان في تاريخ
 * التطبيق ما يُرجَع إليه فارجع إليه، وإلا فاخرج. وهي نفسُ قاعدةِ سهم الرجوع
 * في الرأس (`lib/back.ts`) — فلا يفترق زرُّ الجهاز عن زرِّ الشاشة، والاثنان
 * يقرآن `history.state.idx` نفسَه.
 *
 * **ولا يُستدعى على الويب**: `Capacitor.isNativePlatform()` تحرسه، فالمتصفحُ
 * له زرُّ رجوعه ولا يحتاج من يفسّره له.
 */

import { App } from "@capacitor/app";
import { Capacitor } from "@capacitor/core";

/** يبدأ الاستماع، ويُعيد دالةَ إيقافٍ للتنظيف. */
export function bindHardwareBack(): () => void {
  if (!Capacitor.isNativePlatform()) return () => undefined;

  const handle = App.addListener("backButton", () => {
    const state = window.history.state as { idx?: number } | null;
    const depth = typeof state?.idx === "number" ? state.idx : 0;
    if (depth > 0) {
      window.history.back();
      return;
    }
    // **الخروجُ من جذر التطبيق وحدَه**: من كان في الشاشة الأولى ولا تاريخَ
    // له، الرجوعُ عنده يعني «أغلق» — وهذا ما يتوقعه مستخدمُ أندرويد
    void App.exitApp();
  });

  return () => {
    void handle.then((listener) => listener.remove());
  };
}
