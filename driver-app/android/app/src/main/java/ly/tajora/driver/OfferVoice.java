package ly.tajora.driver;

import android.Manifest;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.media.AudioManager;
import android.media.ToneGenerator;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;

import java.util.ArrayList;
import java.util.List;

/**
 * <b>«قبول» أو «رفض» بالصوت</b> (أمرُ المالك ٢٠/١١ الرابع، البند ٥٤، SPEC §١١٠) — <b>بأسلم طريقٍ تسمح به Google Play</b>:
 *
 * <ul>
 *   <li><b>يستمع في شاشة العرض الظاهرة وحدَها</b> ({@link OfferActivity} في المقدّمة) ويتوقّف لحظةَ تُغلق — <b>لا ميكروفونَ في الخلفيّة</b>،
 *       ولا نوعَ {@code microphone} لخدمة المقدّمة، فلا تصريحَ خلفيّ.</li>
 *   <li><b>ثلاثةُ شروطٍ معاً</b>: مفتاحُ السوق ({@code voice_offer_answer})، <b>واختيارُ الكبتن بنفسه</b> من الإعدادات
 *       ({@code voice_offer_user})، وإذنُ {@code RECORD_AUDIO} الذي طلبه هو.</li>
 *   <li><b>معرِّفُ الكلام في النظام</b> بالعربيّة ويُفضَّل ما على الجهاز؛ والضجيجُ «لم أفهم» لا قبولٌ ({@link BubbleLogic#voiceVerdict}).</li>
 *   <li><b>نغمةُ تأكيدٍ واضحة</b> حين يفهم، ثمّ يمرّ القبولُ أو الرفضُ بالمسار نفسِه الذي تمرّ به اللمسة.</li>
 * </ul>
 */
final class OfferVoice {

    interface Verdict {
        void on(String verdict);
    }

    private final Context context;
    private final Verdict callback;
    private final Handler main = new Handler(Looper.getMainLooper());
    private SpeechRecognizer recognizer;
    private boolean stopped;
    private int restarts;

    private OfferVoice(Context context, Verdict callback) {
        this.context = context;
        this.callback = callback;
    }

    static boolean wanted(Context c) {
        SharedPreferences p = c.getSharedPreferences(LauncherPlugin.PREFS, Context.MODE_PRIVATE);
        return p.getBoolean("voice_offer_answer", false)
                && p.getBoolean("voice_offer_user", false)
                && c.checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
                && SpeechRecognizer.isRecognitionAvailable(c);
    }

    /** يبدأ الاستماعَ بعد لحظة (تنتهي نغمةُ العرض) ويعيده حين لا يُفهم شيء — حتى {@link #stop}. */
    static OfferVoice listen(Context c, Verdict callback) {
        OfferVoice voice = new OfferVoice(c, callback);
        voice.main.postDelayed(voice::start, 1200);
        return voice;
    }

    void stop() {
        stopped = true;
        main.removeCallbacksAndMessages(null);
        if (recognizer != null) {
            try {
                recognizer.cancel();
                recognizer.destroy();
            } catch (Exception ignored) {
                // أُغلق من قبل
            }
            recognizer = null;
        }
    }

    private void start() {
        if (stopped) return;
        try {
            if (recognizer == null) {
                recognizer = SpeechRecognizer.createSpeechRecognizer(context);
                recognizer.setRecognitionListener(new Listener());
            }
            Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                    .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                    .putExtra(RecognizerIntent.EXTRA_LANGUAGE, "ar")
                    .putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                    .putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 5)
                    .putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true);
            recognizer.startListening(intent);
        } catch (Exception ignored) {
            // معرِّفٌ غائب — اللمسُ يبقى كما هو
        }
    }

    private void heard(List<String> texts) {
        if (stopped) return;
        String verdict = BubbleLogic.voiceVerdict(texts);
        if (verdict == null) return;
        stopped = true;
        try {
            ToneGenerator tone = new ToneGenerator(AudioManager.STREAM_NOTIFICATION, 90);
            tone.startTone(ToneGenerator.TONE_PROP_ACK, 220);
            main.postDelayed(tone::release, 400);
        } catch (Exception ignored) {
            // لا نغمة — والفعلُ يمضي
        }
        stop();
        callback.on(verdict);
    }

    private final class Listener implements RecognitionListener {
        @Override public void onReadyForSpeech(Bundle params) {}
        @Override public void onBeginningOfSpeech() {}
        @Override public void onRmsChanged(float rmsdB) {}
        @Override public void onBufferReceived(byte[] buffer) {}
        @Override public void onEndOfSpeech() {}
        @Override public void onEvent(int eventType, Bundle params) {}

        @Override
        public void onError(int error) {
            // لم يُفهم شيءٌ أو انقضت مهلةُ السكوت — يعاد ما دامت الشاشةُ ظاهرة، ثماني مرّاتٍ على الأكثر
            if (stopped || restarts >= 8) return;
            restarts++;
            main.postDelayed(OfferVoice.this::start, 300);
        }

        @Override
        public void onResults(Bundle results) {
            heard(texts(results));
            if (!stopped) onError(SpeechRecognizer.ERROR_NO_MATCH);
        }

        @Override
        public void onPartialResults(Bundle partial) {
            heard(texts(partial));
        }

        private List<String> texts(Bundle b) {
            ArrayList<String> list = b == null ? null : b.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
            return list == null ? new ArrayList<>() : list;
        }
    }
}
