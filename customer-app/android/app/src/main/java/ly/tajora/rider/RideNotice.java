package ly.tajora.rider;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.os.Build;
import android.text.TextUtils;

import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;

import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Map;

/**
 * <b>إشعارُ الكبتن الغنيّ</b> (SPEC §١٠٣ المرحلة A/12، أمرُ المالك ٢٠٢٦-١١-١٦ و١٨) — قبولُه واقترابُه ووصولُه
 * <b>بصورته ولوحته ومركبته</b>، ومعه زرّا <b>«اتصال»</b> و<b>«دردشة»</b> يفتحان المكالمةَ والمحادثةَ القائمتين في التطبيق.
 *
 * <p><b>يرسمه هذا الملفُّ لا النظام</b> لأن الأزرارَ والصورةَ لا تُحمل في إشعارٍ يرسمه النظام. فالخادمُ يرسل بياناتٍ وحدَها
 * ({@code rich: "1"}) <b>للمجموعة الخامسة ومفتاحِ السوق وحدهما</b> (`push/channels.py`) — <b>وعلى قناة النغمة نفسِها</b>
 * ({@code channel})، فالصوتُ هو ما اختاره الراكب.
 *
 * <p><b>والصورةُ برابطٍ موقَّعٍ لهذه الرحلة ٤٥ دقيقة</b> — تُنزل في خيط الرسالة (مهلةُ أربعِ ثوانٍ)؛ <b>وإن تعذّرت
 * يُرسم الإشعارُ بلا صورة</b> لا يُسقط. <b>ومعرّفُه من الرحلة</b>: «وصل» يحلّ محلَّ «قُبلت» لا يتراكم فوقه.
 *
 * <p><b>وقناةُ {@link #LIVE} هنا</b>: «رحلتك الآن» — صامتةٌ منخفضة، <b>ووجودُها على الجهاز شاهدُ المجموعة الخامسة</b>
 * (`push.ts → channelSet`)، كما شهدت {@code taxo.call} على خدمة الرنين.
 */
final class RideNotice {

    static final String LIVE = "taxo.ride.live";
    static final String ACTION_CALL = "ride_call";
    static final String ACTION_CHAT = "ride_chat";

    private RideNotice() {}

    /** <b>أهذا إشعارٌ غنيٌّ يرسمه الراكب؟</b> — والتطبيقُ أمامه لا يُرسم شيء: الشاشةُ تعرض ما جرى. */
    static boolean handles(Map<String, String> data) {
        return "1".equals(data.get("rich")) && !TextUtils.isEmpty(data.get("ride_id"));
    }

    static void ensureChannel(Context context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        if (manager == null || manager.getNotificationChannel(LIVE) != null) return;
        NotificationChannel channel = new NotificationChannel(LIVE, "رحلتك الآن", NotificationManager.IMPORTANCE_LOW);
        channel.setSound(null, null);
        channel.setShowBadge(false);
        manager.createNotificationChannel(channel);
    }

    static void show(Context context, Map<String, String> data) {
        String rideId = data.get("ride_id");
        String channel = data.get("channel");
        if (TextUtils.isEmpty(channel)) channel = TaxoChannels.GENERAL;

        String title = orEmpty(data.get("title"));
        String body = orEmpty(data.get("body"));
        String plate = orEmpty(data.get("plate"));
        String vehicle = orEmpty(data.get("vehicle"));
        String driver = orEmpty(data.get("driver_name"));
        String card = join(" · ", driver, vehicle, plate);

        NotificationCompat.Builder builder = new NotificationCompat.Builder(context, channel)
                .setSmallIcon(R.drawable.ic_stat_taxo)
                .setContentTitle(title)
                .setContentText(body)
                .setSubText(plate.isEmpty() ? null : plate)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(card.isEmpty() ? body : body + "\n" + card))
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setCategory(NotificationCompat.CATEGORY_TRANSPORT)
                .setAutoCancel(true)
                .setContentIntent(open(context, rideId, null, 0))
                .addAction(0, "اتصال", open(context, rideId, ACTION_CALL, 1))
                .addAction(0, "دردشة", open(context, rideId, ACTION_CHAT, 2));

        Bitmap photo = fetch(data.get("photo_url"));
        if (photo != null) builder.setLargeIcon(photo);

        try {
            NotificationManagerCompat.from(context).notify(tag(rideId), 4120, builder.build());
        } catch (SecurityException noPermission) {
            // إذنُ الإشعارات مسحوب — لا شيءَ يُرسم، والتطبيقُ يعرض الحالَ حين يُفتح
        }
    }

    /** <b>الفعلُ يمرّ بباب المُطلِق القائم</b> ({@link LauncherPlugin#EXTRA}) — فالويبُ وحدَه يفتح المكالمةَ أو المحادثة. */
    private static PendingIntent open(Context context, String rideId, String action, int slot) {
        Intent intent = new Intent(context, MainActivity.class)
                .setAction(Intent.ACTION_VIEW)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        if (action != null) intent.putExtra(LauncherPlugin.EXTRA, action + ":" + rideId);
        int code = (tag(rideId).hashCode() & 0xffff) * 4 + slot;
        return PendingIntent.getActivity(context, code, intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    static String tag(String rideId) {
        return "ride:" + rideId;
    }

    static String join(String separator, String... parts) {
        StringBuilder out = new StringBuilder();
        for (String part : parts) {
            if (part == null || part.isEmpty()) continue;
            if (out.length() > 0) out.append(separator);
            out.append(part);
        }
        return out.toString();
    }

    private static String orEmpty(String value) {
        return value == null ? "" : value;
    }

    /** <b>https وحدَه</b>، ومهلةٌ قصيرة، وسقفُ حجم — رابطٌ غريبٌ لا يُنزَل ولا يُعلِّق الخيط. */
    private static Bitmap fetch(String url) {
        if (url == null || !(url.startsWith("https://") || url.startsWith("http://10.0.2.2"))) return null;
        HttpURLConnection connection = null;
        try {
            connection = (HttpURLConnection) new URL(url).openConnection();
            connection.setConnectTimeout(4000);
            connection.setReadTimeout(4000);
            connection.setInstanceFollowRedirects(false);
            if (connection.getResponseCode() != 200) return null;
            if (connection.getContentLength() > 2_000_000) return null;
            try (InputStream in = connection.getInputStream()) {
                return BitmapFactory.decodeStream(in);
            }
        } catch (Exception failed) {
            return null;
        } finally {
            if (connection != null) connection.disconnect();
        }
    }
}
