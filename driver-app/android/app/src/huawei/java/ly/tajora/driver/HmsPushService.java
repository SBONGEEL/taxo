package ly.tajora.driver;

import com.huawei.hms.push.HmsMessageService;
import com.huawei.hms.push.RemoteMessage;

import java.util.Map;

/**
 * <b>خدمةُ رسائل HMS Push — نظيرةُ {@code CallMessagingService} في نسخة Huawei</b> (أمرُ المالك ٢٠٢٦-١١-٢٣).
 *
 * <p><b>المنطقُ نفسُه حرفاً</b>: {@code call_ring_stopped} يطوي الرنين، و{@code incoming_call} يرسمه إن لم يكن التطبيقُ أمامَ صاحبه
 * ({@link CallAlert}) — <b>ثمّ تمضي الرسالةُ إلى الصفحة</b> عبر
 * {@link HmsPushPlugin} كما يمضي بها ملحقُ FCM. والإشعارُ الذي يحمل قسمَ {@code notification} يرسمه HMS نفسُه والتطبيقُ غائب.
 *
 * <p><b>ولا يعمل الإرسالُ قبل حساب AppGallery</b>: معرّفُ التطبيق يُخبز من {@code TAXO_HMS_APP_ID} في البناء، وغيابُه نسخةٌ بلا رمز.
 */
public class HmsPushService extends HmsMessageService {

    @Override
    public void onNewToken(String token) {
        HmsPushPlugin.token(token);
        // **وإلى حدث ملحق الإشعارات نفسِه** — الصفحةُ تنتظر الرمزَ في {@code registration}
        com.capacitorjs.plugins.pushnotifications.PushNotificationsPlugin.onNewToken(token);
    }

    @Override
    public void onMessageReceived(RemoteMessage message) {
        Map<String, String> data = message.getDataOfMap();
        String type = data.get("type");
        if (CallAlert.STOP.equals(type)) {
            CallAlert.cancel(this, data.get(CallAlert.EXTRA_CALL_ID));
            return;
        }
        if (CallAlert.RING.equals(type) && message.getNotification() == null && !CallAlert.appInFront(this)) {
            try {
                CallAlert.show(this, data, message.getMessageId(), message.getSentTime());
            } catch (RuntimeException failed) {
                // **لا يُسقط رسمُ الرنين ما بعده** — كما في خدمة FCM
            }
        }
        HmsPushPlugin.message(data);
    }
}
