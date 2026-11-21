package ly.tajora.rider;

import android.appwidget.AppWidgetManager;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
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
        // **ودجاتُ الأمر الثامن** (٢٠/١١): عند كلِّ إقلاعٍ تتبع ما كُتب آخرَ مرّة — بعد التحديث وقبل أن يكتب الويب؛
        // **وبلا `w_kinds` أو بمفتاحٍ مطفأ لا يُظهر شيئاً** (البيانُ يُطفئها)
        try {
            TaxoWidgets.sync(getContext());
        } catch (Exception ignored) {
            // مُدير الودجات غائبٌ في هذا الجهاز — لا ودجات
        }
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

    /**
     * <b>«أضف ودجت TAXO لشاشتك»</b> (أمرُ المالك ٢٠٢٦-١١-٢١ الثالث، البند ٣) — أيقبل المشغِّلُ طلبَ تثبيت هذه الودجة بلمسة؟
     * <b>أندرويد ٨ فما فوق، ومشغِّلٌ يدعمه، ومزوّدٌ مشتعل</b> ({@code TaxoWidgets.sync} يُشعله حين يشتعل مفتاحُ الودجات لدولته) —
     * وإلا {@code false} فلا تُرسم البطاقةُ أصلاً.
     */
    @PluginMethod
    public void pinSupported(PluginCall call) {
        JSObject ret = new JSObject();
        ret.put("supported", pinReady(getContext(), call.getString("kind", "")));
        call.resolve(ret);
    }

    /** يطلب التثبيت — <b>المشغِّلُ يسأل المستخدمَ بنافذته هو</b>، ولا شيءَ يُثبَّت بلا موافقته. و{@code requested} أنّ الطلبَ قُبل لا أنّه ثُبّت. */
    @PluginMethod
    public void pinWidget(PluginCall call) {
        Context ctx = getContext();
        String kind = call.getString("kind", "");
        boolean requested = false;
        if (pinReady(ctx, kind)) {
            try {
                requested = AppWidgetManager.getInstance(ctx).requestPinAppWidget(new ComponentName(ctx, TaxoWidgets.provider(kind)), null, null);
            } catch (Exception ignored) {
                // المشغِّلُ رفض الطلب — يُقال «لم يُقبل» ولا شيءَ غيرُه
            }
        }
        JSObject ret = new JSObject();
        ret.put("requested", requested);
        call.resolve(ret);
    }

    static boolean pinReady(Context ctx, String kind) {
        if (Build.VERSION.SDK_INT < 26 || kind == null || kind.isEmpty()) return false;
        try {
            AppWidgetManager manager = AppWidgetManager.getInstance(ctx);
            if (manager == null || !manager.isRequestPinAppWidgetSupported()) return false;
            ComponentName name = new ComponentName(ctx, TaxoWidgets.provider(kind));
            return ctx.getPackageManager().getComponentEnabledSetting(name) == PackageManager.COMPONENT_ENABLED_STATE_ENABLED;
        } catch (Exception e) {
            return false;
        }
    }

    /** يوقظ البلاطةَ والأداةَ لتقرآ الجديد — <b>وما لا وجودَ له في هذا التطبيق يُتجاوز بلا أثر</b>. */
    public static void wake(Context ctx) {
        ctx.sendBroadcast(new Intent(CHANGED).setPackage(ctx.getPackageName()));
        // **ودجاتُ الأمر الثامن** (٢٠/١١): ما يُدرج في المنتقي، ورسمُ ما على الشاشة — والمطفأةُ لا تسمع البثّ فتُنادى هنا
        TaxoWidgets.sync(ctx);
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
