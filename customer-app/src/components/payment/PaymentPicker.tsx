/** ورقةُ اختيار طريقة الدفع — تصميمُ الراكب (`payPickShow`)، وقرارُ 26 — **بلغة TAXO 2.0 وحدَها** (ورقةُ «R06»).
 *
 * **ورقةٌ لا قائمةٌ في الصفحة**: القرارُ 26 حسم ذلك لصالح التصميم، والقياسُ يوافقه — طبقةُ تعتيمٍ فوقها ورقةٌ سفلية.
 *
 * **ولا تحمل منطقَ قناةٍ واحدة**: تعرض ما سمحت به الدولةُ وتُعيد ما اختير. البطاقةُ لا تفتح صفحةَ مزوّدٍ من هنا، والمحفظةُ
 * لا تُخصم — كلُّ ذلك في `screens/Payment.tsx` بعد الرحلة، وهو البابُ الوحيد الذي يحرّك مالاً.
 *
 * **وتُنقل إلى `body` ببوّابة، وهذا ليس تنميقاً**: نداؤها من ورقة الطلب يقع داخل `motion.div` تحمل `transform`، و`transform`
 * غيرُ الصفر **يجعل نفسَه المرجعَ لكل `fixed` تحته** — فيُقاس التعتيمُ على الورقة لا على الشاشة.
 *
 * **وكان لها وجهان** (القائمُ بأيقونات `lucide` وTAXO 2.0) — **ونُزع القائم** (§٦٢/٣): شاشةُ الدفع كانت آخرَ من يفتحه.
 */

import { createPortal } from "react-dom";

import type { PayableMethod, PaymentChannel } from "@/lib/payment";
import { PAYMENT_METHOD_LABEL } from "@/lib/labels";
import { SheetT2 } from "@/screens/t2/SheetT2";

import "@/screens/t2/t2.css";
import "@/screens/t2/money.css";

/** رموزُ الهوية لقنوات الدفع. */
export const PAY_ICON_T2: Record<PayableMethod, string> = {
  wallet: "account_balance_wallet",
  cliq: "smartphone",
  card: "credit_card",
  cash: "payments",
};

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
      {/* **الظلُّ بلون الهوية** (`--t2-scrim`) — كان صنفَ اللغة السابقة (`bg-dim`) تحت ورقةٍ بلغة TAXO 2.0 */}
      <button type="button" aria-label="إغلاق" onClick={onClose} className="t2 t2-m-scrim" />
      <div className="t2-picker">
        <SheetT2>
          <div className="t2-picker-title">طريقة الدفع</div>
          <div className="t2-list" role="radiogroup" aria-label="طريقة الدفع">
            {channels.map(({ method, hint }) => (
              <button
                key={method}
                type="button"
                role="radio"
                aria-checked={method === selected}
                onClick={() => {
                  onSelect(method);
                  onClose();
                }}
                className="t2-row t2-pay-row"
              >
                <span className="t2-icon" aria-hidden="true">{PAY_ICON_T2[method]}</span>
                <span className="t2-row-main">
                  <span className="t2-row-title">{PAYMENT_METHOD_LABEL[method]}</span>
                  <span className="t2-row-body">{method === "wallet" && walletHint ? walletHint : hint}</span>
                </span>
                {method === selected ? (
                  <span className="t2-icon t2-pay-check" aria-hidden="true">check</span>
                ) : null}
              </button>
            ))}
          </div>
        </SheetT2>
      </div>
    </>,
    document.body,
  );
}
