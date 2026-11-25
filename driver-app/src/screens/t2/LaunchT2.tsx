/** **حملةُ الإطلاق** (أمرُ المالك ٢٠٢٦-١١-٢٤ السادس، SPEC §١١٤-ج/د) — لافتةٌ بعدٍّ تنازليّ، **وإقرارُ «شريك الإطلاق» مرّةً واحدة**.
 *
 * النصّان من الخلفيّة بحرفهما (`banner` · `partner_notice`) — **فلا يفترق ما في التطبيق عمّا في اللوحة**. ومطفأةً لا يُرسم شيء.
 * والإقرارُ شرطُ أن يعرف الكبتنُ قبل أوّل رحلةٍ أنه يتحمّل خصومَ عروض الركّاب في فترته المجّانية — **ولا يُطلب إلا ومفتاحُ قاعدته
 * مشتعل** (الخلفيّة). **وزرُّ إغلاقٍ ظاهرٌ فيه** يخفيه في هذه الجلسة ويعود في التالية ما دام لم يُوافَق (أمرُ المالك ٢٠٢٦-١١-٢٥:
 * كلُّ نافذةٍ فيها إغلاقٌ واضح).
 *
 * **والبطاقةُ بحافّتَي بطاقات الرئيسيّة وقطرها** (`t2-hm-card`) — كانت ملءَ العرض بلا هامشٍ فلصقت بـ«متجر المركبات» فوقها.
 * **والنافذةُ في `body` لا في الرئيسيّة** (`t2-hm-modal`): كانت داخل ستارٍ `absolute` بطبقة ١٩ **فغطّاها شريطُ التبويب (٣٠)**
 * ولم يقرأها الكبتن (قِيس على هاتفٍ حقيقيّ ٢٠٢٦-١١-٢٥). فهي فوق الشريط، وداخل حوافّ الأمان، **وتُمرَّر إن طالت**.
 */

import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { countOf, DAYS, HOURS, MINUTES } from "@/lib/arabic-count";

import { acknowledgeLaunchPartner, getMyLaunchCampaign, type MyLaunchCampaign } from "@/api/endpoints";
import { tr } from "@/lib/i18n";
import { DISPLAY_LOCALE, digits } from "@/lib/utils";
import { useBackLayer } from "@/lib/back-layers";
import { Icon } from "@/taxo2";

function left(target: number, now: number): string {
  const ms = Math.max(0, target - now);
  const days = Math.floor(ms / 86_400_000);
  const hours = Math.floor((ms % 86_400_000) / 3_600_000);
  const minutes = Math.floor((ms % 3_600_000) / 60_000);
  return [countOf(days, DAYS), countOf(hours, HOURS), countOf(minutes, MINUTES)].join(" · ");
}

export function LaunchCampaignT2() {
  const [data, setData] = useState<MyLaunchCampaign | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [busy, setBusy] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const asking = data !== null && data.enabled && data.ack_required && !dismissed;
  useBackLayer(asking, () => setDismissed(true));

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
        <section className="t2-wal-break t2-hm-card" data-testid="launch-banner" aria-label={tr("حملة الإطلاق")}>
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
      {asking
        ? createPortal(
            <div className="t2 t2-hm-modal" role="presentation">
              <div role="dialog" aria-modal="true" aria-labelledby="launch-ack-title" className="t2-hm-modal-card" data-testid="launch-ack">
                <button type="button" className="t2-hm-modal-x" aria-label={tr("إغلاق")} onClick={() => setDismissed(true)}>
                  <Icon name="close" />
                </button>
                <h2 id="launch-ack-title" className="t2-hm-modal-title">
                  {tr("شريك TAXO للإطلاق")}
                </h2>
                <div className="t2-hm-modal-body">
                  <p className="t2-wal-hint">{data.partner_notice}</p>
                </div>
                <button type="button" className="t2-hm-row" disabled={busy} onClick={() => void ack()}>
                  <span className="t2-hm-row-main">
                    <span className="t2-hm-row-title">{tr("قرأتُ وأوافق")}</span>
                  </span>
                </button>
              </div>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}
