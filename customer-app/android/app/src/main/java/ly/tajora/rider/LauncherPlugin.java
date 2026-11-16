package ly.tajora.rider;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.service.quicksettings.TileService;

import androidx.core.content.pm.ShortcutInfoCompat;
import androidx.core.content.pm.ShortcutManagerCompat;
import androidx.core.graphics.drawable.IconCompat;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;

import org.json.JSONObject;

/**
 * <b>«المُطلِق»</b> (SPEC §١٠٣ المرحلة A/4، 5، 6، 10) — <b>منسوخٌ بايتاً في التطبيقين</b> إلا سطرَ الحزمة ({@code check:permissions-plugin}).
 *
 * <p>بابٌ واحدٌ بين الويب وما يُطلق التطبيقَ من خارجه: <b>اختصاراتُ الأيقونة</b>، وبلاطةُ الإعدادات السريعة، وأداةُ الشاشة الرئيسيّة،
 * وإشعارُ ما بعد الإقلاع. <b>كلُّها تحمل «فعلاً» ({@code taxo_action}) ولا تفعله</b>: الويبُ يستلمه ({@code consume} أو حدثُ
 * {@code action}) <b>وينفّذه بمساره القائم</b> — فلا بابَ ثانياً للاتصال يتجاوز فحصَ الاشتراك والأذونات، ولا مبلغَ يُحسب هنا.
 *
 * <p>و{@code setPrefs} يكتب ما يقرؤه الطرفُ الأصليّ وحدَه (المفاتيحُ مشتعلةٌ لدولته، «متّصل» الآن، ونصُّ الأداة كما صاغه الويب)
 * ثم يوقظ البلاطةَ والأداةَ لتقرآه — <b>وفي تطبيقٍ بلا بلاطةٍ ولا أداةٍ يمرّ الإيقاظُ بلا أثر</b>.
 */
@CapacitorPlugin(name = "Launcher")
public class LauncherPlugin extends Plugin {

    public static final String EXTRA = "taxo_action";
    public static final String PREFS = "taxo_launcher";
    public static final String CHANGED = "ly.tajora.LAUNCHER_CHANGED";

    private String pending;

    @Override
    public void load() {
        if (getActivity() != null) capture(getActivity().getIntent());
    }

    @Override
    protected void handleOnNewIntent(Intent intent) {
        super.handleOnNewIntent(intent);
        String action = capture(intent);
        if (action != null) {
            JSObject data = new JSObject();
            data.put("action", action);
            notifyListeners("action", data, true);
        }
    }

    private String capture(Intent intent) {
        if (intent == null) return null;
        String action = intent.getStringExtra(EXTRA);
        if (action == null) return null;
        intent.removeExtra(EXTRA);
        pending = action;
        return action;
    }

    /** الفعلُ الذي أُطلق به التطبيق (إقلاعٌ بارد) — يُعطى مرّةً ثم يُنسى. */
    @PluginMethod
    public void consume(PluginCall call) {
        JSObject ret = new JSObject();
        ret.put("action", pending);
        pending = null;
        call.resolve(ret);
    }

    /** اختصاراتُ الأيقونة — تُضبط من الويب حين يشتعل مفتاحُها، و{@code []} يزيلها. */
    @PluginMethod
    public void setShortcuts(PluginCall call) {
        Context ctx = getContext();
        JSArray items = call.getArray("items", new JSArray());
        List<ShortcutInfoCompat> list = new ArrayList<>();
        try {
            for (int i = 0; i < items.length(); i++) {
                JSONObject item = items.getJSONObject(i);
                Intent open = new Intent(ctx, MainActivity.class)
                    .setAction(Intent.ACTION_VIEW)
                    .putExtra(EXTRA, item.getString("action"))
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
                list.add(new ShortcutInfoCompat.Builder(ctx, item.getString("id"))
                    .setShortLabel(item.getString("label"))
                    .setIcon(IconCompat.createWithResource(ctx, R.mipmap.ic_launcher))
                    .setIntent(open)
                    .build());
            }
            ShortcutManagerCompat.setDynamicShortcuts(ctx, list);
            call.resolve();
        } catch (Exception e) {
            call.reject("تعذّر ضبطُ الاختصارات", e);
        }
    }

    /** ما يقرؤه الطرفُ الأصليّ وحدَه — قيمٌ بسيطة (منطقيّةٌ أو نصّ)، ثم إيقاظُ البلاطة والأداة. */
    @PluginMethod
    public void setPrefs(PluginCall call) {
        Context ctx = getContext();
        SharedPreferences.Editor edit = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit();
        JSObject data = call.getData();
        Iterator<String> keys = data.keys();
        while (keys.hasNext()) {
            String key = keys.next();
            Object value = data.opt(key);
            if (value instanceof Boolean) edit.putBoolean(key, (Boolean) value);
            else if (value == null || value == JSONObject.NULL) edit.remove(key);
            else edit.putString(key, String.valueOf(value));
        }
        edit.apply();
        wake(ctx);
        call.resolve();
    }

    /** يوقظ البلاطةَ والأداةَ لتقرآ الجديد — <b>وما لا وجودَ له في هذا التطبيق يُتجاوز بلا أثر</b>. */
    public static void wake(Context ctx) {
        ctx.sendBroadcast(new Intent(CHANGED).setPackage(ctx.getPackageName()));
        if (Build.VERSION.SDK_INT >= 24) {
            try {
                String pkg = LauncherPlugin.class.getPackage().getName();
                TileService.requestListeningState(ctx, new ComponentName(ctx, pkg + ".OnlineTileService"));
            } catch (Exception ignored) {
                // لا بلاطةَ في هذا التطبيق
            }
        }
    }
}
