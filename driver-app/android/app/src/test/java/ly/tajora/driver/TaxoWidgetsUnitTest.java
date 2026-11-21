package ly.tajora.driver;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

/** **ودجاتُ الأمر الثامن** (٢٠/١١) — المقاسُ من الأبعاد، وثلاثُ درجاتٍ لا تتداخل. */
public class TaxoWidgetsUnitTest {

    @Test
    public void sizeClassFromDimensions() {
        assertEquals(0, TaxoWidgets.sizeClass(110, 110));
        assertEquals(0, TaxoWidgets.sizeClass(180, 200));
        assertEquals(1, TaxoWidgets.sizeClass(250, 110));
        assertEquals(1, TaxoWidgets.sizeClass(240, 200));
        assertEquals(2, TaxoWidgets.sizeClass(250, 180));
    }

    @Test
    public void listedFollowsTheFlags() {
        org.junit.Assert.assertFalse(TaxoWidgets.listed("status", false, true, true, true));
        org.junit.Assert.assertTrue(TaxoWidgets.listed("status", true, false, false, false));
        org.junit.Assert.assertFalse(TaxoWidgets.listed("goal", true, false, true, true));
        org.junit.Assert.assertTrue(TaxoWidgets.listed("busy", true, false, false, true));
    }

    @Test
    public void everyKindHasItsOwnProvider() {
        java.util.Set<Class<?>> seen = new java.util.HashSet<>();
        for (String kind : TaxoWidgets.KINDS) seen.add(TaxoWidgets.provider(kind));
        assertEquals(TaxoWidgets.KINDS.length, seen.size());
    }

    @Test
    public void daysUnitByCount() {
        assertEquals("يوم باقٍ", TaxoWidgets.daysUnit(1));
        assertEquals("أيام باقية", TaxoWidgets.daysUnit(3));
        assertEquals("أيام باقية", TaxoWidgets.daysUnit(10));
        assertEquals("يوماً باقياً", TaxoWidgets.daysUnit(25));
    }
}
