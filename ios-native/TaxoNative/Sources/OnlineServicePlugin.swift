import Foundation
import CoreLocation
import Capacitor

/// **بثُّ موقع الكبتن في الخلفية على iOS** — نظيرُ `OnlineService.java` بالعقد نفسِه (`start` · `degraded` · `stop`)
/// **وبالبابِ نفسِه**: `POST /drivers/me/location` بترويسة `X-Presence-Token` وجسمٍ `{lat,lng,heading}`.
///
/// **والعلّةُ هي علّةُ أندرويد**: iOS يجمّد شيفرةَ الويب حين يُغلق الكبتنُ الشاشةَ أو ينتقل إلى تطبيقٍ آخر،
/// فيسقط المقبسُ ويخرج من التوزيع وهو «مستقبِل». فالبثُّ هنا أصليٌّ لا يحتاج الويب.
///
/// **وفي حدود Apple لا فوقها** (Guideline 2.5.4 · 5.1.5):
/// - يبدأ **حين يضغط الكبتنُ «استقبال» وحدَه** ويقف مع كلِّ فصلٍ وعند «إيقاف الاستقبال»؛
/// - `showsBackgroundLocationIndicator`: **الشريطُ الأزرقُ ظاهرٌ** طوال البثّ — فلا بثَّ خفيّ؛
/// - لا يُطلب «دائماً» إلا بعد شاشة الإفصاح (`BACKGROUND_STEP`) — والبثُّ يعمل بإذن «أثناء الاستخدام» أيضاً
///   ما دام قد بدأ والتطبيقُ ظاهر (iOS يبقيه بالشريط الأزرق)؛
/// - **ولا يعمل بعد أن يُزيح الكبتنُ التطبيقَ من المبدّل** — سلوكُ iOS، وهو حدُّ أندرويد نفسُه (الشاشةُ تقوله).
///
/// **وكلُّ عشرين ثانيةً نبضةٌ** (`BROADCAST_MS` في أندرويد) — التحديثاتُ تصل كلَّ ثانيةٍ والإرسالُ مخنوقٌ إليها.
@objc(OnlineServicePlugin)
public class OnlineServicePlugin: CAPPlugin, CAPBridgedPlugin, CLLocationManagerDelegate {
    public let identifier = "OnlineServicePlugin"
    public let jsName = "OnlineService"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "start", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "degraded", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "stop", returnType: CAPPluginReturnPromise),
    ]

    private static let broadcastInterval: TimeInterval = 20

    private var manager: CLLocationManager?
    private var endpoint: URL?
    private var token: String?
    private var lastSent: Date = .distantPast
    private var lastFix: CLLocation?
    private var beacon: Timer?

    @objc func start(_ call: CAPPluginCall) {
        guard let raw = call.getString("endpoint"), let url = URL(string: raw) else {
            call.reject("لا عنوانَ للبثّ")
            return
        }
        endpoint = url
        token = call.getString("token")
        DispatchQueue.main.async {
            let manager = self.manager ?? CLLocationManager()
            manager.delegate = self
            manager.activityType = .automotiveNavigation
            manager.desiredAccuracy = kCLLocationAccuracyBest
            manager.distanceFilter = kCLDistanceFilterNone
            manager.pausesLocationUpdatesAutomatically = false
            // **يتطلّب `UIBackgroundModes: location` في البيان** — وبيانُ الكبتن وحدَه يحمله
            if Bundle.main.object(forInfoDictionaryKey: "UIBackgroundModes").flatMap({ $0 as? [String] })?.contains("location") == true {
                manager.allowsBackgroundLocationUpdates = true
                manager.showsBackgroundLocationIndicator = true
            }
            manager.startUpdatingLocation()
            self.manager = manager
            self.lastSent = .distantPast
            // **نبضةٌ ولو لم يتحرّك**: كبتنٌ واقفٌ عند إشارةٍ لا تصل منه تحديثات، والحضورُ ينقضي بالصمت
            self.beacon?.invalidate()
            self.beacon = Timer.scheduledTimer(withTimeInterval: Self.broadcastInterval, repeats: true) { [weak self] _ in
                self?.sendIfDue(force: true)
            }
            call.resolve()
        }
    }

    /// **لا إشعارَ دائماً على iOS يُقلب** — الشريطُ الأزرقُ هو ما يراه الكبتن، والشاشةُ تقول الحالَ حين يعود.
    @objc func degraded(_ call: CAPPluginCall) {
        call.resolve()
    }

    @objc func stop(_ call: CAPPluginCall) {
        DispatchQueue.main.async {
            self.beacon?.invalidate()
            self.beacon = nil
            if let manager = self.manager {
                manager.stopUpdatingLocation()
                manager.allowsBackgroundLocationUpdates = false
            }
            self.token = nil
            self.endpoint = nil
            call.resolve()
        }
    }

    public func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let fix = locations.last else { return }
        lastFix = fix
        sendIfDue(force: false)
    }

    private func sendIfDue(force: Bool) {
        guard let fix = lastFix, let url = endpoint, let token = token else { return }
        let elapsed = Date().timeIntervalSince(lastSent)
        if elapsed < Self.broadcastInterval - (force ? 1 : 0) { return }
        lastSent = Date()
        var request = URLRequest(url: url, timeoutInterval: 10)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        // **ترويسةٌ مستقلّةٌ لا `Authorization`** (§23.4) — كأندرويد حرفاً
        request.setValue(token, forHTTPHeaderField: "X-Presence-Token")
        var body: [String: Any] = ["lat": fix.coordinate.latitude, "lng": fix.coordinate.longitude]
        body["heading"] = fix.course >= 0 ? fix.course : NSNull()
        request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        URLSession.shared.dataTask(with: request).resume()
    }
}
