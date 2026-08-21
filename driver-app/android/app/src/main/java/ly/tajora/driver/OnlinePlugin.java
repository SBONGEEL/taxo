package ly.tajora.driver;

import android.content.Intent;
import android.os.Build;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * جسرٌ رفيعٌ بين حالة «متصل» في التطبيق و{@link OnlineService}.
 *
 * <p><b>ولا قرارَ فيه</b>: التطبيقُ وحدَه يقرّر متى يبدأ الاستقبالُ ومتى
 * ينتهي — تماماً كما لا تقرّر الواجهةُ مالاً. وهذه ثلاثةُ نداءاتٍ لا أكثر،
 * <b>ولا خدمةَ دائمةً لكبتنٍ غيرِ عامل</b>: {@code stop} يقع مع كلِّ فصلٍ.
 */
@CapacitorPlugin(name = "OnlineService")
public class OnlinePlugin extends Plugin {

    /**
     * يبدأ الاستقبال — <b>ومعه ما تحتاجه الخدمةُ لتبثّ بنفسها</b>.
     *
     * <p><b>ورمزُ الوصولِ يُمرَّر مع كلِّ نبضة</b> لا مرةً عند البدء: الويبُ
     * يجدّده وهو حيّ، فيبقى ما تحمله الخدمةُ أحدثَ ما صدر. <b>ولا يُمرَّر
     * رمزُ التجديد</b> — مُدوَّرٌ ذو استعمالٍ واحد (§23)، وحاملان له يخرجان
     * صاحبَه من حسابه.
     */
    @PluginMethod
    public void start(PluginCall call) {
        Intent intent = new Intent(getContext(), OnlineService.class);
        intent.putExtra("endpoint", call.getString("endpoint"));
        intent.putExtra("token", call.getString("token"));
        dispatch(intent);
        call.resolve();
    }

    /** المقبسُ سقط والكبتنُ ما زال «متصلاً» — فيقول الإشعارُ الحقيقة. */
    @PluginMethod
    public void degraded(PluginCall call) {
        send(OnlineService.ACTION_DEGRADED);
        call.resolve();
    }

    @PluginMethod
    public void stop(PluginCall call) {
        getContext().stopService(new Intent(getContext(), OnlineService.class));
        call.resolve();
    }

    private void send(String action) {
        Intent intent = new Intent(getContext(), OnlineService.class);
        if (action != null) intent.setAction(action);
        dispatch(intent);
    }

    private void dispatch(Intent intent) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            getContext().startForegroundService(intent);
        } else {
            getContext().startService(intent);
        }
    }
}
