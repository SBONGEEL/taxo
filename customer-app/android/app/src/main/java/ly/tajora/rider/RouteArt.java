package ly.tajora.rider;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.BitmapShader;
import android.graphics.BlurMaskFilter;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RectF;
import android.graphics.Shader;
import android.util.Base64;

import org.json.JSONArray;
import org.json.JSONObject;

/**
 * <b>خريطةُ المسار الصغيرة وصورةُ السائق في الودجة</b> (أمرُ المالك ٢١/١١، البند ١).
 *
 * <p><b>من إحداثيّاتٍ حقيقيّةٍ وحدَها</b>: النقاطُ التي جلبها التطبيقُ لمسار الرحلة الجارية ({@code rider_ride_route}) تُرسم خطّاً
 * برتقاليّاً على أرضيّةٍ محايدة (شبكةٌ خفيفةٌ لا شوارعُ مخترَعة)، وفي أوّله السيارة وفي آخره الدبّوس. <b>ولا بلاطاتِ خرائط ولا مفتاح</b> —
 * لا شبكة، فلا بطّاريّة ولا خصوصيّة تُنفق. <b>وما لا نقاطَ له لا يُرسم</b>: تظهر السيارةُ مكانه.
 *
 * <p>وصورةُ السائق المعتمدة ({@code rider_ride_photo}) تُقصّ دائرةً — <b>للرحلة الجارية وحدَها</b> (المعرّفُ يطابق رحلةَ {@code rider_ride}).
 */
final class RouteArt {
    private RouteArt() {}

    /** خالصة: تحويلُ [lng,lat] إلى بكسلات مستطيلٍ بهوامش، بنسبةٍ واحدةٍ للمحورين (cos العرض) — يعيد [x0,y0,x1,y1,…] أو null. */
    static float[] project(double[][] pts, float w, float h, float padX, float padTop, float padBottom) {
        if (pts == null || pts.length < 2) return null;
        double minX = 1e9, maxX = -1e9, minY = 1e9, maxY = -1e9;
        double lat0 = 0;
        for (double[] p : pts) lat0 += p[1];
        lat0 /= pts.length;
        double k = Math.cos(Math.toRadians(lat0));
        for (double[] p : pts) {
            double x = p[0] * k, y = p[1];
            minX = Math.min(minX, x); maxX = Math.max(maxX, x);
            minY = Math.min(minY, y); maxY = Math.max(maxY, y);
        }
        double spanX = Math.max(maxX - minX, 1e-5), spanY = Math.max(maxY - minY, 1e-5);
        float aw = w - 2 * padX, ah = h - padTop - padBottom;
        if (aw <= 0 || ah <= 0) return null;
        double s = Math.min(aw / spanX, ah / spanY);
        double offX = padX + (aw - spanX * s) / 2, offY = padTop + (ah - spanY * s) / 2;
        float[] out = new float[pts.length * 2];
        for (int i = 0; i < pts.length; i++) {
            out[i * 2] = (float) (offX + (pts[i][0] * k - minX) * s);
            out[i * 2 + 1] = (float) (offY + (maxY - pts[i][1]) * s);  // الشمالُ إلى الأعلى
        }
        return out;
    }

    /** نقاطُ مسار الرحلة الجارية من التفضيلات — <b>إن طابق معرّفُها الرحلة</b>؛ وإلا null. */
    static double[][] points(JSONObject route, String rideId) {
        if (route == null || rideId == null || !rideId.equals(route.optString("id"))) return null;
        JSONArray pts = route.optJSONArray("pts");
        if (pts == null || pts.length() < 2) return null;
        double[][] out = new double[pts.length()][];
        for (int i = 0; i < pts.length(); i++) {
            JSONArray p = pts.optJSONArray(i);
            if (p == null || p.length() < 2) return null;
            out[i] = new double[] {p.optDouble(0), p.optDouble(1)};
            if (Double.isNaN(out[i][0]) || Double.isNaN(out[i][1])) return null;
        }
        return out;
    }

    static Bitmap draw(Context ctx, double[][] pts, int wDp, int hDp, boolean night, int padTopDp, int padBottomDp) {
        float d = Math.min(ctx.getResources().getDisplayMetrics().density, 2f);  // سقفُ الدقّة: ذاكرةُ RemoteViews محدودة
        int w = Math.round(wDp * d), h = Math.round(hDp * d);
        float[] xy = project(pts, w, h, 26 * d, padTopDp * d, padBottomDp * d);
        if (xy == null) return null;
        Bitmap bm = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(bm);
        c.drawColor(night ? 0xFF16181E : 0xFFF5F0EC);
        Paint grid = new Paint(Paint.ANTI_ALIAS_FLAG);
        grid.setColor(night ? 0x12FFFFFF : 0x0F101828);
        grid.setStrokeWidth(Math.max(1f, d * 0.8f));
        float step = 22 * d;
        for (float x = step / 2; x < w; x += step) c.drawLine(x, 0, x, h, grid);
        for (float y = step / 2; y < h; y += step) c.drawLine(0, y, w, y, grid);
        Path path = new Path();
        path.moveTo(xy[0], xy[1]);
        for (int i = 2; i < xy.length; i += 2) path.lineTo(xy[i], xy[i + 1]);
        Paint glow = new Paint(Paint.ANTI_ALIAS_FLAG);
        glow.setStyle(Paint.Style.STROKE);
        glow.setStrokeCap(Paint.Cap.ROUND);
        glow.setStrokeJoin(Paint.Join.ROUND);
        glow.setColor(0x55FF6A33);
        glow.setStrokeWidth(11 * d);
        glow.setMaskFilter(new BlurMaskFilter(6 * d, BlurMaskFilter.Blur.NORMAL));
        c.drawPath(path, glow);
        Paint line = new Paint(glow);
        line.setMaskFilter(null);
        line.setColor(0xFFFF6A33);
        line.setStrokeWidth(4.5f * d);
        c.drawPath(path, line);
        Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
        // البداية: السيارة — دائرةٌ بيضاءُ بحلقةٍ برتقاليّة
        fill.setColor(0x40000000);
        c.drawCircle(xy[0], xy[1] + d, 10 * d, fill);
        fill.setColor(Color.WHITE);
        c.drawCircle(xy[0], xy[1], 9 * d, fill);
        fill.setColor(0xFFF05A28);
        c.drawCircle(xy[0], xy[1], 5 * d, fill);
        // النهاية: دبّوسٌ برتقاليٌّ بقلبٍ أبيض
        float ex = xy[xy.length - 2], ey = xy[xy.length - 1];
        Path pin = new Path();
        float r = 9 * d;
        pin.addCircle(ex, ey - 2.2f * r, r, Path.Direction.CW);
        pin.moveTo(ex - r * 0.72f, ey - 1.6f * r);
        pin.lineTo(ex, ey);
        pin.lineTo(ex + r * 0.72f, ey - 1.6f * r);
        pin.close();
        fill.setColor(0xFFF05A28);
        c.drawPath(pin, fill);
        fill.setColor(Color.WHITE);
        c.drawCircle(ex, ey - 2.2f * r, r * 0.42f, fill);
        return bm;
    }

    /** صورةُ السائق دائرةً — <b>للرحلة نفسِها وحدَها</b>؛ وإلا null (يبقى الرسمُ الافتراضيّ). */
    static Bitmap photo(JSONObject stored, String rideId, int sizePx) {
        if (stored == null || rideId == null || !rideId.equals(stored.optString("id"))) return null;
        String b64 = stored.optString("b64", "");
        if (b64.isEmpty()) return null;
        try {
            byte[] raw = Base64.decode(b64, Base64.DEFAULT);
            Bitmap src = BitmapFactory.decodeByteArray(raw, 0, raw.length);
            if (src == null) return null;
            int side = Math.min(src.getWidth(), src.getHeight());
            Bitmap sq = Bitmap.createBitmap(src, (src.getWidth() - side) / 2, (src.getHeight() - side) / 2, side, side);
            Bitmap scaled = Bitmap.createScaledBitmap(sq, sizePx, sizePx, true);
            Bitmap out = Bitmap.createBitmap(sizePx, sizePx, Bitmap.Config.ARGB_8888);
            Canvas c = new Canvas(out);
            Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
            p.setShader(new BitmapShader(scaled, Shader.TileMode.CLAMP, Shader.TileMode.CLAMP));
            c.drawOval(new RectF(0, 0, sizePx, sizePx), p);
            return out;
        } catch (IllegalArgumentException e) {
            return null;  // نصٌّ تالف
        }
    }
}
