/** موضعُ تبويبٍ لم يُبنَ بعد.
 *
 * الشريط السفلي أربعةُ تبويبات بحكم التصميم، وثلاثةٌ منها تأتي في الجلسات
 * التالية. تبويبٌ يظهر ولا يفتح شيئاً يُقرأ عطلاً؛ وهذه تقول ما هو صحيح.
 */

import { BottomNav } from "@/components/BottomNav";

export function SoonScreen({ title }: { title: string }) {
  return (
    <div className="relative h-full bg-bg">
      <div className="flex h-full flex-col items-center justify-center gap-10 px-32 pb-nav text-center">
        <div className="text-20 font-bold text-ink">{title}</div>
        <p className="text-13 leading-note text-muted">
          هذه الشاشة قيد البناء في المرحلة 10.
        </p>
      </div>
      <BottomNav />
    </div>
  );
}
