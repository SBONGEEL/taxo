package ly.tajora.driver;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * <b>ملءُ رمز التحقّق في نسخة Huawei</b> — «SMS User Consent» من خدمات Google وحدَها. <b>يُحلّ بلا رمزٍ</b> كما يُحلّ هناك حين لا تصل
 * رسالة، فيكتب صاحبُ الهاتف الرمزَ بيده كما في المتصفّح.
 */
@CapacitorPlugin(name = "SmsConsent")
public class SmsConsentPlugin extends Plugin {

    @PluginMethod(returnType = PluginMethod.RETURN_PROMISE)
    public void listen(PluginCall call) {
        JSObject out = new JSObject();
        out.put("code", (String) null);
        call.resolve(out);
    }

    @PluginMethod
    public void stop(PluginCall call) {
        call.resolve();
    }
}
