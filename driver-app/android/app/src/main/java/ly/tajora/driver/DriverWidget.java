package ly.tajora.driver;

import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.res.Configuration;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.widget.RemoteViews;

import java.util.Locale;

/**
 * <b>ودجةُ الكبتن الجديدة</b> (أمرُ المالك ٢٠/١١ الرابع، الجزء ٣، SPEC §١١٠) — خلف {@code driver_widgets_plus}.
 *
 * <p>صغيرةً: الحالُ وزرُّ الاتّصال/الإيقاف مع صافي اليوم ورحلاته. متوسّطةً: + حلقةُ الهدف وأيّامُ الاشتراك. كبيرةً: + أقربُ منطقةٍ
 * مزدحمة بـ«اذهب إليها»، وأثناء الرحلة حالُها و«اتصال». <b>كلُّ رقمٍ ممّا كتبه التطبيق</b> (الويبُ أو الفقاعة)، ولا حسابَ هنا إلا نسبةَ
 * امتلاء الحلقة للعرض. <b>وتتحدّث حين يتغيّر الحال</b> ({@code LAUNCHER_CHANGED}) لا بمؤقّت، <b>وتقول «سجّل الدخول» لمن خرج</b>.
 *
 * <p><b>والأزرارُ تفتح التطبيقَ على فعلٍ</b> (كالبلاطة): الاتّصالُ يمرّ بفحص الاشتراك والأذونات في الويب، <b>والمكالمةُ بأرقامٍ مخفيّة</b>.
 */
public class DriverWidget extends AppWidgetProvider {

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
            onUpdate(ctx, manager, manager.getAppWidgetIds(new ComponentName(ctx, DriverWidget.class)));
        }
    }

    /** خالصة: <b>حجمُ الودجة</b> من أبعادها بالـdp — {@code 0} صغيرة، {@code 1} متوسّطة، {@code 2} كبيرة. */
    static int sizeClass(int minWidthDp, int minHeightDp) {
        if (minHeightDp >= 150 && minWidthDp >= 250) return 2;
        if (minWidthDp >= 250 || minHeightDp >= 110) return 1;
        return 0;
    }

    /**
     * <b>على تصميم «حالي وأرباح اليوم»</b> (أمرُ المالك ٢١/١١: «كلُّ الودجات» على صورته المرجعيّة) — ترسمها ودجةُ «status» نفسُها بأحجامها الثلاثة،
     * ومفتاحُها ودخولُها كما هما؛ <b>والمكوّنُ باقٍ</b> فلا تنكسر نسخةٌ وُضعت على شاشة، ويُخفيه {@code TaxoWidgets.sync} من المنتقي
     * ما لم تكن له نسخةٌ موضوعة — فلا تتكرّر الودجةُ فيه.
     */
    static RemoteViews render(Context ctx, Bundle options) {
        return TaxoWidgets.views(ctx, "status", options);
    }
}
