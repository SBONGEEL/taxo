package ly.tajora.rider;

import android.Manifest;

import com.capacitorjs.plugins.pushnotifications.PushNotificationsPlugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.huawei.hms.aaid.HmsInstanceId;

/**
 * <b>ملحقُ الإشعارات في نسخة Huawei — الاسمُ نفسُه {@code PushNotifications}، والرمزُ من HMS لا من FCM</b> (أمرُ المالك ٢٠٢٦-١١-٢٣).
 *
 * <p><b>ولمَ يُستبدل ولا يُترك</b> (وقع مقيساً على محاكٍ بلا خدمات Google، ٢٠٢٦-١١-٢٣): الصفحةُ تنادي {@code PushNotifications.register()}
 * بعد الإقلاع، <b>و{@code FirebaseMessaging.getInstance()} يرمي على خيط الملحق</b> لأنّ هذه النسخةَ بلا مشروع Firebase — <b>فسقط التطبيقُ كلُّه
 * بعد أربعين ثانية</b>. والصفحةُ تُحمَّل من الخادم فلا تُصلَح فيها وحدَها: كلُّ نسخةٍ منها تنادي الملحقَ نفسَه.
 *
 * <p><b>فيرث الملحقَ ويُبقي كلَّ شيءٍ</b> (الأذونات، القنوات، الإشعاراتُ المعروضة، الأحداث) <b>إلّا طريقين</b>: {@code register} يطلب رمزَ HMS
 * ويبثّه بحدث {@code registration} نفسِه، و{@code unregister} يحذفه. <b>والتسجيلُ بعده يغلب</b>: يُسجَّل من {@code FlavorPlugins} بعد قائمة
 * الملحقات المولَّدة، و{@code Bridge} يكتب الاسمَ الأخيرَ فوق الأوّل.
 *
 * <p><b>وبلا معرّف AppGallery</b> ({@code TAXO_HMS_APP_ID} فارغ) يبثّ {@code registrationError} بـ{@code hms_unconfigured} — والصفحةُ تقرؤه
 * «لا رمز» كما تقرأ كلَّ فشلٍ في التسجيل. <b>ولا يُرسَل رمزُ HMS إلى الخادم باسم FCM</b> قبل أن يُبنى مُرسِلُ HMS في الخلفيّة (بندٌ في STATE).
 */
@CapacitorPlugin(
    name = "PushNotifications",
    permissions = @Permission(strings = { Manifest.permission.POST_NOTIFICATIONS }, alias = "receive")
)
public class HmsPushNotificationsPlugin extends PushNotificationsPlugin {

    @Override
    @PluginMethod
    public void register(PluginCall call) {
        String appId = HmsPushPlugin.appIdOf(getContext());
        call.resolve();
        if (appId.isEmpty()) {
            sendError("hms_unconfigured");
            return;
        }
        new Thread(() -> {
            try {
                String token = HmsInstanceId.getInstance(getContext()).getToken(appId, "HCM");
                // **وفارغٌ = يصل لاحقاً** إلى {@code HmsPushService.onNewToken} ومنه إلى الحدث نفسِه (EMUI القديم)
                if (token != null && !token.isEmpty()) sendToken(token);
            } catch (Exception failed) {
                sendError("hms_unavailable");
            }
        }).start();
    }

    @Override
    @PluginMethod
    public void unregister(PluginCall call) {
        String appId = HmsPushPlugin.appIdOf(getContext());
        new Thread(() -> {
            try {
                if (!appId.isEmpty()) HmsInstanceId.getInstance(getContext()).deleteToken(appId, "HCM");
            } catch (Exception ignored) {
                // لا رمزَ يُحذف — النتيجةُ واحدة
            }
            call.resolve();
        }).start();
    }
}
