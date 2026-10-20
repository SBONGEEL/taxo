package ly.tajora.admin;

import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;

import androidx.core.app.NotificationCompat;
import androidx.core.app.NotificationManagerCompat;

import java.util.Map;

/**
 * <b>يرسم إشعارَ المالك كما وافق عليه</b> (SPEC §٨١/٦–٧): أيقونةُ الشريط علامةُ TAXO بالأبيض ({@code ic_stat_taxo}) وبرتقاليُّها
 * لوناً، <b>وأيقونةٌ كبيرةٌ بفئة الحدث</b> ({@code drawable-nodpi/alert_large_*})، وعنوانٌ ونصّ، و«افتح» و«مقروء».
 *
 * <p><b>والنصُّ من الخادم</b> ({@code title}/{@code body} في البيانات — {@code services/admin_alerts.tray_text}): نوعٌ وسوقٌ ومبلغٌ
 * بلا اسمٍ ولا رقم، <b>فيُعرض على شاشة القفل كما هو</b> ({@code VISIBILITY_PUBLIC}) — التفاصيلُ في اللوحة بعد الدخول.
 *
 * <p><b>والصفُّ المجموعُ يستبدل إشعارَه بلا صوتٍ ثانٍ</b>: المفتاحُ {@code tag} (النوعُ والسوق) هو وسمُ الإشعار، و{@code bumped}
 * يجعله {@code onlyAlertOnce} — فالذروةُ إشعارٌ واحدٌ يكبر عددُه لا عشرون.
 */
final class AdminAlertNotifier {

    static final String ACTION_OPEN = "ly.tajora.admin.ALERT_OPEN";
    static final String EXTRA_RECORD_TYPE = "record_type";
    static final String EXTRA_RECORD_ID = "record_id";
    static final String EXTRA_KIND = "kind";
    static final String EXTRA_ALERT_ID = "alert_id";
    static final String EXTRA_USER_ID = "user_id";
    static final String EXTRA_TOKEN = "read_token";
    static final String EXTRA_TAG = "tag";
    static final String EXTRA_NOTIFICATION_ID = "notification_id";

    private AdminAlertNotifier() {}

    static int notificationId(String tag) {
        return 81_000 + (tag.hashCode() & 0x7fff);
    }

    static void show(Context context, Map<String, String> data) {
        AdminChannels.ensure(context);
        String tone = AdminChannels.known(value(data, "tone", "account"));
        String tag = value(data, "tag", value(data, "alert_id", "taxo-admin"));
        int id = notificationId(tag);

        Intent open = new Intent(context, MainActivity.class)
                .setAction(ACTION_OPEN)
                .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP)
                .putExtra(EXTRA_RECORD_TYPE, value(data, "record_type", ""))
                .putExtra(EXTRA_RECORD_ID, value(data, "record_id", ""))
                .putExtra(EXTRA_KIND, value(data, "kind", ""))
                .putExtra(EXTRA_ALERT_ID, value(data, "alert_id", ""))
                .putExtra(EXTRA_USER_ID, value(data, "user_id", ""))
                .putExtra(EXTRA_TOKEN, value(data, "read_token", ""))
                .putExtra(EXTRA_TAG, tag)
                .putExtra(EXTRA_NOTIFICATION_ID, id);
        int flags = PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE;
        PendingIntent openIntent = PendingIntent.getActivity(context, id, open, flags);

        String title = value(data, "title", "TAXO");
        String body = value(data, "body", "");
        NotificationCompat.Builder builder = new NotificationCompat.Builder(context, AdminChannels.id(tone))
                .setSmallIcon(R.drawable.ic_stat_taxo)
                .setColor(0xFFF05A28)
                .setLargeIcon(largeIcon(context, tone))
                .setContentTitle(title)
                .setContentText(body)
                .setStyle(new NotificationCompat.BigTextStyle().bigText(body))
                .setContentIntent(openIntent)
                .setAutoCancel(true)
                .setCategory(NotificationCompat.CATEGORY_EVENT)
                .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
                .setOnlyAlertOnce("1".equals(data.get("bumped")))
                .setShowWhen(true)
                .setWhen(System.currentTimeMillis())
                .setPriority("ride".equals(tone)
                        ? NotificationCompat.PRIORITY_DEFAULT
                        : NotificationCompat.PRIORITY_HIGH)
                .addAction(0, "افتح", openIntent);

        String token = value(data, "read_token", "");
        if (!token.isEmpty()) {
            Intent read = new Intent(context, AdminAlertReadReceiver.class)
                    .putExtra(EXTRA_ALERT_ID, value(data, "alert_id", ""))
                    .putExtra(EXTRA_USER_ID, value(data, "user_id", ""))
                    .putExtra(EXTRA_TOKEN, token)
                    .putExtra(EXTRA_TAG, tag)
                    .putExtra(EXTRA_NOTIFICATION_ID, id);
            builder.addAction(0, "مقروء", PendingIntent.getBroadcast(context, id, read, flags));
        }

        try {
            NotificationManagerCompat.from(context).notify(tag, id, builder.build());
        } catch (SecurityException denied) {
            // **لا إذنَ إشعاراتٍ بعد** (أندرويد ١٣) — الجرسُ في اللوحة يبقى، ولا يُسقط ذلك شيئاً
        }
    }

    private static Bitmap largeIcon(Context context, String tone) {
        int res = context.getResources().getIdentifier("alert_large_" + tone, "drawable", context.getPackageName());
        return res == 0 ? null : BitmapFactory.decodeResource(context.getResources(), res);
    }

    private static String value(Map<String, String> data, String key, String fallback) {
        String found = data.get(key);
        return found == null || found.isEmpty() ? fallback : found;
    }
}
