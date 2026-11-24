/** **حملةُ الإطلاق** (أمرُ المالك ٢٠٢٦-١١-٢٤ السادس، SPEC §١١٤-ج/د) — لافتةٌ بعدٍّ تنازليّ، **وإقرارُ «شريك الإطلاق» مرّةً واحدة**.
 *
 * النصّان من الخلفيّة بحرفهما (`banner` · `partner_notice`) — **فلا يفترق ما في التطبيق عمّا في اللوحة**. ومطفأةً لا يُرسم شيء.
 * والإقرارُ لا يُغلق إلا بالموافقة: هو شرطُ أن يعرف الكبتنُ قبل أوّل رحلةٍ أنه يتحمّل خصومَ عروض الركّاب في فترته المجّانية.
 */

import { useCallback, useEffect, useState } from "react";

import { acknowledgeLaunchPartner, getMyLaunchCampaign, type MyLaunchCampaign } from "@/api/endpoints";
import { tr } from "@/lib/i18n";
import { DISPLAY_LOCALE, digits } from "@/lib/utils";

function left(target: number, now: number): string {
  const ms = Math.max(0, target - now);
  const days = Math.floor(ms / 86_400_000);
  const hours = Math.floor((ms % 86_400_000) / 3_600_000);
  const minutes = Math.floor((ms % 3_600_000) / 60_000);
  return digits(tr("{0} يوم · {1} ساعة · {2} دقيقة", { 0: days, 1: hours, 2: minutes }));
}

export function LaunchCampaignT2() {
  const [data, setData] = useState<MyLaunchCampaign | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    getMyLaunchCampaign()
      .then(setData)
      .catch(() => undefined);
  }, []);
  useEffect(() => {
    load();
    const timer = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(timer);
  }, [load]);

  if (data === null || !data.enabled) return null;
  const launch = Date.parse(data.launch_at);
  const before = now < launch;

  const ack = async () => {
    setBusy(true);
    try {
      await acknowledgeLaunchPartner();
      load();
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      {data.show_banner ? (
        <section className="t2-wal-break" data-testid="launch-banner" aria-label={tr("حملة الإطلاق")}>
          <p className="t2-wal-line" style={{ fontWeight: 700 }}>
            <span>{data.banner}</span>
          </p>
          {before ? (
            <p className="t2-wal-hint">
              {tr("الإطلاق بعد {0}", { 0: left(launch, now) })}
            </p>
          ) : null}
          {data.status === "granted" && data.grant_ends_at ? (
            <p className="t2-wal-hint">
              {tr("فترتك المجّانية حتى {0}", {
                0: digits(new Date(data.grant_ends_at).toLocaleDateString(DISPLAY_LOCALE)),
              })}
            </p>
          ) : null}
        </section>
      ) : null}
      {data.ack_required ? (
        <div className="t2-of-dim" role="presentation">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="launch-ack-title"
            className="t2-wal-break"
            data-testid="launch-ack"
            style={{ position: "fixed", insetInline: 16, bottom: 24, zIndex: 60 }}
          >
            <h2 id="launch-ack-title" className="t2-wal-line" style={{ fontWeight: 700 }}>
              <span>{tr("شريك TAXO للإطلاق")}</span>
            </h2>
            <p className="t2-wal-hint">{data.partner_notice}</p>
            <button type="button" className="t2-hm-row" disabled={busy} onClick={() => void ack()}>
              <span className="t2-hm-row-main">
                <span className="t2-hm-row-title">{tr("قرأتُ وأوافق")}</span>
              </span>
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}
