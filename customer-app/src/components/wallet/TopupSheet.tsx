/** ورقةُ شحن الرصيد — تصميمُ الراكب (`topupShow`)، **بلغة TAXO 2.0** (لوحةُ `design/t2-new/rider/R16c`) فوق المحفظة «R11».
 *
 * **ولا تحمل هذه الورقةُ منطقَ القنوات**: تجمع المبلغَ والقناةَ ثم تُسلّم إلى `/wallet/topup` — وهو البابُ الذي يعرف كلَّ قناةٍ
 * وشروطَها (البطاقةُ تُحوَّل إلى صفحة المزود، وكليك الآليةُ تفتح صفحةَ QR بقرار 29، واليدويةُ تنتظر تأكيد الإدارة). ومنطقٌ منسوخٌ
 * في ورقةٍ يفترق عن أصله أولَ مرةٍ يتغيّر شرط.
 *
 * **وما تغيّر طبقةُ العرض وحدَها**: بطاقةُ المبلغ بخطِّ الأرقام والمبالغُ السريعة بلغة خيارات البقشيش (R10)، والقناتان صفّان
 * بلغة منتقي الدفع (R06). **والقيمُ هي هي**: «10» ابتداءً، والقناةُ معطّلةٌ ما دام المبلغُ صفراً، والقناةُ الغائبةُ لا تُرسم.
 */

import { useState } from "react";

import type { PayMethod } from "@/api/types";
import { useNavigate } from "react-router-dom";

import { QUICK_TOPUP_AMOUNTS } from "@/lib/wallet";
import { notMultipleMessage, unitHint } from "@/lib/rounding";
import { formatMoney } from "@/lib/utils";
import { Icon } from "@/taxo2";
import { AmountCardT2, QuickAmountsT2, SheetModalT2, UnitNoteT2 } from "@/screens/t2/MoneyT2"; import { tr } from "@/lib/i18n";

export function TopupSheet({
  currency,
  unit,
  cardEnabled,
  cliqEnabled,
  methods,
  choices = [],
  onClose,
}: {
  currency: string | undefined;
  /** **وحدةُ التقريب مشتعلاً** (`lib/rounding.ts`) و`null` مطفأً — المبلغُ مضاعفٌ لها وإلا لا تُفتح قناة (SPEC §٧٠-ج/٦) */
  unit: string | null;
  cardEnabled: boolean;
  cliqEnabled: boolean;
  /** **طرقُ نظام الدفع الجديد** (SPEC §٧٣-هـ) — تُمرَّر حيث `payment_requests_enabled` مشتعلٌ وحدَه، و`undefined` في غيره:
   *  فورقةُ الأردن وليبيا هي هي حرفاً. **ومعها لا مبالغَ مقترحة** — اقتراحُها لسوقٍ جديدٍ أرقامٌ لم يضعها المالك */
  methods?: PayMethod[];
  /** **مبالغُ الشحن عند الوسيط خياراتٌ ثابتة** (§٧٤-ط/٥) — تُعرض هنا في الورقة نفسِها (§٧٦-ع/٢، المشكلة ١٦): كانت الورقةُ تقبل
   *  مبلغاً حرّاً ثمّ تفرض الصفحةُ التاليةُ خياراتِها وتمسح ما كُتب بصمت */
  choices?: string[];
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const [amount, setAmount] = useState(methods ? "" : "10");
  const unitError = notMultipleMessage(amount, unit, currency);
  const valid = Number(amount) > 0 && unitError === null;
  const gatewayChoices = methods?.some((method) => method.gateway) && choices.length > 0 ? choices : null;
  const chosenAllowed = gatewayChoices === null || gatewayChoices.includes(amount);

  return (
    <SheetModalT2 onClose={onClose}>
      <div className="t2-m-sheet-title">{tr("شحن الرصيد")}</div>
      <p className="t2-m-sheet-sub">{tr("اختر المبلغ ثم طريقة الشحن.")}</p>

      <AmountCardT2 id="topup-sheet-amount" label={tr("المبلغ")} value={amount} onChange={setAmount} currency={currency}>
        {methods ? (
          gatewayChoices ? (
            <QuickAmountsT2
              amounts={gatewayChoices}
              value={amount}
              onPick={setAmount}
              label={(value) => formatMoney(value, currency)}
            />
          ) : null
        ) : (
          <QuickAmountsT2
            amounts={QUICK_TOPUP_AMOUNTS}
            value={amount}
            onPick={setAmount}
            label={(value) => formatMoney(value, currency)}
          />
        )}
      </AmountCardT2>
      <UnitNoteT2 hint={unitHint(unit, currency)} error={unitError} />

      {/* **القنواتُ صفوفٌ لا حبّات** كما في التصميم: لكلٍّ سطرُ شرحٍ يقول ما يقع بعد الضغط — «فوريّ» أم «بعد التأكد».
          والقناةُ الغائبةُ لا تُرسم معطّلةً: مفتاحُها مطفأٌ في هذا السوق */}
      {methods && methods.length > 0 ? (
        <div className="t2-list t2-m-gap">
          {methods.map((method) => (
            <button
              key={method.id}
              type="button"
              className="t2-row t2-m-opt"
              // **بطاقةُ TAXO لا تحتاج مبلغاً** — قيمتُها مطبوعةٌ عليها؛ وتُدخل برمزها في صفحتها
              disabled={method.kind === "purchase_code" ? false : !valid || (method.gateway && !chosenAllowed)}
              onClick={() =>
                method.kind === "purchase_code"
                  ? navigate("/wallet/card")
                  : navigate("/wallet/pay", { state: { amount, methodId: method.id } })
              }
            >
              <Icon name={method.gateway ? "credit_card" : method.kind === "purchase_code" ? "confirmation_number" : method.kind === "cash" ? "payments" : method.kind === "phone_number" ? "smartphone" : "account_balance"} />
              <span className="t2-row-main">
                <span className="t2-row-title">{method.name}</span>
                <span className="t2-row-body">
                  {method.kind === "purchase_code"
                    ? tr("أدخل رمز البطاقة — يُضاف فوراً")
                    : method.gateway
                      ? chosenAllowed
                        ? tr("ادفع بالبطاقة عبر {0} — يُضاف فورَ تأكيده", { 0: method.gateway_name ?? "Chargily" })
                        : tr("اختر أحد المبالغ أعلاه للدفع عبر {0}", { 0: method.gateway_name ?? "Chargily" })
                      : method.requires_receipt
                      ? tr("حوّل ثمّ أرفق الإيصال — يُضاف بعد المراجعة")
                      : tr("ادفع ثمّ يُضاف بعد المراجعة")}
                </span>
              </span>
              <Icon name="chevron_left" className="t2-m-opt-end go" />
            </button>
          ))}
        </div>
      ) : null}

      {cardEnabled || cliqEnabled ? (
        <div className="t2-list t2-m-gap">
          {cardEnabled ? (
            <button
              type="button"
              className="t2-row t2-m-opt"
              disabled={!valid}
              onClick={() => navigate("/wallet/topup", { state: { amount, channel: "card" } })}
            >
              <Icon name="credit_card" />
              <span className="t2-row-main">
                <span className="t2-row-title">{tr("بطاقة")}</span>
                <span className="t2-row-body">{tr("شحن فوري عبر صفحة الدفع الآمنة")}</span>
              </span>
              <Icon name="chevron_left" className="t2-m-opt-end go" />
            </button>
          ) : null}
          {cliqEnabled ? (
            <button
              type="button"
              className="t2-row t2-m-opt"
              disabled={!valid}
              onClick={() => navigate("/wallet/topup", { state: { amount, channel: "cliq" } })}
            >
              <Icon name="smartphone" />
              <span className="t2-row-main">
                <span className="t2-row-title">{tr("كليك")}</span>
                <span className="t2-row-body">{tr("حوّل ثم يُضاف بعد التأكد")}</span>
              </span>
              <Icon name="chevron_left" className="t2-m-opt-end go" />
            </button>
          ) : null}
        </div>
      ) : null}
    </SheetModalT2>
  );
}
