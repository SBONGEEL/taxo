import UIKit
import CoreLocation
import UserNotifications
import AVFoundation
import Capacitor

/// **مركزُ الأذونات على iOS** — نظيرُ `PermissionsPlugin.java` بالعقد نفسِه (`status` · `request` · `open`).
///
/// **والصفوفُ ما يعرفه iOS لا ما يعرفه أندرويد**: لا «ظهور فوق التطبيقات» ولا «توفير البطارية» ولا «تشغيل تلقائي»
/// ولا «ملء الشاشة» — **لا وجودَ لها على iOS**، فلا تُعرض صفوفاً مطفأةً تَعِد بزرٍّ لا يفعل شيئاً.
/// والكبتنُ وحدَه له «الموقع في الخلفية» (`UIBackgroundModes: location` في بيانه وحدَه).
///
/// **والفتحُ صفحةُ التطبيق في «الإعدادات» دائماً** (`details`) — iOS لا يفتح لتطبيقٍ صفحةَ إذنٍ بعينها،
/// إلا الإشعاراتِ منذ iOS 16 (`exact`).
@objc(PermissionsPlugin)
public class PermissionsPlugin: CAPPlugin, CAPBridgedPlugin, CLLocationManagerDelegate {
    public let identifier = "PermissionsPlugin"
    public let jsName = "Permissions"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "status", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "request", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "open", returnType: CAPPluginReturnPromise),
    ]

    private lazy var locationManager: CLLocationManager = {
        let manager = CLLocationManager()
        manager.delegate = self
        return manager
    }()
    private var pendingLocation: CAPPluginCall?

    private var keys: [String] {
        switch TaxoApp.kind {
        case .driver: return ["location", "location_background", "notifications", "microphone"]
        case .rider: return ["location", "notifications", "microphone"]
        }
    }

    // MARK: status

    @objc func status(_ call: CAPPluginCall) {
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            DispatchQueue.main.async {
                let rows: [[String: String]] = self.keys.map { key in
                    ["key": key, "state": self.state(of: key, notifications: settings) ? "on" : "off"]
                }
                let version = Int(UIDevice.current.systemVersion.split(separator: ".").first ?? "0") ?? 0
                call.resolve(["rows": rows, "brand": "apple", "sdk": version])
            }
        }
    }

    private func state(of key: String, notifications: UNNotificationSettings) -> Bool {
        let location = locationManager.authorizationStatus
        switch key {
        case "location":
            return location == .authorizedWhenInUse || location == .authorizedAlways
        case "location_background":
            return location == .authorizedAlways
        case "notifications":
            switch notifications.authorizationStatus {
            case .authorized, .provisional, .ephemeral: return true
            default: return false
            }
        case "microphone":
            return AVAudioSession.sharedInstance().recordPermission == .granted
        default:
            return false
        }
    }

    // MARK: request

    /// **إذنُ التشغيل يُطلب بحواره إن لم يُسأل بعد** — وiOS لا يعرض الحوارَ إلا مرّةً واحدة؛
    /// **فما رُفض يُفتح له «الإعدادات»** ويُعاد `opened` كما في أندرويد.
    @objc func request(_ call: CAPPluginCall) {
        let key = call.getString("key") ?? ""
        DispatchQueue.main.async {
            switch key {
            case "location":
                if self.locationManager.authorizationStatus == .notDetermined {
                    self.pendingLocation = call
                    self.locationManager.requestWhenInUseAuthorization()
                } else {
                    self.openSettings(call, exact: false)
                }
            case "location_background":
                // **«دائماً» يُطلب بعد «أثناء الاستخدام»** — وiOS يعرض الترقيةَ مرّةً واحدة، ثمّ لا يبقى إلا «الإعدادات»
                switch self.locationManager.authorizationStatus {
                case .notDetermined, .authorizedWhenInUse:
                    self.pendingLocation = call
                    self.locationManager.requestAlwaysAuthorization()
                    // **وقد لا يعرض النظامُ شيئاً ولا يُبلغ** (طُلبت الترقيةُ من قبل) — فلا يبقى النداءُ معلّقاً
                    DispatchQueue.main.asyncAfter(deadline: .now() + 4) {
                        if let pending = self.pendingLocation, pending === call {
                            self.pendingLocation = nil
                            call.resolve()
                        }
                    }
                default:
                    self.openSettings(call, exact: false)
                }
            case "notifications":
                UNUserNotificationCenter.current().getNotificationSettings { settings in
                    if settings.authorizationStatus == .notDetermined {
                        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { _, _ in
                            call.resolve()
                        }
                    } else {
                        self.openSettings(call, exact: true)
                    }
                }
            case "microphone":
                if AVAudioSession.sharedInstance().recordPermission == .undetermined {
                    AVAudioSession.sharedInstance().requestRecordPermission { _ in call.resolve() }
                } else {
                    self.openSettings(call, exact: false)
                }
            default:
                call.resolve(["opened": "none"])
            }
        }
    }

    // MARK: open

    @objc func open(_ call: CAPPluginCall) {
        openSettings(call, exact: call.getString("key") == "notifications")
    }

    private func openSettings(_ call: CAPPluginCall, exact notifications: Bool) {
        TaxoApp.openSettings(notifications: notifications)
        var opened = "details"
        if notifications, #available(iOS 16.0, *) { opened = "exact" }
        call.resolve(["opened": opened])
    }

    // MARK: CLLocationManagerDelegate

    public func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        guard manager.authorizationStatus != .notDetermined, let call = pendingLocation else { return }
        pendingLocation = nil
        call.resolve()
    }
}
