package ly.tajora.rider;

import android.content.ComponentName;
import android.content.Context;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.telecom.Connection;
import android.telecom.ConnectionRequest;
import android.telecom.ConnectionService;
import android.telecom.DisconnectCause;
import android.telecom.PhoneAccount;
import android.telecom.PhoneAccountHandle;
import android.telecom.TelecomManager;

import androidx.annotation.RequiresApi;

/**
 * <b>مكالمةُ الرحلة مكالمةٌ يعرفها أندرويد</b> (SPEC §١٠٣ B/27) — حسابُ اتصالٍ <b>مُدارٌ ذاتيّاً</b> ({@code CAPABILITY_SELF_MANAGED}):
 * النظامُ يعرف أن مكالمةً جارية، <b>فيوجّه صوتَها إلى البلوتوث والسيّارة</b>، وتعمل أزرارُ السمّاعة والسيّارة (ردٌّ · رفضٌ · إنهاء)،
 * ويوقف الموسيقى ويعرض المكالمةَ في شاشة السيّارة.
 *
 * <p><b>والصوتُ نفسُه لا يمرّ من هنا</b>: المكالمةُ WebRTC في الويب كما كانت ({@code lib/call-session.ts})، وهذا يقول للنظام
 * «مكالمةٌ» ويُرجع إليه أفعالَ الأزرار ({@link CallBridgePlugin}). <b>وشاشةُ المكالمة شاشةُ التطبيق</b>: أندرويد لا يرسم شاشتَه الأصليّة
 * لمكالمات التطبيقات المُدارة ذاتيّاً — تلك لمكالمات الشريحة وحدها.
 *
 * <p>{@code MANAGE_OWN_CALLS} إذنٌ عاديٌّ يُمنح عند التثبيت — <b>بلا نافذة سؤالٍ ولا إعلانٍ في Play</b>. نسخةُ التطبيق الآخر حرفاً إلا الحزمة.
 */
@RequiresApi(api = Build.VERSION_CODES.O)
public class TaxoConnectionService extends ConnectionService {

    static final String ACCOUNT_ID = "taxo_ride_calls";
    static final String EXTRA_NAME = "taxo_name";
    static final Uri ADDRESS = Uri.fromParts("taxo", "ride", null);

    /** المكالمةُ الجارية — واحدةٌ في كلِّ حين، كما في الويب. */
    static RideConnection current;

    static PhoneAccountHandle handle(Context context) {
        return new PhoneAccountHandle(new ComponentName(context, TaxoConnectionService.class), ACCOUNT_ID);
    }

    /** يُسجَّل الحسابُ قبل كلِّ مكالمة — تكرارُه لا يضرّ، وغيابُه يُسقط المكالمةَ إلى الويب وحدَه. */
    static boolean register(Context context) {
        TelecomManager telecom = context.getSystemService(TelecomManager.class);
        if (telecom == null) return false;
        try {
            telecom.registerPhoneAccount(PhoneAccount.builder(handle(context), "TAXO")
                    .setCapabilities(PhoneAccount.CAPABILITY_SELF_MANAGED)
                    .build());
            return true;
        } catch (Exception ignored) {
            return false;
        }
    }

    @Override
    public Connection onCreateOutgoingConnection(PhoneAccountHandle account, ConnectionRequest request) {
        RideConnection connection = build(request);
        connection.setDialing();
        return connection;
    }

    @Override
    public Connection onCreateIncomingConnection(PhoneAccountHandle account, ConnectionRequest request) {
        RideConnection connection = build(request);
        connection.setRinging();
        return connection;
    }

    @Override
    public void onCreateOutgoingConnectionFailed(PhoneAccountHandle account, ConnectionRequest request) {
        // مكالمةُ شريحةٍ جارية أو رفضٌ من النظام — الويبُ يمضي وحدَه كما كان
        current = null;
        CallBridgePlugin.emit("failed");
    }

    @Override
    public void onCreateIncomingConnectionFailed(PhoneAccountHandle account, ConnectionRequest request) {
        current = null;
        CallBridgePlugin.emit("failed");
    }

    private static RideConnection build(ConnectionRequest request) {
        if (current != null) current.finish(DisconnectCause.LOCAL);
        RideConnection connection = new RideConnection();
        connection.setConnectionProperties(Connection.PROPERTY_SELF_MANAGED);
        connection.setAudioModeIsVoip(true);
        Bundle extras = request.getExtras();
        String name = extras != null ? extras.getString(EXTRA_NAME, "TAXO") : "TAXO";
        connection.setAddress(ADDRESS, TelecomManager.PRESENTATION_ALLOWED);
        connection.setCallerDisplayName(name, TelecomManager.PRESENTATION_ALLOWED);
        current = connection;
        return connection;
    }

    /** أفعالُ النظام (زرُّ السمّاعة، شاشةُ السيّارة) تعود إلى الويب — <b>والويبُ هو من يقرّر</b>، فلا حالَ تفترق. */
    static final class RideConnection extends Connection {
        @Override
        public void onAnswer(int videoState) {
            CallBridgePlugin.emit("answer");
        }

        @Override
        public void onReject() {
            CallBridgePlugin.emit("reject");
            finish(DisconnectCause.REJECTED);
        }

        @Override
        public void onDisconnect() {
            CallBridgePlugin.emit("hangup");
            finish(DisconnectCause.LOCAL);
        }

        @Override
        public void onAbort() {
            onDisconnect();
        }

        @Override
        public void onShowIncomingCallUi() {
            // شاشةُ الرنين شاشةُ التطبيق (المقبسُ والإشعارُ القائمان) — لا شيءَ يُرسم هنا
        }

        void finish(int cause) {
            setDisconnected(new DisconnectCause(cause));
            destroy();
            if (current == this) current = null;
        }
    }
}
