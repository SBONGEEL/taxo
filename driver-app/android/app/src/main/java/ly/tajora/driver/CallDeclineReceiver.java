package ly.tajora.driver;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/**
 * <b>«رفض» على إشعار الرنين</b> (§٦٦-ج/١٧) — <b>يطويه على هذا الجهاز وحدَه</b>، ولا يفتح التطبيق.
 *
 * <p><b>ولمَ لا يُبلَّغ الخادم</b>: لا رمزَ دخولٍ في الشيفرة الأصليّة — الرمزُ يعيش في الويب، <b>ونسخةٌ منه هنا بابٌ
 * ثانٍ للجلسة</b> يفلت من إبطالها. فالمكالمةُ عند الخادم ترنّ حتى ثلاثينها ثمّ تُكتب فائتةً (ويصل المتصلَ «لم يُجب»)،
 * <b>وهو ما يقع اليومَ لمن تجاهل الإشعار</b>. ورفضٌ يصل الخادمَ يحتاج ذلك البابَ أو فتحَ التطبيق — بندٌ مستقلّ.
 *
 * <p><b>ومستقبِلٌ لا نشاط</b>: أندرويد ١٢ فما فوق يمنع نشاطاً يُطلَق من مستقبِلٍ أطلقه إشعار، وهذا لا يُطلق شيئاً.
 */
public class CallDeclineReceiver extends BroadcastReceiver {

    @Override
    public void onReceive(Context context, Intent intent) {
        CallAlert.cancel(context, intent.getStringExtra(CallAlert.EXTRA_CALL_ID));
    }
}
