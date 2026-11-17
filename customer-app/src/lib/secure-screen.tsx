/** **منعُ لقطات الشاشة في المحفظة وشاشة رمز بطاقة TAXO** (SPEC §١٠٣ المرحلة B/26) — خلف `screen_secure` لكلِّ دولة.
 *
 *  **كلُّ ما تحت `/wallet`** (الرصيد والحركات والشحن والتحويل وإدخالُ رمز البطاقة) — والخروجُ منها يرفع المنعَ فورا،
 *  فلا تبقى بقيّةُ التطبيق سوداءَ في اللقطات. **وواحدٌ في التطبيقين حرفاً.** */
import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { Capacitor, registerPlugin } from "@capacitor/core";

import { useFeature } from "@/lib/config";
import { useSession } from "@/lib/session";

const screenSecure = registerPlugin<{ set(options: { on: boolean }): Promise<void> }>("ScreenSecure");

export function securedPath(pathname: string): boolean {
  return pathname === "/wallet" || pathname.startsWith("/wallet/");
}

export function SecureScreen(): null {
  const { user } = useSession();
  const enabled = useFeature(user?.country_code, "screen_secure");
  const { pathname } = useLocation();
  const on = enabled && securedPath(pathname);
  useEffect(() => {
    if (!Capacitor.isNativePlatform() || !Capacitor.isPluginAvailable("ScreenSecure")) return;
    void screenSecure.set({ on }).catch(() => undefined);
  }, [on]);
  return null;
}
