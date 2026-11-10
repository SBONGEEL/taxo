/** **الطلباتُ والشكاوى** (أمرُ المالك ٢٠٢٦-١١-١٠، البندان ٨ و٩) — «محادثة مع الدعم» و«نسيت شيئاً» و«شكوى على الرحلة» من التطبيقين.
 *
 * **ما ينتظر ردّاً أوّلاً**، ثمّ الأحدث. **والدرجُ يجمع ما يحتاجه الجواب**: المحادثةُ كاملةً، والحسابُ وآخرُ رحلاته (البند ٨)، والصورةُ إن
 * أُرفقت (تُجلب بالجلسة). **والحسمُ بسببٍ إلزاميّ** يصل صاحبَ الطلب، ويُدقَّق. **وفي خيط المفقودات الكبتنُ طرفٌ** يقرأ ردودَ الفريق
 * ويردّ — بلا أرقام هواتف.
 */

import { useCallback, useEffect, useState } from "react";

import { decideTicket, getTicket, getTicketStats, listTickets, replyTicket, ticketPhotoBlob } from "@/api/endpoints";
import type { AdminTicket, AdminTicketDetail, ComplaintCategory, TicketKind, TicketStats, TicketStatus } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Drawer } from "@/components/ui/Drawer";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { Segmented } from "@/components/ui/Segmented";
import { moment } from "@/lib/format";

type StatusFilter = "active" | "resolved" | "rejected" | "all";
type KindFilter = "any" | TicketKind;

const KIND_LABEL: Record<TicketKind, string> = {
  support: "محادثة دعم",
  lost_item: "غرضٌ مفقود",
  complaint: "شكوى",
};

const STATUS_LABEL: Record<TicketStatus, string> = {
  open: "مفتوح",
  in_review: "قيد المراجعة",
  resolved: "محسوم",
  rejected: "مرفوض",
};

const CATEGORY_LABEL: Record<ComplaintCategory, string> = {
  behavior: "السلوك",
  vehicle: "السيارة",
  route: "المسار",
  fare: "الأجرة",
  safety: "السلامة",
  other: "أخرى",
};

const ROLE_LABEL: Record<string, string> = {
  user: "صاحبُ الطلب",
  party: "الكبتن",
  staff: "فريقُ الدعم",
};

const APP_LABEL: Record<string, string> = { rider: "الراكب", driver: "الكبتن" };

function statusTone(status: TicketStatus): "warn" | "ok" | "muted" | "danger" {
  if (status === "open") return "warn";
  if (status === "resolved") return "ok";
  if (status === "rejected") return "danger";
  return "muted";
}

function Photo({ ticketId }: { ticketId: string }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let url: string | null = null;
    let alive = true;
    ticketPhotoBlob(ticketId)
      .then((value) => {
        if (alive) {
          url = value;
          setSrc(value);
        } else URL.revokeObjectURL(value);
      })
      .catch(() => undefined);
    return () => {
      alive = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [ticketId]);
  return src ? <img src={src} alt="الصورةُ المرفقة بالطلب" className="mb-10 max-h-[240px] rounded-10 border border-line" /> : null;
}

function TicketDrawer({ ticketId, onClose, onChanged }: { ticketId: string; onClose: () => void; onChanged: () => void }) {
  const [data, setData] = useState<AdminTicketDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reply, setReply] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getTicket(ticketId)
      .then(setData)
      .catch((cause: Error) => setError(cause.message));
  }, [ticketId]);

  const act = async (run: () => Promise<AdminTicketDetail>) => {
    setBusy(true);
    setError(null);
    try {
      setData(await run());
      onChanged();
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const active = data ? data.status === "open" || data.status === "in_review" : false;
  return (
    <Drawer
      name={data?.account.name ?? "…"}
      phone={data?.account.phone}
      badges={
        data ? (
          <>
            <Badge tone={statusTone(data.status)}>{STATUS_LABEL[data.status]}</Badge>{" "}
            <Badge tone="muted">{KIND_LABEL[data.kind]}</Badge>
          </>
        ) : null
      }
      onClose={onClose}
    >
      <ErrorNote message={error} />
      {data === null ? (
        error ? null : (
          <div className="ad-sec-loading">
            <Spinner />
          </div>
        )
      ) : (
        <>
          <h3 className="ad-dh">الطلب</h3>
          <div className="ad-box">
            <div className="ad-kv">
              <div className="ad-kv-row">
                <span className="ad-kv-label">من تطبيق</span>
                <span className="ad-kv-value">{APP_LABEL[data.app] ?? data.app}</span>
              </div>
              {data.category ? (
                <div className="ad-kv-row">
                  <span className="ad-kv-label">الفئة</span>
                  <span className="ad-kv-value">{CATEGORY_LABEL[data.category]}</span>
                </div>
              ) : null}
              {data.against_name ? (
                <div className="ad-kv-row">
                  <span className="ad-kv-label">{data.kind === "lost_item" ? "الكبتن (طرفٌ في المحادثة)" : "الطرفُ الآخر"}</span>
                  <span className="ad-kv-value">{data.against_name}</span>
                </div>
              ) : null}
              {data.ride_id ? (
                <div className="ad-kv-row">
                  <span className="ad-kv-label">الرحلة</span>
                  <a className="ad-kv-value ad-link" href={`/rides?ride=${data.ride_id}`} dir="ltr">
                    {data.ride_id.slice(0, 8)}
                  </a>
                </div>
              ) : null}
              <div className="ad-kv-row">
                <span className="ad-kv-label">فُتح</span>
                <span className="ad-kv-value">{moment(data.created_at)}</span>
              </div>
              {data.decision_reason ? (
                <div className="ad-kv-row">
                  <span className="ad-kv-label">سببُ القرار</span>
                  <span className="ad-kv-value">{data.decision_reason}</span>
                </div>
              ) : null}
            </div>
          </div>

          <h3 className="ad-dh">المحادثة</h3>
          <div className="ad-box">
            {data.has_photo ? <Photo ticketId={data.id} /> : null}
            <ol className="flex flex-col gap-8">
              {data.messages.map((message) => (
                <li
                  key={message.id}
                  className={
                    message.author_role === "staff"
                      ? "rounded-10 bg-surface-2 p-10"
                      : "rounded-10 border border-line p-10"
                  }
                >
                  <p className="mb-4 text-11 text-muted">
                    {ROLE_LABEL[message.author_role]} · {moment(message.created_at)}
                  </p>
                  <p className="whitespace-pre-wrap text-13 leading-relaxed text-ink">{message.body}</p>
                </li>
              ))}
            </ol>
            {active ? (
              <div className="mt-10">
                <label className="mb-4 block text-12 font-bold text-ink" htmlFor="ticket-reply">
                  ردُّ الفريق
                </label>
                <textarea
                  id="ticket-reply"
                  name="reply"
                  rows={3}
                  maxLength={2000}
                  className="fld"
                  value={reply}
                  onChange={(event) => setReply(event.target.value)}
                />
                <Button
                  className="mt-8"
                  size="sm"
                  loading={busy}
                  disabled={!reply.trim()}
                  onClick={() =>
                    act(async () => {
                      const next = await replyTicket(data.id, reply.trim());
                      setReply("");
                      return next;
                    })
                  }
                >
                  أرسل الردّ
                </Button>
              </div>
            ) : null}
          </div>

          {active ? (
            <>
              <h3 className="ad-dh">القرار</h3>
              <div className="ad-box">
                <p className="ad-box-hint">السببُ إلزاميٌّ للحسم، ويصل صاحبَ الطلب إشعاراً ويُسجَّل في سجلّ التدقيق.</p>
                <textarea
                  id="ticket-reason"
                  name="reason"
                  rows={2}
                  maxLength={1000}
                  className="fld"
                  placeholder="سببُ القرار"
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                />
                <div className="mt-8 flex flex-wrap gap-8">
                  <Button size="sm" loading={busy} disabled={reason.trim().length < 3} onClick={() => act(() => decideTicket(data.id, "resolved", reason.trim()))}>
                    حُسم
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    loading={busy}
                    disabled={reason.trim().length < 3}
                    onClick={() => act(() => decideTicket(data.id, "rejected", reason.trim()))}
                  >
                    رفض
                  </Button>
                  {data.status === "open" ? (
                    <Button size="sm" variant="secondary" loading={busy} onClick={() => act(() => decideTicket(data.id, "in_review"))}>
                      قيد المراجعة
                    </Button>
                  ) : null}
                </div>
              </div>
            </>
          ) : null}

          <h3 className="ad-dh">الحساب وآخر الرحلات</h3>
          <div className="ad-box">
            <div className="ad-kv">
              <div className="ad-kv-row">
                <span className="ad-kv-label">الأدوار</span>
                <span className="ad-kv-value">{data.account.roles.join(" · ") || "—"}</span>
              </div>
              <div className="ad-kv-row">
                <span className="ad-kv-label">منذ</span>
                <span className="ad-kv-value">{moment(data.account.created_at)}</span>
              </div>
              {data.account.rides.map((ride) => (
                <div key={ride.id} className="ad-kv-row">
                  <a className="ad-kv-label ad-link" href={`/rides?ride=${ride.id}`} dir="ltr">
                    {ride.id.slice(0, 8)}
                  </a>
                  <span className="ad-kv-value">
                    {ride.status} · {moment(ride.created_at)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </Drawer>
  );
}

function StatsCard() {
  const [stats, setStats] = useState<TicketStats | null>(null);
  useEffect(() => {
    getTicketStats()
      .then(setStats)
      .catch(() => undefined);
  }, []);
  if (stats === null) return null;
  return (
    <section className="mb-14 rounded-14 border border-line bg-surface px-16 py-12">
      <p className="mb-8 text-13 font-bold text-ink">آخر {stats.days} يوماً</p>
      <div className="grid gap-14 md:grid-cols-2">
        <div>
          <p className="mb-4 text-12 font-bold text-ink">الشكاوى بالفئة</p>
          {stats.by_category.length === 0 ? <p className="text-12 text-muted">لا شكاوى.</p> : null}
          {stats.by_category.map((row) => (
            <p key={row.category} className="text-12 text-ink">
              {CATEGORY_LABEL[row.category] ?? row.category}: <span dir="ltr">{row.count}</span>
            </p>
          ))}
        </div>
        <div>
          <p className="mb-4 text-12 font-bold text-ink">أكثرُ الكباتن شكاوى (غيرُ المرفوضة)</p>
          {stats.drivers.length === 0 ? <p className="text-12 text-muted">لا أحد.</p> : null}
          {stats.drivers.map((row) => (
            <p key={row.user_id} className="text-12 text-ink">
              {row.name}: <span dir="ltr">{row.complaints}</span>
            </p>
          ))}
        </div>
      </div>
    </section>
  );
}

export function SupportTicketsScreen() {
  const [status, setStatus] = useState<StatusFilter>("active");
  const [kind, setKind] = useState<KindFilter>("any");
  const [rows, setRows] = useState<AdminTicket[] | null>(null);
  const [waiting, setWaiting] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const page = await listTickets({
        status: status === "all" ? undefined : status,
        kind: kind === "any" ? undefined : kind,
        limit: 100,
      });
      setRows(page.items);
      setWaiting(page.waiting);
    } catch (cause) {
      setError((cause as Error).message);
    }
  }, [status, kind]);

  useEffect(() => {
    setRows(null);
    void load();
  }, [load]);

  return (
    <Shell
      title="الطلبات والشكاوى"
      subtitle={`محادثاتُ الدعم والمفقوداتُ والشكاوى من التطبيقين — ينتظر ردّاً ${waiting}`}
      actions={
        <div className="flex flex-wrap gap-8">
          <Segmented
            label="الحال"
            value={status}
            onPick={setStatus}
            options={[
              { key: "active", label: "قائمة" },
              { key: "resolved", label: "محسومة" },
              { key: "rejected", label: "مرفوضة" },
              { key: "all", label: "الكلّ" },
            ]}
          />
          <Segmented
            label="النوع"
            value={kind}
            onPick={setKind}
            options={[
              { key: "any", label: "الكلّ" },
              { key: "support", label: "دعم" },
              { key: "lost_item", label: "مفقودات" },
              { key: "complaint", label: "شكاوى" },
            ]}
          />
        </div>
      }
    >
      <ErrorNote message={error} />
      <SuccessNote message={done} />
      <StatsCard />
      {rows === null ? (
        <div className="ad-sec-loading">
          <Spinner />
        </div>
      ) : rows.length === 0 ? (
        <p className="ad-mini-empty">لا طلبات هنا.</p>
      ) : (
        <div className="flex flex-col gap-8">
          {rows.map((row) => (
            <button
              key={row.id}
              type="button"
              className="rounded-12 border border-line bg-surface p-12 text-start"
              data-ticket-id={row.id}
              onClick={() => setOpen(row.id)}
            >
              <div className="flex flex-wrap items-center gap-8">
                <Badge tone={statusTone(row.status)}>{STATUS_LABEL[row.status]}</Badge>
                <Badge tone="muted">{KIND_LABEL[row.kind]}</Badge>
                {row.category ? <Badge tone="muted">{CATEGORY_LABEL[row.category]}</Badge> : null}
                {row.needs_staff && (row.status === "open" || row.status === "in_review") ? (
                  <Badge tone="warn">ينتظر ردّاً</Badge>
                ) : null}
              </div>
              <p className="mt-6 text-13 font-bold text-ink">
                {row.user_name ?? "—"} · {APP_LABEL[row.app] ?? row.app}
                {row.against_name ? ` ← ${row.against_name}` : ""}
              </p>
              <p className="text-11.5 text-muted">آخرُ رسالة {moment(row.last_message_at)}</p>
            </button>
          ))}
        </div>
      )}
      {open ? (
        <TicketDrawer
          ticketId={open}
          onClose={() => setOpen(null)}
          onChanged={() => {
            setDone("حُفظ.");
            void load();
          }}
        />
      ) : null}
    </Shell>
  );
}
