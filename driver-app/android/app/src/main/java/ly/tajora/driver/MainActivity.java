package ly.tajora.driver;

import android.os.Bundle;

import androidx.core.content.ContextCompat;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        // **التسجيلُ قبل `super`**: الجسرُ يُبنى داخل `super.onCreate`، وما
        // يُسجَّل بعده لا يجده الويبُ حين ينادي — عطبٌ صامتٌ لا استثناءَ له
        registerPlugin(OnlinePlugin.class);
        registerPlugin(OfferAlertPlugin.class);
        // **القنواتُ قبل أوّل إشعار** (§٦١-ل/٣): ما يصل والتطبيقُ مغلقٌ يرسمه النظامُ
        // بقناته، **وقناةٌ لم تُنشأ تُسقطه إلى الاحتياطية بلا صوتها**
        TaxoChannels.ensure(this);
        super.onCreate(savedInstanceState);
        // **لا سوادَ بين نافذة الإقلاع وأوّل رسمٍ للصفحة** (بلاغُ المالك ٢٠٢٦-١٠-٠٦، قِيس على S21):
        // نافذةُ الإقلاع تزول عند أوّل إطارٍ للنشاط، **والويبُ لم يرسم بعد** — فكان يُرى سوادُه الافتراضيّ
        // في الوضع الليليّ (أبيضُه في النهاريّ) **٠٫٨–١٫٣ ثانيةً** بين لون الإقلاع وأوّل رسمٍ لـ`index.html`.
        // **فخلفيّتُه لونُ الإقلاع نفسُه** (`launch_background`، ويتبع وضعَ النظام كما تتبعه النافذة)، **وإطارُ
        // الإقلاع في الصفحة على اللون نفسِه** — فلا يُرى انتقالٌ حتى تبدأ الحركة.
        // ولا خطّافَ في Capacitor 7 لـ«أوّل رسم» يُبقي النافذةَ إلى حينه، **فاللونُ هو ما يُملك هنا**
        getBridge().getWebView().setBackgroundColor(ContextCompat.getColor(this, R.color.launch_background));
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
