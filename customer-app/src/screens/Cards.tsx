/** البطاقات المحفوظة — «الدفع بضغطة» (SPEC القسم 6.4).
 *
 * **لا رمزَ مزودٍ يصل هنا أبداً**: الخلفية تسلّم العلامة وآخر أربعة والانتهاء
 * لا غير — الرمز هو ما يُدفع به، وعرضُه يبطل غرض الـ tokenization (القسم 4).
 *
 * وحذفُ الافتراضية يرقّي غيرها في الخلفية: محفظةُ بطاقاتٍ بلا افتراضية تجعل
 * «الدفع بضغطة» بلا ضغطة تُعرض.
 */

import { CreditCard, Star, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { deleteSavedCard, listSavedCards, setDefaultCard } from "@/api/endpoints";
import type { SavedCard } from "@/api/types";
import { Badge, EmptyState, ErrorNote, Spinner } from "@/components/ui/Feedback";
import { Screen } from "@/components/ui/Screen";

export function CardsScreen() {
  const [cards, setCards] = useState<SavedCard[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = () =>
    listSavedCards()
      .then(setCards)
      .catch((caught: unknown) =>
        setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة بطاقاتك"),
      )
      .finally(() => setLoading(false));

  useEffect(() => {
    void load();
  }, []);

  async function act(action: Promise<unknown>) {
    setError(null);
    try {
      await action;
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر تنفيذ الإجراء");
    }
  }

  return (
    <Screen title="بطاقاتي" back="/account" nav>
      {loading ? (
        <Spinner />
      ) : (
        <div className="space-y-12">
          <ErrorNote message={error} />

          {cards.length === 0 ? (
            <EmptyState
              title="لا بطاقات محفوظة"
              hint="عند الدفع بالبطاقة يمكنك اختيار حفظها للمرة القادمة."
            />
          ) : (
            <ul className="space-y-8">
              {cards.map((card) => (
                <li key={card.id} className="card flex items-center gap-12 p-16">
                  <CreditCard className="size-24 text-ink" />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-ink">
                      {card.brand ?? "بطاقة"} •••• {card.last4}
                    </p>
                    <p className="text-12 text-muted">
                      تنتهي {String(card.expiry_month).padStart(2, "0")}/{card.expiry_year}
                    </p>
                  </div>

                  {card.is_default ? (
                    <Badge tone="warning">الافتراضية</Badge>
                  ) : (
                    <button
                      type="button"
                      onClick={() => act(setDefaultCard(card.id))}
                      className="rounded-8 p-8 text-muted transition hover:bg-surface-2 hover:text-ink"
                      aria-label="اجعلها الافتراضية"
                    >
                      <Star className="size-16" />
                    </button>
                  )}

                  <button
                    type="button"
                    onClick={() => act(deleteSavedCard(card.id))}
                    className="rounded-8 p-8 text-muted transition hover:bg-surface-2 hover:text-danger"
                    aria-label="حذف البطاقة"
                  >
                    <Trash2 className="size-16" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </Screen>
  );
}
