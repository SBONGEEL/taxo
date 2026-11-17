import Foundation
import UIKit

/// **أيُّ التطبيقين هذا** — يُقرأ من `Info.plist` (`TaxoAppKind`: `rider` · `driver`) لا من المعرّف:
/// المعرّفُ يتغيّر بالقناة (`.test`) وبالسوق (`.dz`)، **والنوعُ لا يتغيّر**.
public enum TaxoApp {
    public enum Kind: String { case rider, driver }

    public static var kind: Kind {
        let raw = Bundle.main.object(forInfoDictionaryKey: "TaxoAppKind") as? String
        return Kind(rawValue: raw ?? "") ?? .rider
    }

    /// صفحةُ إعدادات التطبيق في «الإعدادات» — **الصفحةُ الوحيدةُ التي يفتحها تطبيقٌ على iOS**:
    /// لا صفحةَ «موقعٍ» ولا «بطاريةٍ» بعينها كما في أندرويد.
    public static func openSettings(notifications: Bool = false) {
        DispatchQueue.main.async {
            var target = UIApplication.openSettingsURLString
            if notifications, #available(iOS 16.0, *) {
                target = UIApplication.openNotificationSettingsURLString
            }
            guard let url = URL(string: target) else { return }
            UIApplication.shared.open(url)
        }
    }

    public static var isForeground: Bool {
        if Thread.isMainThread { return UIApplication.shared.applicationState == .active }
        return DispatchQueue.main.sync { UIApplication.shared.applicationState == .active }
    }
}
