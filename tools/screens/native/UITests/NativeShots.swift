import XCTest

/// **لقطاتُ ما يرسمه iOS لا الصفحة** (أمرُ المالك ٢٠٢٦-١١-١٨) — يقود SpringBoard وتطبيقَ TAXO المثبَّت ويصوّر الشاشةَ كلَّها:
/// Dynamic Island مضغوطةً وممدودة · النشاطُ الحيُّ على شاشة القفل · اختصاراتُ الأيقونة · أداتا الشاشة الرئيسيّة (صغيرةٌ ومتوسّطة) · المكالمةُ الواردة.
///
/// **الأصليُّ يُنادى بجسر التطبيق نفسِه** (`harness.js › native` عبر `server.mjs`) ببياناتِ تجربةٍ مكتوبةٍ هنا — لا مستخدمَ حقيقيّ ولا خادم.
/// **وكلُّ صفٍّ يُكتب في `native.json` بما وقع** — ما لم يُبلغ يُقال «لم يُبلغ» بعلّته، وتُحفظ شجرةُ SpringBoard بجانبه لتُقرأ.
final class NativeShots: XCTestCase {
    private let env = ProcessInfo.processInfo.environment
    private lazy var out = env["SHOTS_DIR"] ?? NSTemporaryDirectory()
    private lazy var bundle = env["APP_BUNDLE"] ?? ""
    private lazy var kind = env["APP_KIND"] ?? "rider"
    private lazy var hasIsland = env["HAS_ISLAND"] == "1"
    private let server = "http://127.0.0.1:8787"
    private let springboard = XCUIApplication(bundleIdentifier: "com.apple.springboard")
    private var rows: [[String: Any]] = []

    override func setUp() {
        continueAfterFailure = true
    }

    // MARK: - الأدوات

    /// أمرٌ إلى الصفحة وانتظارُ جوابها — كما يفعل `steps.mjs`
    @discardableResult
    private func page(_ body: [String: Any]) -> (ok: Bool, note: String) {
        guard let sent = request("POST", "/__shot", body), let id = sent["id"] as? Int else { return (false, "لا خادم") }
        for _ in 0..<40 {
            Thread.sleep(forTimeInterval: 0.5)
            if let ack = request("GET", "/__shot/ack", nil), (ack["id"] as? Int) == id {
                return ((ack["ok"] as? Bool) ?? false, (ack["note"] as? String) ?? "")
            }
        }
        return (false, "لا جوابَ من الصفحة خلال ٢٠ ث")
    }

    private func native(_ plugin: String, _ method: String, _ options: [String: Any], after: Int? = nil) -> (ok: Bool, note: String) {
        var body: [String: Any] = ["kind": "native", "plugin": plugin, "method": method, "options": options]
        if let after = after { body["after"] = after }
        return page(body)
    }

    private func request(_ method: String, _ path: String, _ body: [String: Any]?) -> [String: Any]? {
        guard let url = URL(string: server + path) else { return nil }
        // **١٥ ث لا ٥**: أوّلُ أمرٍ بعد صفحة القياس وصل الصفحةَ ونُفّذ (`↩ 102 ✓ Launcher.setShortcuts`) وجوابُه تأخّر فقُرئ «لا خادم» (44353687380)
        var req = URLRequest(url: url, timeoutInterval: 15)
        req.httpMethod = method
        if let body = body { req.httpBody = try? JSONSerialization.data(withJSONObject: body) }
        var result: [String: Any]?
        let done = DispatchSemaphore(value: 0)
        URLSession.shared.dataTask(with: req) { data, _, _ in
            if let data = data { result = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] }
            done.signal()
        }.resume()
        _ = done.wait(timeout: .now() + 16)
        return result
    }

    /// لقطةُ الشاشة كلِّها (لا التطبيق) — ملفٌّ في مجلّد اللقطات، ومرفقٌ في النتيجة إن تعذّرت الكتابة
    private func shot(_ name: String, _ label: String, ok: Bool = true, note: String = "") {
        let image = XCUIScreen.main.screenshot()
        let file = "\(name).png"
        var written = true
        do {
            try image.pngRepresentation.write(to: URL(fileURLWithPath: out).appendingPathComponent(file))
        } catch {
            written = false
            let attachment = XCTAttachment(screenshot: image)
            attachment.name = name
            attachment.lifetime = .keepAlways
            add(attachment)
        }
        rows.append(["name": name, "label": label, "file": file, "reached": ok, "notes": [note, written ? "" : "مرفقٌ لا ملفّ"].filter { !$0.isEmpty }])
        print("📸 \(ok ? "✓" : "✗") \(name) — \(label) \(note)")
    }

    private func missed(_ name: String, _ label: String, _ why: String) {
        rows.append(["name": name, "label": label, "file": "", "reached": false, "notes": [why]])
        print("✗ \(name) — \(label): \(why)")
    }

    /// **شجرةُ SpringBoard تُحفظ عند كلِّ تعثّر** — فيُقرأ ما كان على الشاشة بأسمائه، لا يُخمَّن
    private func dump(_ tag: String) {
        let text = springboard.debugDescription
        try? text.write(to: URL(fileURLWithPath: out).appendingPathComponent("springboard-\(tag).txt"), atomically: true, encoding: .utf8)
    }

    private func save() {
        if let data = try? JSONSerialization.data(withJSONObject: rows, options: [.prettyPrinted]) {
            try? data.write(to: URL(fileURLWithPath: out).appendingPathComponent("native.json"))
        }
    }

    /// أوّلُ عنصرٍ ظاهرٍ بأحد الأسماء — زرّاً أو أيَّ عنصر
    private func element(_ labels: [String], timeout: TimeInterval = 4) -> XCUIElement? {
        let deadline = Date().addingTimeInterval(timeout)
        repeat {
            for label in labels {
                // **وتسميةُ SpringBoard قد تبدأ بمسافة** (« Add Widget» — 44353687380)، فتُقبل منتهيةً بالاسم
                let predicate = NSPredicate(format: "label ==[c] %@ OR identifier ==[c] %@ OR label ENDSWITH[c] %@", label, label, " " + label)
                for query in [springboard.buttons, springboard.descendants(matching: .any)] {
                    let match = query.matching(predicate).firstMatch
                    if match.exists && match.isHittable { return match }
                }
            }
            Thread.sleep(forTimeInterval: 0.4)
        } while Date() < deadline
        return nil
    }

    private func lock() -> Bool {
        let selector = NSSelectorFromString("pressLockButton")
        guard XCUIDevice.shared.responds(to: selector) else { return false }
        XCUIDevice.shared.perform(selector)
        return true
    }

    /// إلى الشاشة الرئيسيّة مفتوحةً — من القفل أو من تطبيق
    private func home() {
        XCUIDevice.shared.press(.home)
        Thread.sleep(forTimeInterval: 1.2)
        if !springboard.icons.firstMatch.isHittable {
            springboard.swipeUp()
            Thread.sleep(forTimeInterval: 1)
            XCUIDevice.shared.press(.home)
            Thread.sleep(forTimeInterval: 1.2)
        }
    }

    /// أيقونةُ TAXO — والتطبيقُ الجديدُ قد يكون في الصفحة الثانية
    private func appIcon() -> XCUIElement? {
        let predicate = NSPredicate(format: "label BEGINSWITH[c] %@", "TAXO")
        for _ in 0..<4 {
            let icon = springboard.icons.matching(predicate).firstMatch
            if icon.exists && icon.isHittable { return icon }
            springboard.swipeLeft()
            Thread.sleep(forTimeInterval: 1)
        }
        return nil
    }

    // MARK: - بياناتُ التجربة

    private var shortcutItems: [[String: String]] {
        kind == "driver"
            ? [["id": "go_online", "label": "اتصل الآن", "action": "go_online"], ["id": "earnings", "label": "أرباحي", "action": "earnings"]]
            : [["id": "ride_home", "label": "اطلب رحلة إلى البيت", "action": "ride_home"], ["id": "wallet", "label": "محفظتي", "action": "wallet"]]
    }

    /// **نصوصُ `rideActivity` نفسُها** (`lib/native-ios-logic.ts`) لرحلةٍ مقبولة — بأسماءٍ وعناوينَ تجريبيّة
    private var activity: [String: Any] {
        kind == "driver"
            ? ["rideId": "shots-ride", "title": "في الطريق إلى الراكب", "detail": "دوار الداخلية، عمّان", "plate": "", "step": 1]
            : ["rideId": "shots-ride", "title": "الكبتن في الطريق إليك", "detail": "كبتن تجريبي · Toyota · Corolla · أبيض", "plate": "10-12345", "step": 1]
    }

    private var caller: String { kind == "driver" ? "راكب تجريبي" : "كبتن تجريبي" }

    // MARK: - المسار

    func testNativeSurfaces() throws {
        let app = XCUIApplication(bundleIdentifier: bundle)
        app.activate()
        Thread.sleep(forTimeInterval: 5)

        let shortcuts = native("Launcher", "setShortcuts", ["items": shortcutItems])
        let live = native("LiveActivity", "show", activity)
        print("· setShortcuts: \(shortcuts) · LiveActivity.show: \(live)")
        Thread.sleep(forTimeInterval: 2)

        islandShots(live: live)
        lockShots(live: live)
        quickActions(shortcuts: shortcuts)
        widgets()
        callShots(app: app)

        _ = native("LiveActivity", "end", ["rideId": "shots-ride"])
        save()
    }

    private func islandShots(live: (ok: Bool, note: String)) {
        guard hasIsland else {
            missed("island-compact", "Dynamic Island — مضغوطة", "iPhone SE بلا Dynamic Island (زرُّ الشاشة الرئيسيّة) — النشاطُ الحيُّ يظهر على شاشة القفل وحدَها")
            missed("island-expanded", "Dynamic Island — ممدودة", "iPhone SE بلا Dynamic Island")
            return
        }
        home()
        Thread.sleep(forTimeInterval: 2)
        shot("island-compact", "Dynamic Island — مضغوطة", ok: live.ok, note: live.note)
        // **الضغطُ المطوَّلُ على الجزيرة يمدّها** — موضعُها أعلى الوسط (≈ ٣٧ نقطة من الحافّة)
        springboard.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0)).withOffset(CGVector(dx: 0, dy: 37)).press(forDuration: 1.2)
        Thread.sleep(forTimeInterval: 1.2)
        shot("island-expanded", "Dynamic Island — ممدودة", ok: live.ok, note: live.note)
        dump("island")
        springboard.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.75)).tap()
        Thread.sleep(forTimeInterval: 1)
    }

    private func lockShots(live: (ok: Bool, note: String)) {
        guard lock() else {
            missed("lock-live-activity", "النشاطُ الحيُّ على شاشة القفل", "لا زرَّ قفلٍ في هذا الإصدار من XCTest")
            return
        }
        Thread.sleep(forTimeInterval: 1.5)
        // **الإيقاظُ يُظهر شاشةَ القفل** ولا يفتحها
        XCUIDevice.shared.press(.home)
        Thread.sleep(forTimeInterval: 2.5)
        // **سؤالُ iOS الأوّل «Allow Live Activities…?»** يغطّي نصفَ البطاقة — يُجاب كما يجيبه صاحبُ الهاتف، ثمّ اللقطة
        if let allow = element(["Allow"], timeout: 2) {
            allow.tap()
            Thread.sleep(forTimeInterval: 1.5)
        }
        shot("lock-live-activity", "النشاطُ الحيُّ على شاشة القفل", ok: live.ok, note: live.note)
        dump("lock")
        home()
    }

    private func quickActions(shortcuts: (ok: Bool, note: String)) {
        home()
        guard let icon = appIcon() else {
            dump("icon")
            missed("quick-actions", "اختصاراتُ الأيقونة", "لم تُوجد أيقونةُ TAXO في الشاشة الرئيسيّة")
            return
        }
        icon.press(forDuration: 1.5)
        Thread.sleep(forTimeInterval: 1.5)
        shot("quick-actions", "اختصاراتُ الأيقونة (ضغطٌ مطوَّل)", ok: shortcuts.ok, note: shortcuts.note)
        dump("quick-actions")
        XCUIDevice.shared.press(.home)
        Thread.sleep(forTimeInterval: 1)
    }

    /// **أداتا الشاشة الرئيسيّة كما تضيفهما اليد**: ضغطٌ مطوَّل ⇐ «تعديل» ⇐ «إضافة أداة» ⇐ بحثٌ عن TAXO ⇐ الحجم ⇐ «إضافة»
    private func widgets() {
        var notes: [String] = []
        var added = 0
        for (index, size) in ["small", "medium"].enumerated() {
            home()
            guard let icon = appIcon() else { notes.append("لا أيقونة"); break }
            icon.press(forDuration: 1.5)
            Thread.sleep(forTimeInterval: 1)
            // في القائمة «Edit Home Screen»، وإلا فالضغطُ المطوَّلُ نفسُه أدخل وضعَ التحرير
            element(["Edit Home Screen"], timeout: 2)?.tap()
            Thread.sleep(forTimeInterval: 1)
            guard let edit = element(["Edit", "edit-button", "Add Widget", "add-widget-button"], timeout: 4) else {
                dump("widget-edit-\(size)"); notes.append("\(size): لا زرَّ «Edit»"); continue
            }
            let editLabel = edit.label
            edit.tap()
            Thread.sleep(forTimeInterval: 1)
            if editLabel.lowercased() == "edit" {
                guard let addWidget = element(["Add Widget"], timeout: 3) else {
                    dump("widget-menu-\(size)"); notes.append("\(size): لا «Add Widget»"); continue
                }
                addWidget.tap()
                Thread.sleep(forTimeInterval: 2)
            }
            let search = springboard.searchFields.firstMatch
            if search.waitForExistence(timeout: 4) {
                search.tap()
                search.typeText("TAXO")
                Thread.sleep(forTimeInterval: 2)
            }
            let result = springboard.descendants(matching: .any).matching(NSPredicate(format: "label BEGINSWITH[c] %@", "TAXO")).allElementsBoundByIndex.first { $0.isHittable }
            guard let result = result else {
                dump("widget-search-\(size)"); notes.append("\(size): لا نتيجةَ لـTAXO في معرض الأدوات"); continue
            }
            result.tap()
            Thread.sleep(forTimeInterval: 2)
            if index == 1 {
                springboard.swipeLeft()
                Thread.sleep(forTimeInterval: 1.2)
            }
            if index == 0 || size == "medium" {
                shot("widget-gallery-\(size)", size == "small" ? "معرضُ الأدوات — صغيرة" : "معرضُ الأدوات — متوسّطة")
            }
            guard let add = element(["Add Widget", "add-widget-button"], timeout: 3) else {
                dump("widget-add-\(size)"); notes.append("\(size): لا زرَّ «Add Widget» في صفحة الحجم"); continue
            }
            add.tap()
            Thread.sleep(forTimeInterval: 1.5)
            element(["Done"], timeout: 3)?.tap()
            Thread.sleep(forTimeInterval: 1.5)
            added += 1
        }
        home()
        // الأداتان تُوضعان أعلى الصفحة التي كانت ظاهرة — فيُبحث عنهما في الصفحات
        for _ in 0..<3 {
            if springboard.descendants(matching: .any).matching(NSPredicate(format: "label CONTAINS[c] %@", "TAXO")).count > 1 { break }
            springboard.swipeLeft()
            Thread.sleep(forTimeInterval: 1)
        }
        shot("widgets", "أداتا الشاشة الرئيسيّة — صغيرةٌ ومتوسّطة", ok: added == 2, note: notes.joined(separator: " · "))
        dump("widgets")
    }

    /// **أظهر iOS شاشةَ المكالمة؟** — زرُّ ردٍّ أو رفضٍ في SpringBoard، لا جوابُ الملحق
    private func callVisible() -> Bool {
        let predicate = NSPredicate(format: "label CONTAINS[c] 'Decline' OR label CONTAINS[c] 'Accept' OR label CONTAINS[c] 'slide to answer' OR label CONTAINS[c] 'رفض' OR label CONTAINS[c] 'رد'")
        return springboard.buttons.matching(predicate).count > 0 || springboard.sliders.count > 0
    }

    private let noCallUI = "محاكي iOS لا يرسم شاشةَ مكالمة CallKit (لا زرَّ ردٍّ ولا رفض في SpringBoard) — تُصوَّر على iPhone حقيقيّ"

    /// **المكالمةُ الواردة** — والتطبيقُ ظاهر (شريطُ iOS في الأعلى)، ثمّ والجهازُ مقفل (شاشةُ المكالمة كاملة)
    private func callShots(app: XCUIApplication) {
        app.activate()
        Thread.sleep(forTimeInterval: 3)
        let banner = native("CallKit", "reportIncoming", ["callId": "shots-call-1", "name": caller])
        Thread.sleep(forTimeInterval: 2.5)
        let bannerSeen = callVisible()
        shot("call-banner", "مكالمةٌ واردة والتطبيقُ مفتوح", ok: banner.ok && bannerSeen, note: bannerSeen ? banner.note : noCallUI)
        dump("call-banner")
        _ = native("CallKit", "end", ["callId": "shots-call-1"])
        Thread.sleep(forTimeInterval: 2)

        // **والجهازُ مقفل**: النداءُ مؤجَّلٌ في الصفحة ثانيتين، ثمّ يُقفل الجهازُ فتصل المكالمةُ إليه مقفلاً
        let later = native("CallKit", "reportIncoming", ["callId": "shots-call-2", "name": caller], after: 2500)
        guard lock() else {
            missed("call-lock", "مكالمةٌ واردة والجهازُ مقفل", "لا زرَّ قفل")
            return
        }
        Thread.sleep(forTimeInterval: 6)
        let lockSeen = callVisible()
        shot("call-lock", "مكالمةٌ واردة والجهازُ مقفل", ok: later.ok && lockSeen, note: lockSeen ? later.note : noCallUI)
        dump("call-lock")
        // الرفضُ بزرِّ القفل مرّتين كما يرفضها صاحبُ الهاتف
        _ = lock(); Thread.sleep(forTimeInterval: 0.5); _ = lock()
        Thread.sleep(forTimeInterval: 1.5)
        home()
    }
}
