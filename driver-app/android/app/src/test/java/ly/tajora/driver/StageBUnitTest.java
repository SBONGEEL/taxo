package ly.tajora.driver;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

/** <b>اختباراتُ وحدةٍ للمرحلة B</b> (SPEC §١٠٣) — ما هو خالصٌ من منطق الإضافات. */
public class StageBUnitTest {

    private static OfferData offer(String fare, String currency, String distance, String pickup) {
        return new OfferData("r1", fare, currency, "", "اقتصادي", distance, pickup, "وسط البلد", 15);
    }

    @Test
    public void offerIsSpokenWithCurrencyAsAWord() {
        assertEquals("طلبٌ جديد. ٢٫٧٥ دينار. ١٫٢ كم. من الدوار السابع.",
                OfferSpeech.sentence(offer("٢٫٧٥", "د.أ", "١٫٢ كم", "الدوار السابع")));
    }

    @Test
    public void missingFieldsAreDroppedNotSpokenEmpty() {
        assertEquals("طلبٌ جديد.", OfferSpeech.sentence(offer("", "د.أ", "", "")));
        assertEquals("طلبٌ جديد. ٣٠٠ دينار جزائري.", OfferSpeech.sentence(offer("٣٠٠", "د.ج", null, null)));
    }

    @Test
    public void unknownCurrencyIsKeptAsIs() {
        assertEquals("EUR", OfferSpeech.spokenCurrency(" EUR "));
        assertEquals("", OfferSpeech.spokenCurrency(null));
    }
}
