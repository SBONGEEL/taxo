/** **طلباتي** (أمرُ المالك ٢٠٢٦-١١-١٠، البندان ٨ و٩) — «محادثة مع الدعم» و«نسيت شيئاً في السيارة» و«شكوى على هذه الرحلة».
 *
 * **ملفٌّ واحدٌ في التطبيقين** بفرق `APP` وحدَه. **بلا أرقام هواتف**: خيطُ المفقودات يجمع الراكبَ والكبتنَ وفريقَ الدعم، والخلفيّةُ
 * ترفض رقماً أو رابطاً فيه. **والحالُ والقرارُ وسببُه** كما تصل من الخلفيّة، وكلُّ تغييرٍ يصل إشعاراً يفتح هذا الخيط.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import {
  getMyTicket,
  listMyTickets,
  openTicket,
  postTicketMessage,
  type MyTicket,
  type MyTicketDetail,
  type TicketKind,
} from "@/api/endpoints";
import { useGoBack } from "@/lib/back";
import { tr } from "@/lib/i18n";
import { DISPLAY_LOCALE } from "@/lib/utils";

import "./support.css";

const APP: "rider" | "driver" = "rider";

const KIND_LABEL: Record<TicketKind, string> = {
  support: "محادثة مع الدعم",
  lost_item: "غرضٌ نسيته في السيارة",
  complaint: "شكوى على رحلة",
};

const STATUS_LABEL: Record<string, string> = {
  open: "مفتوح",
  in_review: "قيد المراجعة",
  resolved: "محسوم",
  rejected: "مُغلق",
};

const CATEGORIES: { key: string; label: string; apps: ("rider" | "driver")[] }[] = [
  { key: "behavior", label: "السلوك", apps: ["rider", "driver"] },
  { key: "vehicle", label: "السيارة", apps: ["rider"] },
  { key: "route", label: "المسار", apps: ["rider"] },
  { key: "fare", label: "الأجرة والدفع", apps: ["rider", "driver"] },
  { key: "safety", label: "السلامة", apps: ["rider", "driver"] },
  { key: "other", label: "أخرى", apps: ["rider", "driver"] },
];

function when(iso: string): string {
  return new Intl.DateTimeFormat(DISPLAY_LOCALE, { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
}

function authorLabel(role: string, mine: "user" | "party"): string {
  if (role === "staff") return tr("فريق الدعم");
  if (role === mine) return tr("أنت");
  return role === "party" ? tr("الكبتن") : tr("الراكب");
}

function Head({ title }: { title: string }) {
  const goBack = useGoBack("/");
  return (
    <div className="t2-head">
      <button type="button" className="t2-back" aria-label={tr("رجوع")} onClick={goBack}>
        <span className="t2-icon" aria-hidden="true">
          arrow_forward
        </span>
      </button>
      <h1 className="t2-title">{title}</h1>
    </div>
  );
}

export function SupportListT2() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<MyTicket[] | null>(null);
  const [composing, setComposing] = useState(false);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listMyTickets()
      .then(setRows)
      .catch((cause: Error) => setError(cause.message));
  }, []);

  const send = async () => {
    setBusy(true);
    setError(null);
    try {
      const ticket = await openTicket({ app: APP, kind: "support", body: body.trim() }, null);
      navigate(`/support/${ticket.id}`, { replace: true });
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="sp-page">
      <Head title={tr("طلباتي ومحادثات الدعم")} />
      <div className="sp-body">
        {composing ? (
          <div className="sp-card">
            <label className="sp-label" htmlFor="sp-new">
              {tr("اكتب سؤالك أو مشكلتك — يردّ عليك فريقُ الدعم هنا")}
            </label>
            <textarea id="sp-new" className="sp-text" rows={4} maxLength={2000} value={body} onChange={(e) => setBody(e.target.value)} />
            <button type="button" className="t2-cta sp-cta" disabled={busy || !body.trim()} onClick={() => void send()}>
              {busy ? "…" : tr("أرسل")}
            </button>
          </div>
        ) : (
          <button type="button" className="t2-cta sp-cta" onClick={() => setComposing(true)}>
            {tr("محادثة جديدة مع الدعم")}
          </button>
        )}
        {error ? (
          <p className="t2-note danger" role="alert">
            {error}
          </p>
        ) : null}
        {rows !== null && rows.length === 0 ? <p className="t2-empty">{tr("لا طلبات بعد.")}</p> : null}
        <div className="t2-list">
          {(rows ?? []).map((row) => (
            <button key={row.id} type="button" className="t2-row sp-row" onClick={() => navigate(`/support/${row.id}`)}>
              <span className="t2-row-main">
                <span className="t2-row-title">{tr(KIND_LABEL[row.kind])}</span>
                <span className="t2-row-when">
                  {tr(STATUS_LABEL[row.status] ?? row.status)} · {when(row.last_message_at)}
                </span>
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export function SupportThreadT2() {
  const { ticketId = "" } = useParams();
  const [data, setData] = useState<MyTicketDetail | null>(null);
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    getMyTicket(ticketId)
      .then(setData)
      .catch((cause: Error) => setError(cause.message));
  }, [ticketId]);

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 30_000);
    return () => window.clearInterval(timer);
  }, [load]);

  const send = async () => {
    setBusy(true);
    setError(null);
    try {
      setData(await postTicketMessage(ticketId, body.trim()));
      setBody("");
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const active = data ? data.status === "open" || data.status === "in_review" : false;
  return (
    <div className="sp-page">
      <Head title={data ? tr(KIND_LABEL[data.kind]) : "…"} />
      <div className="sp-body">
        {data ? (
          <p className="sp-status">
            {tr(STATUS_LABEL[data.status] ?? data.status)}
            {data.decision_reason ? ` — ${data.decision_reason}` : ""}
          </p>
        ) : null}
        {data?.kind === "lost_item" ? <p className="sp-hint">{tr("التواصلُ هنا وحدَه — بلا أرقام هواتف، وفريقُ الدعم يرى المحادثة.")}</p> : null}
        <ol className="sp-thread">
          {(data?.messages ?? []).map((message) => (
            <li key={message.id} className={message.author_role === data?.my_role ? "sp-msg mine" : "sp-msg"}>
              <span className="sp-who">
                {authorLabel(message.author_role, data!.my_role)} · {when(message.created_at)}
              </span>
              <span className="sp-said">{message.body}</span>
            </li>
          ))}
        </ol>
        {error ? (
          <p className="t2-note danger" role="alert">
            {error}
          </p>
        ) : null}
        {active ? (
          <div className="sp-card">
            <textarea
              className="sp-text"
              rows={3}
              maxLength={2000}
              aria-label={tr("رسالتك")}
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
            <button type="button" className="t2-cta sp-cta" disabled={busy || !body.trim()} onClick={() => void send()}>
              {busy ? "…" : tr("أرسل")}
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function ReportRideT2() {
  const { rideId = "" } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const kind: TicketKind = params.get("kind") === "lost_item" && APP === "rider" ? "lost_item" : "complaint";
  const [category, setCategory] = useState<string | null>(null);
  const [body, setBody] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const send = async () => {
    setBusy(true);
    setError(null);
    try {
      const ticket = await openTicket(
        { app: APP, kind, body: body.trim(), ride_id: rideId, category: kind === "complaint" ? category ?? undefined : undefined },
        kind === "complaint" ? photo : null,
      );
      navigate(`/support/${ticket.id}`, { replace: true });
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const ready = body.trim().length > 0 && (kind !== "complaint" || category !== null);
  return (
    <div className="sp-page">
      <Head title={kind === "lost_item" ? tr("نسيت شيئاً في السيارة") : tr("شكوى على هذه الرحلة")} />
      <div className="sp-body">
        {kind === "lost_item" ? (
          <p className="sp-hint">{tr("صِف ما نسيته — يصل الكبتنَ وفريقَ الدعم، ويردّون عليك هنا بلا أرقام هواتف.")}</p>
        ) : (
          <div className="sp-chips" role="radiogroup" aria-label={tr("نوع الشكوى")}>
            {CATEGORIES.filter((item) => item.apps.includes(APP)).map((item) => (
              <button
                key={item.key}
                type="button"
                role="radio"
                aria-checked={category === item.key}
                className={category === item.key ? "t2-chip sp-chip on" : "t2-chip sp-chip"}
                onClick={() => setCategory(item.key)}
              >
                {tr(item.label)}
              </button>
            ))}
          </div>
        )}
        <div className="sp-card">
          <label className="sp-label" htmlFor="sp-report">
            {kind === "lost_item" ? tr("ما الذي نسيته؟ وأين كان في السيارة؟") : tr("ماذا حدث؟")}
          </label>
          <textarea id="sp-report" className="sp-text" rows={5} maxLength={2000} value={body} onChange={(e) => setBody(e.target.value)} />
          {kind === "complaint" ? (
            <label className="sp-photo">
              <span>{photo ? photo.name : tr("أرفق صورة (اختياري)")}</span>
              <input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} />
            </label>
          ) : null}
          <button type="button" className="t2-cta sp-cta" disabled={busy || !ready} onClick={() => void send()}>
            {busy ? "…" : tr("أرسل")}
          </button>
        </div>
        {error ? (
          <p className="t2-note danger" role="alert">
            {error}
          </p>
        ) : null}
      </div>
    </div>
  );
}
