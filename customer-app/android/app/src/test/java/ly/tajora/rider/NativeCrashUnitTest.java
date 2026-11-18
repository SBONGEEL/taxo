package ly.tajora.rider;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

/** **تعطّلُ أندرويد الأصليّ** (SPEC §١٠٣ C/41) — الاسمُ والإطاراتُ، **ولا نصَّ رسالةٍ أبداً**. */
public class NativeCrashUnitTest {

    @Test
    public void namesTheRootCause() {
        Throwable error = new RuntimeException("wrap", new IllegalStateException("inner"));
        assertEquals("java.lang.RuntimeException ← java.lang.IllegalStateException", NativeCrashPlugin.nameOf(error));
        assertEquals("java.lang.IllegalStateException", NativeCrashPlugin.nameOf(new IllegalStateException("x")));
    }

    @Test
    public void framesCarryNoMessageText() {
        Throwable error = new RuntimeException("phone 0791234567", new IllegalStateException("user@example.com"));
        String frames = NativeCrashPlugin.framesOf(error);
        assertTrue(frames.contains("    at "));
        assertTrue(frames.contains("Caused by java.lang.IllegalStateException"));
        assertFalse(frames.contains("0791234567"));
        assertFalse(frames.contains("user@example.com"));
    }
}
