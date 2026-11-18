package ly.tajora.driver;

import android.content.Context;
import android.content.SharedPreferences;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * <b>تعطّلُ أندرويد الأصليّ يصل اللوحة</b> (SPEC §١٠٣ C/41) — {@link #install} يلفّ ماسكَ النظام: عند تعطّلٍ لا يُمسك يُحفظ <b>اسمُ الاستثناء
 * وإطاراتُ المكدَّس وحدَها</b> (لا نصَّ الرسالة: قد يحمل رقماً أو عنواناً) ثمّ يمضي التعطّلُ كما كان. وفي الإقلاع التالي يأخذه الويب
 * ({@code take}) ويرسله بباب تقارير الأعطال القائم — بسقفه ومفتاح إطفائه. نسخةُ التطبيق الآخر حرفاً إلا الحزمة.
 */
@CapacitorPlugin(name = "NativeCrash")
public class NativeCrashPlugin extends Plugin {

    private static final String PREFS = "taxo_native_crash";
    private static final int MAX_FRAMES = 20;
    private static final int MAX_CAUSES = 4;

    /** يُنادى أوّلَ {@code onCreate}، مرّةً واحدة. */
    public static void install(Context context) {
        final Context app = context.getApplicationContext();
        final Thread.UncaughtExceptionHandler previous = Thread.getDefaultUncaughtExceptionHandler();
        if (previous instanceof Catcher) return;
        Thread.setDefaultUncaughtExceptionHandler(new Catcher(app, previous));
    }

    private static final class Catcher implements Thread.UncaughtExceptionHandler {
        private final Context app;
        private final Thread.UncaughtExceptionHandler previous;

        Catcher(Context app, Thread.UncaughtExceptionHandler previous) {
            this.app = app;
            this.previous = previous;
        }

        @Override
        public void uncaughtException(Thread thread, Throwable error) {
            try {
                app.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                        .putString("name", nameOf(error))
                        .putString("stack", framesOf(error))
                        .putLong("at", System.currentTimeMillis())
                        .commit();
            } catch (Throwable ignored) {
                // الحفظُ نفسُه لا يُسقط ما بعده
            }
            if (previous != null) previous.uncaughtException(thread, error);
        }
    }

    /** خالصة: اسمُ الاستثناء الأعمق — «Caused by» هو العلّة. */
    static String nameOf(Throwable error) {
        Throwable root = error;
        int guard = 0;
        while (root.getCause() != null && root.getCause() != root && guard++ < 10) root = root.getCause();
        String outer = error.getClass().getName();
        String inner = root.getClass().getName();
        return outer.equals(inner) ? outer : outer + " ← " + inner;
    }

    /** خالصة: «الصنف.الدالّة(الملف:السطر)» سطراً سطراً — بلا نصِّ رسالة. <b>والسقفُ لكلِّ استثناءٍ لا للمكدَّس كلِّه</b> (قِيس في CI
     *  ٢٠٢٦-١١-١٨): سقفٌ واحدٌ يستنفده المكدَّسُ الخارجيّ — إطاراتُ النظام — <b>فلا يبلغ «Caused by»، وهو العلّة</b>. */
    static String framesOf(Throwable error) {
        StringBuilder out = new StringBuilder();
        Throwable current = error;
        int guard = 0;
        while (current != null && guard++ < MAX_CAUSES) {
            if (current != error) out.append("Caused by ").append(current.getClass().getName()).append('\n');
            int frames = 0;
            for (StackTraceElement frame : current.getStackTrace()) {
                if (frames++ >= MAX_FRAMES) {
                    out.append("    ...\n");
                    break;
                }
                out.append("    at ").append(frame.toString()).append('\n');
            }
            current = current.getCause() == current ? null : current.getCause();
        }
        return out.toString();
    }

    @PluginMethod
    public void take(PluginCall call) {
        SharedPreferences prefs = getContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        JSObject out = new JSObject();
        String name = prefs.getString("name", null);
        if (name != null) {
            out.put("name", name);
            out.put("stack", prefs.getString("stack", ""));
            out.put("at", prefs.getLong("at", 0));
            prefs.edit().clear().apply();
        }
        call.resolve(out);
    }
}
