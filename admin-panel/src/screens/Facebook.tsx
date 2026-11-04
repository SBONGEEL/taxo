/** قسمُ «فيسبوك» — قناةُ مراجعة منشورات صفحة «Taxo» (SPEC §٩٤/٢)، بصلاحيّة `facebook.manage`.
 *
 * **الموافقةُ تُجدوِل على فيسبوك نفسِه**: ينشر فيسبوك المنشورَ في موعده ولو لم تُفتح هذه الشاشة. **والمرفوضُ لا يُنشر أبداً.**
 * **وما صار على فيسبوك لا يُرفض من هنا** (قاعدةُ «لا يُحذف منشور») — يُعاد موعدُه فقط.
 *
 * **والمواعيدُ بتوقيت الجزائر** (UTC+1 بلا توقيتٍ صيفيّ): جمهورُ الصفحة الأوّل، وكلُّ موعدٍ اختاره المالكُ قيل به.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  addFacebookRequest,
  approveFacebookGroup,
  approveFacebookPost,
  closeFacebookRequest,
  decideFacebookPost,
  facebookMediaBlob,
  facebookReport,
  listFacebookPosts,
  listFacebookRequests,
  rescheduleFacebookPost,
  syncFacebook,
} from "@/api/endpoints";
import type { FacebookPost, FacebookPostRequest, FacebookPostStatus, FacebookReport } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { Segmented } from "@/components/ui/Segmented";
import { useFormError } from "@/lib/form-errors";
import { DISPLAY_LOCALE, digits } from "@/lib/utils";

const ZONE = "Africa/Algiers";

const STATUS: Record<FacebookPostStatus, { label: string; tone: "ok" | "warn" | "danger" | "muted" | "ink" }> = {
  pending_review: { label: "بانتظار المراجعة", tone: "warn" },
  changes_requested: { label: "طُلب تعديل", tone: "warn" },
  approved: { label: "موافَق — يُجدوَل الآن", tone: "ink" },
  scheduled: { label: "مجدول على فيسبوك", tone: "ink" },
  published: { label: "منشور", tone: "ok" },
  rejected: { label: "مرفوض", tone: "muted" },
  failed: { label: "فشلت الجدولة", tone: "danger" },
};

const LANG: Record<FacebookPost["lang"], string> = { ar: "فصحى", fr: "Français", dz: "دارجة", en: "English" };

type FacebookTab = "review" | "schedule" | "published" | "rejected" | "requests" | "report";

const TABS: { key: FacebookTab; label: string }[] = [
  { key: "review", label: "للمراجعة" },
  { key: "schedule", label: "المجدول" },
  { key: "published", label: "المنشور" },
  { key: "rejected", label: "المرفوض" },
  { key: "requests", label: "الطلبات" },
  { key: "report", label: "التقارير" },
];

const IN_TAB: Record<Exclude<FacebookTab, "requests" | "report">, FacebookPostStatus[]> = {
  review: ["pending_review", "changes_requested", "failed"],
  schedule: ["approved", "scheduled"],
  published: ["published"],
  rejected: ["rejected"],
};

/** موعدٌ بتوقيت الجزائر للعرض: «الجمعة ٦ نوفمبر 20:00» بأرقامٍ لاتينيّة */
function when(iso: string | null): string {
  if (!iso) return "بلا موعد";
  const at = new Date(iso);
  const dayPart = at.toLocaleDateString(DISPLAY_LOCALE, { weekday: "long", day: "numeric", month: "long", timeZone: ZONE });
  const time = at.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: ZONE });
  return digits(`${dayPart} ${time}`);
}

/** قيمةُ حقل `datetime-local` بتوقيت الجزائر ↔ ISO عالميّ. الجزائرُ UTC+1 طوالَ السنة */
function toLocalInput(iso: string | null): string {
  const at = iso ? new Date(iso) : new Date(Date.now() + 86400000);
  return new Date(at.getTime() + 3600000).toISOString().slice(0, 16);
}
function fromLocalInput(value: string): string {
  return new Date(new Date(`${value}:00Z`).getTime() - 3600000).toISOString();
}

function Media({ post }: { post: FacebookPost }) {
  const [src, setSrc] = useState<string | null>(post.media_count ? null : post.preview_url);
  useEffect(() => {
    if (!post.media_count) return;
    let url: string | null = null;
    facebookMediaBlob(post.id, 0)
      .then((u) => {
        url = u;
        setSrc(u);
      })
      .catch(() => setSrc(null));
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [post.id, post.media_count]);
  if (!src) return <div className="fb-media fb-media-empty">لا معاينة</div>;
  return post.media_types[0] === "video" ? (
    <video className="fb-media" src={src} controls preload="metadata" />
  ) : (
    <img className="fb-media" src={src} alt="" loading="lazy" />
  );
}

function PostCard({ post, onChanged }: { post: FacebookPost; onChanged: (p: FacebookPost, msg: string) => void }) {
  const [note, setNote] = useState("");
  const [at, setAt] = useState(toLocalInput(post.scheduled_at));
  const [open, setOpen] = useState<"note" | "time" | null>(null);
  const [busy, setBusy] = useState(false);
  const form = useFormError();
  const status = STATUS[post.status];
  const reviewable = ["pending_review", "changes_requested", "failed"].includes(post.status);
  const offFacebook = reviewable || post.status === "approved";
  const movable = !["published", "rejected"].includes(post.status);

  async function act(run: () => Promise<FacebookPost>, done: string) {
    setBusy(true);
    form.setMessage(null);
    try {
      const updated = await run();
      setOpen(null);
      onChanged(updated, done);
    } catch (caught) {
      form.capture(caught, "تعذّر الحفظ");
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="ad-card fb-card" dir="rtl">
      <Media post={post} />
      <div className="fb-body">
        <div className="fb-head">
          <strong className="fb-title">{post.title}</strong>
          <Badge tone={status.tone}>{status.label}</Badge>
          <Badge tone="muted">{LANG[post.lang]}</Badge>
          {post.kind !== "photo" && <Badge tone="muted">{post.kind === "video" ? "فيديو" : `دوّار · ${post.media_count}`}</Badge>}
        </div>
        <div className="fb-when">{when(post.scheduled_at)} — بتوقيت الجزائر</div>
        <p className="fb-caption" dir="auto">{post.caption}</p>
        {post.review_note && <p className="fb-note">ملاحظةُ المراجعة: {post.review_note}</p>}
        {post.last_error && <ErrorNote message={post.last_error} />}
        {post.status === "published" && (
          <div className="fb-stats">
            {digits(`إعجابات ${post.stats.reactions ?? 0} · تعليقات ${post.stats.comments ?? 0} · مشاركات ${post.stats.shares ?? 0}`)}
          </div>
        )}
        {post.permalink && (
          <a className="fb-link" href={post.permalink} target="_blank" rel="noreferrer">
            افتحه على فيسبوك
          </a>
        )}
        {form.message && <ErrorNote message={form.message} />}
        <div className="fb-actions">
          {reviewable && (
            <Button size="sm" loading={busy} onClick={() => act(() => approveFacebookPost(post.id), "وُوفق عليه، ويُجدوَل على فيسبوك الآن")}>
              موافقة
            </Button>
          )}
          {offFacebook && (
            <Button size="sm" variant="secondary" disabled={busy} onClick={() => setOpen(open === "note" ? null : "note")}>
              تعديل أو رفض
            </Button>
          )}
          {movable && (
            <Button size="sm" variant="ghost" disabled={busy} onClick={() => setOpen(open === "time" ? null : "time")}>
              تغيير الموعد
            </Button>
          )}
        </div>
        {open === "note" && (
          <div className="fb-panel">
            <textarea className="ad-input" rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder="ما الذي تريد تغييرَه؟" />
            <div className="fb-actions">
              <Button size="sm" variant="secondary" loading={busy}
                onClick={() => act(() => decideFacebookPost(post.id, "changes_requested", note), "أُرسل طلبُ التعديل")}>
                اطلب تعديلاً
              </Button>
              <Button size="sm" variant="danger" loading={busy}
                onClick={() => act(() => decideFacebookPost(post.id, "rejected", note), "رُفض — لن يُنشر")}>
                ارفض
              </Button>
            </div>
          </div>
        )}
        {open === "time" && (
          <div className="fb-panel">
            <input className="ad-input" type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} />
            <Button size="sm" loading={busy}
              onClick={() => act(() => rescheduleFacebookPost(post.id, fromLocalInput(at)), "تغيّر الموعد")}>
              احفظ الموعد
            </Button>
          </div>
        )}
      </div>
    </article>
  );
}

function Requests() {
  const [rows, setRows] = useState<FacebookPostRequest[] | null>(null);
  const [body, setBody] = useState("");
  const [count, setCount] = useState("");
  const [busy, setBusy] = useState(false);
  const form = useFormError();
  const load = useCallback(async () => setRows(await listFacebookRequests()), []);
  useEffect(() => {
    load().catch((c) => form.capture(c, "تعذّرت قراءة الطلبات"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  async function send() {
    setBusy(true);
    try {
      await addFacebookRequest(body, count ? Number(count) : null);
      setBody("");
      setCount("");
      await load();
    } catch (c) {
      form.capture(c, "تعذّر إرسالُ الطلب");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fb-requests">
      <div className="ad-card fb-panel">
        <strong>اطلب منشوراتٍ جديدة</strong>
        <textarea className="ad-input" rows={4} value={body} onChange={(e) => setBody(e.target.value)}
          placeholder="مثلاً: ثلاثةُ منشوراتٍ عن رحلات المطار، بالفصحى والدارجة" />
        <input className="ad-input" inputMode="numeric" value={count} onChange={(e) => setCount(e.target.value.replace(/\D/g, ""))}
          placeholder="العدد (اختياريّ)" />
        {form.message && <ErrorNote message={form.message} />}
        <Button size="sm" loading={busy} disabled={!body.trim()} onClick={send}>أرسل الطلب</Button>
      </div>
      {(rows ?? []).map((r) => (
        <div key={r.id} className="ad-card fb-panel">
          <div className="fb-head">
            <Badge tone={r.status === "open" ? "warn" : "ok"}>{r.status === "open" ? "مفتوح" : "منجَز"}</Badge>
            {r.count && <Badge tone="muted">{digits(String(r.count))} منشورات</Badge>}
          </div>
          <p className="fb-caption">{r.body}</p>
          {r.answer && <p className="fb-note">الردّ: {r.answer}</p>}
          {r.status === "open" && (
            <Button size="sm" variant="ghost" onClick={() => closeFacebookRequest(r.id, "").then(load)}>علّمه منجَزاً</Button>
          )}
        </div>
      ))}
    </div>
  );
}

function Report() {
  const [data, setData] = useState<FacebookReport | null>(null);
  const form = useFormError();
  useEffect(() => {
    facebookReport().then(setData).catch((c) => form.capture(c, "تعذّرت قراءة التقرير"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  if (form.message) return <ErrorNote message={form.message} />;
  if (!data) return <p>…</p>;
  const tiles: [string, number | string][] = [
    ["المتابعون", data.page?.followers_count ?? "—"],
    ["نُشر هذا الأسبوع", data.published_this_week],
    ["مجدولٌ قادم", data.upcoming],
    ["بانتظار المراجعة", data.by_status.pending_review ?? 0],
    ["الإعجابات", data.totals.reactions],
    ["التعليقات", data.totals.comments],
    ["المشاركات", data.totals.shares],
  ];
  return (
    <div className="fb-report">
      {data.page_error && <ErrorNote message={data.page_error} />}
      <div className="fb-tiles">
        {tiles.map(([label, value]) => (
          <div key={label} className="ad-card fb-tile">
            <span>{label}</span>
            <strong>{digits(String(value))}</strong>
          </div>
        ))}
      </div>
      <div className="ad-card fb-panel">
        <strong>الأكثرُ تفاعلاً</strong>
        {data.top.length === 0 && <p>لا منشورَ منشورٌ بعد.</p>}
        {data.top.map((t) => (
          <div key={t.id} className="fb-top">
            {t.permalink ? <a href={t.permalink} target="_blank" rel="noreferrer">{t.title}</a> : t.title}
            <span>{digits(`${t.stats.reactions ?? 0} · ${t.stats.comments ?? 0} · ${t.stats.shares ?? 0}`)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function FacebookScreen() {
  const [tab, setTab] = useState<FacebookTab>("review");
  const [rows, setRows] = useState<FacebookPost[] | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const form = useFormError();

  const load = useCallback(async () => setRows(await listFacebookPosts()), []);
  useEffect(() => {
    load().catch((c) => form.capture(c, "تعذّرت قراءة المنشورات"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  const shown = useMemo(() => {
    if (!rows || tab === "requests" || tab === "report") return [];
    const list = rows.filter((p) => IN_TAB[tab].includes(p.status));
    return tab === "published" ? [...list].reverse() : list;
  }, [rows, tab]);

  /** مجموعاتٌ فيها ما ينتظر المراجعة — موافقةٌ جماعيّةٌ بضغطة */
  const groups = useMemo(() => {
    const keys = new Map<string, number>();
    for (const p of rows ?? []) {
      if (p.group_key && IN_TAB.review.includes(p.status)) keys.set(p.group_key, (keys.get(p.group_key) ?? 0) + 1);
    }
    return [...keys.entries()];
  }, [rows]);

  const count = (t: Exclude<FacebookTab, "requests" | "report">) => (rows ?? []).filter((p) => IN_TAB[t].includes(p.status)).length;

  function changed(updated: FacebookPost, message: string) {
    setRows((prev) => (prev ?? []).map((p) => (p.id === updated.id ? updated : p)));
    setDone(message);
  }

  async function sync() {
    setBusy(true);
    form.setMessage(null);
    try {
      const r = await syncFacebook();
      await load();
      setDone(digits(`تمّت المزامنة: ${r.imported} جديد، ${r.updated} محدَّث`));
    } catch (c) {
      form.capture(c, "تعذّرت المزامنة");
    } finally {
      setBusy(false);
    }
  }

  async function approveGroup(key: string) {
    setBusy(true);
    try {
      const r = await approveFacebookGroup(key);
      await load();
      setDone(digits(`وُوفق على ${r.length} منشورات، وتُجدوَل الآن`));
    } catch (c) {
      form.capture(c, "تعذّرت الموافقة الجماعيّة");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell
      title="فيسبوك"
      subtitle="صفحة Taxo — المراجعةُ والجدولُ والتقارير"
      actions={<Button size="sm" variant="secondary" loading={busy} onClick={sync}>مزامنة مع فيسبوك</Button>}
    >
      <style>{CSS}</style>
      <Segmented
        label="الأقسام"
        value={tab}
        onPick={(t) => {
          setTab(t);
          setDone(null);
        }}
        options={TABS.map((t) => ({
          key: t.key,
          label: t.key === "requests" || t.key === "report" ? t.label : digits(`${t.label} (${count(t.key)})`),
        }))}
      />
      {done && <SuccessNote message={done} />}
      {form.message && <ErrorNote message={form.message} />}
      {tab === "review" && groups.length > 0 && (
        <div className="fb-groups">
          {groups.map(([key, n]) => (
            <Button key={key} size="sm" variant="secondary" disabled={busy} onClick={() => approveGroup(key)}>
              {digits(`وافق على مجموعة «${key}» كلِّها (${n})`)}
            </Button>
          ))}
        </div>
      )}
      {tab === "requests" && <Requests />}
      {tab === "report" && <Report />}
      {tab !== "requests" && tab !== "report" && (
        <div className="fb-list">
          {rows === null && <p>…</p>}
          {rows !== null && shown.length === 0 && <p className="fb-empty">لا شيءَ هنا الآن.</p>}
          {shown.map((p) => (
            <PostCard key={p.id} post={p} onChanged={changed} />
          ))}
        </div>
      )}
    </Shell>
  );
}

const CSS = `
.fb-list{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));margin-top:12px}
.fb-card{display:flex;flex-direction:column;overflow:hidden;padding:0}
.fb-media{width:100%;aspect-ratio:4/5;object-fit:cover;background:#111;display:block}
.fb-media-empty{display:flex;align-items:center;justify-content:center;color:#888;aspect-ratio:3/1}
.fb-body{padding:12px;display:flex;flex-direction:column;gap:8px}
.fb-head{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.fb-title{font-size:15px;margin-inline-end:auto}
.fb-when{font-size:13px;opacity:.8}
.fb-caption{white-space:pre-wrap;font-size:14px;margin:0;max-height:9em;overflow:auto}
.fb-note{font-size:13px;margin:0;opacity:.85}
.fb-stats{font-size:13px}
.fb-link{font-size:13px}
.fb-actions{display:flex;flex-wrap:wrap;gap:8px}
.fb-panel{display:flex;flex-direction:column;gap:8px;padding:12px}
.fb-groups{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
.fb-requests,.fb-report{display:grid;gap:12px;margin-top:12px}
.fb-tiles{display:grid;gap:8px;grid-template-columns:repeat(auto-fill,minmax(140px,1fr))}
.fb-tile{display:flex;flex-direction:column;gap:4px;padding:12px}
.fb-tile strong{font-size:22px}
.fb-top{display:flex;justify-content:space-between;gap:8px;font-size:14px}
.fb-empty{opacity:.7}
@media (max-width:480px){.fb-list{grid-template-columns:1fr}}
`;
