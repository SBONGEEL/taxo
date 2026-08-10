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
      <div className="space-y-5">
        <div className="card bg-gradient-to-bl from-brand/25 to-transparent p-5 text-center">
          <p className="text-sm text-muted">الرصيد المتاح</p>
          <p className="mt-1 text-4xl font-bold text-ink">
            {formatMoney(wallet?.balance, wallet?.currency)}
          </p>
          {wallet?.frozen ? (
            <p className="mt-2 flex items-center justify-center gap-1.5 text-sm text-danger">
              <Snowflake className="size-4" />
              محفظتك مجمّدة مؤقتاً — راجع الدعم
            </p>
          ) : null}
        </div>

        <ErrorNote message={error} />

        {walletEnabled ? (
          <div className="flex gap-2">
            <Button className="flex-1" onClick={() => navigate("/wallet/topup")}>
              <Plus className="size-4" />
              شحن الرصيد
            </Button>
            {transferEnabled ? (
              <Button
                variant="secondary"
                className="flex-1"
                onClick={() => navigate("/wallet/transfer")}
              >
                <ArrowUpRight className="size-4" />
                تحويل
              </Button>
            ) : null}
          </div>
        ) : (
          <p className="rounded-xl border border-line bg-surface p-3 text-sm text-muted">
            المحفظة غير مفعّلة في بلدك حالياً — رصيدك محفوظ ويظهر هنا.
          </p>
        )}

        {topups.length > 0 ? (
          <section className="space-y-2">
            <h2 className="label">طلبات شحن قيد المراجعة</h2>
            {topups.map((request) => (
              <div key={request.id} className="card flex items-center justify-between p-3">
                <div>
                  <p className="font-medium text-ink">
                    {formatMoney(request.amount, request.currency)}
                  </p>
                  <p className="text-xs text-muted">{formatDateTime(request.created_at)}</p>
                </div>
                <Badge tone="warning">{TOPUP_STATUS_LABEL[request.status]}</Badge>
              </div>
            ))}
          </section>
        ) : null}

        <section className="space-y-2">
          <h2 className="label">سجل العمليات</h2>
          {entries.length === 0 ? (
            <EmptyState title="لا عمليات بعد" hint="ستظهر هنا كل حركة على رصيدك." />
          ) : (
            <ul className="space-y-2">
              {entries.map((entry) => {
                const credit = !entry.amount.trimStart().startsWith("-");
                return (
                  <li key={entry.id} className="card flex items-center gap-3 p-3">
                    <span
                      className={`flex size-9 shrink-0 items-center justify-center rounded-full ${
                        credit ? "bg-success/15 text-success" : "bg-line/60 text-muted"
                      }`}
                    >
                      {credit ? (
                        <ArrowDownLeft className="size-4" />
                      ) : (
                        <ArrowUpRight className="size-4" />
                      )}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium text-ink">
                        {TRANSACTION_LABEL[entry.type]}
                      </p>
                      <p className="truncate text-xs text-muted">
                        {entry.reference ?? formatDateTime(entry.created_at)}
                      </p>
                    </div>
                    <div className="text-end">
                      <p className={credit ? "font-semibold text-success" : "font-semibold text-ink"}>
                        {formatMoney(entry.amount, entry.currency)}
                      </p>
                      <p className="text-xs text-muted">
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
    </Screen>
  );
}
