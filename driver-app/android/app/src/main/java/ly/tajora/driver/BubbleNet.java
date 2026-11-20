package ly.tajora.driver;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Handler;
import android.os.Looper;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * <b>نداءاتُ الفقاعة الخفيفة</b> (أمرُ المالك ٢٠/١١ الرابع، SPEC §١١٠) — <b>برمز الوصول الذي يحفظه {@link OfferApi}</b> لا برمزٍ ثانٍ،
 * إلى <b>أبوابٍ قائمة</b> وحدَها: الاستراحة، أقربُ منطقة، بلاغُ الطريق، الردُّ السريع في المحادثة، «وصلت»، الطوارئ، وأرقامُ اليوم
 * والاشتراك. <b>ولا مبلغَ يُحسب هنا ولا يُرسل</b>: ما يُقرأ يُعرض كما جاء.
 *
 * <p>خيطٌ واحدٌ للشبكة، ومهلةُ ثماني ثوانٍ، والجوابُ يعود إلى الخيط الرئيس. <b>رمزٌ منتهٍ أو شبكةٌ ساقطة = {@code code=0} أو ٤٠١</b>،
 * ومن ينادي يفتح التطبيقَ طريقاً ثانياً — كما في قبول العرض.
 */
public final class BubbleNet {

    private static final String SESSION = "taxo.offer.session";
    private static final ExecutorService NET = Executors.newSingleThreadExecutor();

    public interface Done {
        void onDone(int code, JSONObject body);
    }

    private BubbleNet() {}

    static boolean ready(Context c) {
        SharedPreferences s = c.getSharedPreferences(SESSION, Context.MODE_PRIVATE);
        return s.getString("base", null) != null && s.getString("token", null) != null;
    }

    public static void get(Context c, String path, Done done) {
        call(c, "GET", path, null, done);
    }

    public static void post(Context c, String path, JSONObject body, Done done) {
        call(c, "POST", path, body == null ? new JSONObject() : body, done);
    }

    public static void delete(Context c, String path, Done done) {
        call(c, "DELETE", path, null, done);
    }

    private static void call(Context context, String method, String path, JSONObject body, Done done) {
        SharedPreferences s = context.getApplicationContext().getSharedPreferences(SESSION, Context.MODE_PRIVATE);
        final String base = s.getString("base", null);
        final String token = s.getString("token", null);
        Handler main = new Handler(Looper.getMainLooper());
        if (base == null || token == null) {
            main.post(() -> done.onDone(0, null));
            return;
        }
        NET.execute(() -> {
            HttpURLConnection connection = null;
            int code = 0;
            JSONObject parsed = null;
            try {
                connection = (HttpURLConnection) new URL(base + path).openConnection();
                connection.setRequestMethod(method);
                connection.setConnectTimeout(8_000);
                connection.setReadTimeout(8_000);
                connection.setRequestProperty("Authorization", "Bearer " + token);
                connection.setRequestProperty("Accept", "application/json");
                if (body != null) {
                    connection.setRequestProperty("Content-Type", "application/json");
                    connection.setDoOutput(true);
                    try (OutputStream out = connection.getOutputStream()) {
                        out.write(body.toString().getBytes(StandardCharsets.UTF_8));
                    }
                }
                code = connection.getResponseCode();
                InputStream in = code < 400 ? connection.getInputStream() : connection.getErrorStream();
                if (in != null) {
                    ByteArrayOutputStream buffer = new ByteArrayOutputStream();
                    byte[] chunk = new byte[4096];
                    int n;
                    while ((n = in.read(chunk)) > 0) buffer.write(chunk, 0, n);
                    in.close();
                    String text = buffer.toString("UTF-8").trim();
                    if (text.startsWith("{")) parsed = new JSONObject(text);
                }
            } catch (Exception ignored) {
                // شبكةٌ ساقطة — code يبقى 0
            } finally {
                if (connection != null) connection.disconnect();
            }
            final int result = code;
            final JSONObject answer = parsed;
            main.post(() -> done.onDone(result, answer));
        });
    }
}
