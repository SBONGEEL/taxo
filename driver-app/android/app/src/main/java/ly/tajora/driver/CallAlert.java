package ly.tajora.driver;

import android.app.KeyguardManager;
import android.app.Notification;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.media.AudioAttributes;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.service.notification.StatusBarNotification;

import java.util.Iterator;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;

/**
 * <b>رنينُ المكالمة والتطبيقُ مغلق</b> (SPEC §٦٦-ج/١٧، الحزمةُ «2.0») — إشعارُ مكالمةٍ على قناة
 * {@link TaxoChannels#CALL} <b>يرنّ حتى يُردّ عليه أو يُرفض أو ينقضي</b>، كمكالمة هاتف. <b>على غرار
 * {@link OfferAlert}</b>: القفلُ، وملءُ الشاشة بـ{@code canUseFullScreenIntent}، والتكرارُ بـ{@code FLAG_INSISTENT}.
 *
 * <h3>من يرنّ متى — واحدٌ لا اثنان</h3>
 * <ul>
 *   <li><b>التطبيقُ أمامَ صاحبه</b>: الويبُ يرنّ على شاشته من المقبس، <b>ولا يُرسم هنا شيء</b>
 *       ({@link #appInFront}).</li>
 *   <li><b>في الخلفية، أو مغلق، أو الشاشةُ مقفلة</b>: هذا الإشعار — <b>ويُطوى حين يظهر التطبيق</b>
 *       ({@link #onAppShown})، والشاشةُ ترنّ بعده: الخادمُ يعيد الرنينَ القائمَ مع فتح المقبس
 *       ({@code ride_calls.ringing_frame})، ونقرةُ الإشعار تمرّ بـ{@code routeCommsPush} كما اليوم.</li>
 * </ul>
 *
 * <h3>ويُطوى بأربعة</h3>
 * <ol>
 *   <li><b>أمرُ الخادم</b> ({@code call_ring_stopped}): رُدّ عليها من جهازٍ آخر، أو رُفضت، أو قطعها المتصل، أو
 *       فاتت، أو انتهت الرحلة.</li>
 *   <li><b>عمرُها</b> — {@code setTimeoutAfter} بما بقي من ثلاثينها ({@code expires_in_seconds} من الخادم)
 *       <b>ناقصاً ما قضته الرسالةُ في الطريق</b> ({@link #lifetimeMs}).</li>
 *   <li><b>«رفض»</b> — يطويه هنا وحدَه ({@link CallDeclineReceiver}): <b>لا رمزَ دخولٍ في الشيفرة الأصليّة</b>،
 *       فالمكالمةُ عند الخادم ترنّ حتى ثلاثينها ثمّ تُكتب فائتة.</li>
 *   <li><b>ظهورُ التطبيق</b> — «افتح للردّ» والنقرُ وملءُ الشاشة كلُّها تفتحه — <b>وفتحُ القفل والتطبيقُ أمامه</b>
 *       ({@link #onAppFocused}): الظهورُ خلف القفل لا يطويه، وفتحُ القفل لا يُعيد {@code onResume} دائماً.</li>
 * </ol>
 *
 * <h3>وحدُّ ملء الشاشة — مكتوبٌ لا مسكوتٌ عنه</h3>
 * <p>النيّةُ {@link MainActivity} لا شاشةٌ أصليّة، <b>و{@code MainActivity} لا يُعرض فوق القفل — ولا يجوز</b>:
 * التطبيقُ كلُّه (المحفظةُ وما فيها) يصير بلا قفل. <b>فالهاتفُ المقفلُ يُضاء ويرنّ ويعرض الإشعارَ على شاشة القفل،
 * و«افتح للردّ» يطلب فتحَ القفل أوّلاً</b> (يطلبه النظامُ نفسُه). وشاشةُ مكالمةٍ أصليّةٌ فوق القفل — كـ{@link OfferActivity}
 * — بندٌ مستقلّ.
 */
public final class CallAlert {

    /** نوعُ الرنين — {@code TripCommsEvent.INCOMING_CALL} في الخادم حرفاً. */
    static final String RING = "incoming_call";
    /** أمرُ الإسكات — {@code push/channels.py → CALL_RING_STOPPED} حرفاً. */
    static final String STOP = "call_ring_stopped";
    /** معرّفُ المكالمة في الحمولة وفي نيّة «رفض». */
    static final String EXTRA_CALL_ID = "call_id";

    /** <b>والوسمُ معرّفُ المكالمة</b> — فأمرُ إسكاتِ مكالمةٍ لا يطوي غيرَها. */
    static final int NOTIFICATION_ID = 4303;

    /** عمرُ الرنين إن غاب عن الحمولة — ثلاثون الخادم ({@code RING_TIMEOUT_SECONDS}). */
    private static final int DEFAULT_SECONDS = 30;
    /** <b>سقفٌ لعمرٍ فاسد</b>: رنينٌ لا ينتهي أسوأُ من رنينٍ قصير. */
    private static final int MAX_SECONDS = 60;
    /** <b>أرضيّةُ ما بعد طرح الطريق</b> ({@link #lifetimeMs}): رنينٌ أقصرُ من أن يُرى لا رنين. */
    private static final int MIN_SECONDS = 5;

    /**
     * <b>زرُّ الفتح باسمه</b>: يفتح التطبيقَ ولا يردّ — <b>والردُّ نفسُه «ردّ» في شاشة التطبيق</b>: هناك يُسأل الميكروفون
     * ويُقَرّ بتنبيه التسجيل (§٦٦-د/٣)، ولا يجيب الخادمُ ردّاً بلاه. <b>وكان «ردّ»</b> — فمن ضغطه ظنّ نفسَه في مكالمةٍ
     * وهو أمام شاشةٍ ترنّ.
     */
    private static final String ANSWER_LABEL = "افتح للردّ";

    /** نصٌّ احتياطيٌّ لا يُرى إلا إن غاب نصُّ الخادم من الحمولة — <b>والنصُّ بيتُه الخادم</b> ({@code CALL_PUSH_TITLE}). */
    private static final String FALLBACK_TITLE = "مكالمةٌ واردة";
    private static final String FALLBACK_BODY = "افتح التطبيق للرد";
    /** <b>التنبيهُ يسبق «ردّ»</b> (§٦٦-د/٣) — والإقرارُ نفسُه في شاشة التطبيق، والخادمُ يرفض الردَّ بلاه. */
    private static final String RECORDED_NOTE = "هذه المكالمةُ مسجَّلة";

    private static final Handler MAIN = new Handler(Looper.getMainLooper());

    /** <b>أمامَ صاحبه الآن</b> — يُكتب من {@link MainActivity}، ويضيع مع العملية (فالمقتولُ ليس أمامَ أحد). */
    private static volatile boolean inApp;

    /**
     * <b>مكالماتٌ سكت رنينُها للتوّ</b> — FCM لا يضمن الترتيب: أمرُ الإسكات قد يسبق الرنينَ نفسَه (قطعها المتصلُ في
     * ثانيتها الأولى)، <b>فرنينٌ يصل بعد إسكاته لا يُرسم</b>، وإلا رنّ ثلاثين ثانيةً لمكالمةٍ انتهت. <b>في ذاكرة العملية
     * وحدَها وبسقف</b> — يكفي ما بين رسالتين متتاليتين، وعمرُ الرنين حدُّ ما يفوته.
     */
    private static final Set<String> STOPPED = new LinkedHashSet<>();
    private static final int STOPPED_KEPT = 16;

    private CallAlert() {}

    /** {@link MainActivity#onResume}: <b>ظهر التطبيقُ فالشاشةُ ترنّ بعد الآن</b> — إلا خلف القفل. */
    static void onAppShown(Context context) {
        inApp = true;
        if (!locked(context)) hideAll(context);
    }

    /** {@link MainActivity#onPause}. */
    static void onAppHidden() {
        inApp = false;
    }

    /**
     * {@link MainActivity#onWindowFocusChanged}: <b>نال التطبيقُ التركيزَ — وفُتح القفلُ وهو أمامه</b>.
     *
     * <p>{@link #onAppShown} يتخطّى الطيَّ خلف القفل، <b>و{@code onResume} قد يقع وحركةُ فتح القفل جارية</b>
     * ({@code isKeyguardLocked} ما زال صادقاً) أو قبلها والهاتفُ مقفل — <b>ثمّ لا يتكرّر حين يزول القفل</b>، فيبقى الرنينُ
     * يدوّي فوق شاشةٍ ترنّ هي الأخرى. <b>والتركيزُ لا يناله نشاطٌ خلف القفل</b>، فنيلُه بعد زواله هو اللحظةُ التي فاتت.
     * <b>ولا يكتب {@code inApp}</b>: ذاك لـ{@code onResume}/{@code onPause} وحدَهما.
     */
    static void onAppFocused(Context context) {
        if (inApp && !locked(context)) hideAll(context);
    }

    /** <b>أيرنّ الويبُ الآن بنفسه؟</b> — ظاهرٌ وغيرُ مقفل. */
    static boolean appInFront(Context context) {
        return inApp && !locked(context);
    }

    private static boolean locked(Context context) {
        KeyguardManager keyguard = context.getSystemService(KeyguardManager.class);
        PowerManager power = context.getSystemService(PowerManager.class);
        boolean asleep = power != null && !power.isInteractive();
        return asleep || (keyguard != null && keyguard.isKeyguardLocked());
    }

    private static boolean canUseFullScreen(NotificationManager manager) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.UPSIDE_DOWN_CAKE) return true;
        return manager.canUseFullScreenIntent();
    }

    /**
     * <b>يرسم الرنين</b> من حمولة {@code incoming_call} كما وصلت. <b>ونيّةُ الفتح تحمل الحمولةَ نفسَها ومعها
     * {@code google.message_id}</b> — به يعرفها ملحقُ الإشعارات نقرةَ إشعارٍ فيُطلق
     * {@code pushNotificationActionPerformed}، فتمرّ بـ{@code routeCommsPush} كأيِّ نقرةٍ اليوم ولا بابَ جديدٌ في الويب.
     *
     * <p>{@code sentAtMs} لحظةُ قبول FCM للرسالة ({@code RemoteMessage.getSentTime}) — <b>بها يُطرح الطريقُ من عمرها</b>.
     */
    static void show(Context context, Map<String, String> data, String messageId, long sentAtMs) {
        String callId = data.get(EXTRA_CALL_ID);
        if (callId == null || callId.isEmpty() || wasStopped(callId)) return;
        TaxoChannels.ensure(context);
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        if (manager == null) return;
        long lifetimeMs = lifetimeMs(data.get("expires_in_seconds"), sentAtMs, System.currentTimeMillis());
        int code = callId.hashCode();

        Intent open = new Intent(context, MainActivity.class)
                .setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        for (Map.Entry<String, String> entry : data.entrySet()) {
            open.putExtra(entry.getKey(), entry.getValue());
        }
        open.putExtra("google.message_id", messageId != null ? messageId : callId);
        PendingIntent opening = PendingIntent.getActivity(context, code, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Intent decline = new Intent(context, CallDeclineReceiver.class).putExtra(EXTRA_CALL_ID, callId);
        PendingIntent declining = PendingIntent.getBroadcast(context, code + 1, decline,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(context, TaxoChannels.CALL)
                : new Notification.Builder(context);
        builder.setContentTitle(textOr(data.get("title"), FALLBACK_TITLE))
                .setContentText(textOr(data.get("body"), FALLBACK_BODY))
                // **أيقونةُ الشريط أحاديّةُ اللون** (`ic_stat_taxo`): أيقونةُ التشغيل التكيّفيّة هنا تُسقط واجهةَ النظام على أندرويد ٨٫٠
                .setSmallIcon(R.drawable.ic_stat_taxo)
                .setCategory(Notification.CATEGORY_CALL)
                .setVisibility(Notification.VISIBILITY_PUBLIC)
                .setAutoCancel(true)
                .setContentIntent(opening)
                .addAction(new Notification.Action.Builder(null, "رفض", declining).build())
                .addAction(new Notification.Action.Builder(null, ANSWER_LABEL, opening).build());
        if ("true".equals(data.get("recording"))) {
            builder.setSubText(RECORDED_NOTE);
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            builder.setTimeoutAfter(lifetimeMs);
        } else {
            // **قبل أندرويد ٨ لا قناة**: الأولويةُ والصوتُ على الإشعار نفسِه — على مجرى الرنين كالقناة
            builder.setPriority(Notification.PRIORITY_MAX)
                    .setSound(TaxoChannels.sound(context, R.raw.taxo_call), new AudioAttributes.Builder()
                            .setUsage(AudioAttributes.USAGE_NOTIFICATION_RINGTONE)
                            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                            .build());
        }
        if (canUseFullScreen(manager)) {
            builder.setFullScreenIntent(opening, true);
        }
        Notification notification = builder.build();
        // **يتكرّر صوتُ القناة حتى يُطوى** — صوتُ الرنين ثانيتان، وبلا التكرار يرنّ مرّةً ويسكت والمتصلُ ينتظر
        notification.flags |= Notification.FLAG_INSISTENT;
        manager.notify(callId, NOTIFICATION_ID, notification);

        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            // **ولا `setTimeoutAfter` قبل ٨** — فمؤقّتٌ في العملية، وأمرُ الخادم بعده إن ماتت العملية
            final Context app = context.getApplicationContext();
            MAIN.postDelayed(() -> cancel(app, callId), lifetimeMs);
        }
    }

    /** يطوي رنينَ مكالمةٍ بعينها — <b>ومكالمةٌ أخرى ترنّ لا تُمسّ</b>. */
    static void cancel(Context context, String callId) {
        if (callId == null || callId.isEmpty()) return;
        remember(callId);
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        if (manager != null) manager.cancel(callId, NOTIFICATION_ID);
    }

    private static synchronized void remember(String callId) {
        STOPPED.remove(callId);
        STOPPED.add(callId);
        Iterator<String> oldest = STOPPED.iterator();
        while (STOPPED.size() > STOPPED_KEPT && oldest.hasNext()) {
            oldest.next();
            oldest.remove();
        }
    }

    private static synchronized boolean wasStopped(String callId) {
        return STOPPED.contains(callId);
    }

    /** يطوي كلَّ رنين — <b>من الإشعارات القائمة لا من ذاكرة</b>: العمليةُ التي رسمته قد تكون ماتت. */
    static void hideAll(Context context) {
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        if (manager == null) return;
        for (StatusBarNotification shown : manager.getActiveNotifications()) {
            if (shown.getId() == NOTIFICATION_ID) manager.cancel(shown.getTag(), NOTIFICATION_ID);
        }
    }

    /**
     * <b>ما بقي من الرنين لحظةَ وصوله</b> — عمرُه من الخادم ناقصاً ما قضته الرسالةُ في الطريق ({@code now - sentAtMs}).
     *
     * <p><b>والعلّةُ</b>: الخادمُ يحسب ما بقي لحظةَ الإرسال، <b>ورسالةٌ أخّرتها شبكةٌ ضعيفةٌ أو Doze عشرين ثانيةً كانت ترنّ
     * ثلاثين كاملةً</b> — عشراً منها لمكالمةٍ كتبها الخادمُ فائتة. <b>ولا أقلَّ من خمس</b>: ساعةُ الهاتف قد تسبق ساعةَ FCM
     * فيُحسب الطريقُ أطولَ ممّا كان، ورنينٌ أقصرُ من أن يُرى لا رنين — <b>إلا عمراً أقصرَ منها أصلاً</b> فهو حدُّه.
     * <b>ولا أكثرَ من عمره</b>: ساعةٌ متأخّرةٌ لا تطيله. <b>ولحظةٌ مجهولة</b> ({@code sentAtMs <= 0}) لا يُطرح لها شيء.
     */
    static long lifetimeMs(String raw, long sentAtMs, long nowMs) {
        long full = lifetimeSeconds(raw) * 1000L;
        long transit = sentAtMs > 0 ? Math.max(0L, nowMs - sentAtMs) : 0L;
        long floor = Math.min(MIN_SECONDS * 1000L, full);
        return Math.max(floor, full - transit);
    }

    private static long lifetimeSeconds(String raw) {
        int seconds;
        try {
            seconds = raw != null ? Integer.parseInt(raw.trim()) : DEFAULT_SECONDS;
        } catch (NumberFormatException malformed) {
            // **عمرٌ فاسدٌ لا يُسقط الرنين** — ثلاثون الخادم بدلَه
            seconds = DEFAULT_SECONDS;
        }
        return Math.max(1, Math.min(MAX_SECONDS, seconds));
    }

    private static String textOr(String value, String fallback) {
        return value != null && !value.trim().isEmpty() ? value : fallback;
    }
}
