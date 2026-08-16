/** محفظتي — SPEC القسم 9 و12/6، وشكلُها من `DESIGN.md` §5.3.
 *
 * **رقمان لا رقم**: التصميم يعرض «الرصيد المتاح» كبيراً وسطراً تحته بما هو
 * محجوز. والفرقُ بينهما ليس تجميلاً: `available_for_withdrawal` هو الرصيد
 * ناقصَ ما حجزته الطلبات القائمة، **والقيدُ لا يُكتب في الدفتر إلا عند
 * `paid`** — فرصيدُ الكبتن يبقى كما هو بعد الطلب، ولو عرضنا الرصيد وحده
 * لطلب المبلغ نفسه مرتين.
 *
 * والفرقُ يأتي من الخلفية حقلين جاهزين، ولا تطرح الشاشةُ أحدهما من الآخر:
 * سطرُ الحجز يعرض **مبلغ الطلب المعلّق نفسه** من `GET /wallet/me/withdrawals`
 * حين يكون واحداً، وإلا قال إن هناك طلباتٍ تحجز بلا أن يخترع لها مجموعاً.
 *
 * **والدفتر لا يُعدَّل**: ترحيلة `0006` تمنع UPDATE وDELETE عليه، فما يظهر
 * هنا سجلٌّ لا قائمةَ أشياءَ تُحرَّر — والتصحيح قيدُ `adjustment` مضاد.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { Stagger, StaggerItem } from "@/components/ui/Motion";
import {
  getDriverWallet,
  listWalletTransactions,
  listWithdrawals,
} from "@/api/endpoints";
import type { DriverWallet, WalletTransaction, Withdrawal } from "@/api/types";
import { WithdrawSheet } from "@/components/WithdrawSheet";
import { Button } from "@/components/ui/Button";
import { EmptyNote, ErrorNote, Spinner } from "@/components/ui/Feedback";
import { useDriver } from "@/lib/driver";
import { CURRENCY_LABEL, formatWhen } from "@/lib/rideFormat";
import {
  TRANSACTION_ICON,
  TRANSACTION_LABEL,
  isDebit,
  unsigned,
} from "@/lib/walletFormat";
import { arabicDigits, cn } from "@/lib/utils";

const PAGE_SIZE = 20;

/** الطلبُ القائم هو ما حُجز مبلغه ولم يُدفع بعد (`PENDING_WITHDRAWAL_STATUSES`). */
const HOLDING: ReadonlySet<Withdrawal["status"]> = new Set([
  "pending",
  "approved",
]);

export function WalletScreen() {
  const navigate = useNavigate();
  const { profile, refresh: refreshDriver } = useDriver();

  const [wallet, setWallet] = useState<DriverWallet | null>(null);
  const [entries, setEntries] = useState<WalletTransaction[]>([]);
  const [holds, setHolds] = useState<Withdrawal[]>([]);
  const [more, setMore] = useState(false);
  const [busy, setBusy] = useState(false);
  const [sheet, setSheet] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [mine, ledger, requests] = await Promise.all([
      getDriverWallet(),
      listWalletTransactions(PAGE_SIZE, 0),
      listWithdrawals(PAGE_SIZE, 0),
    ]);
    setWallet(mine);
    setEntries(ledger);
    setMore(ledger.length === PAGE_SIZE);
    setHolds(requests.filter((request) => HOLDING.has(request.status)));
  }, []);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة المحفظة",
      ),
    );
  }, [load]);

  async function loadMore() {
    setBusy(true);
    try {
      const page = await listWalletTransactions(PAGE_SIZE, entries.length);
      setEntries((current) => [...current, ...page]);
      setMore(page.length === PAGE_SIZE);
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة الحركات",
      );
    } finally {
      setBusy(false);
    }
  }

  if (!wallet) {
    return (
      <div className="flex h-full items-center justify-center bg-bg px-16">
        {error ? <ErrorNote message={error} /> : <Spinner />}
      </div>
    );
  }

  const currency = CURRENCY_LABEL[wallet.currency];
  const alias = profile?.driver.cliq_alias ?? null;

  return (
    <div className="relative h-full bg-bg">
      <div className="scr h-full px-16 pb-nav pt-safe">
        <div className="mb-16 mt-6 flex items-center justify-between">
          <h1 className="text-20 font-bold text-ink">المحفظة</h1>
          <div className="flex gap-8">
            <button
              type="button"
              onClick={() => navigate("/wallet/earnings")}
              className="pressable rounded-full border border-line px-12 py-6 text-12 font-semibold text-muted"
            >
              أرباحي
            </button>
            <button
              type="button"
              onClick={() => navigate("/wallet/withdrawals")}
              className="pressable rounded-full border border-line px-12 py-6 text-12 font-semibold text-muted"
            >
              طلبات السحب
            </button>
          </div>
        </div>

        <section className="mb-12 rounded-20 border border-line bg-surface p-20">
          <div className="text-12 text-muted">الرصيد المتاح</div>
          <div className="mb-4 mt-2 text-34 font-bold leading-hero text-ink">
            {arabicDigits(wallet.available_for_withdrawal)}{" "}
            <span className="text-14 font-medium text-muted">{currency}</span>
          </div>

          {/* ما حُجز — بمبلغ الطلب نفسه حين يكون واحداً، فلا تطرح الشاشة.
              ومعه الرصيدُ الكلي: من يرى «المتاح» وحده ينقص عمّا يذكر يظن
              أن شيئاً ضاع، والرقمان كلاهما من الخلفية */}
          {holds.length === 1 ? (
            <p className="text-11.5 text-warn">
              محجوز لطلب سحب معلّق: {arabicDigits(holds[0].amount)} {currency} —
              من أصل {arabicDigits(wallet.balance)} {currency}
            </p>
          ) : holds.length > 1 ? (
            <p className="text-11.5 text-warn">
              لديك {arabicDigits(String(holds.length))} طلبات سحب قائمة تحجز من
              رصيدك — تفصيلُها في «طلبات السحب».
            </p>
          ) : null}

          {/* **مستحقاتٌ معلّقة** (`design/CANCELLATION-FEE.md` §8): تعويضُ
              إلغاءٍ استحقّه ولم يسدّده الراكبُ بعد. **يُعرض ولا يُجمع مع
              الرصيد** — رصيدٌ يشمل مالاً لم يصل يكذب على صاحبه، وهي قاعدةُ
              «المتاح للسحب» فوقه بعينها. **ويقول لماذا لم يصل**: من يقرأ رقماً
              معلّقاً بلا سبب يظن العطبَ في المنصّة فيسأل الدعم */}
          {Number(wallet.pending_compensation) > 0 ? (
            <p className="mt-8 text-11.5 leading-note text-warn">
              مستحقاتٌ معلّقة: {arabicDigits(wallet.pending_compensation)} {currency}
              {" "}— تعويضُ رحلاتٍ أُلغيت بعد قبولك، تصلك حين يسدّدها أصحابُها.
            </p>
          ) : null}

          {/* **مبلغٌ مستوفى لكبتنٍ آخر** (§6-أ) — عكسُ السطر الذي فوقه تماماً:
              ذاك مالٌ له لم يصل، وهذا مالٌ ليس له وصله نقداً. **ولذلك يُطرح من
              المتاح ويُقال باسمه**: من يرى متاحاً أقلَّ من رصيده بلا سببٍ
              مكتوبٍ يظن العطب. ويقول **ما المطلوب منه** لا حالَه وحدَه:
              «اشحن» فعلٌ يفعله، و«معلّق» خبرٌ يقرؤه ولا يفعل به شيئاً */}
          {Number(wallet.carrier_dues) > 0 ? (
            <p className="mt-8 text-11.5 leading-note text-warn">
              مبلغٌ مستوفى لكبتنٍ آخر: {arabicDigits(wallet.carrier_dues)}{" "}
              {currency} — استلمتَه نقداً مع الأجرة، ويُحوَّل من محفظتك حالما
              يكفي رصيدُها. اشحن المحفظة ليصله.
            </p>
          ) : null}

          {wallet.frozen ? (
            <p className="mt-8 text-11.5 leading-note text-danger">
              محفظتك مجمّدة — راجع الدعم. الرصيد محفوظ ولا يُسحب حتى ترفع
              الإدارة التجميد.
            </p>
          ) : (
            <Button
              className="mt-14 text-14"
              size="sm"
              onClick={() => {
                setDone(null);
                setSheet(true);
              }}
            >
              طلب سحب
            </Button>
          )}
        </section>

        <ErrorNote message={error} />
        {done ? (
          <p className="mb-12 text-12.5 font-semibold text-ok">{done}</p>
        ) : null}

        <h2 className="mb-10 mt-16 px-2 text-13 font-bold text-muted">
          الحركات
        </h2>

        {entries.length === 0 ? (
          <EmptyNote
            title="لا حركات بعد"
            hint="أرباحُ رحلاتك وعمولاتها واشتراكاتك تظهر هنا سطراً سطراً."
          />
        ) : null}

        <Stagger className="flex flex-col gap-8">
          {entries.map((entry) => {
            const debit = isDebit(entry.amount);
            const Icon = TRANSACTION_ICON[entry.type];
            return (
              <StaggerItem
                key={entry.id}
                className="flex items-center gap-12 rounded-14 border border-line bg-surface px-14 py-12"
              >
                <span
                  className={cn(
                    "flex size-34 flex-none items-center justify-center rounded-11 bg-surface-2",
                    debit ? "text-danger" : "text-ok",
                  )}
                  aria-hidden
                >
                  <Icon size={15} strokeWidth={2} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-13 font-semibold text-ink">
                    {TRANSACTION_LABEL[entry.type]}
                  </div>
                  <div className="text-11 text-muted">
                    {formatWhen(entry.created_at)}
                  </div>
                </div>
                <div className="text-end">
                  <div
                    dir="ltr"
                    className={cn(
                      "text-14 font-bold",
                      debit ? "text-danger" : "text-ok",
                    )}
                  >
                    {debit ? "−" : "+"}
                    {arabicDigits(unsigned(entry.amount))}
                  </div>
                  <div className="text-10 text-muted">
                    الرصيد {arabicDigits(entry.balance_after)}
                  </div>
                </div>
              </StaggerItem>
            );
          })}
        </Stagger>

        {more ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => void loadMore()}
            className="pressable mt-12 w-full rounded-14 border border-line py-13 text-center text-12.5 font-semibold text-muted disabled:opacity-60"
          >
            {busy ? "…" : "عرض المزيد"}
          </button>
        ) : null}
      </div>

      {sheet ? (
        <WithdrawSheet
          wallet={wallet}
          currencyLabel={currency}
          cliqAlias={alias}
          onAliasSaved={() => void refreshDriver()}
          onClose={() => setSheet(false)}
          onDone={() => {
            setSheet(false);
            setDone("أُرسل طلب السحب — بانتظار الموافقة");
            void load();
          }}
        />
      ) : null}

    </div>
  );
}
