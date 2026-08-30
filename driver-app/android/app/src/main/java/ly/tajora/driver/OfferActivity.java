package ly.tajora.driver;

import android.app.Activity;
import android.app.KeyguardManager;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.os.CountDownTimer;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * <b>الشاشة ٠٣ (شاشةٌ مقفلة) والشاشة ٠٤-البديل — نمطُ المكالمة الواردة.</b>
 *
 * <p><b>ونشاطٌ أصليٌّ لا مسارُ ويب</b> (قرارُ المالك 2026-08-30): «المقتولُ
 * وبلا شبكةٍ لا يحمّل WebView». وهذه الشاشةُ تُعرض والتطبيقُ مقتولٌ والشاشةُ
 * مقفلةٌ والشبكةُ قد تكون بطيئة — <b>فكلُّ ما تحتاجه يأتي في الـIntent</b>،
 * ولا تنتظر شيئاً من الشبكة لترسم.
 *
 * <p><b>وهندستُها من التصميم حرفاً</b>: حلقةُ ١١٢ (وفي البديل ١٠٤)، وأجرةٌ
 * ٤٠sp (٣٨ في البديل)، وسطرُ «كاش · مسافة · اقتصادي» ١٢٫٥، وصفَّا الطريق
 * ١٣٫٥، وزرّان دائريّان: الرفضُ ٦٦ بحدٍّ ورمزِ ✕، والقبولُ ٨٢ بخلفيةِ
 * <code>--ok</code> ورمزِ ✓.
 *
 * <p><b>وفوق القفل بلا فتحٍ يدويّ</b>: {@code setShowWhenLocked} و
 * {@code setTurnScreenOn} — وهو نصُّ التصميم «القبول يفتح التطبيق مباشرة دون
 * فتح القفل يدوياً».
 *
 * <p><b>ويقبل ثم يفتح</b> (قرارُ المالك): النداءُ يقع من هنا، ثم يُفتح
 * التطبيقُ على البطاقة. <b>ولو انتظر فتحَ التطبيقِ ليقبل لَخسر الطلب</b> —
 * سبعُ ثوانٍ لا تكفي إقلاعَ WebView وتحميلَ شاشاتٍ من الشبكة.
 */
public class OfferActivity extends Activity {

    /** يُمرَّر من {@link OfferAlert}: أهي شاشةُ القفل أم بديلُ الفقاعة؟ */
    public static final String EXTRA_LOCKED = "locked";

    private CountDownTimer timer;
    private RingView ring;
    private boolean settled = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // **فوق القفل ومع إيقاظ الشاشة** — وإلا وصلت البطاقةُ إلى شاشةٍ مطفأة
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O_MR1) {
            setShowWhenLocked(true);
            setTurnScreenOn(true);
            KeyguardManager keyguard = getSystemService(KeyguardManager.class);
            if (keyguard != null) keyguard.requestDismissKeyguard(this, null);
        } else {
            getWindow().addFlags(
                    WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED
                            | WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
                            | WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        }
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        OfferData offer = OfferData.from(getIntent());
        boolean locked = getIntent().getBooleanExtra(EXTRA_LOCKED, true);
        OfferPalette p = OfferPalette.of(this);
        setContentView(build(offer, p, locked));
        start(offer);
    }

    private View build(OfferData offer, OfferPalette p, boolean locked) {
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(p.dim);

        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setBackground(OfferUi.box(p.sur, p.brd, this, 30));
        card.setPadding(
                OfferUi.dp(this, 22), OfferUi.dp(this, 26),
                OfferUi.dp(this, 22), OfferUi.dp(this, 22));
        FrameLayout.LayoutParams cardLp = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT);
        // التصميم: `inset:44px 12px 18px`
        cardLp.setMargins(OfferUi.dp(this, 12), OfferUi.dp(this, 44),
                OfferUi.dp(this, 12), OfferUi.dp(this, 18));
        card.setLayoutParams(cardLp);

        // ── الرأس: شارةُ TAXO، والعنوان، ومؤشّرُ النغمة
        LinearLayout head = new LinearLayout(this);
        head.setOrientation(LinearLayout.HORIZONTAL);
        head.setGravity(Gravity.CENTER_VERTICAL);
        head.addView(OfferUi.brandChip(this, p, 10.5f));
        TextView title = OfferUi.text(
                this, locked ? "طلب رحلة جديد" : "بديل: إشعار ملء الشاشة",
                11.5f, p.mut, true);
        LinearLayout.LayoutParams titleLp = new LinearLayout.LayoutParams(
                0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        titleLp.setMarginStart(OfferUi.dp(this, 10));
        title.setLayoutParams(titleLp);
        head.addView(title);
        head.addView(OfferUi.tonePill(this, p, false));
        card.addView(head);

        // ── الوسط: الحلقةُ الكبيرة ثم الأجرة ثم السطرُ الوصفيّ
        LinearLayout middle = new LinearLayout(this);
        middle.setOrientation(LinearLayout.VERTICAL);
        middle.setGravity(Gravity.CENTER_HORIZONTAL);
        LinearLayout.LayoutParams midLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        midLp.topMargin = OfferUi.dp(this, locked ? 34 : 30);
        middle.setLayoutParams(midLp);

        int ringSide = OfferUi.dp(this, locked ? 112 : 104);
        ring = new RingView(this, p, locked ? 38f : 36f);
        LinearLayout.LayoutParams ringLp =
                new LinearLayout.LayoutParams(ringSide, ringSide);
        ringLp.bottomMargin = OfferUi.dp(this, locked ? 20 : 18);
        ring.setLayoutParams(ringLp);
        middle.addView(ring);

        LinearLayout fare = OfferUi.fare(this, p, offer, locked ? 40f : 38f, 15f);
        fare.setGravity(Gravity.CENTER);
        middle.addView(fare);

        TextView meta = OfferUi.text(this, offer.meta(true), 12.5f, p.mut, false);
        LinearLayout.LayoutParams metaLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        metaLp.topMargin = OfferUi.dp(this, 7);
        meta.setLayoutParams(metaLp);
        middle.addView(meta);
        card.addView(middle);

        // ── الطريق
        LinearLayout route = OfferUi.route(this, p, offer.pickup, offer.drop, 13.5f);
        LinearLayout.LayoutParams routeLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        routeLp.topMargin = OfferUi.dp(this, locked ? 30 : 28);
        routeLp.setMarginStart(OfferUi.dp(this, 4));
        routeLp.setMarginEnd(OfferUi.dp(this, 4));
        route.setLayoutParams(routeLp);
        card.addView(route);

        // ── القاع: زرّان دائريّان، والقبولُ أكبرُ عمداً
        LinearLayout actions = new LinearLayout(this);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        actions.setGravity(Gravity.CENTER_VERTICAL);
        actions.setWeightSum(2f);
        LinearLayout.LayoutParams actionsLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f);
        actionsLp.topMargin = OfferUi.dp(this, locked ? 26 : 24);
        actionsLp.gravity = Gravity.BOTTOM;
        actions.setLayoutParams(actionsLp);

        actions.addView(circle(
                p, "✕", "تجاهل", locked ? 66 : 64, false,
                v -> decline(offer)));
        actions.addView(circle(
                p, "✓", "اقبل", locked ? 82 : 78, true,
                v -> accept(offer)));
        card.addView(actions);

        TextView note = OfferUi.text(
                this,
                locked
                        ? "القبول يفتح التطبيق مباشرة دون فتح القفل يدوياً."
                        : "الفقاعة معطّلة الآن — لا تظهران معاً.",
                10.5f, p.mut, false);
        note.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams noteLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        noteLp.topMargin = OfferUi.dp(this, locked ? 14 : 13);
        note.setLayoutParams(noteLp);
        card.addView(note);

        root.addView(card);
        return root;
    }

    private LinearLayout circle(
            OfferPalette p, String glyph, String label, int side,
            boolean primary, View.OnClickListener onClick
    ) {
        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);
        column.setGravity(Gravity.CENTER);
        column.setLayoutParams(new LinearLayout.LayoutParams(
                0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));
        column.setOnClickListener(onClick);

        TextView badge = OfferUi.text(
                this, glyph, primary ? 25f : 21f, primary ? Color.WHITE : p.mut, false);
        badge.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams badgeLp = new LinearLayout.LayoutParams(
                OfferUi.dp(this, side), OfferUi.dp(this, side));
        badgeLp.bottomMargin = OfferUi.dp(this, 9);
        badge.setLayoutParams(badgeLp);
        badge.setBackground(primary
                ? OfferUi.box(p.ok, Color.TRANSPARENT, this, side / 2f)
                : OfferUi.box(p.sur2, p.brd, this, side / 2f));
        column.addView(badge);
        column.addView(OfferUi.text(
                this, label, primary ? 12.5f : 11.5f, primary ? p.tx : p.mut, primary));
        return column;
    }

    private void start(OfferData offer) {
        ring.set(offer.seconds, offer.seconds);
        timer = new CountDownTimer(offer.seconds * 1000L, 250L) {
            @Override
            public void onTick(long remaining) {
                ring.set((int) Math.ceil(remaining / 1000d), offer.seconds);
            }

            @Override
            public void onFinish() {
                // **انقضاءُ المهلة يُغلق الشاشةَ ولا يرفض**: الرفضُ فعلٌ
                // يقرّره الكبتن، والصمتُ ليس رفضاً — والخلفيةُ تفرّق بينهما
                ring.set(0, offer.seconds);
                finishAndRemoveTask();
            }
        };
        timer.start();
    }

    private void accept(OfferData offer) {
        if (settled) return;
        settled = true;
        if (timer != null) timer.cancel();
        OfferAlert.hide(this);
        OfferApi.accept(this, offer.rideId, ok -> finishAndRemoveTask());
    }

    private void decline(OfferData offer) {
        if (settled) return;
        settled = true;
        if (timer != null) timer.cancel();
        OfferAlert.hide(this);
        OfferApi.decline(this, offer.rideId, ok -> finishAndRemoveTask());
    }

    @Override
    protected void onDestroy() {
        if (timer != null) timer.cancel();
        super.onDestroy();
    }
}
