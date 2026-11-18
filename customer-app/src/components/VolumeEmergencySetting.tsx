/** **إعدادُ «زرّ الصوت للطوارئ»** (SPEC §١٠٣ B/22) — الراكبُ يشعله ويختار جهتَه بنفسه؛ **وشرحٌ بالعربيّة قبل الإشعال** يقول ما
 *  سيحدث بالضبط. والجهةُ تُحفظ على هذا الجهاز وحدَه. ويُرسم حيث يشتعل `volume_emergency` لدولته وفي التطبيق المثبَّت وحدَه. */
import { useState } from "react";
import { Capacitor } from "@capacitor/core";

import type { CountryCode } from "@/api/types";
import { useFeature } from "@/lib/config";
import { tr } from "@/lib/i18n";
import {
  normalizeContact,
  setVolumeEmergency,
  volumeEmergencyChosen,
  volumeEmergencyContact,
} from "@/lib/volume-emergency";
import { Icon, Switch } from "@/taxo2";

export function VolumeEmergencySetting({ country }: { country: CountryCode | undefined }) {
  const on = useFeature(country, "volume_emergency");
  const [enabled, setEnabled] = useState(volumeEmergencyChosen);
  const [contact, setContact] = useState(() => volumeEmergencyContact() ?? "");
  const [explained, setExplained] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!on || !Capacitor.isNativePlatform()) return null;

  const save = (next: boolean) => {
    const number = normalizeContact(contact);
    if (next && !number) {
      setError(tr("اكتب رقم الجهة كاملاً بمفتاح الدولة، مثل +962791234567"));
      return;
    }
    setError(null);
    setVolumeEmergency(next, number);
    setEnabled(next);
  };

  return (
    <section>
      <div className="t2-group">{tr("الأمان")}</div>
      <div className="t2-list t2-sgroup">
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          aria-label={tr("زرّ الصوت للطوارئ")}
          className="t2-srow"
          onClick={() => (enabled ? save(false) : setExplained(true))}
        >
          <Icon name="shield" className="t2-srow-icon" />
          <span className="t2-srow-main">
            <span className="t2-srow-title">{tr("زرّ الصوت للطوارئ")}</span>
            <span className="t2-srow-hint">
              {tr("اضغط «خفض الصوت» ثلاث مرّات سريعاً أثناء الرحلة والتطبيق مفتوح.")}
            </span>
          </span>
          <Switch on={enabled} />
        </button>
        {explained || enabled ? (
          <div className="t2-srow">
            <span className="t2-srow-main">
              {!enabled ? (
                <span className="t2-srow-hint">
                  {tr(
                    "عند الضغطة الثالثة: نُنبّه فريق TAXO فوراً بموقعك وبيانات الرحلة، ونفتح لك رسالةً جاهزةً إلى الجهة التي تختارها فيها رابطُ موقعك المباشر ولوحةُ السيارة — وتضغط أنت «إرسال». رقمُ الجهة يبقى على هاتفك ولا يصلنا.",
                  )}
                </span>
              ) : null}
              <input
                className="t2-input"
                type="tel"
                dir="ltr"
                inputMode="tel"
                placeholder="+962791234567"
                aria-label={tr("رقم الجهة")}
                value={contact}
                onChange={(event) => setContact(event.target.value)}
                onBlur={() => (enabled ? save(true) : undefined)}
              />
              {!enabled ? (
                <button type="button" className="t2-btn ember" onClick={() => save(true)}>
                  {tr("فعّل")}
                </button>
              ) : null}
              {error ? (
                <p className="t2-srow-error" role="alert">
                  {error}
                </p>
              ) : null}
            </span>
          </div>
        ) : null}
      </div>
    </section>
  );
}
