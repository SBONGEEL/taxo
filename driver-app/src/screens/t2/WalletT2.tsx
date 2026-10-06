/** الأرباحُ والمحفظةُ والسحب — TAXO 2.0 «C09» (Claude Design «Captain»)، **في الداكن المرسوم وحدَه**.
 *
 * **وجهٌ ثانٍ لشاشتين لا شاشةٌ ثالثة**: المحفظةُ وحجزُها ودفترُها وطلبُ السحب من `useWalletScreen` (`screens/Wallet.tsx`)،
 * والفترةُ وأرقامُها من `useEarningsScreen` (`screens/Earnings.tsx`) — **فالطلباتُ طلباتُ الشاشتين بعينها**، والسحبُ
 * يمرّ بورقته نفسِها (`WithdrawSheet`): كليك وحدَه، والمبلغُ يُكتب ويُرسل كما هو اليوم.
 *
 * **ولا حسابَ هنا** (§14): كلُّ رقمٍ يصل من الخلفية جاهزاً — الصافي والمتاحُ والحجزُ وأرصدةُ الدفتر.
 *
 * **وما رسمته اللوحةُ ولم يُبنَ — بعلّته** (`design/TAXO2-DESIGN-CORRECTIONS.md` §٢٥):
 * - **رسمُ أيّام الأسبوع وقيمةُ اليوم عليه**: `GET /drivers/me/earnings` يجيب بمجموع الفترة لا بأيّامها.
 * - **«+12% عن الأسبوع الماضي»**: لا فترةَ سابقةَ في الجواب — والنسبةُ بين فترتين حسابُ مالٍ في الواجهة.
 * - **«31 ساعة»**: لا ساعاتِ عملٍ في أيِّ باب.
 * - **«يصل خلال يوم عمل»**: وعدٌ بموعدٍ لا مصدرَ له — فبقي سطرُ الحجز بنصّه القائم.
 * - **شريطُ التبويب (الرئيسية · الأرباح · المستوى · حسابي)**: يخالف تبويبات اليوم — والشريطُ القائمُ باقٍ فوق الشاشة.
 *
 * **وما في الشاشتين ولم يُرسم يبقى بلغة اللوحة**: تفصيلُ الصافي (الأرباح · العمولة · البقشيش · السلفة · المُحصَّل
 * مباشرة) في موضع الرسم · سطورُ الحجز والإيقاف والمستحقّات والعمولة · التجميد · وقتُ كلِّ حركةٍ ورصيدُها بعدها ·
 * «عرض المزيد» · بابُ «طلبات السحب».
 */

import type { Earnings, WalletTransactionType } from "@/api/types";
import { WithdrawSheet } from "@/components/WithdrawSheet";
import { Spinner } from "@/components/ui/Feedback";
import { CURRENCY_LABEL, formatWhen } from "@/lib/rideFormat";
import { digits } from "@/lib/utils";
import { TRANSACTION_LABEL, isDebit, unsigned } from "@/lib/walletFormat";
import { PERIOD_LABEL, useEarningsScreen } from "@/screens/Earnings";
import { useWalletScreen } from "@/screens/Wallet";

import { countRides } from "./count";

import "@/taxo2";
import "./t2.css";

/** **أيقونةُ كلِّ قيدٍ بمصدره** كما في الشاشة القائمة (`TRANSACTION_ICON`) — بحروف Material، والاشتراكُ كما رسمته اللوحة. */
const TX_ICON: Record<WalletTransactionType, string> = {
  topup: "account_balance_wallet",
  ride_payment: "directions_car",
  ride_earning: "directions_car",
  commission: "percent",
  transfer_in: "swap_horiz",
  transfer_out: "swap_horiz",
  withdrawal: "payments",
  refund: "undo",
  subscription_payment: "card_membership",
  adjustment: "balance",
  tip: "redeem",
  tip_payment: "redeem",
  advance: "payments",
  advance_repayment: "payments",
  cancellation_fee: "balance",
  cancellation_compensation: "balance",
  referral_bonus: "redeem",
  skin_purchase: "directions_car",
};

export function WalletT2Screen() {
  const w = useWalletScreen();
  const e = useEarningsScreen();

  if (!w.wallet) {
    return (
      <div className="t2 t2-wal t2-wal-loading">
        {w.error ? (
          <p className="t2-note danger">
            <span className="t2-icon" aria-hidden="true">
              error
            </span>
            {w.error}
          </p>
        ) : (
          <Spinner />
        )}
      </div>
    );
  }

  const wallet = w.wallet;
  const currency = CURRENCY_LABEL[wallet.currency];
  const alias = w.profile?.driver.cliq_alias ?? null;
  const data = e.data;
  // **الإشارةُ من النصّ كما في «أرباحي»** — لا طرحَ ولا مقارنةَ بصفر
  const negative = data ? data.net.trimStart().startsWith("-") : false;

  return (
    <div className="t2 t2-wal">
      <div className="t2-wal-scroll scr pb-nav">
        <div className="t2-wal-head">
          <h1 className="t2-wal-title">الأرباح</h1>
          <div className="t2-wal-period" role="tablist" aria-label="الفترة">
            {(Object.keys(PERIOD_LABEL) as Earnings["period"][]).map((key) => (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={key === e.period}
                className={
                  key === e.period
                    ? "t2-wal-period-opt on"
                    : "t2-wal-period-opt"
                }
                onClick={() => e.setPeriod(key)}
              >
                {PERIOD_LABEL[key]}
              </button>
            ))}
          </div>
        </div>

        {e.error ? (
          <p className="t2-note danger">
            <span className="t2-icon" aria-hidden="true">
              error
            </span>
            {e.error}
          </p>
        ) : null}

        {data === null ? (
          e.error ? null : (
            <div className="t2-wal-wait">
              <Spinner />
            </div>
          )
        ) : (
          <>
            {/* **الرقمُ الكبيرُ صافي ما دخل المحفظة** — والكاشُ وكليك خارجه، فيُقال اسمُه تحته */}
            <div className={negative ? "t2-wal-net negative" : "t2-wal-net"}>
              <span className="t2-wal-net-num" dir="ltr">
                {digits(data.net)}
              </span>
              <span className="t2-wal-net-cur">
                {CURRENCY_LABEL[data.currency]}
              </span>
            </div>
            <div className="t2-wal-sub">
              <span>صافي ما دخل محفظتك</span>
              <span>{countRides(data.completed_rides)}</span>
            </div>

            {/* ── تفصيلُ الصافي في موضع الرسم: أرقامُ «أرباحي» كما تصل ── */}
            <div className="t2-wal-break">
              <div className="t2-wal-line">
                <span>أرباح الرحلات</span>
                <span dir="ltr">{digits(data.wallet_earnings)}</span>
              </div>
              <div className="t2-wal-line">
                <span>عمولة</span>
                <span dir="ltr">{digits(data.commission)}</span>
              </div>
              {Number(data.tips) > 0 ? (
                <div className="t2-wal-line ok">
                  <span>بقشيش — كاملاً بلا عمولة</span>
                  <span dir="ltr">{digits(data.tips)}</span>
                </div>
              ) : null}
              {Number(data.advance_repaid) > 0 ? (
                <div className="t2-wal-line">
                  <span>سدادُ سلفة</span>
                  <span dir="ltr">{digits(data.advance_repaid)}</span>
                </div>
              ) : null}
              <div className="t2-wal-line">
                <span>مُحصَّل مباشرة</span>
                <span>
                  {digits(data.directly_collected)}{" "}
                  {CURRENCY_LABEL[data.currency]}
                </span>
              </div>
              <p className="t2-wal-hint">
                كاش وكليك قبضتَهما من الركّاب مباشرةً — لا تدخل رصيد محفظتك،
                وتظهر هنا لأنها من دخلك.
              </p>
              {negative ? (
                <p className="t2-wal-hint warn">
                  العمولة تجاوزت أرباح المحفظة في هذه الفترة — عمولةُ الرحلات
                  النقدية تُخصم من رصيدك ولو لم يمرّ مالُها به.
                </p>
              ) : null}
            </div>
          </>
        )}

        {/* ── الرصيدُ القابلُ للسحب وطلبُه ── */}
        <div className="t2-wal-cash">
          <div className="t2-wal-cash-top">
            <div className="t2-wal-cash-main">
              <div className="t2-wal-cash-label">الرصيد القابل للسحب</div>
              <div className="t2-wal-cash-amount">
                <span className="t2-wal-cash-num" dir="ltr">
                  {digits(wallet.available_for_withdrawal)}
                </span>
                <span className="t2-wal-cash-cur">{currency}</span>
              </div>
            </div>
            {wallet.frozen ? null : (
              <button
                type="button"
                className="t2-wal-withdraw"
                onClick={() => {
                  w.setDone(null);
                  w.setSheet(true);
                }}
              >
                <span className="t2-icon" aria-hidden="true">
                  south_west
                </span>
                سحب عبر CliQ
              </button>
            )}
          </div>

          {/* ما حُجز — **بنصّ الشاشة القائمة**: مبلغُ الطلب نفسُه حين يكون واحداً، ومعه الرصيدُ الكلّي */}
          {w.holds.length === 1 ? (
            <p className="t2-wal-note">
              <span className="t2-icon" aria-hidden="true">
                schedule
              </span>
              <span>
                محجوز لطلب سحب معلّق: {digits(w.holds[0].amount)} {currency} —
                من أصل {digits(wallet.balance)} {currency}
              </span>
            </p>
          ) : w.holds.length > 1 ? (
            <p className="t2-wal-note">
              <span className="t2-icon" aria-hidden="true">
                schedule
              </span>
              <span>
                لديك {digits(String(w.holds.length))} طلبات سحب قائمة تحجز من
                رصيدك — تفصيلُها في «طلبات السحب».
              </span>
            </p>
          ) : null}

          {w.payoutStopped &&
          w.holds.some((hold) => hold.status === "approved") ? (
            <p className="t2-wal-note">
              <span className="t2-icon" aria-hidden="true">
                info
              </span>
              <span>
                اعتُمد طلبُك، والصرفُ متوقّفٌ مؤقّتاً — يبقى طلبُك في مكانه
                ويصلك حين يُستأنف. ولا شيءَ نقص من رصيدك.
              </span>
            </p>
          ) : null}

          {Number(wallet.pending_compensation) > 0 ? (
            <p className="t2-wal-note">
              <span className="t2-icon" aria-hidden="true">
                info
              </span>
              <span>
                مستحقاتٌ معلّقة: {digits(wallet.pending_compensation)}{" "}
                {currency} — تعويضُ رحلاتٍ أُلغيت بعد قبولك، تصلك حين يسدّدها
                أصحابُها.
              </span>
            </p>
          ) : null}

          {Number(wallet.carrier_dues) > 0 ? (
            <p className="t2-wal-note">
              <span className="t2-icon" aria-hidden="true">
                info
              </span>
              <span>
                مبلغٌ مستوفى لكبتنٍ آخر: {digits(wallet.carrier_dues)}{" "}
                {currency} — استلمتَه نقداً مع الأجرة، ويُحوَّل من محفظتك حالما
                يكفي رصيدُها. اشحن المحفظة ليصله.
              </span>
            </p>
          ) : null}

          {wallet.frozen ? (
            <p className="t2-wal-note danger">
              <span className="t2-icon" aria-hidden="true">
                lock
              </span>
              <span>
                محفظتك مجمّدة — راجع الدعم. الرصيد محفوظ ولا يُسحب حتى ترفع
                الإدارة التجميد.
              </span>
            </p>
          ) : null}

          {/* **«عمولة TAXO» بنصّ الشاشة القائمة وشرطِه** (§25.11) — والنسبةُ تُقرأ من بابها لا تُكتب هنا */}
          {Number(wallet.commission_this_month) > 0 ? (
            <p className="t2-wal-fine">
              عمولة TAXO هذا الشهر: {digits(wallet.commission_this_month)}{" "}
              {currency}
            </p>
          ) : Number(w.profile?.commission_percent ?? 0) === 0 ? (
            <p className="t2-wal-fine">
              عمولة TAXO هذا الشهر: {digits("0.000")} {currency} — صفر عمولة ما
              دام اشتراكك سارياً.
            </p>
          ) : (
            <p className="t2-wal-fine">
              عمولة TAXO هذا الشهر: {digits("0.000")} {currency} — ونسبتُك{" "}
              {digits(String(Number(w.profile?.commission_percent)))}٪ على ما
              تقبضه.
            </p>
          )}
        </div>

        {/* **بابُ «طلبات السحب»** — كان زرّاً في رأس الشاشة القائمة، واللوحةُ لا ترسمه */}
        <button
          type="button"
          className="t2-wal-door"
          onClick={() => w.navigate("/wallet/withdrawals")}
        >
          <span className="t2-wal-txicon" aria-hidden="true">
            <span className="t2-icon">receipt_long</span>
          </span>
          <span className="t2-wal-door-title">طلبات السحب</span>
          <span className="t2-icon t2-wal-door-go" aria-hidden="true">
            arrow_back
          </span>
        </button>

        {/* **بابُ «سجل الرحلات»** — خرج من الشريط حين صارت تبويباتُ C04 كما رُسمت (§٦٢-ب/٢٦)، **وفيه مدخلُ الاعتراض على
            الدفعة** (§٦١-ب/٣) — فمكانُه حيث أسئلةُ المال */}
        <button type="button" className="t2-wal-door" onClick={() => w.navigate("/rides")}>
          <span className="t2-wal-txicon" aria-hidden="true">
            <span className="t2-icon">route</span>
          </span>
          <span className="t2-wal-door-title">سجل الرحلات</span>
          <span className="t2-icon t2-wal-door-go" aria-hidden="true">
            arrow_back
          </span>
        </button>

        {w.error ? (
          <p className="t2-note danger">
            <span className="t2-icon" aria-hidden="true">
              error
            </span>
            {w.error}
          </p>
        ) : null}
        {w.done ? <p className="t2-wal-done">{w.done}</p> : null}

        {/* ── الدفتر: سطرٌ لكلِّ قيد، والإشارةُ من الخلفية ── */}
        {w.entries.length === 0 ? (
          <div className="t2-empty t2-wal-empty">
            <b>لا حركات بعد</b>
            <span>
              أرباحُ رحلاتك وعمولاتها واشتراكاتك تظهر هنا سطراً سطراً.
            </span>
          </div>
        ) : (
          <div className="t2-wal-tx">
            {w.entries.map((entry) => {
              const debit = isDebit(entry.amount);
              return (
                <div key={entry.id} className="t2-wal-txrow">
                  <span
                    className={debit ? "t2-wal-txicon" : "t2-wal-txicon ok"}
                    aria-hidden="true"
                  >
                    <span className="t2-icon">{TX_ICON[entry.type]}</span>
                  </span>
                  <span className="t2-wal-txmain">
                    {/* **«عمولة TAXO» باسمها** كما في الشاشة القائمة */}
                    <span className="t2-wal-txtitle">
                      {entry.type === "commission"
                        ? "عمولة TAXO"
                        : TRANSACTION_LABEL[entry.type]}
                    </span>
                    <span className="t2-wal-txwhen">
                      {formatWhen(entry.created_at)}
                      {entry.commission_percent !== null &&
                      entry.commission_percent !== undefined ? (
                        <> · {digits(entry.commission_percent)}٪</>
                      ) : null}
                    </span>
                  </span>
                  <span className="t2-wal-txend">
                    <span
                      className={
                        debit ? "t2-wal-txamount" : "t2-wal-txamount ok"
                      }
                      dir="ltr"
                    >
                      {debit ? "−" : "+"}
                      {digits(unsigned(entry.amount))}
                    </span>
                    <span className="t2-wal-txafter">
                      الرصيد {digits(entry.balance_after)}
                    </span>
                  </span>
                </div>
              );
            })}
          </div>
        )}

        {w.more ? (
          <button
            type="button"
            className="t2-more t2-wal-more"
            disabled={w.busy}
            onClick={() => void w.loadMore()}
          >
            {w.busy ? "…" : "عرض المزيد"}
          </button>
        ) : null}
      </div>

      {w.sheet ? (
        // **ورقةُ السحب نفسُها** — بألوان الهوية عبر جسر الألوان القائمة (`.t2-legacy`)
        <div className="t2-legacy t2-wal-sheet">
          <WithdrawSheet
            wallet={wallet}
            currencyLabel={currency}
            cliqAlias={alias}
            onAliasSaved={() => void w.refreshDriver()}
            onClose={() => w.setSheet(false)}
            onDone={() => {
              w.setSheet(false);
              w.setDone("أُرسل طلب السحب — بانتظار الموافقة");
              void w.load();
            }}
          />
        </div>
      ) : null}
    </div>
  );
}
