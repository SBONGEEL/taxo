/** **حمايةُ الدفع** (SPEC §٨٧، أمرُ المالك ٢٠٢٦-١٠-٢٨) — ثلاثةُ ألواح:
 *
 * - **الصحّة**: نسبةُ النجاح لكلِّ طريقةٍ لليوم والأسبوع والشهر، والحالُ الآن (مفعَّلة · مخفيّةٌ آليّاً أو بيد المالك · الوسيطُ متوقّف)،
 *   والإخفاقاتُ المتتالية. **وللمالك وحدَه زرّا «إخفاء» و«إعادة التشغيل» بسببٍ مكتوب** — والخادمُ يحرسهما.
 * - **المطابقةُ اليوميّة**: سجلُّ التقارير بافتراقاتها، **و«طابِق الآن»** للمالك. تقريرٌ لا يكتب في الدفتر.
 * - **دفترُ SofizPay**: معاملاتُ الحساب من Stellar بمرشّحاتها وتصديرُها CSV لمن مُنح `gateway_ledger.read`، **والرصيدُ للمالك وحدَه**.
 *
 * **ويتبع مبدّلَ الدولة.**
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  exportSofizpayTransactions,
  getPaymentHealth,
  getSofizpayBalance,
  getSofizpayTransactions,
  hidePayMethod,
  listReconciliations,
  restorePayMethod,
  runReconciliation,
} from "@/api/endpoints";
import type {
  CountryCode,
  GatewayLedger,
  GatewayLedgerBalance,
  GatewayReconciliation,
  HealthWindow,
  MethodHealth,
  PaymentHealth,
} from "@/api/types";
import { Shell } from "@/components/Shell";
import { Pills, Table } from "@/components/Table";
import { Button } from "@/components/ui/Button";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { DateInput, Field, Select } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { useCountry } from "@/lib/country";
import { useSession } from "@/lib/session";
import { DISPLAY_LOCALE, cn, digits } from "@/lib/utils";

type ProtectionTab = "health" | "reconcile" | "ledger";

const WINDOW_LABEL: Record<HealthWindow, string> = {
  today: "اليوم",
  week: "7 أيام",
  month: "30 يوماً",
};

const MISMATCH_LABEL: Record<string, string> = {
  credited_not_paid: "قُيِّد عندنا ولا يقول الوسيطُ «دُفع»",
  paid_not_credited: "دُفع عند الوسيط ولم يُقيَّد",
  processing: "دُفع وينتظر التفعيل",
  amount: "المبلغُ مختلف",
};

function when(iso: string | null): string {
  if (!iso) return "—";
  const at = new Date(iso);
  return `${digits(at.toLocaleDateString(DISPLAY_LOCALE, { day: "numeric", month: "long" }))} ${digits(
    at.toLocaleTimeString(DISPLAY_LOCALE, { hour: "numeric", minute: "2-digit" }),
  )}`;
}

function message(caught: unknown, fallback: string): string {
  return caught instanceof ApiError || caught instanceof Error ? caught.message : fallback;
}

export function PaymentProtectionScreen() {
  const { user } = useSession();
  const owner = Boolean(user?.roles?.includes("owner"));
  const { country } = useCountry();
  const [tab, setTab] = useState<ProtectionTab>("health");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  return (
    <Shell title="حماية الدفع" subtitle="صحّةُ كلِّ طريقة، والمطابقةُ اليوميّة مع الوسطاء، ودفترُ SofizPay">
      <Pills
        value={tab}
        onPick={(key) => setTab(key as ProtectionTab)}
        options={[
          { key: "health", label: "الصحّة" },
          { key: "reconcile", label: "المطابقة اليوميّة" },
          { key: "ledger", label: "دفتر SofizPay" },
        ]}
      />
      <ErrorNote message={error} />
      <SuccessNote message={done} />
      <div className="mt-12">
        {tab === "health" ? (
          <HealthTab country={country} owner={owner} onError={setError} onDone={setDone} />
        ) : tab === "reconcile" ? (
          <ReconcileTab country={country} owner={owner} onError={setError} onDone={setDone} />
        ) : (
          <LedgerTab country={country} owner={owner} onError={setError} />
        )}
      </div>
    </Shell>
  );
}

// ------------------------------------------------------------------ الصحّة

function HealthTab({
  country,
  owner,
  onError,
  onDone,
}: {
  country: CountryCode;
  owner: boolean;
  onError: (m: string | null) => void;
  onDone: (m: string | null) => void;
}) {
  const [health, setHealth] = useState<PaymentHealth | null>(null);
  const [window, setWindow] = useState<HealthWindow>("today");
  const [acting, setActing] = useState<{ row: MethodHealth; action: "hide" | "restore" } | null>(null);

  const load = useCallback(async () => {
    setHealth(await getPaymentHealth(country));
  }, [country]);

  useEffect(() => {
    load().catch((caught) => onError(message(caught, "تعذّر قراءة صحّة الطرق")));
  }, [load, onError]);

  return (
    <>
      <Pills
        value={window}
        onPick={(key) => setWindow(key as HealthWindow)}
        options={(Object.keys(WINDOW_LABEL) as HealthWindow[]).map((key) => ({ key, label: WINDOW_LABEL[key] }))}
      />
      <p className="mt-8 text-11.5 text-muted">
        النسبةُ من المحسوم (دُفع أو رُفض) — من عاد ولم يُكمل لا يُحسب على الطريقة. وتُخفى طريقةُ الوسيط آليّاً بعد{" "}
        {digits(String(health?.streak_limit ?? 3))} إخفاقاتٍ متتالية، ويعيدها المالكُ وحدَه.
      </p>
      <div className="mt-10">
        <Table
          columns="1.4fr 1fr 0.8fr 0.8fr 0.8fr 0.8fr 1.4fr 1fr"
          headers={["الطريقة", "الحال", "النجاح", "دُفع", "رُفض", "ينتظر", "السبب", ""]}
          rows={health?.methods ?? null}
          keyOf={(row) => row.id}
          empty={{ title: "لا طرقَ دفعٍ في هذه الدولة", hint: "أضف الطرقَ من «نظام الدفع»." }}
          render={(row) => {
            const w = row.windows[window];
            return (
              <>
                <span className="min-w-0">
                  <span className="block truncate font-semibold text-ink">{row.name}</span>
                  <span dir="ltr" className="block text-10.5 text-muted">
                    {row.code}
                    {row.integration ? ` · ${row.integration}` : ""}
                  </span>
                </span>
                <span
                  className={cn(
                    "font-semibold",
                    row.enabled && !row.gateway_down ? "text-ok" : row.hidden_reason || row.gateway_down ? "text-danger" : "text-muted",
                  )}
                >
                  {row.enabled
                    ? row.gateway_down
                      ? "الوسيطُ متوقّف"
                      : "مفعَّلة"
                    : row.hidden_reason
                      ? row.hidden_auto
                        ? "مخفيّة آليّاً"
                        : "مخفيّة بيد المالك"
                      : "موقوفة"}
                  {row.failure_streak > 0 ? (
                    <span className="block text-10.5 font-normal text-muted">
                      {digits(String(row.failure_streak))} إخفاقاتٍ متتالية
                    </span>
                  ) : null}
                </span>
                <span className="font-semibold text-ink">{w.success_rate === null ? "—" : `${digits(String(w.success_rate))}%`}</span>
                <span>{digits(String(w.paid))}</span>
                <span>{digits(String(w.failed))}</span>
                <span>{digits(String(w.pending + w.processing))}</span>
                <span className="min-w-0 text-11.5 text-muted">
                  {row.hidden_reason ? (
                    <>
                      <span className="block truncate" title={row.hidden_reason}>
                        {row.hidden_reason}
                      </span>
                      <span className="block text-10.5">{when(row.hidden_at)}</span>
                    </>
                  ) : (
                    "—"
                  )}
                </span>
                <span className="flex justify-end">
                  {owner && row.integration ? (
                    row.hidden_reason ? (
                      <button type="button" className="text-11.5 font-semibold text-ink" onClick={() => setActing({ row, action: "restore" })}>
                        إعادة التشغيل
                      </button>
                    ) : row.enabled ? (
                      <button type="button" className="text-11.5 font-semibold text-muted" onClick={() => setActing({ row, action: "hide" })}>
                        إخفاء
                      </button>
                    ) : null
                  ) : null}
                </span>
              </>
            );
          }}
        />
      </div>
      {acting ? (
        <ReasonModal
          title={acting.action === "restore" ? `إعادة تشغيل «${acting.row.name}»` : `إخفاء «${acting.row.name}»`}
          hint={
            acting.action === "restore"
              ? "تعود الطريقةُ للناس الآن. اكتب لماذا — يُحفظ مع الوقت في سجلِّ التدقيق."
              : "تختفي الطريقةُ للناس الآن ويرون لافتةً تدلّهم على البدائل. ولا يعيدها غيرُك."
          }
          confirm={acting.action === "restore" ? "إعادة التشغيل" : "إخفاء"}
          onClose={() => setActing(null)}
          onSubmit={async (reason) => {
            if (acting.action === "restore") await restorePayMethod(acting.row.id, reason);
            else await hidePayMethod(acting.row.id, reason);
            onDone(acting.action === "restore" ? `عادت «${acting.row.name}» للناس` : `أُخفيت «${acting.row.name}»`);
            setActing(null);
            await load();
          }}
        />
      ) : null}
    </>
  );
}

function ReasonModal({
  title,
  hint,
  confirm,
  onClose,
  onSubmit,
}: {
  title: string;
  hint: string;
  confirm: string;
  onClose: () => void;
  onSubmit: (reason: string) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  return (
    <Modal title={title} onClose={onClose}>
      <p className="text-12 text-muted">{hint}</p>
      <div className="mt-10">
        <Field label="السبب" value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500} />
      </div>
      <ErrorNote message={failure} />
      <div className="mt-12 flex justify-end gap-8">
        <Button variant="ghost" size="md" onClick={onClose}>
          إلغاء
        </Button>
        <Button
          size="md"
          disabled={busy || reason.trim().length < 3}
          onClick={async () => {
            setBusy(true);
            setFailure(null);
            try {
              await onSubmit(reason.trim());
            } catch (caught) {
              setFailure(message(caught, "تعذّر الحفظ"));
            } finally {
              setBusy(false);
            }
          }}
        >
          {confirm}
        </Button>
      </div>
    </Modal>
  );
}

// ------------------------------------------------------------------ المطابقة

function ReconcileTab({
  country,
  owner,
  onError,
  onDone,
}: {
  country: CountryCode;
  owner: boolean;
  onError: (m: string | null) => void;
  onDone: (m: string | null) => void;
}) {
  const [rows, setRows] = useState<GatewayReconciliation[] | null>(null);
  const [open, setOpen] = useState<GatewayReconciliation | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setRows(await listReconciliations(country));
  }, [country]);

  useEffect(() => {
    load().catch((caught) => onError(message(caught, "تعذّر قراءة سجلِّ المطابقة")));
  }, [load, onError]);

  return (
    <>
      <Table
        columns="1.2fr 1fr 0.8fr 0.8fr 0.9fr 0.9fr 1fr"
        headers={["الوقت", "الوسيط", "سُئل", "طابق", "افترق", "تعذّر", ""]}
        rows={rows}
        keyOf={(row) => row.id}
        toolbar={
          owner ? (
            <Button
              size="md"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  const reports = await runReconciliation();
                  onDone(`طُوبق ${digits(String(reports.length))} عقداً`);
                  await load();
                } catch (caught) {
                  onError(message(caught, "تعذّرت المطابقة"));
                } finally {
                  setBusy(false);
                }
              }}
            >
              طابِق الآن
            </Button>
          ) : undefined
        }
        empty={{ title: "لا تقاريرَ بعد", hint: "تجري المطابقةُ مرّةً كلَّ يوم لكلِّ وسيطٍ بعقدٍ مفعَّل." }}
        render={(row) => (
          <>
            <span>
              {when(row.created_at)}
              <span className="block text-10.5 text-muted">{row.trigger === "manual" ? "بيد المالك" : "يوميّة"}</span>
            </span>
            <span dir="ltr">{row.integration}</span>
            <span>{digits(String(row.checked))}</span>
            <span>{digits(String(row.matched))}</span>
            <span className={row.mismatched ? "font-semibold text-danger" : ""}>{digits(String(row.mismatched))}</span>
            <span>{digits(String(row.unreachable))}</span>
            <span className="flex justify-end">
              <button type="button" className="text-11.5 font-semibold text-ink" onClick={() => setOpen(row)}>
                التفاصيل
              </button>
            </span>
          </>
        )}
      />
      {open ? (
        <Modal title={`مطابقة ${open.integration} — ${when(open.created_at)}`} onClose={() => setOpen(null)} wide>
          <p className="text-12 text-muted">
            النافذة: {when(open.window_start)} ← {when(open.window_end)}. تقريرٌ لا تصحيح — ما دُفع ولم يُقيَّد تقيِّده التسويةُ
            الدوريّةُ مرّةً واحدة، وما افترق غيرُه يُراجع من «نظام الدفع».
          </p>
          {open.details.error ? <p className="mt-8 text-12 text-danger">تعذّر: {open.details.error}</p> : null}
          {open.details.ledger ? (
            <p className="mt-8 text-12">
              Stellar: {digits(String(open.details.ledger.incoming_count ?? 0))} واردة بمجموع{" "}
              <span dir="ltr">{open.details.ledger.incoming_total ?? "—"}</span> DZT
              {open.details.ours ? (
                <>
                  {" "}
                  — وعندنا {digits(String(open.details.ours.paid_count))} مقيَّدة بمجموع{" "}
                  <span dir="ltr">{open.details.ours.paid_total}</span>
                </>
              ) : null}
              {open.details.ledger.error ? ` (تعذّرت القراءة: ${open.details.ledger.error})` : ""}
            </p>
          ) : null}
          <div className="mt-10 grid gap-6">
            {(open.details.items ?? []).length === 0 ? (
              <p className="text-12 text-muted">لا افتراق.</p>
            ) : (
              (open.details.items ?? []).map((item) => (
                <div key={item.request_id} className="rounded-10 border border-line p-8 text-12">
                  <b className="text-ink">{MISMATCH_LABEL[item.kind] ?? item.kind}</b>
                  <span className="block text-muted">
                    <span dir="ltr">{item.ref}</span> · عندنا «{item.ours}» · الوسيط «{item.theirs}» ·{" "}
                    <span dir="ltr">{item.amount}</span>
                    {item.gateway_amount ? (
                      <>
                        {" "}
                        / <span dir="ltr">{item.gateway_amount}</span>
                      </>
                    ) : null}{" "}
                    · {when(item.created_at)}
                  </span>
                </div>
              ))
            )}
          </div>
        </Modal>
      ) : null}
    </>
  );
}

// ------------------------------------------------------------------ دفترُ SofizPay

function LedgerTab({ country, owner, onError }: { country: CountryCode; owner: boolean; onError: (m: string | null) => void }) {
  const [ledger, setLedger] = useState<GatewayLedger | null>(null);
  const [balance, setBalance] = useState<GatewayLedgerBalance | null>(null);
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [direction, setDirection] = useState<"" | "in" | "out">("");
  const [search, setSearch] = useState("");
  const [minAmount, setMinAmount] = useState("");
  const [maxAmount, setMaxAmount] = useState("");
  const [failure, setFailure] = useState<string | null>(null);

  const query = useCallback(
    () => ({
      country,
      since: since || undefined,
      until: until || undefined,
      direction: direction || undefined,
      search: search.trim() || undefined,
      min_amount: minAmount || undefined,
      max_amount: maxAmount || undefined,
    }),
    [country, since, until, direction, search, minAmount, maxAmount],
  );

  const load = useCallback(async () => {
    setFailure(null);
    try {
      setLedger(await getSofizpayTransactions(query()));
    } catch (caught) {
      setLedger(null);
      setFailure(message(caught, "تعذّر قراءة دفتر SofizPay"));
    }
  }, [query]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!owner) return;
    getSofizpayBalance(country)
      .then(setBalance)
      .catch(() => setBalance(null));
  }, [country, owner]);

  return (
    <>
      {owner && balance ? (
        <div className="ad-card mb-12 flex items-baseline justify-between gap-12 p-14">
          <span className="text-12 text-muted">رصيدُ حساب SofizPay — قراءةً من Stellar، للمالك وحدَه</span>
          <span dir="ltr" className="text-20 font-bold text-ink">
            {balance.balance} {balance.asset_code}
          </span>
        </div>
      ) : null}
      <p className="ad-card mb-12 p-12 text-12 text-muted">
        مساعدة: أشهرُ رفضٍ من البنك «رمز التحقّق (CVV) غير صحيح» — الدافعُ يدخل رمزَ PIN بدل CVV2 (3 أرقام خلف البطاقة). التطبيقان ينبّهان قبل صفحة
        البنك وفوقها، وكلُّ طلبٍ مرفوضٍ في «المعاملات» يحمل السببَ بكلماتنا ورمزَ البنك ورسالتَه للدعم.
      </p>
      <div className="grid gap-8 sm:grid-cols-3">
        <DateInput label="من" value={since} onChange={setSince} />
        <DateInput label="إلى" value={until} onChange={setUntil} />
        <Select label="الاتجاه" value={direction} onChange={(event) => setDirection(event.target.value as "" | "in" | "out")}>
          <option value="">الكلّ</option>
          <option value="in">وارد</option>
          <option value="out">خارج</option>
        </Select>
        <Field label="بحث (المذكّرة أو المعاملة)" value={search} onChange={(event) => setSearch(event.target.value)} />
        <Field label="أقلُّ مبلغ" dir="ltr" inputMode="decimal" value={minAmount} onChange={(event) => setMinAmount(event.target.value)} />
        <Field label="أكبرُ مبلغ" dir="ltr" inputMode="decimal" value={maxAmount} onChange={(event) => setMaxAmount(event.target.value)} />
      </div>
      <ErrorNote message={failure} />
      {ledger?.truncated ? <p className="mt-8 text-11.5 text-muted">بلغت القراءةُ سقفَها قبل بداية النافذة — ضيّق التاريخ.</p> : null}
      <div className="mt-10">
        <Table
          columns="1.2fr 0.7fr 1fr 1.6fr 1.6fr"
          headers={["الوقت", "الاتجاه", "المبلغ", "المذكّرة", "المعاملة"]}
          rows={ledger?.entries ?? (failure ? [] : null)}
          keyOf={(row) => row.id}
          toolbar={
            <Button
              size="md"
              variant="ghost"
              onClick={() => exportSofizpayTransactions(query()).catch((caught) => onError(message(caught, "تعذّر التصدير")))}
            >
              تصدير CSV
            </Button>
          }
          empty={{ title: "لا معاملات", hint: "لا شيءَ في الحساب بهذه المرشّحات." }}
          render={(row) => (
            <>
              <span>{when(row.created_at)}</span>
              <span className={row.direction === "in" ? "font-semibold text-ok" : "text-muted"}>
                {row.direction === "in" ? "وارد" : "خارج"}
              </span>
              <span dir="ltr" className="font-semibold text-ink">
                {row.amount} {ledger?.asset_code}
              </span>
              <span className="min-w-0 truncate" title={row.memo}>
                {row.memo || "—"}
              </span>
              <span dir="ltr" className="min-w-0 truncate text-10.5 text-muted" title={row.transaction_hash}>
                {row.transaction_hash}
              </span>
            </>
          )}
        />
      </div>
    </>
  );
}
