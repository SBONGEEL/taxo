package ly.tajora.rider;

import com.android.installreferrer.api.InstallReferrerClient;
import com.android.installreferrer.api.InstallReferrerStateListener;
import com.android.installreferrer.api.ReferrerDetails;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * <b>مُحيلُ التثبيت من Google Play</b> — رمزُ الدعوة لمن ثبّت التطبيقَ من رابط صديق (أمرُ المالك ٢٠٢٦-١١-٠٨).
 *
 * <p>رابطُ الدعوة {@code https://taxo.tajora.ly/i/<الرمز>} يحوّل من لا يملك التطبيقَ إلى صفحة المتجر بـ
 * {@code referrer=taxo_ref=<الرمز>}، <b>والمتجرُ يحفظه ويعيده هنا في أوّل فتح</b>. والقراءةُ والحكمُ في الصفحة
 * ({@code lib/invite.ts})؛ وهذا يعيد النصَّ كما سلّمه المتجر، <b>ولا يقرأ شيئاً غيرَه</b>.
 */
@CapacitorPlugin(name = "InstallReferrer")
public class InstallReferrerPlugin extends Plugin {

    @PluginMethod
    public void get(PluginCall call) {
        InstallReferrerClient client = InstallReferrerClient.newBuilder(getContext()).build();
        client.startConnection(new InstallReferrerStateListener() {
            private boolean done = false;

            @Override
            public void onInstallReferrerSetupFinished(int code) {
                if (done) return;
                done = true;
                try {
                    if (code == InstallReferrerClient.InstallReferrerResponse.OK) {
                        ReferrerDetails details = client.getInstallReferrer();
                        JSObject result = new JSObject();
                        String referrer = details.getInstallReferrer();
                        result.put("referrer", referrer == null ? "" : referrer);
                        call.resolve(result);
                    } else if (code == InstallReferrerClient.InstallReferrerResponse.FEATURE_NOT_SUPPORTED) {
                        // تثبيتٌ من غير المتجر — لا مُحيلَ أبداً، فالجوابُ فارغٌ لا خطأ
                        JSObject result = new JSObject();
                        result.put("referrer", "");
                        call.resolve(result);
                    } else {
                        call.reject("خدمةُ المتجر لم تُجب");
                    }
                } catch (Exception error) {
                    call.reject("تعذّرت قراءةُ مُحيل التثبيت");
                } finally {
                    client.endConnection();
                }
            }

            @Override
            public void onInstallReferrerServiceDisconnected() {
                if (done) return;
                done = true;
                call.reject("انقطع الاتصالُ بخدمة المتجر");
            }
        });
    }
}
