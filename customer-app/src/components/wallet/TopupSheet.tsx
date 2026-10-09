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
import { useNavigate } from "react-router-dom";

import { QUICK_TOPUP_AMOUNTS } from "@/lib/wallet";
import { notMultipleMessage, unitHint } from "@/lib/rounding";
import { formatMoney } from "@/lib/utils";
import { Icon } from "@/taxo2";
import { AmountCardT2, QuickAmountsT2, SheetModalT2, UnitNoteT2 } from "@/screens/t2/MoneyT2";

export function TopupSheet({
  currency,
  unit,
  cardEnabled,
  cliqEnabled,
  onClose,
}: {
  currency: string | undefined;
  /** **وحدةُ التقريب مشتعلاً** (`lib/rounding.ts`) و`null` مطفأً — المبلغُ مضاعفٌ لها وإلا لا تُفتح قناة (SPEC §٧٠-ج/٦) */
  unit: string | null;
  cardEnabled: boolean;
  cliqEnabled: boolean;
  onClose: () => void;
}) {
  const navigate = useNavigate();
  const [amount, setAmount] = useState("10");
  const unitError = notMultipleMessage(amount, unit, currency);
  const valid = Number(amount) > 0 && unitError === null;

  return (
    <SheetModalT2 onClose={onClose}>
      <div className="t2-m-sheet-title">شحن الرصيد</div>
      <p className="t2-m-sheet-sub">اختر المبلغ ثم طريقة الشحن.</p>

      <AmountCardT2 id="topup-sheet-amount" label="المبلغ" value={amount} onChange={setAmount} currency={currency}>
        <QuickAmountsT2
          amounts={QUICK_TOPUP_AMOUNTS}
          value={amount}
          onPick={setAmount}
          label={(value) => formatMoney(value, currency)}
        />
      </AmountCardT2>
      <UnitNoteT2 hint={unitHint(unit, currency)} error={unitError} />

      {/* **القنواتُ صفوفٌ لا حبّات** كما في التصميم: لكلٍّ سطرُ شرحٍ يقول ما يقع بعد الضغط — «فوريّ» أم «بعد التأكد».
          والقناةُ الغائبةُ لا تُرسم معطّلةً: مفتاحُها مطفأٌ في هذا السوق */}
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
                <span className="t2-row-title">بطاقة</span>
                <span className="t2-row-body">شحن فوري عبر صفحة الدفع الآمنة</span>
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
                <span className="t2-row-title">كليك</span>
                <span className="t2-row-body">حوّل ثم يُضاف بعد التأكد</span>
              </span>
              <Icon name="chevron_left" className="t2-m-opt-end go" />
            </button>
          ) : null}
        </div>
      ) : null}
    </SheetModalT2>
  );
}
