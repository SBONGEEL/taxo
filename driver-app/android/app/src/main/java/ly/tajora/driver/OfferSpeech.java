package ly.tajora.driver;

import android.content.Context;
import android.content.SharedPreferences;
import android.media.AudioAttributes;
import android.os.Handler;
import android.os.Looper;
import android.speech.tts.TextToSpeech;

import java.util.Locale;

/**
 * <b>الطلبُ منطوقاً بالعربيّة</b> (SPEC §١٠٣ المرحلة B/14، أمرُ المالك ٢٠٢٦-١١-١٦) — «طلبٌ جديد. ٢٫٧٥ دينار. ١٫٢ كم. من الدوار السابع».
 *
 * <p><b>شرطان معاً</b>: مفتاحُ السوق ({@code offer_tts}، يكتبه الويبُ من اللوحة) <b>واختيارُ الكبتن نفسِه</b> ({@code offer_tts_user}،
 * من «الإعدادات») — فلا ينطق هاتفٌ لم يطلب صاحبُه ذلك. <b>ويُنطق بعد الرنّة الأولى</b> (١٫٢ ث) على مجرى إرشاد الملاحة، فلا يُغطّي
 * الرنينَ ولا يغطّيه. <b>ومحرّكٌ بلا عربيّةٍ يسكت</b> — لا يُقرأ الطلبُ بلغةٍ أخرى ولا بحروفٍ مكسورة.
 */
final class OfferSpeech {

    static final String FEATURE = "offer_tts";
    static final String USER = "offer_tts_user";
    private static final long AFTER_RING_MS = 1_200;

    private static TextToSpeech engine;
    private static boolean ready;
    private static String queued;

    private OfferSpeech() {}

    static boolean wanted(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(LauncherPlugin.PREFS, Context.MODE_PRIVATE);
        return prefs.getBoolean(FEATURE, false) && prefs.getBoolean(USER, false);
    }

    /** <b>الجملةُ وحدَها</b> — خالصةٌ فتُختبر بلا جهاز. وما غاب من الحقول يُسقط لا يُنطق فارغاً. */
    static String sentence(OfferData offer) {
        StringBuilder out = new StringBuilder("طلبٌ جديد.");
        if (offer.fare != null && !offer.fare.isEmpty()) {
            out.append(' ').append(offer.fare);
            String currency = spokenCurrency(offer.currency);
            if (!currency.isEmpty()) out.append(' ').append(currency);
            out.append('.');
        }
        if (offer.distance != null && !offer.distance.isEmpty()) out.append(' ').append(offer.distance).append('.');
        if (offer.pickup != null && !offer.pickup.isEmpty()) out.append(" من ").append(offer.pickup).append('.');
        return out.toString();
    }

    /** <b>العملةُ كلمةً لا اختصاراً</b> — «د.أ» يُقرأ حروفاً. */
    static String spokenCurrency(String label) {
        if (label == null) return "";
        switch (label.trim()) {
            case "د.أ": case "JOD": return "دينار";
            case "د.ج": case "دج": case "DZD": return "دينار جزائري";
            case "د.ل": case "LYD": return "دينار ليبي";
            default: return label.trim();
        }
    }

    static void speak(Context context, OfferData offer) {
        if (!wanted(context)) return;
        String text = sentence(offer);
        Context app = context.getApplicationContext();
        new Handler(Looper.getMainLooper()).postDelayed(() -> say(app, text), AFTER_RING_MS);
    }

    static void stop() {
        queued = null;
        if (engine != null && ready) engine.stop();
    }

    private static void say(Context context, String text) {
        if (engine != null && ready) {
            utter(text);
            return;
        }
        queued = text;
        if (engine != null) return;
        engine = new TextToSpeech(context, status -> {
            if (status != TextToSpeech.SUCCESS) {
                engine = null;
                return;
            }
            int lang = engine.setLanguage(new Locale("ar"));
            if (lang == TextToSpeech.LANG_MISSING_DATA || lang == TextToSpeech.LANG_NOT_SUPPORTED) {
                engine.shutdown();
                engine = null;
                return;
            }
            engine.setAudioAttributes(new AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build());
            ready = true;
            if (queued != null) utter(queued);
        });
    }

    private static void utter(String text) {
        queued = null;
        engine.speak(text, TextToSpeech.QUEUE_FLUSH, null, "taxo-offer");
    }
}
