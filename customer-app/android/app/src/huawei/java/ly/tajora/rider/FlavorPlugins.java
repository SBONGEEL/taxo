package ly.tajora.rider;

import com.getcapacitor.BridgeActivity;

/** <b>إضافاتُ نسخة Huawei</b> — رمزُ HMS Push ورسائلُه ({@link HmsPushPlugin})، وملحقُ الإشعارات بـHMS ({@link HmsPushNotificationsPlugin}).
 *  ونظيرُه في {@code src/gms} فارغ. */
final class FlavorPlugins {
    private FlavorPlugins() {
    }

    static void register(BridgeActivity activity) {
        activity.registerPlugin(HmsPushPlugin.class);
    }

    /**
     * <b>ما يحلّ محلَّ ملحقٍ مولَّدٍ باسمه</b> — يُنادى من {@code MainActivity.load()} <b>بعد</b> قائمة الملحقات المولَّدة
     * ({@code capacitor.plugins.json})، فيكتب {@code Bridge} الاسمَ الأخيرَ فوقها. <b>وما يُسجَّل قبل {@code super.onCreate} يسبق القائمةَ
     * فتغلبه</b> — قِيس على المحاكي ٢٠٢٦-١١-٢٣: ملحقُ FCM بقي هو المسجَّلَ وأسقط التطبيق.
     */
    static void late(BridgeActivity activity) {
        activity.registerPlugin(HmsPushNotificationsPlugin.class);
    }
}
