package ly.tajora.rider;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

/** **بطاقةُ «قبل الدخول»** (٢٠/١١ السادس، البند ٣) — عموديّةٌ حين يتّسع الارتفاع، وصفٌّ واحدٌ حين يضيق فلا يُقصّ الزرّ. */
public class WidgetSignedOutUnitTest {

    @Test
    public void columnOnlyWhenTallEnough() {
        assertFalse(WidgetSignedOut.column(70));
        assertFalse(WidgetSignedOut.column(110));
        assertTrue(WidgetSignedOut.column(WidgetSignedOut.COLUMN_MIN_DP));
        assertTrue(WidgetSignedOut.column(220));
    }

    @Test
    public void portraitTakesTheTallerHeight() {
        assertTrue(WidgetSignedOut.pick(true, 110, 190) == 190);
        assertTrue(WidgetSignedOut.pick(true, 110, 0) == 110);
        assertTrue(WidgetSignedOut.pick(false, 110, 190) == 110);
    }
}
