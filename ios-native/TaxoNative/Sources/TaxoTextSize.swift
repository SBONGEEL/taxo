import UIKit
import WebKit

/// **حجمُ الخطّ من إعداد iPhone** — نظيرُ `textZoom` في WebView أندرويد، الذي يتبع حجمَ خطِّ النظام بنفسه.
///
/// WKWebView لا يتبع «حجمَ النصّ» في iOS، فكان iPhone وحدَه يتجاهل من كبّر خطَّه. **فيُترجم إعدادُه إلى نسبةٍ** تُعطى
/// لـ`-webkit-text-size-adjust` — **النصُّ وحدَه يكبر لا التخطيط**، كما في أندرويد حرفاً. **والسقفُ ٢٠٠٪** كأعلى ما يبلغه أندرويد،
/// فخطوطُ «إمكانيّة الوصول» الكبرى لا تكسر شاشةً لم تُكسر هناك.
enum TaxoTextSize {
    static func percent(_ category: UIContentSizeCategory) -> Int {
        switch category {
        case .extraSmall: return 82
        case .small: return 88
        case .medium: return 94
        case .large: return 100
        case .extraLarge: return 112
        case .extraExtraLarge: return 124
        case .extraExtraExtraLarge: return 135
        case .accessibilityMedium: return 160
        case .accessibilityLarge: return 180
        default: return category.isAccessibilityCategory ? 200 : 100
        }
    }

    static var script: String {
        let pct = percent(UIApplication.shared.preferredContentSizeCategory)
        return "document.documentElement.style.webkitTextSizeAdjust='\(pct)%';"
    }

    /// عند بدء كلِّ صفحة (`WKUserScript`) — وقبل أن يُرسم شيء
    static func userScript() -> WKUserScript {
        WKUserScript(
            source: "(function(){var s=function(){if(document.documentElement){\(script)}};s();document.addEventListener('DOMContentLoaded',s);})();",
            injectionTime: .atDocumentStart, forMainFrameOnly: true)
    }

    /// وحين يغيّره صاحبُه والتطبيقُ مفتوح
    static func apply(to webView: WKWebView) {
        webView.evaluateJavaScript(script, completionHandler: nil)
    }
}
