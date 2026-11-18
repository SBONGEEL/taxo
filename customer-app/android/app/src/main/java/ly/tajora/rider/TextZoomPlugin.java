package ly.tajora.rider;

import android.webkit.WebView;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * <b>النصُّ الكبير</b> (SPEC §١٠٣ C/40) — تكبيرُ نصِّ الواجهة كلِّها بنسبةٍ واحدة ({@code WebSettings.setTextZoom})، فيكبر ما كُتب بالبكسل
 * أيضاً ولا تُمسّ الصور ولا الخريطة. النسبةُ محصورةٌ بين ١٠٠ و١٦٠. نسخةُ التطبيق الآخر حرفاً إلا الحزمة.
 */
@CapacitorPlugin(name = "TextZoom")
public class TextZoomPlugin extends Plugin {

    /** خالصةٌ ومختبَرة: النسبةُ بحدّيها. */
    static int clamp(Integer percent) {
        if (percent == null) return 100;
        return Math.max(100, Math.min(160, percent));
    }

    @PluginMethod
    public void set(PluginCall call) {
        int percent = clamp(call.getInt("percent"));
        getActivity().runOnUiThread(() -> {
            WebView view = getBridge().getWebView();
            if (view != null) view.getSettings().setTextZoom(percent);
            call.resolve();
        });
    }
}
