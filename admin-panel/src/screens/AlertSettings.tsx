/** **إعدادُ الإشعارات** (SPEC §٨١/٤ و١٢) — كلُّ حدثٍ لكلِّ قناة (اللوحة · المتصفّح · الهاتف)، وصوتُ كلِّ فئة. **والافتراضُ: الكلُّ مشغَّل.**
 *
 * **والصوتُ صوتان، ويُقال ذلك هنا** (شرطُ المالك ١٢): واللوحةُ مفتوحةٌ يُعزف صوتُ الفئة بإعدادها أدناه؛ **ومغلقةً يعزف المتصفّحُ صوتَ
 * النظام** — فالمتصفّحُ لا يعزف ملفّاً لإشعارٍ واللسانُ مغلق. **وعلى الهاتف كلُّ فئةٍ قناةٌ مستقلّة** يُضبط صوتُها واهتزازُها من
 * إعدادات أندرويد للتطبيق.
 */

import { useEffect, useState } from "react";

import { alertCatalog, saveAlertSettings } from "@/api/endpoints";
import type { AlertCatalog, AlertChannel, AlertSettings, AlertTone } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { Switch } from "@/components/ui/Field";
import { browserAlertsState, enableBrowserAlerts, type BrowserAlertsState } from "@/lib/alert-push";
import { AlertGlyph, playTone, TONE_META, useAlertFeed } from "@/lib/alerts";
import { useConfig } from "@/lib/config";

const CHANNEL_LABEL: Record<AlertChannel, string> = {
  panel: "اللوحة",
  web: "المتصفّح",
  phone: "الهاتف",
};

const BROWSER_STATE: Record<BrowserAlertsState, string> = {
  granted: "مفعَّلة على هذا المتصفّح — تصل واللسانُ مغلق.",
  default: "لم تُفعَّل بعد على هذا المتصفّح.",
  denied: "رفضها المتصفّح — تُفعَّل من إعدادات الموقع في المتصفّح (رمزُ القفل بجانب العنوان).",
  unsupported: "هذا المتصفّح أو التطبيق لا يدعم إشعاراتِ الويب — والهاتفُ يصله الإشعارُ من تطبيق الإدارة.",
  unconfigured: "عقدُ الإشعارات (FCM) لا يحمل مفاتيحَ الويب بعد — من «عقود مزوّدي API».",
};

export function AlertSettingsScreen() {
  const feed = useAlertFeed();
  const { config } = useConfig();
  const [catalog, setCatalog] = useState<AlertCatalog | null>(null);
  const [draft, setDraft] = useState<AlertSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [browser, setBrowser] = useState<BrowserAlertsState>(() => browserAlertsState(config?.providers.fcm));

  useEffect(() => {
    void alertCatalog().then(setCatalog).catch((cause) => setError((cause as Error).message));
  }, []);

  useEffect(() => {
    if (feed?.settings && !draft) setDraft(feed.settings);
  }, [feed?.settings, draft]);

  useEffect(() => {
    setBrowser(browserAlertsState(config?.providers.fcm));
  }, [config]);

  const setChannel = (kind: string, channel: AlertChannel, on: boolean) =>
    setDraft((current) =>
      current ? { ...current, kinds: { ...current.kinds, [kind]: { ...current.kinds[kind], [channel]: on } } } : current,
    );

  const setSound = (tone: AlertTone, on: boolean) =>
    setDraft((current) => (current ? { ...current, sounds: { ...current.sounds, [tone]: on } } : current));

  const save = async () => {
    if (!draft) return;
    setBusy(true);
    setError(null);
    setDone(null);
    try {
      const saved = await saveAlertSettings(draft);
      feed?.setSettings(saved);
      setDraft(saved);
      setDone("حُفظ الإعداد.");
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const enableBrowser = async () => {
    setError(null);
    try {
      setBrowser(await enableBrowserAlerts(config?.providers.fcm, { ask: true }));
    } catch (cause) {
      setError((cause as Error).message);
    }
  };

  const ready = catalog && draft;

  return (
    <Shell
      title="إعداد الإشعارات"
      subtitle="كلُّ حدثٍ لكلِّ قناة، وصوتُ كلِّ فئة — والافتراضُ: الكلُّ مشغَّل"
      actions={
        <Button size="sm" disabled={!ready || busy} onClick={() => void save()}>
          حفظ
        </Button>
      }
    >
      <div className="ad-alert-page">
        <ErrorNote message={error} />
        <SuccessNote message={done} />
        {!ready ? (
          <div className="ad-sec-loading">
            <Spinner />
          </div>
        ) : (
          <>
            <section className="ad-alert-card">
              <h2 className="ad-alert-h2">إشعاراتُ الحاسوب</h2>
              <p className="ad-alert-note">{BROWSER_STATE[browser]}</p>
              {browser === "default" ? (
                <Button size="sm" onClick={() => void enableBrowser()}>
                  فعّل إشعاراتِ المتصفّح
                </Button>
              ) : null}
              <p className="ad-alert-note">
                <strong>واللوحةُ مفتوحة</strong> يُعزف صوتُ الفئة أدناه. <strong>ومغلقةً</strong> يعزف المتصفّحُ صوتَ النظام —
                فالمتصفّحُ لا يعزف ملفّاً لإشعارٍ واللسانُ مغلق.
              </p>
              <p className="ad-alert-note">
                <strong>وعلى الهاتف</strong> كلُّ فئةٍ قناةٌ مستقلّة: صوتُها واهتزازُها من إعدادات أندرويد ← التطبيقات ← TAXO المشرف
                ← الإشعارات.
              </p>
            </section>

            <section className="ad-alert-card">
              <h2 className="ad-alert-h2">الأصوات واللوحةُ مفتوحة</h2>
              <div className="ad-alert-tones">
                {catalog.tones.map((tone) => (
                  <div key={tone.key} className="ad-alert-tone">
                    <AlertGlyph tone={tone.key} size={36} />
                    <span className="ad-alert-tone-name">{tone.label}</span>
                    <button
                      type="button"
                      className="ad-round ad-alert-play"
                      aria-label={`استمع: ${tone.label}`}
                      onClick={() => playTone(tone.key)}
                    >
                      ▶
                    </button>
                    <Switch
                      checked={draft.sounds[tone.key] !== false}
                      onChange={(on) => setSound(tone.key, on)}
                      label={`صوت ${tone.label}`}
                    />
                  </div>
                ))}
              </div>
            </section>

            {catalog.categories.map((category) => (
              <section key={category.key} className="ad-alert-card">
                <h2 className="ad-alert-h2">{category.label}</h2>
                <div className="ad-alert-matrix" role="table" aria-label={category.label}>
                  <div className="ad-alert-matrix-row head" role="row">
                    <span role="columnheader">الحدث</span>
                    {catalog.channels.map((channel) => (
                      <span key={channel} role="columnheader">
                        {CHANNEL_LABEL[channel]}
                      </span>
                    ))}
                  </div>
                  {catalog.kinds
                    .filter((spec) => spec.category === category.key)
                    .map((spec) => (
                      <div key={spec.kind} className="ad-alert-matrix-row" role="row">
                        <span role="cell" className="ad-alert-matrix-kind">
                          <span className="ad-alert-swatch" style={{ background: TONE_META[spec.tone].color }} />
                          {spec.label}
                        </span>
                        {catalog.channels.map((channel) => (
                          <span key={channel} role="cell">
                            <Switch
                              checked={draft.kinds[spec.kind]?.[channel] !== false}
                              onChange={(on) => setChannel(spec.kind, channel, on)}
                              label={`${spec.label} — ${CHANNEL_LABEL[channel]}`}
                            />
                          </span>
                        ))}
                      </div>
                    ))}
                </div>
              </section>
            ))}
          </>
        )}
      </div>
    </Shell>
  );
}
