package ly.tajora.driver;

import static org.junit.Assert.assertEquals;

import android.telecom.DisconnectCause;

import org.junit.Test;

/** **مكالمةُ الرحلة عند النظام** (SPEC §١٠٣ B/27) — سببُ الانتهاء كما يصل سجلَّ السيّارة، والمجهولُ «أنهيتُها». */
public class CallBridgeUnitTest {

    @Test
    public void mapsEndReasons() {
        assertEquals(DisconnectCause.REJECTED, CallBridgePlugin.causeFor("rejected"));
        assertEquals(DisconnectCause.MISSED, CallBridgePlugin.causeFor("missed"));
        assertEquals(DisconnectCause.ERROR, CallBridgePlugin.causeFor("error"));
        assertEquals(DisconnectCause.REMOTE, CallBridgePlugin.causeFor("remote"));
        assertEquals(DisconnectCause.LOCAL, CallBridgePlugin.causeFor("local"));
        assertEquals(DisconnectCause.LOCAL, CallBridgePlugin.causeFor(null));
    }
}
