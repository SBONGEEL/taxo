package ly.tajora.driver;

import android.Manifest;
import android.app.NotificationManager;
import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.PowerManager;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * حالُ الأذونات الحيّة، وبطاقةُ الطلب فوق كلِّ شيء.
 *
 * <p><b>وشاشةُ الأذونات حالٌ لا معالج</b> (قرارُ المالك): تُقرأ من النظام في
 * كلِّ فتحةٍ ولا تُحفظ إجابةٌ قديمة — <b>لأن المستخدمَ يسحب الإذنَ من إعدادات
 * الهاتف ولا يمرّ بنا</b>، فذاكرةٌ عن إذنٍ مُنح أمسِ تكذب اليوم.
 *
 * <p><b>وما لا نعرفه نقوله «لا نعرف»</b>: لا يقول هذا الجسرُ شيئاً عن إعدادات
 * المصنّع (توفيرُ طاقةٍ خاصٌّ بسامسونغ، «تشغيل تلقائيّ»، قوائمُ بيضاءُ لا
 * تُقرأ برمجيّاً) — <b>ولا API يقرؤها</b>، والادّعاءُ أنّها ضُبطت أسوأُ من
 * السكوت لأنه يوقف صاحبَه عن البحث حين ينقطع عمله.
 */
@CapacitorPlugin(name = "OfferAlert")
public class OfferAlertPlugin extends Plugin {

    private boolean granted(String permission) {
        return getContext().checkSelfPermission(permission)
                == PackageManager.PERMISSION_GRANTED;
    }

    /**
     * حالُ كلِّ إذنٍ يهمّ الاستقبال — <b>مقروءاً من النظام لحظتَه</b>.
     *
     * <p>و{@code batteryUnrestricted} <b>ليس إذناً بل إعفاء</b>: بدونه يُوقف
     * النظامُ خدمةَ الموقع بعد دقائقَ من إطفاء الشاشة، <b>فيبدو الكبتنُ متصلاً
     * وهو غيرُ موجود</b> — وذاك أخطرُ من انقطاعٍ ظاهر.
     */
    @PluginMethod
    public void status(PluginCall call) {
        Context context = getContext();
        JSObject out = new JSObject();

        out.put("notifications",
                Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU
                        || granted(Manifest.permission.POST_NOTIFICATIONS));
        out.put("location", granted(Manifest.permission.ACCESS_FINE_LOCATION));
        out.put("backgroundLocation",
                Build.VERSION.SDK_INT < Build.VERSION_CODES.Q
                        || granted(Manifest.permission.ACCESS_BACKGROUND_LOCATION));
        out.put("overlay", OfferAlert.canDrawOverlay(context));
        out.put("fullScreenIntent", OfferAlert.canUseFullScreen(context));

        PowerManager power = context.getSystemService(PowerManager.class);
        out.put("batteryUnrestricted",
                power != null && power.isIgnoringBatteryOptimizations(context.getPackageName()));

        NotificationManager manager = context.getSystemService(NotificationManager.class);
        boolean channelOn = true;
        if (manager != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            OfferAlert.ensureChannel(context);
            android.app.NotificationChannel channel =
                    manager.getNotificationChannel(OfferAlert.CHANNEL_ID);
            channelOn = channel != null
                    && channel.getImportance() != NotificationManager.IMPORTANCE_NONE;
        }
        // **قناةُ الطلبات وحدَها**: مفتاحُ الإشعارات العامُّ قد يكون مفتوحاً
        // وقناةُ الطلبات مطفأةً بيد المستخدم — <b>وهو صمتٌ لا يفسّره شيء</b>
        out.put("offerChannel", channelOn);

        // **ولا يُدَّعى شيءٌ عن إعدادات المصنّع** — انظر توثيق الصنف
        out.put("manufacturerSettingsKnown", false);
        call.resolve(out);
    }

    @PluginMethod
    public void requestOverlay(PluginCall call) {
        getContext().startActivity(OfferAlert.overlaySettings(getContext()));
        call.resolve();
    }

    @PluginMethod
    public void requestFullScreenIntent(PluginCall call) {
        getContext().startActivity(OfferAlert.fullScreenSettings(getContext()));
        call.resolve();
    }

    @PluginMethod
    public void openAppSettings(PluginCall call) {
        getContext().startActivity(OfferAlert.appSettings(getContext()));
        call.resolve();
    }

    /**
     * يُظهر البطاقة — <b>واحدةً من الأربع، والاختيارُ في {@link OfferAlert}</b>.
     *
     * <p><b>والحمولةُ كاملةٌ لا عنواناً ونصّاً</b>: الأسطحُ الثلاثةُ ترسم
     * الأجرةَ والمسافةَ والطريقَ والمهلةَ بأحجامها — <b>وجملةٌ مصوغةٌ في
     * الويب تُفقدها ذلك كلَّه</b>، وهي قاعدةُ «`data` تحمل القيم خاماً»
     * نفسُها في `services/notifications.py`.
     */
    @PluginMethod
    public void show(PluginCall call) {
        OfferAlert.show(getContext(), new OfferData(
                call.getString("rideId", ""),
                call.getString("fare", ""),
                call.getString("currency", ""),
                call.getString("method", ""),
                call.getString("category", ""),
                call.getString("distance", ""),
                call.getString("pickup", ""),
                call.getString("drop", ""),
                call.getInt("seconds", 7)
        ));
        call.resolve();
    }

    /**
     * <b>ما تحتاجه هذه الأسطحُ لتقبل بنفسها</b> — قاعدةُ الخدمة ورمزُ الوصول.
     *
     * <p><b>ويُنادى مع كلِّ تجديدٍ للرمز</b> لا مرّةً عند الدخول: الرمزُ عمرُه
     * ثلاثون دقيقة، <b>وواحدٌ محفوظٌ منذ ساعةٍ يجعل «اقبل» يسقط بصمت</b>.
     * ويُمحى بالخروج بتمرير فارغَين.
     */
    @PluginMethod
    public void setSession(PluginCall call) {
        OfferApi.remember(
                getContext(),
                call.getString("apiBase", null),
                call.getString("accessToken", null)
        );
        call.resolve();
    }

    @PluginMethod
    public void hide(PluginCall call) {
        OfferAlert.hide(getContext());
        call.resolve();
    }
}
