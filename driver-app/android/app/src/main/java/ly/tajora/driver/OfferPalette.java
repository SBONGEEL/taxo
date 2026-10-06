package ly.tajora.driver;

import android.content.Context;
import android.content.res.Configuration;
import android.graphics.Color;

/**
 * ألوانُ TAXO 2.0 حرفاً — <b>رموزُ الهوية بأدوارها</b> (`driver-app/src/taxo2/tokens.css`، §٦٢-ج/٤٤): كانت ألوانَ اللغة السابقة
 * (`mobile-app-design-request`) فتظهر ورقةُ الطلب وفقاعتُه وشاشتُه الكاملة بهويةٍ غيرِ هوية التطبيق. **والأدوارُ هي هي**
 * (ما يقرؤه `OfferUi` لم يتغيّر): bg ← الأرض · sur ← البطاقة · sur2 ← الغائر · brd ← الحافّة · tx ← النصّ · mut ← الخافت ·
 * acc ← <b>الجمر</b> (الفعلُ الأساسيُّ عند الكبتن في السِمتين، كـ«وصلتني» و«إرسال الطلب») · inv ← ما فوق الجمر · ok ← النجاح ·
 * sa/sb ← البطاقة/الغائر · dim ← الظلّ (`--t2-scrim`).
 *
 * <p><b>ولمَ نُسخت هنا ولم تُقرأ من الويب</b>: هذه الأسطحُ الثلاثةُ (شاشةُ ملء
 * الشاشة · الورقةُ السفلية · الفقاعة) <b>تُرسم والـWebView قد تكون غيرَ
 * محمَّلةٍ أصلاً</b> — والتطبيقُ مقتولٌ والشاشةُ مقفلة. فلا سبيلَ إلى متغيّرات
 * CSS من هنا، <b>والقيمُ تُنسخ من التصميم بأسمائها</b> لا تُخمَّن.
 *
 * <p><b>والسِمتان كلتاهما</b> كما في التصميم: <code>thm-dark</code> و
 * <code>thm-light</code>. وتُختار بسِمة النظام لا بسِمة التطبيق —
 * <b>لأن التطبيقَ قد لا يكون يعمل</b> حين تُرسم.
 */
public final class OfferPalette {

    public final int bg, sur, sur2, brd, tx, mut, inv, acc, ok, sa, sb, dim;

    private OfferPalette(boolean dark) {
        if (dark) {
            // **الإسفلت** — `html.dark` في tokens.css
            bg = Color.parseColor("#0e1013");
            sur = Color.parseColor("#171a1f");
            sur2 = Color.parseColor("#20242b");
            brd = Color.parseColor("#2b3038");
            tx = Color.parseColor("#f2efe8");
            mut = Color.parseColor("#9097a1");
            inv = Color.parseColor("#0e1013");
            acc = Color.parseColor("#ff6a33");
            ok = Color.parseColor("#3dbe7e");
            sa = Color.parseColor("#171a1f");
            sb = Color.parseColor("#20242b");
            dim = Color.argb(153, 0, 0, 0);
        } else {
            // **الحجرُ الجيريّ** — الجذرُ في tokens.css
            bg = Color.parseColor("#f4f1ea");
            sur = Color.parseColor("#ffffff");
            sur2 = Color.parseColor("#f4f1ea");
            brd = Color.parseColor("#e0dad0");
            tx = Color.parseColor("#14161a");
            mut = Color.parseColor("#6a6862");
            inv = Color.parseColor("#14161a");
            acc = Color.parseColor("#f05a28");
            ok = Color.parseColor("#1e7f55");
            sa = Color.parseColor("#ffffff");
            sb = Color.parseColor("#f4f1ea");
            dim = Color.argb(115, 20, 22, 26);
        }
    }

    public static OfferPalette of(Context context) {
        int mode = context.getResources().getConfiguration().uiMode
                & Configuration.UI_MODE_NIGHT_MASK;
        return new OfferPalette(mode == Configuration.UI_MODE_NIGHT_YES);
    }
}
