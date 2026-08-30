package ly.tajora.driver;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/**
 * مسبارُ بطاقةِ الطلب — <b>في النكهة التجريبيّة وحدَها، ومعزولٌ بالبناء لا بالنيّة</b>.
 *
 * <p><b>ولمَ وُجد</b>: شرطُ المالك أن يُقاس على الجهاز «بالإذن تظهر الفقاعة
 * والتطبيق مغلق · وبلا الإذن يظهر الإشعار ملء الشاشة · ولا تظهر الاثنتان معاً».
 * <b>وذلك لا يقع إلا بطلبٍ حقيقيّ</b> — ورحلةٌ حقيقيّةٌ في كلِّ قياسٍ تعني
 * راكباً وكبتناً وشبكةً في كلِّ مرّة، <b>ويبقى ما يُقاس مختلطاً بثلاثةِ أشياء</b>.
 *
 * <p><b>وعزلُه بالبناء لا بشرطٍ في الشيفرة</b> (قرارُ المالك 2026-08-29 في
 * تشخيصٍ سابق): موضعُه {@code src/trial} — <b>فحزمةُ القناة العامّة لا تحتوي
 * هذا الملفَّ أصلاً</b>، ولا يوجد شرطٌ يُنسى إطفاؤه. <b>وشرطٌ يُقرأ في زمن
 * التشغيل كان سيبقى في الحزمة</b> ويُفتح بمن يعرف اسمَه.
 *
 * <p><b>ويُنزع بعد أن يُقرأ السبب</b> — وهو أمرُ المالك في التشخيص السابق نفسِه.
 */
public class OfferProbe extends BroadcastReceiver {

    public static final String ACTION = "ly.tajora.driver.test.SHOW_OFFER";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (!ACTION.equals(intent.getAction())) return;
        if ("hide".equals(intent.getStringExtra("mode"))) {
            OfferAlert.hide(context);
            return;
        }
        // **وإجبارُ السطح للقياس وحدَه** (`--es force sheet|bubble|full`):
        // الفرقُ بين «ورقة» و«فقاعة» يقوم على قربِ العهد بالتطبيق، **وانتظارُ
        // دقيقتين بين كلِّ قياسٍ وآخرَ يجعل القياسَ لا يقع** — والإجبارُ في
        // `src/trial` وحدَه، **فحزمةُ القناة العامّة لا تحمل هذا الملفَّ أصلاً**.
        String force = intent.getStringExtra("force");

        // **قيمُ التصميم نفسُها** — فما يُقاس هو ما رُسم: أجرةُ ٢٫٧٥ و«١٫٢ كم»
        // و«الدوار السابع، عمّان» ← «مجمّع رغدان، وسط البلد»
        OfferData data = new OfferData(
                intent.getStringExtra("ride_id") == null
                        ? "probe-ride" : intent.getStringExtra("ride_id"),
                intent.getStringExtra("fare") == null
                        ? "٢٫٧٥" : intent.getStringExtra("fare"),
                "د.أ",
                intent.getStringExtra("method") == null
                        ? "" : intent.getStringExtra("method"),
                "اقتصادي",
                "١٫٢ كم",
                "الدوار السابع، عمّان",
                "مجمّع رغدان، وسط البلد",
                intent.getIntExtra("timeout", 7)
        );
        if ("sheet".equals(force)) {
            OfferSheetWindow.show(context, data);
        } else if ("bubble".equals(force)) {
            OfferBubble.show(context, data);
        } else if ("full".equals(force) || "locked".equals(force)) {
            OfferAlert.ensureChannel(context);
            android.content.Intent screen =
                    new android.content.Intent(context, OfferActivity.class);
            screen.setFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK
                    | android.content.Intent.FLAG_ACTIVITY_CLEAR_TOP);
            screen.putExtras(data.toBundle());
            screen.putExtra(OfferActivity.EXTRA_LOCKED, "locked".equals(force));
            context.startActivity(screen);
        } else {
            OfferAlert.show(context, data);
        }
    }
}
