package ly.tajora.driver;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

/** <b>اختباراتُ وحدةٍ للمرحلة A</b> (SPEC §١٠٣) — ما هو خالصٌ من منطق الإضافات، بلا جهاز. وما يحتاج النظامَ يُقاس على المحاكي. */
public class StageAUnitTest {

    @Test
    public void intervalStaysDefaultWhenSwitchIsOff() {
        assertEquals(20_000L, OnlineService.effectiveInterval(false, 7_000L));
        assertEquals(20_000L, OnlineService.effectiveInterval(true, 0L));
    }

    @Test
    public void intervalFollowsPanelWithinBounds() {
        assertEquals(15_000L, OnlineService.effectiveInterval(true, 15_000L));
        assertEquals(5_000L, OnlineService.effectiveInterval(true, 1_000L));
        assertEquals(60_000L, OnlineService.effectiveInterval(true, 600_000L));
    }

    @Test
    public void bubbleHidesOnlyInBottomFifth() {
        assertFalse(StatusBubble.inDismissZone(100f, 2000));
        assertFalse(StatusBubble.inDismissZone(1599f, 2000));
        assertTrue(StatusBubble.inDismissZone(1600f, 2000));
        assertFalse(StatusBubble.inDismissZone(1900f, 0));
    }

    /** رمزُ حضورٍ ميت (٤٠١ ثلاثاً متتالية) يكفّ البثَّ حتى يصل رمزٌ جديد — ٦٤١ نداءً ضائعاً من جهازٍ واحدٍ قِيست على الإنتاج ٢٦/١١ */
    @Test
    public void aDeadPresenceTokenStopsBeingSent() {
        assertTrue(OnlineService.tokenAlive(0));
        assertTrue(OnlineService.tokenAlive(OnlineService.DEAD_TOKEN_AFTER - 1));
        assertFalse(OnlineService.tokenAlive(OnlineService.DEAD_TOKEN_AFTER));
        assertFalse(OnlineService.tokenAlive(641));
    }
}
