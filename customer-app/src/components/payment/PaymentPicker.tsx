/** ورقةُ اختيار طريقة الدفع — تصميمُ الراكب (`payPickShow`)، وقرارُ 26.
 *
 * **ورقةٌ لا قائمةٌ في الصفحة**: القرارُ 26 حسم ذلك لصالح التصميم، والقياسُ
 * يوافقه — `payPickShow` طبقةُ تعتيمٍ (`--dim`) فوقها ورقةٌ سفلية، لا `inset:0`
 * كـ`payShow`. فهي أختُ `TopupSheet` في بنيتها لا أختُ `Stage`.
 *
 * **ولا تحمل منطقَ قناةٍ واحدة**: تعرض ما سمحت به الدولةُ وتُعيد ما اختير.
 * البطاقةُ لا تفتح صفحةَ مزوّدٍ من هنا، والمحفظةُ لا تُخصم — كلُّ ذلك في
 * `screens/Payment.tsx` بعد الرحلة، وهو البابُ الوحيد الذي يحرّك مالاً.
 *
 * **وتُنقل إلى `body` ببوّابة، وهذا ليس تنميقاً**: نداؤها من `ConfirmRide` يقع
 * داخل `motion.div` تحمل `y: 40` — أي `transform` — و`transform` غيرُ الصفر
 * **يجعل نفسَه المرجعَ لكل `fixed` تحته**، فتُقاس `inset-0` على الورقة السفلية
 * لا على الشاشة: تعتيمٌ بحجم الورقة ومُنتقٍ محشورٌ فيها. وأبوها كذلك
 * `pointer-events-none` و`max-w-lg`. وهذا من صنف العطب الذي لا يراه أيُّ بناء
 * ولا يظهر إلا بفتح الشاشة — فيُقطع سببُه من الجذر بدل أن يُنتظر.
 */

import { createPortal } from "react-dom";
import { Check } from "lucide-react";

import type { PayableMethod, PaymentChannel } from "@/lib/payment";
import { PAYMENT_METHOD_LABEL } from "@/lib/labels";
import { Sheet } from "@/components/ui/Sheet";
import { cn } from "@/lib/utils";

export function PaymentPicker({
  channels,
  selected,
  onSelect,
  onClose,
  /** رصيدُ المحفظة نصّاً جاهزاً — يُعرض سطراً فرعياً كما في التصميم
   *  (`walletSub`)، ولا يُحسب منه شيء. */
  walletHint,
}: {
  channels: PaymentChannel[];
  selected: PayableMethod | null;
  onSelect: (method: PayableMethod) => void;
  onClose: () => void;
  walletHint?: string | null;
}) {
  return createPortal(
    <>
      <button
        type="button"
        aria-label="إغلاق"
        onClick={onClose}
        className="fixed inset-0 z-[67] bg-dim"
      />
      <div className="fixed inset-x-0 bottom-0 z-[68] mx-auto max-w-lg">
        <Sheet attached>
          <div className="space-y-12 pb-16">
            <p className="text-16 font-semibold text-ink">طريقة الدفع</p>

            <div className="space-y-8" role="radiogroup" aria-label="طريقة الدفع">
              {channels.map(({ method, icon: Icon, hint }) => (
                <button
                  key={method}
                  type="button"
                  role="radio"
                  aria-checked={method === selected}
                  onClick={() => {
                    onSelect(method);
                    onClose();
                  }}
                  className={cn(
                    "pressable flex w-full items-center gap-12 rounded-14 border p-13 text-start transition",
                    method === selected
                      ? "border-brand bg-brand-soft"
                      : "border-line bg-bg hover:bg-surface-2",
                  )}
                >
                  <Icon className="size-20 text-muted" />
                  <span className="min-w-0 flex-1">
                    <span className="block text-13.5 font-semibold text-ink">
                      {PAYMENT_METHOD_LABEL[method]}
                    </span>
                    <span className="block text-11 text-muted">
                      {method === "wallet" && walletHint ? walletHint : hint}
                    </span>
                  </span>
                  {/* علامةٌ لا حبّةُ راديو مرسومة: الحبّةُ في التصميم دائرةٌ
                      بلونٍ داخليّ، وهنا الحدُّ الملوَّن يقولها والعلامةُ تؤكّدها */}
                  {method === selected ? (
                    <Check className="size-16 shrink-0 text-brand" />
                  ) : null}
                </button>
              ))}
            </div>
          </div>
        </Sheet>
      </div>
    </>,
    document.body,
  );
}
