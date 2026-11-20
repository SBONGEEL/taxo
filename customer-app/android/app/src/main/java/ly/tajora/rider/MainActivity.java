package ly.tajora.rider;

import android.os.Bundle;

import androidx.activity.EdgeToEdge;

import androidx.core.content.ContextCompat;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        // **القنواتُ قبل أوّل إشعار** (§٦١-ل/٣): ما يصل والتطبيقُ مغلقٌ يرسمه النظامُ
        // بقناته، **وقناةٌ لم تُنشأ تُسقطه إلى الاحتياطية بلا صوتها**
        TaxoChannels.ensure(this);
        // **رمزُ الجلسة على القرص قبل «حُفظ»** (§٢٣.٢-أ) — قبل `super` كما تقتضي Capacitor
        registerPlugin(SecureFlushPlugin.class);
        // **تقييمُ المتجر داخل التطبيق** (البند ٦) — النافذةُ الأصليّة من Google Play
        registerPlugin(InAppReviewPlugin.class);
        // **منعُ اللقطات في المحفظة** (SPEC §١٠٣ B/26)
        registerPlugin(ScreenSecurePlugin.class);
        // **ملءُ رمز التحقّق من الرسالة** (SPEC §١٠٣ B/23)
        registerPlugin(SmsConsentPlugin.class);
        // **النصُّ الكبير** (SPEC §١٠٣ C/40)
        registerPlugin(TextZoomPlugin.class);
        // **مكالمةُ الرحلة يعرفها النظام** (SPEC §١٠٣ B/27) — البلوتوثُ والسيّارةُ وأزرارُ السمّاعة
        registerPlugin(CallBridgePlugin.class);
        // **تعطّلُ أندرويد الأصليّ يصل اللوحة** (SPEC §١٠٣ C/41) — الماسكُ أوّلاً، ثمّ الملحقُ الذي يسلّمه للويب
        NativeCrashPlugin.install(this);
        registerPlugin(NativeCrashPlugin.class);
        // **إشعارُ التتبّع الحيّ** (SPEC §١٠٣ B/19)
        registerPlugin(RideLivePlugin.class);
        // **زرُّ الصوت ثلاثاً للطوارئ** (SPEC §١٠٣ B/22) — يشعله الراكبُ بنفسه
        registerPlugin(VolumeTriggerPlugin.class);
        // **«يوجد تحديث» من Google Play** (SPEC §١٠٣ A/8) — الحكمُ من لوحة الإصدارات، والتنفيذُ من Play إن قدر
        registerPlugin(AppUpdatePlugin.class);
        // **مركزُ الأذونات** (SPEC §١٠٣ المرحلة A/28) — الحالُ الحيّ وصفحةُ النظام الدقيقة لكلِّ إذن
        registerPlugin(PermissionsPlugin.class);
        // **المُطلِق** (SPEC §١٠٣ المرحلة A/4–6، 10) — الاختصاراتُ والبلاطةُ والأداةُ تحمل فعلاً ينفّذه الويب
        registerPlugin(LauncherPlugin.class);
        // **الطلبُ بالصوت** (البند ١٠) — نافذةُ التعرّف في الهاتف، بلا إذن ميكروفون
        registerPlugin(SpeechInputPlugin.class);
        // **مُحيلُ التثبيت** — رمزُ الدعوة لمن ثبّت من رابط صديق (`lib/invite.ts`)
        registerPlugin(InstallReferrerPlugin.class);
        // **فقاعةُ الراكب** (أمرُ المالك ٢٠/١١ الرابع، SPEC §١١٠) — جلسةُ نداءَيها الخفيفين
        registerPlugin(RiderBubblePlugin.class);
        super.onCreate(savedInstanceState);
        // **العرضُ حتى الحافّة على كلِّ إصدار** (ملاحظةُ Google على 960، CODE-HEALTH ٤-٢): أندرويد ١٥+ يفرضه أصلاً بهدف SDK 35+،
        // **فيُفعَّل لما دونه أيضاً** فيرى الجميعُ الشكلَ نفسَه — والصفحةُ تحسب حواشيها بـ`env(safe-area-inset-*)`.
        // **وبعد `super` لا قبله** (قِيس على المحاكي ٢٠٢٦-١٠-٢٩): قبله يُنشئ النافذةَ بسمة الإقلاع قبل أن يضبط الجسرُ
        // سمةَ «بلا شريط»، **فيظهر شريطُ إجراءاتٍ باسم التطبيق فوق الصفحة**
        EdgeToEdge.enable(this);
        // **لا سوادَ بين نافذة الإقلاع وأوّل رسمٍ للصفحة** (بلاغُ المالك ٢٠٢٦-١٠-٠٦، قِيس على S21):
        // نافذةُ الإقلاع تزول عند أوّل إطارٍ للنشاط، **والويبُ لم يرسم بعد** — فكان يُرى سوادُه الافتراضيّ
        // في الوضع الليليّ (أبيضُه في النهاريّ) **٠٫٨–١٫٣ ثانيةً** بين لون الإقلاع وأوّل رسمٍ لـ`index.html`.
        // **فخلفيّتُه لونُ الإقلاع نفسُه** (`launch_background`، ويتبع وضعَ النظام كما تتبعه النافذة)، **وإطارُ
        // الإقلاع في الصفحة على اللون نفسِه** — فلا يُرى انتقالٌ حتى تبدأ الحركة.
        // ولا خطّافَ في Capacitor 7 لـ«أوّل رسم» يُبقي النافذةَ إلى حينه، **فاللونُ هو ما يُملك هنا**
        getBridge().getWebView().setBackgroundColor(ContextCompat.getColor(this, R.color.launch_background));
    }

    /**
     * <b>ظهر التطبيقُ فالشاشةُ ترنّ بعد الآن</b> (§٦٦-ج/١٧): رنينُ المكالمة الأصليُّ ({@link CallAlert}) يُطوى،
     * فرنينان لمكالمةٍ واحدةٍ لا يُسمعان — <b>إلا خلف القفل</b>: ملءُ الشاشة قد يُطلق هذا النشاطَ والهاتفُ مقفل،
     * ورنينٌ يسكت قبل أن يُرى لا رنين.
     */
    @Override
    public void onResume() {
        super.onResume();
        CallAlert.onAppShown(this);
        // **الفقاعةُ تختفي والتطبيقُ مفتوح** (البند ٥٥ للراكب)
        RiderBubble.onAppShown(this);
    }

    /** <b>غاب التطبيق</b> — فمكالمةٌ ترنّ بعدها يرسمها {@link CallAlert}. */
    @Override
    public void onPause() {
        super.onPause();
        CallAlert.onAppHidden();
        // **وتظهر حين يخرج — أثناء البحث والرحلة وحدَهما، وباختياره**
        RiderBubble.onAppHidden(this);
    }

    /**
     * <b>وفتحُ القفل والتطبيقُ أمامه يطوي الرنينَ أيضاً</b> ({@link CallAlert#onAppFocused}): {@code onResume} قد يقع والقفلُ
     * لم يزل بعد فيتخطّى الطيّ، <b>ولا يتكرّر حين يزول</b> — والتركيزُ لا يُنال إلا بعده.
     */
    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) CallAlert.onAppFocused(this);
    }

    /** **يُعدّ ولا يُؤكل** (§١٠٣ B/22) — `VolumeTriggerPlugin` يرى المفتاحَ، والصوتُ يتغيّر كما اعتاد صاحبُه. */
    @Override
    public boolean dispatchKeyEvent(android.view.KeyEvent event) {
        VolumeTriggerPlugin.onKey(event);
        return super.dispatchKeyEvent(event);
    }
}
