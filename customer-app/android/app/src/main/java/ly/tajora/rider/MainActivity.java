package ly.tajora.rider;

import android.os.Bundle;

import androidx.core.content.ContextCompat;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
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
}
