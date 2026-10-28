/** **نظامُ الدفع الجديد** — طابورُ الموظّف الماليّ وطرقُ الدفع لكلِّ دولة (SPEC §٧٣-هـ المرحلة ١).
 *
 * **لسانان بصلاحيتين** (§٧٣-هـ/١١): **«الطلبات»** — الاعتمادُ والرفضُ والردُّ والإلغاء `finance.manage`؛ **و«طرق الدفع»** — أرقامُ RIP
 * والحسابات وصورةُ QR — `settings.write`، **وكلُّ تغييرٍ فيها يُدقَّق بقبله وبعده**: تبديلُ رقم الحساب أخطرُ بابٍ في النظام. **والخادمُ
 * يحرس الاثنين**؛ والشاشةُ ترسم الأفعالَ للمشرف (`isAdmin`) وتعرض ما يردّه الخادمُ كما هو.
 *
 * **وثلاثةٌ تحكم كلَّ زرٍّ في الطابور**:
 * 1. **المبلغُ المقيَّدُ مبلغُ الموظّف** — ما قرأه في كشف الحساب (قرارُ المالك ٢٠٢٦-٠٨-٢٩)، **ودعوى صاحب الطلب تبقى مرئيّةً جوارَه**.
 * 2. **لا رفضَ ولا ردَّ ولا إلغاءَ بلا سببٍ مكتوب** — يقرؤه صاحبُ الدفعة في تطبيقه كما كُتب.
 * 3. **الإيصالُ يُفتح قبل الاعتماد** — صورتُه أو ملفُّه في حوارٍ لا في تبويبٍ آخر.
 *
 * **ويتبع مبدّلَ الدولة**؛ وحيث `payment_requests_enabled` مطفأٌ يقول البلاغُ أعلاه إن التطبيقين لا يعرضان شيئاً بعد.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  approvePaymentRequest,
  cancelPaymentRequest,
  createPayMethod,
  listPayMethods,
  listPaymentRequests,
  payMethodQrBlob,
  paymentReceiptBlob,
  refundPaymentRequest,
  rejectPaymentRequest,
  updatePayMethod,
  uploadPayMethodQr,
} from "@/api/endpoints";
import type {
  AdminPayMethod,
  AdminPaymentRequest,
  CountryCode,
  GatewayFeeBearer,
  PaymentProviderKind,
  PaymentRequestStatus,
} from "@/api/types";
import { GuardBanner } from "@/components/GuardBanner";
import { Shell } from "@/components/Shell";
import { Pills, Table, TableSearch } from "@/components/Table";
import { Button } from "@/components/ui/Button";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { Checkbox, Field, Select, Switch } from "@/components/ui/Field";
import { MoneyField } from "@/components/ui/Inputs";
import { Modal } from "@/components/ui/Modal";
import { useCountryConfig } from "@/lib/config";
import { useCountry } from "@/lib/country";
import {
  GATEWAY_FEE_BEARER_LABEL,
  PAYMENT_PROVIDER_KIND_LABEL,
  PAYMENT_REQUEST_PURPOSE_LABEL,
  PAYMENT_REQUEST_STATUS_LABEL,
  PAYMENT_REQUEST_STATUS_TONE,
} from "@/lib/labels";
import { NO_RESULTS, useSearch } from "@/lib/search";
import { useSession } from "@/lib/session";
import { DISPLAY_LOCALE, cn, digits } from "@/lib/utils";

type Tab = "requests" | "methods";
type RequestAction = "approve" | "reject" | "refund" | "cancel";

function when(iso: string): string {
  const at = new Date(iso);
  return `${digits(at.toLocaleDateString(DISPLAY_LOCALE, { day: "numeric", month: "long" }))} ${digits(
    at.toLocaleTimeString(DISPLAY_LOCALE, { hour: "numeric", minute: "2-digit" }),
  )}`;
}

export function PaymentSystemScreen() {
  const { isAdmin } = useSession();
  const { country } = useCountry();
  const config = useCountryConfig(country);
  const switchedOff = config?.features.payment_requests_enabled === false;
  const [tab, setTab] = useState<Tab>("requests");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  return (
    <Shell title="نظام الدفع" subtitle="طلباتُ الدفع بإيصالاتها، وطرقُ الدفع لكلِّ دولة">
      <GuardBanner on={switchedOff} title="نظامُ الدفع مطفأٌ في هذه الدولة">
        <b className="text-ink">التطبيقان لا يعرضان طرقَ الدفع ولا يقبلان طلباً</b> حتى يُشعَل «نظام الدفع» من «الإعدادات» —
        وتُضبط الطرقُ هنا قبله.
      </GuardBanner>
      <Pills
        value={tab}
        onPick={(key) => setTab(key as Tab)}
        options={[
          { key: "requests", label: "الطلبات" },
          { key: "methods", label: "طرق الدفع" },
        ]}
      />
      <ErrorNote message={error} />
      <SuccessNote message={done} />
      <div className="mt-12">
        {tab === "requests" ? (
          <RequestsTab country={country} isAdmin={isAdmin} onError={setError} onDone={setDone} />
        ) : (
          <MethodsTab country={country} isAdmin={isAdmin} onError={setError} onDone={setDone} />
        )}
      </div>
    </Shell>
  );
}

// ------------------------------------------------------------------ الطلبات

function RequestsTab({
  country,
  isAdmin,
  onError,
  onDone,
}: {
  country: CountryCode;
  isAdmin: boolean;
  onError: (message: string | null) => void;
  onDone: (message: string | null) => void;
}) {
  const [status, setStatus] = useState<PaymentRequestStatus | "all">("pending");
  const [rows, setRows] = useState<AdminPaymentRequest[] | null>(null);
  const [acting, setActing] = useState<{ row: AdminPaymentRequest; action: RequestAction } | null>(null);
  const [receipt, setReceipt] = useState<AdminPaymentRequest | null>(null);
  const search = useSearch();

  const load = useCallback(async () => {
    setRows(
      await listPaymentRequests({
        country,
        status: status === "all" ? undefined : status,
        q: search.term || undefined,
      }),
    );
  }, [country, status, search.term]);

  useEffect(() => {
    load().catch((caught) => onError(caught instanceof ApiError ? caught.message : "تعذّر قراءة الطلبات"));
  }, [load, onError]);

  return (
    <>
      <Table
        toolbar={
          <div className="flex flex-wrap items-center gap-10">
            <Pills
              value={status}
              onPick={(key) => setStatus(key as PaymentRequestStatus | "all")}
              options={[
                { key: "all", label: "الكل" },
                { key: "pending", label: PAYMENT_REQUEST_STATUS_LABEL.pending },
                { key: "approved", label: PAYMENT_REQUEST_STATUS_LABEL.approved },
                { key: "rejected", label: PAYMENT_REQUEST_STATUS_LABEL.rejected },
                { key: "refunded", label: PAYMENT_REQUEST_STATUS_LABEL.refunded },
                { key: "cancelled", label: PAYMENT_REQUEST_STATUS_LABEL.cancelled },
              ]}
            />
            <TableSearch value={search.text} onChange={search.setText} placeholder="اسمُ صاحبه أو رقمُه أو رقمُ التحويل…" />
          </div>
        }
        searching={search.searching}
        noResults={NO_RESULTS}
        columns="1.3fr 1fr 1.1fr 0.9fr 1fr 1.2fr 1.4fr"
        headers={["صاحبها", "المبلغ", "الطريقة", "الغرض", "الطلب", "الحالة", ""]}
        rows={rows}
        keyOf={(row) => row.id}
        empty={{ title: "لا طلبات", hint: "يظهر هنا كلُّ طلبِ دفعٍ من راكبٍ أو كبتن، من تقديمه حتى حسمه." }}
        render={(row) => (
          <>
            <span className="min-w-0">
              <span className="block truncate text-11.5 text-ink">{row.user_name ?? "—"}</span>
              <span dir="ltr" className="block text-10.5 text-muted">
                {row.user_phone ?? ""} · {row.owner_type === "driver" ? "كبتن" : "راكب"}
              </span>
            </span>
            <span>
              <span className="block font-semibold text-ink">{digits(row.credited_amount ?? row.amount)}</span>
              {row.credited_amount && row.credited_amount !== row.amount ? (
                <span className="block text-10.5 text-muted">ادّعى {digits(row.amount)}</span>
              ) : null}
            </span>
            <span className="text-muted">
              {row.provider_name}
              {row.reference ? (
                <span dir="ltr" className="block text-10.5">
                  {row.reference}
                </span>
              ) : null}
              {row.external_id ? (
                <span dir="ltr" className="block text-10.5">
                  {row.external_id}
                </span>
              ) : null}
            </span>
            <span className="text-muted">{PAYMENT_REQUEST_PURPOSE_LABEL[row.purpose]}</span>
            <span className="text-muted">{when(row.created_at)}</span>
            <span className={cn("font-semibold", PAYMENT_REQUEST_STATUS_TONE[row.status])}>
              {PAYMENT_REQUEST_STATUS_LABEL[row.status]}
              {row.reviewed_at ? <span className="block text-10.5 font-normal text-muted">{when(row.reviewed_at)}</span> : null}
              {row.rejection_reason ?? row.refund_reason ?? row.cancel_reason ?? row.outcome_note ? (
                <span className="block text-10.5 font-normal text-muted">
                  {row.rejection_reason ?? row.refund_reason ?? row.cancel_reason ?? row.outcome_note}
                </span>
              ) : null}
              {row.subscription_id ? <span className="block text-10.5 font-normal text-ok">فُعِّل الاشتراك</span> : null}
              {row.transaction_id ? (
                <span dir="ltr" className="block text-10.5 font-normal text-muted" title="قيدُ الدفتر">
                  {row.transaction_id.slice(0, 8)}
                </span>
              ) : null}
            </span>
            <span className="flex flex-wrap justify-end gap-10">
              {row.has_receipt ? (
                <button type="button" onClick={() => setReceipt(row)} className="text-11.5 font-semibold text-ink">
                  الإيصال
                </button>
              ) : null}
              {isAdmin && row.status === "pending" ? (
                <>
                  <button type="button" onClick={() => setActing({ row, action: "approve" })} className="text-11.5 font-semibold text-ok">
                    اعتماد
                  </button>
                  <button type="button" onClick={() => setActing({ row, action: "reject" })} className="text-11.5 font-semibold text-danger">
                    رفض
                  </button>
                  <button type="button" onClick={() => setActing({ row, action: "cancel" })} className="text-11.5 font-semibold text-muted">
                    إلغاء
                  </button>
                </>
              ) : null}
              {isAdmin && row.status === "approved" ? (
                <button type="button" onClick={() => setActing({ row, action: "refund" })} className="text-11.5 font-semibold text-muted">
                  ردّ
                </button>
              ) : null}
            </span>
          </>
        )}
      />

      {receipt ? <ReceiptModal row={receipt} onClose={() => setReceipt(null)} /> : null}
      {acting ? (
        <ActionModal
          row={acting.row}
          action={acting.action}
          onClose={() => setActing(null)}
          onDone={(message) => {
            setActing(null);
            onDone(message);
            void load();
          }}
        />
      ) : null}
    </>
  );
}

function ReceiptModal({ row, onClose }: { row: AdminPaymentRequest; onClose: () => void }) {
  const [file, setFile] = useState<{ url: string; type: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let opened: string | null = null;
    paymentReceiptBlob(row.id)
      .then((answer) => {
        opened = answer.url;
        setFile(answer);
      })
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "تعذّر فتح الإيصال"));
    // **من يفتح الإيصالَ يحرّره** — وإلا بقي في ذاكرة التبويب
    return () => {
      if (opened) URL.revokeObjectURL(opened);
    };
  }, [row.id]);
  return (
    <Modal title={`إيصال ${row.user_name ?? ""}`} onClose={onClose} wide>
      <ErrorNote message={error} />
      {file ? (
        file.type === "application/pdf" ? (
          <a href={file.url} target="_blank" rel="noreferrer" className="text-12 font-semibold text-ink underline">
            افتح ملفَّ الإيصال (PDF)
          </a>
        ) : (
          <img src={file.url} alt="صورة الإيصال" className="mx-auto block max-h-[70vh] max-w-full rounded-14" />
        )
      ) : null}
      <div className="mt-18 flex">
        <Button className="flex-1" size="md" variant="secondary" onClick={onClose}>
          إغلاق
        </Button>
      </div>
    </Modal>
  );
}

const ACTION_TITLE: Record<RequestAction, string> = {
  approve: "اعتماد الدفعة",
  reject: "رفض الدفعة",
  refund: "ردّ الدفعة",
  cancel: "إلغاء الطلب",
};

function ActionModal({
  row,
  action,
  onClose,
  onDone,
}: {
  row: AdminPaymentRequest;
  action: RequestAction;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [amount, setAmount] = useState(row.amount);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const needsReason = action !== "approve";
  const differs = action === "approve" && amount.trim() !== "" && amount.trim() !== row.amount;

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      if (action === "approve") await approvePaymentRequest(row.id, amount);
      if (action === "reject") await rejectPaymentRequest(row.id, reason.trim());
      if (action === "refund") await refundPaymentRequest(row.id, reason.trim());
      if (action === "cancel") await cancelPaymentRequest(row.id, reason.trim());
      onDone(
        action === "approve"
          ? "اعتُمدت الدفعة — قُيّد الرصيد"
          : action === "refund"
            ? "رُدّت الدفعة — نقص الرصيدُ بقدرها"
            : action === "reject"
              ? "رُفضت الدفعة — ويقرأ صاحبُها السبب"
              : "أُلغي الطلب",
      );
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر التنفيذ");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={ACTION_TITLE[action]} onClose={onClose}>
      {action === "approve" || action === "refund" ? (
        <p className="mb-16 rounded-14 border border-warn bg-surface-2 px-14 py-12 text-12 leading-note text-ink">
          {action === "approve"
            ? "الاعتماد لا يُلغى. والخطأ يُصحَّح بـ«ردّ» بسببٍ مكتوب، لا بمحو الطلب."
            : "الردّ يُنقص رصيدَ صاحبها بقدر ما دخل، ولا يُكتب إن لم يكفِ الرصيد. والمالُ نفسُه يُردّ إلى حسابه خارجَ المنصّة."}
        </p>
      ) : null}
      <div className="mb-16 flex items-baseline justify-between rounded-14 border border-line bg-surface-2 px-14 py-12">
        <span className="text-12.5 text-muted">ما كتبه صاحبُ الطلب</span>
        <span className="text-15 font-bold text-ink">{digits(row.amount)}</span>
      </div>
      {action === "approve" ? (
        <>
          <MoneyField label="المبلغ الذي وصل حسابك فعلاً" name="credited_amount" value={amount} onChange={setAmount} currency={row.currency} />
          {differs ? (
            <p className="mt-8 text-11 leading-note text-warn-ink">
              يخالف ما كتبه — سيُقيَّد ما أدخلتَه أنت، ويبقى ما كتبه في سجلّ الطلب.
            </p>
          ) : null}
        </>
      ) : null}
      {needsReason ? (
        <Field
          label="السبب — يقرؤه صاحبُ الدفعة كما تكتبه"
          name="reason"
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      ) : null}
      <ErrorNote message={error} />
      <div className="mt-18 flex gap-10">
        <Button
          className="flex-1"
          size="md"
          loading={busy}
          disabled={needsReason ? reason.trim().length < 3 : Number(amount) <= 0}
          onClick={() => void submit()}
        >
          {ACTION_TITLE[action]}
        </Button>
        <Button className="flex-1" size="md" variant="secondary" onClick={onClose}>
          تراجع
        </Button>
      </div>
    </Modal>
  );
}

// ------------------------------------------------------------------ طرق الدفع

const KINDS: PaymentProviderKind[] = ["bank_transfer", "cash", "phone_number"];

/** **الوسيطان الآليّان** (المرحلة ٣) — مفتاحُ كلٍّ منهما في صفحة العقود، **وما يقبله كلٌّ من «من يحمل الرسوم»** كما تقول وثائقُه:
    Chargily يقبل الثلاثة، وSofizPay لا يوثّق خياراً فتحملها TAXO وحدَها. والخادمُ يرفض غيرَ ذلك بنصّ. */
type Integration = "chargily" | "sofizpay";
const GATEWAYS: { key: Integration; label: string; bearers: GatewayFeeBearer[] }[] = [
  // **خياران بأمر المالك** (SPEC §٧٤-ك/١): «TAXO» أو «الدافع» لكلِّ دولة — والمناصفةُ لا تُعرض
  { key: "chargily", label: "Chargily — الذهبية وCIB", bearers: ["taxo", "user"] },
  { key: "sofizpay", label: "SofizPay — CIB", bearers: ["taxo"] },
];

function MethodsTab({
  country,
  isAdmin,
  onError,
  onDone,
}: {
  country: CountryCode;
  isAdmin: boolean;
  onError: (message: string | null) => void;
  onDone: (message: string | null) => void;
}) {
  const [rows, setRows] = useState<AdminPayMethod[] | null>(null);
  const [editing, setEditing] = useState<AdminPayMethod | "new" | null>(null);
  const [qr, setQr] = useState<AdminPayMethod | null>(null);

  const load = useCallback(async () => setRows(await listPayMethods(country)), [country]);
  useEffect(() => {
    load().catch((caught) => onError(caught instanceof ApiError ? caught.message : "تعذّر قراءة طرق الدفع"));
  }, [load, onError]);

  return (
    <>
      <Table
        toolbar={
          isAdmin ? (
            <Button size="md" onClick={() => setEditing("new")}>
              إضافة طريقة
            </Button>
          ) : undefined
        }
        columns="1.3fr 1.2fr 1.4fr 0.9fr 1fr 1.2fr"
        headers={["الطريقة", "النوع", "الحساب", "الحال", "الأغراض", ""]}
        rows={rows}
        keyOf={(row) => row.id}
        empty={{ title: "لا طرقَ دفعٍ بعد", hint: "أضف طريقةً لكلِّ ما يقبله TAXO في هذه الدولة: كاشُ المكتب، والتحويلُ برقم RIP، والحسابُ البنكيّ، ورمزُ QR." }}
        render={(row) => (
          <>
            <span className="min-w-0">
              <span className="block truncate font-semibold text-ink">{row.name}</span>
              <span dir="ltr" className="block text-10.5 text-muted">
                {row.code}
                {row.integration ? ` · ${row.integration}` : ""} · {digits(String(row.sort_order))}
              </span>
            </span>
            <span className="text-muted">{PAYMENT_PROVIDER_KIND_LABEL[row.kind]}</span>
            <span className="min-w-0 text-muted">
              <span dir="ltr" className="block truncate">
                {row.account_number ?? "—"}
              </span>
              {row.account_holder ? <span className="block truncate text-10.5">{row.account_holder}</span> : null}
              {row.bank_name ? <span className="block truncate text-10.5">{row.bank_name}</span> : null}
              {row.instructions ? <span className="block truncate text-10.5">{row.instructions}</span> : null}
            </span>
            <span className={row.enabled ? "font-semibold text-ok" : "text-muted"} title={row.hidden_reason ?? undefined}>
              {row.enabled ? "مفعَّلة" : row.hidden_reason ? (row.hidden_auto ? "مخفيّة آليّاً" : "مخفيّة بيد المالك") : "موقوفة"}
            </span>
            <span className="text-muted">
              {[row.for_topup ? "شحن" : null, row.for_subscription ? "اشتراك" : null].filter(Boolean).join(" · ") || "—"}
            </span>
            <span className="flex flex-wrap justify-end gap-10">
              {isAdmin ? (
                <button type="button" onClick={() => setEditing(row)} className="text-11.5 font-semibold text-ink">
                  تعديل
                </button>
              ) : null}
              <button type="button" onClick={() => setQr(row)} className="text-11.5 font-semibold text-muted">
                {row.has_qr ? "رمز QR" : "أضف رمز QR"}
              </button>
            </span>
          </>
        )}
      />

      {editing ? (
        <MethodModal
          country={country}
          method={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onDone={(message) => {
            setEditing(null);
            onDone(message);
            void load();
          }}
        />
      ) : null}
      {qr ? (
        <QrModal
          method={qr}
          canEdit={isAdmin}
          onClose={() => setQr(null)}
          onDone={(message) => {
            setQr(null);
            onDone(message);
            void load();
          }}
        />
      ) : null}
    </>
  );
}

function MethodModal({
  country,
  method,
  onClose,
  onDone,
}: {
  country: CountryCode;
  method: AdminPayMethod | null;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [kind, setKind] = useState<PaymentProviderKind>(method?.kind ?? "bank_transfer");
  const [code, setCode] = useState(method?.code ?? "");
  const [name, setName] = useState(method?.name ?? "");
  const [enabled, setEnabled] = useState(method?.enabled ?? false);
  const [forTopup, setForTopup] = useState(method?.for_topup ?? true);
  const [forSubscription, setForSubscription] = useState(method?.for_subscription ?? true);
  const [holder, setHolder] = useState(method?.account_holder ?? "");
  const [number, setNumber] = useState(method?.account_number ?? "");
  const [bank, setBank] = useState(method?.bank_name ?? "");
  const [instructions, setInstructions] = useState(method?.instructions ?? "");
  const [order, setOrder] = useState(String(method?.sort_order ?? 0));
  const [integration, setIntegration] = useState<Integration | "">((method?.integration as Integration | null) ?? "");
  const [feeBearer, setFeeBearer] = useState<GatewayFeeBearer>(method?.fee_bearer ?? "taxo");
  const gateway = GATEWAYS.find((row) => row.key === integration) ?? null;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    const fields = {
      name: name.trim(),
      enabled,
      for_topup: forTopup,
      for_subscription: forSubscription,
      account_holder: holder.trim() || null,
      account_number: number.trim() || null,
      bank_name: bank.trim() || null,
      instructions: instructions.trim() || null,
      sort_order: Number(order) || 0,
      // **طريقةٌ يدويّةٌ لا رسومَ وسيطٍ عليها** — والخادمُ يرفض غيرَ «على TAXO» لها
      fee_bearer: gateway ? feeBearer : ("taxo" as GatewayFeeBearer),
    };
    try {
      if (method) await updatePayMethod(method.id, fields);
      else await createPayMethod({ ...fields, country_code: country, kind, code: code.trim(), integration: integration || null });
      onDone(method ? "حُفظت الطريقة — وسُجّل التغيير في التدقيق" : "أُضيفت الطريقة");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={method ? `تعديل ${method.name}` : "طريقة دفع جديدة"} onClose={onClose} wide>
      {method ? null : (
        <div className="mb-12 grid gap-12 sm:grid-cols-2">
          <Select label="النوع" name="kind" value={kind} onChange={(event) => setKind(event.target.value as PaymentProviderKind)}>
            {KINDS.map((key) => (
              <option key={key} value={key}>
                {PAYMENT_PROVIDER_KIND_LABEL[key]}
              </option>
            ))}
          </Select>
          <Field label="المعرّف (لاتينيّ ثابت)" name="code" dir="ltr" value={code} onChange={(event) => setCode(event.target.value)} />
          <Select
            label="كيف تُؤكَّد الدفعة"
            name="integration"
            value={integration}
            onChange={(event) => {
              const next = event.target.value as Integration | "";
              setIntegration(next);
              setFeeBearer("taxo");
            }}
          >
            <option value="">يدويّاً — يراجعها موظّفٌ ماليّ</option>
            {GATEWAYS.map((row) => (
              <option key={row.key} value={row.key}>
                آليّاً عبر {row.label}
              </option>
            ))}
          </Select>
        </div>
      )}
      {gateway ? (
        <div className="mb-12 grid gap-12 sm:grid-cols-2">
          <Select
            label="رسومُ الوسيط على من"
            name="fee_bearer"
            value={feeBearer}
            onChange={(event) => setFeeBearer(event.target.value as GatewayFeeBearer)}
          >
            {gateway.bearers.map((key) => (
              <option key={key} value={key}>
                {GATEWAY_FEE_BEARER_LABEL[key]}
              </option>
            ))}
          </Select>
          <p className="self-end text-11 leading-note text-muted">
            مفتاحُ الوسيط يُكتب في «العقود» لهذه الدولة، والطريقةُ لا تُفعَّل قبله. والدفعةُ تُضاف حين يؤكّدها الوسيط نفسُه — لا حين
            يعود المستخدم.
          </p>
        </div>
      ) : null}
      <div className="grid gap-12 sm:grid-cols-2">
        <Field label="الاسم كما يراه المستخدم" name="name" value={name} onChange={(event) => setName(event.target.value)} />
        <Field label="الترتيب" name="sort_order" dir="ltr" inputMode="numeric" value={order} onChange={(event) => setOrder(event.target.value.replace(/\D/g, ""))} />
        <Field
          label={kind === "phone_number" ? "رقم الهاتف" : "رقم الحساب / RIP"}
          name="account_number"
          dir="ltr"
          value={number}
          onChange={(event) => setNumber(event.target.value)}
        />
        <Field label="صاحب الحساب" name="account_holder" value={holder} onChange={(event) => setHolder(event.target.value)} />
        <Field label="البنك" name="bank_name" value={bank} onChange={(event) => setBank(event.target.value)} />
        <Field label="تعليماتٌ تظهر للمستخدم" name="instructions" value={instructions} onChange={(event) => setInstructions(event.target.value)} />
      </div>
      <div className="mt-12 flex flex-wrap items-center gap-16">
        <span className="flex items-center gap-8 text-12 text-ink">
          <Switch checked={enabled} onChange={setEnabled} label="مفعَّلة" />
          مفعَّلة
        </span>
        <Checkbox checked={forTopup} onChange={setForTopup}>
          لشحن المحفظة
        </Checkbox>
        <Checkbox checked={forSubscription} onChange={setForSubscription}>
          لدفع الاشتراك
        </Checkbox>
      </div>
      <p className="mt-12 text-11 leading-note text-muted">
        طريقةُ تحويلٍ لا تُفعَّل بلا رقم حسابٍ أو رمز QR — شاشةٌ تطلب تحويلاً ولا تقول إلى أين تُنتج حوالةً ضائعة. والإيصالُ ورقمُ التحويل
        إجباريّان في كلِّ تحويل.
      </p>
      <ErrorNote message={error} />
      <div className="mt-18 flex gap-10">
        <Button className="flex-1" size="md" loading={busy} disabled={name.trim().length < 2 || (!method && code.trim().length < 2)} onClick={() => void submit()}>
          حفظ
        </Button>
        <Button className="flex-1" size="md" variant="secondary" onClick={onClose}>
          تراجع
        </Button>
      </div>
    </Modal>
  );
}

function QrModal({
  method,
  canEdit,
  onClose,
  onDone,
}: {
  method: AdminPayMethod;
  canEdit: boolean;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [image, setImage] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!method.has_qr) return;
    let opened: string | null = null;
    payMethodQrBlob(method.id)
      .then((answer) => {
        opened = answer.url;
        setImage(answer.url);
      })
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "تعذّر فتح الرمز"));
    return () => {
      if (opened) URL.revokeObjectURL(opened);
    };
  }, [method.id, method.has_qr]);

  async function save() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      await uploadPayMethodQr(method.id, file);
      onDone("حُفظ رمزُ QR — ويراه المستخدمُ تحت الطريقة");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر رفع الرمز");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={`رمز QR — ${method.name}`} onClose={onClose}>
      {image ? <img src={image} alt={`رمز ${method.name}`} className="mx-auto block w-full max-w-xs rounded-14 bg-white p-12" /> : null}
      {canEdit ? (
        <label className="mt-12 block text-12 text-ink">
          {method.has_qr ? "استبدل الصورة" : "صورةُ الرمز"} (PNG أو JPEG أو WebP)
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            className="mt-6 block w-full text-12"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
      ) : null}
      <ErrorNote message={error} />
      <div className="mt-18 flex gap-10">
        {canEdit ? (
          <Button className="flex-1" size="md" loading={busy} disabled={!file} onClick={() => void save()}>
            حفظ الرمز
          </Button>
        ) : null}
        <Button className="flex-1" size="md" variant="secondary" onClick={onClose}>
          إغلاق
        </Button>
      </div>
    </Modal>
  );
}
