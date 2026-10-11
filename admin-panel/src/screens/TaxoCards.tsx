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
  cancelTaxoCard,
  cardShopReport,
  createCardBatch,
  createCardShop,
  findTaxoCards,
  getCardLimits,
  listCardAlerts,
  listCardBatches,
  listCardDenominations,
  listCardShops,
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
  CountryCode,
  TaxoCardLimits,
  TaxoCardRow,
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

type Tab = "batches" | "cards" | "shops" | "denominations" | "report" | "alerts";

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
          { key: "cards", label: "البطاقات" },
          { key: "shops", label: "المحلّات" },
          { key: "denominations", label: "الفئات" },
          { key: "report", label: "التقرير" },
          { key: "alerts", label: "التخمين" },
        ]}
      />
      <ErrorNote message={error} />
      <SuccessNote message={done} />
      <div className="mt-12">
        {tab === "batches" ? <BatchesTab country={country} isAdmin={isAdmin} onError={setError} onDone={setDone} /> : null}
        {tab === "cards" ? <CardsTab country={country} isAdmin={isAdmin} onError={setError} onDone={setDone} /> : null}
        {tab === "shops" ? <ShopsTab country={country} isAdmin={isAdmin} onError={setError} onDone={setDone} /> : null}
        {tab === "denominations" ? (
          <DenominationsTab country={country} currency={currency} isAdmin={isAdmin} onError={setError} onDone={setDone} />
        ) : null}
        {tab === "report" ? <ReportTab country={country} onError={setError} /> : null}
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

  const load = useCallback(async () => setRows(await listCardBatches(country)), [country]);
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
              <span className="block truncate">{row.shop_name ?? "—"}</span>
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
                قائمة {digits(String(row.active))} · مستعمَلة {digits(String(row.redeemed))} · ملغاة {digits(String(row.cancelled))}
              </span>
              {row.cancel_reason ? <span className="block text-10.5 font-normal text-muted">{row.cancel_reason}</span> : null}
            </span>
            <span className="text-ink">
              <span className="block font-semibold">{digits(row.due_amount)}</span>
              <span className="block text-10.5 text-muted">
                استُعمل {digits(row.redeemed_amount)} من {digits(row.live_amount)} {row.currency}
              </span>
            </span>
            <span className="flex justify-end">
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
          shop_id: shopId || null,
          valid_from: new Date(`${validFrom}T00:00:00`).toISOString(),
          expires_at: new Date(`${expiresAt}T23:59:59`).toISOString(),
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
        <Select label="المحلّ" name="shop_id" value={shopId} onChange={(event) => setShopId(event.target.value)}>
          <option value="">بلا محلّ (مكتب TAXO)</option>
          {shops.map((row) => (
            <option key={row.id} value={row.id}>
              {row.name}
            </option>
          ))}
        </Select>
        <span />
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
          disabled={!denominationId || Number(quantity) < 1 || !validFrom || !expiresAt}
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

/** **ملفُّ الطباعة** — يُبنى في المتصفّح من الردّ نفسِه، **ولا يُرسل إلى أيِّ مكان**. */
function downloadCodes(created: CardBatchCreated) {
  const head = "serial,code,amount,currency,valid_from,expires_at";
  const lines = created.codes.map(
    (row) =>
      `${row.serial},${row.code},${created.batch.amount},${created.batch.currency},${created.batch.valid_from},${created.batch.expires_at}`,
  );
  const blob = new Blob([[head, ...lines].join("\n")], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `taxo-cards-batch-${created.batch.number}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
}

function CodesModal({ created, onClose }: { created: CardBatchCreated; onClose: () => void }) {
  const [saved, setSaved] = useState(false);
  return (
    <Modal title={`رموز الدفعة #${created.batch.number}`} onClose={saved ? onClose : () => undefined} wide>
      <p className="mb-12 rounded-14 border border-warn bg-surface-2 px-14 py-12 text-12 leading-note text-ink">
        هذه هي المرّةُ الوحيدةُ التي تظهر فيها الرموز. نزّل الملفّ واحفظه قبل الإغلاق — {digits(String(created.codes.length))} بطاقة.
      </p>
      <div className="max-h-64 overflow-y-auto rounded-14 border border-line px-14 py-10">
        {created.codes.slice(0, 50).map((row) => (
          <div key={row.serial} dir="ltr" className="flex justify-between text-12 text-ink">
            <span>{row.serial}</span>
            <span className="font-semibold">{row.code}</span>
          </div>
        ))}
        {created.codes.length > 50 ? (
          <p className="mt-6 text-11 text-muted">… والباقي في الملفّ.</p>
        ) : null}
      </div>
      <div className="mt-18 flex gap-10">
        <Button
          className="flex-1"
          size="md"
          onClick={() => {
            downloadCodes(created);
            setSaved(true);
          }}
        >
          نزّل ملفَّ الطباعة
        </Button>
        <Button className="flex-1" size="md" variant="secondary" disabled={!saved} onClick={onClose}>
          حفظتُه — أغلق
        </Button>
      </div>
    </Modal>
  );
}

// ------------------------------------------------------------------ البطاقات

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
        columns="1.4fr 0.8fr 0.6fr 1.4fr 1fr"
        headers={["الرقم التسلسليّ", "القيمة", "الدفعة", "الحال", ""]}
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
            <span className="text-muted">#{digits(String(row.batch_number))}</span>
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

function ReportTab({ country, onError }: { country: CountryCode; onError: (message: string | null) => void }) {
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
