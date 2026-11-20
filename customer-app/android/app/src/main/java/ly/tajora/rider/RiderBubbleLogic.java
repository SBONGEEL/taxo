package ly.tajora.rider;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * <b>منطقُ فقاعة الراكب الخالص</b> (أمرُ المالك ٢٠/١١ الرابع، الجزء ٢، SPEC §١١٠) — بلا Android، فيُختبر على JVM.
 *
 * <p><b>لا تظهر إلا في أربع</b>: البحثُ عن كابتن، وكابتنٌ في الطريق، ووصل، وفي الرحلة. <b>ولا رحلةَ تُطلب منها أبداً</b>، <b>والإلغاءُ
 * يفتح شاشةَ الإلغاء نفسَها</b> بقاعدتها ورسمها — الفقاعةُ لا تقرّر أنه مجّانيّ، تعرض ما قاله التطبيق.
 */
final class RiderBubbleLogic {

    private RiderBubbleLogic() {}

    static boolean showsFor(String phase) {
        return "searching".equals(phase) || "assigned".equals(phase) || "arrived".equals(phase) || "in_progress".equals(phase);
    }

    /** <b>حلقةُ الاقتراب</b> ٠..١ — ما قُطع من أوّل وقت وصولٍ عُرف؛ وبلا وقتٍ صفر، والوصولُ واحد. */
    static float approach(String phase, int etaMin, int firstEtaMin) {
        if ("arrived".equals(phase) || "in_progress".equals(phase)) return 1f;
        if (!"assigned".equals(phase) || firstEtaMin <= 0 || etaMin < 0) return 0f;
        return Math.max(0f, Math.min(1f, 1f - etaMin / (float) firstEtaMin));
    }

    static String clock(long seconds) {
        long s = Math.max(0, seconds);
        return String.format(Locale.ROOT, "%02d:%02d", s / 60, s % 60);
    }

    /** أزرارُ القائمة بحسب المرحلة والمفاتيح — خالصة. */
    static List<RadialMenu.Item> items(String phase, boolean quick, boolean editDestination) {
        List<RadialMenu.Item> items = new ArrayList<>();
        if ("searching".equals(phase)) {
            items.add(new RadialMenu.Item("cancel_ride", "close", "إلغاء الطلب", true, true));
            items.add(new RadialMenu.Item("open", "home", "افتح TAXO"));
            return items;
        }
        items.add(new RadialMenu.Item("call", "call", "اتصال"));
        items.add(new RadialMenu.Item("chat", "chat", "دردشة"));
        if (quick) items.add(new RadialMenu.Item("quick", "chat", "ردّ سريع"));
        items.add(new RadialMenu.Item("share_ride", "share", "مشاركة الرحلة"));
        if (editDestination && "in_progress".equals(phase)) items.add(new RadialMenu.Item("edit_destination", "location_on", "تعديل الوجهة"));
        if ("assigned".equals(phase) || "arrived".equals(phase)) {
            items.add(new RadialMenu.Item("cancel_ride", "close", "إلغاء", true, true));
        }
        items.add(new RadialMenu.Item("open", "home", "افتح TAXO"));
        return items;
    }

    static List<RadialMenu.Item> replyItems(List<String> texts) {
        List<RadialMenu.Item> items = new ArrayList<>();
        for (int i = 0; i < texts.size() && i < 6; i++) items.add(new RadialMenu.Item("reply:" + i, "chat", texts.get(i)));
        items.add(new RadialMenu.Item("back", "close", "رجوع"));
        return items;
    }
}
