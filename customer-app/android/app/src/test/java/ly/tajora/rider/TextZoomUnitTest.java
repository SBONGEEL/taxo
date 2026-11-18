package ly.tajora.rider;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

/** **النصُّ الكبير** (SPEC §١٠٣ C/40) — النسبةُ بحدّيها. */
public class TextZoomUnitTest {

    @Test
    public void clampsToTheAllowedRange() {
        assertEquals(100, TextZoomPlugin.clamp(null));
        assertEquals(100, TextZoomPlugin.clamp(80));
        assertEquals(130, TextZoomPlugin.clamp(130));
        assertEquals(160, TextZoomPlugin.clamp(300));
    }
}
