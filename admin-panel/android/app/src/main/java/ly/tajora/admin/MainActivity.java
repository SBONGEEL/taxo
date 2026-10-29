package ly.tajora.admin;

import android.graphics.Color;
import android.os.Bundle;

import androidx.activity.EdgeToEdge;
import androidx.activity.SystemBarStyle;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    @Override
    public void onCreate(Bundle savedInstanceState) {
        // **الملحقُ قبل الجسر** — Capacitor يسجّل ملحقاتِ الحزمة عند الإنشاء، وما يُسجَّل بعده لا تراه الصفحة
        registerPlugin(AdminAlertsPlugin.class);
        // **قنواتُ الفئات قبل أوّل إشعار** (SPEC §٨١/١١): قناةٌ لم تُنشأ تُسقط الإشعارَ إلى الاحتياطية بلا صوتها
        AdminChannels.ensure(this);
        super.onCreate(savedInstanceState);
        // **العرضُ حتى الحافّة على كلِّ إصدار** (ملاحظةُ Google على 960، CODE-HEALTH ٤-٢): أندرويد ١٥+ يفرضه أصلاً بهدف SDK 35+،
        // **فيُفعَّل لما دونه أيضاً** فيرى الجميعُ الشكلَ نفسَه — والصفحةُ تحسب حواشيها بـ`env(safe-area-inset-*)`.
        // **وبعد `super` لا قبله** (قِيس على المحاكي ٢٠٢٦-١٠-٢٩): قبله يُنشئ النافذةَ بسمة الإقلاع قبل أن يضبط الجسرُ
        // سمةَ «بلا شريط»، **فيظهر شريطُ إجراءاتٍ باسم التطبيق فوق الصفحة**
        // **والأيقوناتُ فاتحةٌ دائماً** (قِيس على المحاكي ٢٠٢٦-١٠-٢٩): التطبيقُ ليليٌّ افتراضاً، والنمطُ التلقائيُّ يتبع وضعَ الهاتف —
        // فهاتفٌ بالوضع الفاتح يرسم أيقوناتٍ داكنةً فوق خلفيةٍ داكنةٍ فلا تُرى الساعةُ ولا البطارية
        EdgeToEdge.enable(this, SystemBarStyle.dark(Color.TRANSPARENT), SystemBarStyle.dark(Color.TRANSPARENT));
    }

    /** <b>التطبيقُ أمامَ صاحبه</b> — الجرسُ يعرض ما يصل ويعزف صوتَه، فلا يرسمه {@link AdminAlertService} مرّةً ثانية. */
    @Override
    public void onResume() {
        super.onResume();
        AdminAlertsPlugin.inFront = true;
    }

    @Override
    public void onPause() {
        super.onPause();
        AdminAlertsPlugin.inFront = false;
    }
}
