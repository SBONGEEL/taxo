package ly.tajora.rider;

import android.app.Activity;
import android.view.WindowManager;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * <b>منعُ لقطات الشاشة وتسجيلها</b> في المحفظة وشاشة رمز بطاقة TAXO (SPEC §١٠٣ المرحلة B/26) — {@code FLAG_SECURE} على النافذة:
 * لقطةٌ تخرج سوداء، وقائمةُ التطبيقات الأخيرة تُخفي المعاينة. <b>الويبُ يقول متى</b> (مسارُ {@code /wallet} ومفتاحُ السوق)،
 * <b>وهذا ينفّذ وحدَه</b>. <b>وواحدٌ بايتاً في التطبيقين إلا اسمَ الحزمة.</b>
 */
@CapacitorPlugin(name = "ScreenSecure")
public class ScreenSecurePlugin extends Plugin {

    @PluginMethod
    public void set(PluginCall call) {
        boolean on = Boolean.TRUE.equals(call.getBoolean("on", false));
        Activity activity = getActivity();
        if (activity == null) {
            call.resolve();
            return;
        }
        activity.runOnUiThread(() -> {
            if (on) activity.getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
            else activity.getWindow().clearFlags(WindowManager.LayoutParams.FLAG_SECURE);
            call.resolve();
        });
    }
}
