package ly.tajora.rider;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * <b>تقييمُ المتجر في نسخة Huawei</b> — لا نافذةَ Play هنا. <b>يُرفض كما يُرفض حين لا تجيب خدمةُ المتجر</b>، والصفحةُ تعرف هذا الرفضَ
 * ({@code lib/in-app-review.ts}) فلا يتغيّر فيها شيء.
 */
@CapacitorPlugin(name = "InAppReview")
public class InAppReviewPlugin extends Plugin {

    @PluginMethod
    public void request(PluginCall call) {
        call.reject("خدمةُ المتجر لم تُجب");
    }
}
