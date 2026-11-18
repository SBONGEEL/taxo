import SwiftUI

/// **مضيفٌ فارغٌ** — يشترطه Xcode لاختبار الواجهة، ولا يُفتح: الاختبارُ يقود SpringBoard وتطبيقَ TAXO المثبَّت.
@main
struct HostApp: App {
    var body: some Scene {
        WindowGroup { Text("NativeShots") }
    }
}
