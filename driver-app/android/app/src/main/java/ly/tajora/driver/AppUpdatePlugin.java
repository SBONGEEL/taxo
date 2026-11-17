package ly.tajora.driver;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.google.android.play.core.appupdate.AppUpdateInfo;
import com.google.android.play.core.appupdate.AppUpdateManager;
import com.google.android.play.core.appupdate.AppUpdateManagerFactory;
import com.google.android.play.core.appupdate.AppUpdateOptions;
import com.google.android.play.core.install.InstallStateUpdatedListener;
import com.google.android.play.core.install.model.AppUpdateType;
import com.google.android.play.core.install.model.InstallStatus;
import com.google.android.play.core.install.model.UpdateAvailability;

/**
 * <b>«يوجد تحديث» من Google Play داخل التطبيق</b> (SPEC §١٠٣ المرحلة A/8، أمرُ المالك ٢٠٢٦-١١-١٦) — Play In-App Updates.
 *
 * <p><b>الحكمُ ليس هنا</b>: إلزاميٌّ أم اختياريٌّ يقوله إعدادُ الإصدارات في اللوحة ({@code /public/app-version})، وتسأل بوّابةُ التحديث
 * في الويب. <b>وهذا يجيب سؤالاً واحداً</b>: أيقدر Play أن يحدّث هذه النسخةَ الآن؟ — فإن قدر: <b>الإلزاميُّ فوريٌّ</b> (شاشةُ Play
 * بملء الشاشة) <b>والاختياريُّ مرن</b> (تنزيلٌ في الخلفية ثمّ إعادةُ تشغيلٍ بلمسةٍ من Play).
 *
 * <p><b>ونسخةٌ لم تأتِ من Play</b> (صفحةُ التنزيل، المسارُ المغلقُ المثبَّتُ يدويّاً) يجيب Play عنها «لا تحديث» أو يفشل —
 * فيُعاد {@code started: false} <b>ويفتح الويبُ الرابطَ كما كان</b>. لا تُحجب أحدٌ لأن Play لم يعرفه.
 *
 * <p><b>وشيفرتُه شيفرةُ {@code customer-app} حرفاً إلا اسمَ الحزمة.</b>
 */
@CapacitorPlugin(name = "AppUpdate")
public class AppUpdatePlugin extends Plugin {

    private static final int REQUEST = 4310;
    private AppUpdateManager manager;
    private InstallStateUpdatedListener installListener;

    private AppUpdateManager manager() {
        if (manager == null) manager = AppUpdateManagerFactory.create(getContext());
        return manager;
    }

    /** <b>يبدأ التحديث إن قدر Play</b> — {@code immediate: true} للإلزاميّ. يُحلّ دائماً بـ{@code started}، ولا يُرفض. */
    @PluginMethod
    public void start(PluginCall call) {
        boolean immediate = Boolean.TRUE.equals(call.getBoolean("immediate", false));
        int type = immediate ? AppUpdateType.IMMEDIATE : AppUpdateType.FLEXIBLE;
        if (getActivity() == null) {
            resolve(call, false, "no_activity");
            return;
        }
        manager().getAppUpdateInfo()
                .addOnSuccessListener(info -> launch(call, info, type))
                .addOnFailureListener(e -> resolve(call, false, "play_unavailable"));
    }

    private void launch(PluginCall call, AppUpdateInfo info, int type) {
        boolean available = info.updateAvailability() == UpdateAvailability.UPDATE_AVAILABLE
                || info.updateAvailability() == UpdateAvailability.DEVELOPER_TRIGGERED_UPDATE_IN_PROGRESS;
        if (!available || !info.isUpdateTypeAllowed(type)) {
            resolve(call, false, "not_available");
            return;
        }
        if (type == AppUpdateType.FLEXIBLE) watchFlexible();
        try {
            boolean ok = manager().startUpdateFlowForResult(
                    info, getActivity(), AppUpdateOptions.newBuilder(type).build(), REQUEST);
            resolve(call, ok, ok ? "started" : "not_started");
        } catch (Exception e) {
            resolve(call, false, "launch_failed");
        }
    }

    /** <b>المرنُ ينزل في الخلفية</b> — وحين يكتمل تعيد Play تشغيلَ التطبيق على النسخة الجديدة (اختارها صاحبُها بـ«حمّل الآن»). */
    private void watchFlexible() {
        if (installListener != null) return;
        installListener = state -> {
            if (state.installStatus() == InstallStatus.DOWNLOADED) {
                manager().completeUpdate();
            }
            if (state.installStatus() == InstallStatus.INSTALLED
                    || state.installStatus() == InstallStatus.FAILED
                    || state.installStatus() == InstallStatus.CANCELED) {
                manager().unregisterListener(installListener);
                installListener = null;
            }
        };
        manager().registerListener(installListener);
    }

    private static void resolve(PluginCall call, boolean started, String reason) {
        JSObject ret = new JSObject();
        ret.put("started", started);
        ret.put("reason", reason);
        call.resolve(ret);
    }

    @Override
    protected void handleOnDestroy() {
        if (installListener != null && manager != null) manager.unregisterListener(installListener);
        installListener = null;
        super.handleOnDestroy();
    }
}
