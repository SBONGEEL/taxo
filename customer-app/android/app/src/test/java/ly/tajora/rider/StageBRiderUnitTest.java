package ly.tajora.rider;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

/** <b>المرحلة B للراكب</b> (SPEC §١٠٣) — الخالصُ وحدَه؛ والرسمُ نفسُه على المحاكي. */
public class StageBRiderUnitTest {

    @Test
    public void liveNoticeNeedsATitle() {
        assertEquals(true, RideLivePlugin.drawable("الكبتن في الطريق إليك"));
        assertEquals(false, RideLivePlugin.drawable("   "));
        assertEquals(false, RideLivePlugin.drawable(null));
    }

    @Test
    public void richCardJoinsWhatExists() {
        assertEquals("سامر · كيا ريو · 12-34567", RideNotice.join(" · ", "سامر", "كيا ريو", "12-34567"));
        assertEquals("12-34567", RideNotice.join(" · ", "", null, "12-34567"));
    }
}
