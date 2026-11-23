package ly.tajora.rider;

import com.getcapacitor.BridgeActivity;

/**
 * <b>إضافاتُ النكهة</b> (نسخةُ Huawei، أمرُ المالك ٢٠٢٦-١١-٢٣) — <b>في نكهات Google لا شيءَ يُزاد</b>: الإشعاراتُ من ملحق FCM كما هي.
 * ونظيرُه في {@code src/huawei} يسجّل {@code HmsPushPlugin}. <b>والاسمُ واحدٌ في المجموعتين</b> فلا يعرف {@code MainActivity} أيَّ نكهةٍ هو.
 */
final class FlavorPlugins {
    private FlavorPlugins() {
    }

    static void register(BridgeActivity activity) {
    }

    /** <b>ولا شيءَ يحلّ محلَّ ملحقٍ مولَّد</b> في نكهات Google — ملحقُ FCM كما هو. */
    static void late(BridgeActivity activity) {
    }
}
