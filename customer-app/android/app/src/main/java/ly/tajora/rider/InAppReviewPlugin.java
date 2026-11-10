package ly.tajora.rider;

import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.google.android.play.core.review.ReviewInfo;
import com.google.android.play.core.review.ReviewManager;
import com.google.android.play.core.review.ReviewManagerFactory;

/**
 * <b>تقييمُ المتجر داخل التطبيق</b> (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٦، SPEC §٩٧/٦) — Play In-App Review.
 *
 * <p>يفتح نافذةَ التقييم الأصليّة من Google Play فوق التطبيق. <b>والمتجرُ وحدَه يقرّر أيُظهرها</b> (حصّةٌ لكلِّ مستخدم)،
 * <b>ولا يقول أظهرها أم لا ولا ما اختير</b> — فالوعدُ يُحلّ في الحالين. والتوقيتُ والتكرارُ في الصفحة ({@code lib/in-app-review.ts}).
 */
@CapacitorPlugin(name = "InAppReview")
public class InAppReviewPlugin extends Plugin {

    @PluginMethod
    public void request(PluginCall call) {
        if (getActivity() == null) {
            call.reject("لا نشاطَ ظاهر");
            return;
        }
        ReviewManager manager = ReviewManagerFactory.create(getContext());
        manager.requestReviewFlow().addOnCompleteListener(task -> {
            if (!task.isSuccessful()) {
                call.reject("خدمةُ المتجر لم تُجب");
                return;
            }
            ReviewInfo info = task.getResult();
            manager.launchReviewFlow(getActivity(), info).addOnCompleteListener(done -> call.resolve());
        });
    }
}
