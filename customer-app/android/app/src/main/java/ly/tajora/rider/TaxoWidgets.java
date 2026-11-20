package ly.tajora.rider;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.view.View;
import android.widget.RemoteViews;

import org.json.JSONArray;
import org.json.JSONObject;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/**
 * <b>ودجاتُ الراكب الأربعَ عشرة</b> (أمرُ المالك ٢٠٢٦-١١-٢٠ الثامن؛ «المنزل» و«العمل» نوعان فهي خمسةَ عشرَ مزوّداً).
 *
 * <p><b>ترسم ولا تحسب</b>: ما تعرضه كتبه الويب في {@code w_feed} من أبوابه الحقيقيّة (`lib/widget-feed.ts`)، والرحلةُ الحيّةُ في
 * {@code rider_ride} كما تكتبها الفقاعة. <b>لا رقمَ مخترَع</b> — ما لا قيمةَ له حالٌ فارغةٌ تقول ذلك، <b>ولا رحلةَ من الودجة</b>: كلُّ زرٍّ
 * يفتح التطبيق، والراكبُ يؤكّد في ورقة الطلب. <b>ولا رقمَ هاتف</b>.
 *
 * <p><b>والمستخدمون الحاليّون لا يرون شيئاً جديداً</b> حتى يشتعل {@code rider_widgets_plus} لبلدهم: المزوّداتُ مطفأةٌ في البيان
 * ({@code android:enabled="false"}) و{@link #sync} يُظهر في المنتقي ما في {@code w_kinds} وحدَه — <b>ولا يُخفي ما وضعه الراكبُ على
 * شاشته</b> (إطفاءُ مزوّدٍ له ودجةٌ قائمةٌ يتركها «تعذّر التحميل»)، بل يرسمها فارغةً بأدب.
 *
 * <p>وتتحدّث حين يتغيّر الحال لا بمؤقّت ({@code updatePeriodMillis=0}) — البطاريّة. والزجاجُ تدرّجاتٌ وطبقاتٌ بلا blur.
 */
public final class TaxoWidgets {
    private TaxoWidgets() {}

    static final String[] KINDS = {
        "request", "on_the_way", "quick", "favorites", "wallet", "discount", "schedule", "services",
        "current", "home", "work", "points", "recent", "offers", "nearest",
    };

    /** أقدمُ من هذا لا يُعرض «أقربُ سائق» رقماً — يُقال «افتح التطبيق لتحديثه» (ربعُ ساعة). */
    static final long NEAREST_FRESH_MS = 15 * 60_000L;

    static Class<?> provider(String kind) {
        switch (kind) {
            case "request": return Request.class;
            case "on_the_way": return OnTheWay.class;
            case "quick": return Quick.class;
            case "favorites": return Favorites.class;
            case "wallet": return Wallet.class;
            case "discount": return Discount.class;
            case "schedule": return Schedule.class;
            case "services": return Services.class;
            case "current": return Current.class;
            case "home": return Home.class;
            case "work": return Work.class;
            case "points": return Points.class;
            case "recent": return Recent.class;
            case "offers": return Offers.class;
            default: return Nearest.class;
        }
    }

    /** <b>ما يظهر في منتقي الودجات</b> — من {@code w_kinds}؛ <b>وما له ودجةٌ قائمةٌ يبقى</b>. ثم يُرسم كلُّ ما على الشاشة. */
    public static void sync(Context ctx) {
        SharedPreferences p = ctx.getSharedPreferences(LauncherPlugin.PREFS, Context.MODE_PRIVATE);
        String raw = p.getString("w_kinds", "[]");
        PackageManager pm = ctx.getPackageManager();
        AppWidgetManager manager = AppWidgetManager.getInstance(ctx);
        for (String kind : KINDS) {
            ComponentName name = new ComponentName(ctx, provider(kind));
            int[] ids = new int[0];
            try {
                ids = manager.getAppWidgetIds(name);
            } catch (Exception ignored) {
                // المزوّدُ مطفأ — لا ودجاتٍ له
            }
            boolean want = listed(raw, kind) || ids.length > 0;
            int state = want ? PackageManager.COMPONENT_ENABLED_STATE_ENABLED : PackageManager.COMPONENT_ENABLED_STATE_DEFAULT;
            if (pm.getComponentEnabledSetting(name) != state) {
                pm.setComponentEnabledSetting(name, state, PackageManager.DONT_KILL_APP);
            }
            for (int id : ids) manager.updateAppWidget(id, render(ctx, kind, manager.getAppWidgetOptions(id)));
        }
    }

    /** خالصة: أفي القائمة؟ */
    static boolean listed(String json, String kind) {
        try {
            JSONArray list = new JSONArray(json == null ? "[]" : json);
            for (int i = 0; i < list.length(); i++) if (kind.equals(list.optString(i))) return true;
        } catch (Exception ignored) {
            // قائمةٌ تالفةٌ = فارغة
        }
        return false;
    }

    /** خالصة: {@code 0} صغيرة · {@code 1} متوسّطة · {@code 2} كبيرة — من أبعاد الودجة بالـdp. */
    static int sizeClass(int widthDp, int heightDp) {
        if (heightDp >= 170 && widthDp >= 250) return 2;
        if (widthDp >= 230) return 1;
        return 0;
    }

    private static PendingIntent open(Context ctx, String action, int code) {
        Intent intent = new Intent(ctx, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        if (action != null) intent.putExtra(LauncherPlugin.EXTRA, action);
        return PendingIntent.getActivity(ctx, code, intent, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    private static int code(String kind, int slot) {
        for (int i = 0; i < KINDS.length; i++) if (KINDS[i].equals(kind)) return 3100 + i * 10 + slot;
        return 3099;
    }

    static int car(String key) {
        switch (key == null ? "" : key) {
            case "comfort": return R.drawable.tw_car_comfort;
            case "vip": return R.drawable.tw_car_vip;
            case "hatchback": return R.drawable.tw_car_hatchback;
            case "suv": return R.drawable.tw_car_suv;
            case "family": return R.drawable.tw_car_family;
            case "van": return R.drawable.tw_car_van;
            case "city_taxi": return R.drawable.tw_car_city_taxi;
            case "women": return R.drawable.tw_car_women;
            default: return key != null && key.contains("women") ? R.drawable.tw_car_women : R.drawable.tw_car_economy;
        }
    }

    /** رسمُ بلاطةِ خدمةٍ من مسارها — الخدماتُ يكتبها المشرف، والرسمُ من نمط TAXO لا من أيقونة lucide. */
    static int serviceGlyph(String path) {
        String go = path == null ? "" : path;
        if (go.startsWith("/account/intercity")) return R.drawable.tw_g_directions_car;
        if (go.startsWith("/account/women")) return R.drawable.tw_g_woman;
        if (go.startsWith("/account/bookings")) return R.drawable.tw_g_schedule;
        if (go.startsWith("/account/commute")) return R.drawable.tw_g_history;
        if (go.startsWith("/wallet")) return R.drawable.tw_g_account_balance_wallet;
        if (go.startsWith("/loyalty")) return R.drawable.tw_g_star;
        if (go.startsWith("/plans")) return R.drawable.tw_g_receipt_long;
        if (go.startsWith("/account/referrals")) return R.drawable.tw_g_redeem;
        return R.drawable.tw_g_local_taxi;
    }

    private static final int[] TILE = {R.id.tw_t0, R.id.tw_t1, R.id.tw_t2, R.id.tw_t3};
    private static final int[] TILE_ICON = {R.id.tw_t0i, R.id.tw_t1i, R.id.tw_t2i, R.id.tw_t3i};
    private static final int[] TILE_LABEL = {R.id.tw_t0l, R.id.tw_t1l, R.id.tw_t2l, R.id.tw_t3l};

    static String hhmm(long ms) {
        return new SimpleDateFormat("HH:mm", Locale.US).format(new Date(ms));
    }

    static JSONObject json(SharedPreferences p, String key) {
        String raw = p.getString(key, null);
        if (raw == null) return null;
        try {
            return new JSONObject(raw);
        } catch (Exception e) {
            return null;
        }
    }

    /** أداةُ رسمٍ صغيرة: تُظهر ما يُكتب فيه وتُخفي ما سواه — <b>فلا يبقى نصُّ نوعٍ في ودجة نوعٍ آخر</b>. */
    static final class Card {
        final Context ctx;
        final RemoteViews v;
        final String kind;

        Card(Context ctx, String kind) {
            this.ctx = ctx;
            this.kind = kind;
            v = new RemoteViews(ctx.getPackageName(), R.layout.tw_widget);
            int[] hidden = {R.id.tw_car, R.id.tw_car_s, R.id.tw_art, R.id.tw_dot, R.id.tw_mark, R.id.tw_icon, R.id.tw_bigrow, R.id.tw_sub,
                    R.id.tw_tiles, R.id.tw_actions, R.id.tw_btn, R.id.tw_btn2, R.id.tw_bar, R.id.tw_ringbox, R.id.tw_quick, R.id.tw_place,
                    R.id.wo_root};
            for (int id : hidden) v.setViewVisibility(id, View.GONE);
            v.setViewVisibility(R.id.tw_body, View.VISIBLE);
            v.setViewVisibility(R.id.tw_fill, View.VISIBLE);
            for (int id : TILE) v.setViewVisibility(id, View.GONE);
            v.setTextViewText(R.id.tw_title, "");
        }

        Card title(String text) { v.setTextViewText(R.id.tw_title, text); return this; }
        Card mark() { v.setViewVisibility(R.id.tw_mark, View.VISIBLE); return this; }
        Card dot(boolean live) {
            v.setViewVisibility(R.id.tw_dot, View.VISIBLE);
            v.setImageViewResource(R.id.tw_dot, live ? R.drawable.tw_dot_ok : R.drawable.tw_dot);
            return this;
        }
        Card icon(int res) { v.setViewVisibility(R.id.tw_icon, View.VISIBLE); v.setImageViewResource(R.id.tw_icon, res); return this; }
        Card big(String value, String unit) {
            v.setViewVisibility(R.id.tw_bigrow, View.VISIBLE);
            v.setTextViewText(R.id.tw_big, value);
            v.setTextViewText(R.id.tw_unit, unit == null ? "" : unit);
            return this;
        }
        Card sub(String text) {
            if (text == null || text.isEmpty()) return this;
            v.setViewVisibility(R.id.tw_sub, View.VISIBLE);
            v.setTextViewText(R.id.tw_sub, text);
            return this;
        }
        Card car(String key, boolean small) {
            int id = small ? R.id.tw_car_s : R.id.tw_car;
            v.setViewVisibility(id, View.VISIBLE);
            v.setImageViewResource(id, TaxoWidgets.car(key));
            return this;
        }
        Card art(int res) { v.setViewVisibility(R.id.tw_art, View.VISIBLE); v.setImageViewResource(R.id.tw_art, res); return this; }
        Card button(String text, String action, int slot) {
            v.setViewVisibility(R.id.tw_actions, View.VISIBLE);
            v.setViewVisibility(R.id.tw_btn, View.VISIBLE);
            v.setTextViewText(R.id.tw_btn, text);
            v.setOnClickPendingIntent(R.id.tw_btn, open(ctx, action, code(kind, slot)));
            return this;
        }
        Card button2(String text, String action, int slot) {
            v.setViewVisibility(R.id.tw_actions, View.VISIBLE);
            v.setViewVisibility(R.id.tw_btn2, View.VISIBLE);
            v.setTextViewText(R.id.tw_btn2, text);
            v.setOnClickPendingIntent(R.id.tw_btn2, open(ctx, action, code(kind, slot)));
            return this;
        }
        Card bar(float value) {
            v.setViewVisibility(R.id.tw_bar, View.VISIBLE);
            v.setProgressBar(R.id.tw_bar, 100, Math.round(Math.max(0f, Math.min(1f, value)) * 100), false);
            return this;
        }
        Card tile(int i, int glyph, String label, String action) {
            v.setViewVisibility(R.id.tw_tiles, View.VISIBLE);
            v.setViewVisibility(R.id.tw_fill, View.GONE);
            v.setViewVisibility(TILE[i], View.VISIBLE);
            v.setImageViewResource(TILE_ICON[i], glyph);
            v.setTextViewText(TILE_LABEL[i], label);
            v.setOnClickPendingIntent(TILE[i], open(ctx, action, code(kind, 4 + i)));
            return this;
        }
        Card tap(String action) { v.setOnClickPendingIntent(R.id.tw_root, open(ctx, action, code(kind, 0))); return this; }
    }

    static RemoteViews render(Context ctx, String kind, Bundle options) {
        SharedPreferences p = ctx.getSharedPreferences(LauncherPlugin.PREFS, Context.MODE_PRIVATE);
        int w = options == null ? 250 : options.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 250);
        int h = WidgetSignedOut.heightDp(ctx, options, 110);
        int size = sizeClass(w, h);
        Card c = new Card(ctx, kind);
        c.tap(null);
        if (!p.getBoolean("rider_widgets_plus", false)) {
            // **المفتاحُ أُطفئ لبلده والودجةُ على شاشته** — بطاقةُ TAXO بسطرٍ صادقٍ لا بياناتٌ قديمة
            c.v.setViewVisibility(R.id.tw_body, View.GONE);
            c.v.setViewVisibility(R.id.wo_root, View.VISIBLE);
            WidgetSignedOut.show(ctx, c.v, h, "هذه الودجة غير متاحة الآن", "افتح TAXO", open(ctx, null, code(kind, 9)));
            return c.v;
        }
        if (!p.getBoolean("signed_in", false)) {
            c.v.setViewVisibility(R.id.tw_body, View.GONE);
            c.v.setViewVisibility(R.id.wo_root, View.VISIBLE);
            WidgetSignedOut.show(ctx, c.v, h, "سجّل الدخول لتطلب رحلتك بلمسة", "سجّل الدخول", open(ctx, null, code(kind, 9)));
            return c.v;
        }
        JSONObject feed = json(p, "w_feed");
        JSONObject ride = RiderBubble.ride(p);
        String phase = ride == null ? "" : ride.optString("phase");
        long at = feed == null ? 0 : feed.optLong("at", 0);
        String until = at > 0 ? "حتى " + hhmm(at) : "افتح التطبيق لتحديثها";
        switch (kind) {
            case "request":
                c.mark().title("").sub("اطلب مشوارك الآن — بكل سهولة وأمان").button("إلى أين؟", "where_to", 1).tap("where_to");
                if (size > 0) c.car("economy", false);
                break;
            case "quick":
                c.v.setViewVisibility(R.id.tw_body, View.GONE);
                c.v.setViewVisibility(R.id.tw_quick, View.VISIBLE);
                c.v.setOnClickPendingIntent(R.id.tw_qbtn, open(ctx, "where_to", code(kind, 1)));
                c.tap("where_to");
                break;
            case "on_the_way":
            case "current":
                renderRide(c, kind, ride, phase, size);
                break;
            case "favorites":
                c.title("وجهاتك المفضلة").icon(R.drawable.tw_g_star)
                        .tile(0, R.drawable.tw_g_home, "المنزل", "ride_home")
                        .tile(1, R.drawable.tw_g_work, "العمل", "ride_work")
                        .tile(2, R.drawable.tw_g_location_on, "عرض الكل", "go:/account/places");
                break;
            case "home":
            case "work":
                renderPlace(c, kind, p);
                break;
            case "wallet": {
                JSONObject wallet = feed == null ? null : feed.optJSONObject("wallet");
                c.title("محفظتي").icon(R.drawable.tw_g_account_balance_wallet).tap("wallet");
                if (wallet != null) c.big(wallet.optString("amount"), wallet.optString("unit")).sub(until);
                else c.sub("افتح التطبيق لترى رصيدك");
                c.button("شحن الرصيد", "topup", 1);
                break;
            }
            case "discount":
            case "offers": {
                JSONObject offers = feed == null ? null : feed.optJSONObject("offers");
                int count = offers == null ? 0 : offers.optInt("count", 0);
                boolean special = "discount".equals(kind);
                c.title(special ? "خصم خاص" : "العروض والخصومات").icon(R.drawable.tw_g_sell);
                if (count == 0) {
                    c.sub("لا عروض الآن — نُعلمك حين يصل عرضٌ جديد");
                } else if (special) {
                    String headline = offers.optString("headline", "");
                    if (!headline.isEmpty() && !"null".equals(headline)) c.big(headline, null);
                    c.sub(offers.optString("title", "")).button("اعرف المزيد", null, 1);
                } else {
                    c.big(String.valueOf(count), count == 1 ? "عرض" : "عروض").sub(offers.optString("title", "")).button("تصفّح العروض", null, 1);
                }
                if (size > 0) c.art(R.drawable.tw_g_redeem);
                break;
            }
            case "schedule": {
                JSONObject booking = feed == null ? null : feed.optJSONObject("booking");
                c.title("حجز مسبق").icon(R.drawable.tw_g_schedule).tap("bookings");
                if (booking != null) {
                    String to = booking.optString("to", "");
                    c.big(booking.optString("when"), null).sub(to.isEmpty() ? "رحلتك القادمة" : "إلى " + to);
                } else {
                    c.sub("لا حجوزات قادمة");
                }
                c.button("احجز رحلة", "bookings", 1);
                break;
            }
            case "services": {
                JSONArray list = feed == null ? null : feed.optJSONArray("services");
                c.title("خدمات التنقّل السريع");
                int n = list == null ? 0 : Math.min(list.length(), size == 0 ? 2 : 4);
                for (int i = 0; i < n; i++) {
                    JSONObject tile = list.optJSONObject(i);
                    if (tile == null) continue;
                    String go = tile.optString("go", "/");
                    c.tile(i, serviceGlyph(go), tile.optString("title"), "go:" + go);
                }
                if (n == 0) c.sub("لا خدمات متاحة الآن");
                break;
            }
            case "points": {
                JSONObject points = feed == null ? null : feed.optJSONObject("points");
                c.tap("loyalty");
                if (points == null) {
                    c.title("نقاطي").icon(R.drawable.tw_g_star).sub("النقاط غير متاحة الآن");
                } else {
                    c.v.setViewVisibility(R.id.tw_body, View.GONE);
                    c.v.setViewVisibility(R.id.tw_ringbox, View.VISIBLE);
                    c.v.setProgressBar(R.id.tw_ring, 100, (int) Math.round(points.optDouble("pct", 0) * 100), false);
                    c.v.setTextViewText(R.id.tw_ring_big, points.optString("points"));
                    c.v.setTextViewText(R.id.tw_ring_sub, points.optString("tier"));
                }
                break;
            }
            case "recent": {
                JSONObject last = feed == null ? null : feed.optJSONObject("last");
                c.title("آخر رحلاتي").icon(R.drawable.tw_g_history).tap("rides");
                if (last == null) {
                    c.sub("لا رحلات بعد — رحلتك الأولى تظهر هنا");
                    c.button("اطلب رحلة", "where_to", 1);
                } else {
                    String to = last.optString("to", "");
                    c.sub((to.isEmpty() ? "" : "إلى " + to + " · ") + last.optString("when"));
                    if (size > 0) c.car(last.optString("car"), true);
                    // **«اطلبها مرة أخرى» يفتح ورقةَ الطلب بالوجهة للتأكيد** — الفعلُ نفسُه الذي تستعمله ودجةُ الوجهات الأخيرة
                    if (hasRecent(p)) c.button("اطلبها مرة أخرى", "recent_0", 1);
                    if (size > 0) c.button2("كل الرحلات", "rides", 2);
                }
                break;
            }
            default: { // nearest
                c.title("أقرب سائق متاح").icon(R.drawable.tw_g_my_location).tap("where_to");
                boolean fresh = at > 0 && System.currentTimeMillis() - at <= NEAREST_FRESH_MS;
                int minutes = feed == null || feed.isNull("nearest") ? -1 : feed.optInt("nearest", -1);
                if (!fresh) c.sub("افتح التطبيق لنعرف أقربَ سائقٍ إليك");
                else if (minutes < 0) c.sub("لا سائق متاحٌ قريباً الآن");
                else c.big(String.valueOf(Math.max(1, minutes)), "دقائق").sub(until);
                if (size > 0) c.car("economy", true);
                c.button("اطلب الآن", "where_to", 1);
                break;
            }
        }
        return c.v;
    }

    static boolean hasRecent(SharedPreferences p) {
        try {
            return new JSONArray(p.getString("rider_recent", "[]")).length() > 0;
        } catch (Exception e) {
            return false;
        }
    }

    /** «السائق في الطريق» و«رحلتي الحالية» — <b>أثناء رحلةٍ حقيقيّةٍ وحدَها</b>؛ الاسمُ الأوّلُ واللوحةُ والتقييم، <b>ولا هاتف</b>. */
    static void renderRide(Card c, String kind, JSONObject ride, String phase, int size) {
        boolean onTheWay = "on_the_way".equals(kind);
        boolean live = ride != null && RiderBubbleLogic.showsFor(phase);
        c.title(onTheWay ? "السائق في الطريق" : "رحلتي الحالية");
        if (!live) {
            c.sub(onTheWay ? "يظهر سائقك هنا حين تطلب رحلة" : "لا رحلة الآن").button("اطلب رحلة", "where_to", 1).tap("where_to");
            return;
        }
        c.dot(true);
        String driver = ride.optString("driver", "");
        String plate = ride.optString("plate", "");
        String rating = ride.optString("rating", "");
        int eta = ride.optInt("eta_min", -1);
        if ("searching".equals(phase)) {
            c.sub("نبحث لك عن سائق…");
        } else if ("assigned".equals(phase)) {
            if (eta >= 0) c.big(String.valueOf(Math.max(1, eta)), "دقيقة");
            c.bar(RiderBubbleLogic.approach(phase, eta, ride.optInt("eta_first", -1)));
        } else if ("arrived".equals(phase)) {
            c.sub("وصل السائق — بانتظارك");
        } else {
            c.sub("في الطريق إلى وجهتك");
        }
        StringBuilder line = new StringBuilder(driver.isEmpty() ? "السائق" : driver);
        if (!rating.isEmpty()) line.append(" · ★ ").append(rating);
        if (!plate.isEmpty()) line.append(" · ").append(plate);
        if (!"searching".equals(phase)) c.sub(line.toString());
        if (size > 0) c.car(ride.optString("cat", "economy"), true);
    }

    static void renderPlace(Card c, String kind, SharedPreferences p) {
        boolean home = "home".equals(kind);
        JSONObject places = json(p, "rider_places");
        boolean saved = places != null && places.optBoolean(home ? "home" : "work", false);
        c.v.setViewVisibility(R.id.tw_body, View.GONE);
        c.v.setViewVisibility(R.id.tw_place, View.VISIBLE);
        c.v.setImageViewResource(R.id.tw_place_icon, home ? R.drawable.tw_g_home : R.drawable.tw_g_work);
        c.v.setTextViewText(R.id.tw_place_name, home ? "المنزل" : "العمل");
        c.v.setTextViewText(R.id.tw_place_sub, saved ? "اطلب رحلة" : "أضفه من أماكني");
        c.tap(home ? "ride_home" : "ride_work");
    }

    /** الأصلُ المشترك: يرسم كلَّ ودجةٍ من نوعه حين يُطلب، ويستيقظ على {@code LAUNCHER_CHANGED}. */
    public abstract static class Base extends AppWidgetProvider {
        abstract String kind();

        @Override
        public void onUpdate(Context ctx, AppWidgetManager manager, int[] ids) {
            for (int id : ids) manager.updateAppWidget(id, render(ctx, kind(), manager.getAppWidgetOptions(id)));
        }

        @Override
        public void onAppWidgetOptionsChanged(Context ctx, AppWidgetManager manager, int id, Bundle options) {
            manager.updateAppWidget(id, render(ctx, kind(), options));
        }

        @Override
        public void onReceive(Context ctx, Intent intent) {
            super.onReceive(ctx, intent);
            if (LauncherPlugin.CHANGED.equals(intent.getAction())) {
                AppWidgetManager manager = AppWidgetManager.getInstance(ctx);
                onUpdate(ctx, manager, manager.getAppWidgetIds(new ComponentName(ctx, getClass())));
            }
        }
    }

    public static final class Request extends Base { String kind() { return "request"; } }
    public static final class OnTheWay extends Base { String kind() { return "on_the_way"; } }
    public static final class Quick extends Base { String kind() { return "quick"; } }
    public static final class Favorites extends Base { String kind() { return "favorites"; } }
    public static final class Wallet extends Base { String kind() { return "wallet"; } }
    public static final class Discount extends Base { String kind() { return "discount"; } }
    public static final class Schedule extends Base { String kind() { return "schedule"; } }
    public static final class Services extends Base { String kind() { return "services"; } }
    public static final class Current extends Base { String kind() { return "current"; } }
    public static final class Home extends Base { String kind() { return "home"; } }
    public static final class Work extends Base { String kind() { return "work"; } }
    public static final class Points extends Base { String kind() { return "points"; } }
    public static final class Recent extends Base { String kind() { return "recent"; } }
    public static final class Offers extends Base { String kind() { return "offers"; } }
    public static final class Nearest extends Base { String kind() { return "nearest"; } }
}
