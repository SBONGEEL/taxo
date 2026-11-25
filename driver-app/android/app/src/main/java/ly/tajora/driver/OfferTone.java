package ly.tajora.driver;

import android.content.Context;
import android.content.res.AssetFileDescriptor;
import android.media.AudioAttributes;
import android.media.AudioManager;
import android.media.MediaPlayer;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.util.Log;

/**
 * <b>نغمةُ الطلب — «TAXO بيب بيب» وحدَها، مكرَّرةً ومعها اهتزازٌ مكرَّر</b> (أمرُ المالك ٢٠٢٦-١١-٢٦).
 *
 * <p><b>الملفُّ {@code taxo_offer_beep}</b> هو الخيارُ ٥ من المجموعة الثانية ({@code taxo2_ride_request_5}) نفسُه،
 * <b>مرفوعاً ٢٫٥ dB بلا تشويه</b> (ضاغطٌ خفيفٌ ثمّ {@code loudnorm} بقمّةٍ حقيقيّةٍ ≤ −1 dBTP: −11.1 LUFS، القمّة −0.8 dBFS) —
 * <b>وكانت الورقةُ والفقاعةُ ترنّان بـ{@code taxo_request}</b> لا بالـ«بيب بيب».
 *
 * <p><b>والمجرى بإعداد الكبتن</b> «رنين الطلب حتى في الوضع الصامت» ({@link OfferAlert#silentRing}، مشتعلٌ افتراضاً):
 * مشتعلاً ⇐ <b>مجرى المنبّه</b> فيصيح والهاتفُ صامتٌ أو على الاهتزاز؛ مطفأً ⇐ مجرى الرنين، <b>ويسكت الصوتُ حيث يسكت الهاتف
 * ويبقى الاهتزاز</b>.
 *
 * <p><b>ويقف بثلاثة</b>: {@link OfferAlert#hide} (قبولٌ أو رفضٌ أو انقضاءٌ أو عودةٌ إلى التطبيق)، {@link #stop} من الويب،
 * <b>أو انقضاءُ المهلة بنفسها</b> — فلا يرنّ لعرضٍ مضى إن لم يُنادَ الإخفاءُ لأيِّ سبب.
 */
final class OfferTone {

    /** **سطرٌ في السجلّ لكلِّ بدءٍ وإيقاف** — يقيسه محاكي CI (`android-emulator-films.sh`، §١١٥) بلا صوت: المجرى والمهلةُ والإيقاف */
    static final String TAG = "TaxoOfferTone";
    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static final Runnable EXPIRE = OfferTone::stop;
    /** <b>نبضةُ القناة نفسُها</b> (350/200/350) ثمّ سكونٌ قصير — <b>وتتكرّر</b> من أوّلها ما دامت النغمة. */
    private static final long[] PULSE = {0, 350, 200, 350, 900};
    private static MediaPlayer player;
    private static Vibrator vibrator;

    private OfferTone() {}

    /** يبدأ النغمةَ والاهتزازَ مكرَّرَين حتى {@link #stop} أو انقضاء {@code seconds}. <b>و{@code true} = يرنّ أو يهتزّ بنفسه</b>. */
    static synchronized boolean start(Context context, int seconds) {
        stop();
        boolean loud = OfferAlert.silentRing(context);
        buzz(context);
        MAIN.postDelayed(EXPIRE, Math.max(1, seconds) * 1000L);
        if (!loud && quietPhone(context)) {
            // **الكبتنُ أطفأ «حتى في الصامت» وهاتفُه صامت** — يهتزّ ولا يصيح، وهو ما اختاره
            Log.i(TAG, "start vibrate-only seconds=" + seconds);
            return true;
        }
        MediaPlayer next = new MediaPlayer();
        try (AssetFileDescriptor file = context.getResources().openRawResourceFd(R.raw.taxo_offer_beep)) {
            // **قبل التحضير لا بعده**: سمةُ المجرى لا تُغيَّر على مشغّلٍ محضَّر
            next.setAudioAttributes(new AudioAttributes.Builder()
                    .setUsage(loud ? AudioAttributes.USAGE_ALARM : AudioAttributes.USAGE_NOTIFICATION_RINGTONE)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build());
            next.setDataSource(file.getFileDescriptor(), file.getStartOffset(), file.getLength());
            next.setLooping(true);
            next.prepare();
            next.start();
            Log.i(TAG, "start usage=" + (loud ? "alarm" : "ringtone") + " seconds=" + seconds);
        } catch (Exception failed) {
            // **ولا يسقط العرضُ لأن صوتَه سقط** — والويبُ يرنّ مكانه (`sounding=false`)
            Log.w(TAG, "start failed " + failed.getClass().getSimpleName());
            next.release();
            return vibrator != null;
        }
        player = next;
        return true;
    }

    /** <b>«جرّب النغمة»</b> — دورةٌ واحدةٌ بالمجرى الذي سيرنّ به الطلبُ فعلاً، <b>والكبتنُ متّصلٌ أو لا</b>: هو ضغط الزرّ ليسمعها. */
    static boolean test(Context context) {
        return start(context, 7);
    }

    private static boolean quietPhone(Context context) {
        AudioManager audio = context.getSystemService(AudioManager.class);
        return audio != null && audio.getRingerMode() != AudioManager.RINGER_MODE_NORMAL;
    }

    private static void buzz(Context context) {
        Vibrator v = context.getSystemService(Vibrator.class);
        if (v == null || !v.hasVibrator()) return;
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                v.vibrate(VibrationEffect.createWaveform(PULSE, 0), new AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_ALARM).build());
            } else {
                v.vibrate(PULSE, 0);
            }
            vibrator = v;
        } catch (RuntimeException ignored) {
            // جهازٌ يمنع الاهتزاز — والصوتُ يبقى
        }
    }

    static synchronized void stop() {
        MAIN.removeCallbacks(EXPIRE);
        if (player != null || vibrator != null) Log.i(TAG, "stop playing=" + (player != null && isPlaying()));
        if (vibrator != null) {
            vibrator.cancel();
            vibrator = null;
        }
        if (player == null) return;
        try {
            player.stop();
        } catch (IllegalStateException ignored) {
            // لم يبدأ أو انتهى — ولا شيءَ يُوقَف
        }
        player.release();
        player = null;
    }

    /** **أيعزف الآن؟** — للمسبار وللسجلّ، والمشغّلُ المحرَّرُ لا يعزف */
    static synchronized boolean isPlaying() {
        try {
            return player != null && player.isPlaying();
        } catch (IllegalStateException released) {
            return false;
        }
    }
}
