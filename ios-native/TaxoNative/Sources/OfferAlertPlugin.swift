import UIKit
import CoreLocation
import UserNotifications
import Capacitor

/// **بطاقةُ الطلب على iOS** — نظيرُ `OfferAlertPlugin.java` بالعقد نفسِه.
///
/// **ولا فقاعةَ ولا نافذةَ فوق التطبيقات على iOS** — Apple لا تسمح لتطبيقٍ أن يرسم فوق غيره (ولا يُقلَّد ذلك
/// بقرار المالك). **فالطريقُ هنا إشعارٌ «حسّاسٌ للوقت»** بصوت الطلب وزرّين: «قبول» و«رفض» — يظهر على شاشة
/// القفل وفوق أيِّ تطبيق، ويرنّ ولو كان «التركيز» مفعّلاً حين يُمنح التطبيقُ صلاحيّتَه.
///
/// **وحالُ ما لا وجودَ له على iOS «ممنوحٌ»** (`overlay` · `fullScreenIntent` · `batteryUnrestricted`): لا يملك
/// الكبتنُ ولا التطبيقُ شيئاً يمنحه هناك — **فصفٌّ مطفأٌ بزرٍّ لا يفعل شيئاً يكذب**، والصدقُ أن لا شيءَ ينقص.
@objc(OfferAlertPlugin)
public class OfferAlertPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "OfferAlertPlugin"
    public let jsName = "OfferAlert"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "status", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "requestOverlay", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "requestFullScreenIntent", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "openAppSettings", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "show", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "hide", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "setSession", returnType: CAPPluginReturnPromise),
    ]

    @objc func status(_ call: CAPPluginCall) {
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            DispatchQueue.main.async {
                let location = CLLocationManager().authorizationStatus
                let notifications: Bool
                switch settings.authorizationStatus {
                case .authorized, .provisional, .ephemeral: notifications = true
                default: notifications = false
                }
                call.resolve([
                    "notifications": notifications,
                    "location": location == .authorizedWhenInUse || location == .authorizedAlways,
                    "backgroundLocation": location == .authorizedAlways,
                    "overlay": true,
                    "fullScreenIntent": true,
                    "batteryUnrestricted": true,
                    // **نظيرُ «قناة الطلبات»**: إشعارٌ بلا صوتٍ أو بلا تنبيهٍ يصل همساً — فيُعدّ مطفأً.
                    // **ولا يُبلَّغ عنه والإشعاراتُ نفسُها مرفوضة** — كان الصفّان يظهران معاً لعلّةٍ واحدة («الإشعارات» و«قناة طلبات الرحلات»)
                    // فدفعا زرَّ الاتصال تحت شريط iPhone SE (لقطاتُ التشغيل 44199806732). وiOS لا قناةَ فيه يفتحها الكبتنُ غيرَ الإشعارات نفسِها.
                    "offerChannel": !notifications || (settings.soundSetting == .enabled && settings.alertSetting == .enabled),
                    "manufacturerSettingsKnown": false,
                ])
            }
        }
    }

    @objc func requestOverlay(_ call: CAPPluginCall) { call.resolve() }
    @objc func requestFullScreenIntent(_ call: CAPPluginCall) { call.resolve() }

    @objc func openAppSettings(_ call: CAPPluginCall) {
        TaxoApp.openSettings()
        call.resolve()
    }

    /// **والتطبيقُ ظاهرٌ لا إشعار** — البطاقةُ في الشاشة ونغمةُ الويب ترنّ (`sounding: false`).
    @objc func show(_ call: CAPPluginCall) {
        guard let rideId = call.getString("rideId") else {
            call.reject("لا رحلة")
            return
        }
        if TaxoApp.isForeground {
            call.resolve(["sounding": false])
            return
        }
        let fare = call.getString("fare") ?? ""
        let currency = call.getString("currency") ?? ""
        let content = UNMutableNotificationContent()
        content.title = "طلب رحلة · \(fare) \(currency)".trimmingCharacters(in: .whitespaces)
        let parts = [call.getString("category"), call.getString("method"), call.getString("distance")]
            .compactMap { $0 }.filter { !$0.isEmpty }
        var lines = [parts.joined(separator: " · ")]
        if let pickup = call.getString("pickup"), !pickup.isEmpty { lines.append("من: \(pickup)") }
        if let drop = call.getString("drop"), !drop.isEmpty { lines.append("إلى: \(drop)") }
        content.body = lines.filter { !$0.isEmpty }.joined(separator: "\n")
        content.sound = TaxoNotificationCategories.offerSound
        content.categoryIdentifier = TaxoNotificationCategories.offer
        content.threadIdentifier = "taxo.offer"
        content.userInfo = ["type": "ride_offer", "ride_id": rideId]
        if #available(iOS 15.0, *) {
            content.interruptionLevel = .timeSensitive
            content.relevanceScore = 1
        }
        let id = "offer-\(rideId)"
        let request = UNNotificationRequest(identifier: id, content: content, trigger: nil)
        UNUserNotificationCenter.current().add(request) { error in
            call.resolve(["sounding": error == nil])
        }
        // **العرضُ ينقضي فيُزال** — دعوةٌ إلى رحلةٍ ذهبت لغيره تكذب
        let seconds = max(5, call.getInt("seconds") ?? 20)
        DispatchQueue.main.asyncAfter(deadline: .now() + .seconds(seconds)) {
            UNUserNotificationCenter.current().removeDeliveredNotifications(withIdentifiers: [id])
        }
    }

    @objc func hide(_ call: CAPPluginCall) {
        let center = UNUserNotificationCenter.current()
        center.getDeliveredNotifications { delivered in
            let ids = delivered.map { $0.request.identifier }.filter { $0.hasPrefix("offer-") }
            center.removeDeliveredNotifications(withIdentifiers: ids)
            call.resolve()
        }
    }

    /// **ما تحتاجه أزرارُ الإشعار لتقبل بنفسها** — قاعدةُ الخدمة ورمزُ الوصول (لا رمزُ التجديد أبداً).
    /// في سلسلة المفاتيح بإتاحة «بعد أوّل فتح» — **فزرُّ «قبول» على شاشة القفل يجده** والتطبيقُ مغلق.
    @objc func setSession(_ call: CAPPluginCall) {
        OfferSession.save(apiBase: call.getString("apiBase"), accessToken: call.getString("accessToken"))
        call.resolve()
    }
}

/// **جلسةُ أزرار الإشعار** — نظيرُ `OfferApi.PREFS` في أندرويد، في سلسلة المفاتيح لا في `UserDefaults`.
enum OfferSession {
    private static let service = "ly.tajora.offer-session"

    static func save(apiBase: String?, accessToken: String?) {
        write("apiBase", apiBase)
        write("token", accessToken)
    }

    static var apiBase: String? { read("apiBase") }
    static var token: String? { read("token") }

    private static func write(_ account: String, _ value: String?) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(query as CFDictionary)
        guard let value = value, let data = value.data(using: .utf8) else { return }
        var add = query
        add[kSecValueData as String] = data
        add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        SecItemAdd(add as CFDictionary, nil)
    }

    private static func read(_ account: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    /// **يقبل أو يرفض بالباب نفسِه** الذي ينادي الويب — `POST /rides/{id}/accept|decline`.
    static func post(rideId: String, action: String, done: @escaping (Bool) -> Void) {
        guard let base = apiBase, let token = token,
              let url = URL(string: base + "/rides/" + rideId + "/" + action) else {
            done(false)
            return
        }
        var request = URLRequest(url: url, timeoutInterval: 8)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer " + token, forHTTPHeaderField: "Authorization")
        request.httpBody = Data("{}".utf8)
        URLSession.shared.dataTask(with: request) { _, response, _ in
            let code = (response as? HTTPURLResponse)?.statusCode ?? 0
            done((200..<300).contains(code))
        }.resume()
    }
}
