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

import { Capacitor } from "@capacitor/core";

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

/** المنصة كما تفهمها الخلفية — **تُقرأ من المنصّة لا تُكتب ثابتة**.
 *
 * **كانت `"web"` ثابتةً** بتعليقٍ يقول «وتغليفُ Capacitor لاحقاً يجعله
 * `ios`/`android`» — **وجاء اللاحقُ ولم يتغيّر السطر**، فصار كلُّ جهازٍ
 * يُسجَّل «ويب» وهو أندرويد.
 *
 * **وأثرُه سجلٌّ لا تسليم، وهذا قِيس لا يُفترض**: `push/fcm.py::_payload`
 * يرسل الكتلَ الثلاث (`android`/`apns`/`webpush`) في كلِّ رسالة وFCM يختار
 * بحسب الرمز — فلا أولويةَ ضاعت. **لكنه عمودٌ يقول غيرَ ما هو**، وأولُ منطقٍ
 * يتفرّع عليه غداً يتفرّع على كذب.
 */
export function platform(): "ios" | "android" | "web" {
  const name = Capacitor.getPlatform();
  return name === "android" || name === "ios" ? name : "web";
}
