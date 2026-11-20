package ly.tajora.rider;

import android.content.Context;
import android.content.SharedPreferences;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * <b>جلسةُ فقاعة الراكب</b> (أمرُ المالك ٢٠/١١ الرابع، SPEC §١١٠) — يحفظ عنوانَ الخلفية ورمزَ الوصول لنداءين خفيفين من الفقاعة
 * (الردُّ السريع في المحادثة، والطوارئ) — <b>وهو ما تحفظه الـWebView نفسُها</b>، فلا حمايةَ نقصت. <b>ولا رمزَ تجديدٍ هنا أبداً</b>
 * (مُدوَّرٌ ذو استعمالٍ واحد، §23). ويُمحى بالخروج ({@code remember} بلا رمز).
 */
@CapacitorPlugin(name = "RiderBubble")
public class RiderBubblePlugin extends Plugin {

    static final String SESSION = "taxo.bubble.session";

    @PluginMethod
    public void remember(PluginCall call) {
        SharedPreferences prefs = getContext().getSharedPreferences(SESSION, Context.MODE_PRIVATE);
        String base = call.getString("base");
        String token = call.getString("token");
        if (base == null || token == null) prefs.edit().clear().apply();
        else prefs.edit().putString("base", base).putString("token", token).apply();
        call.resolve();
    }
}
