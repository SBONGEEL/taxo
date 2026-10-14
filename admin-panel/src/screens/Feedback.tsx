/** **ملاحظاتُ المستخدمين** — ما يصل من زرِّ «أرسل ملاحظة» في التطبيقين (SPEC §٧٦/٤).
 *
 * **أربعةُ أسئلةٍ تجيبها كلُّ بطاقة**: مَن أرسل (الاسمُ والرقم) · أيُّ تطبيق · أيُّ إصدار (الغلافُ المثبَّت وحزمةُ الشاشات) · متى.
 * **والإصدارُ إصداران** لأن الشاشاتِ تُحمَّل من الخادم: ملاحظةٌ لا يُعرف من أيِّ حزمةٍ كُتبت لا يُعرف إن أُصلحت.
 *
 * **وزرٌّ واحدٌ يحمل القرار**: «عولجت» تنقلها من الجديدة، و«أعِدها جديدة» تعيدها — **وكلاهما يُدقَّق**. **والصورةُ تُجلب بالجلسة**
 * (`feedbackScreenshotBlob`) — لا عنوانَ لصورةِ شاشةِ أحدٍ يعمل بلا جلسة.
 */

import { useCallback, useEffect, useState } from "react";

import { feedbackScreenshotBlob, listFeedback, markFeedback } from "@/api/endpoints";
import type { AdminFeedback } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { Segmented } from "@/components/ui/Segmented";
import { moment } from "@/lib/format";
import { Icon } from "@/taxo2";

type FeedbackStatus = "new" | "handled" | "all";
type AppFilter = "any" | "rider" | "driver";

const PAGE = 50;

const APP_LABEL: Record<string, string> = {
  rider: "تطبيق الراكب",
  driver: "تطبيق الكبتن",
};

function Screenshot({ feedbackId }: { feedbackId: string }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let url: string | null = null;
    let alive = true;
    (async () => {
      try {
        url = await feedbackScreenshotBlob(feedbackId);
      } catch {
        return;
      }
      if (alive) setSrc(url);
      else {
        URL.revokeObjectURL(url);
        url = null;
      }
    })();
    return () => {
      alive = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [feedbackId]);
  return (
    <div className="ad-report-photo">
      {src ? (
        <a href={src} target="_blank" rel="noreferrer" aria-label="افتح صورة الشاشة كاملة">
          <img src={src} alt="صورةُ الشاشة المرفقة" />
        </a>
      ) : (
        <Icon name="image" />
      )}
    </div>
  );
}

export function FeedbackScreen() {
  const [status, setStatus] = useState<FeedbackStatus>("new");
  const [app, setApp] = useState<AppFilter>("any");
  const [rows, setRows] = useState<AdminFeedback[] | null>(null);
  const [total, setTotal] = useState(0);
  const [newCount, setNewCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(
    async (offset = 0) => {
      try {
        const page = await listFeedback({
          status,
          app: app === "any" ? undefined : app,
          limit: PAGE,
          offset,
        });
        setRows((current) => (offset === 0 || !current ? page.items : [...current, ...page.items]));
        setTotal(page.total);
        setNewCount(page.new_count);
      } catch (cause) {
        setError((cause as Error).message);
      }
    },
    [status, app],
  );

  useEffect(() => {
    setRows(null);
    void load(0);
  }, [load]);

  const toggle = async (row: AdminFeedback) => {
    setBusy(row.id);
    setError(null);
    setDone(null);
    try {
      await markFeedback(row.id, row.handled_at === null);
      setDone(row.handled_at === null ? "عُلِّمت معالَجة." : "أُعيدت إلى الجديدة.");
      await load(0);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <Shell
      title="ملاحظات المستخدمين"
      subtitle={`ما يصل من زرّ «أرسل ملاحظة» في التطبيقين — الجديدةُ ${newCount}`}
      actions={
        <div className="flex flex-wrap gap-8">
          <Segmented
            label="الحال"
            value={status}
            onPick={setStatus}
            options={[
              { key: "new", label: "جديدة" },
              { key: "handled", label: "معالَجة" },
              { key: "all", label: "الكلّ" },
            ]}
          />
          <Segmented
            label="التطبيق"
            value={app}
            onPick={setApp}
            options={[
              { key: "any", label: "الاثنان" },
              { key: "rider", label: "الراكب" },
              { key: "driver", label: "الكبتن" },
            ]}
          />
        </div>
      }
    >
      <div className="ad-reports-page">
        <ErrorNote message={error} />
        <SuccessNote message={done} />
        {rows === null ? (
          <div className="ad-sec-loading">
            <Spinner />
          </div>
        ) : null}
        {rows !== null && rows.length === 0 ? (
          <div className="ad-reports-empty">
            <p className="ad-empty-title">لا ملاحظات هنا.</p>
          </div>
        ) : null}
        {rows !== null && rows.length > 0 ? (
          <div className="ad-reports">
            {rows.map((row) => (
              <article key={row.id} className="ad-report" data-feedback-id={row.id}>
                {row.has_screenshot ? <Screenshot feedbackId={row.id} /> : null}
                <div className="ad-report-body">
                  <p className="ad-report-name">{row.user_name ?? "—"}</p>
                  <p dir="ltr" className="ad-report-line ad-ltr">
                    {row.user_phone ?? "—"}
                  </p>
                  <p className="ad-report-line">
                    {APP_LABEL[row.app] ?? row.app} · {moment(row.created_at)}
                  </p>
                  <p dir="ltr" className="ad-report-line ad-ltr">
                    {[row.app_version ?? "متصفّح", row.web_build, row.platform].filter(Boolean).join(" · ")}
                  </p>
                  {row.route ? (
                    <p dir="ltr" className="ad-report-line ad-ltr">
                      {row.route}
                    </p>
                  ) : null}
                  <p className="mt-8 whitespace-pre-wrap text-13 leading-relaxed text-ink">{row.message}</p>
                  <div className="ad-report-actions">
                    <Button
                      size="sm"
                      variant={row.handled_at === null ? "primary" : "secondary"}
                      disabled={busy === row.id}
                      onClick={() => void toggle(row)}
                    >
                      {row.handled_at === null ? "عولجت" : "أعِدها جديدة"}
                    </Button>
                    {row.handled_at ? <span className="ad-report-line">عولجت {moment(row.handled_at)}</span> : null}
                  </div>
                </div>
              </article>
            ))}
          </div>
        ) : null}
        {rows !== null && rows.length < total ? (
          <Button size="sm" variant="secondary" onClick={() => void load(rows.length)}>
            المزيد
          </Button>
        ) : null}
      </div>
    </Shell>
  );
}
