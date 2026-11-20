package ly.tajora.driver;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/** **الفقاعةُ الجديدة** (أمرُ المالك ٢٠/١١ الرابع، SPEC §١١٠) — المنطقُ الخالص: الحلقات، والأوقات، والصوت، والقائمة، والهندسة، والإعدادات. */
public class BubbleUnitTest {

    private static List<String> ids(List<RadialMenu.Item> items) {
        List<String> out = new ArrayList<>();
        for (RadialMenu.Item item : items) out.add(item.id);
        return out;
    }

    private static Map<String, Boolean> all() {
        Map<String, Boolean> on = new HashMap<>();
        for (String key : DriverBubbleMenu.FLAGS) on.put(key, true);
        return on;
    }

    @Test
    public void goalRingIsDisplayOnlyAndBounded() {
        assertEquals(0.5f, BubbleLogic.goalFraction("12.500", "25"), 0.0001f);
        assertEquals(1f, BubbleLogic.goalFraction("40", "25"), 0f);
        assertEquals(0f, BubbleLogic.goalFraction("10", null), 0f);
        assertEquals(0f, BubbleLogic.goalFraction("10", "0"), 0f);
        assertEquals(0f, BubbleLogic.goalFraction("-3", "25"), 0f);
        assertEquals(0f, BubbleLogic.goalFraction("abc", "25"), 0f);
        assertTrue(BubbleLogic.goalReached("25.000", "25"));
        assertFalse(BubbleLogic.goalReached("24.999", "25"));
    }

    @Test
    public void subscriptionRingIsDaysOfThirty() {
        assertEquals(0f, BubbleLogic.subscriptionFraction(0), 0f);
        assertEquals(0.5f, BubbleLogic.subscriptionFraction(15), 0.0001f);
        assertEquals(1f, BubbleLogic.subscriptionFraction(45), 0f);
    }

    @Test
    public void isoFromTheBackendParsesWithoutJavaTime() {
        assertEquals(0L, BubbleLogic.isoMillis("1970-01-01T00:00:00Z"));
        assertEquals(1_000L * 60 * 60 * 24 + 123, BubbleLogic.isoMillis("1970-01-02T00:00:00.123456+00:00"));
        assertEquals(0L, BubbleLogic.isoMillis("1970-01-01T03:00:00+03:00"));
        assertEquals(-1L, BubbleLogic.isoMillis("not a date"));
        assertEquals(-1L, BubbleLogic.isoMillis(null));
    }

    @Test
    public void clocksAndLines() {
        assertEquals("02:05", BubbleLogic.clock(125));
        assertEquals("00:00", BubbleLogic.clock(-4));
        assertEquals("4س 10د", BubbleLogic.workTime(250));
        assertEquals("45د", BubbleLogic.workTime(45));
        assertEquals("—", BubbleLogic.workTime(null));
        assertEquals("منطقة مزدحمة · 2.1 كم تقريباً", BubbleLogic.busyLine(null, 2.06));
    }

    @Test
    public void voiceNeedsOneClearWord() {
        assertEquals("accept", BubbleLogic.voiceVerdict(Collections.singletonList("قَبول")));
        assertEquals("accept", BubbleLogic.voiceVerdict(Collections.singletonList("نعم اقبل")));
        assertEquals("decline", BubbleLogic.voiceVerdict(Collections.singletonList("رفض")));
        assertNull(BubbleLogic.voiceVerdict(Collections.singletonList("قبول لا رفض")));
        assertNull(BubbleLogic.voiceVerdict(Collections.singletonList("مرحبا")));
        assertEquals("decline", BubbleLogic.voiceVerdict(Arrays.asList("مرحبا", "ارفض")));
    }

    @Test
    public void menuFollowsFlagsAndState() {
        // مطفأٌ كلُّه ⇐ «افتح TAXO» وحدَه
        assertEquals(Collections.singletonList("open"), ids(BubbleLogic.driverItems(new HashMap<>(), true, null, false, true)));
        List<String> idle = ids(BubbleLogic.driverItems(all(), true, null, false, true));
        assertTrue(idle.containsAll(Arrays.asList("break_15", "break_30", "busy", "last_ride", "road", "offline", "open")));
        assertFalse(idle.contains("call"));
        List<String> resting = ids(BubbleLogic.driverItems(all(), true, null, true, true));
        assertTrue(resting.contains("break_end"));
        assertFalse(resting.contains("break_15"));
        List<String> going = ids(BubbleLogic.driverItems(all(), true, "accepted", false, true));
        assertTrue(going.containsAll(Arrays.asList("call", "chat", "arrived", "navigate", "quick")));
        // لا إيقافَ ولا استراحةَ أثناء الرحلة
        assertFalse(going.contains("offline"));
        assertFalse(going.contains("break_15"));
        assertFalse(ids(BubbleLogic.driverItems(all(), true, "in_progress", false, true)).contains("arrived"));
        // بلاغُ الطريق يحتاج مفتاحَه ومفتاحَ البلاغات القائم معاً
        Map<String, Boolean> noReports = all();
        noReports.put("map_road_reports", false);
        assertFalse(ids(BubbleLogic.driverItems(noReports, true, null, false, true)).contains("road"));
    }

    @Test
    public void roadKindsMatchTheBackend() {
        assertEquals(Arrays.asList("road:works", "road:closed", "road:accident", "road:jam", "back"), ids(BubbleLogic.roadItems()));
        assertEquals(7, BubbleLogic.replyItems(Arrays.asList("1", "2", "3", "4", "5", "6", "7", "8")).size());
    }

    @Test
    public void radialItemsNeverTouchAndStayOnScreen() {
        float itemR = 32f;
        float gap = 10f;
        float[][] spots = RadialMenu.positions(9, 40f, 300f, 400f, 800f, 110f, 190f, itemR, gap);
        for (float[] spot : spots) {
            assertTrue(spot[0] >= itemR && spot[0] <= 400f - itemR);
            assertTrue(spot[1] >= itemR && spot[1] <= 800f - itemR);
        }
        // في الحلقة الأولى لا يتماسّ زرّان
        int first = RadialMenu.capacity(110f, itemR, gap);
        for (int i = 1; i < Math.min(first, spots.length); i++) {
            double d = Math.hypot(spots[i][0] - spots[i - 1][0], spots[i][1] - spots[i - 1][1]);
            assertTrue("تماسّ " + i + ": " + d, d >= 2 * itemR - 0.5);
        }
        assertEquals(0, RadialMenu.positions(0, 0, 0, 100, 100, 50, 80, 10, 4).length);
        assertTrue(RadialMenu.capacity(10f, 32f, 10f) >= 1);
    }

    @Test
    public void bubbleSettings() {
        assertEquals(48, StatusBubble.sizeDp("s"));
        assertEquals(58, StatusBubble.sizeDp(null));
        assertEquals(70, StatusBubble.sizeDp("l"));
        assertEquals(0.6f, StatusBubble.alpha("60"), 0f);
        assertEquals(1f, StatusBubble.alpha("x"), 0f);
        assertEquals(6, StatusBubble.snapX(100, 58, 400, 6));
        assertEquals(400 - 58 - 6, StatusBubble.snapX(300, 58, 400, 6));
        assertTrue(StatusBubble.overTarget(200, 700, 200, 710, 64));
        assertFalse(StatusBubble.overTarget(200, 500, 200, 710, 64));
    }

    @Test
    public void widgetSizes() {
        assertEquals(0, DriverWidget.sizeClass(110, 60));
        assertEquals(1, DriverWidget.sizeClass(250, 60));
        assertEquals(2, DriverWidget.sizeClass(260, 160));
    }
}
