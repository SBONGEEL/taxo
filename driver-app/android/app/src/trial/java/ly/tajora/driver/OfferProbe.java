package ly.tajora.driver;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/**
 * مسبارُ بطاقةِ الطلب — <b>في النكهة التجريبيّة وحدَها، ومعزولٌ بالبناء لا بالنيّة</b>.
 *
 * <p><b>ولمَ وُجد</b>: شرطُ المالك أن يُقاس على الجهاز «بالإذن تظهر الفقاعة
 * والتطبيق مغلق · وبلا الإذن يظهر الإشعار ملء الشاشة · ولا تظهر الاثنتان معاً».
 * <b>وذلك لا يقع إلا بطلبٍ حقيقيّ</b> — ورحلةٌ حقيقيّةٌ في كلِّ قياسٍ تعني
 * راكباً وكبتناً وشبكةً في كلِّ مرّة، <b>ويبقى ما يُقاس مختلطاً بثلاثةِ أشياء</b>.
 *
 * <p><b>وعزلُه بالبناء لا بشرطٍ في الشيفرة</b> (قرارُ المالك 2026-08-29 في
 * تشخيصٍ سابق): موضعُه {@code src/trial} — <b>فحزمةُ القناة العامّة لا تحتوي
 * هذا الملفَّ أصلاً</b>، ولا يوجد شرطٌ يُنسى إطفاؤه. <b>وشرطٌ يُقرأ في زمن
 * التشغيل كان سيبقى في الحزمة</b> ويُفتح بمن يعرف اسمَه.
 *
 * <p><b>ويُنزع بعد أن يُقرأ السبب</b> — وهو أمرُ المالك في التشخيص السابق نفسِه.
 */
public class OfferProbe extends BroadcastReceiver {

    public static final String ACTION = "ly.tajora.driver.test.SHOW_OFFER";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (!ACTION.equals(intent.getAction())) return;
        String mode = intent.getStringExtra("mode");
        if ("hide".equals(mode)) {
            OfferAlert.hide(context);
            return;
        }
        // **«بيب بيب» (§١١٥)**: الطلبُ كما يصل من FCM بياناتٍ وحدَها — **من خيطٍ عاملٍ كخيط FCM**، فيُمسك عرضٌ لا يعود إلى الخيط الرئيسيّ
        if ("push".equals(mode)) {
            java.util.Map<String, String> m = new java.util.HashMap<>();
            m.put("type", "ride_offer");
            m.put("ride_id", intent.getStringExtra("ride_id") == null ? "probe-push" : intent.getStringExtra("ride_id"));
            m.put("expires_in_seconds", String.valueOf(intent.getIntExtra("timeout", 12)));
            m.put("amount", "2.750");
            m.put("currency", "JOD");
            m.put("distance_to_pickup_km", "1.2");
            m.put("category", "economy");
            m.put("pickup", "الدوار السابع، عمّان");
            m.put("drop", "مجمّع رغدان، وسط البلد");
            Context app = context.getApplicationContext();
            new Thread(() -> OfferAlert.showFromPush(app, m, System.currentTimeMillis())).start();
            return;
        }
        if ("silent_ring".equals(mode)) {
            OfferAlert.setSilentRing(context, intent.getBooleanExtra("on", true));
            return;
        }
        if ("playing".equals(mode)) {
            android.util.Log.i(OfferTone.TAG, "probe playing=" + OfferTone.isPlaying());
            return;
        }
        // **حالُ «متّصل» من داخل العمليّة** — `force-stop` لكتابة الملفّ يضع الحزمةَ في «موقوفة» فلا يبلغها البثُّ أصلاً (قِيس في CI)
        if ("online".equals(mode)) {
            context.getSharedPreferences(LauncherPlugin.PREFS, Context.MODE_PRIVATE).edit()
                    .putBoolean("online", intent.getBooleanExtra("on", true)).commit();
            android.util.Log.i(OfferTone.TAG, "probe online=" + intent.getBooleanExtra("on", true));
            return;
        }
        // **وضعُ الرنين من داخل التطبيق** — `cmd audio set-ringer-mode` لا يغيّره على المحاكي (قِيس: «الصامت» نجح لأن المنبّه يرنّ في كلِّ وضع).
        // «اهتزاز» لا «صامت»: لا يحتاج إذنَ «عدم الإزعاج»، و`quietPhone` يعدّ كلَّ ما ليس «عاديّاً» هادئاً
        if ("ringer".equals(mode)) {
            android.media.AudioManager audio = context.getSystemService(android.media.AudioManager.class);
            try {
                audio.setRingerMode("vibrate".equals(intent.getStringExtra("to"))
                        ? android.media.AudioManager.RINGER_MODE_VIBRATE : android.media.AudioManager.RINGER_MODE_NORMAL);
            } catch (Exception refused) {
                android.util.Log.w(OfferTone.TAG, "probe ringer refused " + refused.getClass().getSimpleName());
            }
            android.util.Log.i(OfferTone.TAG, "probe ringer=" + audio.getRingerMode());
            return;
        }
        // **وإجبارُ السطح للقياس وحدَه** (`--es force sheet|bubble|full`):
        // الفرقُ بين «ورقة» و«فقاعة» يقوم على قربِ العهد بالتطبيق، **وانتظارُ
        // دقيقتين بين كلِّ قياسٍ وآخرَ يجعل القياسَ لا يقع** — والإجبارُ في
        // `src/trial` وحدَه، **فحزمةُ القناة العامّة لا تحمل هذا الملفَّ أصلاً**.
        String force = intent.getStringExtra("force");

        // **قيمُ التصميم نفسُها** — فما يُقاس هو ما رُسم: أجرةُ ٢٫٧٥ و«١٫٢ كم»
        // و«الدوار السابع، عمّان» ← «مجمّع رغدان، وسط البلد»
        OfferData data = new OfferData(
                intent.getStringExtra("ride_id") == null
                        ? "probe-ride" : intent.getStringExtra("ride_id"),
                intent.getStringExtra("fare") == null
                        ? "٢٫٧٥" : intent.getStringExtra("fare"),
                "د.أ",
                intent.getStringExtra("method") == null
                        ? "" : intent.getStringExtra("method"),
                "اقتصادي",
                "١٫٢ كم",
                "الدوار السابع، عمّان",
                "مجمّع رغدان، وسط البلد",
                intent.getIntExtra("timeout", 7)
        );
        if ("sheet".equals(force)) {
            OfferSheetWindow.show(context, data);
        } else if ("bubble".equals(force)) {
            OfferBubble.show(context, data);
        } else if ("full".equals(force) || "locked".equals(force)) {
            OfferAlert.ensureChannel(context);
            android.content.Intent screen =
                    new android.content.Intent(context, OfferActivity.class);
            screen.setFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK
                    | android.content.Intent.FLAG_ACTIVITY_CLEAR_TOP);
            screen.putExtras(data.toBundle());
            screen.putExtra(OfferActivity.EXTRA_LOCKED, "locked".equals(force));
            context.startActivity(screen);
        } else {
            OfferAlert.show(context, data);
        }
    }
}
