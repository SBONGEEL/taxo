package ly.tajora.driver;

import android.content.Context;
import android.location.Location;
import android.os.Build;

import java.io.File;

/**
 * <b>إشاراتُ الجهاز للمشرف</b> (SPEC §١٠٣ B/17 و25) — <b>بلاغٌ لا حجب</b>: موقعٌ مزيَّفٌ رُصد، وجهازٌ معدَّل (root).
 *
 * <p><b>لا شيءَ هنا يوقف الاستقبالَ أو يرفض رحلة</b> (أمرُ المالك ١٨/١١: «يبلّغان فقط، بلا حجبٍ آليّ») — الويبُ يقرأ
 * {@link #read} ويرسله إلى درج الكبتن في اللوحة، والقرارُ لإنسان. <b>والرصدُ تقريبيٌّ ويُقال كذلك</b>: الإخفاءُ ممكنٌ على جهازٍ
 * معدَّل، وهذا يمسك الشائعَ لا المتعمِّد.
 */
final class DeviceSignals {

    static final String MOCK_SEEN_AT = "mock_seen_at";
    static final long MOCK_WINDOW_MS = 24L * 60 * 60 * 1000;

    private static final String[] SU_PATHS = {
        "/system/bin/su", "/system/xbin/su", "/sbin/su", "/su/bin/su",
        "/data/local/xbin/su", "/data/local/bin/su", "/system/app/Superuser.apk",
    };

    private DeviceSignals() {}

    /** <b>أمزيَّفٌ هذا الموقع؟</b> — بما يقوله النظامُ عن مصدره، لا بتخمينٍ من القفزات. */
    static boolean isMock(Location fix) {
        if (fix == null) return false;
        if (Build.VERSION.SDK_INT >= 31) return fix.isMock();
        return fix.isFromMockProvider();
    }

    static void noteFix(Context context, Location fix) {
        if (!isMock(fix)) return;
        context.getSharedPreferences(LauncherPlugin.PREFS, Context.MODE_PRIVATE)
            .edit().putLong(MOCK_SEEN_AT, System.currentTimeMillis()).apply();
    }

    /** خالصةٌ ومختبَرة: رُصد مزيَّفٌ في آخر يوم؟ */
    static boolean mockRecently(long seenAt, long now) {
        return seenAt > 0 && now - seenAt >= 0 && now - seenAt <= MOCK_WINDOW_MS;
    }

    /** خالصةٌ ومختبَرة: «test-keys» في وسوم البناء أو ملفُّ su في موضعٍ معروف. */
    static boolean rootedBy(String tags, boolean suFound) {
        return suFound || (tags != null && tags.contains("test-keys"));
    }

    static boolean rooted() {
        boolean su = false;
        for (String path : SU_PATHS) {
            try {
                if (new File(path).exists()) {
                    su = true;
                    break;
                }
            } catch (SecurityException ignored) {
                // مسارٌ ممنوعُ القراءة — لا يُعدّ شيئاً
            }
        }
        return rootedBy(Build.TAGS, su);
    }

    /** خالصةٌ ومختبَرة: <b>محاكٍ لا هاتف</b> (نقاطُ الالتزام §١١٤-ب) — بصماتُ البناء المعروفة لمحاكيات أندرويد. */
    static boolean emulatorBy(String fingerprint, String hardware, String product, String model) {
        String f = fingerprint == null ? "" : fingerprint.toLowerCase();
        String h = hardware == null ? "" : hardware.toLowerCase();
        String p = product == null ? "" : product.toLowerCase();
        String m = model == null ? "" : model.toLowerCase();
        return f.startsWith("generic") || f.contains("emulator") || f.contains("/sdk_gphone")
            || h.contains("goldfish") || h.contains("ranchu") || h.contains("vbox")
            || p.contains("sdk_gphone") || p.equals("sdk") || p.contains("emulator") || p.contains("simulator")
            || m.contains("android sdk built for") || m.contains("emulator");
    }

    static boolean emulator() {
        return emulatorBy(Build.FINGERPRINT, Build.HARDWARE, Build.PRODUCT, Build.MODEL);
    }

    static boolean mockRecently(Context context) {
        long seen = context.getSharedPreferences(LauncherPlugin.PREFS, Context.MODE_PRIVATE).getLong(MOCK_SEEN_AT, 0L);
        return mockRecently(seen, System.currentTimeMillis());
    }
}
