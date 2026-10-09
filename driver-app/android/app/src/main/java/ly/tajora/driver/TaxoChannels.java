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
    /**
     * <b>المكالمةُ الواردة — المجموعةُ الثالثة</b> (§٦٦-ج/١٧، الحزمةُ «2.0»). <b>يرسمها {@link CallAlert}
     * لا النظام</b>: الخادمُ يرسلها بياناتٍ وحدَها لجهازٍ بلّغ بهذه القناة ({@code src/lib/push.ts → channelSet})،
     * <b>فوجودُها شاهدٌ على الخدمة</b> — وهما في الحزمة نفسِها.
     */
    static final String CALL = "taxo.call";

    private TaxoChannels() {}

    /**
     * يُنادى من {@link MainActivity#onCreate}، <b>ومن {@link CallAlert#show} قبل أن يرسم</b>: الرنينُ يصل والتطبيقُ مقتول
     * فلا {@code onCreate} قبله، وإشعارٌ على قناةٍ لم تُنشأ لا يُرسم — <b>ولا يكلّف شيئاً بعد أوّل مرّة</b>.
     */
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
        createCall(context, manager);
    }

    /**
     * <b>قناةُ المكالمة — على مجرى الرنين لا الإشعار ولا المنبّه</b>: تسكت حيث يسكت رنينُ الهاتف (الصامت)
     * وتهتزّ حيث يهتزّ، <b>كمكالمةٍ حقيقيّة</b> — <b>بخلاف الطلب</b> الذي يصيح على مجرى المنبّه ولو كان صامتاً.
     * <b>وصوتُها رنينُ المكالمة داخل التطبيق نفسُه</b> ({@code taxo_call} = {@code request.mp3} في
     * {@code src/lib/sound.ts → callRing}) — فلا تفترق نغمتان لحدثٍ واحد. <b>وتكرارُه من الإشعار</b>
     * ({@code FLAG_INSISTENT} في {@link CallAlert}) لا من الملفّ.
     */
    private static void createCall(Context context, NotificationManager manager) {
        if (manager.getNotificationChannel(CALL) != null) return;
        NotificationChannel channel = new NotificationChannel(
                CALL, "المكالمات الواردة", NotificationManager.IMPORTANCE_HIGH);
        channel.setDescription("مكالمةُ الراكب أثناء الرحلة — ترنّ والتطبيقُ مغلق.");
        channel.enableVibration(true);
        channel.setVibrationPattern(new long[] {0, 350, 200, 350});
        channel.setSound(sound(context, R.raw.taxo_call), new AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_NOTIFICATION_RINGTONE)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build());
        manager.createNotificationChannel(channel);
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
