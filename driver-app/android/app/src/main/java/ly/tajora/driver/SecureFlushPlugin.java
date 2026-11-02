package ly.tajora.driver;

import android.content.Context;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * <b>رمزُ الجلسة على القرص قبل أن يُقال «حُفظ»</b> (SPEC §٢٣.٢-أ، الجزء B من أمر المالك ٢٠٢٦-١١-٠٢).
 *
 * <p><b>العطبُ الذي أنشأه — مقيسٌ على المحاكي</b>: {@code @aparajita/capacitor-secure-storage} يحفظ بـ{@code apply()}، فيعود
 * «حُفظ» والكتابةُ إلى القرص لم تقع بعد. <b>وقتلُ التطبيق وهو أمام صاحبه في الأجزاء من الثانية التالية لتدوير الرمز</b>
 * (نفادُ البطارية، إعادةُ التشغيل، قتلُ النظام) <b>يُبقي الرمزَ القديمَ على القرص</b> — وهو مُدوَّرٌ ذو استعمالٍ واحد، فالفتحةُ
 * التالية تقدّمه ثانيةً ⇐ {@code reuse_detected} ⇐ تُبطَل الجلسة ويخرج صاحبُها.
 *
 * <p><b>والإصلاحُ هنا لا في الحزمة</b>: {@code commit()} على الملفّ نفسِه يكتب <b>كلَّ</b> ما في الذاكرة إلى القرص كتابةً
 * متزامنة — وفيه ما وضعه {@code apply()} قبله — <b>ولا يعود حتى يقع</b>. والنسخةُ المخزَّنةُ من التفضيلات واحدةٌ في العمليّة،
 * فالذاكرةُ التي يكتبها هي التي كتب فيها الملحق. <b>ولا يقرأ قيمةً ولا يكتبها</b>: يُمضي ما كُتب فقط.
 */
@CapacitorPlugin(name = "SecureFlush")
public class SecureFlushPlugin extends Plugin {

    /** اسمُ ملفِّ الملحق — {@code SecureStorage.SHARED_PREFERENCES} حرفاً. */
    private static final String SECURE_PREFS = "WSSecureStorageSharedPreferences";

    @PluginMethod
    public void flush(PluginCall call) {
        boolean written = getContext()
            .getSharedPreferences(SECURE_PREFS, Context.MODE_PRIVATE)
            .edit()
            .commit();
        if (written) call.resolve();
        else call.reject("تعذّرت كتابةُ المخزن الآمن إلى القرص");
    }
}
