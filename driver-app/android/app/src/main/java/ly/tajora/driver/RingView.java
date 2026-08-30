package ly.tajora.driver;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.view.View;

/**
 * حلقةُ المهلة — <b>هندسةُ التصميم حرفاً</b>.
 *
 * <p>التصميمُ يرسمها SVG بـ<code>viewBox="0 0 56 56"</code> مُدارةً
 * <code>-90deg</code>، دائرتان <code>r=26</code> بعرض <code>3.5</code>،
 * و<code>stroke-dasharray:163</code>، والإزاحة
 * <code>(1 − المتبقي/٧) × 163</code>. <b>والنسبةُ هي ما نُقل</b> لا البكسلات:
 * نصفُ القطر <code>26/56</code> من الضلع، والعرضُ <code>3.5/56</code> — فتكبر
 * الحلقةُ إلى ١١٢ في شاشة ملء الشاشة كما في التصميم (<code>r=52</code>،
 * عرض <code>5</code>، <code>dasharray 327</code>) <b>بالنسبة نفسِها</b>.
 *
 * <p><b>والرقمُ في وسطها يُرسم هنا</b> لا في عرضٍ ثانٍ فوقها: نصٌّ مركزيٌّ
 * واحدٌ أدقُّ من تكديس <code>FrameLayout</code>، ويُقاس بالخطّ نفسِه.
 *
 * <p><b>والخاناتُ عربيّةٌ-هنديّة</b> كما في التصميم (<code>_fmtN</code> يحوّل
 * في العربية وحدَها)، <b>وهذه الأسطحُ عربيّةٌ دائماً</b> بقرار المالك
 * 2026-08-30: «عربيّ. الإنجليزية في التصميم مرجع لا شحنة».
 */
public class RingView extends View {

    private static final String[] AR = {"٠", "١", "٢", "٣", "٤", "٥", "٦", "٧", "٨", "٩"};

    private final Paint track = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint arc = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint label = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF box = new RectF();

    private int left = 7;
    private int total = 7;

    public RingView(Context context, OfferPalette p, float labelSp) {
        super(context);
        track.setStyle(Paint.Style.STROKE);
        track.setColor(p.brd);
        arc.setStyle(Paint.Style.STROKE);
        arc.setColor(p.ok);
        arc.setStrokeCap(Paint.Cap.ROUND);
        label.setColor(p.tx);
        label.setTextAlign(Paint.Align.CENTER);
        label.setFakeBoldText(true);
        label.setTextSize(labelSp * getResources().getDisplayMetrics().scaledDensity);
    }

    /** المتبقّي بالثواني، ومنه تُحسب الإزاحةُ كما في التصميم. */
    public void set(int secondsLeft, int totalSeconds) {
        left = Math.max(0, secondsLeft);
        total = Math.max(1, totalSeconds);
        invalidate();
    }

    private static String arabic(int value) {
        StringBuilder out = new StringBuilder();
        for (char c : String.valueOf(value).toCharArray()) {
            out.append(c >= '0' && c <= '9' ? AR[c - '0'] : String.valueOf(c));
        }
        return out.toString();
    }

    @Override
    protected void onDraw(Canvas canvas) {
        float side = Math.min(getWidth(), getHeight());
        // **النِّسبُ من التصميم**: r = 26/56 من الضلع، والعرض 3.5/56
        float stroke = side * (3.5f / 56f);
        float radius = side * (26f / 56f);
        track.setStrokeWidth(stroke);
        arc.setStrokeWidth(stroke);

        float cx = getWidth() / 2f, cy = getHeight() / 2f;
        box.set(cx - radius, cy - radius, cx + radius, cy + radius);
        canvas.drawOval(box, track);

        // **يبدأ من الأعلى** — وهو ما يفعله `rotate(-90deg)` في التصميم
        float sweep = 360f * ((float) left / (float) total);
        if (sweep > 0) canvas.drawArc(box, -90f, sweep, false, arc);

        float baseline = cy - (label.descent() + label.ascent()) / 2f;
        canvas.drawText(arabic(left), cx, baseline, label);
    }
}
