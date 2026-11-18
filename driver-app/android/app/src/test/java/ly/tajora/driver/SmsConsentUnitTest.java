package ly.tajora.driver;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

/** **ملءُ الرمز** (SPEC §١٠٣ B/23) — الاستخراجُ وحدَه؛ والموافقةُ نافذةُ النظام. */
public class SmsConsentUnitTest {

    @Test
    public void picksTheCodeOfTheRequestedLength() {
        assertEquals("482913", SmsConsentPlugin.extractCode("رمز التحقق في TAXO: 482913 لا تشاركه", 6));
        assertEquals("482913", SmsConsentPlugin.extractCode("Your TAXO code is 482913. Call 0791234567 for help", 6));
    }

    @Test
    public void readsArabicIndicDigits() {
        assertEquals("482913", SmsConsentPlugin.extractCode("رمزك ٤٨٢٩١٣", 6));
    }

    @Test
    public void nothingWhenNoStandaloneCode() {
        assertEquals(null, SmsConsentPlugin.extractCode("رقمك 0791234567", 6));
        assertEquals(null, SmsConsentPlugin.extractCode(null, 6));
    }
}
