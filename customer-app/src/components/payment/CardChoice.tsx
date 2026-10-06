/** «الدفع بضغطة» — اختيار بطاقةٍ محفوظة أو بطاقةٍ جديدة (SPEC القسم 6.4).
 *
 * البطاقة المحفوظة تُحسم **بلا صفحة دفع**: الخلفية تخصم على الرمز وتعيد الطلب
 * محسوماً. والجديدة تفتح صفحة المزود، و**حفظُها قرار صاحبها لا افتراضنا** —
 * فالمفتاح مطفأٌ ابتداءً.
 *
 * ولا يظهر هذا الاختيار إلا إن كانت للمستخدم بطاقةٌ محفوظة: قائمةٌ من عنصرٍ
 * واحد اسمه «بطاقة جديدة» خطوةٌ زائدة بين الراكب ودفعه.
 *
 * **بلغة TAXO 2.0 ورقةً فوق شاشة الدفع** (لوحةُ `design/t2-new/rider/R19c`) — أختُ «طريقة الدفع»: صفوفٌ بعلامة الاختيار، والالتزامُ
 * بالجمر في قدمٍ لا تُمرَّر. **والمنطقُ حرفاً**: النداءُ نفسُه، والافتراضيةُ مختارةٌ ابتداءً، والحفظُ للجديدة وحدَها، و«تراجع»
 * معطّلٌ ما دام الدفعُ جارياً — **والظلُّ كذلك لا يُغلقها حينها**.
 */

import { useEffect, useState } from "react";

import { listSavedCards } from "@/api/endpoints";
import type { SavedCard } from "@/api/types";
import { Icon } from "@/taxo2";
import { BusyLabel, SheetModalT2 } from "@/screens/t2/MoneyT2";

export function CardChoice({
  busy,
  onPay,
  onCancel,
}: {
  busy: boolean;
  onPay: (extras: { save_card?: boolean; saved_card_id?: string }) => void;
  onCancel: () => void;
}) {
  const [cards, setCards] = useState<SavedCard[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [save, setSave] = useState(false);

  useEffect(() => {
    listSavedCards()
      .then((saved) => {
        setCards(saved);
        setSelected(saved.find((card) => card.is_default)?.id ?? null);
      })
      .catch(() => setCards([]));
  }, []);

  if (cards === null) return null;

  return (
    <SheetModalT2
      onClose={busy ? null : onCancel}
      footer={
        <div className="t2-m-foot">
          <button
            type="button"
            className="t2-button action t2-m-cta"
            disabled={busy}
            aria-busy={busy}
            onClick={() =>
              onPay(selected === null ? { save_card: save } : { saved_card_id: selected })
            }
          >
            <BusyLabel busy={busy}>{selected === null ? "متابعة إلى صفحة الدفع" : "ادفع الآن"}</BusyLabel>
          </button>
          <button type="button" className="t2-button secondary t2-m-wide" onClick={onCancel} disabled={busy}>
            تراجع
          </button>
        </div>
      }
    >
      <div className="t2-m-sheet-title">الدفع بالبطاقة</div>

      {cards.length > 0 ? (
        <div className="t2-list" role="radiogroup" aria-label="الدفع بالبطاقة">
          {cards.map((card) => (
            <button
              key={card.id}
              type="button"
              role="radio"
              aria-checked={selected === card.id}
              onClick={() => setSelected(card.id)}
              className="t2-row t2-m-opt"
            >
              <Icon name="credit_card" />
              <span className="t2-row-main">
                <span className="t2-row-title">
                  <span dir="ltr">
                    {card.brand ?? "بطاقة"} •••• {card.last4}
                  </span>
                </span>
                <span className="t2-row-body">
                  تنتهي <span dir="ltr">{String(card.expiry_month).padStart(2, "0")}/{card.expiry_year}</span>
                </span>
              </span>
              {selected === card.id ? <Icon name="check" className="t2-m-opt-end check" /> : null}
            </button>
          ))}
          <button
            type="button"
            role="radio"
            aria-checked={selected === null}
            onClick={() => setSelected(null)}
            className="t2-row t2-m-opt single"
          >
            <Icon name="add" />
            <span className="t2-row-main">
              <span className="t2-row-title">بطاقة جديدة</span>
            </span>
            {selected === null ? <Icon name="check" className="t2-m-opt-end check" /> : null}
          </button>
        </div>
      ) : null}

      {selected === null ? (
        <label className="t2-m-check">
          <input type="checkbox" checked={save} onChange={(event) => setSave(event.target.checked)} />
          <span className="t2-m-check-box" aria-hidden="true">
            <Icon name="check" />
          </span>
          <span>احفظ هذه البطاقة للدفع بضغطة لاحقاً</span>
        </label>
      ) : null}
    </SheetModalT2>
  );
}
