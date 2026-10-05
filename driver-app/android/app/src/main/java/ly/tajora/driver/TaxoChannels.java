package ly.tajora.driver;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Context;
import android.media.AudioAttributes;
import android.net.Uri;
import android.os.Build;

/**
 * <b>قنواتُ إشعار الكبتن بأصواتها</b> — المجموعةُ الثانية (SPEC §٦١-ل/٣–٥، ٢٠٢٦-١٠-٠٥).
 *
 * <p><b>تُنشأ عند الإقلاع لا عند أوّل إشعار</b>: الإشعارُ الواصلُ والتطبيقُ مغلقٌ يرسمه
 * النظامُ بقناته — <b>وقناةٌ لم تُنشأ بعدُ تُسقطه إلى الاحتياطية بلا صوتها</b>. وكانت قناةُ
 * الطلب تُنشأ كسولاً عند أوّل بطاقةٍ أو أوّل فتحٍ لشاشة الأذونات، وما عداها بلا قناةٍ أصلاً.
 *
 * <p><b>وصوتُ القناة وأهميّتُها يُضبطان مرّةً عند إنشائها</b> (أندرويد) — فلا يُعاد ضبطُ قناةٍ
 * قائمة، والصوتُ الجديدُ معرّفٌ جديد. <b>والمعرّفاتُ هي ما في
 * {@code backend/app/services/push/channels.py} حرفاً</b>، والتطبيقُ يبلّغ الخادمَ أنها عنده
 * ({@code src/lib/push.ts → channelSet}) — <b>فلا يُرسل إليها قبل أن توجد</b>.
 *
 * <p><b>والطلبُ في {@link OfferAlert}</b> — قناتُه على مجرى المنبّه، وهنا يُضمن إنشاؤها مع أخواتها.
 * <b>وما يصل الراكبَ وحدَه</b> (قَبِل، يقترب، وصل، بدأت) <b>لا قناةَ له هنا</b>: لا يصل الكبتن.
 */
final class TaxoChannels {

    /** «انتهت الرحلة» — بانتظار اختيار الراكب طريقةَ الدفع. */
    static final String ENDED = "taxo.ended";
    /** «نجح دفعٌ أو شحن» — مالٌ وصل: بقشيشٌ أو مكافأة. */
    static final String PAYMENT = "taxo.payment";
    /** <b>العامّ — وقناةُ الافتراض في البيان</b>: ما لا قناةَ له يقع فيها بصوت «الإشعار». */
    static final String GENERAL = "taxo.general";

    private TaxoChannels() {}

    /** يُنادى من {@link MainActivity#onCreate} — <b>ولا يكلّف شيئاً بعد أوّل مرّة</b>. */
    static void ensure(Context context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        if (manager == null) return;
        OfferAlert.ensureChannel(context);
        create(context, manager, ENDED, "انتهاء الرحلة",
                NotificationManager.IMPORTANCE_HIGH, R.raw.taxo_ended);
        create(context, manager, PAYMENT, "المدفوعات",
                NotificationManager.IMPORTANCE_HIGH, R.raw.taxo_payment);
        create(context, manager, GENERAL, "إشعارات عامة",
                NotificationManager.IMPORTANCE_DEFAULT, R.raw.taxo_notify);
    }

    /** عنوانُ صوتٍ من {@code res/raw} — <b>باسم الحزمة المثبَّتة</b> (حزمةُ التجربة {@code .test}). */
    static Uri sound(Context context, int raw) {
        return Uri.parse("android.resource://" + context.getPackageName() + "/" + raw);
    }

    private static void create(Context context, NotificationManager manager,
                               String id, String name, int importance, int raw) {
        if (manager.getNotificationChannel(id) != null) return;
        NotificationChannel channel = new NotificationChannel(id, name, importance);
        channel.setSound(sound(context, raw), new AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_NOTIFICATION)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build());
        manager.createNotificationChannel(channel);
    }
}
