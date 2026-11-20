package ly.tajora.rider;

import android.view.Window;

import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * <b>أيقوناتُ شريط النظام تتبع مظهرَ التطبيق لا مظهرَ الهاتف</b> (قِيس على S21 ٢٠٢٦-١١-٢٠): {@code EdgeToEdge} يختار لونَها من وضع
 * <b>النظام</b> — فمن اختار «فاتح» في التطبيق وهاتفُه ليليّ رأى الساعةَ والبطاريّةَ بيضاءَ على أرضٍ فاتحة لا تكاد تُقرأ. فالصفحةُ تُبلغ
 * مظهرَها هنا عند كلِّ تبديل. نسخةُ التطبيق الآخر حرفاً إلا الحزمة.
 */
@CapacitorPlugin(name = "SystemBars")
public class SystemBarsPlugin extends Plugin {

    @PluginMethod
    public void setLight(PluginCall call) {
        boolean light = Boolean.TRUE.equals(call.getBoolean("light", false));
        getActivity().runOnUiThread(() -> {
            Window window = getActivity().getWindow();
            WindowInsetsControllerCompat bars = WindowCompat.getInsetsController(window, window.getDecorView());
            bars.setAppearanceLightStatusBars(light);
            bars.setAppearanceLightNavigationBars(light);
            call.resolve();
        });
    }
}
