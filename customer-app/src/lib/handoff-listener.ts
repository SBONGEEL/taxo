/** يستقبل النيّةَ الواردة ويحوّلها إلى مسار الاستقبال.
 *
 * **والقراءةُ من `appUrlOpen` لا من `location`**: الغلافُ يفتح عنوانَ المخطط
 * الخاصّ، ولا يصير مسارَ الويب من نفسه — فبلا هذا المستمع تصل النيّةُ ولا
 * يحدث شيء، وهو شكلُ «بابٌ بلا زرّ» في ثوبِ منصّة.
 */

import { App } from "@capacitor/app";

export function listenForHandoff(): void {
  void App.addListener("appUrlOpen", ({ url }) => {
    try {
      const parsed = new URL(url);
      if (parsed.host !== "handoff") return;
      const token = parsed.searchParams.get("t");
      if (!token) return;
      // يُمرَّر في الجزء (`#`) داخل التطبيق: لا يدخل تاريخَ تنقّلٍ ولا يُرسل
      window.location.replace(`/handoff#token=${encodeURIComponent(token)}`);
    } catch {
      /* عنوانٌ لا يُحلَّل — لا شيء يُفعل، ولا يُسقط التطبيق */
    }
  });
}
