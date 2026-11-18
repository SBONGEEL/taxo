/** **ميزاتُ أندرويد الأصليّ (A وB وC) لمن على الغلاف الجديد وحدَه** (أمرُ المالك ٢٠٢٦-١١-١٨ السادس، البند ٦:
 *  «تُشعل الميزاتُ في الأردن والجزائر وليبيا **لمن على الإصدار الجديد**»).
 *
 *  **العلّة**: المفتاحُ لكلِّ دولةٍ لا لكلِّ إصدار — فما يحتاج ملحقاً أصليّاً يسكت في الغلاف القديم وحدَه، **وما كان ويباً خالصاً**
 *  (مؤقّتُ الالتقاط، اقتراحُ الوجهة، «آخر رحلة»، النصُّ الكبير…) **كان سيصل غلافَ 1118 أيضاً** بلا أن يُختبر عليه. فهنا حدٌّ واحد:
 *  **على أندرويد، مفتاحٌ من هذه القائمة لا يُقرأ مشتعلاً تحت `NEW_SHELL_MIN_ANDROID`**.
 *
 *  **وما لا يمسّه**: iOS (رقمُه يُرقَّم وحدَه، وله وكيلُه) والمتصفّح — كلاهما يقرأ المفتاحَ كما هو. **وكلُّ مفتاحٍ غيرِ هذه القائمة** كما كان.
 *  **ورقمُ الغلاف يُحفظ** لإقلاعٍ قادم، ويُقرأ من `App.getInfo()` في كلِّ إقلاعٍ فيُصحَّح إن تغيّر.
 *
 *  **نسختان متطابقتان بايتاً** في `customer-app/src/lib/` و`driver-app/src/lib/` — لكلِّ تطبيقٍ بناؤه.
 */
import { useSyncExternalStore } from "react";
import { App } from "@capacitor/app";
import { Capacitor } from "@capacitor/core";

import { shellAllowsFor } from "@/lib/shell-features-core";

export { NEW_SHELL_KEYS, NEW_SHELL_MIN_ANDROID, shellAllowsFor } from "@/lib/shell-features-core";

const BUILD_KEY = "taxo.shell.build";
const listeners = new Set<() => void>();

let shellBuild: number | null = (() => {
  try {
    const stored = Number(localStorage.getItem(BUILD_KEY));
    return Number.isFinite(stored) && stored > 0 ? stored : null;
  } catch {
    return null;
  }
})();

if (Capacitor.getPlatform() === "android") {
  void App.getInfo()
    .then((info) => {
      const build = Number(info.build);
      if (!Number.isFinite(build) || build === shellBuild) return;
      shellBuild = build;
      try {
        localStorage.setItem(BUILD_KEY, String(build));
      } catch {
        // تخزينٌ محجوب — يُقرأ ثانيةً في الإقلاع القادم
      }
      for (const listener of listeners) listener();
    })
    .catch(() => undefined);
}

/** للقراءة خارج المكوّنات (مثل `sms-consent`). */
export function shellAllows(key: string): boolean {
  return shellAllowsFor(key, Capacitor.getPlatform(), shellBuild);
}

/** للمكوّنات — **يعيد الرسمَ حين يُعرف رقمُ الغلاف** بعد الإقلاع. */
export function useShellAllows(key: string): boolean {
  const build = useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => shellBuild,
  );
  return shellAllowsFor(key, Capacitor.getPlatform(), build);
}
