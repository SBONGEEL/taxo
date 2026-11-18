package ly.tajora.rider;

import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.Bundle;

import androidx.activity.result.ActivityResult;
import androidx.core.content.ContextCompat;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.ActivityCallback;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.google.android.gms.auth.api.phone.SmsRetriever;
import com.google.android.gms.common.api.CommonStatusCodes;
import com.google.android.gms.common.api.Status;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * <b>ملءُ رمز التحقّق من الرسالة القصيرة</b> (SPEC §١٠٣ B/23) — واجهةُ «SMS User Consent» من Google: <b>بلا إذنٍ ولا بصمةِ تطبيقٍ في
 * الرسالة</b>؛ النظامُ يسأل صاحبَ الهاتف «أتسمح لـTAXO بقراءة هذه الرسالة؟» لرسالةٍ واحدةٍ فيها رمز، <b>ولا يُقرأ شيءٌ بلا موافقته</b>.
 *
 * <p>يستمع خمسَ دقائق (حدُّ النظام) ثمّ يسكت؛ ورفضُ الموافقة أو انقضاءُ المهلة {@code code=null} — <b>والكتابةُ باليد باقيةٌ دائماً</b>.
 * نسخةُ التطبيق الآخر حرفاً إلا الحزمة.
 */
@CapacitorPlugin(name = "SmsConsent")
public class SmsConsentPlugin extends Plugin {

    private BroadcastReceiver receiver;
    private PluginCall waiting;
    private int length = 6;

    /** خالصةٌ ومختبَرة: أوّلُ عددٍ بالطول المطلوب قائمٍ وحدَه — والخاناتُ العربيّةُ-الهنديّةُ تُقرأ لاتينيّة. */
    static String extractCode(String message, int length) {
        if (message == null || length < 4 || length > 8) return null;
        StringBuilder latin = new StringBuilder(message.length());
        for (int i = 0; i < message.length(); i++) {
            char c = message.charAt(i);
            if (c >= '\u0660' && c <= '\u0669') latin.append((char) ('0' + (c - '\u0660')));
            else if (c >= '\u06F0' && c <= '\u06F9') latin.append((char) ('0' + (c - '\u06F0')));
            else latin.append(c);
        }
        Matcher match = Pattern.compile("(?<![0-9])[0-9]{" + length + "}(?![0-9])").matcher(latin);
        return match.find() ? match.group() : null;
    }

    @PluginMethod(returnType = PluginMethod.RETURN_PROMISE)
    public void listen(PluginCall call) {
        Activity activity = getActivity();
        if (activity == null) {
            resolveCode(call, null);
            return;
        }
        stopListening();
        Integer requested = call.getInt("length");
        length = requested == null ? 6 : requested;
        waiting = call;
        receiver = new BroadcastReceiver() {
            @Override
            public void onReceive(Context context, Intent intent) {
                if (!SmsRetriever.SMS_RETRIEVED_ACTION.equals(intent.getAction())) return;
                Bundle extras = intent.getExtras();
                Status status = extras == null ? null : (Status) extras.get(SmsRetriever.EXTRA_STATUS);
                PluginCall pending = waiting;
                stopListening();
                if (pending == null) return;
                if (status == null || status.getStatusCode() != CommonStatusCodes.SUCCESS) {
                    resolveCode(pending, null);
                    return;
                }
                Intent consent = extras.getParcelable(SmsRetriever.EXTRA_CONSENT_INTENT);
                if (consent == null) {
                    resolveCode(pending, null);
                    return;
                }
                try {
                    startActivityForResult(pending, consent, "consentResult");
                } catch (Exception failed) {
                    resolveCode(pending, null);
                }
            }
        };
        ContextCompat.registerReceiver(getContext(), receiver, new IntentFilter(SmsRetriever.SMS_RETRIEVED_ACTION),
                SmsRetriever.SEND_PERMISSION, null, ContextCompat.RECEIVER_EXPORTED);
        SmsRetriever.getClient(activity).startSmsUserConsent(null)
                .addOnFailureListener(error -> {
                    PluginCall pending = waiting;
                    stopListening();
                    if (pending != null) resolveCode(pending, null);
                });
    }

    @ActivityCallback
    private void consentResult(PluginCall call, ActivityResult result) {
        if (call == null) return;
        String message = result.getResultCode() == Activity.RESULT_OK && result.getData() != null
                ? result.getData().getStringExtra(SmsRetriever.EXTRA_SMS_MESSAGE) : null;
        resolveCode(call, extractCode(message, length));
    }

    @PluginMethod
    public void stop(PluginCall call) {
        PluginCall pending = waiting;
        stopListening();
        if (pending != null) resolveCode(pending, null);
        call.resolve();
    }

    private void stopListening() {
        waiting = null;
        if (receiver != null) {
            try {
                getContext().unregisterReceiver(receiver);
            } catch (IllegalArgumentException ignored) {
                // سُجّل ثمّ أُزيل — لا شيء
            }
            receiver = null;
        }
    }

    private static void resolveCode(PluginCall call, String code) {
        JSObject out = new JSObject();
        out.put("code", code);
        call.resolve(out);
    }

    @Override
    protected void handleOnDestroy() {
        stopListening();
        super.handleOnDestroy();
    }
}
