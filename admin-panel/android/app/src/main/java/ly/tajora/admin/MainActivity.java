package ly.tajora.admin;

import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {

    @Override
    public void onCreate(Bundle savedInstanceState) {
        // **الملحقُ قبل الجسر** — Capacitor يسجّل ملحقاتِ الحزمة عند الإنشاء، وما يُسجَّل بعده لا تراه الصفحة
        registerPlugin(AdminAlertsPlugin.class);
        // **قنواتُ الفئات قبل أوّل إشعار** (SPEC §٨١/١١): قناةٌ لم تُنشأ تُسقط الإشعارَ إلى الاحتياطية بلا صوتها
        AdminChannels.ensure(this);
        super.onCreate(savedInstanceState);
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
