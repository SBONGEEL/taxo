package ly.tajora.rider;

import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.widget.RemoteViews;

/**
 * <b>ودجةُ الراكب الجديدة</b> (أمرُ المالك ٢٠/١١ الرابع، الجزء ٣، SPEC §١١٠) — خلف {@code rider_widgets_plus}.
 *
 * <p>«إلى أين؟» يفتح التطبيقَ جاهزاً للكتابة؛ <b>«البيت» و«العمل» والوجهاتُ الأخيرة تفتح ورقةَ الطلب للتأكيد — لا رحلةَ بلا تأكيدٍ أبداً</b>؛
 * وحالُ الرحلة الحيّ (وقتُ الوصول والسيّارة واللوحة) ممّا كتبه التطبيق. <b>تتحدّث حين يتغيّر الحال</b> لا بمؤقّت، <b>وتقول «سجّل الدخول»</b>
 * لمن خرج. والصغيرةُ «إلى أين؟» وحدَها، والمتوسّطةُ معها البيتُ والعمل، والكبيرةُ معها الأخيرةُ والرحلة.
 */
public class RiderQuickWidget extends AppWidgetProvider {

    @Override
    public void onUpdate(Context ctx, AppWidgetManager manager, int[] ids) {
        for (int id : ids) manager.updateAppWidget(id, render(ctx, manager.getAppWidgetOptions(id)));
    }

    @Override
    public void onAppWidgetOptionsChanged(Context ctx, AppWidgetManager manager, int id, Bundle options) {
        manager.updateAppWidget(id, render(ctx, options));
    }

    @Override
    public void onReceive(Context ctx, Intent intent) {
        super.onReceive(ctx, intent);
        if (LauncherPlugin.CHANGED.equals(intent.getAction())) {
            AppWidgetManager manager = AppWidgetManager.getInstance(ctx);
            onUpdate(ctx, manager, manager.getAppWidgetIds(new ComponentName(ctx, RiderQuickWidget.class)));
        }
    }

    /** خالصة: {@code 0} صغيرة · {@code 1} متوسّطة · {@code 2} كبيرة. */
    static int sizeClass(int minWidthDp, int minHeightDp) {
        if (minHeightDp >= 150) return 2;
        if (minHeightDp >= 100 || minWidthDp >= 250) return 1;
        return 0;
    }

    /**
     * <b>على تصميم «اطلب مشوارك»</b> (أمرُ المالك ٢١/١١: «كلُّ الودجات» على صورته المرجعيّة) — ترسمها ودجةُ «request» نفسُها بأحجامها الثلاثة،
     * ومفتاحُها ودخولُها كما هما؛ <b>والمكوّنُ باقٍ</b> فلا تنكسر نسخةٌ وُضعت على شاشة، ويُخفيه {@code TaxoWidgets.sync} من المنتقي
     * ما لم تكن له نسخةٌ موضوعة — فلا تتكرّر الودجةُ فيه.
     */
    static RemoteViews render(Context ctx, Bundle options) {
        return TaxoWidgets.views(ctx, "request", options);
    }
}
