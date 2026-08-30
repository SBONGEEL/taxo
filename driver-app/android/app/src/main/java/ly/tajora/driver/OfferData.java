package ly.tajora.driver;

import android.content.Intent;
import android.os.Bundle;

/**
 * حمولةُ بطاقة الطلب — <b>ما ترسمه الأسطحُ الثلاثةُ كلُّها</b>.
 *
 * <p><b>وبيتٌ واحدٌ لا ثلاثة</b>: الورقةُ والفقاعةُ وشاشةُ ملء الشاشة ترسم
 * الحقولَ نفسَها بأحجامٍ مختلفة — <b>ونسخُ الحقول ثلاثَ مرّاتٍ يجعل إضافةَ
 * حقلٍ إصلاحاً يقع مرّتين ويُنسى مرّة</b>، وهو الشكلُ المسجَّل في هذا المشروع.
 *
 * <p><b>ولا هويّةَ راكبٍ فيها</b>: نقطةُ الانطلاق والوجهةُ والأجرةُ والمسافةُ
 * والمهلة — <b>كما في التصميم، وكما في `OfferSheet.tsx` منذ بنائها</b>.
 */
public final class OfferData {

    public final String rideId;
    public final String fare;
    public final String currency;
    public final String method;
    public final String category;
    public final String distance;
    public final String pickup;
    public final String drop;
    public final int seconds;

    public OfferData(
            String rideId,
            String fare,
            String currency,
            String method,
            String category,
            String distance,
            String pickup,
            String drop,
            int seconds
    ) {
        this.rideId = or(rideId, "");
        this.fare = or(fare, "");
        this.currency = or(currency, "");
        this.method = or(method, "");
        this.category = or(category, "");
        this.distance = or(distance, "");
        this.pickup = or(pickup, "");
        this.drop = or(drop, "");
        this.seconds = seconds > 0 ? seconds : 7;
    }

    private static String or(String value, String fallback) {
        return value == null ? fallback : value;
    }

    /** «كاش · ١٫٢ كم · اقتصادي» — <b>وما غاب يُطوى ولا يترك فاصلاً معلَّقاً</b>. */
    public String meta(boolean withCategory) {
        StringBuilder out = new StringBuilder();
        if (!method.isEmpty()) out.append(method);
        if (!distance.isEmpty()) {
            if (out.length() > 0) out.append(" · ");
            out.append(distance);
        }
        if (withCategory && !category.isEmpty()) {
            if (out.length() > 0) out.append(" · ");
            out.append(category);
        }
        return out.toString();
    }

    public Bundle toBundle() {
        Bundle b = new Bundle();
        b.putString("ride_id", rideId);
        b.putString("fare", fare);
        b.putString("currency", currency);
        b.putString("method", method);
        b.putString("category", category);
        b.putString("distance", distance);
        b.putString("pickup", pickup);
        b.putString("drop", drop);
        b.putInt("seconds", seconds);
        return b;
    }

    public static OfferData from(Intent intent) {
        return new OfferData(
                intent.getStringExtra("ride_id"),
                intent.getStringExtra("fare"),
                intent.getStringExtra("currency"),
                intent.getStringExtra("method"),
                intent.getStringExtra("category"),
                intent.getStringExtra("distance"),
                intent.getStringExtra("pickup"),
                intent.getStringExtra("drop"),
                intent.getIntExtra("seconds", 7)
        );
    }
}
