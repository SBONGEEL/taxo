package ly.tajora.driver;

import androidx.annotation.NonNull;

import com.capacitorjs.plugins.pushnotifications.MessagingService;
import com.google.firebase.messaging.RemoteMessage;

import java.util.Map;

/**
 * <b>خدمةُ الرسائل — خدمةُ ملحق الإشعارات نفسُها، ومعها رنينُ المكالمة</b> (SPEC §٦٦-ج/١٧، الحزمةُ «2.0»).
 *
 * <p><b>ولمَ وراثةٌ لا خدمةٌ ثانية</b>: {@code FirebaseMessagingService} واحدٌ يستقبل — خدمتان على
 * {@code MESSAGING_EVENT} تُسقط إحداهما الأخرى، <b>فتنقطع بطاقةُ الطلب نفسُها</b> إن أخطأ ترتيبُهما. فهذه ترث خدمةَ
 * الملحق ({@code com.capacitorjs.plugins.pushnotifications.MessagingService})، <b>والبيانُ ينزع تلك ويسجّل هذه</b>
 * ({@code tools:node="remove"}) — <b>وكلُّ رسالةٍ تمرّ بـ{@code super}</b> فيصل الويبَ ما يصله اليومَ حرفاً، ويصل
 * الرمزُ الجديدُ ({@code onNewToken}) بالوراثة.
 *
 * <p><b>وما تزيده اثنتان لا غير</b>، وكلاهما بياناتٌ وحدَها لا يرسلها الخادمُ إلا لجهازٍ بلّغ بقناة المكالمة:
 * <ul>
 *   <li>{@code incoming_call} — <b>يرسم الرنينَ إن لم يكن التطبيقُ أمامَ صاحبه</b> ({@link CallAlert})، <b>ثمّ يمضي
 *       إلى الملحق</b> كما هو. ورسالةٌ تحمل قسمَ {@code notification} لا تُرسم هنا: النظامُ يرسمها والتطبيقُ في الخلفية،
 *       ولا تصل هنا إلا والتطبيقُ مفتوح.</li>
 *   <li>{@code call_ring_stopped} — <b>يطوي رنينَ تلك المكالمة ولا يمضي إلى الويب</b>: أمرٌ لهذه الخدمة لا خبر.</li>
 * </ul>
 */
public class CallMessagingService extends MessagingService {

    @Override
    public void onMessageReceived(@NonNull RemoteMessage remoteMessage) {
        Map<String, String> data = remoteMessage.getData();
        String type = data.get("type");
        if (CallAlert.STOP.equals(type)) {
            CallAlert.cancel(this, data.get(CallAlert.EXTRA_CALL_ID));
            return;
        }
        if (CallAlert.RING.equals(type)
                && remoteMessage.getNotification() == null
                && !CallAlert.appInFront(this)) {
            try {
                // **ومعها لحظةُ إرسالها** — يُطرح الطريقُ من عمر الرنين (`CallAlert.lifetimeMs`)
                CallAlert.show(this, data, remoteMessage.getMessageId(), remoteMessage.getSentTime());
            } catch (RuntimeException failed) {
                // **لا يُسقط رسمُ الرنين ما بعده**: الرسالةُ تمضي إلى الملحق كما تمضي اليوم، والمكالمةُ تُرى حين يُفتح التطبيق
            }
        }
        super.onMessageReceived(remoteMessage);
    }
}
