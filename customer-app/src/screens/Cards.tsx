/** البطاقات المحفوظة — «الدفع بضغطة» (SPEC القسم 6.4).
 *
 * **لا رمزَ مزودٍ يصل هنا أبداً**: الخلفية تسلّم العلامة وآخر أربعة والانتهاء
 * لا غير — الرمز هو ما يُدفع به، وعرضُه يبطل غرض الـ tokenization (القسم 4).
 *
 * وحذفُ الافتراضية يرقّي غيرها في الخلفية: محفظةُ بطاقاتٍ بلا افتراضية تجعل
 * «الدفع بضغطة» بلا ضغطة تُعرض.
 *
 * **بلغة TAXO 2.0** (لوحتا `design/t2-new/rider/R21` · `R21b`): مربّعُ «طرق الدفع» في R11 بعرض الشاشة — العلامةُ وشارةُ
 * «الافتراضية» فوق، والرقمُ والانتهاءُ تحت، والفعلان في سطرٍ أخير. **ولا زرَّ «إضافة»**: البطاقةُ تُحفظ عند الدفع وحدَه، والفراغُ
 * يقول ذلك. **والنداءاتُ الثلاثةُ حرفاً** — ولا تأكيدَ للحذف كما لم يكن.
 */

import { useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { deleteSavedCard, listSavedCards, setDefaultCard } from "@/api/endpoints";
import type { SavedCard } from "@/api/types";
import { useGoBack } from "@/lib/back";
import { Icon } from "@/taxo2";
import { BannerT2, HeadT2, WaitT2 } from "@/screens/t2/MoneyT2";

export function CardsScreen() {
  // **من حيث جئت، و«حسابي» لمن دخل مباشرةً** (`lib/back.ts`) — كما كان رأسُ الشاشة
  const goBack = useGoBack("/account");
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
    <div className="t2 t2-m-page">
      <HeadT2 title="بطاقاتي" onBack={goBack} />

      {loading ? (
        <WaitT2 />
      ) : (
        <>
          <BannerT2 tone="danger" message={error} />

          {cards.length === 0 ? (
            <div className="t2-m-empty">
              <span className="t2-m-empty-icon" aria-hidden="true">
                <Icon name="credit_card" />
              </span>
              <div className="t2-m-empty-title">لا بطاقات محفوظة</div>
              <p className="t2-m-empty-hint">عند الدفع بالبطاقة يمكنك اختيار حفظها للمرة القادمة.</p>
            </div>
          ) : (
            <ul className="t2-m-saved">
              {cards.map((card) => (
                <li key={card.id} className="t2-m-saved-card">
                  <div className="t2-m-saved-top">
                    <span dir="ltr" className="t2-m-brand">
                      {card.brand ?? "بطاقة"}
                    </span>
                    {card.is_default ? <span className="t2-m-default">الافتراضية</span> : null}
                  </div>
                  <div className="t2-m-saved-mid">
                    <span dir="ltr" className="t2-m-last4">
                      •••• {card.last4}
                    </span>
                    <span className="t2-m-expiry">
                      تنتهي <span dir="ltr">{String(card.expiry_month).padStart(2, "0")}/{card.expiry_year}</span>
                    </span>
                  </div>
                  <div className={card.is_default ? "t2-m-saved-acts end" : "t2-m-saved-acts"}>
                    {card.is_default ? null : (
                      <button type="button" className="t2-m-make-default" onClick={() => act(setDefaultCard(card.id))}>
                        <Icon name="star" />
                        اجعلها الافتراضية
                      </button>
                    )}
                    <button
                      type="button"
                      className="t2-m-delete"
                      onClick={() => act(deleteSavedCard(card.id))}
                      aria-label="حذف البطاقة"
                    >
                      <Icon name="delete" />
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}
