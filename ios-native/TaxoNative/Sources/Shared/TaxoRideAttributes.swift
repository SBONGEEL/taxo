import Foundation
#if canImport(ActivityKit)
import ActivityKit

/// **شكلُ النشاط الحيّ للرحلة** — ملفٌّ واحدٌ يُجمَّع في الهدفين: التطبيقُ (`TaxoNative`) يبدؤه ويحدّثه،
/// والامتدادُ (`TaxoWidgets`) يرسمه على شاشة القفل وفي Dynamic Island. **ويطابق النظامُ بينهما بالاسم**،
/// فنسختان من الملفّ تفترقان = نشاطٌ لا يُرسم.
///
/// **قيمٌ مصوغةٌ لا خامٌ** هنا بقصد: النصُّ يُصاغ في الويب بلغة المستخدم (`tr`) وبأرقامٍ لاتينيّة، والامتدادُ يرسم ما وصله
/// — فلا تُكتب ترجمةٌ ثانيةٌ في Swift تفترق عن الأولى.
@available(iOS 16.1, *)
public struct TaxoRideAttributes: ActivityAttributes {
    public struct ContentState: Codable, Hashable {
        /// «الكبتن في الطريق» · «وصل الكبتن» · «في الرحلة»
        public var title: String
        /// «٣ دقائق» · «Toyota Corolla · أبيض»
        public var detail: String
        /// اللوحة إن وُجدت
        public var plate: String
        /// ٠ بحث · ١ في الطريق · ٢ وصل · ٣ في الرحلة · ٤ انتهت
        public var step: Int

        public init(title: String, detail: String, plate: String, step: Int) {
            self.title = title
            self.detail = detail
            self.plate = plate
            self.step = step
        }
    }

    public var rideId: String
    /// `rider` · `driver` — الرابطُ عند اللمس يفتح التطبيقَ الصحيح
    public var appKind: String
    /// «TAXO» · «TAXO كبتن»
    public var brand: String

    public init(rideId: String, appKind: String, brand: String) {
        self.rideId = rideId
        self.appKind = appKind
        self.brand = brand
    }
}
#endif
