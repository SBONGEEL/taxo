package ly.tajora.rider;

import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;

import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * <b>إشعارُ التتبّع الحيّ للراكب</b> (SPEC §١٠٣ B/19) — إشعارٌ واحدٌ مستمرٌّ على قناة {@link RideNotice#LIVE} الصامتة،
 * <b>يتبدّل سطرُه بحال الرحلة</b> (في الطريق خلال N د ← وصل ← في الرحلة) ويُزال حين تنتهي.
 *
 * <p><b>والويبُ يكتبه ويمحوه</b>، ولا يُنشئ الإشعارَ شيءٌ غيرُه: لا حالَ يعيش هنا فيكذب بعد رحلةٍ انتهت. <b>ومعرّفُه ثابت</b>
 * (الوسمُ {@code live} والرقم {@value #ID}) فكلُّ كتابةٍ تحلّ محلَّ سابقتها ولا تتراكم.
 */
@CapacitorPlugin(name = "RideLive")
public class RideLivePlugin extends Plugin {

    static final int ID = 4121;
    static final String TAG = "live";

    /** <b>أيُرسم؟</b> — خالصٌ ومختبَر: بلا عنوانٍ لا إشعار، فلا يبقى إشعارٌ فارغٌ مستمرّ. */
    static boolean drawable(String title) {
        return title != null && !title.trim().isEmpty();
    }

    @PluginMethod
    public void show(PluginCall call) {
        String title = call.getString("title");
        if (!drawable(title)) {
            clear(call);
            return;
        }
        Context context = getContext();
        RideNotice.ensureChannel(context);
        Intent open = new Intent(context, MainActivity.class)
                .setAction(Intent.ACTION_VIEW)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent tap = PendingIntent.getActivity(context, ID, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        String text = call.getString("text", "");
        NotificationCompat.Builder builder = new NotificationCompat.Builder(context, RideNotice.LIVE)
                .setSmallIcon(R.drawable.ic_stat_taxo)
                .setContentTitle(title.trim())
                .setContentText(text)
                .setOngoing(true)
                .setOnlyAlertOnce(true)
                .setSilent(true)
                .setCategory(NotificationCompat.CATEGORY_TRANSPORT)
                .setPriority(NotificationCompat.PRIORITY_LOW)
                .setContentIntent(tap);
        try {
            NotificationManagerCompat.from(context).notify(TAG, ID, builder.build());
        } catch (SecurityException noPermission) {
            // إذنُ الإشعارات مسحوب — الشاشةُ تعرض الحالَ حين تُفتح
        }
        call.resolve();
    }

    @PluginMethod
    public void clear(PluginCall call) {
        NotificationManagerCompat.from(getContext()).cancel(TAG, ID);
        call.resolve();
    }
}
