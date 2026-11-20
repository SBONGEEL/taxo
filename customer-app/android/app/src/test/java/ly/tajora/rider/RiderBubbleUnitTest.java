package ly.tajora.rider;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/** **فقاعةُ الراكب وودجته** (أمرُ المالك ٢٠/١١ الرابع، SPEC §١١٠) — المنطقُ الخالص. */
public class RiderBubbleUnitTest {

    private static List<String> ids(List<RadialMenu.Item> items) {
        List<String> out = new ArrayList<>();
        for (RadialMenu.Item item : items) out.add(item.id);
        return out;
    }

    @Test
    public void showsOnlyWhileSearchingOrRiding() {
        assertTrue(RiderBubbleLogic.showsFor("searching"));
        assertTrue(RiderBubbleLogic.showsFor("assigned"));
        assertTrue(RiderBubbleLogic.showsFor("arrived"));
        assertTrue(RiderBubbleLogic.showsFor("in_progress"));
        assertFalse(RiderBubbleLogic.showsFor("completed"));
        assertFalse(RiderBubbleLogic.showsFor(null));
    }

    @Test
    public void approachRingFillsAsTheCaptainNears() {
        assertEquals(0.5f, RiderBubbleLogic.approach("assigned", 4, 8), 0.0001f);
        assertEquals(0f, RiderBubbleLogic.approach("assigned", 9, 8), 0f);
        assertEquals(0f, RiderBubbleLogic.approach("assigned", -1, 8), 0f);
        assertEquals(1f, RiderBubbleLogic.approach("arrived", -1, -1), 0f);
        assertEquals(0f, RiderBubbleLogic.approach("searching", 3, 5), 0f);
    }

    @Test
    public void menuNeverRequestsARide() {
        assertEquals(Arrays.asList("cancel_ride", "open"), ids(RiderBubbleLogic.items("searching", true, true)));
        List<String> assigned = ids(RiderBubbleLogic.items("assigned", true, true));
        assertTrue(assigned.containsAll(Arrays.asList("call", "chat", "quick", "share_ride", "cancel_ride", "open")));
        // تعديلُ الوجهة في الرحلة وحدَها وبمفتاحه
        assertFalse(assigned.contains("edit_destination"));
        assertTrue(ids(RiderBubbleLogic.items("in_progress", false, true)).contains("edit_destination"));
        assertFalse(ids(RiderBubbleLogic.items("in_progress", false, false)).contains("edit_destination"));
        assertFalse(ids(RiderBubbleLogic.items("in_progress", false, true)).contains("cancel_ride"));
        for (String id : assigned) assertFalse(id.contains("request"));
    }

    @Test
    public void clockAndWidgetSizes() {
        assertEquals("01:05", RiderBubbleLogic.clock(65));
        assertEquals(0, RiderQuickWidget.sizeClass(180, 70));
        assertEquals(1, RiderQuickWidget.sizeClass(260, 70));
        assertEquals(2, RiderQuickWidget.sizeClass(260, 180));
    }
}
