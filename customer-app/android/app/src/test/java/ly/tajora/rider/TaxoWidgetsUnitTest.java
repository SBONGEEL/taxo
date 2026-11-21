package ly.tajora.rider;

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
        // 4×2 في Pixel 7 (قِيس ٢١/١١) متوسّطةٌ لا كبيرة — والكبيرةُ من 4×3
        assertEquals(1, TaxoWidgets.sizeClass(373, 200));
        assertEquals(1, TaxoWidgets.sizeClass(250, 180));
        assertEquals(2, TaxoWidgets.sizeClass(373, 300));
    }

    @Test
    public void everyKindHasItsOwnProvider() {
        java.util.Set<Class<?>> seen = new java.util.HashSet<>();
        for (String kind : TaxoWidgets.KINDS) seen.add(TaxoWidgets.provider(kind));
        assertEquals(TaxoWidgets.KINDS.length, seen.size());
    }

    /** العددُ كما يُقال بالعربيّة — لا «2 عروض» ولا «11 عروض». */
    @Test
    public void offersLineCountsInArabic() {
        assertEquals("لا عروض الآن", TaxoWidgets.offersLine(0));
        assertEquals("عرضٌ واحد متاح", TaxoWidgets.offersLine(1));
        assertEquals("عرضان متاحان", TaxoWidgets.offersLine(2));
        assertEquals("3 عروض متاحة", TaxoWidgets.offersLine(3));
        assertEquals("10 عروض متاحة", TaxoWidgets.offersLine(10));
        assertEquals("11 عرضاً متاحاً", TaxoWidgets.offersLine(11));
    }

    @Test
    public void minutesUnitByCount() {
        assertEquals("دقيقة", TaxoWidgets.minutesUnit(1));
        assertEquals("دقائق", TaxoWidgets.minutesUnit(2));
        assertEquals("دقائق", TaxoWidgets.minutesUnit(10));
        assertEquals("دقيقة", TaxoWidgets.minutesUnit(11));
    }

    /** خريطةُ المسار: كلُّ النقاط داخل الهوامش، والشمالُ إلى الأعلى، ونسبةٌ واحدةٌ للمحورين. */
    @Test
    public void routeProjectionStaysInsideAndKeepsNorthUp() {
        double[][] pts = {{35.90, 31.95}, {35.92, 31.97}, {35.95, 31.96}};
        float[] xy = RouteArt.project(pts, 300, 200, 20, 30, 40);
        assertEquals(6, xy.length);
        for (int i = 0; i < xy.length; i += 2) {
            org.junit.Assert.assertTrue(xy[i] >= 20 - 0.01f && xy[i] <= 280 + 0.01f);
            org.junit.Assert.assertTrue(xy[i + 1] >= 30 - 0.01f && xy[i + 1] <= 160 + 0.01f);
        }
        org.junit.Assert.assertTrue("الأشملُ أعلى", xy[3] < xy[1]);
        org.junit.Assert.assertTrue("الأشرقُ أيمن", xy[4] > xy[0]);
    }

    @Test
    public void routeProjectionRefusesTooFewPointsOrNoRoom() {
        org.junit.Assert.assertNull(RouteArt.project(null, 300, 200, 20, 30, 40));
        org.junit.Assert.assertNull(RouteArt.project(new double[][] {{35.9, 31.9}}, 300, 200, 20, 30, 40));
        org.junit.Assert.assertNull(RouteArt.project(new double[][] {{35.9, 31.9}, {35.91, 31.91}}, 30, 200, 20, 30, 40));
    }
}
