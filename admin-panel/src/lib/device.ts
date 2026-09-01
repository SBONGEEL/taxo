/** `device_id` للوحة — عقدُ تسجيل الأجهزة في SPEC القسم 10، بمفتاحٍ خاصٍّ بها.
 *
 * **ومفتاحٌ ثالثٌ لا مشترك**: `taxo.driver.device_id` و`taxo.device_id`
 * قائمان في التطبيقين، **والأصلُ واحدٌ حين يُثبَّت غلافان على هاتفٍ واحد**
 * (`androidScheme: "https"` يجعل الأصلَ نطاقاً، والنطاقان مختلفان — لكنّ
 * المتصفحَ على سطح المكتب أصلٌ واحدٌ لمن يفتح اللوحةَ والتطبيقَ من نطاقين
 * مختلفين، فالفصلُ بالمفتاح أرخصُ من الاعتماد على عزل الأصل).
 *
 * **ويعيش في `localStorage` لا في الحالة**: مسحُه عند الخروج يخلق جهازاً
 * جديداً في كلِّ جلسة، فتتراكم رموزٌ ميتةٌ على حسابٍ واحد.
 */

import { Capacitor } from "@capacitor/core";

const KEY = "taxo.admin.device_id";

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
 * **والدرسُ منقولٌ من `driver-app/src/lib/device.ts`**: كانت `"web"` ثابتةً
 * بتعليقٍ يقول «وتغليفُ Capacitor لاحقاً يجعله `android`» — **وجاء اللاحقُ
 * ولم يتغيّر السطر**، فصار كلُّ جهازٍ يُسجَّل «ويب» وهو أندرويد. فهنا تُقرأ
 * من اليوم الأول.
 */
export function platform(): "ios" | "android" | "web" {
  const name = Capacitor.getPlatform();
  return name === "android" || name === "ios" ? name : "web";
}
