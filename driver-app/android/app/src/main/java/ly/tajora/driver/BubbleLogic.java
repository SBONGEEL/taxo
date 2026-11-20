package ly.tajora.driver;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.text.Normalizer;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * <b>منطقُ فقاعة الكبتن الخالص</b> (أمرُ المالك ٢٠/١١ الرابع، SPEC §١١٠) — بلا Android، فيُختبر على JVM ({@code BubbleLogicUnitTest}).
 *
 * <p><b>ولا حسابَ مال</b>: الأرباحُ والهدفُ نصّان كما جاءا، و{@link #goalFraction} <b>نسبةُ عرضٍ</b> لامتلاء حلقةٍ لا مبلغٌ يُحفظ أو
 * يُرسل (الأمر: «الأرباحُ والأهدافُ عرضٌ فقط»). والأرقامُ لاتينيّةٌ دائماً.
 */
final class BubbleLogic {

    private BubbleLogic() {}

    /** <b>امتلاءُ حلقة الهدف</b> ٠..١ — صافي اليوم على الهدف؛ وهدفٌ غائبٌ أو غيرُ موجبٍ = ٠، والسالبُ ٠، وما فوق الهدف ١. */
    static float goalFraction(String earned, String goal) {
        BigDecimal e = decimal(earned);
        BigDecimal g = decimal(goal);
        if (e == null || g == null || g.signum() <= 0 || e.signum() <= 0) return 0f;
        BigDecimal ratio = e.divide(g, 4, RoundingMode.DOWN);
        return Math.min(1f, ratio.floatValue());
    }

    static boolean goalReached(String earned, String goal) {
        BigDecimal e = decimal(earned);
        BigDecimal g = decimal(goal);
        return e != null && g != null && g.signum() > 0 && e.compareTo(g) >= 0;
    }

    private static BigDecimal decimal(String s) {
        if (s == null) return null;
        try {
            return new BigDecimal(s.trim());
        } catch (NumberFormatException e) {
            return null;
        }
    }

    /** <b>حلقةُ الاشتراك</b>: الأيّامُ الباقيةُ من ثلاثين — ٣٠ فما فوق حلقةٌ كاملة. */
    static float subscriptionFraction(int days) {
        if (days <= 0) return 0f;
        return Math.min(1f, days / 30f);
    }

    /**
     * <b>لحظةٌ بصيغة ISO من الخلفية</b> إلى ميلي ثانية — {@code 2026-11-20T13:05:00.123456+00:00} أو {@code …Z}؛ والكسرُ يُقصّ إلى
     * ثلاث. بلا {@code java.time} (أندرويد ٢٤ لا يحمله). {@code -1} لما لا يُفهم.
     */
    static long isoMillis(String iso) {
        if (iso == null) return -1;
        String s = iso.trim();
        if (s.length() < 19) return -1;
        try {
            int y = Integer.parseInt(s.substring(0, 4));
            int mo = Integer.parseInt(s.substring(5, 7));
            int d = Integer.parseInt(s.substring(8, 10));
            int h = Integer.parseInt(s.substring(11, 13));
            int mi = Integer.parseInt(s.substring(14, 16));
            int se = Integer.parseInt(s.substring(17, 19));
            int i = 19;
            int ms = 0;
            if (i < s.length() && s.charAt(i) == '.') {
                int j = i + 1;
                while (j < s.length() && Character.isDigit(s.charAt(j))) j++;
                String frac = (s.substring(i + 1, j) + "000").substring(0, 3);
                ms = Integer.parseInt(frac);
                i = j;
            }
            long offsetMin = 0;
            if (i < s.length()) {
                char sign = s.charAt(i);
                if (sign == '+' || sign == '-') {
                    int oh = Integer.parseInt(s.substring(i + 1, i + 3));
                    int om = Integer.parseInt(s.substring(i + 4, i + 6));
                    offsetMin = (oh * 60L + om) * (sign == '+' ? 1 : -1);
                }
            }
            java.util.Calendar cal = java.util.Calendar.getInstance(java.util.TimeZone.getTimeZone("UTC"));
            cal.clear();
            cal.set(y, mo - 1, d, h, mi, se);
            return cal.getTimeInMillis() + ms - offsetMin * 60_000L;
        } catch (RuntimeException e) {
            return -1;
        }
    }

    /** عدّادٌ بالدقائق والثواني «04:07» — والسالبُ صفر. */
    static String clock(long seconds) {
        long s = Math.max(0, seconds);
        return String.format(Locale.ROOT, "%02d:%02d", s / 60, s % 60);
    }

    /** ساعاتُ العمل «4س 10د» من الدقائق؛ و{@code null} (لم يُقَس) شرطة. */
    static String workTime(Integer minutes) {
        if (minutes == null || minutes < 0) return "—";
        int h = minutes / 60;
        int m = minutes % 60;
        return h > 0 ? String.format(Locale.ROOT, "%dس %dد", h, m) : String.format(Locale.ROOT, "%dد", m);
    }

    /** «الشميساني · 2.1 كم تقريباً» — خطٌّ مستقيمٌ فيُقال «تقريباً»؛ وبلا اسمٍ «منطقة مزدحمة». */
    static String busyLine(String name, double km) {
        String where = name == null || name.trim().isEmpty() ? "منطقة مزدحمة" : name.trim();
        return String.format(Locale.ROOT, "%s · %.1f كم تقريباً", where, km);
    }

    /** يطبّع العربيّةَ للمطابقة: يُسقط التشكيلَ والتطويل، ويوحّد الألفاتِ والتاءَ المربوطة والياء. */
    static String fold(String s) {
        if (s == null) return "";
        String n = Normalizer.normalize(s, Normalizer.Form.NFKC);
        StringBuilder out = new StringBuilder();
        for (char ch : n.toCharArray()) {
            if (ch >= 'ً' && ch <= 'ٟ' || ch == 'ٰ' || ch == 'ـ') continue;
            if (ch == 'أ' || ch == 'إ' || ch == 'آ' || ch == 'ٱ') ch = 'ا';
            else if (ch == 'ة') ch = 'ه';
            else if (ch == 'ى') ch = 'ي';
            out.append(ch);
        }
        return out.toString().toLowerCase(Locale.ROOT).trim();
    }

    /**
     * <b>حكمُ الصوت</b> (البند ٥٤): {@code "accept"} أو {@code "decline"} أو {@code null}. كلمتا الأمر «قبول» و«رفض» ومشتقّاتُهما
     * القريبة؛ <b>وجملةٌ فيها الاثنان لا حكمَ لها</b> — الضجيجُ يُقرأ «لم أفهم» لا قبولاً.
     */
    static String voiceVerdict(List<String> heard) {
        if (heard == null) return null;
        for (String raw : heard) {
            String t = " " + fold(raw) + " ";
            boolean yes = t.contains("قبول") || t.contains(" اقبل") || t.contains(" قبلت") || t.contains("موافق");
            boolean no = t.contains("رفض") || t.contains(" ارفض");
            if (yes && !no) return "accept";
            if (no && !yes) return "decline";
        }
        return null;
    }

    /**
     * <b>أزرارُ القائمة الدائريّة</b> بحسب المفاتيح والحال — خالصة. {@code on}: المفاتيحُ المشتعلة (مفتاحٌ غائبٌ مطفأ)؛ {@code ride}:
     * {@code null} بلا رحلة، وإلا حالُها ({@code accepted}/{@code arrived}/{@code in_progress}).
     */
    static List<RadialMenu.Item> driverItems(Map<String, Boolean> on, boolean online, String ride, boolean onBreak, boolean hasBusy) {
        List<RadialMenu.Item> items = new ArrayList<>();
        if (ride != null && is(on, "bubble_ride_panel")) {
            items.add(new RadialMenu.Item("call", "call", "اتصال"));
            items.add(new RadialMenu.Item("chat", "chat", "دردشة"));
            if ("accepted".equals(ride)) items.add(new RadialMenu.Item("arrived", "location_on", "وصلت"));
            items.add(new RadialMenu.Item("navigate", "navigate", "الملاحة"));
        }
        if (ride != null && is(on, "quick_replies")) items.add(new RadialMenu.Item("quick", "chat", "ردّ سريع"));
        if (ride == null && online && is(on, "driver_break")) {
            if (onBreak) {
                items.add(new RadialMenu.Item("break_end", "timer", "أنهِ الاستراحة"));
            } else {
                items.add(new RadialMenu.Item("break_15", "pause", "توقّف 15"));
                items.add(new RadialMenu.Item("break_30", "pause", "توقّف 30"));
            }
        }
        if (ride == null && online && hasBusy && is(on, "bubble_busy_area")) {
            items.add(new RadialMenu.Item("busy", "flame", "اذهب إليها"));
        }
        if (online && is(on, "bubble_last_ride")) items.add(new RadialMenu.Item("last_ride", "flag", "آخر رحلة", true, false));
        if (online && is(on, "bubble_road_report") && is(on, "map_road_reports")) {
            items.add(new RadialMenu.Item("road", "road_closed", "بلاغ طريق"));
        }
        if (ride == null && online && is(on, "bubble_online_toggle")) {
            items.add(new RadialMenu.Item("offline", "power", "أوقف الاستقبال", true, true));
        }
        items.add(new RadialMenu.Item("open", "home", "افتح TAXO"));
        return items;
    }

    /** البلاغاتُ الأربعة — بأسماء الخلفية (`RoadReportKind`). */
    static List<RadialMenu.Item> roadItems() {
        List<RadialMenu.Item> items = new ArrayList<>();
        items.add(new RadialMenu.Item("road:works", "wrench", "صيانة"));
        items.add(new RadialMenu.Item("road:closed", "road_closed", "طريق مغلق"));
        items.add(new RadialMenu.Item("road:accident", "accident", "حادث"));
        items.add(new RadialMenu.Item("road:jam", "jam", "ازدحام"));
        items.add(new RadialMenu.Item("back", "close", "رجوع"));
        return items;
    }

    /** الردودُ السريعةُ أزراراً — ستّةٌ على الأكثر كما تحفظها اللوحة. */
    static List<RadialMenu.Item> replyItems(List<String> texts) {
        List<RadialMenu.Item> items = new ArrayList<>();
        for (int i = 0; i < texts.size() && i < 6; i++) items.add(new RadialMenu.Item("reply:" + i, "chat", texts.get(i)));
        items.add(new RadialMenu.Item("back", "close", "رجوع"));
        return items;
    }

    private static boolean is(Map<String, Boolean> on, String key) {
        Boolean v = on.get(key);
        return v != null && v;
    }
}
