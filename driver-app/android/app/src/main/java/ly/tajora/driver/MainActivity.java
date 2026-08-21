package ly.tajora.driver;

import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        // **التسجيلُ قبل `super`**: الجسرُ يُبنى داخل `super.onCreate`، وما
        // يُسجَّل بعده لا يجده الويبُ حين ينادي — عطبٌ صامتٌ لا استثناءَ له
        registerPlugin(OnlinePlugin.class);
        super.onCreate(savedInstanceState);
    }
}
