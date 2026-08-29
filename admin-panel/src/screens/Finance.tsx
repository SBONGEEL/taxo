/** المالية: طلبات السحب وشحنات كليك — SPEC القسم 13/5، و`DESIGN.md` §3.3.
 *
 * **الشاشة التي ينتظرها مالٌ حقيقي**، وثلاثةُ أشياء تحكم كل زرٍّ فيها:
 *
 * 1. **المال يتحرك في الدفتر عند `paid` وحدها**، لا عند الموافقة. فالموافقةُ
 *    قرارٌ إداري والدفعُ فعلٌ يقع في البنك، وبينهما يبقى المبلغ **محجوزاً**
 *    من رصيد الكبتن المتاح ولا قيدَ له بعد. ولذلك زرّان لا واحد: «موافقة» ثم
 *    «سُجّل التحويل» بمرجعه.
 * 2. **مرجعُ التحويل إلزاميٌّ عند التسجيل**: هو ما يُحتج به حين يقول الكبتن
 *    «لم يصلني»، وسحبٌ مقيَّدٌ بلا مرجعٍ قيدٌ لا يُدافع عنه.
 * 3. **شحنةُ كليك تُؤكَّد بعد رؤية المال** في الحساب: التأكيد هو ما يقيّد
 *    الرصيد للراكب، ولا API يشهد على هذه القناة (القسم 6.2).
 *
 * ولا زرَّ «دفعٌ آلي عبر المزود» هنا بعد: مسارُه مبنيٌّ في الخلفية
 * (`withdrawals.pay_via_provider`) ويحتاج عقد payout مفعّلاً — وزرٌّ يظهر بلا
 * عقدٍ يرتدّ بخطأ. يظهر مع صفحة العقود.
 */

import { GuardBanner } from "@/components/GuardBanner";
import { useCountry } from "@/lib/country";
import { useCountryConfig } from "@/lib/config";
import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  approveWithdrawal,
  confirmTopup,
  listTopups,
  listWithdrawals,
  markWithdrawalPaid,
  rejectTopup,
  rejectWithdrawal,
  listCliqClaims,
  confirmCliqClaim,
} from "@/api/endpoints";
import type { TopupRequest, Withdrawal, WithdrawalStatus } from "@/api/types";
import { CancellationCharges } from "@/components/CancellationCharges";
import { WalletDesk } from "@/components/WalletDesk";
import { Shell } from "@/components/Shell";
import { Pills, Table } from "@/components/Table";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { useSession } from "@/lib/session";
import { FormErrors, useFormError } from "@/lib/form-errors";
import { digits, cn,
  DISPLAY_LOCALE,
} from "@/lib/utils";

const WITHDRAWAL_LABEL: Record<WithdrawalStatus, string> = {
  pending: "معلّق",
  approved: "موافَق عليه",
  paid: "مدفوع",
  rejected: "مرفوض",
};

const WITHDRAWAL_TONE: Record<WithdrawalStatus, string> = {
  pending: "text-warn",
  approved: "text-warn",
  paid: "text-ok",
  rejected: "text-danger",
};

function when(iso: string): string {
  const at = new Date(iso);
  return `${digits(at.toLocaleDateString(DISPLAY_LOCALE, { day: "numeric", month: "long" }))} ${digits(at.toLocaleTimeString(DISPLAY_LOCALE, { hour: "numeric", minute: "2-digit" }))}`;
}

/** **ورسومُ الإلغاء ثالثةٌ هنا لا في شاشةٍ مستقلة**: مالٌ ينتظر قراراً
 *  إدارياً، وهو بالضبط ما تعنيه هذه الشاشة — غير أن مالَه يمرّ بين
 *  **مستخدمَين** لا بين المنصّة وأحدهما، ولذلك لا زرَّ تحصيلٍ فيه. */
type Tab = "withdrawals" | "topups" | "claims" | "cancellations" | "desk";

export function FinanceScreen() {
  const { isAdmin } = useSession();
  // **إيقافُ الصرف**: يمنع مغادرةَ المال — والطلباتُ والاعتمادُ يعملان
  const { country } = useCountry();
  const payoutStopped =
    useCountryConfig(country)?.features.withdrawal_payout_enabled === false;
  const [tab, setTab] = useState<Tab>("withdrawals");
  const [claims, setClaims] = useState<CliqClaim[] | null>(null);
  const [claiming, setClaiming] = useState<CliqClaim | null>(null);
  const [claimAmount, setClaimAmount] = useState("");

  const [withdrawals, setWithdrawals] = useState<Withdrawal[] | null>(null);
  const [topups, setTopups] = useState<TopupRequest[] | null>(null);
  const [paying, setPaying] = useState<Withdrawal | null>(null);
  const [confirming, setConfirming] = useState<TopupRequest | null>(null);
  const [credited, setCredited] = useState("");
  const form = useFormError();
  const error = form.message;
  const setError = form.setMessage;
  const [done, setDone] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [w, t, c] = await Promise.all([
      listWithdrawals(),
      listTopups("pending"),
      listCliqClaims(),
    ]);
    setWithdrawals(w);
    setTopups(t);
    setClaims(c);
  }, []);

  useEffect(() => {
    load().catch((caught) =>
      setError(caught instanceof ApiError ? caught.message : "تعذّر القراءة"),
    );
  }, [load]);

  async function run(action: () => Promise<unknown>, message: string) {
    setError(null);
    setDone(null);
    try {
      await action();
      await load();
      setDone(message);
    } catch (caught) {
      form.capture(caught, "تعذّر التنفيذ");
    }
  }

  return (
    <FormErrors value={form.field}>
    <Shell
      title="المحافظ وطلبات السحب"
      subtitle="الموافقة قرارٌ إداري، والقيد في الدفتر يقع عند الدفع وحده"
    >
      <GuardBanner on={payoutStopped} title="صرفُ السحوبات موقوف">
        <b className="text-ink">المالُ لا يغادر</b> حتى يُستأنف من «الإعدادات».
        والطلباتُ تُقبل والاعتمادُ يمرّ كما كان، والطلبُ يبقى «معتمَداً» في
        مكانه — والكبتنُ يقرأ ذلك على طلبه فلا يظنّه ضاع.
      </GuardBanner>
      <Pills
        value={tab}
        onPick={(key) => setTab(key as Tab)}
        options={[
          { key: "withdrawals", label: "طلبات السحب" },
          { key: "topups", label: "شحنات بانتظار التأكيد" },
          // **مطالباتُ كليك اليدوية** — اشتراكاتٌ تنتظر «تأكيد الدفع»
          { key: "claims", label: "مطالبات كليك" },
          { key: "cancellations", label: "رسوم الإلغاء" },
          // **مكتبُ الدفتر**: تصحيحٌ وشحنٌ إداريّ — بابان كانا بلا زرّ
          { key: "desk", label: "تصحيحُ الدفتر وشحنٌ إداريّ" },
        ]}
      />

      <ErrorNote message={error} />
      <SuccessNote message={done} />

      <div className="mt-12">
        {tab === "claims" ? (
          /* **مطالباتُ كليك اليدوية** — «تأكيد الدفع» بمبلغ المشرف. */
          <Table
            columns="1fr 1.4fr 1fr 1fr"
            headers={["المطلوب", "المرجع", "الطلب", ""]}
            rows={claims ?? []}
            keyOf={(row) => row.id}
            empty={{
              title: "لا مطالبات معلّقة",
              hint: "مطالبةُ كبتنٍ دفع اشتراكه بكليك تنتظر تأكيدك بعد أن يصل المال.",
            }}
            render={(row) => (
              <>
                <span className="font-semibold text-ink">
                  {digits(row.amount)}
                </span>
                <span dir="ltr" className="text-start text-muted">
                  {row.cart_id}
                </span>
                <span className="text-muted">{when(row.created_at)}</span>
                <span className="flex justify-end gap-10">
                  {isAdmin ? (
                    <button
                      type="button"
                      onClick={() => {
                        setClaiming(row);
                        setClaimAmount(row.amount);
                      }}
                      className="text-11.5 font-semibold text-ok"
                    >
                      تأكيد الدفع
                    </button>
                  ) : null}
                </span>
              </>
            )}
          />
        ) : tab === "desk" ? (
          <WalletDesk onError={setError} />
        ) : tab === "cancellations" ? (
          <CancellationCharges onError={setError} />
        ) : tab === "withdrawals" ? (
          <Table
            columns="1fr 0.8fr 1fr 1fr 1.4fr"
            headers={["المبلغ", "القناة", "الطلب", "الحالة", ""]}
            rows={withdrawals}
            keyOf={(row) => row.id}
            empty={{
              title: "لا طلبات سحب",
              hint: "يظهر هنا كل طلبٍ من كبتن، من لحظة تقديمه حتى تحويله.",
            }}
            render={(row) => (
              <>
                <span className="font-semibold text-ink">
                  {digits(row.amount)}
                </span>
                <span className="text-muted">
                  {row.method === "cliq" ? "كليك" : "حوالة بنكية"}
                </span>
                <span className="text-muted">{when(row.created_at)}</span>
                <span
                  className={cn("font-semibold", WITHDRAWAL_TONE[row.status])}
                >
                  {WITHDRAWAL_LABEL[row.status]}
                  {row.reference ? (
                    <span dir="ltr" className="block text-10.5 text-muted">
                      {row.reference}
                    </span>
                  ) : null}
                </span>
                <span className="flex justify-end gap-10">
                  {isAdmin && row.status === "pending" ? (
                    <>
                      <button
                        type="button"
                        onClick={() =>
                          void run(
                            () => approveWithdrawal(row.id),
                            "وُوفق على الطلب — يبقى المبلغ محجوزاً حتى التحويل",
                          )
                        }
                        className="text-11.5 font-semibold text-ink"
                      >
                        موافقة
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          void run(
                            () => rejectWithdrawal(row.id),
                            "رُفض الطلب وأُعيد الرصيد",
                          )
                        }
                        className="text-11.5 font-semibold text-danger"
                      >
                        رفض
                      </button>
                    </>
                  ) : null}
                  {isAdmin && row.status === "approved" ? (
                    // **يُعطَّل ولا يُخفى**: زرٌّ يعمل ثم يردّ ٤٠٣ يعلّم صاحبَه
                    // أن يعيد الضغط، وزرٌّ يختفي يُقرأ عطباً في اللوحة
                    <button
                      type="button"
                      disabled={payoutStopped}
                      title={payoutStopped ? "صرفُ السحوبات موقوف" : undefined}
                      onClick={() => setPaying(row)}
                      className="text-11.5 font-semibold text-ok disabled:text-muted"
                    >
                      سجّل التحويل
                    </button>
                  ) : null}
                </span>
              </>
            )}
          />
        ) : (
          <Table
            columns="1fr 0.8fr 1.2fr 1fr 1fr"
            headers={["المبلغ", "القناة", "المرجع", "الطلب", ""]}
            rows={topups}
            keyOf={(row) => row.id}
            empty={{
              title: "لا شحنات معلّقة",
              hint: "شحنةُ كليك أو كاش تنتظر تأكيدك بعد أن يصل المال.",
            }}
            render={(row) => (
              <>
                <span className="font-semibold text-ink">
                  {digits(row.amount)}
                </span>
                <span className="text-muted">
                  {row.method === "cliq" ? "كليك" : "كاش"}
                </span>
                <span dir="ltr" className="text-start text-muted">
                  {row.reference ?? "—"}
                </span>
                <span className="text-muted">{when(row.created_at)}</span>
                <span className="flex justify-end gap-10">
                  {isAdmin ? (
                    <>
                      <button
                        type="button"
                        onClick={() => {
                          setConfirming(row);
                          setCredited(row.amount);
                        }}
                        className="text-11.5 font-semibold text-ok"
                      >
                        تأكيد
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          void run(() => rejectTopup(row.id), "رُفضت الشحنة")
                        }
                        className="text-11.5 font-semibold text-danger"
                      >
                        رفض
                      </button>
                    </>
                  ) : null}
                </span>
              </>
            )}
          />
        )}
      </div>

      {/* لا نجومَ Markdown في JSX: النصُّ يخرج كما هو، والتوكيدُ وسمٌ.
          **ولا يُعرض على تبويب رسوم الإلغاء**: ذاك مالٌ بين مستخدمَين لا يحجز
          شيئاً ولا يُقيَّد بزرٍّ هنا، وله سطرُه الخاصُّ به */}
      {tab === "cancellations" ? null : (
      <p className="mt-14 text-11.5 leading-note text-muted">
        الطلب المعلّق أو الموافَق عليه <b className="text-ink">يحجز</b> مبلغه من
        رصيد الكبتن المتاح، وقيد السحب لا يُكتب في الدفتر إلا عند تسجيل التحويل.
        وتأكيدُ الشحنة هو ما يقيّد رصيد الراكب — فلا يُؤكَّد إلا بعد رؤية المال.
      </p>
      )}

      {paying ? (
        <PayoutModal
          request={paying}
          onClose={() => setPaying(null)}
          onPaid={(message) => {
            setPaying(null);
            setDone(message);
            void load();
          }}
        />
      ) : null}

      {claiming ? (
        <ConfirmClaimModal
          claim={claiming}
          amount={claimAmount}
          onAmount={setClaimAmount}
          onClose={() => setClaiming(null)}
          onDone={(message) => {
            setClaiming(null);
            setDone(message);
            void load();
          }}
        />
      ) : null}

      {confirming ? (
        <ConfirmTopupModal
          request={confirming}
          amount={credited}
          onAmount={setCredited}
          onClose={() => setConfirming(null)}
          onDone={(message) => {
            setConfirming(null);
            setDone(message);
            void load();
          }}
        />
      ) : null}
    </Shell>
    </FormErrors>
  );
}



/** **تأكيدُ دفعِ مطالبةٍ يدوية** — والمبلغُ مبلغُك أنت.
 *
 * **ولا رجعةَ له**: التأكيدُ يفعّل اشتراكاً. **ودونَ الثمن لا تفعيل** —
 * المطالبةُ تبقى معلّقةً بفرقها مكتوباً، فترفض أو تنتظر التكملة.
 */
function ConfirmClaimModal({
  claim,
  amount,
  onAmount,
  onClose,
  onDone,
}: {
  claim: CliqClaim;
  amount: string;
  onAmount: (value: string) => void;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const short = amount.trim() !== "" && Number(amount) < Number(claim.amount);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-dim px-20"
      onClick={onClose}
    >
      <div
        className="w-modal max-w-full rounded-20 border border-line bg-surface p-24"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 className="mb-4 text-16 font-bold text-ink">تأكيد الدفع</h2>
        <p className="mb-16 rounded-14 border border-warn bg-surface-2 px-14 py-12 text-12 leading-note text-ink">
          التأكيد يفعّل الاشتراك ولا يُلغى. والتصحيح بقيدٍ مقابلٍ من التسوية.
        </p>

        <div className="mb-16 flex items-baseline justify-between rounded-14 border border-line bg-surface-2 px-14 py-12">
          <span className="text-12.5 text-muted">المطلوب</span>
          <span className="text-17 font-bold text-ink">
            {digits(claim.amount)}
          </span>
        </div>

        <Field
          label="المبلغ الذي وصل حسابك فعلاً"
          name="claim_credited"
          dir="ltr"
          inputMode="decimal"
          value={amount}
          onChange={(event) =>
            onAmount(event.target.value.replace(/[^0-9.]/g, ""))
          }
        />
        {short ? (
          <p className="mt-8 text-11 leading-note text-warn-ink">
            أقلُّ من المطلوب — لن يُفعَّل الاشتراك، وتبقى المطالبة معلّقة
            بفرقها مكتوباً.
          </p>
        ) : null}

        <ErrorNote message={error} />

        <div className="mt-18 flex gap-10">
          <Button
            className="flex-1"
            size="md"
            loading={busy}
            disabled={Number(amount) <= 0}
            onClick={() => {
              setBusy(true);
              setError(null);
              confirmCliqClaim(claim.id, amount.trim())
                .then((row) =>
                  onDone(
                    row.status === "paid"
                      ? "أُكّد الدفع — فُعِّل الاشتراك"
                      : "سُجّل المبلغ — لم يُفعَّل الاشتراك لنقصه",
                  ),
                )
                .catch((caught) =>
                  setError(
                    caught instanceof ApiError ? caught.message : "تعذّر التأكيد",
                  ),
                )
                .finally(() => setBusy(false));
            }}
          >
            أكّد الدفع
          </Button>
          <Button
            className="flex-1"
            size="md"
            variant="secondary"
            onClick={onClose}
          >
            تراجع
          </Button>
        </div>
      </div>
    </div>
  );
}

/** **تأكيدُ شحنة — والمبلغُ مبلغُك أنت** (قرارُ المالك 2026-08-29).
 *
 * **ولمَ لوحةٌ لا نقرةٌ مباشرة**: التأكيدُ **يكتب قيداً في دفتر مالِ إنسان**،
 * **ولا رجعةَ له من هذا الباب** — `reject` يشترط `PENDING` فيردّ 409 على
 * المؤكَّد. **ونقرةٌ واحدةٌ تفعل ما لا يُلغى ليست زرّاً بل فخّ.**
 *
 * **والسطرُ يُقرأ قبل النقر لا بعده** (قرارُ المالك): من نقر ثمّ رأى 409
 * **يبحث عن بابٍ لا وجودَ له** — ويسأل الدعمَ عن مالٍ تحرّك.
 *
 * **ودعوى المستخدم تُعرض ولا تُصرف**: تُقرأ لتُقارَن بما وصل، والمُدخَلُ هو
 * ما قرأه المشرفُ في كشفه.
 */
function ConfirmTopupModal({
  request,
  amount,
  onAmount,
  onClose,
  onDone,
}: {
  request: TopupRequest;
  amount: string;
  onAmount: (value: string) => void;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const differs = amount.trim() !== "" && amount.trim() !== request.amount;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-dim px-20"
      onClick={onClose}
    >
      <div
        className="w-modal max-w-full rounded-20 border border-line bg-surface p-24"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 className="mb-4 text-16 font-bold text-ink">تأكيد الشحنة</h2>

        {/* **السطرُ الذي يُقرأ قبل النقر** — لا رسالةَ خطأٍ بعده */}
        <p className="mb-16 rounded-14 border border-warn bg-surface-2 px-14 py-12 text-12 leading-note text-ink">
          التأكيد لا يُلغى. والتصحيح بقيدٍ مقابلٍ من التسوية، لا بإلغاء هذه
          الشحنة.
        </p>

        <div className="mb-16 flex items-baseline justify-between rounded-14 border border-line bg-surface-2 px-14 py-12">
          <span className="text-12.5 text-muted">ما كتبه صاحبُ الطلب</span>
          <span className="text-15 font-bold text-ink">
            {digits(request.amount)}
          </span>
        </div>

        <Field
          label="المبلغ الذي وصل حسابك فعلاً"
          name="credited"
          dir="ltr"
          inputMode="decimal"
          value={amount}
          onChange={(event) =>
            onAmount(event.target.value.replace(/[^0-9.]/g, ""))
          }
        />
        {differs ? (
          <p className="mt-8 text-11 leading-note text-warn-ink">
            يخالف ما كتبه — سيُقيَّد ما أدخلتَه أنت، ويبقى ما كتبه في سجلّ
            الطلب.
          </p>
        ) : null}

        <ErrorNote message={error} />

        <div className="mt-18 flex gap-10">
          <Button
            className="flex-1"
            size="md"
            loading={busy}
            disabled={Number(amount) <= 0}
            onClick={() => {
              setBusy(true);
              setError(null);
              confirmTopup(request.id, amount.trim())
                .then(() => onDone("أُكّدت الشحنة — قُيّد الرصيد"))
                .catch((caught) =>
                  setError(
                    caught instanceof ApiError ? caught.message : "تعذّر التأكيد",
                  ),
                )
                .finally(() => setBusy(false));
            }}
          >
            أكّد وقيّد
          </Button>
          <Button
            className="flex-1"
            size="md"
            variant="secondary"
            onClick={onClose}
          >
            تراجع
          </Button>
        </div>
      </div>
    </div>
  );
}

/** تسجيلُ التحويل — **بمرجعٍ إلزامي**: به يُحتج حين يُنكر الوصول. */
function PayoutModal({
  request,
  onClose,
  onPaid,
}: {
  request: Withdrawal;
  onClose: () => void;
  onPaid: (message: string) => void;
}) {
  const [reference, setReference] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-dim px-20"
      onClick={onClose}
    >
      <div
        className="w-modal max-w-full rounded-20 border border-line bg-surface p-24"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 className="mb-4 text-16 font-bold text-ink">تسجيل التحويل</h2>
        <p className="mb-16 text-12 leading-note text-muted">
          يُكتب الآن قيدُ السحب في دفتر الكبتن — وهذه هي اللحظة التي يتحرك فيها
          المال. سجّله بعد أن تحوّل فعلاً، لا قبله.
        </p>

        <div className="mb-16 flex items-baseline justify-between rounded-14 border border-line bg-surface-2 px-14 py-12">
          <span className="text-12.5 text-muted">المبلغ</span>
          <span className="text-17 font-bold text-ink">
            {digits(request.amount)}
          </span>
        </div>

        <Field
          label="مرجع التحويل"
          name="reference"
          dir="ltr"
          placeholder="CLIQ-…"
          value={reference}
          maxLength={64}
          onChange={(event) => setReference(event.target.value)}
        />

        <ErrorNote message={error} />

        <div className="mt-18 flex gap-10">
          <Button
            className="flex-1"
            size="md"
            loading={busy}
            disabled={reference.trim().length < 3}
            onClick={() => {
              setBusy(true);
              setError(null);
              markWithdrawalPaid(request.id, reference.trim())
                .then(() => onPaid("تم تنفيذ التحويل ✓"))
                .catch((caught) =>
                  setError(
                    caught instanceof ApiError
                      ? caught.message
                      : "تعذّر التسجيل",
                  ),
                )
                .finally(() => setBusy(false));
            }}
          >
            سجّل ونفّذ القيد
          </Button>
          <Button
            className="flex-1"
            size="md"
            variant="secondary"
            onClick={onClose}
          >
            تراجع
          </Button>
        </div>
      </div>
    </div>
  );
}
