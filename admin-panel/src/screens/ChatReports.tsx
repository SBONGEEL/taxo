/** **الرسائلُ المبلَّغُ عنها** (A30 — SPEC §٦٦-ب/١٣، `design/APPROVALS-DATA.md` §١ «البلاغ»).
 *
 * قائمةٌ — الرسالةُ ومرسلُها، ومن أبلغ، والسبب، والرحلة، والحال — **المفتوحُ أوّلاً** (ترتيبُ الخادم)، وتفصيلٌ بزرّ «عولج» وسطرِ
 * ملاحظة. **وبصلاحية `trip_chats.read` نفسِها**: الصفُّ يحمل نصَّ الرسالة، فقراءتُه قراءةُ محادثة — **وفتحُ القائمة سطرٌ في
 * التدقيق** (الخادمُ يكتبه)، فلا تُطلب لمن لا يملكها. **وتتبع مبدّلَ السوق** كبقية اللوحة.
 *
 * **و«عولج» مرّةً واحدة** (`chat_report_already_handled`)، **ومعه يبدأ عدّادُ حذف المحادثة** — فلا يُضغط قبل أن تُقرأ.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { handleChatReport, listChatReports } from "@/api/endpoints";
import type { AdminChatReport, ChatReportStatus } from "@/api/types";
import { REPORT_REASON_LABEL, TripChatsRefusal } from "@/components/RideComms";
import { Shell } from "@/components/Shell";
import { Pills, Table } from "@/components/Table";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { Modal } from "@/components/ui/Modal";
import { useCountry } from "@/lib/country";
import { moment } from "@/lib/format";
import { TRIP_CHATS_READ, useMyPermissions } from "@/lib/permissions";

import "@/t2/comms.css";

const COLUMNS = "2fr 1fr 1fr 0.8fr 0.8fr 0.8fr";

const SIDE_LABEL: Record<"rider" | "driver", string> = { rider: "الراكب", driver: "الكبتن" };

export function ChatReportsScreen() {
  const held = useMyPermissions();
  const { country } = useCountry();
  const [status, setStatus] = useState<ChatReportStatus | "all">("open");
  const [rows, setRows] = useState<AdminChatReport[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refused, setRefused] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [open, setOpen] = useState<AdminChatReport | null>(null);
  const allowed = held?.has(TRIP_CHATS_READ) === true;

  const load = useCallback(async () => {
    setRows(null);
    setError(null);
    try {
      setRows(await listChatReports({ status: status === "all" ? undefined : status, country_code: country, limit: 200 }));
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 403) setRefused(true);
      else setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة البلاغات");
    }
  }, [country, status]);

  useEffect(() => {
    // **لا يُطلب لمن لا يملكها** — والطلبُ نفسُه سطرٌ في التدقيق
    if (allowed) void load();
  }, [allowed, load]);

  return (
    <Shell title="الرسائل المبلَّغ عنها" subtitle="بلاغاتُ الركّاب والكباتن على رسائل المحادثة — وكلُّ فتحٍ لهذه القائمة يُسجَّل باسمك">
      {held === null ? null : !allowed || refused ? (
        <TripChatsRefusal />
      ) : (
        <>
          <Pills
            value={status}
            onPick={(key) => setStatus(key)}
            options={[
              { key: "open", label: "مفتوحة" },
              { key: "handled", label: "عولجت" },
              { key: "all", label: "الكل" },
            ]}
          />
          <ErrorNote message={error} />
          <SuccessNote message={done} />
          <Table
            columns={COLUMNS}
            headers={["الرسالة", "المرسل", "من أبلغ", "السبب", "الرحلة", "الحال"]}
            rows={rows}
            keyOf={(row) => row.id}
            empty={{
              title: status === "open" ? "لا بلاغاتٍ مفتوحة" : "لا بلاغات",
              hint: "يصل البلاغُ حين يلمس راكبٌ أو كبتنٌ رسالةَ الطرف الآخر لمساً مطوّلاً ويختار سببه.",
            }}
            render={(row) => (
              <>
                <button type="button" className="ad-cm-clip text-start font-semibold text-ink" onClick={() => setOpen(row)}>
                  {row.message.body}
                </button>
                <span>{row.message.sender_name ?? SIDE_LABEL[row.message.sender_role]}</span>
                <span>{row.reporter_name ?? (row.reporter_role ? SIDE_LABEL[row.reporter_role] : "—")}</span>
                <span>{REPORT_REASON_LABEL[row.reason]}</span>
                <span dir="ltr" className="text-start text-muted">
                  #{row.ride_id.slice(0, 8)}
                </span>
                <span>
                  <Badge tone={row.status === "open" ? "danger" : "ok"}>{row.status === "open" ? "مفتوح" : "عولج"}</Badge>
                </span>
              </>
            )}
          />
        </>
      )}

      {open ? (
        <ReportDetail
          report={open}
          onClose={() => setOpen(null)}
          onHandled={(row) => {
            setOpen(row);
            setDone("عولج البلاغ — ويبدأ الآن عدّادُ حذف المحادثة");
            setRows((current) => current?.map((item) => (item.id === row.id ? row : item)) ?? current);
          }}
        />
      ) : null}
    </Shell>
  );
}

/** التفصيل — الرسالةُ كاملةً، ومن أرسلها ومن أبلغ ولماذا، **و«عولج» بسطرِ ملاحظة**. */
function ReportDetail({
  report,
  onClose,
  onHandled,
}: {
  report: AdminChatReport;
  onClose: () => void;
  onHandled: (row: AdminChatReport) => void;
}) {
  const navigate = useNavigate();
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <Modal title="بلاغٌ على رسالة" onClose={onClose}>
      <blockquote className="ad-cm-quote">{report.message.body}</blockquote>
      <div className="ad-kv mt-12">
        <div className="ad-kv-row">
          <span className="ad-kv-label">المرسل</span>
          <span className="ad-kv-value">
            {report.message.sender_name ?? "—"} · {SIDE_LABEL[report.message.sender_role]}
            <span className="ad-kv-hint">أُرسلت {moment(report.message.created_at)}</span>
          </span>
        </div>
        <div className="ad-kv-row">
          <span className="ad-kv-label">من أبلغ</span>
          <span className="ad-kv-value">
            {report.reporter_name ?? "—"}
            {report.reporter_role ? ` · ${SIDE_LABEL[report.reporter_role]}` : ""}
            <span className="ad-kv-hint">أبلغ {moment(report.created_at)}</span>
          </span>
        </div>
        <div className="ad-kv-row">
          <span className="ad-kv-label">السبب</span>
          <span className="ad-kv-value">
            {REPORT_REASON_LABEL[report.reason]}
            {report.note ? <span className="ad-kv-hint">{report.note}</span> : null}
          </span>
        </div>
        <div className="ad-kv-row">
          <span className="ad-kv-label">الرحلة</span>
          <span className="ad-kv-value">
            <button type="button" className="font-semibold text-ink underline" onClick={() => navigate(`/rides?open=${report.ride_id}`)}>
              <span dir="ltr">#{report.ride_id.slice(0, 8)}</span>
            </button>
          </span>
        </div>
        {report.status === "handled" ? (
          <div className="ad-kv-row">
            <span className="ad-kv-label">عولج</span>
            <span className="ad-kv-value">
              {report.handled_by_name ?? "—"}
              {report.handled_at ? ` · ${moment(report.handled_at)}` : ""}
              {report.handled_note ? <span className="ad-kv-hint">{report.handled_note}</span> : null}
            </span>
          </div>
        ) : null}
      </div>

      {report.status === "open" ? (
        <div className="mt-12">
          <Field
            label="ملاحظة (اختياريّة)"
            name="handled_note"
            value={note}
            maxLength={500}
            onChange={(event) => setNote(event.target.value)}
          />
          <ErrorNote message={error} />
          <Button
            className="mt-12"
            loading={busy}
            onClick={() => {
              setBusy(true);
              setError(null);
              handleChatReport(report.id, note.trim())
                .then(onHandled)
                .catch((caught) => setError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ"))
                .finally(() => setBusy(false));
            }}
          >
            عولج
          </Button>
        </div>
      ) : null}
      <Button className="mt-12" variant="ghost" onClick={onClose}>
        إغلاق
      </Button>
    </Modal>
  );
}
