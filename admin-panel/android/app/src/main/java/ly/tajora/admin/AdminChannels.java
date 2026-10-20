package ly.tajora.admin;

import android.app.NotificationChannel;
import android.app.NotificationChannelGroup;
import android.app.NotificationManager;
import android.content.Context;
import android.media.AudioAttributes;
import android.net.Uri;
import android.os.Build;

/**
 * <b>قنواتُ إشعارات المالك — قناةٌ لكلِّ فئةٍ بصوتها واهتزازها</b> (SPEC §٨١/١١، أمرُ المالك ٢٠٢٦-١٠-٢٠).
 *
 * <p><b>ولمَ قناةٌ لكلِّ فئة</b>: بنصِّ المالك «كلُّ فئةٍ قناةٌ مستقلّة، فيُضبط صوتُها واهتزازُها وحدَها» — وأندرويد يملّك المستخدمَ
 * صوتَ القناة وأهميّتَها بعد إنشائها، فقناةٌ واحدةٌ تجعل الذروةَ والمشكلةَ صوتاً واحداً. <b>والأصواتُ مولَّدةٌ لا منسوخة</b>
 * ({@code design/admin-alerts/make_sounds.py}).
 *
 * <p><b>والرحلاتُ أهميّتُها «افتراضيّة» لا «عالية»</b>: تُسمع نقرتُها ولا تنبثق فوق الشاشة — «فلا تصخب الذروة». <b>والمعرّفاتُ هي
 * {@code tone} في الخادم حرفاً</b> ({@code services/admin_alerts.TONES}) بسابقة {@code taxo.admin.}.
 */
final class AdminChannels {

    static final String PREFIX = "taxo.admin.";
    static final String GROUP = "taxo.admin.activity";
    /** <b>قناةُ الافتراض</b> — ما يرسمه النظامُ من إشعارات اللوحة القائمة (تأكيدُ تحويل كليك) يقع فيها لا في احتياطيّة FCM. */
    static final String GENERAL = "taxo.admin.general";

    /** الفئة · اسمُها في إعدادات أندرويد · {@code true} إن كانت تنبثق فوق الشاشة · نمطُ الاهتزاز ({@code null} بلا اهتزاز). */
    private static final Object[][] TONES = {
        {"money_in", "مالٌ داخل — دفعاتٌ وشحنٌ واشتراكات", true, new long[] {0, 110, 70, 110}},
        {"money_out", "مالٌ خارج أو معلَّق — سحبٌ واستردادٌ وتسويات", true, new long[] {0, 180}},
        {"account", "حساباتٌ جديدة ووثائقُ الكباتن", true, new long[] {0, 140}},
        {"problem", "مشكلات — دفعٌ فشل وشكاوى وتقييمٌ منخفض وسقفُ الدَّين", true, new long[] {0, 260, 120, 260, 120, 260}},
        {"ride", "الرحلات — طلبٌ وقبولٌ واكتمالٌ وإلغاء", false, null},
        {"feedback", "رسائلُ «أرسل ملاحظة»", true, new long[] {0, 90, 60, 90}},
    };

    private AdminChannels() {}

    static String id(String tone) {
        return PREFIX + tone;
    }

    /** <b>هل الفئةُ معروفة؟</b> — فئةٌ يرسلها خادمٌ أحدثُ من الحزمة تقع في قناة «الحسابات» لا في قناةٍ لا وجودَ لها. */
    static String known(String tone) {
        for (Object[] row : TONES) {
            if (row[0].equals(tone)) return tone;
        }
        return "account";
    }

    /** يُنادى من {@link MainActivity#onCreate} <b>ومن {@link AdminAlertNotifier#show} قبل أن يرسم</b> — الإشعارُ يصل والتطبيقُ مقتول. */
    static void ensure(Context context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        if (manager == null) return;
        manager.createNotificationChannelGroup(new NotificationChannelGroup(GROUP, "إشعاراتُ النشاط"));
        for (Object[] row : TONES) {
            String tone = (String) row[0];
            if (manager.getNotificationChannel(id(tone)) != null) continue;
            int importance = (Boolean) row[2] ? NotificationManager.IMPORTANCE_HIGH : NotificationManager.IMPORTANCE_DEFAULT;
            NotificationChannel channel = new NotificationChannel(id(tone), (String) row[1], importance);
            channel.setGroup(GROUP);
            channel.setSound(sound(context, tone), new AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_NOTIFICATION)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build());
            long[] pattern = (long[]) row[3];
            channel.enableVibration(pattern != null);
            if (pattern != null) channel.setVibrationPattern(pattern);
            channel.enableLights(true);
            channel.setLightColor(0xFFF05A28);
            manager.createNotificationChannel(channel);
        }
        if (manager.getNotificationChannel(GENERAL) == null) {
            manager.createNotificationChannel(
                    new NotificationChannel(GENERAL, "إشعاراتُ اللوحة", NotificationManager.IMPORTANCE_HIGH));
        }
    }

    /** صوتُ الفئة من {@code res/raw/alert_<الفئة>.ogg} — <b>باسم الحزمة المثبَّتة</b> (حزمةُ التجربة {@code .test}). */
    static Uri sound(Context context, String tone) {
        int raw = context.getResources().getIdentifier("alert_" + tone, "raw", context.getPackageName());
        return Uri.parse("android.resource://" + context.getPackageName() + "/" + raw);
    }
}
