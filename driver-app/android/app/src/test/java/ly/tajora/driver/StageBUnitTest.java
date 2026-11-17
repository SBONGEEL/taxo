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
    public void standingStillSendsOnlyThePanelHeartbeat() {
        // واقف (٥ م < ٣٠) والنبضةُ ٦٠ ث: لا يُرسل قبلها، ويُرسل عندها
        assertEquals(false, OnlineService.shouldSend(true, false, 5f, 20_000L, 60_000L, 30));
        assertEquals(true, OnlineService.shouldSend(true, false, 5f, 60_000L, 60_000L, 30));
        // تحرّك مسافةَ اللوحة ⇐ يُرسل
        assertEquals(true, OnlineService.shouldSend(true, false, 31f, 1_000L, 60_000L, 30));
    }

    @Test
    public void neverReducedDuringRideOrWhenOff() {
        assertEquals(true, OnlineService.shouldSend(true, true, 0f, 1_000L, 60_000L, 30));
        assertEquals(true, OnlineService.shouldSend(false, false, 0f, 1_000L, 60_000L, 30));
        assertEquals(true, OnlineService.shouldSend(true, false, 0f, 1_000L, 0L, 30));
        assertEquals(true, OnlineService.shouldSend(true, false, -1f, 1_000L, 60_000L, 30));
    }

    @Test
    public void rideLineReplacesTheTitleOnlyWhenOnAndConnected() {
        assertEquals("في الطريق إلى الراكب", OnlineService.rideTitle(true, " في الطريق إلى الراكب ", false));
        assertEquals(null, OnlineService.rideTitle(false, "في الطريق إلى الراكب", false));
        assertEquals(null, OnlineService.rideTitle(true, "في الطريق إلى الراكب", true));
        assertEquals(null, OnlineService.rideTitle(true, "", false));
        assertEquals(null, OnlineService.rideTitle(true, null, false));
    }

    @Test
    public void mockSignalLastsOneDay() {
        long now = 1_000_000_000_000L;
        assertEquals(false, DeviceSignals.mockRecently(0L, now));
        assertEquals(true, DeviceSignals.mockRecently(now - 60_000L, now));
        assertEquals(false, DeviceSignals.mockRecently(now - DeviceSignals.MOCK_WINDOW_MS - 1, now));
    }

    @Test
    public void rootedByTagsOrSu() {
        assertEquals(true, DeviceSignals.rootedBy("release-keys", true));
        assertEquals(true, DeviceSignals.rootedBy("test-keys", false));
        assertEquals(false, DeviceSignals.rootedBy("release-keys", false));
        assertEquals(false, DeviceSignals.rootedBy(null, false));
    }

    @Test
    public void unknownCurrencyIsKeptAsIs() {
        assertEquals("EUR", OfferSpeech.spokenCurrency(" EUR "));
        assertEquals("", OfferSpeech.spokenCurrency(null));
    }
}
