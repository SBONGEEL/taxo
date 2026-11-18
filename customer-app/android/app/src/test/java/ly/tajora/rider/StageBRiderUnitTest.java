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
    public void thirdPressInsideTheWindowFires() {
        long[] two = {1_000L, 1_800L};
        assertEquals(true, VolumeTriggerPlugin.completes(two, 2, 3_000L, 2_500L, 3));
        // الأولى أقدمُ من النافذة
        assertEquals(false, VolumeTriggerPlugin.completes(two, 2, 3_600L, 2_500L, 3));
        // ضغطتان لا ثلاث
        assertEquals(false, VolumeTriggerPlugin.completes(new long[] {1_000L, 0L}, 1, 1_500L, 2_500L, 3));
    }

    @Test
    public void richCardJoinsWhatExists() {
        assertEquals("سامر · كيا ريو · 12-34567", RideNotice.join(" · ", "سامر", "كيا ريو", "12-34567"));
        assertEquals("12-34567", RideNotice.join(" · ", "", null, "12-34567"));
    }
}
