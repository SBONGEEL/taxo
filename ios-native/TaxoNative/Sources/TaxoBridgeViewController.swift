import UIKit
import WebKit
import UserNotifications
import Capacitor

/// **واجهةُ التطبيق** — `CAPBridgeViewController` نفسُها ومعها ثلاثة:
///
/// 1. **تسجيلُ ملحقات iOS** بأسماء نظائرها في أندرويد — والراكبُ لا يُسجَّل له ما للكبتن وحدَه
///    (البثُّ الخلفيُّ للموقع وبطاقةُ الطلب): ملحقٌ لا يُنادى لا يُحمل.
/// 2. **سدّادتان في الويب** (`TaxoShims`): `navigator.vibrate` و`BarcodeDetector` غائبتان في WKWebView —
///    فتُسدّان بالملحق الأصليّ **بلا سطرٍ يتغيّر في شيفرة الشاشات**، والشاشاتُ تسأل عنهما كما تسأل اليوم.
/// 3. **مندوبُ الإشعارات** يلتقط أزرارَ بطاقة الطلب (قبول · رفض) ويمرّر كلَّ ما عداها إلى Capacitor كما كان.
///
/// ويُشار إليها من `Main.storyboard` (`customModule="TaxoNative"`).
open class TaxoBridgeViewController: CAPBridgeViewController {

    private var notificationDelegate: TaxoNotificationDelegate?

    open override func webViewConfiguration(for instanceConfiguration: InstanceConfiguration) -> WKWebViewConfiguration {
        let configuration = super.webViewConfiguration(for: instanceConfiguration)
        configuration.userContentController.addUserScript(
            WKUserScript(source: TaxoShims.source, injectionTime: .atDocumentStart, forMainFrameOnly: true)
        )
        // **المكالمةُ داخل التطبيق** (WebRTC): الصوتُ يُشغَّل بلا لمسةٍ ثانية وفي الصفحة نفسِها
        configuration.allowsInlineMediaPlayback = true
        configuration.mediaTypesRequiringUserActionForPlayback = []
        return configuration
    }

    open override func capacitorDidLoad() {
        super.capacitorDidLoad()
        guard let bridge = bridge else { return }

        // **المشتركُ بين التطبيقين**
        bridge.registerPluginInstance(PermissionsPlugin())
        bridge.registerPluginInstance(InAppReviewPlugin())
        bridge.registerPluginInstance(SecureFlushPlugin())
        bridge.registerPluginInstance(HapticsPlugin())
        bridge.registerPluginInstance(QrReaderPlugin())
        bridge.registerPluginInstance(CallKitPlugin())
        bridge.registerPluginInstance(LiveActivityPlugin())

        switch TaxoApp.kind {
        case .driver:
            bridge.registerPluginInstance(OnlineServicePlugin())
            bridge.registerPluginInstance(OfferAlertPlugin())
        case .rider:
            bridge.registerPluginInstance(SpeechInputPlugin())
            bridge.registerPluginInstance(InstallReferrerPlugin())
        }

        // **بعد أن ضبط Capacitor مندوبَه** — فنلفّه ولا نستبدله
        let delegate = TaxoNotificationDelegate(forwardingTo: UNUserNotificationCenter.current().delegate)
        UNUserNotificationCenter.current().delegate = delegate
        notificationDelegate = delegate
        TaxoNotificationCategories.register()
    }
}
