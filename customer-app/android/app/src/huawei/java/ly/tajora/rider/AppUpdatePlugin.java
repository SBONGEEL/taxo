package ly.tajora.rider;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * <b>التحديثُ في نسخة Huawei</b> — لا تحديثَ من Play. {@code source} <b>قراءةُ نسخة Google نفسُها حرفاً</b> (المثبِّتُ وخدماتُ Google)
 * فتختار البوّابةُ رابطَ متجرها من اللوحة؛ و{@code start} يُحلّ {@code started=false} بسبب {@code play_unavailable} كما يُحلّ هناك
 * حين يغيب Play — <b>فالإلزاميُّ يفتح رابطَ المتجر</b> كما في كلِّ هاتفٍ بلا Play.
 */
@CapacitorPlugin(name = "AppUpdate")
public class AppUpdatePlugin extends Plugin {

    @PluginMethod
    public void source(PluginCall call) {
        JSObject ret = new JSObject();
        String installer = null;
        android.content.pm.PackageManager pm = getContext().getPackageManager();
        String pkg = getContext().getPackageName();
        try {
            if (android.os.Build.VERSION.SDK_INT >= 30) {
                installer = pm.getInstallSourceInfo(pkg).getInstallingPackageName();
            } else {
                installer = pm.getInstallerPackageName(pkg);
            }
        } catch (Exception ignored) {
        }
        boolean gms = false;
        try {
            gms = pm.getApplicationInfo("com.google.android.gms", 0).enabled;
        } catch (Exception ignored) {
        }
        ret.put("installer", installer);
        ret.put("gms", gms);
        call.resolve(ret);
    }

    @PluginMethod
    public void start(PluginCall call) {
        JSObject ret = new JSObject();
        ret.put("started", false);
        ret.put("reason", "play_unavailable");
        call.resolve(ret);
    }
}
