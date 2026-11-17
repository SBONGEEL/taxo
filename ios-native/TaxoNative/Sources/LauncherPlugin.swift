import Capacitor
import UIKit

/// **المُطلِق على iOS** (SPEC §١٠٣/١٠ ونظيرُ `LauncherPlugin.java` بعقده حرفاً) — `consume` · `setShortcuts` · `setPrefs` · حدثُ `action`.
///
/// **يحمل فعلاً ولا يفعله**، كنظيره: اختصارُ الأيقونة يُسلَّم إلى الويب، والويبُ ينفّذه بمساره القائم (`lib/launcher.ts`).
/// **والاختصاراتُ ديناميكيّةٌ لا ثابتةٌ في `Info.plist`** — فمفتاحُ `app_shortcuts` لدولة المستخدم يحكمها على iOS كما يحكمها على
/// أندرويد: مطفأٌ ⇐ `setShortcuts([])` ⇐ لا اختصار. (اختصاراتٌ ثابتةٌ كانت ستظهر رغم المفتاح — وأُزيلت لذلك.)
///
/// `setPrefs` يُحفظ ولا يُقرأ بعد: البلاطةُ لا نظيرَ لها في iOS، **والأداةُ تحتاج App Group** (حسابُ Apple) لتقرأ ما يكتبه التطبيق.
@objc(LauncherPlugin)
public class LauncherPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "LauncherPlugin"
    public let jsName = "Launcher"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "consume", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "setShortcuts", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "setPrefs", returnType: CAPPluginReturnPromise),
    ]

    /// **فعلٌ وصل قبل أن يستمع الويب** — إقلاعٌ باردٌ من اختصار: يُسلَّم مرّةً بـ`consume` ثمّ يُمحى
    static var pending: String?
    static weak var live: LauncherPlugin?
    static let typeKey = "taxo.action"

    override public func load() {
        LauncherPlugin.live = self
    }

    /// **من `AppDelegate`** — اختصارٌ ضُغط. والتطبيقُ حيٌّ ⇐ حدث؛ وإلا يُحفظ لـ`consume`.
    public static func deliver(_ item: UIApplicationShortcutItem) -> Bool {
        guard let action = item.userInfo?["action"] as? String else { return false }
        if let plugin = live, plugin.bridge?.webView != nil {
            plugin.notifyListeners("action", data: ["action": action], retainUntilConsumed: true)
        } else {
            pending = action
        }
        return true
    }

    @objc func consume(_ call: CAPPluginCall) {
        let action = LauncherPlugin.pending
        LauncherPlugin.pending = nil
        call.resolve(["action": action as Any])
    }

    @objc func setShortcuts(_ call: CAPPluginCall) {
        let raw = call.getArray("items", JSObject.self) ?? []
        let items: [UIApplicationShortcutItem] = raw.compactMap { item in
            guard let id = item["id"] as? String, let label = item["label"] as? String,
                  let action = item["action"] as? String else { return nil }
            return UIApplicationShortcutItem(
                type: "\(LauncherPlugin.typeKey).\(id)",
                localizedTitle: label,
                localizedSubtitle: nil,
                icon: UIApplicationShortcutIcon(systemImageName: LauncherPlugin.symbol(for: action)),
                userInfo: ["action": action as NSString]
            )
        }
        DispatchQueue.main.async {
            UIApplication.shared.shortcutItems = items
            call.resolve()
        }
    }

    @objc func setPrefs(_ call: CAPPluginCall) {
        UserDefaults.standard.set(call.options as? [String: Any] ?? [:], forKey: "taxo.launcher.prefs")
        call.resolve()
    }

    static func symbol(for action: String) -> String {
        switch action {
        case "ride_home", "home": return "house.fill"
        case "wallet", "earnings": return "wallet.pass.fill"
        case "go_online": return "dot.radiowaves.left.and.right"
        case "go_offline": return "pause.circle.fill"
        default: return "car.fill"
        }
    }
}
