package ly.tajora.driver;

import android.content.Context;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.os.Build;
import android.os.CountDownTimer;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * <b>الشاشة ٠٢ — ورقةٌ سفليّةٌ فوق التطبيق الذي يستعمله</b>.
 *
 * <p>«يستعمل هاتفه في تطبيق آخر، فتظهر ورقة سفلية فوق ما يفعله <b>دون أن
 * تخرجه منه</b>» — ولذلك ورقةٌ لا شاشةٌ كاملة، ولذلك «الرفض يعيدك إلى ما كنت
 * فيه فوراً».
 *
 * <p><b>⚠ وحدُّ المنصّة مكتوبٌ هنا لا مسكوتٌ عنه</b> (قرارُ المالك 2026-08-30):
 * <b>هذه الورقةُ والفقاعةُ تمرّان بإذنٍ واحد</b> —
 * {@code SYSTEM_ALERT_WINDOW}. فكلُّ ما يُرسم فوق تطبيقٍ آخر يحتاجه، <b>ورفضُ
 * الإذن يُسقط الاثنتين معاً</b> ولا تنجو إحداهما. ومن رفضه يذهب إلى
 * {@link OfferActivity} أو إلى إشعارٍ بأقصى أهميّة — <b>ولا يبقى بلا شيء</b>.
 *
 * <p><b>وهندستُها من التصميم</b>: مقبضٌ ٤٠×٤ فوقها، ورأسٌ فيه شارةُ TAXO
 * و«طلب رحلة جديد» ومؤشّرُ النغمة، وحلقةُ ٥٢ بجانب أجرةِ ٢٣، وسطرُ «كاش ·
 * مسافة»، وصفَّا الطريق ١٣، وزرّان: «اقبل وافتح التطبيق» بوزن ٢٫٥ و«تجاهل»
 * بوزن ١، وسطرٌ ١٠٫٥ في القاع.
 */
public final class OfferSheetWindow {

    private static View view;
    private static CountDownTimer timer;

    private OfferSheetWindow() {}

    public static boolean showing() {
        return view != null;
    }

    public static void show(Context context, OfferData offer) {
        if (!Settings.canDrawOverlays(context)) return;
        new Handler(Looper.getMainLooper())
                .post(() -> attach(context.getApplicationContext(), offer));
    }

    private static void attach(Context c, OfferData offer) {
        hideNow(c);
        WindowManager manager = c.getSystemService(WindowManager.class);
        if (manager == null) return;
        OfferPalette p = OfferPalette.of(c);

        FrameLayout root = new FrameLayout(c);
        // **التعتيمُ خلفها** كما في التصميم (`--dim`) — ويقول إنّ شيئاً يُنتظر
        root.setBackgroundColor(p.dim);

        LinearLayout sheet = new LinearLayout(c);
        sheet.setOrientation(LinearLayout.VERTICAL);
        sheet.setBackground(topRounded(c, p));
        sheet.setPadding(OfferUi.dp(c, 18), OfferUi.dp(c, 12),
                OfferUi.dp(c, 18), OfferUi.dp(c, 24));
        FrameLayout.LayoutParams sheetLp = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM);
        sheet.setLayoutParams(sheetLp);

        View grip = new View(c);
        LinearLayout.LayoutParams gripLp =
                new LinearLayout.LayoutParams(OfferUi.dp(c, 40), OfferUi.dp(c, 4));
        gripLp.gravity = Gravity.CENTER_HORIZONTAL;
        gripLp.bottomMargin = OfferUi.dp(c, 15);
        grip.setLayoutParams(gripLp);
        grip.setBackground(OfferUi.box(p.brd, Color.TRANSPARENT, c, 99));
        sheet.addView(grip);

        LinearLayout head = new LinearLayout(c);
        head.setOrientation(LinearLayout.HORIZONTAL);
        head.setGravity(Gravity.CENTER_VERTICAL);
        head.addView(OfferUi.brandChip(c, p, 10.5f));
        TextView title = OfferUi.text(c, "طلب رحلة جديد", 11.5f, p.mut, true);
        LinearLayout.LayoutParams titleLp = new LinearLayout.LayoutParams(
                0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        titleLp.setMarginStart(OfferUi.dp(c, 9));
        title.setLayoutParams(titleLp);
        head.addView(title);
        head.addView(OfferUi.tonePill(c, p, false));
        LinearLayout.LayoutParams headLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        headLp.bottomMargin = OfferUi.dp(c, 14);
        head.setLayoutParams(headLp);
        sheet.addView(head);

        LinearLayout money = new LinearLayout(c);
        money.setOrientation(LinearLayout.HORIZONTAL);
        money.setGravity(Gravity.CENTER_VERTICAL);
        RingView ring = new RingView(c, p, 17f);
        LinearLayout.LayoutParams ringLp = new LinearLayout.LayoutParams(
                OfferUi.dp(c, 52), OfferUi.dp(c, 52));
        ringLp.setMarginEnd(OfferUi.dp(c, 14));
        ring.setLayoutParams(ringLp);
        money.addView(ring);

        LinearLayout column = new LinearLayout(c);
        column.setOrientation(LinearLayout.VERTICAL);
        column.addView(OfferUi.fare(c, p, offer, 23f, 12f));
        column.addView(OfferUi.text(c, offer.meta(false), 11.5f, p.mut, false));
        money.addView(column);
        LinearLayout.LayoutParams moneyLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        moneyLp.bottomMargin = OfferUi.dp(c, 15);
        money.setLayoutParams(moneyLp);
        sheet.addView(money);

        LinearLayout route = OfferUi.route(c, p, offer.pickup, offer.drop, 13f);
        LinearLayout.LayoutParams routeLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        routeLp.bottomMargin = OfferUi.dp(c, 17);
        route.setLayoutParams(routeLp);
        sheet.addView(route);

        LinearLayout actions = new LinearLayout(c);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        actions.addView(button(c, p, "اقبل وافتح التطبيق", true, 2.5f,
                v -> { settle(c); OfferApi.accept(c, offer.rideId, ok -> {}); }));
        actions.addView(button(c, p, "تجاهل", false, 1f,
                v -> { settle(c); OfferApi.decline(c, offer.rideId, ok -> {}); }));
        sheet.addView(actions);

        TextView note = OfferUi.text(
                c, "الرفض يعيدك إلى ما كنت فيه فوراً.", 10.5f, p.mut, false);
        note.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams noteLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        noteLp.topMargin = OfferUi.dp(c, 12);
        note.setLayoutParams(noteLp);
        sheet.addView(note);

        root.addView(sheet);

        int type = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                : WindowManager.LayoutParams.TYPE_PHONE;
        WindowManager.LayoutParams params = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.MATCH_PARENT,
                type,
                // **لا `SHOW_WHEN_LOCKED` هنا**: الشاشةُ المقفلةُ لملء الشاشة
                // وحدَه (قرارُ المالك) — والورقةُ لمن هاتفُه مفتوحٌ بيده
                WindowManager.LayoutParams.FLAG_WATCH_OUTSIDE_TOUCH,
                PixelFormat.TRANSLUCENT);
        params.gravity = Gravity.BOTTOM;

        try {
            manager.addView(root, params);
            view = root;
        } catch (Exception ignored) {
            view = null;
            return;
        }

        ring.set(offer.seconds, offer.seconds);
        timer = new CountDownTimer(offer.seconds * 1000L, 250L) {
            @Override
            public void onTick(long remaining) {
                ring.set((int) Math.ceil(remaining / 1000d), offer.seconds);
            }

            @Override
            public void onFinish() {
                hideNow(c);
            }
        };
        timer.start();
    }

    private static android.graphics.drawable.GradientDrawable topRounded(
            Context c, OfferPalette p
    ) {
        android.graphics.drawable.GradientDrawable d =
                new android.graphics.drawable.GradientDrawable();
        d.setColor(p.sur);
        float r = OfferUi.dp(c, 28);
        d.setCornerRadii(new float[] {r, r, r, r, 0, 0, 0, 0});
        d.setStroke(OfferUi.dp(c, 1), p.brd);
        return d;
    }

    private static TextView button(
            Context c, OfferPalette p, String label, boolean primary,
            float weight, View.OnClickListener onClick
    ) {
        TextView button = OfferUi.text(
                c, label, primary ? 15f : 13f, primary ? p.inv : p.mut, primary);
        button.setGravity(Gravity.CENTER);
        button.setPadding(0, OfferUi.dp(c, 16), 0, OfferUi.dp(c, 16));
        button.setBackground(primary
                ? OfferUi.box(p.acc, Color.TRANSPARENT, c, 15)
                : OfferUi.box(Color.TRANSPARENT, p.brd, c, 15));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                0, LinearLayout.LayoutParams.WRAP_CONTENT, weight);
        lp.setMarginEnd(primary ? OfferUi.dp(c, 8) : 0);
        button.setLayoutParams(lp);
        button.setOnClickListener(onClick);
        return button;
    }

    private static void settle(Context c) {
        hideNow(c.getApplicationContext());
    }

    public static void hide(Context context) {
        new Handler(Looper.getMainLooper())
                .post(() -> hideNow(context.getApplicationContext()));
    }

    private static void hideNow(Context c) {
        if (timer != null) {
            timer.cancel();
            timer = null;
        }
        if (view == null) return;
        WindowManager manager = c.getSystemService(WindowManager.class);
        try {
            if (manager != null) manager.removeView(view);
        } catch (Exception ignored) {
            // نافذةٌ أُزيلت من تحتنا
        }
        view = null;
    }
}
