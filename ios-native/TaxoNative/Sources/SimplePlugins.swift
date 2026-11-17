import UIKit
import StoreKit
import Vision
import AudioToolbox
import Capacitor

// MARK: - InAppReview

/// **نافذةُ التقييم داخل التطبيق** — نظيرُ `InAppReviewPlugin.java` (Play In-App Review).
///
/// **وiOS هو من يقرّر أتظهر**: ثلاثُ مرّاتٍ في السنة لكلِّ تطبيقٍ على الأكثر، ولا جوابَ يقول أظهرت —
/// كأندرويد تماماً، فالشاشةُ لا تبني على الجواب شيئاً. **وفي TestFlight لا تظهر أبداً** (سلوكُ Apple).
@objc(InAppReviewPlugin)
public class InAppReviewPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "InAppReviewPlugin"
    public let jsName = "InAppReview"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "request", returnType: CAPPluginReturnPromise),
    ]

    @objc func request(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            let scene = UIApplication.shared.connectedScenes
                .compactMap { $0 as? UIWindowScene }
                .first { $0.activationState == .foregroundActive }
            if let scene = scene {
                SKStoreReviewController.requestReview(in: scene)
            }
            call.resolve()
        }
    }
}

// MARK: - SecureFlush

/// **نظيرُ `SecureFlushPlugin.java`** — هناك يُجبر `commit()` المخزنَ الآمن على القرص قبل أن يقتل النظامُ العملية.
/// **وعلى iOS لا شيءَ يُنتظر**: `SecItemAdd`/`SecItemUpdate` في سلسلة المفاتيح متزامنةٌ ومكتوبةٌ لحظةَ عودتها.
/// فالجوابُ «تمّ» صادقٌ هنا لا ادّعاء.
@objc(SecureFlushPlugin)
public class SecureFlushPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "SecureFlushPlugin"
    public let jsName = "SecureFlush"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "flush", returnType: CAPPluginReturnPromise),
    ]

    @objc func flush(_ call: CAPPluginCall) {
        call.resolve()
    }
}

// MARK: - Haptics

/// **الاهتزازُ لسدّادة `navigator.vibrate`** (`TaxoShims`).
///
/// النمطُ كما في الويب: [تشغيل، صمت، تشغيل، …] بالملّي‌ثانية. **والنبضُ دون ٢٥٠ ms لمسةٌ قويّة**،
/// وما فوقه اهتزازُ النظام (≈٤٠٠ ms ثابتة — لا يملك تطبيقٌ على iOS مدّةً غيرَها).
@objc(HapticsPlugin)
public class HapticsPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "HapticsPlugin"
    public let jsName = "Haptics"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "vibrate", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "impact", returnType: CAPPluginReturnPromise),
    ]

    @objc func vibrate(_ call: CAPPluginCall) {
        let pattern = (call.getArray("pattern", Double.self) ?? [200]).prefix(16)
        var at: Double = 0
        for (index, value) in pattern.enumerated() {
            let ms = max(0, value)
            if index % 2 == 0, ms > 0 {
                let long = ms >= 250
                DispatchQueue.main.asyncAfter(deadline: .now() + at / 1000) {
                    if long {
                        AudioServicesPlaySystemSound(kSystemSoundID_Vibrate)
                    } else {
                        let generator = UIImpactFeedbackGenerator(style: .heavy)
                        generator.impactOccurred()
                    }
                }
            }
            at += ms
        }
        call.resolve()
    }

    @objc func impact(_ call: CAPPluginCall) {
        let style: UIImpactFeedbackGenerator.FeedbackStyle
        switch call.getString("style") ?? "medium" {
        case "light": style = .light
        case "heavy": style = .heavy
        default: style = .medium
        }
        DispatchQueue.main.async {
            UIImpactFeedbackGenerator(style: style).impactOccurred()
            call.resolve()
        }
    }
}

// MARK: - QrReader

/// **قراءةُ QR من صورة، في الجهاز نفسِه** (Vision) — لسدّادة `BarcodeDetector` (`TaxoShims`).
/// الصورةُ تأتي من الكاميرا عبر `<input capture>` في الشاشة، **ولا تغادر الهاتف**.
@objc(QrReaderPlugin)
public class QrReaderPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "QrReaderPlugin"
    public let jsName = "QrReader"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "detect", returnType: CAPPluginReturnPromise),
    ]

    @objc func detect(_ call: CAPPluginCall) {
        guard let base64 = call.getString("image"),
              let data = Data(base64Encoded: base64),
              let image = UIImage(data: data)?.cgImage else {
            call.reject("صورةٌ غيرُ مقروءة")
            return
        }
        DispatchQueue.global(qos: .userInitiated).async {
            let request = VNDetectBarcodesRequest()
            request.symbologies = [.qr]
            let handler = VNImageRequestHandler(cgImage: image, options: [:])
            do {
                try handler.perform([request])
                let codes = (request.results ?? []).compactMap { $0.payloadStringValue }
                call.resolve(["codes": codes])
            } catch {
                call.reject("تعذّرت قراءةُ الصورة", nil, error)
            }
        }
    }
}

// MARK: - InstallReferrer

/// **نظيرُ `InstallReferrerPlugin.java`** — وiOS **لا يملك مُحيلَ تثبيت**: App Store لا يمرّر للتطبيق
/// شيئاً من الرابط الذي جاء منه (لا API، وهذا قرارُ خصوصيّةٍ عند Apple).
/// فالجوابُ فارغٌ صادقاً، **ودعوةُ الصديق تعمل على iOS برابط التطبيق** (`appUrlOpen`) أو بكتابة الرمز.
@objc(InstallReferrerPlugin)
public class InstallReferrerPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "InstallReferrerPlugin"
    public let jsName = "InstallReferrer"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "get", returnType: CAPPluginReturnPromise),
    ]

    @objc func get(_ call: CAPPluginCall) {
        call.resolve(["referrer": ""])
    }
}
