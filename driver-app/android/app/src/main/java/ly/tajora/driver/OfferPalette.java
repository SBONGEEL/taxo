package ly.tajora.driver;

import android.content.Context;
import android.content.res.Configuration;
import android.graphics.Color;

/**
 * ألوانُ التصميم حرفاً — <b>`mobile-app-design-request` بسِمتيه</b>.
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
            bg = Color.parseColor("#14181d");
            sur = Color.parseColor("#0d1014");
            sur2 = Color.parseColor("#1a2027");
            brd = Color.parseColor("#2a313a");
            tx = Color.parseColor("#e6edf3");
            mut = Color.parseColor("#8b949e");
            inv = Color.parseColor("#0d1014");
            acc = Color.parseColor("#e6edf3");
            ok = Color.parseColor("#3fb970");
            sa = Color.parseColor("#1c2128");
            sb = Color.parseColor("#20262e");
            dim = Color.argb(158, 4, 6, 8);
        } else {
            bg = Color.parseColor("#f2f0eb");
            sur = Color.parseColor("#ffffff");
            sur2 = Color.parseColor("#faf9f6");
            brd = Color.parseColor("#ddd8cf");
            tx = Color.parseColor("#171b20");
            mut = Color.parseColor("#6e7681");
            inv = Color.parseColor("#f2f0eb");
            acc = Color.parseColor("#171b20");
            ok = Color.parseColor("#1a7f4e");
            sa = Color.parseColor("#e6e3db");
            sb = Color.parseColor("#ece9e1");
            dim = Color.argb(115, 20, 24, 29);
        }
    }

    public static OfferPalette of(Context context) {
        int mode = context.getResources().getConfiguration().uiMode
                & Configuration.UI_MODE_NIGHT_MASK;
        return new OfferPalette(mode == Configuration.UI_MODE_NIGHT_YES);
    }
}
