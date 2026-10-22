/** **مراجعةُ تحويلات BaridiMob — الجزائر** (SPEC §٨٢-ب/٤–٥، أمرُ المالك ٢٠٢٦-١٠-٢٢).
 *
 * **صفحةُ المراجع وحدُها** — ويفتحها المالكُ أيضاً، **واعتمادٌ واحدٌ من أيّهما يكفي**. لكلِّ طلب: صورةُ الإيصال، والمبلغ، ورقمُ التحويل،
 * ومرجعُ TAXO، والتاريخ، والسوق — **ومن صاحبه اسمُه الأوّلُ وهاتفٌ مقنَّعٌ لا غير**. والقرار: «اعتماد» أو «رفض» بسببٍ يقرؤه صاحبُه.
 *
 * **والمراجعُ لا يغيّر المبلغ**: يطابق ما وصل في BaridiMob بما كُتب هنا — فإن خالفه رفض بسببه، ويعيد صاحبُه الطلبَ بالصحيح.
 *
 * **وللمالك وحدَه بطاقةُ الإعداد أعلاها** — RIP، واسما صاحب الحساب بالعربيّة واللاتينيّة، والحدّان، والمفتاح. **ولا تظهر الطريقةُ للناس حتى
 * تكتمل وتُشعل** (والخادمُ يرفض الإشعالَ ناقصاً).
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  approveTransfer,
  getTransferSettings,
  listTransfers,
  rejectTransfer,
  saveTransferSettings,
  transferReceiptBlob,
} from "@/api/endpoints";
import type { AdminTransfer, PaymentRequestStatus, TransferSettings } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Pills, Table } from "@/components/Table";
import { Button } from "@/components/ui/Button";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { Field, Switch } from "@/components/ui/Field";
import { MoneyField } from "@/components/ui/Inputs";
import { Modal } from "@/components/ui/Modal";
import { PAYMENT_REQUEST_PURPOSE_LABEL, PAYMENT_REQUEST_STATUS_LABEL, PAYMENT_REQUEST_STATUS_TONE } from "@/lib/labels";
import { useSession } from "@/lib/session";
import { DISPLAY_LOCALE, cn, digits } from "@/lib/utils";

const MARKET_NAME: Record<string, string> = { DZ: "الجزائر", JO: "الأردن", LY: "ليبيا" };

function when(iso: string): string {
  const at = new Date(iso);
  return `${digits(at.toLocaleDateString(DISPLAY_LOCALE, { day: "numeric", month: "long" }))} ${digits(
    at.toLocaleTimeString(DISPLAY_LOCALE, { hour: "numeric", minute: "2-digit" }),
  )}`;
}

function day(value: string | null): string {
  if (!value) return "—";
  const at = new Date(`${value}T12:00:00`);
  return digits(at.toLocaleDateString(DISPLAY_LOCALE, { day: "numeric", month: "long", year: "numeric" }));
}

/** **مَن حسم** — بلا اسمِ إنسان */
const DECIDED_BY: Record<string, string> = { reviewer: "المراجع", owner: "المالك", staff: "الماليّة" };

export function TransfersScreen() {
  const { user } = useSession();
  const owner = Boolean(user?.roles?.includes("owner"));
  const [filter, setFilter] = useState<PaymentRequestStatus | "all">("pending");
  const [rows, setRows] = useState<AdminTransfer[] | null>(null);
  const [open, setOpen] = useState<AdminTransfer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRows(
      await listTransfers(
        filter === "all" ? { all: true } : { status: filter },
      ),
    );
  }, [filter]);

  useEffect(() => {
    load().catch((caught) => setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة التحويلات"));
  }, [load]);

  return (
    <Shell title="تحويلات BaridiMob" subtitle="الجزائر — طابقِ كلَّ طلبٍ بما وصل فعلاً في BaridiMob، ثمّ اعتمِده أو ارفضه بسبب">
      {owner ? <SettingsCard onSaved={setDone} /> : null}
      <Pills
        value={filter}
        onPick={(key) => setFilter(key as PaymentRequestStatus | "all")}
        options={[
          { key: "pending", label: "تنتظر المراجعة" },
          { key: "approved", label: PAYMENT_REQUEST_STATUS_LABEL.approved },
          { key: "rejected", label: PAYMENT_REQUEST_STATUS_LABEL.rejected },
          { key: "all", label: "الكل" },
        ]}
      />
      <ErrorNote message={error} />
      <SuccessNote message={done} />
      <div className="mt-12">
        <Table
          columns="1.1fr 0.9fr 1.1fr 1fr 1fr 1.1fr 0.8fr"
          headers={["صاحبه", "المبلغ", "رقم التحويل", "مرجع TAXO", "تاريخ التحويل", "الحالة", ""]}
          rows={rows}
          keyOf={(row) => row.id}
          empty={{ title: "لا تحويلات", hint: "يظهر هنا كلُّ طلبِ تحويلٍ عبر BaridiMob في الجزائر، من تقديمه حتى حسمه." }}
          render={(row) => (
            <>
              <span className="min-w-0">
                <span className="block truncate text-11.5 text-ink">{row.first_name}</span>
                <span dir="ltr" className="block text-10.5 text-muted">
                  {row.masked_phone}
                </span>
              </span>
              <span>
                <span className="block font-semibold text-ink">{digits(row.amount)}</span>
                <span className="block text-10.5 text-muted">{PAYMENT_REQUEST_PURPOSE_LABEL[row.purpose]}</span>
              </span>
              <span dir="ltr" className="text-muted">
                {row.reference ?? "—"}
              </span>
              <span dir="ltr" className="font-semibold text-ink">
                {row.public_ref}
              </span>
              <span className="text-muted">
                {day(row.transfer_date)}
                <span className="block text-10.5">{MARKET_NAME[row.country_code] ?? row.country_code}</span>
              </span>
              <span className={cn("font-semibold", PAYMENT_REQUEST_STATUS_TONE[row.status])}>
                {row.status === "pending" ? "تنتظر المراجعة" : PAYMENT_REQUEST_STATUS_LABEL[row.status]}
                {row.reviewed_at ? (
                  <span className="block text-10.5 font-normal text-muted">
                    {row.reviewed_by ? `${DECIDED_BY[row.reviewed_by] ?? ""} · ` : ""}
                    {when(row.reviewed_at)}
                  </span>
                ) : null}
                {row.rejection_reason ? (
                  <span className="block text-10.5 font-normal text-muted">{row.rejection_reason}</span>
                ) : null}
              </span>
              <span className="flex justify-end">
                <button type="button" onClick={() => setOpen(row)} className="text-11.5 font-semibold text-ink">
                  {row.status === "pending" ? "مراجعة" : "الإيصال"}
                </button>
              </span>
            </>
          )}
        />
      </div>
      {open ? (
        <ReviewModal
          row={open}
          onClose={() => setOpen(null)}
          onDone={(message) => {
            setOpen(null);
            setDone(message);
            void load();
          }}
        />
      ) : null}
    </Shell>
  );
}

function ReviewModal({ row, onClose, onDone }: { row: AdminTransfer; onClose: () => void; onDone: (message: string) => void }) {
  const [file, setFile] = useState<{ url: string; type: string } | null>(null);
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let opened: string | null = null;
    if (row.has_receipt) {
      transferReceiptBlob(row.id)
        .then((answer) => {
          opened = answer.url;
          setFile(answer);
        })
        .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "تعذّر فتح الإيصال"));
    }
    // **من يفتح الإيصالَ يحرّره** — وإلا بقي في ذاكرة التبويب
    return () => {
      if (opened) URL.revokeObjectURL(opened);
    };
  }, [row.id, row.has_receipt]);

  async function decide(approve: boolean) {
    setBusy(true);
    setError(null);
    try {
      if (approve) await approveTransfer(row.id);
      else await rejectTransfer(row.id, reason.trim());
      onDone(approve ? "اعتُمد التحويل — أُضيف المبلغ إلى رصيد صاحبه" : "رُفض التحويل — ويقرأ صاحبُه السبب");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر التنفيذ");
    } finally {
      setBusy(false);
    }
  }

  const facts: [string, string, boolean][] = [
    ["المبلغ", digits(row.amount), false],
    ["رقم التحويل", row.reference ?? "—", true],
    ["مرجع TAXO", row.public_ref, true],
    ["تاريخ التحويل", day(row.transfer_date), false],
    ["السوق", MARKET_NAME[row.country_code] ?? row.country_code, false],
    ["صاحبه", `${row.first_name} · ${row.masked_phone}`, false],
    ["قُدِّم", when(row.created_at), false],
  ];

  return (
    <Modal title={`تحويل ${row.public_ref}`} onClose={onClose} wide>
      <div className="grid gap-8">
        {facts.map(([label, value, ltr]) => (
          <div key={label} className="flex items-baseline justify-between rounded-14 border border-line bg-surface-2 px-14 py-10">
            <span className="text-12 text-muted">{label}</span>
            <span dir={ltr ? "ltr" : undefined} className="text-13 font-semibold text-ink">
              {value}
            </span>
          </div>
        ))}
      </div>
      <div className="mt-14">
        {file ? (
          file.type === "application/pdf" ? (
            <a href={file.url} target="_blank" rel="noreferrer" className="text-12 font-semibold text-ink underline">
              افتح ملفَّ الإيصال (PDF)
            </a>
          ) : (
            <img src={file.url} alt="صورة الإيصال" className="mx-auto block max-h-[60vh] max-w-full rounded-14" />
          )
        ) : row.has_receipt ? null : (
          <p className="text-12 text-muted">لا إيصالَ مرفق.</p>
        )}
      </div>
      {row.status === "pending" ? (
        <>
          <p className="mt-14 rounded-14 border border-warn bg-surface-2 px-14 py-12 text-12 leading-note text-ink">
            اعتمِد فقط إن وصل هذا المبلغُ نفسُه في BaridiMob برقم التحويل نفسِه. الاعتمادُ يضيف المبلغَ إلى رصيد صاحبه ولا يُلغى.
          </p>
          {rejecting ? (
            <Field
              label="سببُ الرفض — يقرؤه صاحبُ التحويل كما تكتبه"
              name="reason"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          ) : null}
        </>
      ) : null}
      <ErrorNote message={error} />
      <div className="mt-18 flex gap-10">
        {row.status === "pending" && !rejecting ? (
          <>
            <Button className="flex-1" size="md" loading={busy} onClick={() => void decide(true)}>
              اعتماد
            </Button>
            <Button className="flex-1" size="md" variant="secondary" onClick={() => setRejecting(true)}>
              رفض
            </Button>
          </>
        ) : null}
        {row.status === "pending" && rejecting ? (
          <Button className="flex-1" size="md" loading={busy} disabled={reason.trim().length < 3} onClick={() => void decide(false)}>
            ارفض بهذا السبب
          </Button>
        ) : null}
        <Button className="flex-1" size="md" variant="secondary" onClick={onClose}>
          إغلاق
        </Button>
      </div>
    </Modal>
  );
}

/** **بطاقةُ المالك** — حسابُ الاستقبال وحدّاه ومفتاحُه */
function SettingsCard({ onSaved }: { onSaved: (message: string) => void }) {
  const [current, setCurrent] = useState<TransferSettings | null>(null);
  const [rip, setRip] = useState("");
  const [holder, setHolder] = useState("");
  const [latin, setLatin] = useState("");
  const [min, setMin] = useState("");
  const [max, setMax] = useState("");
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fill = useCallback((answer: TransferSettings) => {
    setCurrent(answer);
    setRip(answer.account_number ?? "");
    setHolder(answer.account_holder ?? "");
    setLatin(answer.account_holder_latin ?? "");
    setMin(answer.min_amount ?? "");
    setMax(answer.max_amount ?? "");
    setEnabled(answer.enabled);
  }, []);

  useEffect(() => {
    getTransferSettings()
      .then(fill)
      .catch((caught) => setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة الإعداد"));
  }, [fill]);

  const ripDigits = rip.replace(/\D/g, "");
  const ripOk = ripDigits.length === 20;

  async function save() {
    setBusy(true);
    setError(null);
    try {
      fill(
        await saveTransferSettings({
          account_number: ripDigits || null,
          account_holder: holder.trim() || null,
          account_holder_latin: latin.trim() || null,
          min_amount: min.trim() || null,
          max_amount: max.trim() || null,
          enabled,
        }),
      );
      onSaved(enabled ? "حُفظ — وBaridiMob ظاهرةٌ للناس في الجزائر" : "حُفظ — وBaridiMob مخفيّةٌ عن الناس");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mb-16 rounded-18 border border-line bg-surface px-16 py-14">
      <div className="mb-10 flex items-baseline justify-between gap-10">
        <h2 className="text-14 font-bold text-ink">إعداد BaridiMob — للمالك وحدَه</h2>
        <span className={cn("text-11.5 font-semibold", current?.enabled ? "text-ok" : "text-muted")}>
          {current === null ? "" : current.enabled ? "ظاهرةٌ للناس" : current.configured ? "مكتملة · مخفيّة" : "لم تُضبط · مخفيّة"}
        </span>
      </div>
      <div className="grid gap-10 md:grid-cols-2">
        <Field
          label="رقم RIP — عشرون رقماً"
          name="rip"
          dir="ltr"
          inputMode="numeric"
          autoComplete="off"
          value={rip}
          onChange={(event) => setRip(event.target.value)}
          error={rip && !ripOk ? `${digits(String(ripDigits.length))} رقماً — المطلوبُ عشرون` : null}
        />
        <Field label="اسمُ صاحب الحساب (بالعربيّة)" name="holder" value={holder} onChange={(event) => setHolder(event.target.value)} />
        <Field
          label="الاسمُ كما يظهر في BaridiMob (لاتينيّ)"
          name="holder_latin"
          dir="ltr"
          value={latin}
          onChange={(event) => setLatin(event.target.value.toUpperCase())}
        />
        <div className="grid grid-cols-2 gap-10">
          <MoneyField label="أقلُّ مبلغ" name="min_amount" value={min} onChange={setMin} currency={current?.currency} />
          <MoneyField label="أكثرُ مبلغ" name="max_amount" value={max} onChange={setMax} currency={current?.currency} />
        </div>
      </div>
      <div className="mt-12 flex flex-wrap items-center justify-between gap-10">
        <Switch checked={enabled} onChange={setEnabled} label="أظهِرها للناس في تطبيقَي الراكب والكبتن" />
        <Button size="md" loading={busy} disabled={Boolean(rip) && !ripOk} onClick={() => void save()}>
          حفظ
        </Button>
      </div>
      <ErrorNote message={error} />
    </section>
  );
}
