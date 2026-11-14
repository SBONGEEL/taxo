/** **بطاقاتُ شحن TAXO** — الدفعاتُ والبطاقاتُ والمحلّاتُ والفئاتُ والتقريرُ وتنبيهاتُ التخمين (SPEC §٧٣-هـ المرحلة ٢).
 *
 * **ثلاثةٌ تحكم هذه الشاشة**:
 * 1. **الرموزُ تظهر مرّةً واحدة** — في ردّ إنشاء الدفعة، فيُحفظ ملفُّ الطباعة فوراً؛ **ولا بابَ يعيدها** (تُخزَّن بصماتُها وحدَها).
 *    فإن ضاع الملفّ: تُلغى الدفعةُ بسببها وتُصدر غيرُها.
 * 2. **لا حذف** — الإلغاءُ لبطاقةٍ أو لدفعةٍ كاملةٍ بسببٍ مكتوب؛ **والمستعمَلةُ تبقى مستعمَلة** (مالُها في محفظة صاحبها).
 * 3. **كلُّ رقمٍ من الخلفية** (§14): العدُّ والقيمُ والمستحقُّ من المحلّ بشرطه المجمَّد على الدفعة.
 *
 * **والصلاحيات في الخادم**: الفئاتُ وسقوفُ التخمين `settings.write`، والمحلّاتُ والدفعاتُ والإلغاءُ `finance.manage`. **ويتبع مبدّلَ الدولة.**
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  addCardDenomination,
  cancelCardBatch,
  cancelGift,
  cancelTaxoCard,
  cardShopReport,
  createCardBatch,
  createCardSeller,
  createCardShop,
  createGift,
  exportCardBatch,
  findTaxoCards,
  getCardLimits,
  listCardAlerts,
  listBatchCards,
  listCardBatches,
  listCardDenominations,
  downloadBatchInvoice,
  cardKindReport,
  extendCardBatch,
  getInvoiceSettings,
  listCardSellers,
  saveInvoiceSettings,
  listExpiringBatches,
  listCardShops,
  getPosSettings,
  savePosSettings,
  setCardSellerActive,
  listGifts,
  markGiftSent,
  reviewCardAlert,
  saveCardLimits,
  setCardDenominationActive,
  updateCardShop,
} from "@/api/endpoints";
import type {
  CardBatch,
  CardBatchCreated,
  CardDenomination,
  CardGuessAlert,
  CardShop,
  CardShopPaymentMode,
  CardShopReport,
  CardKindReport,
  CardSeller,
  CountryCode,
  InvoiceSettings,
  GiftChannel,
  GiftCreated,
  GiftDesign,
  GiftLink,
  GiftState,
  PosSettings,
  TaxoCardLimits,
  TaxoCardRow,
  TaxoCardState,
} from "@/api/types";
import { Shell } from "@/components/Shell";
import { Pills, Table, TableSearch } from "@/components/Table";
import { Button } from "@/components/ui/Button";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { DateInput, Field, Select, Switch } from "@/components/ui/Field";
import { MoneyField } from "@/components/ui/Inputs";
import { Modal } from "@/components/ui/Modal";
import { useCountryConfig } from "@/lib/config";
import { useCountry } from "@/lib/country";
import {
  CARD_SHOP_PAYMENT_MODE_LABEL,
  TAXO_CARD_BATCH_STATUS_LABEL,
  TAXO_CARD_STATUS_LABEL,
} from "@/lib/labels";
import { useSearch } from "@/lib/search";
import { useSession } from "@/lib/session";
import { DISPLAY_LOCALE, cn, digits } from "@/lib/utils";

type Tab = "batches" | "gifts" | "cards" | "shops" | "sellers" | "denominations" | "report" | "alerts";

function day(iso: string): string {
  return digits(new Date(iso).toLocaleDateString(DISPLAY_LOCALE, { day: "numeric", month: "long", year: "numeric" }));
}

function errorText(caught: unknown, fallback: string): string {
  return caught instanceof ApiError ? caught.message : fallback;
}

export function TaxoCardsScreen() {
  const { isAdmin } = useSession();
  const { country } = useCountry();
  const config = useCountryConfig(country);
  const currency = config?.currency;
  const [tab, setTab] = useState<Tab>("batches");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  return (
    <Shell title="بطاقات TAXO" subtitle="بطاقاتُ شحنٍ مطبوعةٌ تُباع في المحلّات — رمزٌ يشحن المحفظةَ مرّةً واحدة">
      <Pills
        value={tab}
        onPick={(key) => setTab(key as Tab)}
        options={[
          { key: "batches", label: "الدفعات" },
          { key: "gifts", label: "الهدايا" },
          { key: "cards", label: "البطاقات" },
          { key: "shops", label: "المحلّات" },
          { key: "sellers", label: "البائعون" },
          { key: "denominations", label: "الفئات" },
          { key: "report", label: "التقرير" },
          { key: "alerts", label: "التخمين" },
        ]}
      />
      <ErrorNote message={error} />
      <SuccessNote message={done} />
      <div className="mt-12">
        {tab === "batches" ? <BatchesTab country={country} isAdmin={isAdmin} onError={setError} onDone={setDone} /> : null}
        {tab === "gifts" ? <GiftsTab country={country} isAdmin={isAdmin} onError={setError} onDone={setDone} /> : null}
        {tab === "cards" ? <CardsTab country={country} isAdmin={isAdmin} onError={setError} onDone={setDone} /> : null}
        {tab === "shops" ? <ShopsTab country={country} isAdmin={isAdmin} onError={setError} onDone={setDone} /> : null}
        {tab === "sellers" ? <SellersTab country={country} isAdmin={isAdmin} onError={setError} onDone={setDone} /> : null}
        {tab === "denominations" ? (
          <DenominationsTab country={country} currency={currency} isAdmin={isAdmin} onError={setError} onDone={setDone} />
        ) : null}
        {tab === "report" ? <ReportTab country={country} isAdmin={isAdmin} onError={setError} onDone={setDone} /> : null}
        {tab === "alerts" ? <AlertsTab country={country} isAdmin={isAdmin} onError={setError} onDone={setDone} /> : null}
      </div>
    </Shell>
  );
}

type TabProps = {
  country: CountryCode;
  isAdmin: boolean;
  onError: (message: string | null) => void;
  onDone: (message: string | null) => void;
};

// ------------------------------------------------------------------ الدفعات

function BatchesTab({ country, isAdmin, onError, onDone }: TabProps) {
  const [rows, setRows] = useState<CardBatch[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<CardBatchCreated | null>(null);
  const [cancelling, setCancelling] = useState<CardBatch | null>(null);
  const [opened, setOpened] = useState<CardBatch | null>(null);

  const load = useCallback(
    async () => setRows((await listCardBatches(country)).filter((row) => row.kind !== "gift" && row.kind !== "pos")),
    [country],
  );
  useEffect(() => {
    load().catch((caught) => onError(errorText(caught, "تعذّر قراءة الدفعات")));
  }, [load, onError]);

  return (
    <>
      <Table
        toolbar={
          isAdmin ? (
            <Button size="md" onClick={() => setCreating(true)}>
              دفعة جديدة
            </Button>
          ) : undefined
        }
        columns="0.6fr 0.9fr 1.2fr 1.3fr 1.3fr 1fr 1fr"
        headers={["الدفعة", "الفئة × العدد", "المحلّ", "الصلاحية", "الحال", "المستحقّ", ""]}
        rows={rows}
        keyOf={(row) => row.id}
        empty={{ title: "لا دفعات بعد", hint: "أضف فئةً ومحلّاً، ثمّ ولّد دفعةً واحفظ ملفَّ طباعتها فور ظهوره." }}
        render={(row) => (
          <>
            <span className="font-semibold text-ink">#{digits(String(row.number))}</span>
            <span className="text-ink">
              {digits(row.amount)} × {digits(String(row.quantity))}
            </span>
            <span className="min-w-0 text-muted">
              <span className="block truncate">{row.buyer_company ? `شركة: ${row.buyer_company}` : (row.shop_name ?? "—")}</span>
              {row.invoice_number ? <span className="block text-10.5" dir="ltr">{row.invoice_number}</span> : null}
              {row.payment_mode_at_issue ? (
                <span className="block text-10.5">
                  {CARD_SHOP_PAYMENT_MODE_LABEL[row.payment_mode_at_issue]} · خصم {digits(row.discount_percent_at_issue)}٪
                </span>
              ) : null}
            </span>
            <span className="text-muted">
              <span className="block">من {day(row.valid_from)}</span>
              <span className="block text-10.5">حتى {day(row.expires_at)}</span>
              <span className="block text-10.5">أُصدرت {day(row.created_at)}</span>
            </span>
            <span className={cn("font-semibold", row.status === "active" ? "text-ok" : "text-muted")}>
              {TAXO_CARD_BATCH_STATUS_LABEL[row.status]}
              <span className="block text-10.5 font-normal text-muted">
                غير مستعملة {digits(String(row.unused))} · مستعمَلة {digits(String(row.redeemed))} · منتهية{" "}
                {digits(String(row.expired))} · ملغاة {digits(String(row.cancelled))}
              </span>
              {row.cancel_reason ? <span className="block text-10.5 font-normal text-muted">{row.cancel_reason}</span> : null}
            </span>
            <span className="text-ink">
              <span className="block font-semibold">{digits(row.due_amount)}</span>
              <span className="block text-10.5 text-muted">
                استُعمل {digits(row.redeemed_amount)} من {digits(row.live_amount)} {row.currency}
              </span>
            </span>
            <span className="flex flex-col items-end gap-4">
              <button type="button" onClick={() => setOpened(row)} className="text-11.5 font-semibold text-accent">
                البطاقات
              </button>
              {row.invoice_number ? (
                <button
                  type="button"
                  onClick={() => downloadBatchInvoice(row.id).catch((caught) => onError(errorText(caught, "تعذّر تنزيلُ الفاتورة")))}
                  className="text-11.5 font-semibold text-ink"
                >
                  الفاتورة
                </button>
              ) : null}
              {isAdmin && row.status === "active" ? (
                <button type="button" onClick={() => setCancelling(row)} className="text-11.5 font-semibold text-danger">
                  إلغاء الدفعة
                </button>
              ) : null}
            </span>
          </>
        )}
      />
      {creating ? (
        <BatchModal
          country={country}
          onClose={() => setCreating(false)}
          onCreated={(body) => {
            setCreating(false);
            setCreated(body);
            void load();
          }}
        />
      ) : null}
      {created ? <CodesModal created={created} onClose={() => setCreated(null)} /> : null}
      {opened ? (
        <BatchCardsModal
          batch={opened}
          isAdmin={isAdmin}
          onClose={() => setOpened(null)}
          onChanged={(message) => {
            onDone(message);
            void load();
          }}
        />
      ) : null}
      {cancelling ? (
        <ReasonModal
          title={`إلغاء الدفعة #${cancelling.number}`}
          note="تُلغى كلُّ بطاقةٍ قائمةٍ فيها، والمستعمَلةُ تبقى مستعمَلة — مالُها في محفظة صاحبها."
          onClose={() => setCancelling(null)}
          onSubmit={async (reason) => {
            await cancelCardBatch(cancelling.id, reason);
            setCancelling(null);
            onDone("أُلغيت الدفعة");
            await load();
          }}
        />
      ) : null}
    </>
  );
}

function BatchModal({
  country,
  onClose,
  onCreated,
}: {
  country: CountryCode;
  onClose: () => void;
  onCreated: (body: CardBatchCreated) => void;
}) {
  const [denominations, setDenominations] = useState<CardDenomination[]>([]);
  const [shops, setShops] = useState<CardShop[]>([]);
  const [denominationId, setDenominationId] = useState("");
  const [shopId, setShopId] = useState("");
  const [quantity, setQuantity] = useState("");
  const [validFrom, setValidFrom] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [corporate, setCorporate] = useState(false);
  const [company, setCompany] = useState("");
  const [taxNumber, setTaxNumber] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([listCardDenominations(country), listCardShops(country)])
      .then(([denoms, shopRows]) => {
        const active = denoms.filter((row) => row.is_active);
        setDenominations(active);
        setShops(shopRows.filter((row) => row.is_active));
        setDenominationId((current) => current || active[0]?.id || "");
      })
      .catch((caught) => setError(errorText(caught, "تعذّر قراءة الفئات والمحلّات")));
  }, [country]);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      onCreated(
        await createCardBatch({
          country_code: country,
          denomination_id: denominationId,
          quantity: Number(quantity),
          shop_id: corporate ? null : shopId || null,
          valid_from: new Date(`${validFrom}T00:00:00`).toISOString(),
          expires_at: new Date(`${expiresAt}T23:59:59`).toISOString(),
          buyer_company: corporate ? company.trim() : null,
          buyer_tax_number: corporate ? taxNumber.trim() || null : null,
        }),
      );
    } catch (caught) {
      setError(errorText(caught, "تعذّر توليد الدفعة"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="دفعة بطاقات جديدة" onClose={onClose} wide>
      <div className="grid gap-12 sm:grid-cols-2">
        <Select label="الفئة" name="denomination_id" value={denominationId} onChange={(event) => setDenominationId(event.target.value)}>
          {denominations.length === 0 ? <option value="">لا فئةَ مفعَّلة — أضفها من «الفئات»</option> : null}
          {denominations.map((row) => (
            <option key={row.id} value={row.id}>
              {digits(row.amount)} {row.currency}
            </option>
          ))}
        </Select>
        <Field
          label="عدد البطاقات (حتى 5000)"
          name="quantity"
          dir="ltr"
          inputMode="numeric"
          value={quantity}
          onChange={(event) => setQuantity(event.target.value.replace(/\D/g, ""))}
        />
        {corporate ? (
          <Field label="اسمُ الشركة المشترية" name="buyer_company" value={company} onChange={(event) => setCompany(event.target.value)} />
        ) : (
          <Select label="المحلّ" name="shop_id" value={shopId} onChange={(event) => setShopId(event.target.value)}>
            <option value="">بلا محلّ (مكتب TAXO)</option>
            {shops.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name}
              </option>
            ))}
          </Select>
        )}
        {corporate ? (
          <Field
            label="الرقمُ الضريبيّ للشركة (اختياريّ)"
            name="buyer_tax_number"
            dir="ltr"
            value={taxNumber}
            onChange={(event) => setTaxNumber(event.target.value)}
          />
        ) : (
          <span />
        )}
        <span className="flex items-center gap-8 text-12 text-ink sm:col-span-2">
          <Switch checked={corporate} onChange={setCorporate} label="دفعةٌ لشركةٍ بفاتورة" />
          دفعةٌ لشركةٍ بفاتورة — تُعلَّم الدفعةُ بها ويُصدر لها رقمُ فاتورة
        </span>
        <DateInput label="تبدأ العمل في" name="valid_from" value={validFrom} onChange={setValidFrom} />
        <DateInput label="تنتهي صلاحيتها في" name="expires_at" value={expiresAt} onChange={setExpiresAt} />
      </div>
      <p className="mt-12 rounded-14 border border-warn bg-surface-2 px-14 py-12 text-12 leading-note text-ink">
        الرموزُ تظهر بعد التوليد مرّةً واحدة — احفظ ملفَّ الطباعة فوراً. لا تُخزَّن الرموزُ ولا يُعاد عرضُها.
      </p>
      <ErrorNote message={error} />
      <div className="mt-18 flex gap-10">
        <Button
          className="flex-1"
          size="md"
          loading={busy}
          disabled={!denominationId || Number(quantity) < 1 || !validFrom || !expiresAt || (corporate && company.trim().length < 2)}
          onClick={() => void submit()}
        >
          ولّد الدفعة
        </Button>
        <Button className="flex-1" size="md" variant="secondary" onClick={onClose}>
          تراجع
        </Button>
      </div>
    </Modal>
  );
}

const FILES: { format: "xlsx" | "pdf" | "sheet"; label: string }[] = [
  { format: "xlsx", label: "Excel" },
  { format: "pdf", label: "PDF للطباعة" },
  { format: "sheet", label: "ورقة المطبعة (QR)" },
];

/** **ملفّاتُ الدفعة** (SPEC §١٠٠-أ/١) — تُنزَّل **الآن وحدَه** بكلمة سرٍّ تكتبها هنا (لا تُحفظ ولا تُسجَّل)، **وتحفظها أنت**:
 *  الرموزُ لا تُستعاد بعد إغلاق هذه النافذة، ولا بابَ يعيدها. والخادمُ يرفض الملفَّ بعد ٣٠ دقيقةً من الإنشاء. */
function CodesModal({ created, onClose }: { created: CardBatchCreated; onClose: () => void }) {
  const [password, setPassword] = useState("");
  const [done, setDone] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const ready = password.length >= 8;

  async function download(format: "xlsx" | "pdf" | "sheet") {
    setBusy(format);
    setError(null);
    try {
      await exportCardBatch(created.batch.id, format, password, created.codes);
      setDone(new Set([...done, format]));
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : "تعذّر تنزيلُ الملفّ");
    } finally {
      setBusy(null);
    }
  }

  return (
    <Modal title={`ملفّات الدفعة #${created.batch.number}`} onClose={done.size ? onClose : () => undefined} wide>
      <p className="mb-12 rounded-14 border border-warn bg-surface-2 px-14 py-12 text-12 leading-note text-ink">
        هذه هي المرّةُ الوحيدةُ التي تُنزَّل فيها رموزُ الدفعة ({digits(String(created.codes.length))} بطاقة). اكتب كلمةَ سرٍّ للملفّات
        ونزّلها واحفظها — بعد إغلاق النافذة لا يعيدها أحد، ومن ضاعت ملفّاتُه يُلغي الدفعةَ ويُصدر غيرَها.
      </p>
      <label className="mb-6 block text-12 font-bold text-ink" htmlFor="batch-file-password">
        كلمة سرّ الملفّات (8 أحرف على الأقل)
      </label>
      <input
        id="batch-file-password"
        type="password"
        autoComplete="new-password"
        dir="ltr"
        className="mb-14 w-full rounded-10 border border-line bg-surface px-12 py-10 text-13 text-ink"
        value={password}
        onChange={(event) => setPassword(event.target.value)}
      />
      <div className="flex flex-wrap gap-10">
        {FILES.map((file) => (
          <Button
            key={file.format}
            className="flex-1"
            size="md"
            variant={done.has(file.format) ? "secondary" : "primary"}
            disabled={!ready || busy !== null}
            loading={busy === file.format}
            onClick={() => void download(file.format)}
          >
            {done.has(file.format) ? `✓ ${file.label}` : `نزّل ${file.label}`}
          </Button>
        ))}
      </div>
      {error ? <p className="mt-10 text-12 text-danger">{error}</p> : null}
      <Button className="mt-18 w-full" size="md" variant="secondary" disabled={!done.size} onClick={onClose}>
        حفظتُ الملفّات — أغلق
      </Button>
    </Modal>
  );
}

// ------------------------------------------------------------------ بطاقاتُ دفعة (SPEC §١٠٠-أ/٢)

const STATE_LABEL: Record<TaxoCardState, string> = {
  unused: "غير مستعملة",
  redeemed: "مستعمَلة",
  expired: "منتهية",
  cancelled: "ملغاة",
  not_started: "لم تبدأ بعد",
};
const MASKED = "••••-••••-••••-••••";

/** **بطاقاتُ الدفعة** — التسلسلُ والرمزُ محجوباً والحالُ ومن استعملها ومتى؛ **ولا زرَّ كشفٍ ولا إعادةَ تنزيل** (قرارُ المالك: البصمةُ
 *  وحدَها مخزَّنة). والإلغاءُ لبطاقةٍ قائمةٍ بسببٍ مكتوب. */
function BatchCardsModal({
  batch,
  isAdmin,
  onClose,
  onChanged,
}: {
  batch: CardBatch;
  isAdmin: boolean;
  onClose: () => void;
  onChanged: (message: string) => void;
}) {
  const search = useSearch();
  const [state, setState] = useState<TaxoCardState | "all">("all");
  const [rows, setRows] = useState<TaxoCardRow[] | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState<TaxoCardRow | null>(null);

  const load = useCallback(
    async (offset = 0) => {
      const page = await listBatchCards(batch.id, { q: search.term, state: state === "all" ? undefined : state, offset });
      setTotal(page.total);
      setRows((previous) => (offset === 0 ? page.cards : [...(previous ?? []), ...page.cards]));
    },
    [batch.id, search.term, state],
  );
  useEffect(() => {
    setRows(null);
    load().catch((caught) => setError(errorText(caught, "تعذّر قراءة البطاقات")));
  }, [load]);

  return (
    <Modal title={`بطاقات الدفعة #${digits(String(batch.number))}`} onClose={onClose} wide>
      <p className="mb-10 text-12 text-muted">
        {digits(batch.amount)} {batch.currency} × {digits(String(batch.quantity))} · الرموزُ لا تُعرض ولا تُنزَّل بعد الإنشاء — تُحفظ
        بصماتُها وحدَها.
      </p>
      <Pills
        value={state}
        onPick={(key) => setState(key)}
        options={[
          { key: "all", label: "الكل" },
          { key: "unused", label: "غير مستعملة" },
          { key: "redeemed", label: "مستعمَلة" },
          { key: "expired", label: "منتهية" },
          { key: "cancelled", label: "ملغاة" },
        ]}
      />
      <ErrorNote message={error} />
      <div className="mt-10">
        <Table
          height="compact"
          toolbar={<TableSearch value={search.text} onChange={search.setText} placeholder="التسلسل أو اسم من استعملها" />}
          searching={search.searching}
          columns="1.3fr 1.4fr 0.9fr 1.3fr 0.8fr"
          headers={["التسلسل", "الرمز", "الحال", "الاستعمال", ""]}
          rows={rows}
          keyOf={(row) => row.id}
          empty={{ title: "لا بطاقات", hint: "لا بطاقةَ بهذه الحال في الدفعة." }}
          noResults={{ title: "لا نتيجة", hint: "جرّب جزءاً من التسلسل أو من الاسم." }}
          render={(row) => (
            <>
              <span dir="ltr" className="text-start font-semibold text-ink">
                {row.serial}
              </span>
              <span dir="ltr" className="text-start text-muted">
                {MASKED}
              </span>
              <span className={cn("font-semibold", row.state === "unused" ? "text-ok" : "text-muted")}>
                {STATE_LABEL[row.state]}
                {row.cancel_reason ? <span className="block text-10.5 font-normal">{row.cancel_reason}</span> : null}
              </span>
              <span className="text-muted">
                {row.redeemed_at ? (
                  <>
                    <span className="block text-ink">{row.redeemed_by_name ?? "—"}</span>
                    <span className="block text-10.5">{day(row.redeemed_at)}</span>
                  </>
                ) : (
                  "—"
                )}
              </span>
              <span className="flex justify-end">
                {isAdmin && row.status === "active" ? (
                  <button type="button" onClick={() => setCancelling(row)} className="text-11.5 font-semibold text-danger">
                    إلغاء
                  </button>
                ) : null}
              </span>
            </>
          )}
        />
      </div>
      {rows && rows.length < total ? (
        <Button className="mt-10 w-full" size="md" variant="secondary" onClick={() => void load(rows.length)}>
          المزيد ({digits(String(total - rows.length))})
        </Button>
      ) : null}
      {cancelling ? (
        <ReasonModal
          title={`إلغاء البطاقة ${cancelling.serial}`}
          note="لا تشحن بعد الإلغاء، ولا تعود."
          onClose={() => setCancelling(null)}
          onSubmit={async (reason) => {
            await cancelTaxoCard(cancelling.id, reason);
            setCancelling(null);
            onChanged("أُلغيت البطاقة");
            await load();
          }}
        />
      ) : null}
    </Modal>
  );
}

/** **«دفعات البطاقات»** — بابٌ مستقلٌّ في القائمة الرئيسيّة (أمرُ المالك ٢٠٢٦-١١-١٣): الدفعاتُ بعدِّها، وبطاقاتُ كلِّ دفعة. */
export function CardBatchesScreen() {
  const { isAdmin } = useSession();
  const { country } = useCountry();
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  return (
    <Shell title="دفعات البطاقات" subtitle="كلُّ دفعةٍ بعدد بطاقاتها في كلِّ حال، وبطاقاتُها بالتسلسل ومن استعملها ومتى">
      <ErrorNote message={error} />
      <SuccessNote message={done} />
      <BatchesTab country={country} isAdmin={isAdmin} onError={setError} onDone={setDone} />
    </Shell>
  );
}

// ------------------------------------------------------------------ البطاقات

/** **من باع البطاقةَ ومتى** (§١٠٠-ب/٤) — المحلُّ ومن أصدرها ووقتُ إصدارها، ونوعُها إن لم تكن من دفعةٍ مطبوعة */
function origin(row: TaxoCardRow): string {
  const kind = row.batch_kind === "pos" ? "بيعٌ في المحلّ" : row.batch_kind === "gift" ? "هدية" : null;
  const parts = [kind, row.shop_name, row.issued_by_name, row.issued_at ? day(row.issued_at) : null].filter(Boolean);
  return parts.length ? parts.join(" · ") : "—";
}

function CardsTab({ country, isAdmin, onError, onDone }: TabProps) {
  const search = useSearch();
  const [rows, setRows] = useState<TaxoCardRow[] | null>([]);
  const [cancelling, setCancelling] = useState<TaxoCardRow | null>(null);

  const load = useCallback(async () => {
    const term = (search.term ?? "").trim();
    if (term.length < 3) {
      setRows([]);
      return;
    }
    setRows(await findTaxoCards(country, term));
  }, [country, search.term]);
  useEffect(() => {
    load().catch((caught) => onError(errorText(caught, "تعذّر البحث")));
  }, [load, onError]);

  return (
    <>
      <Table
        toolbar={<TableSearch value={search.text} onChange={search.setText} placeholder="الرقمُ التسلسليّ (ثلاثةُ أحرفٍ على الأقل)…" />}
        searching={search.searching}
        noResults={{ title: "لا بطاقة", hint: "ابحث بجزءٍ من الرقم التسلسليّ المطبوع — الرمزُ نفسُه لا يُبحث به." }}
        columns="1.3fr 0.8fr 1.3fr 1.3fr 0.6fr"
        headers={["الرقم التسلسليّ", "القيمة", "الدفعة ومن باعها", "الحال", ""]}
        rows={rows}
        keyOf={(row) => row.id}
        empty={{ title: "ابحث عن بطاقة", hint: "اكتب جزءاً من رقمها التسلسليّ — لإلغاء بطاقةٍ ضاعت أو معرفة من استعملها." }}
        render={(row) => (
          <>
            <span dir="ltr" className="text-start font-semibold text-ink">
              {row.serial}
            </span>
            <span className="text-ink">
              {digits(row.amount)} {row.currency}
            </span>
            <span className="text-muted">
              #{digits(String(row.batch_number))}
              <span className="block text-10.5">{origin(row)}</span>
            </span>
            <span className={cn("font-semibold", row.status === "active" ? "text-ok" : "text-muted")}>
              {TAXO_CARD_STATUS_LABEL[row.status]}
              {row.redeemed_at ? (
                <span className="block text-10.5 font-normal text-muted">
                  {row.redeemed_by_name ?? "—"} · {day(row.redeemed_at)}
                </span>
              ) : null}
              {row.cancel_reason ? <span className="block text-10.5 font-normal text-muted">{row.cancel_reason}</span> : null}
            </span>
            <span className="flex justify-end">
              {isAdmin && row.status === "active" ? (
                <button type="button" onClick={() => setCancelling(row)} className="text-11.5 font-semibold text-danger">
                  إلغاء
                </button>
              ) : null}
            </span>
          </>
        )}
      />
      {cancelling ? (
        <ReasonModal
          title={`إلغاء البطاقة ${cancelling.serial}`}
          note="البطاقةُ الملغاةُ لا تشحن — ولا يُعاد طبعُ رمزها."
          onClose={() => setCancelling(null)}
          onSubmit={async (reason) => {
            await cancelTaxoCard(cancelling.id, reason);
            setCancelling(null);
            onDone("أُلغيت البطاقة");
            await load();
          }}
        />
      ) : null}
    </>
  );
}

// ------------------------------------------------------------------ المحلّات

function ShopsTab({ country, isAdmin, onError, onDone }: TabProps) {
  const [rows, setRows] = useState<CardShop[] | null>(null);
  const [editing, setEditing] = useState<CardShop | "new" | null>(null);
  const load = useCallback(async () => setRows(await listCardShops(country)), [country]);
  useEffect(() => {
    load().catch((caught) => onError(errorText(caught, "تعذّر قراءة المحلّات")));
  }, [load, onError]);

  return (
    <>
      <Table
        toolbar={
          isAdmin ? (
            <Button size="md" onClick={() => setEditing("new")}>
              إضافة محلّ
            </Button>
          ) : undefined
        }
        columns="1.4fr 1fr 0.7fr 1.2fr 0.8fr 0.7fr"
        headers={["المحلّ", "الهاتف", "الخصم", "الدفع", "الحال", ""]}
        rows={rows}
        keyOf={(row) => row.id}
        empty={{ title: "لا محلّات بعد", hint: "أضف كلَّ محلٍّ يبيع البطاقات — بخصمه وطريقة دفعه لـTAXO." }}
        render={(row) => (
          <>
            <span className="min-w-0">
              <span className="block truncate font-semibold text-ink">{row.name}</span>
              {row.address ? <span className="block truncate text-10.5 text-muted">{row.address}</span> : null}
              {row.notes ? <span className="block truncate text-10.5 text-muted">{row.notes}</span> : null}
            </span>
            <span dir="ltr" className="text-start text-muted">
              {row.phone ?? "—"}
            </span>
            <span className="text-ink">{digits(row.discount_percent)}٪</span>
            <span className="text-muted">{CARD_SHOP_PAYMENT_MODE_LABEL[row.payment_mode]}</span>
            <span className={row.is_active ? "font-semibold text-ok" : "text-muted"}>{row.is_active ? "يبيع" : "موقوف"}</span>
            <span className="flex justify-end">
              {isAdmin ? (
                <button type="button" onClick={() => setEditing(row)} className="text-11.5 font-semibold text-ink">
                  تعديل
                </button>
              ) : null}
            </span>
          </>
        )}
      />
      {editing ? (
        <ShopModal
          country={country}
          shop={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onDone={(message) => {
            setEditing(null);
            onDone(message);
            void load();
          }}
        />
      ) : null}
    </>
  );
}

function ShopModal({
  country,
  shop,
  onClose,
  onDone,
}: {
  country: CountryCode;
  shop: CardShop | null;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [name, setName] = useState(shop?.name ?? "");
  const [phone, setPhone] = useState(shop?.phone ?? "");
  const [address, setAddress] = useState(shop?.address ?? "");
  const [discount, setDiscount] = useState(shop?.discount_percent ?? "");
  const [mode, setMode] = useState<CardShopPaymentMode>(shop?.payment_mode ?? "before_receipt");
  const [notes, setNotes] = useState(shop?.notes ?? "");
  const [active, setActive] = useState(shop?.is_active ?? true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    const body = {
      name: name.trim(),
      phone: phone.trim() || null,
      address: address.trim() || null,
      discount_percent: discount.trim(),
      payment_mode: mode,
      notes: notes.trim() || null,
    };
    try {
      if (shop) await updateCardShop(shop.id, { ...body, is_active: active });
      else await createCardShop(country, body);
      onDone(shop ? "حُفظ المحلّ — والدفعاتُ الصادرةُ بشروطها المجمَّدة" : "أُضيف المحلّ");
    } catch (caught) {
      setError(errorText(caught, "تعذّر الحفظ"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={shop ? `تعديل ${shop.name}` : "محلّ جديد"} onClose={onClose}>
      <div className="grid gap-12">
        <Field label="اسم المحلّ" name="name" value={name} onChange={(event) => setName(event.target.value)} />
        <Field label="الهاتف" name="phone" dir="ltr" value={phone} onChange={(event) => setPhone(event.target.value)} />
        <Field label="العنوان" name="address" value={address} onChange={(event) => setAddress(event.target.value)} />
        <Field
          label="خصم المحلّ (٪)"
          name="discount_percent"
          dir="ltr"
          inputMode="decimal"
          value={discount}
          onChange={(event) => setDiscount(event.target.value.replace(/[^0-9.]/g, ""))}
        />
        <Select label="متى يدفع لـTAXO" name="payment_mode" value={mode} onChange={(event) => setMode(event.target.value as CardShopPaymentMode)}>
          <option value="before_receipt">{CARD_SHOP_PAYMENT_MODE_LABEL.before_receipt}</option>
          <option value="after_sale">{CARD_SHOP_PAYMENT_MODE_LABEL.after_sale}</option>
        </Select>
        <Field label="ملاحظات" name="notes" value={notes} onChange={(event) => setNotes(event.target.value)} />
        {shop ? (
          <span className="flex items-center gap-8 text-12 text-ink">
            <Switch checked={active} onChange={setActive} label="يبيع البطاقات" />
            يبيع البطاقات
          </span>
        ) : null}
      </div>
      <ErrorNote message={error} />
      <div className="mt-18 flex gap-10">
        <Button className="flex-1" size="md" loading={busy} disabled={name.trim().length < 2 || discount.trim() === ""} onClick={() => void submit()}>
          حفظ
        </Button>
        <Button className="flex-1" size="md" variant="secondary" onClick={onClose}>
          تراجع
        </Button>
      </div>
    </Modal>
  );
}

// ------------------------------------------------------------------ الفئات

function DenominationsTab({
  country,
  currency,
  isAdmin,
  onError,
  onDone,
}: TabProps & { currency: string | undefined }) {
  const [rows, setRows] = useState<CardDenomination[] | null>(null);
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => setRows(await listCardDenominations(country)), [country]);
  useEffect(() => {
    load().catch((caught) => onError(errorText(caught, "تعذّر قراءة الفئات")));
  }, [load, onError]);

  async function add() {
    setBusy(true);
    try {
      await addCardDenomination(country, amount.trim());
      setAmount("");
      onDone("أُضيفت الفئة");
      await load();
    } catch (caught) {
      onError(errorText(caught, "تعذّر إضافة الفئة"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {isAdmin ? (
        <div className="mb-12 flex flex-wrap items-end gap-10">
          <MoneyField label="قيمة فئةٍ جديدة" name="amount" value={amount} onChange={setAmount} currency={currency} />
          <Button size="md" loading={busy} disabled={Number(amount) <= 0} onClick={() => void add()}>
            أضف الفئة
          </Button>
        </div>
      ) : null}
      <Table
        columns="1fr 1fr"
        headers={["الفئة", "تُصدر منها دفعات"]}
        rows={rows}
        keyOf={(row) => row.id}
        empty={{ title: "لا فئات بعد", hint: "الفئاتُ قيمٌ ثابتةٌ تضعها أنت — لا تُبذر ولا تُقترح." }}
        render={(row) => (
          <>
            <span className="font-semibold text-ink">
              {digits(row.amount)} {row.currency}
            </span>
            <span>
              <Switch
                checked={row.is_active}
                disabled={!isAdmin}
                label={`الفئة ${row.amount} مفعَّلة`}
                onChange={(next) => {
                  setCardDenominationActive(row.id, next)
                    .then(load)
                    .catch((caught) => onError(errorText(caught, "تعذّر الحفظ")));
                }}
              />
            </span>
          </>
        )}
      />
    </>
  );
}

// ------------------------------------------------------------------ التقرير

function ShopReport({ country, onError }: { country: CountryCode; onError: (message: string | null) => void }) {
  const [rows, setRows] = useState<CardShopReport[] | null>(null);
  useEffect(() => {
    cardShopReport(country)
      .then(setRows)
      .catch((caught) => onError(errorText(caught, "تعذّر قراءة التقرير")));
  }, [country, onError]);
  return (
    <Table
      columns="1.4fr 0.8fr 1.4fr 1.2fr 1fr"
      headers={["المحلّ", "الدفعات", "البطاقات", "القيمة", "المستحقّ منه"]}
      rows={rows}
      keyOf={(row) => row.shop_id}
      empty={{ title: "لا تقرير بعد", hint: "يظهر هنا لكلِّ محلٍّ ما سُلِّم له وما استُعمل وما يستحقّ عليه بشرطه." }}
      render={(row) => (
        <>
          <span className="font-semibold text-ink">{row.shop_name}</span>
          <span className="text-muted">{digits(String(row.batches))}</span>
          <span className="text-muted">
            {digits(String(row.cards))} · مستعمَلة {digits(String(row.redeemed))} · ملغاة {digits(String(row.cancelled))}
          </span>
          <span className="text-muted">
            <span className="block">استُعمل {digits(row.redeemed_amount)}</span>
            <span className="block text-10.5">سُلِّم {digits(row.live_amount)}</span>
          </span>
          <span className="font-semibold text-ink">
            {digits(row.due_amount)} {row.currency}
          </span>
        </>
      )}
    />
  );
}

// ------------------------------------------------------------------ التخمين

function AlertsTab({ country, isAdmin, onError, onDone }: TabProps) {
  const [rows, setRows] = useState<CardGuessAlert[] | null>(null);
  const [limits, setLimits] = useState<TaxoCardLimits | null>(null);
  const [account, setAccount] = useState("");
  const [ip, setIp] = useState("");
  const [windowMinutes, setWindowMinutes] = useState("");

  const load = useCallback(async () => {
    const [alertRows, current] = await Promise.all([listCardAlerts(country), getCardLimits(country)]);
    setRows(alertRows);
    setLimits(current);
    setAccount(String(current.max_wrong_per_account));
    setIp(String(current.max_wrong_per_ip));
    setWindowMinutes(String(current.window_minutes));
  }, [country]);
  useEffect(() => {
    load().catch((caught) => onError(errorText(caught, "تعذّر قراءة التنبيهات")));
  }, [load, onError]);

  async function save() {
    try {
      await saveCardLimits(country, {
        max_wrong_per_account: Number(account),
        max_wrong_per_ip: Number(ip),
        window_minutes: Number(windowMinutes),
      });
      onDone("حُفظت سقوفُ التخمين");
      await load();
    } catch (caught) {
      onError(errorText(caught, "تعذّر الحفظ"));
    }
  }

  return (
    <>
      {limits ? (
        <div className="mb-12 grid gap-12 sm:grid-cols-4 sm:items-end">
          <Field label="خطأٌ لكلِّ حساب" name="max_wrong_per_account" dir="ltr" inputMode="numeric" value={account} disabled={!isAdmin}
            onChange={(event) => setAccount(event.target.value.replace(/\D/g, ""))} />
          <Field label="خطأٌ لكلِّ عنوان IP" name="max_wrong_per_ip" dir="ltr" inputMode="numeric" value={ip} disabled={!isAdmin}
            onChange={(event) => setIp(event.target.value.replace(/\D/g, ""))} />
          <Field label="خلال (دقيقة)" name="window_minutes" dir="ltr" inputMode="numeric" value={windowMinutes} disabled={!isAdmin}
            onChange={(event) => setWindowMinutes(event.target.value.replace(/\D/g, ""))} />
          {isAdmin ? (
            <Button size="md" disabled={!Number(account) || !Number(ip) || !Number(windowMinutes)} onClick={() => void save()}>
              حفظ السقوف
            </Button>
          ) : null}
        </div>
      ) : null}
      <Table
        columns="0.8fr 1.4fr 1fr 0.7fr 1fr 0.8fr"
        headers={["النوع", "الحساب", "العنوان", "المحاولات", "متى", ""]}
        rows={rows}
        keyOf={(row) => row.id}
        empty={{ title: "لا تنبيهات", hint: "يظهر هنا كلُّ حسابٍ أو عنوانٍ بلغ سقفَ الرموز الخاطئة — ويُوقف حتى تنقضي النافذة." }}
        render={(row) => (
          <>
            <span className="text-ink">{row.scope === "account" ? "حساب" : "عنوان IP"}</span>
            <span className="min-w-0 text-muted">
              <span className="block truncate">{row.user_name ?? "—"}</span>
              <span dir="ltr" className="block text-10.5">
                {row.user_phone ?? ""}
              </span>
            </span>
            <span dir="ltr" className="text-start text-muted">
              {row.ip ?? "—"}
            </span>
            <span className="font-semibold text-danger">{digits(String(row.attempts))}</span>
            <span className="text-muted">{day(row.created_at)}</span>
            <span className="flex justify-end">
              {row.reviewed_at ? (
                <span className="text-11 text-muted">رُوجع {day(row.reviewed_at)}</span>
              ) : isAdmin ? (
                <button
                  type="button"
                  onClick={() => {
                    reviewCardAlert(row.id)
                      .then(load)
                      .catch((caught) => onError(errorText(caught, "تعذّر الحفظ")));
                  }}
                  className="text-11.5 font-semibold text-ink"
                >
                  رُوجع
                </button>
              ) : null}
            </span>
          </>
        )}
      />
    </>
  );
}

// ------------------------------------------------------------------ سببٌ مكتوب

function ReasonModal({
  title,
  note,
  onClose,
  onSubmit,
}: {
  title: string;
  note: string;
  onClose: () => void;
  onSubmit: (reason: string) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <Modal title={title} onClose={onClose}>
      <p className="mb-12 text-12 leading-note text-muted">{note}</p>
      <Field label="السبب — يُكتب في السجلّ" name="reason" value={reason} onChange={(event) => setReason(event.target.value)} />
      <ErrorNote message={error} />
      <div className="mt-18 flex gap-10">
        <Button
          className="flex-1"
          size="md"
          loading={busy}
          disabled={reason.trim().length < 3}
          onClick={() => {
            setBusy(true);
            setError(null);
            onSubmit(reason.trim())
              .catch((caught) => setError(errorText(caught, "تعذّر التنفيذ")))
              .finally(() => setBusy(false));
          }}
        >
          إلغاء
        </Button>
        <Button className="flex-1" size="md" variant="secondary" onClick={onClose}>
          تراجع
        </Button>
      </div>
    </Modal>
  );
}

// ------------------------------------------------------------------ بطاقاتُ الهدية (SPEC §١٠٠-أ/٣)

const GIFT_STATE_LABEL: Record<GiftState, string> = {
  created: "أُنشئت",
  sent: "أُرسلت",
  opened: "فُتحت",
  scratched: "كُشطت",
  redeemed: "استُعملت",
  expired: "انتهت",
  cancelled: "أُلغيت",
  printed: "مطبوعة",
};

const GIFT_DESIGNS: { key: GiftDesign; label: string; preview: string }[] = [
  { key: "night", label: "ليل", preview: "radial-gradient(120% 90% at 85% 10%, rgba(242,107,33,.6), transparent 55%), #14181d" },
  { key: "sunrise", label: "شروق", preview: "linear-gradient(135deg, #F26B21 0%, #FF8A3D 55%, #FFB36B 100%)" },
  { key: "city", label: "مدينة", preview: "linear-gradient(115deg, transparent 40%, #F26B21 40.3%, #F26B21 41.5%, transparent 41.8%), #faf6f0" },
];

const CHANNELS: { key: GiftChannel; label: string }[] = [
  { key: "whatsapp", label: "واتساب" },
  { key: "sms", label: "رسالة SMS" },
  { key: "email", label: "بريد" },
];

function shareHref(channel: GiftChannel, url: string): string {
  const text = `هديةٌ لك من TAXO — افتح الرابط واكشط البطاقة: ${url}`;
  if (channel === "whatsapp") return `https://wa.me/?text=${encodeURIComponent(text)}`;
  if (channel === "sms") return `sms:?&body=${encodeURIComponent(text)}`;
  return `mailto:?subject=${encodeURIComponent("بطاقة هدية من TAXO")}&body=${encodeURIComponent(text)}`;
}

/** **بطاقاتُ الهدية** — رابطٌ خاصٌّ يُكشط مرّةً، أو نسخةٌ مطبوعةٌ بمنطقة كشط. **والحالُ بأوقاتها**: أُرسلت، فُتحت، كُشطت، استُعملت.
 *  **ولا رمزَ ولا رابطَ في القائمة**: الرابطُ يظهر مرّةً لحظةَ الإنشاء، والرمزُ يُخزَّن معمًّى حتى يُكشط ثمّ يُمحى. */
function GiftsTab({ country, isAdmin, onError, onDone }: TabProps) {
  const [rows, setRows] = useState<GiftLink[] | null>(null);
  const [creating, setCreating] = useState(false);
  const [created, setCreated] = useState<GiftCreated | null>(null);
  const [cancelling, setCancelling] = useState<GiftLink | null>(null);

  const load = useCallback(async () => setRows(await listGifts(country)), [country]);
  useEffect(() => {
    load().catch((caught) => onError(errorText(caught, "تعذّر قراءة الهدايا")));
  }, [load, onError]);

  return (
    <>
      <Table
        toolbar={
          isAdmin ? (
            <Button size="md" onClick={() => setCreating(true)}>
              هدية جديدة
            </Button>
          ) : undefined
        }
        columns="1.1fr 0.8fr 0.8fr 1.1fr 1.6fr 0.8fr"
        headers={["البطاقة", "القيمة", "التصميم", "إلى", "الحال", ""]}
        rows={rows}
        keyOf={(row) => row.id}
        empty={{ title: "لا هدايا بعد", hint: "أنشئ هديةً من فئةٍ مفعَّلة، وأرسل رابطَها بواتساب أو رسالةٍ أو بريد." }}
        render={(row) => (
          <>
            <span className="min-w-0">
              <span className="block truncate font-semibold text-ink" dir="ltr">
                {row.serial}
              </span>
              <span className="block text-10.5 text-muted">أُنشئت {day(row.created_at)}</span>
            </span>
            <span className="text-ink">
              {digits(row.amount)} {row.currency}
            </span>
            <span className="text-muted">{GIFT_DESIGNS.find((d) => d.key === row.design)?.label ?? row.design}</span>
            <span className="min-w-0 text-muted">
              <span className="block truncate">{row.recipient_name ?? "—"}</span>
              {row.message ? <span className="block truncate text-10.5">{row.message}</span> : null}
            </span>
            <span className={cn("font-semibold", row.state === "redeemed" ? "text-ok" : row.state === "cancelled" ? "text-muted" : "text-ink")}>
              {GIFT_STATE_LABEL[row.state]}
              <span className="block text-10.5 font-normal text-muted">
                {row.sent_at ? `أُرسلت ${day(row.sent_at)}` : "لم تُرسل"}
                {row.opened_at ? ` · فُتحت ${digits(String(row.open_count))}×` : ""}
                {row.scratched_at ? ` · كُشطت ${day(row.scratched_at)}` : ""}
                {row.redeemed_at ? ` · استُعملت ${day(row.redeemed_at)}` : ""}
              </span>
              <span className="block text-10.5 font-normal text-muted">تنتهي {day(row.expires_at)}</span>
              {row.cancel_reason ? <span className="block text-10.5 font-normal text-muted">{row.cancel_reason}</span> : null}
            </span>
            <span className="flex flex-col items-end gap-4">
              {isAdmin && row.state !== "cancelled" && row.state !== "redeemed" ? (
                <button type="button" onClick={() => setCancelling(row)} className="text-11.5 font-semibold text-danger">
                  إلغاء الهدية
                </button>
              ) : null}
            </span>
          </>
        )}
      />
      {creating ? (
        <GiftModal
          country={country}
          onClose={() => setCreating(false)}
          onCreated={(body) => {
            setCreating(false);
            setCreated(body);
            void load();
          }}
        />
      ) : null}
      {created ? (
        <GiftCreatedModal
          created={created}
          onSent={() => void load()}
          onClose={() => {
            setCreated(null);
            void load();
          }}
        />
      ) : null}
      {cancelling ? (
        <ReasonModal
          title={`إلغاء الهدية ${cancelling.serial}`}
          note="يُلغى الرابطُ وبطاقتُه، ويُمحى الرمزُ المعمّى. من يفتح الرابطَ بعدها يرى «أُلغيت هذه البطاقة»."
          onClose={() => setCancelling(null)}
          onSubmit={async (reason) => {
            await cancelGift(cancelling.id, reason);
            setCancelling(null);
            onDone("أُلغيت الهدية");
            await load();
          }}
        />
      ) : null}
    </>
  );
}

function inAYear(): string {
  const date = new Date();
  date.setFullYear(date.getFullYear() + 1);
  return date.toISOString().slice(0, 10);
}

function GiftModal({
  country,
  onClose,
  onCreated,
}: {
  country: CountryCode;
  onClose: () => void;
  onCreated: (body: GiftCreated) => void;
}) {
  const [denominations, setDenominations] = useState<CardDenomination[]>([]);
  const [denominationId, setDenominationId] = useState("");
  const [design, setDesign] = useState<GiftDesign>("night");
  const [delivery, setDelivery] = useState<"link" | "print">("link");
  const [recipient, setRecipient] = useState("");
  const [message, setMessage] = useState("");
  const [expiresAt, setExpiresAt] = useState(inAYear());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listCardDenominations(country)
      .then((rows) => {
        const active = rows.filter((row) => row.is_active);
        setDenominations(active);
        setDenominationId((current) => current || active[0]?.id || "");
      })
      .catch((caught) => setError(errorText(caught, "تعذّر قراءة الفئات")));
  }, [country]);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      onCreated(
        await createGift({
          country_code: country,
          denomination_id: denominationId,
          design,
          delivery,
          expires_at: new Date(`${expiresAt}T23:59:59`).toISOString(),
          recipient_name: recipient.trim() || null,
          message: message.trim() || null,
        }),
      );
    } catch (caught) {
      setError(errorText(caught, "تعذّر إنشاء الهدية"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="بطاقة هدية جديدة" onClose={onClose} wide>
      <div className="grid gap-12 sm:grid-cols-2">
        <Select label="الفئة" name="denomination_id" value={denominationId} onChange={(event) => setDenominationId(event.target.value)}>
          {denominations.length === 0 ? <option value="">لا فئةَ مفعَّلة — أضفها من «الفئات»</option> : null}
          {denominations.map((row) => (
            <option key={row.id} value={row.id}>
              {digits(row.amount)} {row.currency}
            </option>
          ))}
        </Select>
        <Select
          label="طريقة التسليم"
          name="delivery"
          value={delivery}
          onChange={(event) => setDelivery(event.target.value as "link" | "print")}
        >
          <option value="link">رابطٌ خاصّ يُكشط (واتساب · SMS · بريد)</option>
          <option value="print">نسخةٌ مطبوعة بمنطقة كشط</option>
        </Select>
        <Field label="اسم المُهدى إليه (اختياريّ)" name="recipient_name" value={recipient} maxLength={80} onChange={(event) => setRecipient(event.target.value)} />
        <DateInput label="تنتهي صلاحيتها في" name="expires_at" value={expiresAt} onChange={setExpiresAt} />
      </div>
      <Field label="رسالة قصيرة (اختياريّة)" name="message" value={message} maxLength={200} onChange={(event) => setMessage(event.target.value)} />
      <p className="mb-8 mt-14 text-12 font-bold text-ink">التصميم</p>
      <div className="grid grid-cols-3 gap-10">
        {GIFT_DESIGNS.map((option) => (
          <button
            key={option.key}
            type="button"
            onClick={() => setDesign(option.key)}
            className={cn(
              "flex flex-col items-center gap-6 rounded-14 border p-8 text-12 font-semibold",
              design === option.key ? "border-accent text-ink" : "border-line text-muted",
            )}
          >
            <span className="block h-[54px] w-full rounded-10" style={{ background: option.preview }} />
            {option.label}
          </button>
        ))}
      </div>
      <p className="mt-12 rounded-14 border border-warn bg-surface-2 px-14 py-12 text-12 leading-note text-ink">
        {delivery === "link"
          ? "الرابطُ يظهر بعد الإنشاء مرّةً واحدة: أرسله فوراً. الرمزُ يُخزَّن معمًّى حتى يُكشط ثمّ يُمحى، ولا يراه أحدٌ قبل صاحبه."
          : "الرمزُ يظهر مرّةً واحدة في ملفّ الطباعة: نزّله فوراً. لا يُخزَّن الرمز."}
      </p>
      <ErrorNote message={error} />
      <div className="mt-18 flex gap-10">
        <Button className="flex-1" size="md" loading={busy} disabled={!denominationId || !expiresAt} onClick={() => void submit()}>
          أنشئ الهدية
        </Button>
        <Button className="flex-1" size="md" variant="secondary" onClick={onClose}>
          تراجع
        </Button>
      </div>
    </Modal>
  );
}

/** **الرابطُ أو ملفُّ الطباعة مرّةً واحدة** — بعد الإغلاق لا يعيدهما أحد؛ ومن ضاع رابطُه يُلغي الهديةَ ويُنشئ غيرَها. */
function GiftCreatedModal({ created, onSent, onClose }: { created: GiftCreated; onSent: () => void; onClose: () => void }) {
  const [sent, setSent] = useState<Set<GiftChannel>>(new Set());
  const [password, setPassword] = useState("");
  const [printed, setPrinted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const url = created.url;

  async function record(channel: GiftChannel) {
    if (!created.gift) return;
    try {
      await markGiftSent(created.gift.id, channel);
      setSent(new Set([...sent, channel]));
      onSent();
    } catch (caught) {
      setError(errorText(caught, "تعذّر تسجيلُ الإرسال"));
    }
  }

  async function copy() {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      await record("copy");
    } catch {
      setError("تعذّر النسخ — حدِّد الرابطَ وانسخه بيدك");
    }
  }

  async function print() {
    if (!created.code) return;
    setBusy(true);
    setError(null);
    try {
      await exportCardBatch(created.batch_id, "gift", password, [created.code], created.gift?.design ?? "night");
      setPrinted(true);
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : "تعذّر تنزيلُ الملفّ");
    } finally {
      setBusy(false);
    }
  }

  const finished = url ? sent.size > 0 : printed;
  return (
    <Modal title={`الهدية ${created.serial}`} onClose={finished ? onClose : () => undefined} wide>
      {url ? (
        <>
          <p className="mb-12 rounded-14 border border-warn bg-surface-2 px-14 py-12 text-12 leading-note text-ink">
            هذه هي المرّةُ الوحيدةُ التي يظهر فيها الرابط. أرسله الآن. بعد إغلاق النافذة لا يعيده أحد.
          </p>
          <div className="mb-12 break-all rounded-10 border border-line bg-surface px-12 py-10 text-12 text-ink" dir="ltr">
            {url}
          </div>
          <div className="flex flex-wrap gap-10">
            {CHANNELS.map((channel) => (
              <a
                key={channel.key}
                href={shareHref(channel.key, url)}
                target="_blank"
                rel="noreferrer"
                onClick={() => void record(channel.key)}
                className={cn(
                  "flex min-h-[44px] flex-1 items-center justify-center rounded-12 px-12 text-13 font-semibold",
                  sent.has(channel.key) ? "bg-surface-2 text-muted" : "bg-accent text-white",
                )}
              >
                {sent.has(channel.key) ? `✓ ${channel.label}` : `أرسل ب${channel.label}`}
              </a>
            ))}
            <Button className="flex-1" size="md" variant="secondary" onClick={() => void copy()}>
              {sent.has("copy") ? "✓ نُسخ الرابط" : "انسخ الرابط"}
            </Button>
          </div>
        </>
      ) : (
        <>
          <p className="mb-12 rounded-14 border border-warn bg-surface-2 px-14 py-12 text-12 leading-note text-ink">
            هذه هي المرّةُ الوحيدةُ التي يُنزَّل فيها ملفُّ الهدية. اكتب كلمةَ سرٍّ ونزّله واحفظه.
          </p>
          <label className="mb-6 block text-12 font-bold text-ink" htmlFor="gift-file-password">
            كلمة سرّ الملفّ (8 أحرف على الأقل)
          </label>
          <input
            id="gift-file-password"
            type="password"
            autoComplete="new-password"
            dir="ltr"
            className="mb-14 w-full rounded-10 border border-line bg-surface px-12 py-10 text-13 text-ink"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <Button className="w-full" size="md" disabled={password.length < 8 || busy} loading={busy} onClick={() => void print()}>
            {printed ? "✓ نُزّل ملفُّ الطباعة" : "نزّل ملفَّ الطباعة (PDF بمنطقة كشط)"}
          </Button>
        </>
      )}
      {error ? <p className="mt-10 text-12 text-danger">{error}</p> : null}
      <Button className="mt-18 w-full" size="md" variant="secondary" disabled={!finished} onClick={onClose}>
        {url ? "أرسلتُ الرابط — أغلق" : "حفظتُ الملفّ — أغلق"}
      </Button>
    </Modal>
  );
}

// ------------------------------------------------------------------ البائعون والبيعُ لحظةَ الطلب (SPEC §١٠٠-ب/٤–٥)

/** **البائعون في المحلّات** — حساباتٌ ينشئها المالك، ومبيعاتُ كلٍّ منهم، **ومفتاحُ البيع للمالك وحدَه**. */
function SellersTab({ country, onError, onDone }: TabProps) {
  const { user } = useSession();
  const isOwner = Boolean(user?.roles?.includes("owner"));
  const [rows, setRows] = useState<CardSeller[] | null>(null);
  const [pos, setPos] = useState<PosSettings | null>(null);
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [cap, setCap] = useState("");
  const [validity, setValidity] = useState("");

  const load = useCallback(async () => {
    const [sellers, settings] = await Promise.all([listCardSellers(country), getPosSettings(country)]);
    setRows(sellers);
    setPos(settings);
    setCap(String(settings.pos_daily_cap));
    setValidity(String(settings.pos_validity_days));
  }, [country]);
  useEffect(() => {
    load().catch((caught) => onError(errorText(caught, "تعذّر قراءة البائعين")));
  }, [load, onError]);

  async function save(changes: Partial<Omit<PosSettings, never>>, message: string) {
    setBusy(true);
    try {
      setPos(await savePosSettings(country, changes));
      onDone(message);
    } catch (caught) {
      onError(errorText(caught, "تعذّر الحفظ"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="mb-14 rounded-card border border-line bg-surface p-14">
        <div className="flex flex-wrap items-center gap-10">
          <span className="text-13 font-semibold text-ink">البيعُ في المحلّات لحظةَ الطلب</span>
          <span className={cn("text-12 font-semibold", pos?.pos_enabled ? "text-ok" : "text-muted")}>
            {pos ? (pos.pos_enabled ? "مفتوح" : "مطفأ") : "…"}
          </span>
          {isOwner && pos ? (
            <Button
              size="sm"
              variant={pos.pos_enabled ? "secondary" : "primary"}
              loading={busy}
              onClick={() => void save({ pos_enabled: !pos.pos_enabled }, pos.pos_enabled ? "أُطفئ البيعُ في المحلّات" : "فُتح البيعُ في المحلّات")}
            >
              {pos.pos_enabled ? "إطفاء" : "فتح البيع"}
            </Button>
          ) : null}
        </div>
        <p className="mt-6 text-11.5 text-muted">
          كلُّ بيعٍ يولّد بطاقةً واحدةً باسم محلّ البائع، ورمزُها يظهر في الإيصال مرّةً ولا يُخزَّن. ورصيدُ المحلّ وحدُّ ائتمانه
          وعمولتُه وتسويتُه تنتظر قيمَ المالك — وما يستحقّه المحلُّ يُقرأ في «التقرير» بخصمه المجمَّد.
        </p>
        {isOwner && pos ? (
          <div className="mt-10 flex flex-wrap items-end gap-10">
            <Field
              label="سقفُ البيع لكلِّ بائعٍ في 24 ساعة (بطاقات)"
              name="pos_daily_cap"
              dir="ltr"
              inputMode="numeric"
              value={cap}
              onChange={(event) => setCap(event.target.value.replace(/[^0-9]/g, ""))}
            />
            <Field
              label="صلاحيةُ البطاقة المبيعة (أيام)"
              name="pos_validity_days"
              dir="ltr"
              inputMode="numeric"
              value={validity}
              onChange={(event) => setValidity(event.target.value.replace(/[^0-9]/g, ""))}
            />
            <Button
              size="md"
              variant="secondary"
              loading={busy}
              disabled={!cap || !validity}
              onClick={() => void save({ pos_daily_cap: Number(cap), pos_validity_days: Number(validity) }, "حُفظ السقفُ والصلاحية")}
            >
              حفظ
            </Button>
          </div>
        ) : null}
      </div>
      <Table
        toolbar={
          isOwner ? (
            <Button size="md" onClick={() => setCreating(true)}>
              حسابُ بائع
            </Button>
          ) : undefined
        }
        columns="1.3fr 1.1fr 0.9fr 0.7fr 0.9fr 0.7fr"
        headers={["البائع", "المحلّ", "المبيع", "المستعمَل", "الحساب", ""]}
        rows={rows}
        keyOf={(row) => row.id}
        empty={{ title: "لا بائعين بعد", hint: "ينشئ المالكُ حسابَ بائعٍ لكلِّ محلّ — يدخل اللوحةَ من هاتفه ويرى صفحةَ البيع وحدَها." }}
        render={(row) => (
          <>
            <span className="min-w-0">
              <span className="block truncate font-semibold text-ink">{row.name}</span>
              <span dir="ltr" className="block truncate text-start text-10.5 text-muted">
                {row.username ?? "—"}
              </span>
            </span>
            <span className="truncate text-ink">{row.shop_name}</span>
            <span className="text-ink">
              {digits(String(row.sold))}
              <span className="block text-10.5 text-muted">
                {digits(row.sold_amount)} {row.currency}
              </span>
            </span>
            <span className="text-muted">{digits(String(row.redeemed))}</span>
            <span className={cn("text-11.5", row.is_active && !row.is_blocked ? "font-semibold text-ok" : "text-muted")}>
              {!row.is_active ? "موقوف" : row.is_blocked ? "محظور" : "يبيع"}
              <span className="block text-10.5 font-normal text-muted">
                {row.has_factor ? "العاملُ الثاني مسجَّل" : "لم يسجّل العاملَ الثاني"}
              </span>
            </span>
            <span className="flex justify-end">
              {isOwner ? (
                <button
                  type="button"
                  className={cn("text-11.5 font-semibold", row.is_active ? "text-danger" : "text-ink")}
                  onClick={async () => {
                    try {
                      await setCardSellerActive(row.id, !row.is_active);
                      onDone(row.is_active ? "أُوقف البائع" : "أُعيد البائع");
                      await load();
                    } catch (caught) {
                      onError(errorText(caught, "تعذّر الحفظ"));
                    }
                  }}
                >
                  {row.is_active ? "إيقاف" : "إعادة"}
                </button>
              ) : null}
            </span>
          </>
        )}
      />
      {creating ? (
        <SellerModal
          country={country}
          onClose={() => setCreating(false)}
          onDone={(message) => {
            setCreating(false);
            onDone(message);
            void load();
          }}
        />
      ) : null}
    </>
  );
}

function SellerModal({
  country,
  onClose,
  onDone,
}: {
  country: CountryCode;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [shops, setShops] = useState<CardShop[]>([]);
  const [shopId, setShopId] = useState("");
  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listCardShops(country)
      .then((rows) => {
        const live = rows.filter((row) => row.is_active);
        setShops(live);
        if (live[0]) setShopId(live[0].id);
      })
      .catch((caught) => setError(errorText(caught, "تعذّر قراءة المحلّات")));
  }, [country]);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await createCardSeller({ shop_id: shopId, name: name.trim(), username: username.trim(), password });
      onDone("أُنشئ حسابُ البائع — يغيّر كلمتَه ويسجّل العاملَ الثاني عند أوّل دخول");
    } catch (caught) {
      setError(errorText(caught, "تعذّر الإنشاء"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="حسابُ بائعٍ جديد" onClose={onClose}>
      <div className="grid gap-12">
        <Select label="المحلّ" name="shop_id" value={shopId} onChange={(event) => setShopId(event.target.value)}>
          {shops.map((shop) => (
            <option key={shop.id} value={shop.id}>
              {shop.name}
            </option>
          ))}
        </Select>
        <Field label="اسمُ البائع" name="name" value={name} onChange={(event) => setName(event.target.value)} />
        <Field label="اسمُ الدخول" name="username" dir="ltr" value={username} onChange={(event) => setUsername(event.target.value)} />
        <Field
          label="كلمةٌ مؤقّتة (تتغيّر عند أوّل دخول)"
          name="password"
          type="password"
          dir="ltr"
          autoComplete="new-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <p className="text-11.5 text-muted">
          يدخل البائعُ اللوحةَ من هاتفه أو حاسوبه، ويرى صفحةَ البيع وحدَها. والعاملُ الثاني إلزاميٌّ له قبل أيِّ بيع.
        </p>
      </div>
      <ErrorNote message={error} />
      <div className="mt-18 flex gap-10">
        <Button
          className="flex-1"
          size="md"
          loading={busy}
          disabled={!shopId || name.trim().length < 2 || username.trim().length < 3 || password.length < 8}
          onClick={() => void submit()}
        >
          إنشاء
        </Button>
        <Button className="flex-1" size="md" variant="secondary" onClick={onClose}>
          تراجع
        </Button>
      </div>
    </Modal>
  );
}

// ------------------------------------------------------------------ التقريرُ بالنوع والصلاحية (SPEC §١٠٠-ب/١٢ و١٤)

const KIND_LABEL: Record<CardKindReport["kind"], string> = {
  batch: "مطبوعة",
  gift: "هدايا",
  pos: "بيعٌ في المحلّات",
  corporate: "للشركات (من المطبوعة)",
};

function ReportTab({ country, isAdmin, onError, onDone }: TabProps) {
  return (
    <div className="grid gap-18">
      <KindSummary country={country} onError={onError} />
      <ExpiringBatches country={country} isAdmin={isAdmin} onError={onError} onDone={onDone} />
      <div>
        <p className="mb-8 text-13 font-semibold text-ink">المحلّات</p>
        <ShopReport country={country} onError={onError} />
      </div>
      <InvoiceSellerCard country={country} onError={onError} onDone={onDone} />
    </div>
  );
}

/** **ما صدر وما استُعمل، والالتزامُ القائم، وقيمةُ المنتهية بلا استعمال** — من الخلفية بالنوع */
function KindSummary({ country, onError }: { country: CountryCode; onError: (message: string | null) => void }) {
  const [rows, setRows] = useState<CardKindReport[] | null>(null);
  useEffect(() => {
    cardKindReport(country)
      .then(setRows)
      .catch((caught) => onError(errorText(caught, "تعذّر قراءة التقرير")));
  }, [country, onError]);
  return (
    <Table
      columns="1.2fr 0.9fr 1fr 1.2fr 1.2fr 1.1fr"
      headers={["النوع", "البطاقات", "الاستعمال", "صدر · استُعمل", "الالتزامُ القائم", "انتهت بلا استعمال"]}
      rows={rows}
      keyOf={(row) => row.kind}
      empty={{ title: "لا تقرير بعد", hint: "يظهر هنا لكلِّ نوعٍ ما صدر وما استُعمل وما بقي في أيدي الناس." }}
      render={(row) => (
        <>
          <span className="font-semibold text-ink">{KIND_LABEL[row.kind]}</span>
          <span className="text-muted">
            {digits(String(row.cards))}
            <span className="block text-10.5">ملغاة {digits(String(row.cancelled))}</span>
          </span>
          <span className="text-ink">
            {digits(row.redemption_rate)}٪
            <span className="block text-10.5 text-muted">مستعمَلة {digits(String(row.redeemed))}</span>
          </span>
          <span className="text-muted">
            <span className="block">{digits(row.issued_amount)}</span>
            <span className="block text-10.5">استُعمل {digits(row.redeemed_amount)}</span>
          </span>
          <span className="font-semibold text-ink">
            {digits(row.outstanding_amount)} {row.currency}
            <span className="block text-10.5 font-normal text-muted">{digits(String(row.unused))} بطاقة</span>
          </span>
          <span className="text-muted">
            {digits(row.expired_amount)}
            <span className="block text-10.5">{digits(String(row.expired))} بطاقة</span>
          </span>
        </>
      )}
    />
  );
}

/** **تذكيرُ الصلاحية** — ما ينتهي خلال ٣٠ يوماً وفيه غيرُ مستعمَل، **والتمديدُ بسببٍ مكتوب**. والهديةُ وبطاقةُ البيع دفعةٌ من بطاقةٍ
 *  واحدة، فتمديدُها تمديدُ البطاقة نفسِها. */
function ExpiringBatches({ country, isAdmin, onError, onDone }: TabProps) {
  const [rows, setRows] = useState<CardBatch[] | null>(null);
  const [extending, setExtending] = useState<CardBatch | null>(null);
  const load = useCallback(async () => setRows(await listExpiringBatches(country, 30)), [country]);
  useEffect(() => {
    load().catch((caught) => onError(errorText(caught, "تعذّر قراءة الصلاحية")));
  }, [load, onError]);
  return (
    <div>
      <p className="mb-8 text-13 font-semibold text-ink">تنتهي خلال 30 يوماً وفيها ما لم يُستعمل</p>
      <Table
        columns="0.8fr 1fr 1.3fr 1.2fr 0.8fr"
        headers={["الدفعة", "النوع", "المحلّ أو الشركة", "تنتهي", ""]}
        rows={rows}
        keyOf={(row) => row.id}
        empty={{ title: "لا شيءَ ينتهي قريباً", hint: "كلُّ بطاقةٍ غيرِ مستعملةٍ صلاحيتُها أبعدُ من ثلاثين يوماً." }}
        render={(row) => (
          <>
            <span className="font-semibold text-ink">#{digits(String(row.number))}</span>
            <span className="text-muted">
              {row.kind === "gift" ? "هدية" : row.kind === "pos" ? "بيعٌ في المحلّ" : "مطبوعة"}
              <span className="block text-10.5">
                غير مستعملة {digits(String(row.unused))} × {digits(row.amount)} {row.currency}
              </span>
            </span>
            <span className="truncate text-muted">{row.buyer_company ?? row.shop_name ?? "—"}</span>
            <span className="text-ink">{day(row.expires_at)}</span>
            <span className="flex justify-end">
              {isAdmin ? (
                <button type="button" onClick={() => setExtending(row)} className="text-11.5 font-semibold text-accent">
                  تمديد
                </button>
              ) : null}
            </span>
          </>
        )}
      />
      {extending ? (
        <ExtendModal
          batch={extending}
          onClose={() => setExtending(null)}
          onDone={(message) => {
            setExtending(null);
            onDone(message);
            void load();
          }}
        />
      ) : null}
    </div>
  );
}

function ExtendModal({ batch, onClose, onDone }: { batch: CardBatch; onClose: () => void; onDone: (message: string) => void }) {
  const [until, setUntil] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await extendCardBatch(batch.id, new Date(`${until}T23:59:59`).toISOString(), reason.trim());
      onDone(`مُدّدت الدفعة #${batch.number}`);
    } catch (caught) {
      setError(errorText(caught, "تعذّر التمديد"));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title={`تمديد الدفعة #${batch.number}`} onClose={onClose}>
      <div className="grid gap-12">
        <p className="text-12 text-muted">تنتهي اليومَ في {day(batch.expires_at)} — والتمديدُ إلى الأمام وحدَه، وسطرٌ في التدقيق.</p>
        <DateInput label="تنتهي صلاحيتُها في" name="expires_at" value={until} onChange={setUntil} />
        <Field label="السبب" name="reason" value={reason} onChange={(event) => setReason(event.target.value)} />
      </div>
      <ErrorNote message={error} />
      <div className="mt-18 flex gap-10">
        <Button className="flex-1" size="md" loading={busy} disabled={!until || reason.trim().length < 3} onClick={() => void submit()}>
          مدِّد
        </Button>
        <Button className="flex-1" size="md" variant="secondary" onClick={onClose}>
          تراجع
        </Button>
      </div>
    </Modal>
  );
}

/** **البائعُ في فواتير الشركات** (SPEC §١٠٠-ب/٧) — يراه الطاقم، **ويكتبه المالكُ وحدَه**؛ وفارغاً تُطبع «TAXO». */
function InvoiceSellerCard({
  country,
  onError,
  onDone,
}: {
  country: CountryCode;
  onError: (message: string | null) => void;
  onDone: (message: string) => void;
}) {
  const { user } = useSession();
  const isOwner = Boolean(user?.roles?.includes("owner"));
  const [row, setRow] = useState<InvoiceSettings | null>(null);
  const [name, setName] = useState("");
  const [tax, setTax] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    getInvoiceSettings(country)
      .then((read) => {
        setRow(read);
        setName(read.invoice_seller_name ?? "");
        setTax(read.invoice_seller_tax_number ?? "");
      })
      .catch((caught) => onError(errorText(caught, "تعذّر قراءة بيانات الفاتورة")));
  }, [country, onError]);
  async function save() {
    setBusy(true);
    try {
      const saved = await saveInvoiceSettings(country, {
        invoice_seller_name: name.trim() || null,
        invoice_seller_tax_number: tax.trim() || null,
      });
      setRow(saved);
      onDone("حُفظت بياناتُ البائع في الفواتير");
    } catch (caught) {
      onError(errorText(caught, "تعذّر الحفظ"));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="rounded-card border border-line bg-surface p-14">
      <p className="text-13 font-semibold text-ink">البائعُ في فواتير الشركات</p>
      <p className="mt-6 text-11.5 text-muted">
        {row ? `${row.invoice_seller_name ?? "TAXO"}${row.invoice_seller_tax_number ? ` · الرقم الضريبي ${row.invoice_seller_tax_number}` : ""}` : "…"}
      </p>
      {isOwner ? (
        <div className="mt-10 flex flex-wrap items-end gap-10">
          <Field label="اسمُ البائع" name="invoice_seller_name" value={name} onChange={(event) => setName(event.target.value)} />
          <Field
            label="الرقمُ الضريبيّ"
            name="invoice_seller_tax_number"
            dir="ltr"
            value={tax}
            onChange={(event) => setTax(event.target.value)}
          />
          <Button size="md" variant="secondary" loading={busy} onClick={() => void save()}>
            حفظ
          </Button>
        </div>
      ) : null}
    </div>
  );
}
