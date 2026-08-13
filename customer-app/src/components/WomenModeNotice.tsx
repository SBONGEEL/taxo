/** «تم تفعيل الوضع النسائي» — إشعارُ مرةٍ واحدةٍ في عمر الجهاز (2026-08-13).
 *
 * **لماذا إشعارٌ أصلاً؟** لأن السِمةَ تُفعَّل **تلقائياً** بإقرارها الذاتي، ولا
 * أحدَ يبحث عن مفتاحٍ لشيءٍ لم يطلبه: من فتحت التطبيقَ فوجدته ورديّاً إمّا
 * تظنّه عطباً أو تظنّه غيرَ قابلٍ للتغيير. فالإشعارُ يقول ما وقع **وأين يُطفأ**.
 *
 * **ويبقى حتى تُغلقه هي — لا يزول بمهلة.** قاعدةُ `DESIGN.md` §2.7 تعطي التوست
 * عمراً (٢٨٠٠ms)، وهي صحيحةٌ لتوستِ حدثٍ («تم الدفع ✓») لأن الحدثَ وقع ولا شيءَ
 * يُفعل به. وهذا **تعريفٌ بمفتاح**: من غابت عن الشاشة ثلاث ثوانٍ تفقده ولا يعود
 * أبداً — فيبقى وضعٌ لا تعرف كيف تُطفئه. فالشكلُ من §2.7 والعمرُ من غرضه.
 *
 * **ولونُه `--acc` لا `--brand`**: حزمةُ التصميم النسائية تحصر التلوينَ في
 * «الشعار والزر الأساسي والخيار المحدد» — والتوستُ ليس منها. ولو صُبغ وردياً
 * لصار إعلاناً عن نفسه مرتين.
 */

import { X } from "lucide-react";

import { useBrand } from "@/lib/brand";

export function WomenModeNotice() {
  const { showNotice, dismissNotice } = useBrand();
  if (!showNotice) return null;

  return (
    <div
      role="status"
      // **`inset-x-0 mx-auto` لا `left-1/2 -translate-x-1/2`**: الثانيةُ تبدو
      // مركزةً وهي تقصّ العرضَ المتاح إلى نصفه — صندوقٌ `fixed` بـ`left:50%`
      // بلا `right` يتقلّص في ما بقي من الشاشة (قُيس: ٢٠١ من ٤٠٢)، فتلتفّ
      // جملةٌ قصيرةٌ ثلاثةَ أسطر. والإزاحةُ تُعيد التمركزَ **بعد** أن يُحسب
      // العرض، فلا تُصلحه. وهذا ما يفعله `Toasts.tsx` أصلاً
      className="fixed inset-x-16 bottom-nav z-[80] mx-auto flex w-max max-w-[88%] items-center gap-10 rounded-full bg-accent px-20 py-10 text-12.5 font-bold text-accent-ink shadow-toast"
    >
      <span>تم تفعيل الوضع النسائي — يمكنك إطفاؤه من الإعدادات</span>
      <button
        type="button"
        onClick={dismissNotice}
        aria-label="إغلاق"
        className="pressable -me-6 shrink-0 rounded-full p-4 opacity-70 transition hover:opacity-100"
      >
        <X className="size-14" />
      </button>
    </div>
  );
}
