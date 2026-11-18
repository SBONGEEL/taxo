import Foundation
import CallKit
import AVFoundation
import Capacitor

/// **المكالمةُ داخل التطبيق «مكالمةً حقيقيّة» على iOS** (CallKit) — للراكب والكبتن.
///
/// المكالمةُ نفسُها WebRTC في الويب كما هي (`lib/call-session.ts`)، **وهذا يُعلنها للنظام**: الشريطُ الأخضرُ
/// في أعلى الشاشة، وزرُّ الإنهاء في «مركز التحكّم»، وأولويّةُ الصوت فلا يقطعها تطبيقٌ آخر، وسلوكُ «مكالمةٍ
/// على الخطّ» حين تصل مكالمةٌ هاتفيّة.
///
/// **وما لا يُبنى هنا — بقصدٍ ومكتوباً**:
/// - **شاشةُ المكالمة الواردة والتطبيقُ مغلق** تحتاج دفعَ VoIP (PushKit) من الخادم إلى APNs مباشرةً بمفتاح
///   حساب Apple — **وApple تُلزم كلَّ دفعِ VoIP بإعلان مكالمةٍ فوراً وإلا أوقفت الدفعَ للتطبيق**. حتى يُبنى ذلك
///   تصل المكالمةُ والتطبيقُ مغلقٌ **إشعاراً حسّاساً للوقت يرنّ بنغمة المكالمة وبزرّي «ردّ» و«رفض»** (`TAXO_CALL`).
/// - **لا يُسجَّل الاسمُ في «سجلّ المكالمات»** (`includesCallsInRecents = false`): اسمُ راكبٍ أو كبتنٍ في سجلّ
///   هاتف الطرف الآخر بعد انتهاء الرحلة كشفٌ لا يُنتظر.
///
/// **والصوتُ ملكُ WebKit لا ملكُنا**: لا يُضبط `AVAudioSession` هنا — وهو أوّلُ ما يُقاس على iPhone حقيقيّ
/// (قائمةُ TestFlight). والرجوعُ مفتاحٌ واحد: `TaxoCallKit = false` في `Info.plist`.
@objc(CallKitPlugin)
public class CallKitPlugin: CAPPlugin, CAPBridgedPlugin, CXProviderDelegate {
    public let identifier = "CallKitPlugin"
    public let jsName = "CallKit"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "available", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "startOutgoing", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "reportIncoming", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "reportConnected", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "end", returnType: CAPPluginReturnPromise),
    ]

    private lazy var provider: CXProvider = {
        let name = (Bundle.main.object(forInfoDictionaryKey: "CFBundleDisplayName") as? String) ?? "TAXO"
        let configuration: CXProviderConfiguration
        if #available(iOS 14.0, *) {
            configuration = CXProviderConfiguration()
        } else {
            configuration = CXProviderConfiguration(localizedName: name)
        }
        configuration.supportsVideo = false
        configuration.maximumCallGroups = 1
        configuration.maximumCallsPerCallGroup = 1
        configuration.supportedHandleTypes = [.generic]
        configuration.includesCallsInRecents = false
        if Bundle.main.url(forResource: "taxo_call", withExtension: "caf") != nil {
            configuration.ringtoneSound = "taxo_call.caf"
        }
        let provider = CXProvider(configuration: configuration)
        provider.setDelegate(self, queue: nil)
        return provider
    }()
    private let controller = CXCallController()
    /// معرّفُ مكالمة الخادم ← معرّفُ CallKit
    private var calls: [String: UUID] = [:]
    /// **ما أنهاه الويبُ لا يُعاد إليه حدثاً** — وإلا أنهى الويبُ مكالمةً منتهيةً مرّتين
    private var endingFromWeb: Set<UUID> = []

    private var enabled: Bool {
        (Bundle.main.object(forInfoDictionaryKey: "TaxoCallKit") as? Bool) ?? false
    }

    @objc func available(_ call: CAPPluginCall) {
        call.resolve(["available": enabled])
    }

    @objc func startOutgoing(_ call: CAPPluginCall) {
        guard enabled, let callId = call.getString("callId") else { call.resolve(); return }
        let uuid = UUID()
        calls[callId] = uuid
        let handle = CXHandle(type: .generic, value: call.getString("name") ?? "TAXO")
        let action = CXStartCallAction(call: uuid, handle: handle)
        controller.request(CXTransaction(action: action)) { error in
            if let error = error { call.reject("تعذّر إعلانُ المكالمة", nil, error) } else { call.resolve() }
        }
    }

    @objc func reportIncoming(_ call: CAPPluginCall) {
        guard enabled, let callId = call.getString("callId") else { call.resolve(); return }
        let uuid = calls[callId] ?? UUID()
        calls[callId] = uuid
        let update = CXCallUpdate()
        update.remoteHandle = CXHandle(type: .generic, value: call.getString("name") ?? "TAXO")
        update.localizedCallerName = call.getString("name")
        update.hasVideo = false
        update.supportsHolding = false
        update.supportsGrouping = false
        update.supportsUngrouping = false
        update.supportsDTMF = false
        provider.reportNewIncomingCall(with: uuid, update: update) { error in
            if let error = error { call.reject("تعذّر إعلانُ المكالمة", nil, error) } else { call.resolve() }
        }
    }

    @objc func reportConnected(_ call: CAPPluginCall) {
        guard enabled, let callId = call.getString("callId"), let uuid = calls[callId] else { call.resolve(); return }
        provider.reportOutgoingCall(with: uuid, connectedAt: Date())
        call.resolve()
    }

    @objc func end(_ call: CAPPluginCall) {
        guard enabled, let callId = call.getString("callId"), let uuid = calls.removeValue(forKey: callId) else {
            call.resolve()
            return
        }
        endingFromWeb.insert(uuid)
        controller.request(CXTransaction(action: CXEndCallAction(call: uuid))) { error in
            if error != nil {
                // لم يعرفها النظام (انتهت قبل أن تُعلن) — يُقال للنظام إنها انتهت ولا يُعاد شيء
                self.provider.reportCall(with: uuid, endedAt: Date(), reason: .remoteEnded)
            }
            call.resolve()
        }
    }

    private func callId(of uuid: UUID) -> String? {
        calls.first { $0.value == uuid }?.key
    }

    // MARK: CXProviderDelegate

    public func providerDidReset(_ provider: CXProvider) {
        for (callId, _) in calls { notifyListeners("callEnded", data: ["callId": callId]) }
        calls.removeAll()
    }

    public func provider(_ provider: CXProvider, perform action: CXStartCallAction) {
        provider.reportOutgoingCall(with: action.callUUID, startedConnectingAt: Date())
        action.fulfill()
    }

    public func provider(_ provider: CXProvider, perform action: CXAnswerCallAction) {
        if let callId = callId(of: action.callUUID) {
            notifyListeners("callAnswered", data: ["callId": callId])
        }
        action.fulfill()
    }

    public func provider(_ provider: CXProvider, perform action: CXEndCallAction) {
        let fromWeb = endingFromWeb.remove(action.callUUID) != nil
        if !fromWeb, let callId = callId(of: action.callUUID) {
            calls.removeValue(forKey: callId)
            notifyListeners("callEnded", data: ["callId": callId])
        }
        action.fulfill()
    }

    public func provider(_ provider: CXProvider, perform action: CXSetMutedCallAction) {
        if let callId = callId(of: action.callUUID) {
            notifyListeners("callMuted", data: ["callId": callId, "muted": action.isMuted])
        }
        action.fulfill()
    }

    public func provider(_ provider: CXProvider, didActivate audioSession: AVAudioSession) {}
    public func provider(_ provider: CXProvider, didDeactivate audioSession: AVAudioSession) {}
}
