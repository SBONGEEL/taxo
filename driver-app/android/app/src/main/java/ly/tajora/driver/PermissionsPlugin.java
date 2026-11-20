package ly.tajora.driver;

import android.Manifest;
import android.app.NotificationManager;
import android.content.ActivityNotFoundException;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.location.LocationManager;
import android.net.Uri;
import android.os.Build;
import android.os.PowerManager;
import android.provider.Settings;

import androidx.core.app.NotificationManagerCompat;
import androidx.core.content.ContextCompat;
import androidx.core.location.LocationManagerCompat;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;

import java.util.Locale;

/**
 * <b>مركزُ الأذونات</b> (SPEC §١٠٣ المرحلة A/28، أمرُ المالك ٢٠٢٦-١١-١٦) — <b>منسوخٌ بايتاً في التطبيقين</b> إلا سطرَ الحزمة
 * ({@code tools/check-permissions-plugin.mjs}).
 *
 * <p>ثلاثةُ أبواب: {@code status} يقرأ الحالَ الحيَّ لكلِّ إذنٍ <b>أعلنه البيانُ</b> (فلا صفَّ لإذنٍ لا يستعمله التطبيق)،
 * و{@code request} يطلب إذنَ وقت التشغيل من داخل التطبيق، و{@code open} يفتح <b>صفحةَ النظام الدقيقة</b> لذلك الإذن.
 * والتشغيلُ التلقائيُّ لا يقرؤه أندرويد لأحد — فحالُه {@code unknown}، وزرُّه يفتح صفحةَ المصنّع إن وُجدت.
 *
 * <p><b>وكلُّ فتحٍ يقول أين وقع</b> ({@code exact} · {@code vendor} · {@code details}): {@code details} يعني أن الصفحةَ الدقيقةَ لم تُفتح
 * فوقعنا على تفاصيل التطبيق، <b>فتعرض الصفحةُ خطواتِها المصوّرة</b> — لا يُقال «فُتحت» وما فُتح غيرُها.
 */
@CapacitorPlugin(
    name = "Permissions",
    permissions = {
        @Permission(alias = "location", strings = { Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION }),
        @Permission(alias = "location_background", strings = { "android.permission.ACCESS_BACKGROUND_LOCATION" }),
        @Permission(alias = "notifications", strings = { "android.permission.POST_NOTIFICATIONS" }),
        @Permission(alias = "microphone", strings = { Manifest.permission.RECORD_AUDIO }),
    }
)
public class PermissionsPlugin extends Plugin {

    /** صفحاتُ المصنّعين للتشغيل التلقائيّ — الأولى التي تُفتح تُستعمل، وإلا تفاصيلُ التطبيق. */
    private static final String[][] AUTOSTART = {
        { "xiaomi", "com.miui.securitycenter", "com.miui.permcenter.autostart.AutoStartManagementActivity" },
        { "redmi", "com.miui.securitycenter", "com.miui.permcenter.autostart.AutoStartManagementActivity" },
        { "poco", "com.miui.securitycenter", "com.miui.permcenter.autostart.AutoStartManagementActivity" },
        { "huawei", "com.huawei.systemmanager", "com.huawei.systemmanager.startupmgr.ui.StartupNormalAppListActivity" },
        { "huawei", "com.huawei.systemmanager", "com.huawei.systemmanager.optimize.process.ProtectActivity" },
        { "honor", "com.hihonor.systemmanager", "com.hihonor.systemmanager.startupmgr.ui.StartupNormalAppListActivity" },
        { "oppo", "com.coloros.safecenter", "com.coloros.safecenter.permission.startup.StartupAppListActivity" },
        { "oppo", "com.coloros.safecenter", "com.coloros.safecenter.startupapp.StartupAppListActivity" },
        { "oppo", "com.oppo.safe", "com.oppo.safe.permission.startup.StartupAppListActivity" },
        { "realme", "com.coloros.safecenter", "com.coloros.safecenter.permission.startup.StartupAppListActivity" },
        { "oneplus", "com.oneplus.security", "com.oneplus.security.chainlaunch.view.ChainLaunchAppListActivity" },
        { "vivo", "com.vivo.permissionmanager", "com.vivo.permissionmanager.activity.BgStartUpManagerActivity" },
        { "vivo", "com.iqoo.secure", "com.iqoo.secure.ui.phoneoptimize.AddWhiteListActivity" },
        { "samsung", "com.samsung.android.lool", "com.samsung.android.sm.battery.ui.BatteryActivity" },
        { "samsung", "com.samsung.android.sm", "com.samsung.android.sm.battery.ui.BatteryActivity" },
        { "infinix", "com.transsion.phonemaster", "com.cyin.himgr.autostart.AutoStartActivity" },
        { "tecno", "com.transsion.phonemaster", "com.cyin.himgr.autostart.AutoStartActivity" },
        { "itel", "com.transsion.phonemaster", "com.cyin.himgr.autostart.AutoStartActivity" },
    };

    private boolean declared(String permission) {
        try {
            String[] list = getContext().getPackageManager()
                .getPackageInfo(getContext().getPackageName(), PackageManager.GET_PERMISSIONS).requestedPermissions;
            if (list == null) return false;
            for (String item : list) if (permission.equals(item)) return true;
        } catch (Exception ignored) {
            // بيانٌ لا يُقرأ — لا صفَّ يُعلن ما لا يُعرف
        }
        return false;
    }

    private boolean granted(String permission) {
        return ContextCompat.checkSelfPermission(getContext(), permission) == PackageManager.PERMISSION_GRANTED;
    }

    static String brand() {
        return (Build.MANUFACTURER == null ? "" : Build.MANUFACTURER).toLowerCase(Locale.ROOT);
    }

    static boolean hasVendorAutostart() {
        String b = brand();
        for (String[] row : AUTOSTART) if (b.contains(row[0])) return true;
        return false;
    }

    private void put(JSArray out, String key, Boolean on) {
        JSObject row = new JSObject();
        row.put("key", key);
        if (on == null) row.put("state", "unknown");
        else row.put("state", on ? "on" : "off");
        out.put(row);
    }

    @PluginMethod
    public void status(PluginCall call) {
        Context ctx = getContext();
        JSArray rows = new JSArray();
        if (declared(Manifest.permission.ACCESS_FINE_LOCATION)) {
            put(rows, "location", granted(Manifest.permission.ACCESS_FINE_LOCATION) || granted(Manifest.permission.ACCESS_COARSE_LOCATION));
            // **زرُّ الموقع في الهاتف** (SPEC §١٠٩-ج) — غيرُ إذن التطبيق: إذنٌ ممنوحٌ وGPS مطفأٌ لا موقعَ لهما. يقرؤه «لم نتمكن من
            // تحديد موقعك» ليقول السببَ الصحيح ويفتح الصفحةَ الصحيحة، **ولا يُعرض صفّاً في مركز الأذونات** (ليس إذناً)
            LocationManager lm = (LocationManager) ctx.getSystemService(Context.LOCATION_SERVICE);
            put(rows, "location_services", lm == null ? null : LocationManagerCompat.isLocationEnabled(lm));
        }
        if (declared("android.permission.ACCESS_BACKGROUND_LOCATION")) {
            // قبل أندرويد ١٠ لا إذنَ منفصلاً — الموقعُ يكفي
            put(rows, "location_background", Build.VERSION.SDK_INT < 29
                ? granted(Manifest.permission.ACCESS_FINE_LOCATION)
                : granted("android.permission.ACCESS_BACKGROUND_LOCATION"));
        }
        put(rows, "notifications", NotificationManagerCompat.from(ctx).areNotificationsEnabled());
        if (declared(Manifest.permission.SYSTEM_ALERT_WINDOW)) {
            put(rows, "overlay", Build.VERSION.SDK_INT < 23 || Settings.canDrawOverlays(ctx));
        }
        if (declared(Manifest.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)) {
            PowerManager pm = (PowerManager) ctx.getSystemService(Context.POWER_SERVICE);
            put(rows, "battery", pm != null && pm.isIgnoringBatteryOptimizations(ctx.getPackageName()));
            if (hasVendorAutostart()) put(rows, "autostart", null);
        }
        if (declared("android.permission.USE_FULL_SCREEN_INTENT")) {
            boolean on = true;
            if (Build.VERSION.SDK_INT >= 34) {
                NotificationManager nm = (NotificationManager) ctx.getSystemService(Context.NOTIFICATION_SERVICE);
                on = nm != null && nm.canUseFullScreenIntent();
            }
            put(rows, "full_screen", on);
        }
        if (declared(Manifest.permission.RECORD_AUDIO)) {
            put(rows, "microphone", granted(Manifest.permission.RECORD_AUDIO));
        }
        JSObject ret = new JSObject();
        ret.put("rows", rows);
        ret.put("brand", brand());
        ret.put("sdk", Build.VERSION.SDK_INT);
        call.resolve(ret);
    }

    /** إذنُ وقت التشغيل من داخل التطبيق — وما ليس كذلك (الفقاعة، البطارية، ملءُ الشاشة) يُفتح بصفحته. */
    @PluginMethod
    public void request(PluginCall call) {
        String key = call.getString("key", "");
        if ("notifications".equals(key) && Build.VERSION.SDK_INT < 33) {
            // قبل ١٣ لا يُطلب إذنُ الإشعارات — يُفتح بابُها
            open(call);
            return;
        }
        if ("location".equals(key) || "location_background".equals(key) || "notifications".equals(key) || "microphone".equals(key)) {
            requestPermissionForAlias(key, call, "requested");
            return;
        }
        open(call);
    }

    @PermissionCallback
    private void requested(PluginCall call) {
        status(call);
    }

    @PluginMethod
    public void open(PluginCall call) {
        String key = call.getString("key", "");
        Context ctx = getContext();
        String pkg = ctx.getPackageName();
        Intent exact = null;
        switch (key) {
            case "notifications":
                if (Build.VERSION.SDK_INT >= 26) {
                    exact = new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, pkg);
                }
                break;
            case "overlay":
                exact = new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:" + pkg));
                break;
            case "battery":
                exact = new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:" + pkg));
                break;
            case "full_screen":
                if (Build.VERSION.SDK_INT >= 34) {
                    exact = new Intent(Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT, Uri.parse("package:" + pkg));
                }
                break;
            case "location_services":
                // **صفحةُ «الموقع» في إعدادات الهاتف** — حيث زرُّ GPS نفسُه، لا أذوناتُ التطبيق
                exact = new Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS);
                break;
            case "autostart":
                if (openVendor()) {
                    resolveOpened(call, "vendor");
                    return;
                }
                break;
            default:
                // الموقعُ والموقعُ في الخلفيّة والميكروفون: صفحتُها الدقيقةُ هي «أذوناتُ التطبيق» في تفاصيله
                break;
        }
        if (exact != null && start(exact)) {
            resolveOpened(call, "exact");
            return;
        }
        if ("battery".equals(key) && start(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))) {
            resolveOpened(call, "exact");
            return;
        }
        boolean details = start(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + pkg)));
        boolean permissionPage = "location".equals(key) || "location_background".equals(key) || "microphone".equals(key);
        resolveOpened(call, details ? (permissionPage ? "exact" : "details") : "none");
    }

    private boolean openVendor() {
        String b = brand();
        for (String[] row : AUTOSTART) {
            if (!b.contains(row[0])) continue;
            Intent intent = new Intent().setComponent(new ComponentName(row[1], row[2]));
            if (start(intent)) return true;
        }
        return false;
    }

    private boolean start(Intent intent) {
        try {
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
            if (intent.resolveActivity(getContext().getPackageManager()) == null && intent.getComponent() == null) return false;
            getContext().startActivity(intent);
            return true;
        } catch (ActivityNotFoundException | SecurityException e) {
            return false;
        }
    }

    private void resolveOpened(PluginCall call, String where) {
        JSObject ret = new JSObject();
        ret.put("opened", where);
        call.resolve(ret);
    }
}
