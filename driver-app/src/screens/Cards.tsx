/** البطاقات المحفوظة — SPEC القسم 6.4، وشكلُها من `DESIGN.md` §5.3.
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
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import {
  deleteSavedCard,
  listSavedCards,
  makeCardDefault,
} from "@/api/endpoints";
import type { SavedCard } from "@/api/types";
import { EmptyNote, ErrorNote, Spinner } from "@/components/ui/Feedback";
import { cn } from "@/lib/utils";

export function CardsScreen() {
  const navigate = useNavigate();
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
    <div className="scr h-full bg-bg px-16 pb-12 pt-safe">
      <div className="mb-16 mt-6 flex items-center gap-10">
        <button
          type="button"
          onClick={() => navigate(-1)}
          aria-label="رجوع"
          className="text-18 text-muted"
        >
          →
        </button>
        <h1 className="text-20 font-bold text-ink">البطاقات المحفوظة</h1>
      </div>

      <ErrorNote message={error} />

      {cards === null && !error ? <Spinner className="mx-auto" /> : null}

      {cards?.length === 0 ? (
        <EmptyNote
          title="لا بطاقات محفوظة"
          hint="تُحفظ البطاقة حين تدفع بها وتختار حفظها — لا من هذه الشاشة."
        />
      ) : null}

      <div className="flex flex-col gap-10">
        {(cards ?? []).map((card) => (
          <div
            key={card.id}
            className={cn(
              "flex items-center gap-12 rounded-16 border bg-surface p-15",
              card.is_default ? "border-ink" : "border-line",
            )}
          >
            <span className="flex h-27 w-40 flex-none items-center justify-center overflow-hidden rounded-5 border border-line bg-surface-2 px-2 text-9 font-bold text-ink">
              {card.brand ?? "بطاقة"}
            </span>
            <div className="min-w-0 flex-1">
              {/* ما هو مطبوعٌ على البطاقة يُعرض كما هو ليطابقها الكبتن
                  بعينه — الأرقام العربية-الهندية للكميات لا للمعرّفات */}
              <div dir="ltr" className="text-13.5 font-bold text-ink">
                •••• {card.last4}
              </div>
              <div dir="ltr" className="text-end text-11 text-muted">
                {String(card.expiry_month).padStart(2, "0")}/{card.expiry_year}
              </div>
            </div>
            <div className="flex flex-col items-end gap-5">
              {card.is_default ? (
                <span className="text-10.5 font-bold text-ok">افتراضية</span>
              ) : (
                <button
                  type="button"
                  disabled={busy === card.id}
                  onClick={() =>
                    void act(card.id, () => makeCardDefault(card.id))
                  }
                  className="text-10.5 font-bold text-muted disabled:opacity-60"
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
                className="text-10.5 text-danger disabled:opacity-60"
              >
                حذف
              </button>
            </div>
          </div>
        ))}
      </div>

      <p className="mt-14 text-11.5 leading-note text-muted">
        لا نحتفظ برقم بطاقتك ولا برمزها السري — رمزٌ من المزوّد فقط. وتُحفظ
        البطاقة حين تدفع بها وتختار حفظها.
      </p>
    </div>
  );
}
