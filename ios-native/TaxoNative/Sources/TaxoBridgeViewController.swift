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
/// 4. **لوحةُ المفاتيح تُقصِّر الصفحةَ ولا تغطّيها** — نظيرُ `adjustResize` في أندرويد: WKWebView لا يتقلّص مع لوحة المفاتيح، فالحقلُ
///    في ورقةٍ مثبَّتةٍ أسفلَ الشاشة يقع تحتها. **فيُقصَّر إطارُ الصفحة إلى حافّة اللوحة** (كما يفعل ملحقُ Keyboard لـCapacitor بوضع
///    `native`) — فكلُّ ما يُثبَّت في أسفلها بـCSS يصعد فوقها كما يصعد في أندرويد، **بلا سطرٍ في الشاشات ولا حزمةٍ تُضاف لأندرويد**.
/// 5. **حجمُ الخطّ من إعداد iPhone** (`TaxoTextSize`) — كما يتبعه WebView أندرويد بنفسه.
///
/// ويُشار إليها من `Main.storyboard` (`customModule="TaxoNative"`).
open class TaxoBridgeViewController: CAPBridgeViewController {

    private var notificationDelegate: TaxoNotificationDelegate?
    private var keyboardObserver: NSObjectProtocol?
    private var textSizeObserver: NSObjectProtocol?

    open override func webViewConfiguration(for instanceConfiguration: InstanceConfiguration) -> WKWebViewConfiguration {
        let configuration = super.webViewConfiguration(for: instanceConfiguration)
        configuration.userContentController.addUserScript(
            WKUserScript(source: TaxoShims.source, injectionTime: .atDocumentStart, forMainFrameOnly: true)
        )
        configuration.userContentController.addUserScript(TaxoTextSize.userScript())
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
        bridge.registerPluginInstance(LauncherPlugin())

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

        keyboardObserver = NotificationCenter.default.addObserver(
            forName: UIResponder.keyboardWillChangeFrameNotification, object: nil, queue: .main
        ) { [weak self] note in self?.keyboardChanged(note) }
        // **حجمُ الخطّ يتبع إعدادَ iPhone** وهو مفتوح (`TaxoTextSize`)
        textSizeObserver = NotificationCenter.default.addObserver(
            forName: UIContentSizeCategory.didChangeNotification, object: nil, queue: .main
        ) { [weak self] _ in if let webView = self?.webView { TaxoTextSize.apply(to: webView) } }
    }

    deinit {
        if let keyboardObserver { NotificationCenter.default.removeObserver(keyboardObserver) }
        if let textSizeObserver { NotificationCenter.default.removeObserver(textSizeObserver) }
    }

    /// **الصفحةُ تنتهي حيث تبدأ اللوحة** — وتعود كاملةً حين تُغلق (التداخلُ صفر).
    private func keyboardChanged(_ note: Notification) {
        guard let webView, let window = webView.window,
              let end = (note.userInfo?[UIResponder.keyboardFrameEndUserInfoKey] as? NSValue)?.cgRectValue else { return }
        let overlap = max(0, window.bounds.maxY - end.minY)
        let duration = note.userInfo?[UIResponder.keyboardAnimationDurationUserInfoKey] as? Double ?? 0.25
        let frame = CGRect(x: 0, y: 0, width: window.bounds.width, height: window.bounds.height - overlap)
        UIView.animate(withDuration: duration) {
            webView.frame = frame
            webView.layoutIfNeeded()
        }
        // **ولا إزاحةَ يضيفها WKWebView من عنده** — وإلا صعدت الصفحةُ مرّتين
        webView.scrollView.contentInset = .zero
    }
}
