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
import android.view.MotionEvent;
import android.view.View;
import android.view.WindowManager;
import android.view.animation.AlphaAnimation;
import android.view.animation.Animation;
import android.view.animation.AnimationSet;
import android.view.animation.ScaleAnimation;
import android.view.animation.TranslateAnimation;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * <b>الشاشة ٠٤ — فقاعةٌ عائمةٌ تُقرأ والتطبيقُ مغلق</b>، بحالتيها كما رُسمتا.
 *
 * <p><b>المطويّة</b>: بطاقةُ ١١٨ عرضاً، فيها حلقةُ ٥٦ بهالةٍ نابضة، ثم الأجرةُ
 * ١٧، ثم المسافةُ ١٠، ثم شارةُ TAXO ٩ — وتحتها «اسحبها لأي مكان». <b>وتتمايل</b>
 * (<code>bob</code>) كما في التصميم.
 *
 * <p><b>والموسَّعة</b> (بضغطةٍ عليها): تعتيمٌ خلفها، وبطاقةٌ فيها شارةُ TAXO
 * و«الفقاعة موسّعة» وحلقةُ ٤٠ في الطرف، ثم أجرةُ ٢٦، و«كاش · مسافة»، وصفَّا
 * الطريق، وزرّان: «اقبل وافتح التطبيق» بوزن ٢٫٥ و«تصغير» بوزن ١.
 *
 * <p><b>والسحبُ مبنيٌّ لأن التصميم يَعِد به نصّاً</b> — «اسحبها لأي مكان».
 * ووعدٌ مكتوبٌ لا يُنفَّذ أسوأُ من غيابه.
 *
 * <p><b>⚠ ولا تظهر فوق شاشةٍ مقفلة</b> (قرارُ المالك 2026-08-30): نُزع
 * {@code FLAG_SHOW_WHEN_LOCKED} — <b>والمقفلةُ لملء الشاشة وحدَه</b>، كما
 * تقول الشاشةُ ٠٣.
 *
 * <p><b>⚠ وهي والورقةُ السفليّةُ إذنٌ واحد</b> ({@code SYSTEM_ALERT_WINDOW}):
 * <b>رفضُه يُسقط الاثنتين معاً</b>، فلا يُقال إنّ إحداهما تنجو.
 *
 * <p><b>ولا زرَّ قبولٍ في المطويّة</b>: التصميمُ يجعل الضغطةَ توسيعاً لا
 * قبولاً — <b>وقبولُ رحلةٍ بضغطةٍ على شيءٍ يتمايل في جيبه خطأٌ ينتظر أن يقع</b>.
 */
public final class OfferBubble {

    private static View view;
    private static CountDownTimer timer;
    private static int lastLeft = 0;
    private static OfferData current;

    private OfferBubble() {}

    public static boolean showing() {
        return view != null;
    }

    public static void show(Context context, OfferData offer) {
        if (!Settings.canDrawOverlays(context)) return;
        new Handler(Looper.getMainLooper())
                .post(() -> attach(context.getApplicationContext(), offer, false));
    }

    private static void attach(Context c, OfferData offer, boolean expanded) {
        int carried = lastLeft;
        boolean resuming = view != null && current != null
                && current.rideId.equals(offer.rideId);
        detach(c, false);
        current = offer;

        WindowManager manager = c.getSystemService(WindowManager.class);
        if (manager == null) return;
        OfferPalette p = OfferPalette.of(c);

        View content = expanded ? expandedCard(c, p, offer) : collapsed(c, p, offer);
        WindowManager.LayoutParams params = expanded
                ? expandedParams(c)
                : collapsedParams(c);

        try {
            manager.addView(content, params);
            view = content;
        } catch (Exception ignored) {
            // **إذنٌ سُحب بين السؤال والرسم** — والطريقُ الثاني في `OfferAlert`
            view = null;
            return;
        }
        if (!expanded) dragging(manager, content, params);

        int start = resuming && carried > 0 ? carried : offer.seconds;
        RingView ring = content.findViewWithTag("ring");
        ring.set(start, offer.seconds);
        lastLeft = start;
        timer = new CountDownTimer(start * 1000L, 250L) {
            @Override
            public void onTick(long remaining) {
                lastLeft = (int) Math.ceil(remaining / 1000d);
                ring.set(lastLeft, offer.seconds);
            }

            @Override
            public void onFinish() {
                lastLeft = 0;
                detach(c, true);
            }
        };
        timer.start();
    }

    // ─────────────────────────────────────────────────────── المطويّة

    private static View collapsed(Context c, OfferPalette p, OfferData offer) {
        LinearLayout wrap = new LinearLayout(c);
        wrap.setOrientation(LinearLayout.VERTICAL);
        wrap.setGravity(Gravity.CENTER_HORIZONTAL);

        LinearLayout card = new LinearLayout(c);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setGravity(Gravity.CENTER_HORIZONTAL);
        card.setBackground(OfferUi.box(p.sur, p.brd, c, 22));
        card.setPadding(OfferUi.dp(c, 12), OfferUi.dp(c, 12),
                OfferUi.dp(c, 12), OfferUi.dp(c, 12));
        card.setLayoutParams(new LinearLayout.LayoutParams(
                OfferUi.dp(c, 118), LinearLayout.LayoutParams.WRAP_CONTENT));

        RingView ring = new RingView(c, p, 18f);
        ring.setTag("ring");
        LinearLayout.LayoutParams ringLp = new LinearLayout.LayoutParams(
                OfferUi.dp(c, 56), OfferUi.dp(c, 56));
        ringLp.bottomMargin = OfferUi.dp(c, 9);
        ring.setLayoutParams(ringLp);
        card.addView(ring);

        card.addView(OfferUi.text(c, offer.fare, 17f, p.tx, true));
        TextView dist = OfferUi.text(c, offer.distance, 10f, p.mut, false);
        LinearLayout.LayoutParams distLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        distLp.topMargin = OfferUi.dp(c, 3);
        dist.setLayoutParams(distLp);
        card.addView(dist);

        TextView chip = OfferUi.brandChip(c, p, 9f);
        LinearLayout.LayoutParams chipLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        chipLp.topMargin = OfferUi.dp(c, 9);
        chip.setLayoutParams(chipLp);
        card.addView(chip);
        wrap.addView(card);

        TextView hint = OfferUi.text(c, "اسحبها لأي مكان", 10f, p.mut, false);
        hint.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams hintLp = new LinearLayout.LayoutParams(
                OfferUi.dp(c, 118), LinearLayout.LayoutParams.WRAP_CONTENT);
        hintLp.topMargin = OfferUi.dp(c, 8);
        hint.setLayoutParams(hintLp);
        wrap.addView(hint);

        // **تتمايل** (`bob`) — ٥dp صعوداً وهبوطاً في ٢٫٦ ثانية، كما رُسمت
        TranslateAnimation bob = new TranslateAnimation(0, 0, 0, -OfferUi.dp(c, 5));
        bob.setDuration(1300);
        bob.setRepeatCount(Animation.INFINITE);
        bob.setRepeatMode(Animation.REVERSE);
        wrap.startAnimation(bob);
        return wrap;
    }

    private static WindowManager.LayoutParams collapsedParams(Context c) {
        WindowManager.LayoutParams params = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.WRAP_CONTENT,
                overlayType(),
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                        | WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL,
                PixelFormat.TRANSLUCENT);
        params.gravity = Gravity.TOP | Gravity.START;
        params.x = OfferUi.dp(c, 16);
        params.y = OfferUi.dp(c, 214);
        return params;
    }

    // ─────────────────────────────────────────────────────── الموسَّعة

    private static View expandedCard(Context c, OfferPalette p, OfferData offer) {
        FrameLayout root = new FrameLayout(c);
        root.setBackgroundColor(p.dim);
        AlphaAnimation fade = new AlphaAnimation(0f, 1f);
        fade.setDuration(200);
        root.startAnimation(fade);

        LinearLayout card = new LinearLayout(c);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setBackground(OfferUi.box(p.sur, p.brd, c, 26));
        card.setPadding(OfferUi.dp(c, 18), OfferUi.dp(c, 18),
                OfferUi.dp(c, 18), OfferUi.dp(c, 18));
        FrameLayout.LayoutParams cardLp = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.WRAP_CONTENT);
        cardLp.setMargins(OfferUi.dp(c, 14), OfferUi.dp(c, 150), OfferUi.dp(c, 14), 0);
        card.setLayoutParams(cardLp);

        LinearLayout head = new LinearLayout(c);
        head.setOrientation(LinearLayout.HORIZONTAL);
        head.setGravity(Gravity.CENTER_VERTICAL);
        head.addView(OfferUi.brandChip(c, p, 10.5f));
        TextView title = OfferUi.text(c, "الفقاعة موسّعة", 11.5f, p.mut, true);
        LinearLayout.LayoutParams titleLp = new LinearLayout.LayoutParams(
                0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f);
        titleLp.setMarginStart(OfferUi.dp(c, 9));
        title.setLayoutParams(titleLp);
        head.addView(title);
        RingView ring = new RingView(c, p, 14f);
        ring.setTag("ring");
        ring.setLayoutParams(new LinearLayout.LayoutParams(
                OfferUi.dp(c, 40), OfferUi.dp(c, 40)));
        head.addView(ring);
        LinearLayout.LayoutParams headLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        headLp.bottomMargin = OfferUi.dp(c, 15);
        head.setLayoutParams(headLp);
        card.addView(head);

        card.addView(OfferUi.fare(c, p, offer, 26f, 12f));
        TextView meta = OfferUi.text(c, offer.meta(false), 11.5f, p.mut, false);
        LinearLayout.LayoutParams metaLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        metaLp.topMargin = OfferUi.dp(c, 3);
        metaLp.bottomMargin = OfferUi.dp(c, 15);
        meta.setLayoutParams(metaLp);
        card.addView(meta);

        LinearLayout route = OfferUi.route(c, p, offer.pickup, offer.drop, 13f);
        LinearLayout.LayoutParams routeLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        routeLp.bottomMargin = OfferUi.dp(c, 17);
        route.setLayoutParams(routeLp);
        card.addView(route);

        LinearLayout actions = new LinearLayout(c);
        actions.setOrientation(LinearLayout.HORIZONTAL);
        actions.addView(pill(c, p, "اقبل وافتح التطبيق", true, 2.5f, v -> {
            detach(c, false);
            OfferApi.accept(c, offer.rideId, ok -> {});
        }));
        actions.addView(pill(c, p, "تصغير", false, 1f,
                v -> attach(c, offer, false)));
        card.addView(actions);

        root.addView(card);
        ScaleAnimation pop = new ScaleAnimation(
                .94f, 1f, .94f, 1f,
                Animation.RELATIVE_TO_SELF, .5f, Animation.RELATIVE_TO_SELF, .5f);
        pop.setDuration(250);
        AnimationSet set = new AnimationSet(true);
        set.addAnimation(pop);
        card.startAnimation(set);
        return root;
    }

    private static WindowManager.LayoutParams expandedParams(Context c) {
        return new WindowManager.LayoutParams(
                WindowManager.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.MATCH_PARENT,
                overlayType(),
                WindowManager.LayoutParams.FLAG_WATCH_OUTSIDE_TOUCH,
                PixelFormat.TRANSLUCENT);
    }

    private static TextView pill(
            Context c, OfferPalette p, String label, boolean primary,
            float weight, View.OnClickListener onClick
    ) {
        TextView button = OfferUi.text(
                c, label, primary ? 14.5f : 13f, primary ? p.inv : p.mut, primary);
        button.setGravity(Gravity.CENTER);
        button.setPadding(0, OfferUi.dp(c, 15), 0, OfferUi.dp(c, 15));
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

    // ─────────────────────────────────────────────────────── السحب

    /**
     * «اسحبها لأي مكان» — <b>وعدُ التصميم منفَّذاً</b>.
     *
     * <p><b>والفرقُ بين سحبٍ وضغطة يُقاس بالمسافة لا بالزمن</b>: إصبعٌ يتحرّك
     * أقلَّ من عتبة اللمس ضغطةٌ توسّع، وما فوقها سحبٌ ينقل — <b>وبلا هذا
     * الفصل يوسّعها كلُّ سحبٍ فتُغطّى الشاشة</b>.
     */
    private static void dragging(
            WindowManager manager, View target, WindowManager.LayoutParams params
    ) {
        final int slop = OfferUi.dp(target.getContext(), 8);
        target.setOnTouchListener(new View.OnTouchListener() {
            float downX, downY;
            int startX, startY;
            boolean moved;

            @Override
            public boolean onTouch(View v, MotionEvent event) {
                switch (event.getAction()) {
                    case MotionEvent.ACTION_DOWN:
                        downX = event.getRawX();
                        downY = event.getRawY();
                        startX = params.x;
                        startY = params.y;
                        moved = false;
                        return true;
                    case MotionEvent.ACTION_MOVE: {
                        int dx = Math.round(event.getRawX() - downX);
                        int dy = Math.round(event.getRawY() - downY);
                        if (Math.abs(dx) > slop || Math.abs(dy) > slop) moved = true;
                        if (moved) {
                            params.x = startX + dx;
                            params.y = startY + dy;
                            try {
                                manager.updateViewLayout(target, params);
                            } catch (Exception ignored) {
                                // نافذةٌ أُزيلت أثناء السحب
                            }
                        }
                        return true;
                    }
                    case MotionEvent.ACTION_UP:
                        if (!moved && current != null) {
                            attach(v.getContext().getApplicationContext(), current, true);
                        }
                        return true;
                    default:
                        return false;
                }
            }
        });
    }

    // ─────────────────────────────────────────────────────── الطيّ

    private static int overlayType() {
        return Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
                ? WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
                : WindowManager.LayoutParams.TYPE_PHONE;
    }

    public static void hide(Context context) {
        new Handler(Looper.getMainLooper())
                .post(() -> detach(context.getApplicationContext(), true));
    }

    private static void detach(Context c, boolean forget) {
        if (timer != null) {
            timer.cancel();
            timer = null;
        }
        if (view != null) {
            WindowManager manager = c.getSystemService(WindowManager.class);
            try {
                if (manager != null) manager.removeView(view);
            } catch (Exception ignored) {
                // أُزيلت من تحتنا
            }
            view = null;
        }
        if (forget) {
            current = null;
            lastLeft = 0;
        }
    }
}
