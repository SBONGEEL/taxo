/** «الدفع بضغطة» — اختيار بطاقةٍ محفوظة أو بطاقةٍ جديدة (SPEC القسم 6.4).
 *
 * البطاقة المحفوظة تُحسم **بلا صفحة دفع**: الخلفية تخصم على الرمز وتعيد الطلب
 * محسوماً. والجديدة تفتح صفحة المزود، و**حفظُها قرار صاحبها لا افتراضنا** —
 * فالمفتاح مطفأٌ ابتداءً.
 *
 * ولا يظهر هذا الاختيار إلا إن كانت للمستخدم بطاقةٌ محفوظة: قائمةٌ من عنصرٍ
 * واحد اسمه «بطاقة جديدة» خطوةٌ زائدة بين الراكب ودفعه.
 */

import { CreditCard, Plus } from "lucide-react";
import { useEffect, useState } from "react";

import { listSavedCards } from "@/api/endpoints";
import type { SavedCard } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";

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
    <section className="card space-y-3 p-4">
      <h2 className="font-semibold text-ink">الدفع بالبطاقة</h2>

      {cards.length > 0 ? (
        <ul className="space-y-2">
          {cards.map((card) => (
            <li key={card.id}>
              <button
                type="button"
                onClick={() => setSelected(card.id)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-start transition",
                  selected === card.id
                    ? "border-brand bg-brand/10"
                    : "border-line hover:bg-line/30",
                )}
              >
                <CreditCard className="size-5 text-ink" />
                <span className="flex-1">
                  <span className="block font-medium text-ink">
                    {card.brand ?? "بطاقة"} •••• {card.last4}
                  </span>
                  <span className="block text-xs text-muted">
                    تنتهي {String(card.expiry_month).padStart(2, "0")}/{card.expiry_year}
                  </span>
                </span>
              </button>
            </li>
          ))}
          <li>
            <button
              type="button"
              onClick={() => setSelected(null)}
              className={cn(
                "flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-start transition",
                selected === null
                  ? "border-brand bg-brand/10"
                  : "border-line hover:bg-line/30",
              )}
            >
              <Plus className="size-5 text-ink" />
              <span className="font-medium text-ink">بطاقة جديدة</span>
            </button>
          </li>
        </ul>
      ) : null}

      {selected === null ? (
        <label className="flex items-center gap-2 text-sm text-muted">
          <input
            type="checkbox"
            className="size-4 accent-[rgb(var(--brand))]"
            checked={save}
            onChange={(event) => setSave(event.target.checked)}
          />
          احفظ هذه البطاقة للدفع بضغطة لاحقاً
        </label>
      ) : null}

      <div className="flex gap-2">
        <Button
          className="flex-1"
          loading={busy}
          onClick={() =>
            onPay(
              selected === null ? { save_card: save } : { saved_card_id: selected },
            )
          }
        >
          {selected === null ? "متابعة إلى صفحة الدفع" : "ادفع الآن"}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={busy}>
          تراجع
        </Button>
      </div>
    </section>
  );
}
