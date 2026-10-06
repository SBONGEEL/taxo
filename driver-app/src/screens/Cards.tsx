/** البطاقات المحفوظة — SPEC القسم 6.4، **بلغة TAXO 2.0** «C25» (`design/t2-new/captain/C25*.dc.html`).
 *
 * **لا رقمَ بطاقةٍ هنا ولا رمزَ مزود**: المحفوظ لدينا `provider_token` ولا
 * يخرج من الخلفية أبداً — هو ما يُدفع به، وعرضُه يبطل غرض الـtokenization
 * كلَّه. فما تعرضه الشاشة ما يعرّف البطاقة لصاحبها: العلامة وآخر أربعة
 * وانتهاؤها.
 *
 * **ولا زرَّ «إضافة بطاقة»**: النموذج يرسمه ويصفه بـ«تحقق ١ فلس»، ولا منفذَ
 * لذلك في الخلفية — `save_card` **علامةٌ على دفعةٍ حقيقية** (اشتراك أو شحن أو
 * أجرة) لا عمليةٌ مستقلة. وقناةُ البطاقة في تطبيق الكبتن موقوفةٌ على أمرٍ
 * ثانٍ: `settings.card_return_url` عنوانٌ واحدٌ يشير إلى تطبيق الراكب، فصفحةُ
 * المزود تعيد الكبتن إلى تطبيقٍ ليس تطبيقه. الاثنان في
 * `FUTURE-FEATURES.md` بند 44، وحتى ذلك تقول الشاشة أين تُحفظ البطاقة فعلاً
 * بدل زرٍّ يعد بما لا يقع.
 *
 * **والشكلُ**: صفُّ «C12» بمربّع العلامة، **والافتراضيةُ بحافّة «المختار» في C10** ووسمِها، **والفعلان شريطٌ تحت البطاقة** —
 * كلٌّ منهما ٤٤ للمس بدل رابطين صغيرين متراكبين. **والمنطقُ حرفاً**: النداءاتُ الثلاثة، والتعطيلُ أثناء فعلِ البطاقة نفسِها.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  deleteSavedCard,
  listSavedCards,
  makeCardDefault,
} from "@/api/endpoints";
import type { SavedCard } from "@/api/types";
import { useGoBack } from "@/lib/back";
import { Icon } from "@/taxo2";

import "@/screens/t2/account.css";

export function CardsScreen() {
  const goBack = useGoBack();
  const [cards, setCards] = useState<SavedCard[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setCards(await listSavedCards());
  }, []);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة البطاقات",
      ),
    );
  }, [load]);

  async function act(cardId: string, action: () => Promise<unknown>) {
    setBusy(cardId);
    setError(null);
    try {
      await action();
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر التنفيذ");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="t2 t2-ax">
      <div className="t2-ax-scroll">
        <div className="t2-head">
          <button type="button" className="t2-back" aria-label="رجوع" onClick={() => goBack()}>
            <Icon name="arrow_forward" />
          </button>
          <h1 className="t2-title">البطاقات المحفوظة</h1>
        </div>

        {error ? (
          <p className="t2-note danger" role="alert">
            <Icon name="error" />
            {error}
          </p>
        ) : null}

        {cards === null && !error ? (
          <div className="t2-ax-center">
            <span className="t2-ax-spin" role="status" aria-label="جارٍ التحميل" />
          </div>
        ) : null}

        {cards?.length === 0 ? (
          <div className="t2-empty t2-ax-empty">
            <b>لا بطاقات محفوظة</b>
            <span>تُحفظ البطاقة حين تدفع بها وتختار حفظها — لا من هذه الشاشة.</span>
          </div>
        ) : null}

        <div className="t2-pcard-list">
          {(cards ?? []).map((card) => (
            <div
              key={card.id}
              className={card.is_default ? "t2-pcard default" : "t2-pcard"}
            >
              <div className="t2-pcard-top">
                <span className="t2-pcard-brand">{card.brand ?? "بطاقة"}</span>
                <div className="t2-pcard-main">
                  {/* ما هو مطبوعٌ على البطاقة يُعرض كما هو ليطابقها الكبتن
                      بعينه — الأرقام العربية-الهندية للكميات لا للمعرّفات */}
                  <div dir="ltr" className="t2-pcard-num">
                    •••• {card.last4}
                  </div>
                  <div dir="ltr" className="t2-pcard-exp">
                    {String(card.expiry_month).padStart(2, "0")}/{card.expiry_year}
                  </div>
                </div>
                {card.is_default ? <span className="t2-chip ok">افتراضية</span> : null}
              </div>
              <div className="t2-pcard-acts">
                {card.is_default ? null : (
                  <button
                    type="button"
                    disabled={busy === card.id}
                    onClick={() =>
                      void act(card.id, () => makeCardDefault(card.id))
                    }
                    className="t2-pcard-act"
                  >
                    اجعلها افتراضية
                  </button>
                )}
                <button
                  type="button"
                  disabled={busy === card.id}
                  onClick={() =>
                    void act(card.id, () => deleteSavedCard(card.id))
                  }
                  className="t2-pcard-act danger"
                  aria-label={`حذف البطاقة •••• ${card.last4}`}
                >
                  حذف
                </button>
              </div>
            </div>
          ))}
        </div>

        <p className="t2-ax-fine">
          <Icon name="lock" />
          <span>
            لا نحتفظ برقم بطاقتك ولا برمزها السري — رمزٌ من المزوّد فقط. وتُحفظ
            البطاقة حين تدفع بها وتختار حفظها.
          </span>
        </p>
      </div>
    </div>
  );
}
