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

/** خالصة: أيُقرأ المفتاحُ في هذا الغلاف؟ — `false` لمفتاحٍ من القائمة على أندرويد تحت الحدّ (أو برقمٍ لم يُعرف بعد). */
export function shellAllowsFor(key: string, platform: string, build: number | null): boolean {
  if (!NEW_SHELL_KEYS.has(key) || platform !== "android") return true;
  return build !== null && build >= NEW_SHELL_MIN_ANDROID;
}
