package ly.tajora.rider;

import android.annotation.SuppressLint;
import android.os.Build;
import android.os.Bundle;
import android.telecom.DisconnectCause;
import android.telecom.PhoneAccountHandle;
import android.telecom.TelecomManager;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/**
 * <b>جسرُ مكالمة الرحلة إلى نظام المكالمات</b> (SPEC §١٠٣ B/27) — {@link TaxoConnectionService}. الويبُ يقول «تبدأ · ترنّ · جارية ·
 * انتهت»، والنظامُ يُرجع «ردّ · رفض · إنهاء» من أزرار السمّاعة والسيّارة ({@code callAction}). <b>وكلُّ فشلٍ هنا يُرجع {@code placed: false}
 * ولا يرمي</b>: المكالمةُ في الويب تمضي كما كانت. نسخةُ التطبيق الآخر حرفاً إلا الحزمة.
 */
@CapacitorPlugin(name = "CallBridge")
public class CallBridgePlugin extends Plugin {

    private static CallBridgePlugin instance;

    @Override
    public void load() {
        instance = this;
    }

    static void emit(String action) {
        CallBridgePlugin plugin = instance;
        if (plugin == null) return;
        JSObject event = new JSObject();
        event.put("action", action);
        plugin.notifyListeners("callAction", event);
    }

    /** خالصة: سببُ الانتهاء كما يقوله الويب ← سببُه عند النظام (يظهر في سجلّ السيّارة). */
    static int causeFor(String reason) {
        if ("rejected".equals(reason)) return DisconnectCause.REJECTED;
        if ("missed".equals(reason)) return DisconnectCause.MISSED;
        if ("error".equals(reason)) return DisconnectCause.ERROR;
        if ("remote".equals(reason)) return DisconnectCause.REMOTE;
        return DisconnectCause.LOCAL;
    }

    private static JSObject placed(boolean value) {
        JSObject out = new JSObject();
        out.put("placed", value);
        return out;
    }

    @PluginMethod
    public void available(PluginCall call) {
        JSObject out = new JSObject();
        out.put("available", Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && TaxoConnectionService.register(getContext()));
        call.resolve(out);
    }

    @SuppressLint("MissingPermission")
    @PluginMethod
    public void startOutgoing(PluginCall call) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O || !TaxoConnectionService.register(getContext())) {
            call.resolve(placed(false));
            return;
        }
        TelecomManager telecom = getContext().getSystemService(TelecomManager.class);
        PhoneAccountHandle handle = TaxoConnectionService.handle(getContext());
        try {
            if (telecom == null || !telecom.isOutgoingCallPermitted(handle)) {
                call.resolve(placed(false));
                return;
            }
            Bundle inner = new Bundle();
            inner.putString(TaxoConnectionService.EXTRA_NAME, call.getString("name", "TAXO"));
            Bundle extras = new Bundle();
            extras.putParcelable(TelecomManager.EXTRA_PHONE_ACCOUNT_HANDLE, handle);
            extras.putBundle(TelecomManager.EXTRA_OUTGOING_CALL_EXTRAS, inner);
            telecom.placeCall(TaxoConnectionService.ADDRESS, extras);
            call.resolve(placed(true));
        } catch (Exception ignored) {
            call.resolve(placed(false));
        }
    }

    @SuppressLint("MissingPermission")
    @PluginMethod
    public void reportIncoming(PluginCall call) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O || !TaxoConnectionService.register(getContext())) {
            call.resolve(placed(false));
            return;
        }
        TelecomManager telecom = getContext().getSystemService(TelecomManager.class);
        PhoneAccountHandle handle = TaxoConnectionService.handle(getContext());
        try {
            if (telecom == null || !telecom.isIncomingCallPermitted(handle)) {
                call.resolve(placed(false));
                return;
            }
            Bundle inner = new Bundle();
            inner.putString(TaxoConnectionService.EXTRA_NAME, call.getString("name", "TAXO"));
            Bundle extras = new Bundle();
            extras.putBundle(TelecomManager.EXTRA_INCOMING_CALL_EXTRAS, inner);
            telecom.addNewIncomingCall(handle, extras);
            call.resolve(placed(true));
        } catch (Exception ignored) {
            call.resolve(placed(false));
        }
    }

    @PluginMethod
    public void setActive(PluginCall call) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            TaxoConnectionService.RideConnection connection = TaxoConnectionService.current;
            if (connection != null) connection.setActive();
        }
        call.resolve();
    }

    @PluginMethod
    public void end(PluginCall call) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            TaxoConnectionService.RideConnection connection = TaxoConnectionService.current;
            if (connection != null) connection.finish(causeFor(call.getString("reason", "local")));
        }
        call.resolve();
    }
}
