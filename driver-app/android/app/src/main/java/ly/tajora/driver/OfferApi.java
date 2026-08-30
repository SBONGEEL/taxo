package ly.tajora.driver;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * قبولُ الطلب ورفضُه <b>من الأصليِّ مباشرةً</b> — قرارُ المالك 2026-08-30:
 * «نعم: يقبل ثم يفتح».
 *
 * <p><b>ولمَ لا يُفتح التطبيقُ أوّلاً ثم يُقبل</b>: مهلةُ القبول سبعُ ثوانٍ،
 * <b>وإقلاعُ WebView وتحميلُ الشاشات من الشبكة يلتهمها</b> — والشاشةُ مقفلةٌ
 * والتطبيقُ قد يكون مقتولاً. فمن ينتظر التطبيقَ ليقبل <b>يخسر الطلبَ الذي
 * ضغط قبولَه</b>.
 *
 * <p><b>ورمزُ الوصول لا رمزُ الحضور</b>: {@link OnlineService} تحمل رمزَ
 * حضورٍ بترويسةٍ مستقلّة (§23.4) <b>لا يُقرأ جلسةً أصلاً</b>، فلا يصلح لقبول
 * رحلة. فيُحفظ رمزُ الوصول في تفضيلاتٍ خاصّةٍ بالتطبيق — <b>وهو ما تفعله
 * الـWebView نفسُها بـ`localStorage`</b>، فلا حمايةَ نقصت.
 *
 * <p><b>ولا رمزَ تجديدٍ هنا أبداً</b>: مُدوَّرٌ ذو استعمالٍ واحد (§23)،
 * وحاملان له يُخرجان صاحبَه من حسابه.
 *
 * <p><b>وإن سقط النداءُ لأيِّ سبب — رمزٌ منتهٍ، أو شبكةٌ ساقطة — يُفتح
 * التطبيقُ على البطاقة نفسِها</b> (<code>?offer=</code>)، فلا يبقى الكبتنُ
 * أمام زرٍّ ضغطه ولم يحدث شيء. <b>وهذا هو الفرقُ بين تسليمٍ يفشل بصمتٍ
 * وتسليمٍ يعرف طريقَه الثاني.</b>
 */
public final class OfferApi {

    private static final String PREFS = "taxo.offer.session";
    private static final ExecutorService NET = Executors.newSingleThreadExecutor();

    private OfferApi() {}

    /** يحفظ ما تحتاجه هذه الأسطحُ للنداء — ويُمحى بالخروج. */
    public static void remember(Context context, String apiBase, String accessToken) {
        SharedPreferences prefs =
                context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        if (apiBase == null || accessToken == null) {
            prefs.edit().clear().apply();
            return;
        }
        prefs.edit().putString("base", apiBase).putString("token", accessToken).apply();
    }

    private static String base(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString("base", null);
    }

    private static String token(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString("token", null);
    }

    public interface Done {
        void onDone(boolean accepted);
    }

    /** <b>يقبل ثم يفتح</b> — والفتحُ يقع في الحالين، والقبولُ قد يسبقه. */
    public static void accept(Context context, String rideId, Done done) {
        call(context, "/rides/" + rideId + "/accept", ok -> {
            openApp(context, rideId);
            done.onDone(ok);
        });
    }

    /** <b>والرفضُ لا يفتح شيئاً</b> — «الرفض يعيدك إلى ما كنت فيه فوراً». */
    public static void decline(Context context, String rideId, Done done) {
        call(context, "/rides/" + rideId + "/decline", done::onDone);
    }

    private static void call(Context context, String path, Done done) {
        final String url = base(context);
        final String bearer = token(context);
        if (url == null || bearer == null) {
            done.onDone(false);
            return;
        }
        NET.execute(() -> {
            HttpURLConnection connection = null;
            boolean ok = false;
            try {
                connection = (HttpURLConnection) new URL(url + path).openConnection();
                connection.setRequestMethod("POST");
                connection.setConnectTimeout(8_000);
                connection.setReadTimeout(8_000);
                connection.setRequestProperty("Content-Type", "application/json");
                connection.setRequestProperty("Authorization", "Bearer " + bearer);
                connection.setDoOutput(true);
                try (OutputStream out = connection.getOutputStream()) {
                    out.write("{}".getBytes("UTF-8"));
                }
                int code = connection.getResponseCode();
                ok = code >= 200 && code < 300;
            } catch (Exception ignored) {
                // شبكةٌ ساقطة — والفتحُ هو الطريقُ الثاني
            } finally {
                if (connection != null) connection.disconnect();
            }
            final boolean result = ok;
            new android.os.Handler(android.os.Looper.getMainLooper())
                    .post(() -> done.onDone(result));
        });
    }

    /**
     * يفتح التطبيقَ على البطاقة نفسِها.
     *
     * <p><b>و`?offer=` مسارٌ قائمٌ منذ قبل اليوم</b> (`Home.tsx` يقرأه)، فمن
     * فتح عليه يرى العرضَ المعلَّق حين يصل أولُ اتصال — <b>ولا يُبنى له بابٌ
     * ثانٍ</b>.
     */
    public static void openApp(Context context, String rideId) {
        Intent intent = new Intent(context, MainActivity.class);
        intent.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        intent.setData(Uri.parse("taxo://offer/" + rideId));
        intent.putExtra("ride_id", rideId);
        context.startActivity(intent);
    }
}
