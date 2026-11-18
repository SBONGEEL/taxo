package ly.tajora.rider;

import android.os.SystemClock;
import android.view.KeyEvent;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * <b>زرُّ الصوت ثلاثاً للطوارئ</b> (SPEC §١٠٣ B/22) — <b>يشعله الراكبُ بنفسه ويختار جهتَه</b>، ويُسلَّح أثناء الرحلة الجارية وحدَها.
 *
 * <p>يعدّ ضغطاتِ «خفض الصوت» والتطبيقُ أمامه ({@link MainActivity#dispatchKeyEvent})؛ <b>ثلاثٌ في {@value #WINDOW_MS} مللي</b> ⇐ حدثُ
 * {@code trigger} إلى الويب، وهو يفعل الباقي (تنبيهُ الفريق ورسالةُ الجهة). <b>ولا يأكل الضغطة</b>: الصوتُ ينخفض كما اعتاد صاحبُه،
 * فلا يتغيّر شيءٌ لمن لم يُشعله. <b>وغيرُ مسلَّحٍ لا يعدّ شيئاً.</b>
 */
@CapacitorPlugin(name = "VolumeTrigger")
public class VolumeTriggerPlugin extends Plugin {

    static final int PRESSES = 3;
    static final long WINDOW_MS = 2_500L;

    private static VolumeTriggerPlugin instance;
    private static volatile boolean armed = false;
    private static final long[] presses = new long[PRESSES];
    private static int count = 0;

    @Override
    public void load() {
        instance = this;
    }

    @PluginMethod
    public void arm(PluginCall call) {
        armed = Boolean.TRUE.equals(call.getBoolean("on", false));
        synchronized (presses) {
            count = 0;
        }
        call.resolve();
    }

    /** خالصةٌ ومختبَرة: أهذه الضغطةُ الثالثةُ في النافذة؟ {@code times} أقدمُها أوّلاً، و{@code n} عددُ ما فيها. */
    static boolean completes(long[] times, int n, long now, long windowMs, int needed) {
        if (n < needed - 1) return false;
        long first = times[n - (needed - 1)];
        return now - first <= windowMs;
    }

    /** يُنادى من {@link MainActivity} على كلِّ مفتاح — <b>ولا يقرّر أكلَه</b>. */
    static void onKey(KeyEvent event) {
        if (!armed || event.getKeyCode() != KeyEvent.KEYCODE_VOLUME_DOWN || event.getAction() != KeyEvent.ACTION_DOWN
                || event.getRepeatCount() > 0) return;
        long now = SystemClock.elapsedRealtime();
        boolean fire;
        synchronized (presses) {
            fire = completes(presses, count, now, WINDOW_MS, PRESSES);
            if (fire) {
                count = 0;
            } else {
                if (count == PRESSES - 1) {
                    System.arraycopy(presses, 1, presses, 0, PRESSES - 2);
                    count = PRESSES - 2;
                }
                presses[count++] = now;
            }
        }
        VolumeTriggerPlugin plugin = instance;
        if (fire && plugin != null) plugin.notifyListeners("trigger", new JSObject(), true);
    }
}
