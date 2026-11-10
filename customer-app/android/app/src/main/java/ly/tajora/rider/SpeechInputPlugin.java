package ly.tajora.rider;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.speech.RecognizerIntent;

import androidx.activity.result.ActivityResult;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.ActivityCallback;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.util.ArrayList;

/**
 * <b>الطلبُ بالصوت</b> (أمرُ المالك ٢٠٢٦-١١-١٠، البند ١٠، SPEC §٩٧/١٠) — نافذةُ التعرّف الصوتيّ في الهاتف نفسِه.
 *
 * <p>{@code RecognizerIntent} يفتح خدمةَ النظام (Google في أندرويد)، <b>فلا يحتاج التطبيقُ إذنَ الميكروفون</b> ولا يرى الصوت:
 * يعود بالنصِّ وحدَه. <b>ولا شيءَ يُحفظ هنا</b>، والنصُّ يُكتب في البحث ({@code lib/voice-input.ts}) والوجهةُ تُختار وتُؤكَّد.
 * وإلغاءُ النافذة أو غيابُ الخدمة يعودان بنصٍّ فارغ.
 */
@CapacitorPlugin(name = "SpeechInput")
public class SpeechInputPlugin extends Plugin {

    @PluginMethod
    public void listen(PluginCall call) {
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, call.getString("language", "ar"));
        intent.putExtra(RecognizerIntent.EXTRA_PROMPT, call.getString("prompt", ""));
        intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
        try {
            startActivityForResult(call, intent, "onHeard");
        } catch (ActivityNotFoundException missing) {
            call.reject("لا خدمةَ تعرّفٍ صوتيٍّ في الهاتف");
        }
    }

    @ActivityCallback
    private void onHeard(PluginCall call, ActivityResult result) {
        if (call == null) return;
        String text = "";
        Intent data = result.getData();
        if (result.getResultCode() == Activity.RESULT_OK && data != null) {
            ArrayList<String> matches = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);
            if (matches != null && !matches.isEmpty() && matches.get(0) != null) text = matches.get(0);
        }
        JSObject out = new JSObject();
        out.put("text", text);
        call.resolve(out);
    }
}
