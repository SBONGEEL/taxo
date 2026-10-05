package ly.tajora.rider;

import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        // **القنواتُ قبل أوّل إشعار** (§٦١-ل/٣): ما يصل والتطبيقُ مغلقٌ يرسمه النظامُ
        // بقناته، **وقناةٌ لم تُنشأ تُسقطه إلى الاحتياطية بلا صوتها**
        TaxoChannels.ensure(this);
        super.onCreate(savedInstanceState);
    }
}
