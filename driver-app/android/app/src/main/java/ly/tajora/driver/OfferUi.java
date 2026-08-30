package ly.tajora.driver;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.animation.Animation;
import android.view.animation.ScaleAnimation;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * قِطعُ التصميم المشتركة — <b>بيتٌ واحدٌ لما يتكرّر في الأسطح الثلاثة</b>.
 *
 * <p>شارةُ TAXO، وشارةُ «نغمة + اهتزاز»، وصفَّا الانطلاق والوجهة، وكتلةُ
 * الأجرة — <b>يرسمها التصميمُ في الشاشات الأربع بالحروف نفسِها وبأحجامٍ
 * تختلف</b>. فتُبنى مرّةً بمقاسٍ يُمرَّر، <b>ونسخُها ثلاثاً يجعل تعديلَ حرفٍ
 * إصلاحاً يقع مرّتين ويُنسى مرّة</b>.
 *
 * <p><b>والأحجامُ من التصميم بالبكسل المستقلّ</b> — والتصميمُ يكتبها px في
 * إطارٍ عرضُه 390، وهو عرضُ هاتفٍ منطقيّ، <b>فتُقرأ dp مباشرةً</b>.
 */
public final class OfferUi {

    private OfferUi() {}

    public static int dp(Context c, float v) {
        return Math.round(TypedValue.applyDimension(
                TypedValue.COMPLEX_UNIT_DIP, v, c.getResources().getDisplayMetrics()));
    }

    public static TextView text(
            Context c, String value, float sp, int color, boolean bold
    ) {
        TextView view = new TextView(c);
        view.setText(value);
        view.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        view.setTextColor(color);
        if (bold) view.setTypeface(Typeface.DEFAULT_BOLD);
        return view;
    }

    public static GradientDrawable box(int fill, int stroke, Context c, float radiusDp) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(fill);
        d.setCornerRadius(dp(c, radiusDp));
        if (stroke != Color.TRANSPARENT) d.setStroke(dp(c, 1), stroke);
        return d;
    }

    /** شارةُ TAXO — <b>خلفيةُ `--acc` ونصُّ `--inv`</b> كما في التصميم. */
    public static TextView brandChip(Context c, OfferPalette p, float sp) {
        TextView chip = text(c, "TAXO", sp, p.inv, true);
        chip.setLetterSpacing(0.12f);
        chip.setBackground(box(p.acc, Color.TRANSPARENT, c, 6));
        chip.setPadding(dp(c, 8), dp(c, 4), dp(c, 8), dp(c, 4));
        return chip;
    }

    /**
     * شارةُ «نغمة + اهتزاز» — ثلاثةُ أعمدةٍ تنبض ومعها النصّ.
     *
     * <p><b>وهي في التصميم فوق البطاقة داخل التطبيق وفي رأس الورقة وشاشةِ
     * القفل</b>، بحركة <code>eq</code> و<code>shake</code> — <b>والحركةُ
     * جزءٌ من الرسم لا زينة</b>: هي ما يقول للكبتن أنّ صوتاً يعمل الآن.
     */
    public static LinearLayout tonePill(Context c, OfferPalette p, boolean pill) {
        LinearLayout row = new LinearLayout(c);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);

        LinearLayout bars = new LinearLayout(c);
        bars.setOrientation(LinearLayout.HORIZONTAL);
        bars.setGravity(Gravity.CENTER_VERTICAL);
        float[] heights = {6f, 12f, 9f};
        for (int i = 0; i < heights.length; i++) {
            View bar = new View(c);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                    dp(c, 2.5f), dp(c, heights[i]));
            lp.setMarginEnd(dp(c, 2.5f));
            bar.setLayoutParams(lp);
            bar.setBackground(box(p.ok, Color.TRANSPARENT, c, 2));
            ScaleAnimation pulse = new ScaleAnimation(
                    1f, 1f, 0.3f, 1f,
                    Animation.RELATIVE_TO_SELF, 0.5f,
                    Animation.RELATIVE_TO_SELF, 0.5f);
            pulse.setDuration(800);
            pulse.setRepeatCount(Animation.INFINITE);
            pulse.setRepeatMode(Animation.REVERSE);
            pulse.setStartOffset(Math.round(i * 150));
            bar.startAnimation(pulse);
            bars.addView(bar);
        }
        row.addView(bars);

        TextView label = text(c, "نغمة + اهتزاز", 11f, p.ok, true);
        label.setPadding(dp(c, 6), 0, 0, 0);
        row.addView(label);

        if (pill) {
            row.setBackground(box(p.sur, p.brd, c, 99));
            row.setPadding(dp(c, 14), dp(c, 7), dp(c, 14), dp(c, 7));
        }
        return row;
    }

    /**
     * صفَّا الانطلاق والوجهة — <b>شبكةُ `12px 1fr` في التصميم</b>: نقطةٌ
     * دائريّةٌ بلون النصّ فوق، وخطٌّ رأسيٌّ، ومربّعٌ بلون الخافت تحت.
     */
    public static LinearLayout route(
            Context c, OfferPalette p, String pickup, String drop, float sp
    ) {
        LinearLayout wrap = new LinearLayout(c);
        wrap.setOrientation(LinearLayout.VERTICAL);

        wrap.addView(routeRow(c, p, pickup, sp, true));

        View stem = new View(c);
        LinearLayout.LayoutParams stemLp =
                new LinearLayout.LayoutParams(dp(c, 2), dp(c, 12));
        stemLp.setMarginStart(dp(c, 5));
        stem.setLayoutParams(stemLp);
        stem.setBackgroundColor(p.brd);
        wrap.addView(stem);

        wrap.addView(routeRow(c, p, drop, sp, false));
        return wrap;
    }

    private static LinearLayout routeRow(
            Context c, OfferPalette p, String value, float sp, boolean origin
    ) {
        LinearLayout row = new LinearLayout(c);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);

        View dot = new View(c);
        LinearLayout.LayoutParams lp =
                new LinearLayout.LayoutParams(dp(c, 8), dp(c, 8));
        lp.setMarginEnd(dp(c, 10));
        dot.setLayoutParams(lp);
        // **دائرةٌ للانطلاق ومربّعٌ صغيرُ الاستدارة للوجهة** — كما في التصميم
        dot.setBackground(box(origin ? p.tx : p.mut, Color.TRANSPARENT, c, origin ? 99 : 2));
        row.addView(dot);

        TextView label = text(c, value, sp, origin ? p.tx : p.mut, false);
        label.setMaxLines(2);
        row.addView(label);
        return row;
    }

    /** كتلةُ الأجرة: رقمٌ كبيرٌ ثم رمزُ العملة أصغرَ وبلون الخافت. */
    public static LinearLayout fare(
            Context c, OfferPalette p, OfferData offer, float sp, float currencySp
    ) {
        LinearLayout row = new LinearLayout(c);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.BOTTOM);
        row.addView(text(c, offer.fare, sp, p.tx, true));
        TextView currency = text(c, offer.currency, currencySp, p.mut, false);
        currency.setPadding(dp(c, 5), 0, 0, dp(c, 2));
        row.addView(currency);
        return row;
    }
}
