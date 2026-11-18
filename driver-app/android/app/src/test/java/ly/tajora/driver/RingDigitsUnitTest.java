package ly.tajora.driver;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;

import java.util.Locale;
import org.junit.Test;

/** **عدّادُ شاشات الطلب لاتينيّ** (أمرُ المالك ٢٠٢٦-١١-١٨ الثاني) — ولو كانت لغةُ الجهاز عربيّة. */
public class RingDigitsUnitTest {

    @Test
    public void secondsAreLatinEvenOnAnArabicPhone() {
        Locale before = Locale.getDefault();
        try {
            Locale.setDefault(new Locale("ar", "JO"));
            assertEquals("12", RingView.digits(12));
            assertEquals("7", RingView.digits(7));
            assertEquals("0", RingView.digits(0));
            for (char c : RingView.digits(1234567890).toCharArray()) {
                assertFalse("خانةٌ عربيّةٌ-هنديّة في العدّاد", c >= '٠' && c <= '٩');
            }
        } finally {
            Locale.setDefault(before);
        }
    }
}
