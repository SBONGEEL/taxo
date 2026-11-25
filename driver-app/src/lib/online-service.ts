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


import { locationBroadcastUrl, issuePresenceToken } from "@/api/endpoints";
import { demoActive } from "@/demo/mode";

interface OnlineServicePlugin {
  /** `endpoint` و`token` يُمرَّران مع كلِّ نبضة — فالخدمةُ تبثّ بنفسها حين
   *  يخنق النظامُ مؤقتاتِ الـWebView، **بالبابِ نفسِه** الذي ينادي الويب. */
  start(options: {
    endpoint: string;
    token: string | null;
    interval_seconds?: number;
    heartbeat_seconds?: number;
    move_meters?: number;
  }): Promise<void>;
  /** المقبسُ سقط والكبتنُ ما زال «مستقبِلاً» — فيقول الإشعارُ الحقيقة. */
  degraded(): Promise<void>;
  stop(): Promise<void>;
  /** **إشاراتُ الجهاز** (§١٠٣ B/17 و25) — غلافٌ أقدمُ لا يعرفها فيرمي، ويُقرأ ذلك «لم يُقس» */
  signals(): Promise<{ mock_location: boolean; rooted: boolean; emulator?: boolean }>;
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

/** **رمزُ الحضور يُطلب مرةً لكلِّ اتصال** — ويُنسى مع الفصل.
 *
 * **وهو وعدٌ مشتركٌ لا قيمة** (عطبٌ مقيسٌ على الإنتاج ٢٠٢٦-١١-٢٥): المقبسُ (`socket.ts`) والرحلةُ (`ride.tsx`) يناديان `start`
 * **في اللحظة نفسِها** عند الاتصال، وكان كلٌّ منهما يرى `cached` فارغاً فيطلب رمزاً — **والإصدارُ الثاني يُبطل الأوّل**
 * (`presence_token.issue`). فكانت الخدمةُ الأماميّةُ تحتفظ أحياناً بالرمز **المُبطَل**، فيُردّ كلُّ بثٍّ من الخلفيّة ٤٠١،
 * **ويسقط حضورُ الكبتن بعد دقيقةٍ من مغادرة التطبيق** والفقاعةُ ظاهرةٌ والمفتاحُ «متّصل» — فلا يصله طلب. والوعدُ المشتركُ
 * يجعل النداءين طلباً واحداً ورمزاً واحداً. */
let pending: Promise<string> | null = null;

function presenceToken(): Promise<string> {
  if (!pending) {
    const request = issuePresenceToken().then((out) => out.token);
    pending = request;
    // **فشلٌ لا يُخبَّأ**: النبضةُ التاليةُ تطلب من جديد
    request.catch(() => {
      if (pending === request) pending = null;
    });
  }
  return pending;
}

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
  /** `intervalSeconds` فاصلُ «المتاح» من لوحة البثّ (§١٠٣ A/3) — تقرؤه الخدمةُ حين يشتعل `native_location`، وغيابُه فاصلُها كما كان */
  start: (intervalSeconds?: number, heartbeatSeconds?: number, moveMeters?: number) => {
    // **وضعُ الضيف لا يبثّ موقعاً إلى الخادم** (SPEC §٧٦-ن/٢) — فلا خدمةَ استقبالٍ تبدأ
    if (!Capacitor.isNativePlatform() || demoActive()) return;
    void (async () => {
      try {
        const token = await presenceToken();
        await plugin.start({
          endpoint: locationBroadcastUrl(),
          token,
          ...(intervalSeconds ? { interval_seconds: Math.round(intervalSeconds) } : {}),
          // **نبضةُ اللوحة ومسافةُ الحركة** (§١٠٣ B/15) — إرسالٌ أقلُّ والكبتنُ واقف، ولا أقلَّ من النبضة
          ...(heartbeatSeconds ? { heartbeat_seconds: Math.round(heartbeatSeconds) } : {}),
          ...(moveMeters ? { move_meters: Math.round(moveMeters) } : {}),
        });
      } catch (error) {
        console.warn("تعذّر بدءُ خدمة الاستقبال", error);
      }
    })();
  },
  degraded: () => call("degraded"),
  stop: () => {
    pending = null;
    call("stop");
  },
};

/** **إشاراتُ الجهاز** (SPEC §١٠٣ B/17 و25) — من المكوِّن نفسِه لا من تسجيلٍ ثانٍ له. */
export function readDeviceSignals(): Promise<{ mock_location: boolean; rooted: boolean; emulator?: boolean }> {
  return plugin.signals();
}
