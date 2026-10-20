package ly.tajora.admin;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;

/**
 * <b>الجسرُ بين اللوحة وإشعارات المالك الأصليّة</b> (SPEC §٨١) — أربعةُ أشياءَ لا غير:
 *
 * <ul>
 *   <li>{@code version()} — <b>ما تحمله الحزمة</b>: {@code 51} (قنواتُ الفئات الستّ وخدمتُها). <b>اللوحةُ تسأل ولا تفترض</b>: شاشاتُها
 *       من الخادم فقد تكون أحدثَ من الحزمة، وحزمةٌ بلا هذا الملحق يصلها الإشعارُ كما يرسمه النظام.</li>
 *   <li>{@code configure({apiBase})} — <b>عنوانُ الخادم لزرِّ «مقروء»</b> من البناء نفسِه ({@code API_URL})، لا نسخةٌ في الحزمة.</li>
 *   <li>{@code preview(data)} — <b>يرسم إشعاراً على هذا الهاتف</b> بلا FCM: صفحةُ المعاينة تُري الشكلَ والصوتَ قبل الطرح.</li>
 *   <li>حدثُ {@code alertTap} — نقرةُ الإشعار تفتح سجلَّه، <b>والمسارُ يُشتقّ في اللوحة</b> من نوعه ومعرّفه.</li>
 * </ul>
 */
@CapacitorPlugin(name = "AdminAlerts")
public class AdminAlertsPlugin extends Plugin {

    /** = {@code services/admin_alerts.ADMIN_NATIVE} في الخادم. */
    static final int LEVEL = 51;
    private static final String PREFS = "taxo_admin_alerts";
    private static final String API_BASE = "api_base";

    /** <b>التطبيقُ أمامَ صاحبه</b> — يضبطه {@link MainActivity}، فلا يرسم {@link AdminAlertService} ما يعرضه الجرسُ أصلاً. */
    static volatile boolean inFront = false;

    static String apiBase(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(API_BASE, null);
    }

    @PluginMethod
    public void version(PluginCall call) {
        JSObject answer = new JSObject();
        answer.put("level", LEVEL);
        call.resolve(answer);
    }

    @PluginMethod
    public void configure(PluginCall call) {
        String base = call.getString("apiBase");
        if (base != null && (base.startsWith("https://") || base.startsWith("http://"))) {
            SharedPreferences prefs = getContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
            prefs.edit().putString(API_BASE, base.replaceAll("/+$", "")).apply();
        }
        call.resolve();
    }

    @PluginMethod
    public void preview(PluginCall call) {
        JSObject data = call.getData();
        Map<String, String> values = new HashMap<>();
        Iterator<String> keys = data.keys();
        while (keys.hasNext()) {
            String key = keys.next();
            values.put(key, data.optString(key, ""));
        }
        values.put("type", "admin_alert");
        AdminAlertNotifier.show(getContext(), values);
        call.resolve();
    }

    @Override
    public void load() {
        deliver(getActivity().getIntent());
    }

    @Override
    protected void handleOnNewIntent(Intent intent) {
        super.handleOnNewIntent(intent);
        deliver(intent);
    }

    private void deliver(Intent intent) {
        if (intent == null || !AdminAlertNotifier.ACTION_OPEN.equals(intent.getAction())) return;
        JSObject data = new JSObject();
        data.put("record_type", intent.getStringExtra(AdminAlertNotifier.EXTRA_RECORD_TYPE));
        data.put("record_id", intent.getStringExtra(AdminAlertNotifier.EXTRA_RECORD_ID));
        data.put("kind", intent.getStringExtra(AdminAlertNotifier.EXTRA_KIND));
        data.put("alert_id", intent.getStringExtra(AdminAlertNotifier.EXTRA_ALERT_ID));
        // **يُحفظ حتى يُصغى إليه** (`retainUntilConsumed`): التطبيقُ المقتولُ يُقلع من النقرة، والصفحةُ لم تُعلّق مستمعَها بعد
        notifyListeners("alertTap", data, true);
        // **ولا يُسلَّم مرّتين**: إعادةُ إنشاء النشاط (تدويرُ الشاشة) تقرأ النيّةَ نفسَها
        intent.setAction(null);

        // **«افتح» تعني «قُرئ»** — كما في الجرس: النقرُ على صفٍّ يجعله مقروءاً
        Intent read = new Intent(getContext(), AdminAlertReadReceiver.class).putExtras(intent);
        getContext().sendBroadcast(read.setPackage(getContext().getPackageName()));
    }
}
