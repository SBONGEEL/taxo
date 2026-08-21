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

import { API_URL } from "@/api/client";
import { issuePresenceToken } from "@/api/endpoints";

interface OnlineServicePlugin {
  /** `endpoint` و`token` يُمرَّران مع كلِّ نبضة — فالخدمةُ تبثّ بنفسها حين
   *  يخنق النظامُ مؤقتاتِ الـWebView، **بالبابِ نفسِه** الذي ينادي الويب. */
  start(options: { endpoint: string; token: string | null }): Promise<void>;
  /** المقبسُ سقط والكبتنُ ما زال «مستقبِلاً» — فيقول الإشعارُ الحقيقة. */
  degraded(): Promise<void>;
  stop(): Promise<void>;
}

const plugin = registerPlugin<OnlineServicePlugin>("OnlineService");

/** **الفشلُ يُبتلع ويُسجَّل**: خدمةٌ لم تبدأ أهونُ من شاشةٍ لا تعمل — والكبتنُ
 *  يبقى مستقبِلاً ما دام تطبيقُه مفتوحاً، وهو الحالُ قبل هذه الخدمة كلِّها. */
function call(name: "degraded" | "stop"): void {
  if (!Capacitor.isNativePlatform()) return;
  void plugin[name]().catch((error) =>
    console.warn(`تعذّر ${name} لخدمة الاستقبال`, error),
  );
}

/** **رمزُ الحضور يُطلب مرةً لكلِّ اتصال** — ويُنسى مع الفصل. */
let cached: string | null = null;

export const onlineService = {
  /** **العنوانُ من `api/client` لا من ثابتٍ هنا**: حزمةٌ تُبنى لهدفٍ وتبثّ
   *  إلى غيره هي الشكلُ العاشر بعينه — وحارساه `check:target`/`check:dist`
   *  يقرآن الحزمةَ لا هذا الملف. */
  /** **يبدأ برمز الحضور لا برمز الجلسة** (§23.4).
   *
   * **والعلّةُ عمرٌ لا ذوق**: رمزُ الوصول ثلاثون دقيقةً ووردياتُ الكبتن
   * أطول، **ورمزُ التجديد أحاديُّ الاستعمال** فحاملان له يخرجانه من حسابه.
   * فرمزُ الحضور **بابٌ واحدٌ** يُلغى لحظةَ الفصل وعند الخروج.
   *
   * **ويُطلب مرةً عند أول نبضة ويُخبَّأ**: طلبُه مع كلِّ بثٍّ يبطل السابقَ
   * كلَّ عشرين ثانية، **فيصير الإلغاءُ ضجيجاً لا حدثاً**.
   */
  start: () => {
    if (!Capacitor.isNativePlatform()) return;
    void (async () => {
      try {
        if (!cached) cached = (await issuePresenceToken()).token;
        await plugin.start({
          endpoint: `${API_URL}/drivers/me/location`,
          token: cached,
        });
      } catch (error) {
        console.warn("تعذّر بدءُ خدمة الاستقبال", error);
      }
    })();
  },
  degraded: () => call("degraded"),
  stop: () => {
    cached = null;
    call("stop");
  },
};
