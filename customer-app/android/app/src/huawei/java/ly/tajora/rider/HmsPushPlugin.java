package ly.tajora.rider;

import android.content.pm.ApplicationInfo;
import android.content.pm.PackageManager;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.huawei.hms.aaid.HmsInstanceId;

import java.util.Map;

/**
 * <b>رمزُ HMS Push ورسائلُه للصفحة</b> (نسخةُ Huawei وحدَها، أمرُ المالك ٢٠٢٦-١١-٢٣).
 *
 * <ul>
 *   <li>{@code getToken()} ⇐ {@code {token}} — <b>أو رفضٌ يسمّي سببه</b>: {@code hms_unconfigured} (لا معرّفَ تطبيقٍ من AppGallery في
 *       هذا البناء) أو {@code hms_unavailable} (خدماتُ Huawei غائبةٌ أو لم تُجب). والرمزُ لا يُطبع ولا يُسجَّل.</li>
 *   <li>الحدثان {@code token} (رمزٌ جديدٌ يصل متأخّراً — EMUI القديم) و{@code received} ({@code {data}}).</li>
 * </ul>
 */
@CapacitorPlugin(name = "HmsPush")
public class HmsPushPlugin extends Plugin {

    private static HmsPushPlugin live;

    @Override
    public void load() {
        live = this;
    }

    @PluginMethod
    public void getToken(PluginCall call) {
        String appId = appIdOf(getContext());
        if (appId.isEmpty()) {
            call.reject("hms_unconfigured");
            return;
        }
        // **النداءُ يحجب**: خارج خيط الواجهة، كما تشترط مكتبةُ HMS
        new Thread(() -> {
            try {
                String issued = HmsInstanceId.getInstance(getContext()).getToken(appId, "HCM");
                JSObject ret = new JSObject();
                ret.put("token", issued == null || issued.isEmpty() ? null : issued);
                call.resolve(ret);
            } catch (Exception failed) {
                call.reject("hms_unavailable");
            }
        }).start();
    }

    static void token(String token) {
        HmsPushPlugin plugin = live;
        if (plugin == null || token == null || token.isEmpty()) return;
        JSObject ret = new JSObject();
        ret.put("token", token);
        plugin.notifyListeners("token", ret);
    }

    static void message(Map<String, String> data) {
        HmsPushPlugin plugin = live;
        if (plugin == null) return;
        JSObject payload = new JSObject();
        for (Map.Entry<String, String> entry : data.entrySet()) payload.put(entry.getKey(), entry.getValue());
        JSObject ret = new JSObject();
        ret.put("data", payload);
        plugin.notifyListeners("received", ret);
    }

    /** <b>معرّفُ التطبيق من البيان</b> ({@code appid=<…>} — يُخبز من {@code TAXO_HMS_APP_ID})، وفارغٌ = لا حسابَ بعد. */
    static String appIdOf(android.content.Context context) {
        try {
            ApplicationInfo info = context.getPackageManager()
                    .getApplicationInfo(context.getPackageName(), PackageManager.GET_META_DATA);
            String value = info.metaData == null ? null : info.metaData.getString("com.huawei.hms.client.appid");
            if (value == null) return "";
            return value.startsWith("appid=") ? value.substring(6).trim() : value.trim();
        } catch (Exception missing) {
            return "";
        }
    }
}
