package ly.tajora.driver;

import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        // **التسجيلُ قبل `super`**: الجسرُ يُبنى داخل `super.onCreate`، وما
        // يُسجَّل بعده لا يجده الويبُ حين ينادي — عطبٌ صامتٌ لا استثناءَ له
        registerPlugin(OnlinePlugin.class);
        registerPlugin(OfferAlertPlugin.class);
        super.onCreate(savedInstanceState);
    }

    /**
     * <b>ختمُ آخر ظهورٍ لشاشتنا</b> — وبه يفرّق {@link OfferAlert} بين «في
     * تطبيقٍ آخر» (ورقةٌ سفليّة، الشاشة ٠٢) و«خارج التطبيق تماماً» (فقاعة،
     * الشاشة ٠٤).
     *
     * <p><b>وهي إشارةٌ لا يقين</b>: أندرويد لا يقول أيُّ تطبيقٍ في المقدّمة
     * بلا {@code PACKAGE_USAGE_STATS}، <b>وقربُ العهد أقربُ ما يُتاح</b> إلى
     * ما رسمه التصميم — وحدُّها مكتوبٌ في {@link OfferAlert} وفي ملفّ التصميم.
     */
    @Override
    public void onPause() {
        super.onPause();
        OfferAlert.markLeftApp(this);
    }

    /**
     * <b>وعودتُه إلى الشاشة تطوي ما فوقها</b>: من فتح التطبيق يرى البطاقةَ
     * داخله (الشاشة ٠١)، <b>وورقةٌ أو فقاعةٌ باقيةٌ فوقها تُقرأ طلباً ثانياً</b>
     * — وهو نصُّ «أوّلُ طريقةٍ متاحةٍ تُستعمل والبقيّةُ تُلغى».
     */
    @Override
    public void onResume() {
        super.onResume();
        OfferAlert.hide(this);
    }
}
