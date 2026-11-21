/** **الجزءُ الخالص من `shell-features.ts`** — بلا React ولا Capacitor، فيُختبر بـ`node --test`. نسختان متطابقتان بايتاً في التطبيقين. */
/** **أوّلُ غلافٍ يحمل المراحلَ الثلاث** — v2.0.1367 (١٨/١١)، على Play والمسار المغلق وصفحة التنزيل. */
export const NEW_SHELL_MIN_ANDROID = 1367;

/** مفاتيحُ المراحل الثلاث ونغمةُ الإشعارات (ج/١) — **كلُّها مطفأةٌ على الإنتاج حين كُتب هذا** (قِيس ١٨/١١: لا صفَّ لأيٍّ منها). */
export const NEW_SHELL_KEYS: ReadonlySet<string> = new Set([
  "permissions_center",
  "notification_tones_enabled",
  "quick_tile",
  "home_widget",
  "boot_resume",
  "app_shortcuts",
  "haptics",
  "status_bubble",
  "native_location",
  "in_app_update",
  "in_app_review",
  "rich_notifications",
  "display_accessibility",
  "native_crash_reports",
  "bubble_demand_heat",
  "pickup_wait_timer",
  "smart_destination",
  "native_call_ui",
  "bubble_offer_card",
  "offer_tts",
  "screen_secure",
  "auto_night_keep_awake",
  "motion_aware_location",
  "ride_live_notification",
  "ride_live_tracking",
  "mock_location_report",
  "root_report",
  "volume_emergency",
  "ride_widget",
  "weak_network_retry",
  "sms_autofill",
  "voice_ride_phrase",
  "last_ride_mode",
]);

/** **أوّلُ غلافٍ يحمل الفقاعتين والودجات** (أمرُ المالك ٢٠/١١ الرابع) — رقمُ إيداع الإصدار الموقَّع نفسِه (`versionCode` = عددُ الإيداعات).
 *  **وقيمةٌ أدنى من الإصدار الفعليّ لا تضرّ**: لا غلافَ منشوراً بين 1367 والإصدار، فلا غلافَ بلا الأصليِّ يجتاز الشرط. */
export const BUBBLE_SHELL_MIN_ANDROID = 1409;

/** مفاتيحُ الفقاعتين والودجات — **مطفأةٌ لكلِّ دولة**، ولا تُقرأ في غلافٍ أقدم: الغلافُ القديمُ لا قائمةَ دائريّةَ فيه ولا فقاعةَ راكب. */
export const BUBBLE_SHELL_KEYS: ReadonlySet<string> = new Set([
  "bubble_radial_menu",
  "bubble_online_toggle",
  "bubble_today_card",
  "driver_break",
  "bubble_busy_area",
  "bubble_last_ride",
  "bubble_goal_ring",
  "bubble_subscription_ring",
  "bubble_ride_panel",
  "quick_replies",
  "bubble_wait_counter",
  "bubble_road_report",
  "bubble_sos",
  "voice_offer_answer",
  "rider_bubble",
]);

/** **أوّلُ غلافٍ يحمل الودجاتِ الجديدة وزرَّ تثبيتها** (أمرُ المالك ٢١/١١ الثالث) — 1409 حمل الفقاعتين **بلا الودجات** (قِيس: إيداعاتُها بعده).
 *  **والحدُّ أوّلُ إيداعٍ بعد 1439** (رأسُ ٢١/١١ صباحاً): لا غلافَ منشوراً بين 1409 والإصدار الموقَّع القادم، فلا غلافَ بلا الودجات يجتازه. */
export const WIDGETS_SHELL_MIN_ANDROID = 1440;

/** مفاتيحُ الودجات — **لا تُقرأ في غلافٍ أقدم**: مزوّداتُها ليست فيه، ومفتاحٌ مشتعلٌ هناك يَعِد بما لا يوجد. */
export const WIDGETS_SHELL_KEYS: ReadonlySet<string> = new Set(["driver_widgets_plus", "rider_widgets_plus"]);

/** خالصة: أيُقرأ المفتاحُ في هذا الغلاف؟ — `false` لمفتاحٍ من القائمة على أندرويد تحت الحدّ (أو برقمٍ لم يُعرف بعد). */
export function shellAllowsFor(key: string, platform: string, build: number | null): boolean {
  if (platform !== "android") return true;
  if (WIDGETS_SHELL_KEYS.has(key)) return build !== null && build >= WIDGETS_SHELL_MIN_ANDROID;
  if (BUBBLE_SHELL_KEYS.has(key)) return build !== null && build >= BUBBLE_SHELL_MIN_ANDROID;
  if (!NEW_SHELL_KEYS.has(key)) return true;
  return build !== null && build >= NEW_SHELL_MIN_ANDROID;
}
