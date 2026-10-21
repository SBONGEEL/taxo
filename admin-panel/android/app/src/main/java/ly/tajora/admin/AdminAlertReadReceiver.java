package ly.tajora.admin;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import androidx.core.app.NotificationManagerCompat;

import org.json.JSONObject;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * <b>«مقروء» على إشعار المالك</b> (SPEC §٨١/٧) — يطوي الإشعارَ ويُرسل إيصالَ القراءة إلى {@code POST /alerts/{id}/read-by-receipt}.
 *
 * <p><b>بلا جلسة</b>: الجلسةُ في صفحة الويب لا هنا، <b>والإذنُ في الرمز نفسِه</b> — يخصّ هذا المستلمَ وهذا الصفَّ ولا يفعل غيرَ ذلك
 * ({@code services/admin_alerts.read_receipt}). <b>وعنوانُ الخادم من البناء لا من الإشعار</b>: سلّمته اللوحةُ للملحق
 * ({@link AdminAlertsPlugin#configure}) — فإشعارٌ مزوَّرٌ لا يوجّه الهاتفَ إلى غير خادمه.
 */
public class AdminAlertReadReceiver extends BroadcastReceiver {

    @Override
    public void onReceive(Context context, Intent intent) {
        String tag = intent.getStringExtra(AdminAlertNotifier.EXTRA_TAG);
        int id = intent.getIntExtra(AdminAlertNotifier.EXTRA_NOTIFICATION_ID, 0);
        NotificationManagerCompat.from(context).cancel(tag, id);

        String apiBase = AdminAlertsPlugin.apiBase(context);
        String alertId = intent.getStringExtra(AdminAlertNotifier.EXTRA_ALERT_ID);
        String userId = intent.getStringExtra(AdminAlertNotifier.EXTRA_USER_ID);
        String receipt = intent.getStringExtra(AdminAlertNotifier.EXTRA_READ_RECEIPT);
        if (apiBase == null || alertId == null || alertId.isEmpty() || receipt == null || receipt.isEmpty()) return;

        final PendingResult pending = goAsync();
        new Thread(() -> {
            HttpURLConnection connection = null;
            try {
                JSONObject body = new JSONObject();
                body.put("user_id", userId);
                body.put("receipt", receipt);
                URL url = new URL(apiBase + "/alerts/" + alertId + "/read-by-receipt");
                connection = (HttpURLConnection) url.openConnection();
                connection.setRequestMethod("POST");
                connection.setConnectTimeout(8_000);
                connection.setReadTimeout(8_000);
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", "application/json");
                try (OutputStream out = connection.getOutputStream()) {
                    out.write(body.toString().getBytes(StandardCharsets.UTF_8));
                }
                connection.getResponseCode();
            } catch (Exception ignored) {
                // **«مقروء» لم يصل** — الصفُّ يبقى غيرَ مقروءٍ في الجرس، ويُقرأ هناك. لا يُسقط ذلك شيئاً
            } finally {
                if (connection != null) connection.disconnect();
                pending.finish();
            }
        }).start();
    }
}
