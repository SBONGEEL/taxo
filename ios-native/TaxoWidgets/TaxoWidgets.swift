import WidgetKit
import SwiftUI
import ActivityKit

/// **امتدادُ الأدوات للتطبيقين** — أداةُ الشاشة الرئيسيّة، والنشاطُ الحيُّ للرحلة (شاشةُ القفل وDynamic Island).
///
/// **يُضاف إلى مشروع Xcode عند البناء** (`tools/ios/add-widgets.rb`) لا بتحريرٍ يدويٍّ لـ`project.pbxproj`،
/// ونوعُ التطبيق من `TaxoAppKind` في بيان الامتداد (`$(TAXO_APP_KIND)`).
@main
struct TaxoWidgetsBundle: WidgetBundle {
    var body: some Widget {
        TaxoQuickWidget()
        TaxoRideLiveActivity()
    }
}

enum Brand {
    static let ink = Color(red: 0x17 / 255, green: 0x1B / 255, blue: 0x20 / 255)
    static let paper = Color.white
    static let pink = Color(red: 0xD8 / 255, green: 0x1B / 255, blue: 0x73 / 255)

    static var kind: String {
        (Bundle.main.object(forInfoDictionaryKey: "TaxoAppKind") as? String) ?? "rider"
    }

    static var scheme: String { kind == "driver" ? "taxo-driver" : "taxo-rider" }

    /// **الرابطُ يفتح مساراً من قائمةٍ مسمّاة** (`TaxoDeepLink` في التطبيق) — لا مسارَ حرّاً من خارج التطبيق
    static func link(_ path: String) -> URL {
        URL(string: "\(scheme)://open\(path)")!
    }
}

// MARK: - أداةُ الشاشة الرئيسيّة

struct QuickEntry: TimelineEntry {
    let date: Date
}

struct QuickProvider: TimelineProvider {
    func placeholder(in context: Context) -> QuickEntry { QuickEntry(date: Date()) }
    func getSnapshot(in context: Context, completion: @escaping (QuickEntry) -> Void) { completion(QuickEntry(date: Date())) }
    func getTimeline(in context: Context, completion: @escaping (Timeline<QuickEntry>) -> Void) {
        completion(Timeline(entries: [QuickEntry(date: Date())], policy: .never))
    }
}

/// **أداةٌ بلا بياناتٍ حيّة بقصد**: «اطلب رحلة» للراكب و«ابدأ الاستقبال» للكبتن — زرٌّ واحدٌ يفتح الشاشةَ الصحيحة.
/// **والبياناتُ الحيّةُ (الرصيد، حالُ الاتصال)** تحتاج «مجموعةَ تطبيقات» مشتركةً تُسجَّل في حساب Apple — بندٌ بعد الحساب،
/// ولا يُعرض في الأداة رقمٌ لا يُحدَّث.
struct TaxoQuickWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "TaxoQuick", provider: QuickProvider()) { _ in
            QuickView()
        }
        .configurationDisplayName(Brand.kind == "driver" ? "TAXO كبتن" : "TAXO")
        .description(Brand.kind == "driver" ? "افتح الاستقبال بلمسة." : "اطلب رحلةً بلمسة.")
        .supportedFamilies([.systemSmall, .accessoryCircular, .accessoryRectangular])
    }
}

struct QuickView: View {
    @Environment(\.widgetFamily) private var family

    private var title: String { Brand.kind == "driver" ? "ابدأ الاستقبال" : "إلى أين؟" }
    private var symbol: String { Brand.kind == "driver" ? "steeringwheel" : "magnifyingglass" }
    private var target: URL { Brand.link("/") }

    var body: some View {
        Group {
            switch family {
            case .accessoryCircular:
                ZStack {
                    AccessoryWidgetBackground()
                    Image(systemName: symbol).font(.title2)
                }
            case .accessoryRectangular:
                HStack(spacing: 6) {
                    Image(systemName: symbol)
                    Text(title).font(.headline)
                }
            default:
                VStack(alignment: .leading, spacing: 8) {
                    Text("TAXO").font(.system(size: 15, weight: .black)).foregroundColor(Brand.paper.opacity(0.7))
                    Spacer()
                    Image(systemName: symbol).font(.system(size: 26, weight: .semibold)).foregroundColor(Brand.paper)
                    Text(title).font(.system(size: 17, weight: .bold)).foregroundColor(Brand.paper)
                        .lineLimit(1).minimumScaleFactor(0.7)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .leading)
                .padding(14)
            }
        }
        .environment(\.layoutDirection, .rightToLeft)
        .widgetURL(target)
        .widgetBackground(Brand.ink)
    }
}

extension View {
    /// iOS 17 يشترط خلفيّةً معلنة، وما قبله يرسمها بنفسه
    @ViewBuilder
    func widgetBackground(_ color: Color) -> some View {
        if #available(iOSApplicationExtension 17.0, *) {
            containerBackground(color, for: .widget)
        } else {
            background(color)
        }
    }
}

// MARK: - النشاطُ الحيُّ للرحلة

struct TaxoRideLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: TaxoRideAttributes.self) { context in
            LockScreenView(context: context)
                .activityBackgroundTint(Brand.ink)
                .activitySystemActionForegroundColor(Brand.paper)
                .widgetURL(Brand.link("/"))
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    Image(systemName: "car.fill").foregroundColor(Brand.pink).font(.title2)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    if !context.state.plate.isEmpty {
                        Text(context.state.plate).font(.system(.callout, design: .monospaced)).bold()
                    }
                }
                DynamicIslandExpandedRegion(.center) {
                    Text(context.state.title).font(.headline).lineLimit(1)
                }
                DynamicIslandExpandedRegion(.bottom) {
                    VStack(spacing: 6) {
                        Text(context.state.detail).font(.subheadline).lineLimit(1)
                        StepBar(step: context.state.step)
                    }
                    .environment(\.layoutDirection, .rightToLeft)
                }
            } compactLeading: {
                Image(systemName: "car.fill").foregroundColor(Brand.pink)
            } compactTrailing: {
                Text(context.state.detail).font(.caption2).lineLimit(1).frame(maxWidth: 64)
            } minimal: {
                Image(systemName: "car.fill").foregroundColor(Brand.pink)
            }
            .widgetURL(Brand.link("/"))
        }
    }
}

struct LockScreenView: View {
    let context: ActivityViewContext<TaxoRideAttributes>

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(context.attributes.brand).font(.system(size: 14, weight: .black)).foregroundColor(Brand.paper.opacity(0.7))
                Spacer()
                if !context.state.plate.isEmpty {
                    Text(context.state.plate)
                        .font(.system(.callout, design: .monospaced)).bold()
                        .padding(.horizontal, 8).padding(.vertical, 2)
                        .background(Brand.paper).foregroundColor(Brand.ink)
                        .clipShape(RoundedRectangle(cornerRadius: 4))
                }
            }
            Text(context.state.title).font(.title3).bold().foregroundColor(Brand.paper)
            if !context.state.detail.isEmpty {
                Text(context.state.detail).font(.subheadline).foregroundColor(Brand.paper.opacity(0.85)).lineLimit(1)
            }
            StepBar(step: context.state.step)
        }
        .padding(16)
        .environment(\.layoutDirection, .rightToLeft)
    }
}

struct StepBar: View {
    let step: Int

    var body: some View {
        HStack(spacing: 4) {
            ForEach(0..<4, id: \.self) { index in
                Capsule()
                    .fill(index < max(1, step) ? Brand.pink : Brand.paper.opacity(0.25))
                    .frame(height: 4)
            }
        }
    }
}
