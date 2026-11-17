import Foundation
import Capacitor
#if canImport(ActivityKit)
import ActivityKit
#endif

/// **تتبّعُ الرحلة على شاشة القفل وفي Dynamic Island** (Live Activities، iOS 16.1+).
///
/// يبدأ حين يُقبل الطلب، ويتحدّث مع كلِّ تغيّرٍ في الحال، وينتهي مع نهاية الرحلة — **والويبُ يقرّر النصَّ**
/// (`lib/native-ios.ts`)، وهذا يرسله إلى النظام وحدَه.
///
/// **وحدُّه مكتوب**: يتحدّث ما دام التطبيقُ يعمل. **وتحديثُه والتطبيقُ معلّقٌ في الخلفية يحتاج دفعاً من الخادم**
/// (`apns-push-type: liveactivity`) بمفتاح APNs من حساب Apple — بندٌ بعد الحساب. وحتى ذلك يبقى آخرُ حالٍ
/// مرسومةً، **وتصير «قديمةً» بعد عشر دقائق** (`staleDate`) فلا يُقرأ وقتٌ مضى على أنه الآن.
@objc(LiveActivityPlugin)
public class LiveActivityPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "LiveActivityPlugin"
    public let jsName = "LiveActivity"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "available", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "show", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "end", returnType: CAPPluginReturnPromise),
    ]

    @objc func available(_ call: CAPPluginCall) {
        #if canImport(ActivityKit)
        if #available(iOS 16.1, *) {
            call.resolve(["available": ActivityAuthorizationInfo().areActivitiesEnabled])
            return
        }
        #endif
        call.resolve(["available": false])
    }

    /// **يبدأ أو يحدّث** — نداءٌ واحدٌ لكلِّ حال، فلا يحتاج الويبُ أن يعرف أبدأ النشاطُ أم لا.
    @objc func show(_ call: CAPPluginCall) {
        #if canImport(ActivityKit)
        if #available(iOS 16.2, *) {
            guard let rideId = call.getString("rideId") else { call.reject("لا رحلة"); return }
            let state = TaxoRideAttributes.ContentState(
                title: call.getString("title") ?? "",
                detail: call.getString("detail") ?? "",
                plate: call.getString("plate") ?? "",
                step: call.getInt("step") ?? 0
            )
            let content = ActivityContent(state: state, staleDate: Date().addingTimeInterval(600))
            Task {
                for other in Activity<TaxoRideAttributes>.activities where other.attributes.rideId != rideId {
                    await other.end(nil, dismissalPolicy: .immediate)
                }
                if let current = Activity<TaxoRideAttributes>.activities.first(where: { $0.attributes.rideId == rideId }) {
                    await current.update(content)
                    call.resolve(["shown": true])
                    return
                }
                guard ActivityAuthorizationInfo().areActivitiesEnabled else {
                    call.resolve(["shown": false])
                    return
                }
                let attributes = TaxoRideAttributes(
                    rideId: rideId,
                    appKind: TaxoApp.kind.rawValue,
                    brand: (Bundle.main.object(forInfoDictionaryKey: "CFBundleDisplayName") as? String) ?? "TAXO"
                )
                do {
                    _ = try Activity.request(attributes: attributes, content: content, pushType: nil)
                    call.resolve(["shown": true])
                } catch {
                    call.resolve(["shown": false, "error": error.localizedDescription])
                }
            }
            return
        }
        #endif
        call.resolve(["shown": false])
    }

    @objc func end(_ call: CAPPluginCall) {
        #if canImport(ActivityKit)
        if #available(iOS 16.2, *) {
            let rideId = call.getString("rideId")
            Task {
                for activity in Activity<TaxoRideAttributes>.activities where rideId == nil || activity.attributes.rideId == rideId {
                    await activity.end(nil, dismissalPolicy: .default)
                }
                call.resolve()
            }
            return
        }
        #endif
        call.resolve()
    }
}
