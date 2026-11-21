/** **«أضف ودجت TAXO لشاشتك»** (أمرُ المالك ٢٠٢٦-١١-٢١ الثالث، البند ٣) — **منسوخٌ بايتاً في التطبيقين** (`check:storefront-card`).
 *
 * أندرويد ٨+ يسمح للتطبيق بطلب تثبيت ودجته بلمسة (`requestPinAppWidget` في `LauncherPlugin.java`) — **والمشغِّلُ يسأل المستخدمَ بنافذته هو**،
 * فلا شيءَ يُثبَّت بلا موافقته. **وما لا يدعمه يُخفي البطاقةَ ولا يقول شيئاً**: غلافٌ أقدمُ بلا الطريقة، أو مشغِّلٌ لا يقبل، أو ودجةٌ
 * مزوّدُها مطفأٌ لأن مفتاحَ الودجات مطفأٌ لدولته — كلُّها «غيرُ مدعوم».
 *
 * **والبطاقةُ في الرئيسيّة مرّةً واحدة** (`taxo.pinCard.v1` في هذا الهاتف): لمسُ «أضف» أو الإغلاقُ يُخفيها، **وصفُّ الإعدادات يبقى**.
 */
import { useEffect, useState } from "react";
import { Capacitor, registerPlugin } from "@capacitor/core";

interface NativePin {
  pinSupported(options: { kind: string }): Promise<{ supported: boolean }>;
  pinWidget(options: { kind: string }): Promise<{ requested: boolean }>;
}

const native = registerPlugin<NativePin>("Launcher");
const SEEN = "taxo.pinCard.v1";

export function pinCardSeen(): boolean {
  try {
    return window.localStorage.getItem(SEEN) === "done";
  } catch {
    return true;
  }
}

export function markPinCardSeen(): void {
  try {
    window.localStorage.setItem(SEEN, "done");
  } catch {
    // تخزينٌ ممنوع — تظهر في الفتحة القادمة، ولا ضرر
  }
}

/** **أيقبل هذا الهاتفُ تثبيتَ الودجة؟** — `false` حتى يجيب الطرفُ الأصليّ، و`false` لكلِّ رفضٍ أو غيابٍ أو مفتاحٍ مطفأ. */
export function usePinWidget(kind: string, enabled: boolean): { supported: boolean; pin: () => Promise<boolean> } {
  const [supported, setSupported] = useState(false);
  useEffect(() => {
    if (!enabled || !Capacitor.isNativePlatform() || !Capacitor.isPluginAvailable("Launcher")) {
      setSupported(false);
      return;
    }
    let alive = true;
    native
      .pinSupported({ kind })
      .then((answer) => {
        if (alive) setSupported(answer.supported === true);
      })
      .catch(() => {
        // غلافٌ أقدمُ بلا الطريقة — لا بطاقة
        if (alive) setSupported(false);
      });
    return () => {
      alive = false;
    };
  }, [kind, enabled]);
  const pin = () =>
    native
      .pinWidget({ kind })
      .then((answer) => answer.requested === true)
      .catch(() => false);
  return { supported, pin };
}
