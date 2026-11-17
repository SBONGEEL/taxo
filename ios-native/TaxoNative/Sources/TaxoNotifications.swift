import UIKit
import UserNotifications

/// **فئاتُ الإشعار وأزرارُها** — «إشعاراتٌ غنيّةٌ بأزرار» على iOS بلا امتدادٍ منفصل.
///
/// | الفئة | الأزرار | من يرسلها |
/// |---|---|---|
/// | `TAXO_OFFER` | قبول (يفتح التطبيق) · رفض (في الخلفية) | الخادم (`aps.category`) والتطبيقُ نفسُه (`OfferAlert.show`) |
/// | `TAXO_CALL` | ردّ (يفتح التطبيق) · رفض | الخادم لمكالمةٍ واردةٍ والتطبيقُ مغلق |
/// | `TAXO_RIDE` | عرض الرحلة | أحداثُ الرحلة للراكب (وصل الكبتن · بدأت · انتهت) |
///
/// **والاسمُ هنا يطابق `app/services/push/fcm.py::IOS_CATEGORIES` حرفاً** — واختلافُ حرفٍ يُسقط الأزرارَ بصمت.
public enum TaxoNotificationCategories {
    public static let offer = "TAXO_OFFER"
    public static let call = "TAXO_CALL"
    public static let ride = "TAXO_RIDE"

    public static let accept = "TAXO_ACCEPT"
    public static let decline = "TAXO_DECLINE"
    public static let answer = "TAXO_ANSWER"
    public static let reject = "TAXO_REJECT"
    public static let open = "TAXO_OPEN"

    /// **صوتُ الطلب** — `taxo_request.caf` من أصوات أندرويد نفسِها (`res/raw/taxo_request.ogg`) محوّلةً،
    /// ودون ٣٠ ثانية (حدُّ Apple لصوت الإشعار). **وغيابُه يُسقط إلى صوت النظام لا إلى الصمت.**
    static var offerSound: UNNotificationSound {
        UNNotificationSound(named: UNNotificationSoundName("taxo_request.caf"))
    }

    public static func register() {
        let offerCategory = UNNotificationCategory(
            identifier: Self.offer,
            actions: [
                UNNotificationAction(identifier: Self.accept, title: "قبول", options: [.foreground]),
                UNNotificationAction(identifier: Self.decline, title: "رفض", options: [.destructive]),
            ],
            intentIdentifiers: [],
            options: []
        )
        let callCategory = UNNotificationCategory(
            identifier: Self.call,
            actions: [
                UNNotificationAction(identifier: Self.answer, title: "ردّ", options: [.foreground]),
                UNNotificationAction(identifier: Self.reject, title: "رفض", options: [.destructive]),
            ],
            intentIdentifiers: [],
            options: []
        )
        let rideCategory = UNNotificationCategory(
            identifier: Self.ride,
            actions: [UNNotificationAction(identifier: Self.open, title: "عرض الرحلة", options: [.foreground])],
            intentIdentifiers: [],
            options: []
        )
        UNUserNotificationCenter.current().setNotificationCategories([offerCategory, callCategory, rideCategory])
    }
}

/// **مندوبٌ يلفّ مندوبَ Capacitor ولا يستبدله** — يلتقط زرَّي «قبول»/«رفض» بطاقةِ الطلب فيقبل بالشبكة
/// **قبل أن يُفتح التطبيق** (كما يفعل `OfferApi.java`)، ويمرّر كلَّ ما عداهما كما كان: الضغطُ على الإشعار،
/// وأزرارُ المكالمة، وإشعاراتُ التطبيق وهو ظاهر — فتبلغ `pushNotificationActionPerformed` في الويب كما اليوم.
final class TaxoNotificationDelegate: NSObject, UNUserNotificationCenterDelegate {
    private weak var forward: UNUserNotificationCenterDelegate?

    init(forwardingTo forward: UNUserNotificationCenterDelegate?) {
        self.forward = forward
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        if let forward = forward,
           forward.responds(to: #selector(UNUserNotificationCenterDelegate.userNotificationCenter(_:willPresent:withCompletionHandler:))) {
            forward.userNotificationCenter?(center, willPresent: notification, withCompletionHandler: completionHandler)
        } else {
            completionHandler([])
        }
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                didReceive response: UNNotificationResponse,
                                withCompletionHandler completionHandler: @escaping () -> Void) {
        let info = response.notification.request.content.userInfo
        let rideId = (info["ride_id"] as? String) ?? ""
        switch response.actionIdentifier {
        case TaxoNotificationCategories.decline where !rideId.isEmpty:
            OfferSession.post(rideId: rideId, action: "decline") { _ in
                DispatchQueue.main.async { completionHandler() }
            }
            return
        case TaxoNotificationCategories.accept where !rideId.isEmpty:
            // **يقبل ثمّ يفتح** — والفتحُ يقع في الحالين (`.foreground`)، والويبُ يجد الرحلةَ مقبولةً أو العرضَ قائماً
            OfferSession.post(rideId: rideId, action: "accept") { _ in }
        default:
            break
        }
        if let forward = forward,
           forward.responds(to: #selector(UNUserNotificationCenterDelegate.userNotificationCenter(_:didReceive:withCompletionHandler:))) {
            forward.userNotificationCenter?(center, didReceive: response, withCompletionHandler: completionHandler)
        } else {
            completionHandler()
        }
    }
}
