/** `device_id` — عقد تسجيل الأجهزة في SPEC القسم 10.
 *
 * **يولّده التطبيق ويثبت مع تثبيته**: لا يتغير بدوران رمز FCM ولا بخروجٍ
 * ودخول. هو الوصلة الوحيدة بين «هذا المقبس مفتوح» و«هذا الرمز لا تُرسل إليه»،
 * ومقبسٌ يفتح بمعرّفٍ غير الذي سجّل الرمز يجعل الجهاز يستقبل الحدث مرتين: على
 * الشاشة ومن نظام التشغيل.
 *
 * ولذلك يعيش في `localStorage` لا في الحالة: مسحُه عند الخروج يخلق جهازاً
 * جديداً في كل جلسة، فتتراكم رموزٌ ميتة على حسابٍ واحد.
 */

const KEY = "taxo.driver.device_id";

export function deviceId(): string {
  let value = localStorage.getItem(KEY);
  if (!value) {
    value =
      globalThis.crypto?.randomUUID?.() ??
      `dev-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    localStorage.setItem(KEY, value);
  }
  return value;
}

/** المنصة كما تفهمها الخلفية. التطبيق ويبٌ اليوم، وتغليفُ Capacitor لاحقاً
 * (SPEC القسم 15/ج) يجعله `ios`/`android` بلا تغييرٍ في العقد. */
export function platform(): "ios" | "android" | "web" {
  return "web";
}
