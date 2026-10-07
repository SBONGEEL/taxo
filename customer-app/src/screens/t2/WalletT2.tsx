/** المحفظة — TAXO 2.0 «R11» (Claude Design «Rider»)، **في المظهرين** — رُسم نهاريّاً، **والليليُّ برموز إسفلت الهوية نفسِها** (§٦٢/٣).
 *
 * **الطلباتُ هي هي** (`screens/WalletHome.tsx`): `GET /wallet/me` و`GET /wallet/me/transactions`
 * (ثلاثون) و`GET /wallet/me/topups` (عشرة، ويُعرض المعلَّقُ منها)، معاً عند الفتح — **ولا طلبَ رابع**.
 * والأبوابُ هي هي: ورقةُ الشحن (`TopupSheet`)، و`/wallet/transfer`، و`/account/cards` — **وبمفاتيحها**:
 * `wallet_enabled` يخفي الشحنَ والتحويلَ لا الرقم، و`wallet_transfer_enabled`، و`card_enabled`.
 *
 * **وما تغيّر طبقةُ العرض**: بطاقةُ الرصيد بالحبر وشريطاها، والحركاتُ قائمةً بأيقونةٍ لكلِّ نوعٍ ورأسِ شهر.
 *
 * **وما رسمته اللوحةُ ولم يُبنَ — بعلّته** (`TAXO2-DESIGN-CORRECTIONS.md` §١٥):
 * - **«الرصيد المتاح»**: القرار 23 يقول «الرصيد» للراكب — لا محجوزَ له، فالوصفُ يفرّق بلا فرق.
 * - **زرُّ «+» في «طرق الدفع»**: لا بابَ اليومَ يحفظ بطاقةً بلا دفعة — **وهو بندٌ ينتظر إذنَ المالك** (§٦٢-ج/١٣)،
 *   فزرٌّ لا يفعل شيئاً لا يُرسم. **والمربّعان بُنيا** (§٦٢-ج/٢٤): البطاقةُ الافتراضيةُ وكليك، و«إدارة» إلى البطاقات.
 * - **زرُّ الرمز (QR) في الرأس**: لا فعلَ له في محفظة الراكب اليوم.
 * - **عنوانُ الحركة بوجهة الرحلة** («رحلة إلى دابوق»): الحركةُ لا تحمل العنوان — فبقي اسمُ نوعها.
 *
 * **وما في المحفظة اليومَ ولم يُرسم يبقى**: دَينُ الإلغاء بجانب الرصيد، والتجميد، وطلباتُ الشحن المعلَّقة،
 * والرصيدُ بعد كلِّ حركة، **والعملةُ بجانب كلِّ مبلغ**.
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getWallet, listSavedCards, listTopups, listTransactions } from "@/api/endpoints";
import type { SavedCard, TopupRequest, Wallet, WalletTransaction, WalletTransactionType } from "@/api/types";
import { TopupSheet } from "@/components/wallet/TopupSheet";
import { EmptyState, ErrorNote, Spinner } from "@/components/ui/Feedback";
import { useCountryConfig } from "@/lib/config";
import { TOPUP_STATUS_LABEL, TRANSACTION_LABEL } from "@/lib/labels";
import { useSession } from "@/lib/session";
import { currencyLabel, formatMoney } from "@/lib/utils";

import { byMonth, startOfToday, whenParts } from "./when";

import "@/taxo2";
import "./t2.css";

/** أيقونةُ كلِّ نوعٍ بمفردات اللوحة — **وما لم تُرسم أيقونتُه فبأيقونة المحفظة**. */
const TX_ICON: Partial<Record<WalletTransactionType, string>> = {
  ride_payment: "local_taxi",
  tip_payment: "local_taxi",
  cancellation_fee: "local_taxi",
  cancellation_compensation: "local_taxi",
  topup: "add_card",
  transfer_in: "sync_alt",
  transfer_out: "sync_alt",
  // **الحجزُ المضمون** (§٦٣-ج/٣) — شارةُ الضمان نفسُها على بطاقة الحجز
  guarantee_hold: "verified_user",
  guarantee_refund: "verified_user",
  guarantee_compensation: "verified_user",
  // **المشوارُ الثابت** (§٦٣-ج/٦) — أيقونةُ «اشتراكاتي» للمقدَّم وما عاد منه
  commute_prepay: "event_repeat",
  commute_credit: "event_repeat",
  // **بين المدن** (§٦٣-ج/٧) — أيقونةُ مدخلها في «حسابي» للمقعد وردِّه
  intercity_hold: "route",
  intercity_refund: "route",
  // **الاسترداد الأسبوعي** (§٦٣-ج/٨) — نارُ سلسلته في الرئيسية نفسُها
  cashback: "local_fire_department",
};

export function WalletT2Screen() {
  const navigate = useNavigate();
  const { user } = useSession();
  const country = useCountryConfig(user?.country_code);

  const [topupOpen, setTopupOpen] = useState(false);
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [entries, setEntries] = useState<WalletTransaction[]>([]);
  const [topups, setTopups] = useState<TopupRequest[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // **مربّعُ البطاقة** (§٦٢-ج/٢٤) — طلبٌ رابعٌ خلف مفتاح البطاقة وحده، **وفشلُه لا يُسقط المحفظة**: يبقى بابُ «إدارة»
  const [cards, setCards] = useState<SavedCard[] | null>(null);

  useEffect(() => {
    Promise.all([getWallet(), listTransactions(30), listTopups(10)])
      .then(([balance, history, requests]) => {
        setWallet(balance);
        setEntries(history);
        setTopups(requests.filter((request) => request.status === "pending"));
      })
      .catch((caught: unknown) =>
        setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة المحفظة"),
      )
      .finally(() => setLoading(false));
  }, []);

  const walletEnabled = country?.features.wallet_enabled === true;
  const currency = country?.currency;
  const cardEnabled = country?.features.card_enabled === true;
  const cliqEnabled = country?.features.cliq_enabled === true;
  useEffect(() => {
    if (!cardEnabled) return;
    let cancelled = false;
    listSavedCards()
      .then((rows) => !cancelled && setCards(rows))
      .catch(() => !cancelled && setCards([]));
    return () => {
      cancelled = true;
    };
  }, [cardEnabled]);
  const card = cards?.find((row) => row.is_default) ?? cards?.[0] ?? null;
  const transferEnabled = country?.features.wallet_transfer_enabled === true;

  if (loading) {
    return (
      <div className="t2 t2-page pb-nav">
        <h1 className="t2-h1">المحفظة</h1>
        <Spinner />
      </div>
    );
  }

  const today = startOfToday();
  const months = byMonth(entries, (entry) => entry.created_at);

  return (
    <div className="t2 t2-page pb-nav">
      <h1 className="t2-h1">المحفظة</h1>

      <div className="t2-balance">
        <span className="t2-stripe a" aria-hidden="true" />
        <span className="t2-stripe b" aria-hidden="true" />
        {/* **«الرصيد» لا «الرصيد المتاح»** (القرار 23) — اللوحةُ تقول الثانية، والراكبُ لا محجوزَ له */}
        <div className="t2-balance-label">الرصيد</div>
        <div className="t2-balance-amount">
          <span dir="ltr" className="t2-num">{formatMoney(wallet?.balance)}</span>
          <span className="t2-balance-cur">{currencyLabel(wallet?.currency)}</span>
        </div>
        {walletEnabled ? (
          <div className="t2-balance-actions">
            <button type="button" className="t2-btn ember" onClick={() => setTopupOpen(true)}>
              <span className="t2-icon" aria-hidden="true">add</span>
              شحن الرصيد
            </button>
            {transferEnabled ? (
              <button type="button" className="t2-btn ghost" onClick={() => navigate("/wallet/transfer")}>
                <span className="t2-icon" aria-hidden="true">sync_alt</span>
                تحويل لصديق
              </button>
            ) : null}
          </div>
        ) : (
          <p className="t2-balance-note">المحفظة غير مفعّلة في بلدك حالياً — رصيدك محفوظ ويظهر هنا.</p>
        )}
      </div>

      {/* **دَينُ الإلغاء بجانب الرصيد لا مطروحاً منه** (`design/CANCELLATION-FEE.md` §4) — ورقمُه من الخلفية */}
      {Number(wallet?.cancellation_debt ?? 0) > 0 ? (
        <p className="t2-note warn">
          <span className="t2-icon" aria-hidden="true">error</span>
          <span>
            عليك رسومُ إلغاء {formatMoney(wallet?.cancellation_debt, wallet?.currency)}
            {" "}— تُخصم تلقائياً من أول شحنٍ لمحفظتك.
          </span>
        </p>
      ) : null}
      {wallet?.frozen ? (
        <p className="t2-note danger">
          <span className="t2-icon" aria-hidden="true">lock</span>
          <span>محفظتك مجمّدة مؤقتاً — راجع الدعم</span>
        </p>
      ) : null}

      <ErrorNote message={error} />

      {topups.length > 0 ? (
        <section>
          <div className="t2-section">طلبات شحن قيد المراجعة</div>
          <div className="t2-list">
            {topups.map((request) => {
              const when = whenParts(request.created_at, today);
              return (
                <div key={request.id} className="t2-tx">
                  <span className="t2-tx-icon">
                    <span className="t2-icon" aria-hidden="true">hourglass_top</span>
                  </span>
                  <span className="t2-tx-main">
                    <span className="t2-tx-title">{formatMoney(request.amount, request.currency)}</span>
                    <span className="t2-tx-sub">
                      {when.day} · <span dir="ltr">{when.time}</span>
                    </span>
                  </span>
                  <span className="t2-chip warn">{TOPUP_STATUS_LABEL[request.status]}</span>
                </div>
              );
            })}
          </div>
        </section>
      ) : null}

      {/* **«طرق الدفع» كما رسمتها R11** (§٦٢-ج/٢٤): مربّعُ البطاقة الافتراضية ومربّعُ كليك، و«إدارة» إلى البطاقات —
          **وكلٌّ خلف مفتاحه**. وبلا بطاقةٍ محفوظةٍ يبقى مربّعُها باباً يقول ذلك */}
      {cardEnabled || (cliqEnabled && walletEnabled) ? (
        <section>
          <div className="t2-section">
            <span>طرق الدفع</span>
            {cardEnabled ? (
              <button type="button" className="t2-section-aside t2-paytiles-manage" onClick={() => navigate("/account/cards")}>
                إدارة
              </button>
            ) : null}
          </div>
          <div className="t2-paytiles">
            {cardEnabled ? (
              <button type="button" className="t2-paytile wide" onClick={() => navigate("/account/cards")}>
                {card ? (
                  <>
                    <span className="t2-paytile-top">
                      <span dir="ltr" className="t2-paytile-brand">
                        {(card.brand ?? card.provider).toUpperCase()}
                      </span>
                      {card.is_default ? <span className="t2-chip ok">افتراضية</span> : null}
                    </span>
                    <span dir="ltr" className="t2-paytile-num">
                      •••• {card.last4}
                    </span>
                  </>
                ) : (
                  <>
                    <span className="t2-icon" aria-hidden="true">credit_card</span>
                    <span className="t2-paytile-name">{cards === null ? "البطاقات" : "لا بطاقة محفوظة"}</span>
                  </>
                )}
              </button>
            ) : null}
            {cliqEnabled && walletEnabled ? (
              <button
                type="button"
                className="t2-paytile"
                onClick={() => navigate("/wallet/topup", { state: { channel: "cliq" } })}
              >
                <span dir="ltr" className="t2-paytile-brand end">
                  CliQ
                </span>
                <span className="t2-paytile-name">كليك</span>
              </button>
            ) : null}
          </div>
        </section>
      ) : null}

      <section>
        <div className="t2-section">
          <span>الحركات</span>
          {months.length > 0 ? <span className="t2-section-aside">{months[0].label}</span> : null}
        </div>
        {entries.length === 0 ? (
          <EmptyState title="لا عمليات بعد" hint="ستظهر هنا كل حركة على رصيدك." />
        ) : (
          months.map((month, index) => (
            <div key={month.label}>
              {/* الشهرُ الأولُ في رأس القسم كما في اللوحة، وما بعده رأسٌ لكلِّ شهر */}
              {index > 0 ? <div className="t2-month">{month.label}</div> : null}
              <div className="t2-list">
                {month.items.map((entry) => {
                  const credit = !entry.amount.trimStart().startsWith("-");
                  const when = whenParts(entry.created_at, today);
                  return (
                    <div key={entry.id} className="t2-tx">
                      <span className={credit ? "t2-tx-icon in" : "t2-tx-icon"}>
                        <span className="t2-icon" aria-hidden="true">
                          {TX_ICON[entry.type] ?? "account_balance_wallet"}
                        </span>
                      </span>
                      <span className="t2-tx-main">
                        <span className="t2-tx-title">{TRANSACTION_LABEL[entry.type]}</span>
                        <span className="t2-tx-sub">
                          {when.day} · <span dir="auto">{entry.reference ?? when.time}</span>
                        </span>
                      </span>
                      <span className="t2-tx-end">
                        <span className={credit ? "t2-tx-amt in" : "t2-tx-amt"}>
                          <span dir="ltr">
                            {credit ? "+" : ""}
                            {formatMoney(entry.amount)}
                          </span>{" "}
                          {currencyLabel(entry.currency)}
                        </span>
                        <span className="t2-tx-after">الرصيد {formatMoney(entry.balance_after)}</span>
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          ))
        )}
      </section>

      {topupOpen ? (
        <TopupSheet
          currency={currency}
          cardEnabled={cardEnabled}
          cliqEnabled={cliqEnabled}
          onClose={() => setTopupOpen(false)}
        />
      ) : null}
    </div>
  );
}
