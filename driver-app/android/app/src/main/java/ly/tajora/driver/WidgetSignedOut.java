package ly.tajora.driver;

import android.app.PendingIntent;
import android.content.Context;
import android.text.SpannableString;
import android.text.Spanned;
import android.text.style.ForegroundColorSpan;
import android.view.View;
import android.widget.RemoteViews;

/**
 * <b>بطاقةُ «قبل الدخول» في الودجة</b> (أمرُ المالك ٢٠/١١ السادس، البند ٣) — كان ثلثا الودجة فارغين: سطرٌ واحدٌ في أعلاها وفراغٌ تحته.
 *
 * <p>الآن تملأ الودجةَ كلَّها: شعارُ التطبيق، وكلمةُ TAXO بحرف X البرتقاليّ، وسطرٌ عربيٌّ قصير، وزرٌّ واحدٌ واضح. <b>عموديّةٌ حين يتّسع
 * الارتفاع</b> ({@link #COLUMN_MIN_DP} فأكثر) <b>وصفٌّ واحدٌ حين يضيق</b> — فلا يُقصّ الزرُّ في المقاس الصغير ولا يبقى فراغٌ في الكبير.
 * والألوانُ من {@code values}/{@code values-night} فتتبع نهارَ الهاتف وليلَه. والودجةُ تخفي محتواها قبل استدعائها.
 * <b>منسوخةٌ بين التطبيقين</b> باسم الحزمة وحدَه.
 */
final class WidgetSignedOut {
    /** أدنى ارتفاعٍ للبطاقة العموديّة — شعارٌ ٤٨ وكلمةٌ وسطرٌ وزرٌّ ٤٢ مع الحشوة. */
    static final int COLUMN_MIN_DP = 150;

    private WidgetSignedOut() {}

    /** <b>ارتفاعُ الودجة في الاتّجاه الظاهر</b> بالـdp — الطوليُّ {@code MAX_HEIGHT} والأفقيُّ {@code MIN_HEIGHT} (عُرفُ أندرويد للمشغِّلات). */
    static int heightDp(Context ctx, android.os.Bundle options, int fallback) {
        if (options == null) return fallback;
        boolean portrait = ctx.getResources().getConfiguration().orientation
                == android.content.res.Configuration.ORIENTATION_PORTRAIT;
        return pick(portrait,
                options.getInt(android.appwidget.AppWidgetManager.OPTION_APPWIDGET_MIN_HEIGHT, fallback),
                options.getInt(android.appwidget.AppWidgetManager.OPTION_APPWIDGET_MAX_HEIGHT, 0));
    }

    /** خالصة: الطوليُّ يأخذ الأكبرَ من الاثنين (بعضُ المشغِّلات لا تملأ MAX فيبقى صفراً). */
    static int pick(boolean portrait, int minH, int maxH) {
        return portrait ? Math.max(minH, maxH) : minH;
    }

    /** خالصة: <b>أعموديّة؟</b> من ارتفاع الودجة بالـdp. */
    static boolean column(int heightDp) {
        return heightDp >= COLUMN_MIN_DP;
    }

    static void show(Context ctx, RemoteViews v, int heightDp, String line, String button, PendingIntent open) {
        boolean col = column(heightDp);
        v.setViewVisibility(R.id.wo_root, View.VISIBLE);
        v.setViewVisibility(R.id.wo_col, col ? View.VISIBLE : View.GONE);
        v.setViewVisibility(R.id.wo_row, col ? View.GONE : View.VISIBLE);
        CharSequence mark = wordmark(ctx);
        v.setTextViewText(R.id.wo_mark, mark);
        v.setTextViewText(R.id.wo_mark2, mark);
        v.setTextViewText(R.id.wo_line, line);
        v.setTextViewText(R.id.wo_line2, line);
        v.setTextViewText(R.id.wo_btn, button);
        v.setTextViewText(R.id.wo_btn2, button);
        v.setOnClickPendingIntent(R.id.wo_btn, open);
        v.setOnClickPendingIntent(R.id.wo_btn2, open);
    }

    /** «TAXO» وحرفُ X بلون الهوية — كالشعار في التطبيق. */
    private static CharSequence wordmark(Context ctx) {
        SpannableString s = new SpannableString("TAXO");
        s.setSpan(new ForegroundColorSpan(ctx.getColor(R.color.w2_acc)), 2, 3, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        return s;
    }
}
