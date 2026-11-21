package ly.tajora.rider;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.content.res.Configuration;
import android.graphics.Bitmap;
import android.graphics.drawable.Icon;
import android.os.Build;
import android.os.Bundle;
import android.util.ArrayMap;
import android.util.SizeF;
import android.view.View;
import android.widget.RemoteViews;

import org.json.JSONArray;
import org.json.JSONObject;

import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.Map;

/**
 * <b>ودجاتُ الراكب</b> (أمرُ المالك ٢٠٢٦-١١-٢٠ الثامن؛ وأُعيد تصميمُها ٢١/١١ على صورته المرجعيّة: عنوانٌ واضح، وسيارةُ TAXO كبيرة،
 * وبطاقاتٌ زجاجيّةٌ بلمسةٍ برتقاليّة، وأزرارُ الأماكن مستديرة، <b>ولا فراغ في أيِّ حجم</b>).
 *
 * <p><b>تخطيطٌ لكلِّ نوعٍ ولكلِّ حجم</b> ({@link TwLayouts}، مولَّدٌ من {@code tools/gen-android-widgets.py})، وعلى أندرويد ١٢+ تُسلَّم
 * الثلاثةُ معاً فيختار المشغِّلُ ما يناسب المقاس بلا انتظار. <b>والمعاينةُ في المنتقي هي التخطيطُ نفسُه</b> ({@code previewLayout}).
 *
 * <p><b>ترسم ولا تحسب</b>: ما تعرضه كتبه الويب في {@code w_feed} من أبوابه الحقيقيّة (`lib/widget-feed.ts`)، والرحلةُ الحيّةُ في
 * {@code rider_ride} كما تكتبها الفقاعة، ومسارُها في {@code rider_ride_route} وصورةُ السائق المعتمدة في {@code rider_ride_photo}.
 * <b>لا رقمَ مخترَع</b> — ما لا قيمةَ له حالٌ فارغةٌ تقول ذلك، <b>ولا رحلةَ من الودجة</b>: كلُّ زرٍّ يفتح التطبيق والراكبُ يؤكّد.
 * <b>ولا رقمَ هاتف</b>، <b>وصورةُ السائق أثناء الرحلة وحدَها</b>.
 *
 * <p><b>والمستخدمون الحاليّون لا يرون شيئاً جديداً</b> حتى يشتعل {@code rider_widgets_plus} لبلدهم: المزوّداتُ مطفأةٌ في البيان و{@link #sync}
 * يُظهر في المنتقي ما في {@code w_kinds} وحدَه — ولا يُخفي ما وضعه الراكبُ على شاشته بل يرسمها بسطرٍ صادق.
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
            for (int id : ids) manager.updateAppWidget(id, views(ctx, kind, manager.getAppWidgetOptions(id)));
        }
        legacy(ctx, pm, manager, RiderQuickWidget.class);
    }

    /** <b>ودجةٌ قديمةٌ ترسمها ودجةٌ جديدة</b> (٢١/١١): تبقى ما دامت لها نسخةٌ موضوعة، وتُخفى من المنتقي وإلا — فلا تتكرّر فيه. */
    static void legacy(Context ctx, PackageManager pm, AppWidgetManager manager, Class<?> cls) {
        ComponentName name = new ComponentName(ctx, cls);
        int[] ids = new int[0];
        try {
            ids = manager.getAppWidgetIds(name);
        } catch (Exception ignored) {
            // مطفأة — لا نسخ
        }
        int state = ids.length > 0 ? PackageManager.COMPONENT_ENABLED_STATE_DEFAULT : PackageManager.COMPONENT_ENABLED_STATE_DISABLED;
        if (pm.getComponentEnabledSetting(name) != state) pm.setComponentEnabledSetting(name, state, PackageManager.DONT_KILL_APP);
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

    /** خالصة: {@code 0} صغيرة · {@code 1} متوسّطة · {@code 2} كبيرة — من أبعاد الودجة بالـdp (ما قبل أندرويد ١٢). */
    static int sizeClass(int widthDp, int heightDp) {
        if (heightDp >= 260 && widthDp >= 250) return 2;
        if (widthDp >= 230) return 1;
        return 0;
    }

    /** خالصة: «عرضٌ واحد» · «عرضان» · «٣ عروض» · «١١ عرضاً» — العددُ كما يُقال. */
    static String offersLine(int count) {
        if (count <= 0) return "لا عروض الآن";
        if (count == 1) return "عرضٌ واحد متاح";
        if (count == 2) return "عرضان متاحان";
        if (count <= 10) return count + " عروض متاحة";
        return count + " عرضاً متاحاً";
    }

    /** خالصة: «دقيقة» للواحد والأحد عشر فما فوق، و«دقائق» من ٢ إلى ١٠. */
    static String minutesUnit(int n) {
        return n >= 2 && n <= 10 ? "دقائق" : "دقيقة";
    }

    /** الثلاثةُ معاً على أندرويد ١٢+ (يختار المشغِّل)، وواحدٌ بالمقاس قبله. */
    static RemoteViews views(Context ctx, String kind, Bundle options) {
        if (Build.VERSION.SDK_INT >= 31) {
            Map<SizeF, RemoteViews> map = new ArrayMap<>();
            map.put(new SizeF(100f, 100f), render(ctx, kind, 0));
            map.put(new SizeF(230f, 100f), render(ctx, kind, 1));
            // **الكبيرةُ من 4×3** (قِيس على المحاكي ٢١/١١): 4×2 في Pixel 7 نحوُ 373×200dp، فعتبةُ 200 أعطته الكبيرةَ فقُصّ زرُّها
            map.put(new SizeF(230f, 260f), render(ctx, kind, 2));
            return new RemoteViews(map);
        }
        int w = options == null ? 250 : options.getInt(AppWidgetManager.OPTION_APPWIDGET_MIN_WIDTH, 250);
        int h = WidgetSignedOut.heightDp(ctx, options, 110);
        return render(ctx, kind, sizeClass(w, h));
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
    private static final int[] ROW = {R.id.tw_r0, R.id.tw_r1, R.id.tw_r2};
    private static final int[] ROW_LABEL = {R.id.tw_r0l, R.id.tw_r1l, R.id.tw_r2l};

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

    /** أداةُ رسمٍ صغيرة على تخطيط النوع والحجم. <b>والمعرّفُ الغائبُ عن تخطيطٍ يُتجاوَز</b> (RemoteViews يتركه بلا خطأ). */
    static final class W {
        final Context ctx;
        final RemoteViews v;
        final String kind;
        final int size;

        W(Context ctx, String kind, int size) {
            this.ctx = ctx;
            this.kind = kind;
            this.size = size;
            v = new RemoteViews(ctx.getPackageName(), TwLayouts.of(kind, size));
        }

        W text(int id, String s) { v.setTextViewText(id, s == null ? "" : s); return this; }
        W show(int id, boolean on) { v.setViewVisibility(id, on ? View.VISIBLE : View.GONE); return this; }
        W img(int id, int res) { v.setImageViewResource(id, res); return this; }
        W click(int id, String action, int slot) { v.setOnClickPendingIntent(id, open(ctx, action, code(kind, slot))); return this; }
        W bar(int id, float f) {
            v.setProgressBar(id, 100, Math.round(Math.max(0f, Math.min(1f, f)) * 100), false);
            return this;
        }
        W tile(int i, int glyph, String label, String action) {
            show(TILE[i], true).img(TILE_ICON[i], glyph).text(TILE_LABEL[i], label);
            return click(TILE[i], action, 4 + i);
        }
        /** صورةٌ بنسختيها نهاراً وليلاً على أندرويد ١٢+ (تتبع الهاتفَ بلا إعادة رسم)، والحاضرةُ قبله. */
        W bitmap(int id, Bitmap day, Bitmap night) {
            if (Build.VERSION.SDK_INT >= 31 && day != null && night != null) {
                v.setIcon(id, "setImageIcon", Icon.createWithBitmap(day), Icon.createWithBitmap(night));
            } else {
                Bitmap one = isNight(ctx) && night != null ? night : day;
                if (one != null) v.setImageViewBitmap(id, one);
            }
            return this;
        }
    }

    static boolean isNight(Context ctx) {
        return (ctx.getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES;
    }

    /** أماكنُ الراكب الثلاثة: المنزل والعمل — <b>والمطارُ الأقربُ الحقيقيّ</b> إن كتبه الويب (`feed.airport`)، وإلا يُخفى. */
    static void places(W c, JSONObject feed) {
        c.tile(0, R.drawable.tw_g_home, "المنزل", "ride_home").tile(1, R.drawable.tw_g_work, "العمل", "ride_work");
        JSONObject airport = feed == null ? null : feed.optJSONObject("airport");
        if (airport != null && !airport.optString("id", "").isEmpty()) c.tile(2, R.drawable.tw_g_flight, "المطار", "ride_airport");
        else c.show(R.id.tw_t2, false);
    }

    static RemoteViews render(Context ctx, String kind, int size) {
        SharedPreferences p = ctx.getSharedPreferences(LauncherPlugin.PREFS, Context.MODE_PRIVATE);
        if (!p.getBoolean("rider_widgets_plus", false) || !p.getBoolean("signed_in", false)) {
            // **المفتاحُ أُطفئ لبلده والودجةُ على شاشته، أو لم يدخل** — بطاقةُ TAXO بسطرٍ صادقٍ لا بياناتٌ قديمة
            boolean plus = p.getBoolean("rider_widgets_plus", false);
            RemoteViews v = new RemoteViews(ctx.getPackageName(), R.layout.tw_signed_out);
            WidgetSignedOut.show(ctx, v, size == 1 ? 110 : 170, plus ? "سجّل الدخول لتطلب رحلتك بلمسة" : "هذه الودجة غير متاحة الآن",
                    plus ? "سجّل الدخول" : "افتح TAXO", open(ctx, null, code(kind, 9)));
            v.setOnClickPendingIntent(R.id.tw_root, open(ctx, null, code(kind, 9)));
            return v;
        }
        W c = new W(ctx, kind, size);
        c.click(R.id.tw_root, null, 0);
        JSONObject feed = json(p, "w_feed");
        JSONObject ride = RiderBubble.ride(p);
        String phase = ride == null ? "" : ride.optString("phase");
        long at = feed == null ? 0 : feed.optLong("at", 0);
        String until = at > 0 ? "حتى " + hhmm(at) : "افتح التطبيق لتحديثها";
        switch (kind) {
            case "request":
                c.click(R.id.tw_btn, "where_to", 1).click(R.id.tw_root, "where_to", 0);
                if (size == 2) places(c, feed);
                break;
            case "quick":
                c.click(R.id.tw_qbtn, "where_to", 1).click(R.id.tw_root, "where_to", 0);
                if (size == 2) places(c, feed);
                break;
            case "on_the_way":
            case "current":
                renderRide(c, p, ride, phase);
                break;
            case "favorites":
                places(c, feed);
                if (size == 0) c.tile(3, R.drawable.tw_g_location_on, "الكل", "go:/account/places");
                c.click(R.id.tw_btn, "go:/account/places", 2);
                break;
            case "home":
            case "work":
                renderPlace(c, p);
                break;
            case "wallet": {
                JSONObject wallet = feed == null ? null : feed.optJSONObject("wallet");
                c.click(R.id.tw_root, "wallet", 0).click(R.id.tw_btn, "topup", 1);
                if (wallet != null) c.show(R.id.tw_bigrow, true).text(R.id.tw_big, wallet.optString("amount")).text(R.id.tw_unit, wallet.optString("unit")).text(R.id.tw_sub, until);
                else c.show(R.id.tw_bigrow, false).text(R.id.tw_sub, "افتح التطبيق لترى رصيدك");
                break;
            }
            case "discount":
            case "offers": {
                JSONObject offers = feed == null ? null : feed.optJSONObject("offers");
                int count = offers == null ? 0 : offers.optInt("count", 0);
                String title = offers == null ? "" : offers.optString("title", "");
                if ("null".equals(title)) title = "";
                if (count == 0) {
                    c.show(R.id.tw_big, false).show(R.id.tw_btn, false).text(R.id.tw_sub, "لا عروض الآن — نُعلمك حين يصل عرضٌ جديد");
                } else if ("discount".equals(kind)) {
                    String headline = offers.optString("headline", "");
                    boolean has = !headline.isEmpty() && !"null".equals(headline);
                    c.show(R.id.tw_big, has).text(R.id.tw_big, headline).text(R.id.tw_sub, title.isEmpty() ? offersLine(count) : title)
                            .show(R.id.tw_btn, true).click(R.id.tw_btn, null, 1);
                } else {
                    c.show(R.id.tw_big, size == 0).text(R.id.tw_big, String.valueOf(count))
                            .text(R.id.tw_sub, offersLine(count) + (title.isEmpty() ? "" : " — " + title)).show(R.id.tw_btn, true).click(R.id.tw_btn, null, 1);
                }
                break;
            }
            case "schedule": {
                JSONObject booking = feed == null ? null : feed.optJSONObject("booking");
                c.click(R.id.tw_root, "bookings", 0).click(R.id.tw_btn, "bookings", 1);
                if (booking != null) {
                    String to = booking.optString("to", "");
                    c.show(R.id.tw_big, true).text(R.id.tw_big, booking.optString("when")).text(R.id.tw_sub, to.isEmpty() ? "رحلتك القادمة" : "إلى " + to);
                } else {
                    c.show(R.id.tw_big, false).text(R.id.tw_sub, "لا حجوزات قادمة — احجز رحلتك في موعدٍ لاحق");
                }
                break;
            }
            case "services": {
                JSONArray list = feed == null ? null : feed.optJSONArray("services");
                int n = list == null ? 0 : Math.min(list.length(), 4);
                int shown = 0;
                for (int i = 0; i < n; i++) {
                    JSONObject tile = list.optJSONObject(i);
                    if (tile == null) continue;
                    String go = tile.optString("go", "/");
                    c.tile(shown++, serviceGlyph(go), tile.optString("title"), "go:" + go);
                }
                for (int i = shown; i < 4; i++) c.show(TILE[i], false);
                c.show(R.id.tw_sub, shown == 0).text(R.id.tw_sub, "لا خدمات متاحة الآن");
                break;
            }
            case "points": {
                JSONObject points = feed == null ? null : feed.optJSONObject("points");
                c.click(R.id.tw_root, "loyalty", 0).click(R.id.tw_btn, "loyalty", 1);
                if (points == null) {
                    c.text(R.id.tw_big, "").text(R.id.tw_ring_t, "").bar(R.id.tw_ring, 0).text(R.id.tw_sub, "النقاط غير متاحة الآن");
                } else {
                    int pct = (int) Math.round(points.optDouble("pct", 0) * 100);
                    String tier = points.optString("tier", "");
                    c.text(R.id.tw_big, points.optString("points")).text(R.id.tw_ring_t, pct + "%").bar(R.id.tw_ring, pct / 100f)
                            .text(R.id.tw_sub, (tier.isEmpty() ? "" : "المستوى: " + tier + " · ") + pct + "% نحو التالي");
                }
                break;
            }
            case "recent": {
                JSONObject last = feed == null ? null : feed.optJSONObject("last");
                c.click(R.id.tw_root, "rides", 0);
                if (last == null) {
                    c.show(R.id.tw_empty, true).show(R.id.tw_row, false).show(R.id.tw_btns, false).show(R.id.tw_btn, false)
                            .click(R.id.tw_e_btn, "where_to", 1);
                    for (int r : ROW) c.show(r, false);
                } else {
                    String to = last.optString("to", "");
                    c.show(R.id.tw_empty, false).show(R.id.tw_row, true).show(R.id.tw_btns, true).text(R.id.tw_sub, to.isEmpty() ? "رحلتك الأخيرة" : "إلى " + to)
                            .text(R.id.tw_sub2, last.optString("when")).img(R.id.tw_car, car(last.optString("car")));
                    // **«اطلبها مرة أخرى» يفتح ورقةَ الطلب بالوجهة للتأكيد** — الفعلُ نفسُه الذي تستعمله ودجةُ الوجهات الأخيرة
                    boolean again = hasRecent(p);
                    c.show(R.id.tw_btn, again).click(R.id.tw_btn, "recent_0", 1).click(R.id.tw_btn2, "rides", 2).click(R.id.tw_row, "rides", 3);
                    JSONArray names = recent(p);
                    for (int i = 0; i < ROW.length; i++) {
                        boolean on = size == 2 && names != null && i < names.length();
                        c.show(ROW[i], on);
                        if (on) c.text(ROW_LABEL[i], names.optString(i)).click(ROW[i], "recent_" + i, 6 + i);
                    }
                }
                break;
            }
            default: { // nearest
                c.click(R.id.tw_root, "where_to", 0).click(R.id.tw_btn, "where_to", 1);
                boolean fresh = at > 0 && System.currentTimeMillis() - at <= NEAREST_FRESH_MS;
                int minutes = feed == null || feed.isNull("nearest") ? -1 : feed.optInt("nearest", -1);
                if (!fresh) {
                    c.show(R.id.tw_bigrow, false).text(R.id.tw_sub, "افتح التطبيق لنعرف أقربَ سائقٍ إليك");
                } else if (minutes < 0) {
                    c.show(R.id.tw_bigrow, false).text(R.id.tw_sub, "لا سائق متاحٌ قريباً الآن");
                } else {
                    int m = Math.max(1, minutes);
                    c.show(R.id.tw_bigrow, true).text(R.id.tw_big, String.valueOf(m)).text(R.id.tw_unit, minutesUnit(m) + " منك").text(R.id.tw_sub, until);
                }
                break;
            }
        }
        return c.v;
    }

    static JSONArray recent(SharedPreferences p) {
        try {
            return new JSONArray(p.getString("rider_recent", "[]"));
        } catch (Exception e) {
            return null;
        }
    }

    static boolean hasRecent(SharedPreferences p) {
        JSONArray a = recent(p);
        return a != null && a.length() > 0;
    }

    /** «السائق في الطريق» و«رحلتي الحالية» — <b>أثناء رحلةٍ حقيقيّةٍ وحدَها</b>؛ الاسمُ الأوّلُ واللوحةُ والتقييم، <b>ولا هاتف</b>. */
    static void renderRide(W c, SharedPreferences p, JSONObject ride, String phase) {
        boolean onTheWay = "on_the_way".equals(c.kind);
        boolean live = ride != null && RiderBubbleLogic.showsFor(phase);
        c.show(R.id.tw_live, live).show(R.id.tw_empty, !live);
        if (!live) {
            c.click(R.id.tw_root, "where_to", 0).click(R.id.tw_e_btn, "where_to", 1);
            c.show(R.id.tw_map, false).show(R.id.tw_carbox, false);
            return;
        }
        String id = ride.optString("id", "");
        String driver = ride.optString("driver", "");
        String plate = ride.optString("plate", "");
        String rating = ride.optString("rating", "");
        int eta = ride.optInt("eta_min", -1);
        c.bar(R.id.tw_bar, RiderBubbleLogic.approach(phase, eta, ride.optInt("eta_first", -1)));
        // المسار: خريطةٌ صغيرةٌ من نقاطٍ حقيقيّة — في المتوسّطة والكبيرة؛ وإلا السيارة
        double[][] pts = RouteArt.points(json(p, "rider_ride_route"), id);
        boolean map = pts != null && c.size > 0;
        if (map) {
            // المقاساتُ تقريبُ ما يرسمه التخطيط (مولَّد): الكبيرةُ خلفيّةٌ كاملةٌ بين الشارة وصفِّ السائق، والمتوسّطةُ لوحةٌ جانبيّة
            int wDp, hDp, top, bottom;
            if (onTheWay && c.size == 2) { wDp = 330; hDp = 300; top = 56; bottom = 116; }
            else if (onTheWay) { wDp = 140; hDp = 140; top = 16; bottom = 16; }
            else if (c.size == 2) { wDp = 300; hDp = 170; top = 18; bottom = 18; }
            else { wDp = 190; hDp = 100; top = 14; bottom = 14; }
            Bitmap day = RouteArt.draw(c.ctx, pts, wDp, hDp, false, top, bottom);
            Bitmap night = RouteArt.draw(c.ctx, pts, wDp, hDp, true, top, bottom);
            map = day != null;
            if (map) c.bitmap(R.id.tw_map, day, night);
        }
        c.show(R.id.tw_map, map);
        if (onTheWay) {
            c.show(R.id.tw_carbox, !map && c.size > 0);
            if ("assigned".equals(phase) && eta >= 0) {
                int m = Math.max(1, eta);
                c.show(R.id.tw_big, true).text(R.id.tw_big, String.valueOf(m)).text(R.id.tw_unit, minutesUnit(m));
            } else {
                c.show(R.id.tw_big, false).text(R.id.tw_unit, "searching".equals(phase) ? "نبحث لك عن سائق…"
                        : "arrived".equals(phase) ? "وصل السائق — بانتظارك" : "في الطريق إلى وجهتك");
            }
            c.text(R.id.tw_title, driver.isEmpty() ? "السائق في الطريق" : driver);
            StringBuilder line = new StringBuilder();
            if (!rating.isEmpty()) line.append(rating);
            if (!plate.isEmpty()) line.append(line.length() > 0 ? " · " : "").append(plate);
            c.text(R.id.tw_sub, "searching".equals(phase) ? "" : line.toString());
            // **صورةُ السائق المعتمدة — لهذه الرحلة وحدَها**
            Bitmap face = RouteArt.photo(json(p, "rider_ride_photo"), id, Math.round(56 * Math.min(c.ctx.getResources().getDisplayMetrics().density, 2.5f)));
            if (face != null) c.v.setImageViewBitmap(R.id.tw_photo, face);
            c.click(R.id.tw_root, null, 0);
        } else {
            c.show(R.id.tw_car, !map).img(R.id.tw_car, car(ride.optString("cat", "economy")));
            if ("assigned".equals(phase) && eta >= 0) {
                int m = Math.max(1, eta);
                c.text(R.id.tw_chip_t, "الوصول خلال").show(R.id.tw_bigrow, true).text(R.id.tw_big, String.valueOf(m)).text(R.id.tw_unit, minutesUnit(m));
            } else {
                c.show(R.id.tw_bigrow, false).text(R.id.tw_chip_t, "searching".equals(phase) ? "نبحث لك عن سائق…"
                        : "arrived".equals(phase) ? "وصل السائق — بانتظارك" : "في الطريق إلى وجهتك");
            }
        }
    }

    static void renderPlace(W c, SharedPreferences p) {
        boolean home = "home".equals(c.kind);
        JSONObject places = json(p, "rider_places");
        boolean saved = places != null && places.optBoolean(home ? "home" : "work", false);
        c.text(R.id.tw_sub, saved ? (home ? "اطلب رحلة إلى منزلك" : "اطلب رحلة إلى عملك") : "أضفه من أماكني")
                .text(R.id.tw_btn_t, saved ? "اطلب رحلة" : "أضفه الآن");
        c.click(R.id.tw_root, home ? "ride_home" : "ride_work", 0).click(R.id.tw_btn, home ? "ride_home" : "ride_work", 1);
    }

    /** الأصلُ المشترك: يرسم كلَّ ودجةٍ من نوعه حين يُطلب، ويستيقظ على {@code LAUNCHER_CHANGED}. */
    public abstract static class Base extends AppWidgetProvider {
        abstract String kind();

        @Override
        public void onUpdate(Context ctx, AppWidgetManager manager, int[] ids) {
            for (int id : ids) manager.updateAppWidget(id, views(ctx, kind(), manager.getAppWidgetOptions(id)));
        }

        @Override
        public void onAppWidgetOptionsChanged(Context ctx, AppWidgetManager manager, int id, Bundle options) {
            manager.updateAppWidget(id, views(ctx, kind(), options));
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
