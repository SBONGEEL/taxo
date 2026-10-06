/** **أيقوناتُ اللوحة برموز TAXO 2.0** — جسرٌ لا قائمةٌ ثانية.
 *
 * المشرفُ يختار أيقونةَ البلاطة واللافتة **من قائمةٍ مقرَّرة بأسماء lucide** (`SERVICE_ICONS` في
 * `backend/app/services/storefront.py`، قرارُ المالك ٢٠٢٦-٠٨-٣١)، **والهويةُ ترسم بـMaterial Symbols Rounded**.
 * فهذا الجدولُ يترجم الاسمَ ولا يضيف خياراً: **ما يختاره المشرفُ هو ما يُرسم**، بعائلة الهوية.
 *
 * **و`check:taxo2` يقيس الجهتين**: كلُّ اسمٍ في القائمة المقرَّرة له هنا مقابل، **وكلُّ مقابلٍ في مقتطَع الخطّ**
 * (`icon_names=` في `index.html` لكلِّ تطبيق) — **وإلا رُسم اسمُ الأيقونة نصّاً** بدلها.
 */
export const SERVICE_ICON: Readonly<Record<string, string>> = {
  // ── تنقّلٌ ومركبات
  car: "directions_car",
  "car-taxi-front": "local_taxi",
  bus: "directions_bus",
  truck: "local_shipping",
  bike: "pedal_bike",
  "plane-takeoff": "flight_takeoff",
  "map-pin": "location_on",
  map: "map",
  route: "route",
  navigation: "navigation",
  "calendar-clock": "event_upcoming",
  warehouse: "garage",
  // ── طرودٌ وتسوّق
  package: "package_2",
  boxes: "inventory_2",
  "shopping-bag": "shopping_bag",
  "shopping-cart": "shopping_cart",
  store: "storefront",
  gift: "redeem",
  // ── مالٌ ومحفظة
  wallet: "account_balance_wallet",
  banknote: "payments",
  "credit-card": "credit_card",
  coins: "toll",
  receipt: "receipt_long",
  percent: "percent",
  "arrow-down-left": "south_west",
  "hand-coins": "request_quote",
  // ── حسابٌ وخدمة
  user: "person",
  users: "group",
  "shield-check": "verified_user",
  "life-buoy": "support",
  headphones: "headset_mic",
  star: "star",
  trophy: "trophy",
  "badge-check": "verified",
  bell: "notifications",
  settings: "settings",
  "file-text": "description",
  clock: "schedule",
  "id-card": "card_membership",
  "folder-open": "folder_shared",
  // ── عامّ
  "layout-grid": "grid_view",
  sparkles: "auto_awesome",
  heart: "favorite",
  flame: "local_fire_department",
  zap: "bolt",
  flag: "flag",
};

/** رمزُ الهوية لاسم lucide — **و`grid_view` لما لا يُعرف** (والحارسُ يمنع أن يقع: القائمةُ والجدولُ يُقاسان). */
export function serviceIcon(name: string): string {
  return SERVICE_ICON[name] ?? "grid_view";
}
