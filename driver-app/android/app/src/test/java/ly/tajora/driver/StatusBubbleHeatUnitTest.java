package ly.tajora.driver;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

/** **حرارةُ الطلب في الفقاعة** (SPEC §١٠٣ C/29) — متّصلٌ وطلبٌ عالٍ معاً، ولا حرارةَ لغير المتّصل. */
public class StatusBubbleHeatUnitTest {

    @Test
    public void heatNeedsOnlineAndHighDemand() {
        assertTrue(StatusBubble.showsHeat(true, true));
        assertFalse(StatusBubble.showsHeat(true, false));
        assertFalse(StatusBubble.showsHeat(false, true));
    }
}
