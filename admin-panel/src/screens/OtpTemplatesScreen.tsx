/** شاشةُ قوالب رسائل الرمز — **عالميةٌ لا تتبع مبدّلَ الدولة في الترويسة**.
 *
 * وشاشةٌ مستقلةٌ لا قسمٌ في «الإعدادات» لأن تلك مقسومةٌ بالدولة: قالبٌ عالميٌّ
 * داخلها يُقرأ خاصّاً بالسوق المختار، فيظنّ المشرفُ أنه حرّر الأردنَ وحدَه.
 */

import { OtpTemplates } from "@/components/OtpTemplates";

export function OtpTemplatesScreen() {
  return (
    <div className="mx-auto max-w-3xl px-16 py-16">
      <h1 className="mb-4 text-20 font-bold text-ink">قوالب رسائل الرمز</h1>
      <p className="mb-14 text-11.5 leading-note text-muted">
        نصٌّ واحدٌ لكل غرض، ويُطبَّق على السوقين معاً — الرقمُ والعقدُ عالميان.
      </p>
      <OtpTemplates />
    </div>
  );
}
