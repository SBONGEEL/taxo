/** محفظتي: الرصيد والشحن والتحويل والسجل (SPEC القسم 11.6).
 *
 * قاعدتان تظهران في هذه الشاشة بالتحديد:
 *
 * - **الراكب يشحن ولا يسحب أبداً** (القسم 7) — فلا زرَّ سحبٍ هنا ولا مسار.
 * - **القراءة لا تمر بمفتاح `wallet_enabled`**: رصيدٌ سابقٌ لإطفاء المفتاح
 *   يبقى مرئياً لصاحبه وإن تعذّر إنفاقه — فالمفتاح يخفي أزرار الشحن والتحويل
 *   لا الرقم.
 */

import { ArrowDownLeft, ArrowUpRight, Plus, Snowflake } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getWallet, listTopups, listTransactions } from "@/api/endpoints";
import type { TopupRequest, Wallet, WalletTransaction } from "@/api/types";
import { TopupSheet } from "@/components/wallet/TopupSheet";
import { Button } from "@/components/ui/Button";
import { Badge, EmptyState, ErrorNote, Spinner } from "@/components/ui/Feedback";
import { Screen } from "@/components/ui/Screen";
import { useCountryConfig } from "@/lib/config";
import { TOPUP_STATUS_LABEL, TRANSACTION_LABEL } from "@/lib/labels";
import { useSession } from "@/lib/session";
import { formatDateTime, formatMoney } from "@/lib/utils";

export function WalletScreen() {
  const navigate = useNavigate();
  const { user } = useSession();
  const country = useCountryConfig(user?.country_code);

  // **ورقةٌ لا تنقّل** (تصميمُ `topupShow`): اختيارُ المبلغ والقناة يقع فوق
  // الرصيد الذي تنظر إليه — ومن غيّر رأيه يُغلق الورقةَ ويبقى مكانه
  const [topupOpen, setTopupOpen] = useState(false);
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [entries, setEntries] = useState<WalletTransaction[]>([]);
  const [topups, setTopups] = useState<TopupRequest[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

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
  const transferEnabled = country?.features.wallet_transfer_enabled === true;

  if (loading) {
    return (
      <Screen title="محفظتي" back="/">
        <Spinner />
      </Screen>
    );
  }

  return (
    <Screen title="محفظتي" back="/">
      <div className="space-y-20">
        {/* كان تدرّجاً بشفافيةٍ ٢٥٪ على `--brand`؛ ولوحةُ التصميم hex لا
            تحتمل الشفافية (`index.css`)، فالتدرّجُ الآن من الرمز **الخافت**
            وهو ما وُجد له. المرحلة 12-أ */}
        <div className="card bg-gradient-to-bl from-brand-soft to-transparent p-20 text-center">
          <p className="text-14 text-muted">الرصيد المتاح</p>
          <p className="mt-4 text-38 font-bold text-ink">
            {formatMoney(wallet?.balance, wallet?.currency)}
          </p>
          {wallet?.frozen ? (
            <p className="mt-8 flex items-center justify-center gap-6 text-14 text-danger">
              <Snowflake className="size-16" />
              محفظتك مجمّدة مؤقتاً — راجع الدعم
            </p>
          ) : null}
        </div>

        <ErrorNote message={error} />

        {walletEnabled ? (
          <div className="flex gap-8">
            <Button className="flex-1" onClick={() => setTopupOpen(true)}>
              <Plus className="size-16" />
              شحن الرصيد
            </Button>
            {transferEnabled ? (
              <Button
                variant="secondary"
                className="flex-1"
                onClick={() => navigate("/wallet/transfer")}
              >
                <ArrowUpRight className="size-16" />
                تحويل
              </Button>
            ) : null}
          </div>
        ) : (
          <p className="rounded-12 border border-line bg-surface p-12 text-14 text-muted">
            المحفظة غير مفعّلة في بلدك حالياً — رصيدك محفوظ ويظهر هنا.
          </p>
        )}

        {topups.length > 0 ? (
          <section className="space-y-8">
            <h2 className="label">طلبات شحن قيد المراجعة</h2>
            {topups.map((request) => (
              <div key={request.id} className="card flex items-center justify-between p-12">
                <div>
                  <p className="font-medium text-ink">
                    {formatMoney(request.amount, request.currency)}
                  </p>
                  <p className="text-12 text-muted">{formatDateTime(request.created_at)}</p>
                </div>
                <Badge tone="warning">{TOPUP_STATUS_LABEL[request.status]}</Badge>
              </div>
            ))}
          </section>
        ) : null}

        <section className="space-y-8">
          <h2 className="label">سجل العمليات</h2>
          {entries.length === 0 ? (
            <EmptyState title="لا عمليات بعد" hint="ستظهر هنا كل حركة على رصيدك." />
          ) : (
            <ul className="space-y-8">
              {entries.map((entry) => {
                const credit = !entry.amount.trimStart().startsWith("-");
                return (
                  <li key={entry.id} className="card flex items-center gap-12 p-12">
                    <span
                      className={`flex size-9 shrink-0 items-center justify-center rounded-full ${
                        credit ? "bg-surface-2 text-ok" : "bg-surface-2 text-muted"
                      }`}
                    >
                      {credit ? (
                        <ArrowDownLeft className="size-16" />
                      ) : (
                        <ArrowUpRight className="size-16" />
                      )}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium text-ink">
                        {TRANSACTION_LABEL[entry.type]}
                      </p>
                      <p className="truncate text-12 text-muted">
                        {entry.reference ?? formatDateTime(entry.created_at)}
                      </p>
                    </div>
                    <div className="text-end">
                      <p className={credit ? "font-semibold text-ok" : "font-semibold text-ink"}>
                        {formatMoney(entry.amount, entry.currency)}
                      </p>
                      <p className="text-12 text-muted">
                        الرصيد {formatMoney(entry.balance_after)}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      </div>
      {topupOpen ? (
        <TopupSheet
          currency={currency}
          cardEnabled={cardEnabled}
          cliqEnabled={cliqEnabled}
          onClose={() => setTopupOpen(false)}
        />
      ) : null}

    </Screen>
  );
}
