package ly.tajora.admin;

import androidx.annotation.NonNull;

import com.capacitorjs.plugins.pushnotifications.MessagingService;
import com.google.firebase.messaging.RemoteMessage;

import java.util.Map;

/**
 * <b>خدمةُ الرسائل — خدمةُ ملحق الإشعارات نفسُها، ومعها رسمُ إشعار المالك</b> (SPEC §٨١).
 *
 * <p><b>وراثةٌ لا خدمةٌ ثانية</b> — نمطُ {@code CallMessagingService} في تطبيقَي الراكب والكبتن حرفاً: خدمتان على
 * {@code MESSAGING_EVENT} تُسقط إحداهما الأخرى <b>فتنقطع كلُّ إشعارات التطبيق</b>. فالبيانُ ينزع خدمةَ الملحق ويسجّل هذه، <b>وكلُّ
 * رسالةٍ تمرّ بـ{@code super}</b> — فما يصل الويبَ اليومَ يصله حرفاً، والرمزُ الجديدُ يصل بالوراثة.
 *
 * <p><b>وما تزيده واحدةٌ</b>: {@code admin_alert} بياناتٍ وحدَها — <b>ترسمه إن لم يكن التطبيقُ أمامَ صاحبه</b>؛ وأمامَه يسأل الجرسُ
 * ويعزف صوتَ الفئة ({@code lib/alerts.tsx}) فلا إشعاران لحدثٍ واحد.
 */
public class AdminAlertService extends MessagingService {

    @Override
    public void onMessageReceived(@NonNull RemoteMessage remoteMessage) {
        Map<String, String> data = remoteMessage.getData();
        if ("admin_alert".equals(data.get("type"))
                && remoteMessage.getNotification() == null
                && !AdminAlertsPlugin.inFront) {
            try {
                AdminAlertNotifier.show(this, data);
            } catch (RuntimeException failed) {
                // **لا يُسقط الرسمُ ما بعده**: الرسالةُ تمضي إلى الملحق، والجرسُ يحملها حين يُفتح التطبيق
            }
        }
        super.onMessageReceived(remoteMessage);
    }
}
