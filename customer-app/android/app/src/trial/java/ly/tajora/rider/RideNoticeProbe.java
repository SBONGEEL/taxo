package ly.tajora.rider;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import java.util.HashMap;
import java.util.Map;

/**
 * <b>مسبارُ الإشعار الغنيّ</b> (SPEC §١٠٣ A/12) — في {@code src/trial} وحدَه. يرسم ما ترسمه {@link RideNotice} حين يصل
 * إشعارُ «قُبلت» من الخادم، <b>ببياناتٍ ثابتةٍ وصورةٍ من رابطٍ يمرّره المحاكي</b> ({@code --es photo_url}) — فما يُصوَّر هو الرسمُ
 * نفسُه لا نسخةٌ منه.
 */
public class RideNoticeProbe extends BroadcastReceiver {

    public static final String ACTION = "ly.tajora.rider.test.SHOW_RIDE_NOTICE";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (!ACTION.equals(intent.getAction())) return;
        Map<String, String> data = new HashMap<>();
        data.put("type", "driver_assigned");
        data.put("rich", "1");
        data.put("ride_id", "00000000-0000-4000-8000-000000000012");
        data.put("title", "تم قبول رحلتك");
        data.put("body", "الكبتن في طريقه إلى نقطة الانطلاق");
        data.put("driver_name", "أحمد");
        data.put("plate", "12-34567");
        data.put("vehicle", "تويوتا كامري أبيض");
        data.put("channel", "taxo.accepted.s2_5");
        String photo = intent.getStringExtra("photo_url");
        if (photo != null) data.put("photo_url", photo);
        PendingResult pending = goAsync();
        new Thread(() -> {
            try {
                RideNotice.show(context, data);
            } finally {
                pending.finish();
            }
        }).start();
    }
}
