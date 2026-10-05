package ly.tajora.driver;

import android.content.Context;
import android.content.res.AssetFileDescriptor;
import android.media.AudioAttributes;
import android.media.MediaPlayer;
import android.os.Handler;
import android.os.Looper;

/**
 * <b>نغمةُ الطلب للورقة والفقاعة</b> — بصوت الطلب الجديد <b>على مجرى المنبّه</b>، كقناته
 * (SPEC §٦١-ل/٥، ٢٠٢٦-١٠-٠٥).
 *
 * <p><b>والعلّةُ أن الورقةَ والفقاعةَ نافذتان لا إشعاران</b>: لا قناةَ لهما فلا صوتَ من
 * النظام، <b>وكانتا صامتتين في الشيفرة الأصليّة</b> — وما يُسمع معهما إن سُمع فنغمةُ الويب،
 * <b>وهي على مجرى الوسائط</b>: يُخفضها مفتاحُ الصوت وتسكت حيث يسكت. ومجرى المنبّه هو ما
 * ينجو من الصامت، <b>وهو شرطُ المالك بنصّه</b>: «ترنّ والهاتفُ صامت، كاليوم».
 *
 * <p><b>وواحدةٌ لا اثنتان</b>: الحزمةُ تقول للويب إنها ترنّ ({@code sounding})، <b>فلا تبدأ
 * نغمةُ الويب فوقها</b>. <b>وتقف بثلاثة</b>: {@link OfferAlert#hide} (قبولٌ أو رفضٌ أو
 * انقضاءٌ أو عودةٌ إلى التطبيق)، <b>أو انقضاءُ المهلة بنفسها</b> — فلا ترنّ لعرضٍ مضى إن
 * لم يُنادَ الإخفاءُ لأيِّ سبب.
 */
final class OfferTone {

    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static final Runnable EXPIRE = OfferTone::stop;
    private static MediaPlayer player;

    private OfferTone() {}

    /** يبدأ النغمةَ مكرَّرةً حتى {@link #stop} أو انقضاء {@code seconds}. */
    static synchronized boolean start(Context context, int seconds) {
        stop();
        MediaPlayer next = new MediaPlayer();
        try (AssetFileDescriptor file =
                     context.getResources().openRawResourceFd(R.raw.taxo_request)) {
            // **قبل التحضير لا بعده**: سمةُ المجرى لا تُغيَّر على مشغّلٍ محضَّر
            next.setAudioAttributes(new AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_ALARM)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build());
            next.setDataSource(file.getFileDescriptor(), file.getStartOffset(), file.getLength());
            next.setLooping(true);
            next.prepare();
            next.start();
        } catch (Exception failed) {
            // **ولا يسقط العرضُ لأن صوتَه سقط** — والويبُ يرنّ مكانه (`sounding=false`)
            next.release();
            return false;
        }
        player = next;
        MAIN.postDelayed(EXPIRE, Math.max(1, seconds) * 1000L);
        return true;
    }

    static synchronized void stop() {
        MAIN.removeCallbacks(EXPIRE);
        if (player == null) return;
        try {
            player.stop();
        } catch (IllegalStateException ignored) {
            // لم يبدأ أو انتهى — ولا شيءَ يُوقَف
        }
        player.release();
        player = null;
    }
}
