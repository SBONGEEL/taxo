package ly.tajora.driver;

import android.app.KeyguardManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.media.AudioAttributes;
import android.net.Uri;
import android.os.Build;
import android.os.PowerManager;
import android.os.SystemClock;
import android.provider.Settings;

import java.util.Map;

/**
 * <b>أيُّ الأربع تُستعمل الآن</b> — وقاعدةُ التصميم: «أوّلُ طريقةٍ متاحةٍ
 * تُستعمل، والبقيّةُ تُلغى، فلا يستقبل السائقُ البلاغَ نفسَه مرّتين».
 *
 * <h3>الترتيب كما رُسم</h3>
 * <ol>
 *   <li><b>بطاقةٌ داخل التطبيق</b> — يتولّاها الويب، ولا يُنادى هذا الملفُّ
 *       أصلاً حين تكون الشاشةُ ظاهرة.</li>
 *   <li><b>ورقةٌ سفليّة</b> — والتطبيقُ في الخلفيةِ وهاتفُه بيده.</li>
 *   <li><b>فقاعةٌ عائمة</b> — وهو خارجُ التطبيق تماماً.</li>
 *   <li><b>إشعارُ ملء الشاشة</b> — والشاشةُ مقفلةٌ أو الإذنُ مرفوض.</li>
 * </ol>
 *
 * <h3>وحدّان من المنصّة، مكتوبان لا مسكوتٌ عنهما (قرارُ المالك 2026-08-30)</h3>
 * <p><b>١ — الورقةُ والفقاعةُ إذنٌ واحد.</b> كلُّ ما يُرسم فوق تطبيقٍ آخر يمرّ
 * بـ{@code SYSTEM_ALERT_WINDOW}، <b>فرفضُ الإذن يُسقط الاثنتين معاً</b> ولا
 * تنجو إحداهما. ومن رفضه ينزل إلى ملء الشاشة، فإن مُنع ذلك أيضاً فإشعارٌ بأقصى
 * أهميّة — <b>ولا يبقى بلا شيء</b>.
 *
 * <p><b>٢ — {@code USE_FULL_SCREEN_INTENT} قد ينزعه المتجر</b> عن غير تطبيقات
 * المكالمات (أندرويد ١٤ فما فوق). <b>فيُقرأ حيّاً</b> بـ
 * {@code canUseFullScreenIntent} ولا يُفترض، والبديلُ إشعارٌ بأقصى أهميّةٍ
 * يحمل المهلةَ والأجرةَ وزرّاً يفتح التطبيق.
 *
 * <h3>و«في تطبيقٍ آخر» مقابل «خارج التطبيق تماماً»</h3>
 * <p><b>أندرويد لا يعطي هذا الفرقَ بلا إذنٍ خاصّ</b> ({@code PACKAGE_USAGE_STATS})
 * — لا API يقول أيُّ تطبيقٍ في المقدّمة. <b>والإشارةُ المتاحةُ هي قربُ العهد
 * بتطبيقنا</b>: من غادر شاشتَنا قبل دقائقَ ما زال يستعمل هاتفَه (ورقة)، ومن
 * مضى عليه أطولُ من ذلك خارجٌ تماماً (فقاعة). <b>وهي إشارةٌ لا يقين</b>،
 * وكُتب حدُّها هنا وفي ملفّ التصميم كي لا يُقرأ الفرقُ يقيناً.
 */
public final class OfferAlert {

    /**
     * <b>قناةُ الطلب الجديدة</b> — صوتُ الطلب الجديد على مجرى المنبّه نفسِه (SPEC §٦١-ل/٥،
     * ٢٠٢٦-١٠-٠٥). <b>وكانت {@code taxo.offer} بمنبّه الهاتف الافتراضيّ</b>، وصوتُ قناةٍ لا يُغيَّر
     * بعد إنشائها (أندرويد) — <b>فالصوتُ الجديدُ معرّفٌ جديد</b>.
     *
     * <p><b>والقديمةُ لا تُحذف</b>: الخادمُ يرسل إليها ما لم يبلّغه الجهازُ بالمجموعة الثانية
     * ({@code device_tokens.push_channels})، <b>وقناةٌ محذوفةٌ تُسقط الطلبَ إلى الافتراض بلا
     * منبّه</b> — فبقاؤها سطرٌ زائدٌ في الإعدادات، وحذفُها طلبٌ يصل همساً.
     */
    public static final String CHANNEL_ID = "taxo.offer.v2";
    /**
     * <b>قناةُ الطلب الثالثة — «TAXO بيب بيب» على مجرى المنبّه</b> (أمرُ المالك ٢٠٢٦-١١-٢٦). <b>معرّفٌ جديدٌ لا تعديلُ القديمة</b>:
     * صوتُ قناةٍ قائمةٍ لا يتغيّر (أندرويد)، و{@code taxo.offer.v2} صوتُها {@code taxo_request}. <b>ووجودُها شاهدٌ</b> يبلّغ به
     * الويبُ الخادمَ ({@code src/lib/push.ts → channelSet} = 6) فيصله الطلبُ بياناتٍ ترسمها {@link #showFromPush}.
     */
    public static final String CHANNEL_V3 = "taxo.offer.v3";
    /** <b>أختُها لمن أطفأ «رنين الطلب حتى في الوضع الصامت»</b> — الصوتُ نفسُه على مجرى الرنين، فيسكت حيث يسكت الهاتف ويهتزّ. */
    public static final String CHANNEL_V3_QUIET = "taxo.offer.v3.quiet";
    public static final int NOTIFICATION_ID = 4202;

    private static final String PREFS = "taxo.offer.presence";
    /** حدُّ «ما زال يستعمل هاتفَه» — دقيقتان من آخر ظهورٍ لشاشتنا. */
    private static final long RECENT_MS = 2 * 60 * 1000L;

    private OfferAlert() {}

    /** يُستدعى من {@link MainActivity} عند كلِّ توقّف — <b>ختمُ آخر ظهور</b>. */
    public static void markLeftApp(Context context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().putLong("left_at", SystemClock.elapsedRealtime()).apply();
    }

    private static boolean recentlyInApp(Context context) {
        SharedPreferences prefs =
                context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        long at = prefs.getLong("left_at", 0L);
        if (at <= 0L) return false;
        long since = SystemClock.elapsedRealtime() - at;
        // **إقلاعٌ باردٌ يصفّر الساعة** فيُقرأ سالباً — ومن أُعيد تشغيلُ
        // هاتفِه ليس «للتوّ في التطبيق»
        return since >= 0 && since < RECENT_MS;
    }

    private static final String TONE_PREFS = "taxo.tone";

    /** <b>نغمةُ الطلب المختارة</b> («نغمة الإشعارات») — يكتبها الويبُ بـ{@code OfferAlert.setTone} حين يشتعل مفتاحُ سوقه، <b>ومحوُها
     *  الافتراضيّ</b>. و«اهتزاز فقط» لا يُسكت الطلب: <b>الطلبُ يرنّ دائماً والكبتنُ متّصل</b> (أمرُ المالك ج/١/٤) فيبقى على الافتراضيّ. */
    public static void setTone(Context context, String tone) {
        context.getSharedPreferences(TONE_PREFS, Context.MODE_PRIVATE).edit().putString("tone", tone).apply();
    }

    /** <b>القناةُ التي يُرسم عليها الطلبُ الآن — «بيب بيب» لكلِّ طلب</b> (أمرُ المالك ٢٠٢٦-١١-٢٦): لا تتبع «نغمة الإشعارات»، والمجرى
     *  بإعداد «حتى في الوضع الصامت». <b>وقناةٌ غائبةٌ تُسقط الإشعارَ همساً</b>، فتُنشأ قبل أن تُعاد. */
    static String channelFor(Context context) {
        ensureChannel(context);
        return silentRing(context) ? CHANNEL_V3 : CHANNEL_V3_QUIET;
    }

    /** <b>«رنين الطلب حتى في الوضع الصامت» — مشتعلٌ افتراضاً</b> (أمرُ المالك ٢٠٢٦-١١-٢٦)، والكبتنُ يطفئه من الإعدادات. */
    static boolean silentRing(Context context) {
        return context.getSharedPreferences(TONE_PREFS, Context.MODE_PRIVATE).getBoolean("silent_ring", true);
    }

    public static void setSilentRing(Context context, boolean on) {
        context.getSharedPreferences(TONE_PREFS, Context.MODE_PRIVATE).edit().putBoolean("silent_ring", on).apply();
    }

    private static final String LABEL_PREFS = "taxo.offer.labels";

    /** <b>تسمياتُ العملة والفئة بلغة التطبيق</b> — يكتبها الويبُ عند الاتّصال، فيرسم {@link #showFromPush} ما يرسمه الويبُ حرفاً. */
    public static void setLabels(Context context, Map<String, String> labels) {
        SharedPreferences.Editor edit = context.getSharedPreferences(LABEL_PREFS, Context.MODE_PRIVATE).edit();
        for (Map.Entry<String, String> entry : labels.entrySet()) edit.putString(entry.getKey(), entry.getValue());
        edit.apply();
    }

    private static String label(Context context, String key, String fallback) {
        return context.getSharedPreferences(LABEL_PREFS, Context.MODE_PRIVATE).getString(key, fallback);
    }

    /** <b>قناةُ طلبٍ لكلِّ نغمة</b> — على مجرى المنبّه كأختها الافتراضيّة، فترنّ والهاتفُ صامت. */
    public static void ensureToneChannels(Context context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        if (manager == null) return;
        int[] raws = {R.raw.taxo2_ride_request_1, R.raw.taxo2_ride_request_2, R.raw.taxo2_ride_request_3, R.raw.taxo2_ride_request_4,
                R.raw.taxo2_ride_request_5, R.raw.taxo_ride_request_1, R.raw.taxo_ride_request_2, R.raw.taxo_ride_request_3};
        for (int i = 0; i < TaxoChannels.TONES.length; i++) {
            String id = CHANNEL_ID + "." + TaxoChannels.TONES[i];
            if (manager.getNotificationChannel(id) != null) continue;
            NotificationChannel channel = new NotificationChannel(id, "طلبات الرحلات · " + TaxoChannels.toneLabel(i), NotificationManager.IMPORTANCE_HIGH);
            channel.setDescription("بطاقةُ طلبٍ جديد بنغمتك — تصيح ولو كان الهاتفُ صامتاً.");
            channel.enableVibration(true);
            channel.setVibrationPattern(new long[] {0, 350, 200, 350});
            channel.enableLights(true);
            channel.setShowBadge(true);
            channel.setSound(
                    TaxoChannels.sound(context, raws[i]),
                    new AudioAttributes.Builder()
                            .setUsage(AudioAttributes.USAGE_ALARM)
                            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                            .build());
            manager.createNotificationChannel(channel);
        }
    }

    /** ينشئ القنواتِ إن لم تكن — <b>وإنشاؤها مرّةً واحدةً بحكم النظام</b>. */
    public static void ensureChannel(Context context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return;
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        if (manager == null) return;
        createBeep(context, manager, CHANNEL_V3, "طلبات الرحلات",
                "«TAXO بيب بيب» — تصيح ولو كان الهاتفُ صامتاً.", AudioAttributes.USAGE_ALARM);
        createBeep(context, manager, CHANNEL_V3_QUIET, "طلبات الرحلات · تتبع الوضع الصامت",
                "«TAXO بيب بيب» — تسكت حيث يسكت الهاتف وتهتزّ.", AudioAttributes.USAGE_NOTIFICATION_RINGTONE);
        if (manager.getNotificationChannel(CHANNEL_ID) != null) return;

        NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID, "طلبات الرحلات", NotificationManager.IMPORTANCE_HIGH);
        channel.setDescription("بطاقةُ طلبٍ جديد — تصيح ولو كان الهاتفُ صامتاً.");
        channel.enableVibration(true);
        channel.setVibrationPattern(new long[] {0, 350, 200, 350});
        channel.enableLights(true);
        channel.setShowBadge(true);
        // **مجرى المنبّه هو ما ينجو من الصامت** — وهو ما يطلبه التصميم:
        // «النغمة والاهتزاز يعملان في كلٍّ منها». **والصوتُ صوتُ الطلب الجديد**
        // (اختيارُ المالك §٦١-ك) لا منبّهُ الهاتف — والمجرى نفسُه (§٦١-ل/٥)
        channel.setSound(
                TaxoChannels.sound(context, R.raw.taxo_request),
                new AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_ALARM)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                        .build());
        manager.createNotificationChannel(channel);
    }

    private static void createBeep(Context context, NotificationManager manager, String id, String name, String description, int usage) {
        if (manager.getNotificationChannel(id) != null) return;
        NotificationChannel channel = new NotificationChannel(id, name, NotificationManager.IMPORTANCE_HIGH);
        channel.setDescription(description);
        channel.enableVibration(true);
        channel.setVibrationPattern(new long[] {0, 350, 200, 350});
        channel.enableLights(true);
        channel.setShowBadge(true);
        channel.setLockscreenVisibility(Notification.VISIBILITY_PUBLIC);
        channel.setSound(TaxoChannels.sound(context, R.raw.taxo_offer_beep), new AudioAttributes.Builder()
                .setUsage(usage)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                .build());
        manager.createNotificationChannel(channel);
    }

    /**
     * <b>الطلبُ من الإشعار نفسِه — والتطبيقُ في الخلفية أو مغلقٌ أو الشاشةُ مقفلة</b> (أمرُ المالك ٢٠٢٦-١١-٢٦).
     *
     * <p><b>العلّةُ مقيسة</b>: كان الطلبُ يصل الغائبَ إشعاراً يرسمه النظامُ بقناته — <b>يرنّ مرّةً ثانيتين بـ{@code taxo_request}
     * ولا يتكرّر ولا يملأ الشاشة</b>؛ والطريقُ المكرَّرُ (الورقةُ والفقاعةُ وملءُ الشاشة) <b>لا يبلغه إلا الويب</b> من مقبسه، والويبُ
     * يُخنق في الخلفية ويموت مع التطبيق. فالخادمُ يرسله لهذا الجهاز بياناتٍ وحدَها ({@code channels.py → CHANNELS_V6})، <b>وهذا يرسمه</b>.
     *
     * <p><b>ولا يرنّ والكبتنُ غيرُ متّصل</b>: «متّصل» يكتبه الويبُ عند الاتّصال ويمحوه موتُ خدمة الموقع ({@link OnlineService#onDestroy}).
     */
    public static void showFromPush(Context context, Map<String, String> data, long sentAt) {
        if (!context.getSharedPreferences(LauncherPlugin.PREFS, Context.MODE_PRIVATE).getBoolean("online", false)) return;
        int seconds;
        try {
            seconds = Integer.parseInt(value(data, "expires_in_seconds", "0"));
        } catch (NumberFormatException bad) {
            seconds = 0;
        }
        // **عمرُ الطريق يُطرح** — رسالةٌ تأخّرت لا تعدّ ثوانيَ مضت
        if (sentAt > 0) seconds -= (int) Math.max(0, (System.currentTimeMillis() - sentAt) / 1000L);
        if (seconds <= 0) return;
        String currency = value(data, "currency", "");
        String amount = value(data, "amount", "");
        // **الدينارُ الجزائريُّ بلا كسور** كما يرسمه الويب (`formatAmount`)
        if ("DZD".equals(currency) && amount.contains(".")) amount = amount.substring(0, amount.indexOf('.'));
        String category = value(data, "category", "");
        String distance = value(data, "distance_to_pickup_km", "");
        show(context, new OfferData(
                data.get("ride_id"),
                amount,
                label(context, "currency." + currency, currency),
                "",
                label(context, "category." + category, category),
                distance.isEmpty() ? "" : distance + " " + label(context, "km", "كم"),
                value(data, "pickup", ""),
                value(data, "drop", ""),
                seconds));
    }

    private static String value(Map<String, String> data, String key, String fallback) {
        String found = data.get(key);
        return found == null ? fallback : found;
    }

    /** <b>الطلبُ الظاهرُ الآن</b> — فلا يُعاد رسمُه ولا تُعاد نغمتُه حين يصل من الطريقين (المقبس والإشعار). */
    private static String shownRide;
    private static long shownUntil;

    public static boolean canUseFullScreen(Context context) {
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        if (manager == null) return false;
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.UPSIDE_DOWN_CAKE) return true;
        return manager.canUseFullScreenIntent();
    }

    public static boolean canDrawOverlay(Context context) {
        return Settings.canDrawOverlays(context);
    }

    private static boolean locked(Context context) {
        KeyguardManager keyguard = context.getSystemService(KeyguardManager.class);
        PowerManager power = context.getSystemService(PowerManager.class);
        boolean asleep = power != null && !power.isInteractive();
        return asleep || (keyguard != null && keyguard.isKeyguardLocked());
    }

    /**
     * <b>واحدةٌ لا اثنتان</b> — والاختيارُ يقع <b>قبل العرض لا بعده</b>، وهو
     * نصُّ القاعدة الثانية في التصميم.
     *
     * <p><b>ويعيد أيرنّ بنفسه</b> (§٦١-ل/٥): ملءُ الشاشة بصوت قناته مكرَّراً، والورقةُ
     * والفقاعةُ بـ{@link OfferTone} — <b>فلا تبدأ نغمةُ الويب فوقه</b>. و{@code false}
     * حين تعذّر الصوت، فيرنّ الويبُ مكانه.
     */
    public static boolean show(Context context, OfferData offer) {
        ensureChannel(context);
        if (!offer.rideId.isEmpty() && offer.rideId.equals(shownRide) && SystemClock.elapsedRealtime() < shownUntil) return true;
        hide(context);
        shownRide = offer.rideId;
        shownUntil = SystemClock.elapsedRealtime() + offer.seconds * 1000L;
        // **نبضُ فقاعة الحال** (§١٠٣ A/1) — إن كانت ظاهرة؛ ولا شيءَ إن لم تكن
        StatusBubble.pulse();
        // **الطلبُ منطوقاً** (§١٠٣ B/14) — مفتاحُ السوق واختيارُ الكبتن معاً، وبعد الرنّة الأولى
        OfferSpeech.speak(context, offer);

        if (locked(context)) {
            // **الشاشةُ المقفلةُ لملء الشاشة وحدَه** (قرارُ المالك): لا فقاعةَ
            // ولا ورقةَ فوق القفل
            return fullScreen(context, offer, true);
        }
        if (canDrawOverlay(context)) {
            if (recentlyInApp(context)) {
                OfferSheetWindow.show(context, offer);
            } else {
                OfferBubble.show(context, offer);
            }
            return OfferTone.start(context, offer.seconds);
        }
        // **بلا إذنِ تراكبٍ تسقط الورقةُ والفقاعةُ معاً** — والطريقُ الباقي
        return fullScreen(context, offer, false);
    }

    private static boolean fullScreen(Context context, OfferData offer, boolean isLocked) {
        Intent screen = new Intent(context, OfferActivity.class);
        screen.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK
                | Intent.FLAG_ACTIVITY_CLEAR_TOP
                | Intent.FLAG_ACTIVITY_NO_USER_ACTION);
        screen.putExtras(offer.toBundle());
        screen.putExtra(OfferActivity.EXTRA_LOCKED, isLocked);

        PendingIntent pending = PendingIntent.getActivity(
                context, 1, screen,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        NotificationManager manager = context.getSystemService(NotificationManager.class);
        if (manager == null) return false;

        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? new Notification.Builder(context, channelFor(context))
                : new Notification.Builder(context);
        builder.setContentTitle("طلب رحلة جديد")
                // **المهلةُ والأجرةُ في نصِّ الإشعار** (قرارُ المالك): «إشعارٌ
                // بأهمّية قصوى فيه المهلة والأجرة وزرٌّ يفتح التطبيق»
                .setContentText(offer.fare + " " + offer.currency
                        + " · " + offer.meta(true)
                        + " · " + offer.seconds + " ث")
                // **أيقونةُ الشريط أحاديّةُ اللون** (`ic_stat_taxo`): أيقونةُ التشغيل التكيّفيّة هنا تُسقط واجهةَ النظام على أندرويد ٨٫٠
                .setSmallIcon(R.drawable.ic_stat_taxo)
                .setAutoCancel(true)
                .setCategory(Notification.CATEGORY_CALL)
                .setContentIntent(pending)
                .setTimeoutAfter(offer.seconds * 1000L)
                .addAction(new Notification.Action.Builder(
                        null, "افتح الطلب", pending).build());

        if (canUseFullScreen(context)) {
            builder.setFullScreenIntent(pending, true);
        }
        Notification notification = builder.build();
        // **ويتكرّر صوتُ القناة حتى يُطوى الإشعار** (§٦١-ل/٥): منبّهُ الهاتف الذي
        // كان طويلٌ بطبعه، **وصوتُ الطلب ثانيتان** — فبلا التكرار يرنّ مرّةً ويسكت
        // والمهلةُ تجري. **والطيُّ مضمونٌ**: `hide` عند كلِّ نهاية، و`setTimeoutAfter` بالمهلة
        notification.flags |= Notification.FLAG_INSISTENT;
        manager.notify(NOTIFICATION_ID, notification);

        // **ولا شاشةَ فارغة**: من مُنح ملءَ الشاشة يُفتح له النشاطُ مباشرةً
        // أيضاً — والإشعارُ يبقى مدخلَه إن كان النظامُ منع الإطلاق
        if (canUseFullScreen(context)) {
            try {
                context.startActivity(screen);
            } catch (Exception ignored) {
                // إطلاقٌ من الخلفية قد يُمنع — والإشعارُ هو الطريقُ الثاني
            }
        }
        // **والصوتُ صوتُ القناة** — يرنّ ما دام الإشعارُ قائماً، ولو مُنع النشاط
        return true;
    }

    /** يطوي كلَّ ما قد يكون ظاهراً — <b>الثلاثةَ معاً ونغمتَها</b>، فلا يبقى أثر. */
    public static void hide(Context context) {
        shownRide = null;
        OfferSpeech.stop();
        OfferTone.stop();
        OfferBubble.hide(context);
        OfferSheetWindow.hide(context);
        NotificationManager manager = context.getSystemService(NotificationManager.class);
        if (manager != null) manager.cancel(NOTIFICATION_ID);
    }

    public static Intent overlaySettings(Context context) {
        return new Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:" + context.getPackageName())
        ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
    }

    public static Intent fullScreenSettings(Context context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            return appSettings(context);
        }
        return new Intent(
                Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT,
                Uri.parse("package:" + context.getPackageName())
        ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
    }

    public static Intent appSettings(Context context) {
        return new Intent(
                Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                Uri.parse("package:" + context.getPackageName())
        ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
    }
}
