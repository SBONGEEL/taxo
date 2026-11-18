import UIKit
import WebKit
import Capacitor

/// **روابطُ الأداة واختصاراتُ الأيقونة** — `taxo-rider://open/<مسار>` و`taxo-driver://open/<مسار>`.
///
/// **قائمةٌ مسمّاةٌ لا مسارٌ حرّ**: الرابطُ يأتي من خارج التطبيق (أداةٌ، اختصار، أو تطبيقٌ آخر يعرف المخطّط)،
/// فلا يُفتح به إلا ما في `allowed`. والتنقّلُ بـ`history.pushState` ثمّ `popstate` — **ما يسمعه موجّهُ الشاشات نفسُه**،
/// فلا يُعاد تحميلُ الصفحة ولا تسقط الجلسة.
///
/// **وما عداه يمرّ إلى Capacitor كما كان** (`appUrlOpen`): رمزُ التبديل بين التطبيقين ودعوةُ الصديق وعودةُ الدفع.
public enum TaxoDeepLink {
    static let allowed: Set<String> = ["/", "/wallet", "/rides", "/account", "/notifications", "/account/permissions"]

    /// اختصاراتُ الأيقونة (`UIApplicationShortcutItems`) — النوعُ هو المسار
    public static func handle(shortcut: UIApplicationShortcutItem) -> Bool {
        // **اختصارُ المُطلِق أوّلاً** (`LauncherPlugin` — يحكمه مفتاحُ `app_shortcuts`): فعلٌ يُسلَّم للويب لا مسار
        if LauncherPlugin.deliver(shortcut) { return true }
        let path = shortcut.type.hasPrefix("/") ? shortcut.type : "/"
        return navigate(path)
    }

    /// `true` إن كان الرابطُ لنا وقد عُومل؛ `false` ليمرّ إلى Capacitor
    public static func handle(url: URL) -> Bool {
        guard ["taxo-rider", "taxo-driver"].contains(url.scheme ?? ""), url.host == "open" else { return false }
        let path = url.path.isEmpty ? "/" : url.path
        return navigate(path)
    }

    @discardableResult
    static func navigate(_ path: String, attempt: Int = 0) -> Bool {
        guard allowed.contains(path) else { return false }
        DispatchQueue.main.async {
            guard let webView = bridgeWebView() else {
                // **إقلاعٌ بارد**: الواجهةُ لم تُبنَ بعد — يُعاد حتى عشر مرّات
                if attempt < 10 {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { navigate(path, attempt: attempt + 1) }
                }
                return
            }
            let literal = "\"" + path + "\""
            let script = """
            (function(p){
              if (document.readyState !== 'complete') return false;
              if (location.pathname !== p) { history.pushState({}, '', p); dispatchEvent(new PopStateEvent('popstate', { state: {} })); }
              return true;
            })(\(literal))
            """
            webView.evaluateJavaScript(script) { result, _ in
                if (result as? Bool) != true, attempt < 10 {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { navigate(path, attempt: attempt + 1) }
                }
            }
        }
        return true
    }

    private static func bridgeWebView() -> WKWebView? {
        let root = UIApplication.shared.connectedScenes
            .compactMap { ($0 as? UIWindowScene)?.windows.first { $0.isKeyWindow } }
            .first?.rootViewController ?? UIApplication.shared.delegate?.window??.rootViewController
        return (root as? CAPBridgeViewController)?.bridge?.webView
    }
}
