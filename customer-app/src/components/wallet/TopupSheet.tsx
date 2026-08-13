/** ورقةُ شحن الرصيد — تصميمُ الراكب (`topupShow`).
 *
 * **وهي الورقةُ الحقيقيةُ الوحيدة من الثلاث التي طُلب تحويلُها**، وقياسُ النموذج
 * هو ما فرّق: `topupShow` طبقةُ تعتيمٍ (`--dim`، z 70) فوقها ورقةٌ سفليةٌ بنصف
 * قطرٍ أعلى `24px` وحركةِ `slideup`؛ أما `payShow` و`rateShow` فـ`inset:0`
 * بخلفيةٍ معتمةٍ كاملة (z 60) — أي **شاشتان كاملتان لا ورقتان**. فما احتاج
 * تحويلاً واحدٌ لا ثلاثة، وما عداهما يُطابَق في **بنيته** لا في نوعه.
 *
 * **ولا تحمل هذه الورقةُ منطقَ القنوات**: تجمع المبلغَ والقناةَ ثم تُسلّم إلى
 * `/wallet/topup` — وهو البابُ الذي يعرف كلَّ قناةٍ وشروطَها (البطاقةُ تُحوَّل
 * إلى صفحة المزود، وكليك الآليةُ تفتح صفحةَ QR بقرار 29، واليدويةُ تنتظر تأكيد
 * الإدارة). ومنطقٌ منسوخٌ في ورقةٍ يفترق عن أصله أولَ مرةٍ يتغيّر شرط.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { CreditCard, Landmark } from "lucide-react";

import { Field } from "@/components/ui/Field";
import { Sheet } from "@/components/ui/Sheet";
import { QUICK_TOPUP_AMOUNTS } from "@/lib/wallet";
import { cn, currencyLabel, formatMoney } from "@/lib/utils";

export function TopupSheet({
  currency,
  cardEnabled,
  cliqEnabled,
  onClose,
}: {
  currency: string | undefined;
  cardEnabled: boolean;
  cliqEnabled: boolean;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const [amount, setAmount] = useState("10");
  const valid = Number(amount) > 0;

  return (
    <>
      {/* التعتيمُ يُغلق بالضغط عليه كبقية أوراق التطبيق */}
      <button
        type="button"
        aria-label="إغلاق"
        onClick={onClose}
        className="fixed inset-0 z-[69] bg-dim"
      />
      <div className="fixed inset-x-0 bottom-0 z-[70]">
        <Sheet>
          <div className="space-y-14 pb-16">
            <div>
              <p className="text-16 font-semibold text-ink">شحن الرصيد</p>
              <p className="mt-2 text-12 text-muted">
                اختر المبلغ ثم طريقة الشحن.
              </p>
            </div>

            <Field
              label="المبلغ"
              inputMode="decimal"
              dir="ltr"
              value={amount}
              onChange={(event) =>
                setAmount(event.target.value.replace(/[^\d.]/g, ""))
              }
              suffix={currencyLabel(currency)}
            />
            <div className="flex gap-8">
              {QUICK_TOPUP_AMOUNTS.map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setAmount(value)}
                  className={cn(
                    "pressable flex-1 rounded-8 border px-8 py-8 text-14 transition",
                    amount === value
                      ? "border-brand bg-brand-soft text-ink"
                      : "border-line text-muted hover:bg-surface-2",
                  )}
                >
                  {formatMoney(value, currency)}
                </button>
              ))}
            </div>

            {/* **القنواتُ صفوفٌ لا حبّات** كما في التصميم: لكلٍّ سطرُ شرحٍ يقول
                ما يقع بعد الضغط — «فوريّ» أم «بعد التأكد». والقناةُ الغائبةُ
                لا تُرسم معطّلةً: مفتاحُها مطفأٌ في هذا السوق */}
            <div className="space-y-8">
              {cardEnabled ? (
                <button
                  type="button"
                  onClick={() =>
                    navigate("/wallet/topup", {
                      state: { amount, channel: "card" },
                    })
                  }
                  disabled={!valid}
                  className="pressable flex w-full items-center gap-12 rounded-12 border border-line bg-bg p-14 text-start transition hover:bg-surface-2 disabled:opacity-50"
                >
                  <CreditCard className="size-20 text-muted" />
                  <span className="flex-1">
                    <span className="block font-medium text-ink">بطاقة</span>
                    <span className="block text-12 text-muted">
                      شحن فوري عبر صفحة الدفع الآمنة
                    </span>
                  </span>
                </button>
              ) : null}
              {cliqEnabled ? (
                <button
                  type="button"
                  onClick={() =>
                    navigate("/wallet/topup", {
                      state: { amount, channel: "cliq" },
                    })
                  }
                  disabled={!valid}
                  className="pressable flex w-full items-center gap-12 rounded-12 border border-line bg-bg p-14 text-start transition hover:bg-surface-2 disabled:opacity-50"
                >
                  <Landmark className="size-20 text-muted" />
                  <span className="flex-1">
                    <span className="block font-medium text-ink">كليك</span>
                    <span className="block text-12 text-muted">
                      حوّل ثم يُضاف بعد التأكد
                    </span>
                  </span>
                </button>
              ) : null}
            </div>
          </div>
        </Sheet>
      </div>
    </>
  );
}
