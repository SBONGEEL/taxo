/** **معاينةُ الإشعارات قبل الطرح** (SPEC §٨١ «قبل الطرح») — كلُّ نوعٍ كما يُرسم على الهاتف وفي المتصفّح وفي الجرس، وزرُّ صوته،
 * وزرٌّ يرسله **حقيقيّاً إلى أجهزتي وحدَها** بوسم «معاينة» ولا يُكتب منه شيء.
 *
 * **والنصُّ من الخادم** (`GET /admin/alerts/samples` ← `tray_text`) — الدالّةُ نفسُها التي تكتب سطرَ القفل، فلا تَعِد المعاينةُ بسطرٍ
 * لا يصل. **وصفُّ الجمع معه** («١٢ طلبَ رحلة») لأن الذروةَ شكلٌ يُوافَق عليه كما يُوافَق على الحدث المفرد.
 */

import { useEffect, useState } from "react";

import { alertCatalog, alertSamples, sendTestAlert } from "@/api/endpoints";
import type { AlertCatalog, AlertSample } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { Segmented } from "@/components/ui/Segmented";
import { AlertGlyph, playTone, TONE_META } from "@/lib/alerts";

function PhoneCard({ sample }: { sample: AlertSample }) {
  return (
    <div className="ad-alert-phone" data-tone={sample.tone}>
      <div className="ad-alert-phone-head">
        <span className="ad-alert-phone-mark" style={{ background: "#F05A28" }} aria-hidden="true">
          <img src="/icons/alerts/alert_badge.png" alt="" />
        </span>
        <span>TAXO المشرف · الآن</span>
      </div>
      <div className="ad-alert-phone-body">
        <div className="ad-alert-phone-text">
          <p className="ad-alert-title">{sample.title}</p>
          <p className="ad-alert-body">{sample.body}</p>
        </div>
        <img className="ad-alert-phone-large" src={TONE_META[sample.tone].image} alt="" />
      </div>
      <div className="ad-alert-phone-actions">
        <span>افتح</span>
        <span>مقروء</span>
      </div>
    </div>
  );
}

function DesktopCard({ sample }: { sample: AlertSample }) {
  return (
    <div className="ad-alert-desk" data-tone={sample.tone}>
      <img className="ad-alert-desk-icon" src={TONE_META[sample.tone].image} alt="" />
      <div className="ad-alert-desk-text">
        <p className="ad-alert-desk-app">admin.tajora.ly</p>
        <p className="ad-alert-title">{sample.title}</p>
        <p className="ad-alert-body">{sample.body}</p>
        <div className="ad-alert-desk-actions">
          <span>افتح</span>
          <span>مقروء</span>
        </div>
      </div>
    </div>
  );
}

export function AlertPreviewScreen() {
  const [catalog, setCatalog] = useState<AlertCatalog | null>(null);
  const [samples, setSamples] = useState<AlertSample[] | null>(null);
  const [grouped, setGrouped] = useState<"one" | "many">("one");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    void Promise.all([alertCatalog(), alertSamples()])
      .then(([kinds, rows]) => {
        setCatalog(kinds);
        setSamples(rows);
      })
      .catch((cause) => setError((cause as Error).message));
  }, []);

  const send = async (kind: string, count: number) => {
    setBusy(kind);
    setError(null);
    setDone(null);
    try {
      const answer = await sendTestAlert({ kind, count });
      const reached = answer.web + answer.phone;
      setDone(
        reached
          ? `أُرسل «${answer.title}» إلى ${reached} من أجهزتك (المتصفّح ${answer.web} · الهاتف ${answer.phone}).`
          : "لا جهازَ مسجَّلاً لك بعد — فعّل إشعاراتِ المتصفّح من صفحة الإعداد، أو ادخل من تطبيق الإدارة على الهاتف.",
      );
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const count = grouped === "one" ? 1 : 12;

  return (
    <Shell
      title="معاينة الإشعارات"
      subtitle="كلُّ نوعٍ كما يصل الهاتفَ والحاسوبَ ويُرى في الجرس — وصوتُه، وزرٌّ يرسله إلى أجهزتك وحدَها"
      actions={
        <Segmented
          label="الشكل"
          value={grouped}
          onPick={setGrouped}
          options={[
            { key: "one", label: "حدثٌ واحد" },
            { key: "many", label: "مجموعةٌ في الذروة" },
          ]}
        />
      }
    >
      <div className="ad-alert-page">
        <ErrorNote message={error} />
        <SuccessNote message={done} />
        {!catalog || !samples ? (
          <div className="ad-sec-loading">
            <Spinner />
          </div>
        ) : (
          catalog.categories.map((category) => (
            <section key={category.key} className="ad-alert-card">
              <h2 className="ad-alert-h2">{category.label}</h2>
              <div className="ad-alert-previews">
                {catalog.kinds
                  .filter((spec) => spec.category === category.key)
                  .map((spec) => {
                    const sample = samples.find((row) => row.kind === spec.kind && row.count === count);
                    if (!sample) return null;
                    return (
                      <article key={spec.kind} className="ad-alert-preview" data-kind={spec.kind}>
                        <div className="ad-alert-preview-head">
                          <AlertGlyph tone={spec.tone} size={32} />
                          <span className="ad-alert-preview-name">{spec.label}</span>
                          <span className="ad-alert-preview-tone">
                            {catalog.tones.find((tone) => tone.key === spec.tone)?.label}
                          </span>
                        </div>
                        <PhoneCard sample={sample} />
                        <DesktopCard sample={sample} />
                        <div className="ad-alert-preview-actions">
                          <Button size="sm" variant="secondary" onClick={() => playTone(spec.tone)}>
                            ▶ الصوت
                          </Button>
                          <Button size="sm" disabled={busy === spec.kind} onClick={() => void send(spec.kind, count)}>
                            أرسله إلى أجهزتي
                          </Button>
                        </div>
                      </article>
                    );
                  })}
              </div>
            </section>
          ))
        )}
      </div>
    </Shell>
  );
}
