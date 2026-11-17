/** **«نغمة الإشعارات»** (أمرُ المالك ٢٠٢٦-١١-١٧، ج/١) — قائمةُ النغمات بزرِّ معاينةٍ لكلٍّ و«اهتزاز فقط»، **واختيارُ كلِّ مستخدمٍ له وحدَه**
 *  (`users.notification_tone` في الخلفية). **والافتراضيُّ الحاليُّ يبقى لكلِّ من لم يختر.** خلف مفتاح السوق
 *  `notification_tones_enabled` — مطفأً لا يُرسم شيء ولا تُطبَّق نغمة. */
import { useEffect, useState } from "react";

import { getNotificationPreferences, setNotificationTone } from "@/api/endpoints";
import { useFeature } from "@/lib/config";
import { tr } from "@/lib/i18n";
import { useSession } from "@/lib/session";
import { preview, setTone, type RingTone } from "@/lib/sound";
import { Icon } from "@/taxo2";

export const TONES_FLAG = "notification_tones_enabled";

const LABEL: Record<RingTone, string> = {
  default: "الافتراضيّة",
  s1_1: "نغمة 1",
  s1_2: "نغمة 2",
  s1_3: "نغمة 3",
  vibrate: "اهتزاز فقط",
};

/** **النغمةُ المحفوظةُ تُطبَّق عند كلِّ دخول** — الصوتُ في الويب، ونغمةُ الطلب الأصليّ في الغلاف (`applyNative`) */
export function ToneSync({ applyNative }: { applyNative?: (tone: RingTone, on: boolean) => void }): null {
  const { user } = useSession();
  const on = useFeature(user?.country_code, TONES_FLAG);
  useEffect(() => {
    if (!user || !on) {
      setTone("default");
      applyNative?.("default", false);
      return;
    }
    let cancelled = false;
    getNotificationPreferences()
      .then((prefs) => {
        if (cancelled) return;
        const tone = (prefs.notification_tone ?? "default") as RingTone;
        setTone(tone);
        applyNative?.(tone, true);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [user, on, applyNative]);
  return null;
}

export function NotificationTones({ applyNative, note }: { applyNative?: (tone: RingTone, on: boolean) => void; note?: string }) {
  const { user } = useSession();
  const on = useFeature(user?.country_code, TONES_FLAG);
  const [tones, setTones] = useState<RingTone[] | null>(null);
  const [chosen, setChosen] = useState<RingTone>("default");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!on) return;
    let cancelled = false;
    getNotificationPreferences()
      .then((prefs) => {
        if (cancelled) return;
        setTones(((prefs.tones ?? []) as RingTone[]).filter((tone) => tone in LABEL));
        setChosen((prefs.notification_tone ?? "default") as RingTone);
      })
      .catch(() => !cancelled && setTones([]));
    return () => {
      cancelled = true;
    };
  }, [on]);

  if (!on || !tones || tones.length === 0) return null;

  async function pick(tone: RingTone) {
    if (saving || tone === chosen) return;
    const before = chosen;
    setChosen(tone);
    setSaving(true);
    setError(null);
    try {
      await setNotificationTone(tone);
      setTone(tone);
      applyNative?.(tone, true);
    } catch {
      setChosen(before);
      setError(tr("تعذّر حفظ النغمة — حاول مرّةً أخرى."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="t2-tones" role="radiogroup" aria-label={tr("نغمة الإشعارات")}>
      <div className="t2-srow-title">{tr("نغمة الإشعارات")}</div>
      {note ? <p className="t2-srow-hint">{note}</p> : null}
      {tones.map((tone) => (
        <div key={tone} className="t2-srow">
          <button
            type="button"
            role="radio"
            aria-checked={chosen === tone}
            className="t2-tones-pick"
            disabled={saving}
            onClick={() => void pick(tone)}
          >
            <Icon name={chosen === tone ? "radio_button_checked" : "radio_button_unchecked"} />
            <span>{tr(LABEL[tone])}</span>
          </button>
          <button
            type="button"
            className="t2-tones-play"
            aria-label={tr("استمع إلى {0}", { 0: tr(LABEL[tone]) })}
            onClick={() => preview(tone)}
          >
            <Icon name={tone === "vibrate" ? "notifications" : "volume_up"} />
          </button>
        </div>
      ))}
      {error ? (
        <p className="t2-srow-error" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
