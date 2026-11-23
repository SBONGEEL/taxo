/** **بيعُ بطاقات TAXO** (أمرُ المالك ٢٠٢٦-١١-٢٣، `design/CAPTAIN-CARDS-2026-11-23.md`، الترحيلة `0189`).
 *
 * الكبتنُ يشتري دفعةً من محفظته بخصمٍ يضبطه المالك، ثمّ يفتح كلَّ بطاقةٍ ليُري الراكبَ رمزَها وQR **ويقبض قيمتَها نقداً**.
 * **كلُّ مبلغٍ هنا من الخلفية** (§14): كلفةُ البطاقة وما يُخصم قبل التأكيد ورصيدُه — والواجهةُ تعرض.
 * **ومفتاحُ تكرارٍ واحدٌ لكلِّ تأكيد**: ضغطتان أو انقطاعُ شبكةٍ لا يشتريان مرّتين.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { buyCaptainCards, getCaptainCardCode, getCaptainSales, listCaptainCards, quoteCaptainCards } from "@/api/endpoints";
import type { CaptainCard, CaptainCardCode, CaptainQuote, CaptainSales } from "@/api/types";
import { useGoBack } from "@/lib/back";
import { tr } from "@/lib/i18n";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { digits, formatAmount } from "@/lib/utils";
import { Icon } from "@/taxo2";

import "./fields.css";
import "./money.css";
import "./payrequest.css";

function newKey(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

/** **حالُ البطاقة بالترجمة** — حرفيّاتُ `tr` صريحةٌ ليقرأها جردُ النصوص */
function stateLabel(state: CaptainCard["state"]): string {
  if (state === "unused") return tr("لم تُبع بعد");
  if (state === "redeemed") return tr("شحنها راكب");
  if (state === "expired") return tr("انتهت");
  if (state === "cancelled") return tr("ملغاة");
  return tr("لم تبدأ");
}

export function CaptainCardsT2Screen() {
  const goBack = useGoBack("/account");
  const [sales, setSales] = useState<CaptainSales | null>(null);
  const [cards, setCards] = useState<CaptainCard[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [denomination, setDenomination] = useState<string | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [quote, setQuote] = useState<CaptainQuote | null>(null);
  const [key, setKey] = useState(newKey);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [shown, setShown] = useState<CaptainCardCode | null>(null);

  const load = useCallback(async () => {
    const [state, mine] = await Promise.all([getCaptainSales(), listCaptainCards()]);
    setSales(state);
    setCards(mine);
    setDenomination((current) => current ?? state.denominations[0]?.id ?? null);
  }, []);

  useEffect(() => {
    load().catch((caught) => setError(caught instanceof ApiError ? caught.message : tr("تعذّر التحميل — أعد المحاولة")));
  }, [load]);

  const max = Math.max(0, Math.min(sales?.remaining_today ?? 0, 100));
  useEffect(() => {
    setQuote(null);
    if (!sales?.open || !denomination || quantity < 1 || quantity > max) return;
    let alive = true;
    quoteCaptainCards(denomination, quantity)
      .then((row) => alive && setQuote(row))
      .catch(() => alive && setQuote(null));
    return () => {
      alive = false;
    };
  }, [sales, denomination, quantity, max]);

  async function buy() {
    if (!denomination) return;
    setBusy(true);
    setError(null);
    try {
      const bought = await buyCaptainCards(denomination, quantity, key);
      setDone(
        tr("اشتريتَ {0} بطاقة — خُصم {1} {2}، ورصيدُك الآن {3} {2}.", {
          0: digits(String(bought.quantity)),
          1: formatAmount(bought.cost_amount, bought.currency),
          2: CURRENCY_LABEL[bought.currency],
          3: formatAmount(bought.balance_amount, bought.currency),
        }),
      );
      setKey(newKey());
      setQuantity(1);
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : tr("تعذّر الشراء — أعد المحاولة"));
    } finally {
      setBusy(false);
    }
  }

  async function open(card: CaptainCard) {
    setError(null);
    try {
      setShown(await getCaptainCardCode(card.id));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : tr("تعذّر فتح البطاقة"));
    }
  }

  const label = sales ? CURRENCY_LABEL[sales.currency] : "";
  const unsold = cards.filter((card) => card.state === "unused");
  const rest = cards.filter((card) => card.state !== "unused");

  return (
    <div className="t2 t2-clq-page scr">
      <div className="t2-head">
        <button type="button" className="t2-back" aria-label={tr("رجوع")} onClick={() => (shown ? setShown(null) : goBack())}>
          <Icon name="arrow_forward" />
        </button>
        <h1 className="t2-title">{tr("بيع بطاقات TAXO")}</h1>
      </div>

      {shown ? (
        <div className="t2-wdl-card t2-pr-done">
          <h2 className="t2-pr-done-title">
            {formatAmount(shown.amount, shown.currency)} {CURRENCY_LABEL[shown.currency]}
          </h2>
          <img src={shown.qr_svg} alt={tr("رمز QR للبطاقة")} width={220} height={220} style={{ background: "#fff", borderRadius: 12 }} />
          <p className="t2-pr-done-text">
            <b dir="ltr" style={{ fontSize: 20, letterSpacing: 1 }}>
              {shown.code}
            </b>
          </p>
          <p className="t2-pr-done-text">{tr("يمسح الراكبُ الرمزَ بكاميرا هاتفه أو يكتبه في «شحن ببطاقة TAXO» في محفظته.")}</p>
          <p className="t2-fld-hint" dir="ltr">
            {shown.serial}
          </p>
          <p className="t2-fld-hint">{tr("خذ قيمتَها نقداً قبل أن تُريه الرمز.")}</p>
          <button type="button" className="t2-clq-cta t2-pr-gap" onClick={() => setShown(null)}>
            {tr("تم")}
          </button>
        </div>
      ) : (
        <>
          {sales === null && !error ? <p className="t2-fld-hint">{tr("جارٍ…")}</p> : null}
          {sales && !sales.open ? (
            <p className="t2-note">{tr("بيعُ بطاقات TAXO غيرُ مفتوحٍ في بلدك الآن.")}</p>
          ) : null}

          {sales?.open ? (
            <div className="t2-wdl-card">
              <p className="t2-fld-label">{tr("الفئة")}</p>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {sales.denominations.map((row) => (
                  <button
                    key={row.id}
                    type="button"
                    className={row.id === denomination ? "t2-clq-cta" : "t2-link"}
                    style={{ flex: "0 0 auto", padding: "8px 14px" }}
                    aria-pressed={row.id === denomination}
                    onClick={() => setDenomination(row.id)}
                  >
                    {formatAmount(row.amount, row.currency)} {label}
                    <span className="t2-fld-hint" style={{ display: "block" }}>
                      {tr("تدفع {0} {1}", { 0: formatAmount(row.unit_cost_amount, row.currency), 1: label })}
                    </span>
                  </button>
                ))}
              </div>

              <label className="t2-fld-label" htmlFor="captain-cards-qty">
                {tr("العدد")}
              </label>
              <input
                id="captain-cards-qty"
                className="t2-fld"
                dir="ltr"
                inputMode="numeric"
                value={String(quantity)}
                onChange={(event) => setQuantity(Number(event.target.value.replace(/[^0-9]/g, "") || "0"))}
              />
              <p className="t2-fld-hint">
                {tr("بقي لك اليوم {0} بطاقة · رصيدُ محفظتك {1} {2}", {
                  0: digits(String(sales.remaining_today)),
                  1: formatAmount(sales.balance_amount, sales.currency),
                  2: label,
                })}
              </p>
              {quote ? (
                <p className="t2-pr-done-text">
                  {tr("قيمتُها {0} {2} · يُخصم من محفظتك {1} {2}", {
                    0: formatAmount(quote.face_amount, quote.currency),
                    1: formatAmount(quote.cost_amount, quote.currency),
                    2: label,
                  })}
                </p>
              ) : null}
              <button
                type="button"
                className="t2-clq-cta t2-pr-gap"
                disabled={busy || !quote || quantity < 1 || quantity > max}
                aria-busy={busy}
                onClick={() => void buy()}
              >
                {busy ? tr("جارٍ…") : tr("اشترِ البطاقات")}
              </button>
            </div>
          ) : null}

          {done ? (
            <p className="t2-note" role="status">
              <Icon name="check_circle" fill />
              {done}
            </p>
          ) : null}
          {error ? (
            <p className="t2-note danger" role="alert">
              <Icon name="error" fill />
              {error}
            </p>
          ) : null}

          {unsold.length ? <p className="t2-fld-label">{tr("بطاقاتي غيرُ المبيعة")}</p> : null}
          {unsold.map((card) => (
            <button key={card.id} type="button" className="t2-wdl-card" style={{ display: "flex", width: "100%", justifyContent: "space-between", marginBottom: 8 }} onClick={() => void open(card)}>
              <span>
                {formatAmount(card.amount, card.currency)} {CURRENCY_LABEL[card.currency]}
                <span className="t2-fld-hint" dir="ltr" style={{ display: "block" }}>
                  {card.serial}
                </span>
              </span>
              <span className="t2-link">{tr("افتح للبيع")}</span>
            </button>
          ))}
          {rest.length ? <p className="t2-fld-label">{tr("السابقة")}</p> : null}
          {rest.map((card) => (
            <div key={card.id} className="t2-wdl-card" style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
              <span>
                {formatAmount(card.amount, card.currency)} {CURRENCY_LABEL[card.currency]}
                <span className="t2-fld-hint" dir="ltr" style={{ display: "block" }}>
                  {card.serial}
                </span>
              </span>
              <span className="t2-fld-hint">{stateLabel(card.state)}</span>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
