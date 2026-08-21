/** الخدمةُ الأمامية: تبقي العمليةَ حيّةً ما دام الكبتنُ **مستقبِلاً**.
 *
 * **العلّةُ مقيسةٌ لا مقدَّرة** (S21، 2026-08-21): أُرسل التطبيقُ إلى الخلفية
 * فسقط مفتاحُ الحضور في **أقلَّ من ٣٠ ثانية** وصار `is_online = false` —
 * إغلاقُ المقبس يشغّل `go_offline`، **والتوزيعُ لا يعرض على غير الحاضر**.
 * فكبتنٌ غادر التطبيقَ خارجٌ من التوزيع، **ولا إشعارَ يوقظه لأن لا عرضَ
 * يُصنع له أصلاً**.
 *
 * **وثلاثةُ حدودٍ تُقال قبل أن تُصدَّق:**
 *
 * 1. **تبقي العمليةَ لا المقبس**: تعمل والشاشةُ مطفأةٌ والتطبيقُ في الخلفية،
 *    **ولا تعمل بعد إزاحة التطبيق من قائمة المهامّ** — المقبسُ في الـWebView
 *    ويموت معها. ولذلك توقف الخدمةُ نفسَها هناك بدل إشعارٍ يكذب.
 * 2. **لا خدمةَ لكبتنٍ غيرِ عامل**: تبدأ مع `onOpen` وتقف مع كلِّ فصل — وهو
 *    شرطُ المالك حرفياً.
 * 3. **والويبُ لا يعرفها**: `isNativePlatform` تحرس النداءات، فالمتصفحُ
 *    يعمل كما كان بلا شرطٍ إضافيّ.
 */

import { Capacitor, registerPlugin } from "@capacitor/core";

interface OnlineServicePlugin {
  start(): Promise<void>;
  /** المقبسُ سقط والكبتنُ ما زال «مستقبِلاً» — فيقول الإشعارُ الحقيقة. */
  degraded(): Promise<void>;
  stop(): Promise<void>;
}

const plugin = registerPlugin<OnlineServicePlugin>("OnlineService");

/** **الفشلُ يُبتلع ويُسجَّل**: خدمةٌ لم تبدأ أهونُ من شاشةٍ لا تعمل — والكبتنُ
 *  يبقى مستقبِلاً ما دام تطبيقُه مفتوحاً، وهو الحالُ قبل هذه الخدمة كلِّها. */
function call(name: keyof OnlineServicePlugin): void {
  if (!Capacitor.isNativePlatform()) return;
  void plugin[name]().catch((error) =>
    console.warn(`تعذّر ${name} لخدمة الاستقبال`, error),
  );
}

export const onlineService = {
  start: () => call("start"),
  degraded: () => call("degraded"),
  stop: () => call("stop"),
};
