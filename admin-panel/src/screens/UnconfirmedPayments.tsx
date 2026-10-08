/** **«المدفوعات غير المؤكدة»** — A10 (`design/PAYMENTS-UNCONFIRMED.md` §٥، SPEC §٦٤-ز) — **بلا لوحة**: جدولُ العُدّة وحوارُها كأخواتها
 * («الدفعات» · «النزاعات والدعم»)، فالطرفان بخليّتهما وزرُّ ملفِّ كلٍّ منهما (`OpenProfile`) والحكمُ حوار.
 *
 * **الأقدمُ أوّلاً** كما ترسله الخلفية، **والعمرُ أحمرُ فوق ٢٤ ساعة** (§٥). **والأعمدةُ أعمدةُ التصميم**: العمر · الحال (بأسماء
 * الخلفية بالعربية) · المبلغ والطريقة · الطرفان (اسمٌ ورقمٌ مقنَّع ومجموعُ معلَّقاتِ كلٍّ منهما) · الأثر (التذكيراتُ بأوقاتها،
 * وإقرارُ الراكب، والمرجعُ، والنزاعُ والاعتراض). **وصفٌّ سبق المفتاحَ** (`in_flow: false`) يُوسم «قبل الإطلاق»: لا تذكيرَ عليه ولا
 * حجب، والطابورُ وحدَه يحسمه.
 *
 * **والأفعالُ الأربعةُ في حوارٍ واحد** — «أرسل تذكيراً الآن» · «احسم: مدفوع» · «احسم: غيرُ مدفوع» · «حوّل إلى نزاع» — **كلٌّ بسببٍ
 * مكتوب** (٨ أحرفٍ على الأقل، والخلفيةُ تفرضه أيضاً) يدخل التدقيقَ باسم صاحبه، **ونصُّ الخلفية يُقال كما وصل** — ومنه ٥٠١
 * `objection_counter_entry_pending` لحكم «غيرُ مدفوع» على إتمامٍ آليٍّ معترَضٍ عليه (قيدُه المقابلُ لم يُبنَ). **وما لا يقبله
 * الصفُّ يُعطَّل ويقول لماذا** (قاعدةُ اللوحة) لا يُرسل ثمّ يرتدّ.
 *
 * **ولا «حذف» ولا «تعديل مبلغ»** — الدفترُ لا يُعدَّل (القاعدةُ الثانية في `CLAUDE.md`). **ولا «أنهِ الرحلة»**: الإنهاءُ الآليُّ
 * وحالتُه لم يُبنيا (§٦٤-ز).
 */

import { useCallback, useEffect, useRef, useState } from "react";

import {
  disputeUnconfirmedPayment,
  listUnconfirmedPayments,
  remindUnconfirmed,
  resolveUnconfirmed,
} from "@/api/endpoints";
import type { DisputeResolution, QueueParty, UnconfirmedQueueRow } from "@/api/types";
import { OpenProfile } from "@/components/profile/OpenProfile";
import { Shell } from "@/components/Shell";
import { Table } from "@/components/Table";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { Modal } from "@/components/ui/Modal";
import { Segmented } from "@/components/ui/Segmented";
import { TestAccountBadge } from "@/components/ui/TestAccountBadge";
import { useCountry } from "@/lib/country";
import { FormErrors, useFormError } from "@/lib/form-errors";
import { moment, money } from "@/lib/format";
import { PAYMENT_METHOD_LABEL, UNCONFIRMED_STATE_LABEL, UNCONFIRMED_STATE_TONE } from "@/lib/labels";
import { digits } from "@/lib/utils";

/** **«أحمرُ فوق ٢٤ س»** (§٥) — رقمُ التصميم نفسُه، **وهو `ESCALATION_HOURS` في الخلفية** (`services/unconfirmed_payments.py`: «لا
 *  عمودَ له في جدول §٩»). فلا يُضبط من اللوحة ولا يُنشر — ويُكتب هنا بعلّته لا رقماً يُخترع. */
const RED_AFTER_MINUTES = 24 * 60;

/** **أقلُّ طولِ سببٍ يُكتب** — «٨ أحرف على الأقل» (§٥)، **والخلفيةُ تفرضه** (`AdminReason`)؛ وهنا لتعطيل الزرِّ قبل الارتداد. */
const MIN_REASON = 8;

/** **صفحةُ الطابور سقفُ الخلفية نفسُه** (`limit ≤ 200`، `admin_unconfirmed_payments.py`) — **ولا تكفي صفحةٌ واحدةٌ بلا «المزيد»**:
 *  الترتيبُ الأقدمُ أوّلاً، **والمعلَّقُ القديمُ كلُّه** (`in_flow: false` — «يذهب إلى طابور الإدارة وحدَه») يُرسل إلى هنا يومَ يشتعل
 *  المفتاح. فصفحةٌ بخمسين — وكانت بها — **يملؤها ما سبق الإطلاق ويُخفي بصمتٍ كلَّ صفٍّ جديد**، وهي الصفوفُ التي تحجب راكباً أو
 *  كبتناً الآن. **فالصفحةُ مئتان، وما بعدها «عرض المزيد»، ويُقال إن الطابورَ لم يُقرأ كلُّه.** */
const PAGE = 200;

/** **أفعالُ الحوار الأربعة** — والحكمان **هما `DisputeResolution` نفسُه** يُرسلان `outcome` كما هما (الواقعةُ لا الحالة)، فلا
 *  يُكتبان هنا ثانيةً فيفترقا عن العقد. */
type Action = "remind" | "dispute" | DisputeResolution;

const ACTION_LABEL: Record<Action, string> = {
  remind: "أرسل تذكيراً الآن",
  paid: "احسم: مدفوع",
  unpaid: "احسم: غيرُ مدفوع",
  dispute: "حوّل إلى نزاع",
};

/** **ما يقع بعد كلِّ فعل** — يُقرأ قبل الضغط لا بعده (§٥ · §٨). */
const ACTION_EFFECT: Record<Action, string> = {
  remind: "يصل الطرفَ المنتظَرَ تذكيرٌ الآن — ولا تتغيّر مواعيدُ الجدول (شرطُ الإتمام الآليّ).",
  paid: "يُكتب ما يكتبه تأكيدُ الكبتن حرفاً، مؤكَّدةً بحكمك — وعلى إتمامٍ آليٍّ معترَضٍ عليه يُغلق الاعتراضَ بلا قيدٍ جديد.",
  unpaid: "لا قيدَ في الدفتر — تصير الدفعةُ «فاشلة» ويعود المبلغُ مستحقّاً على الراكب.",
  dispute: "تصير الدفعةُ نزاعاً، ويُسأل الطرفان بنصّهما. لا قيد.",
};

/** **أيقبل الصفُّ هذا الفعل؟** — `null` نعم، وإلا علّتُه نصّاً. **التذكيرُ والنزاعُ لما ينتظر أحداً وحدَه** (`_require_unconfirmed`:
 *  معلَّقٌ كاشاً أو كليك)؛ والحكمُ لكلِّ صفّ — **و«غيرُ مدفوع» على الاعتراض يُرسل** فيردّ ٥٠١ بنصّه: القرارُ قرارُ الخلفية. */
function refusal(row: UnconfirmedQueueRow, action: Action): string | null {
  const pending = row.status === "pending";
  if ((action === "remind" || action === "dispute") && !pending) {
    return row.state === "disputed"
      ? "في نزاعٍ سلفاً — يُحسم ولا يُذكَّر به أحد"
      : "أُتمّت آلياً واعتُرض عليها — تُحسم ولا يُذكَّر بها أحد";
  }
  return null;
}

/** «26 س» · «40 د» · «3 ي» — **العمرُ من الخلفية** (`age_minutes`)، والتقريبُ للعرض وحدَه. */
function ageLabel(minutes: number): string {
  if (minutes < 60) return `${digits(String(minutes))} د`;
  const hours = Math.floor(minutes / 60);
  if (hours < 72) return `${digits(String(hours))} س`;
  return `${digits(String(Math.floor(hours / 24)))} ي`;
}

export function UnconfirmedPaymentsScreen() {
  // **مبدّلُ الدولة في الرأس وعدٌ لكلِّ شاشة** — كأخواتها
  const { country } = useCountry();
  const [rows, setRows] = useState<UnconfirmedQueueRow[] | null>(null);
  // **امتلأت آخرُ صفحة ⇒ قد يكون بعدها المزيد** — والعددُ الكاملُ لا تنشره الخلفية، فلا يُخترع هنا
  const [more, setMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  // **كم صفحةً قُرئت** — فالحسمُ يعيد قراءتَها كلَّها لا الأولى وحدَها، ولا يعود بالمشرف إلى رأس طابورٍ نزل فيه
  const pages = useRef(1);
  const [open, setOpen] = useState<UnconfirmedQueueRow | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRows(null);
    let all: UnconfirmedQueueRow[] = [];
    let full = false;
    for (let page = 0; page < pages.current; page += 1) {
      const chunk = await listUnconfirmedPayments(country, PAGE, page * PAGE);
      all = appendRows(all, chunk);
      full = chunk.length === PAGE;
      if (!full) break;
    }
    setRows(all);
    setMore(full);
  }, [country]);

  useEffect(() => {
    pages.current = 1;
    load().catch((caught: Error) => setError(caught.message || "تعذّر قراءة الطابور"));
  }, [load]);

  async function loadMore() {
    setLoadingMore(true);
    setError(null);
    try {
      const chunk = await listUnconfirmedPayments(country, PAGE, pages.current * PAGE);
      pages.current += 1;
      setRows((current) => appendRows(current ?? [], chunk));
      setMore(chunk.length === PAGE);
    } catch (caught) {
      setError(caught instanceof Error && caught.message ? caught.message : "تعذّر قراءة بقية الطابور");
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <Shell
      title="المدفوعات غير المؤكدة"
      subtitle="ما ينتظر تأكيدَ أحدٍ بعد نهاية رحلته — الأقدمُ أوّلاً، وكلُّ حسمٍ بسببٍ مكتوب"
    >
      <ErrorNote message={error} />
      <SuccessNote message={done} />

      <div className={error || done ? "ad-uq-table mt-12" : "ad-uq-table"}>
        <Table
          columns=".55fr 1fr .95fr 1.45fr 1.7fr auto"
          headers={["العمر", "الحال", "المبلغ والطريقة", "الطرفان", "الأثر", ""]}
          rows={rows}
          keyOf={(row) => row.payment_id}
          empty={{
            title: "لا مدفوعاتٍ تنتظر أحداً",
            hint: "يظهر هنا كلُّ كاشٍ أو كليكٍ لم يُؤكَّد بعد نهاية رحلته، والنزاعاتُ، وما أُتمّ آلياً واعتُرض عليه.",
          }}
          render={(row) => (
            <>
              {/* **العمرُ أحمرُ فوق ٢٤ س** (§٥) — والوقتُ الدقيقُ في التلميح */}
              <span
                className={row.age_minutes > RED_AFTER_MINUTES ? "font-bold text-danger" : "text-ink"}
                title={row.completed_at ? digits(moment(row.completed_at)) : undefined}
              >
                {ageLabel(row.age_minutes)}
              </span>
              <span className="ad-uq-state">
                <Badge tone={UNCONFIRMED_STATE_TONE[row.state]}>{UNCONFIRMED_STATE_LABEL[row.state]}</Badge>
                {/* **صفٌّ سبق المفتاح** (`in_flow: false`) — لا تذكيرَ عليه ولا حجبَ ولا إتمامَ آليّ */}
                {row.in_flow ? null : <span className="ad-uq-tag">قبل الإطلاق</span>}
              </span>
              <span className="ad-reason">
                <span className="ad-fare">
                  <span dir="ltr">{money(row.amount, row.currency)}</span>
                </span>
                <span className="ad-reason-sub">{PAYMENT_METHOD_LABEL[row.method] ?? row.method}</span>
              </span>
              <span className="ad-parties">
                <PartyLine kind="rider" party={row.rider} />
                {row.driver ? <PartyLine kind="driver" party={row.driver} /> : <span className="ad-party sub">—</span>}
              </span>
              <Trail row={row} />
              <span className="ad-row-end">
                <Button size="sm" variant="secondary" onClick={() => setOpen(row)}>
                  احسم…
                </Button>
              </span>
            </>
          )}
        />
      </div>

      {/* **كم قُرئ، وأنّ بعده المزيد** — «الأقدمُ أوّلاً» يعني أن الأحدثَ في آخرها: صفحةٌ ممتلئةٌ بلا هذا السطر تُقرأ طابوراً كاملاً */}
      {rows && rows.length > 0 ? (
        <div className="mt-12 flex flex-wrap items-center justify-between gap-8 text-11.5 text-muted">
          <span>
            {more
              ? `يُعرض أقدمُ ${digits(String(rows.length))} — وبعدها المزيد، والأحدثُ آخرَها`
              : `يُعرض الطابورُ كلُّه: ${digits(String(rows.length))}`}
          </span>
          {more ? (
            <Button size="sm" variant="secondary" className="w-auto" loading={loadingMore} onClick={() => void loadMore()}>
              عرض المزيد
            </Button>
          ) : null}
        </div>
      ) : null}

      {open ? (
        <ActionModal
          row={open}
          onClose={() => setOpen(null)}
          onDone={(message) => {
            setOpen(null);
            setDone(message);
            void load().catch((caught: Error) => setError(caught.message));
          }}
        />
      ) : null}
    </Shell>
  );
}

/** **يُلحق صفحةً بما قُرئ بلا تكرار** — الطابورُ يتحرّك بين صفحتين (حسمٌ أو صفٌّ جديد)، فصفٌّ قُرئ وأعادته الإزاحةُ لا يُرسم مرّتين. */
function appendRows(current: UnconfirmedQueueRow[], chunk: UnconfirmedQueueRow[]): UnconfirmedQueueRow[] {
  const seen = new Set(current.map((row) => row.payment_id));
  return [...current, ...chunk.filter((row) => !seen.has(row.payment_id))];
}

/** **طرفٌ بسطرين**: اسمُه وزرُّ ملفِّه، ثمّ رقمُه المقنَّع ومجموعُ معلَّقاته — «اسمٌ ورقمٌ مقنَّع ومجموعُ معلَّقاتِ كلٍّ منهما» (§٥). */
function PartyLine({ kind, party }: { kind: "rider" | "driver"; party: QueueParty }) {
  // **`drivers.id` للكبتن لا `users.id`** — خلطُهما يفتح ملفَّ إنسانٍ آخر (`QueuePartyOut`)؛ وبلا معرّفٍ لا زرَّ يفتح لا شيء
  const profileId = kind === "driver" ? party.driver_id : party.user_id;
  return (
    <>
      <span className={kind === "driver" ? "ad-party sub" : "ad-party"}>
        <span className="ad-party-name">
          {kind === "driver" ? "الكبتن " : ""}
          {party.name}
        </span>
        {/* **طرفُ تجربة** (SPEC §٦٥-ج) — «لم يدفع» أو نزاعٌ على دفعة تجربةٍ يُحكم وهو معروف */}
        <TestAccountBadge isTest={party.is_test} />
        {profileId ? (
          <OpenProfile kind={kind} id={profileId} search={kind === "driver" ? party.name : undefined} />
        ) : null}
      </span>
      <span className="ad-uq-meta">
        <span dir="ltr">{party.phone_masked}</span> · معلَّقاتُه {digits(String(party.pending_count))}
      </span>
    </>
  );
}

/** **الأثر** (§٥): التذكيراتُ المرسلةُ بأوقاتها، وإقرارُ الراكب، والمرجعُ، والنزاعُ أو الاعتراضُ بسببه. **قراءةٌ لا حساب** — كلُّ
 *  وقتٍ وعددٍ من الصفّ كما وصل. */
function Trail({ row }: { row: UnconfirmedQueueRow }) {
  const lines: string[] = [];
  if (row.declared_at) lines.push(`أقرّ الراكبُ بالتسليم ${digits(moment(row.declared_at))}`);
  if (row.cliq_transfer_reference) {
    lines.push(
      `مرجعُ الحوالة ${row.cliq_transfer_reference}${row.cliq_reference_at ? ` · ${digits(moment(row.cliq_reference_at))}` : ""}`,
    );
  }
  if (row.dispute_reason) lines.push(`النزاع: ${row.dispute_reason}`);
  if (row.objection_reason) {
    lines.push(`اعتراضُ الكبتن: ${row.objection_reason}${row.objected_at ? ` · ${digits(moment(row.objected_at))}` : ""}`);
  }
  // **آخرُ ثلاثةٍ بأوقاتها** والعددان كاملين — الأثرُ الكاملُ طويلٌ في صفّ، والعددُ يقول كم وصل كلَّ طرف
  const recent = row.reminder_trail.slice(-3);
  return (
    <span className="ad-reason">
      <span className="ad-reason-main">
        تذكيرات: الكبتن {digits(String(row.driver_reminders))} · الراكب {digits(String(row.rider_reminders))}
      </span>
      {recent.map((stamp) => (
        <span key={`${stamp.to}-${stamp.at}`} className="ad-reason-sub">
          {stamp.to === "captain" ? "للكبتن" : "للراكب"} {digits(moment(stamp.at))}
        </span>
      ))}
      {lines.map((line) => (
        <span key={line} className="ad-reason-sub">
          {line}
        </span>
      ))}
    </span>
  );
}

/** **حوارُ الحسم** — الفعلُ يُختار ثمّ سببُه ثمّ التنفيذ. **الحوارُ نفسُه هو التأكيد** (نمطُ «فصل النزاع»)، والأثرُ يُقرأ تحت الفعل
 *  قبل الضغط، **والخطأُ من الخلفية كما وصل** — ومنه ٥٠١ «قيدُه المقابلُ لم يُبنَ». */
function ActionModal({
  row,
  onClose,
  onDone,
}: {
  row: UnconfirmedQueueRow;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [action, setAction] = useState<Action>(refusal(row, "remind") === null ? "remind" : "paid");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const form = useFormError();
  const why = refusal(row, action);
  const ready = why === null && reason.trim().length >= MIN_REASON;

  function run() {
    const cleaned = reason.trim();
    setBusy(true);
    form.setMessage(null);
    const call: Promise<string> =
      action === "remind"
        ? remindUnconfirmed(row.payment_id, cleaned).then((out) =>
            out.sent_to.length === 0
              ? "لم يُرسل شيء — لا طرفَ ينتظره الآن"
              : `أُرسل التذكيرُ إلى ${out.sent_to.map((side) => (side === "captain" ? "الكبتن" : "الراكب")).join(" و")}`,
          )
        : action === "dispute"
          ? disputeUnconfirmedPayment(row.payment_id, cleaned).then(() => "حُوّلت إلى نزاع — وسُئل الطرفان")
          : resolveUnconfirmed(row.payment_id, action, cleaned).then((out) =>
              action === "paid"
                ? out.status === "confirmed"
                  ? "حُسمت: مدفوعة — كُتب ما يكتبه التأكيد"
                  : "حُسمت: مدفوعة"
                : "حُسمت: غيرُ مدفوعة — عاد المبلغُ مستحقّاً على الراكب",
            );
    call
      .then(onDone)
      .catch((caught) => form.capture(caught, "تعذّر تنفيذ الفعل"))
      .finally(() => setBusy(false));
  }

  return (
    <FormErrors value={form.field}>
      <Modal title="حسمُ دفعةٍ غير مؤكدة" onClose={onClose}>
        <p className="ad-modal-lede">
          كلُّ فعلٍ هنا بسببٍ مكتوبٍ يدخل سجلَّ التدقيق باسمك. ولا حذفَ ولا تعديلَ مبلغ — الدفترُ لا يُعدَّل.
        </p>

        <dl className="ad-resolve-dl">
          <div>
            <dt>المبلغ</dt>
            <dd dir="ltr">{money(row.amount, row.currency)}</dd>
          </div>
          <div>
            <dt>الطريقة · الحال</dt>
            <dd>
              {PAYMENT_METHOD_LABEL[row.method] ?? row.method} · {UNCONFIRMED_STATE_LABEL[row.state]}
            </dd>
          </div>
          <div>
            <dt>الراكب · الكبتن</dt>
            <dd>
              {row.rider.name} · {row.driver?.name ?? "—"}
            </dd>
          </div>
        </dl>

        <Segmented
          label="الفعل"
          value={action}
          options={(Object.keys(ACTION_LABEL) as Action[]).map((key) => ({ key, label: ACTION_LABEL[key] }))}
          onPick={(key) => {
            setAction(key);
            form.setMessage(null);
          }}
        />
        <p className={why ? "mt-8 text-11.5 leading-snug text-warn" : "mt-8 text-11.5 leading-snug text-muted"}>
          {why ?? ACTION_EFFECT[action]}
        </p>

        <div className="mt-12">
          <Field
            label="السبب (يدخل سجلَّ التدقيق)"
            name="reason"
            placeholder="ثمانية أحرف على الأقل"
            value={reason}
            maxLength={255}
            disabled={why !== null}
            onChange={(event) => setReason(event.target.value)}
          />
        </div>

        <ErrorNote message={form.message} />

        <div className="ad-modal-actions">
          <Button
            size="md"
            variant={action === "unpaid" ? "danger" : "primary"}
            loading={busy}
            disabled={!ready}
            onClick={run}
          >
            {ACTION_LABEL[action]}
          </Button>
          <Button size="md" variant="ghost" disabled={busy} onClick={onClose}>
            تراجع
          </Button>
        </div>
      </Modal>
    </FormErrors>
  );
}
