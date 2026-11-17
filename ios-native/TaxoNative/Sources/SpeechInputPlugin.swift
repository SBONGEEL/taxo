import UIKit
import Speech
import AVFoundation
import Capacitor

/// **البحثُ بالصوت للراكب** — نظيرُ `SpeechInputPlugin.java` بالعقد نفسِه (`listen({language, prompt}) → {text}`).
///
/// أندرويد يعرض حوارَ النظام؛ **وiOS لا حوارَ له** — فتُعرض ورقةٌ صغيرةٌ بنصّ `prompt` وزرّين («تمّ» · «إلغاء»)،
/// ويُفهم الكلامُ على الجهاز حين يدعمه (`requiresOnDeviceRecognition` إن أمكن)، وينتهي وحدَه بعد ثانيتين من الصمت.
/// **والإلغاءُ رفضٌ لا نصٌّ فارغ** — كما يرفض أندرويد حين يُغلق الحوار.
@objc(SpeechInputPlugin)
public class SpeechInputPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "SpeechInputPlugin"
    public let jsName = "SpeechInput"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "listen", returnType: CAPPluginReturnPromise),
    ]

    private let engine = AVAudioEngine()
    private var task: SFSpeechRecognitionTask?
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var sheet: UIAlertController?
    private var silence: Timer?
    private var best = ""
    private var pending: CAPPluginCall?

    @objc func listen(_ call: CAPPluginCall) {
        let language = call.getString("language") ?? "ar"
        let prompt = call.getString("prompt") ?? "تكلّم الآن"
        SFSpeechRecognizer.requestAuthorization { status in
            guard status == .authorized else {
                call.reject("لم يُسمح بالتعرّف على الكلام", "denied")
                return
            }
            AVAudioSession.sharedInstance().requestRecordPermission { granted in
                guard granted else {
                    call.reject("لم يُسمح بالميكروفون", "denied")
                    return
                }
                DispatchQueue.main.async { self.begin(call, language: language, prompt: prompt) }
            }
        }
    }

    private func locale(for language: String) -> Locale {
        switch language.prefix(2) {
        case "fr": return Locale(identifier: "fr-FR")
        case "en": return Locale(identifier: "en-US")
        default: return Locale(identifier: "ar-SA")
        }
    }

    private func begin(_ call: CAPPluginCall, language: String, prompt: String) {
        guard pending == nil else { call.reject("استماعٌ جارٍ"); return }
        guard let recognizer = SFSpeechRecognizer(locale: locale(for: language)), recognizer.isAvailable else {
            call.reject("التعرّفُ على الكلام غيرُ متاح", "unavailable")
            return
        }
        pending = call
        best = ""
        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        if recognizer.supportsOnDeviceRecognition { request.requiresOnDeviceRecognition = true }
        self.request = request

        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.record, mode: .measurement, options: .duckOthers)
            try session.setActive(true, options: .notifyOthersOnDeactivation)
            let input = engine.inputNode
            input.removeTap(onBus: 0)
            input.installTap(onBus: 0, bufferSize: 1024, format: input.outputFormat(forBus: 0)) { buffer, _ in
                request.append(buffer)
            }
            engine.prepare()
            try engine.start()
        } catch {
            finish(cancelled: true)
            return
        }

        task = recognizer.recognitionTask(with: request) { [weak self] result, error in
            guard let self = self else { return }
            if let result = result {
                self.best = result.bestTranscription.formattedString
                DispatchQueue.main.async {
                    self.sheet?.message = self.best
                    self.armSilence()
                }
                if result.isFinal { DispatchQueue.main.async { self.finish(cancelled: false) } }
            } else if error != nil {
                DispatchQueue.main.async { self.finish(cancelled: self.best.isEmpty) }
            }
        }

        let sheet = UIAlertController(title: prompt, message: "…", preferredStyle: .alert)
        sheet.addAction(UIAlertAction(title: "إلغاء", style: .cancel) { _ in self.finish(cancelled: true) })
        sheet.addAction(UIAlertAction(title: "تمّ", style: .default) { _ in self.finish(cancelled: false) })
        self.sheet = sheet
        bridge?.viewController?.present(sheet, animated: true)
        armSilence()
    }

    private func armSilence() {
        silence?.invalidate()
        silence = Timer.scheduledTimer(withTimeInterval: best.isEmpty ? 6 : 2, repeats: false) { [weak self] _ in
            self?.finish(cancelled: false)
        }
    }

    private func finish(cancelled: Bool) {
        guard let call = pending else { return }
        pending = nil
        silence?.invalidate()
        engine.stop()
        engine.inputNode.removeTap(onBus: 0)
        request?.endAudio()
        task?.cancel()
        task = nil
        request = nil
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        sheet?.dismiss(animated: true)
        sheet = nil
        let text = best.trimmingCharacters(in: .whitespacesAndNewlines)
        if cancelled || text.isEmpty {
            call.reject("أُلغي", "cancelled")
        } else {
            call.resolve(["text": text])
        }
    }
}
