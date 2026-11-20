/** **إعداداتُ الفقاعة** (البند ٥٥ و٤٧ و٥٤ من أمر المالك ٢٠/١١ الرابع، SPEC §١١٠) — الحجمُ والشفافيّةُ والالتصاقُ بالحافة،
 * وهدفُ اليوم، و«قبول/رفض بالصوت».
 *
 * **تظهر حيث تعمل الفقاعةُ الجديدة وحدَها** (`bubble_radial_menu` لدولته وغلافٍ يحملها) — مطفأةً لا قسمَ ولا وعد. **والهدفُ رقمٌ يكتبه
 * الكبتنُ لنفسه ويُقارن للعرض** — لا يمسّ أجرةً ولا عمولة. **والصوتُ لا يُسمع إلا وطلبُ الرحلة ظاهر**، والميكروفونُ يُطلب حين يُشعله
 * هو لا قبل. والإخفاءُ بالسحب إلى ✕ أسفل الشاشة، والاختفاءُ والتطبيقُ مفتوح — كلاهما في الفقاعة نفسِها لا هنا.
 */
import { useState } from "react";

import type { CountryCode } from "@/api/types";
import { useFeature } from "@/lib/config";
import { readSettings, saveSettings, type BubbleAlpha, type BubbleSettings, type BubbleSize } from "@/lib/bubble-bridge";
import { askPermission } from "@/lib/permissions-center";
import { tr } from "@/lib/i18n";

const SIZES: { value: BubbleSize; label: string }[] = [
  { value: "s", label: "صغيرة" },
  { value: "m", label: "متوسّطة" },
  { value: "l", label: "كبيرة" },
];
const ALPHAS: { value: BubbleAlpha; label: string }[] = [
  { value: "100", label: "واضحة" },
  { value: "80", label: "80%" },
  { value: "60", label: "60%" },
];

function Choice<T extends string>({
  label,
  value,
  options,
  onPick,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onPick: (value: T) => void;
}) {
  return (
    <div className="t2-srow" role="radiogroup" aria-label={label}>
      <span className="t2-srow-main">
        <span className="t2-srow-title">{label}</span>
      </span>
      <span className="t2-navpick" style={{ display: "flex", gap: 6, padding: 0 }}>
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={value === option.value}
            className={value === option.value ? "t2-navpick-opt on" : "t2-navpick-opt"}
            onClick={() => onPick(option.value)}
          >
            {tr(option.label)}
          </button>
        ))}
      </span>
    </div>
  );
}

function Switch({ title, hint, on, onToggle }: { title: string; hint?: string; on: boolean; onToggle: () => void }) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={title} onClick={onToggle} className="t2-srow">
      <span className="t2-srow-main">
        <span className="t2-srow-title">{title}</span>
        {hint ? <span className="t2-srow-hint">{hint}</span> : null}
      </span>
      <span className={on ? "t2-switch on" : "t2-switch"} aria-hidden="true">
        <span className="t2-switch-knob" />
      </span>
    </button>
  );
}

export function BubbleSettingsT2({ country, currencyLabel }: { country: CountryCode | undefined; currencyLabel: string | null }) {
  const radial = useFeature(country, "bubble_radial_menu");
  const goalOn = useFeature(country, "bubble_goal_ring");
  const voiceOn = useFeature(country, "voice_offer_answer");
  const [settings, setSettings] = useState<BubbleSettings>(readSettings);
  const [goalText, setGoalText] = useState(settings.goal);
  if (!radial && !goalOn && !voiceOn) return null;
  const update = (patch: Partial<BubbleSettings>) => setSettings(saveSettings({ ...settings, ...patch }));

  return (
    <section>
      <div className="t2-group">{tr("الفقاعة")}</div>
      <div className="t2-list t2-sgroup">
        {radial ? (
          <>
            <Choice label={tr("الحجم")} value={settings.size} options={SIZES} onPick={(size) => update({ size })} />
            <Choice label={tr("الشفافيّة")} value={settings.alpha} options={ALPHAS} onPick={(alpha) => update({ alpha })} />
            <Switch
              title={tr("التصاق بالحافة")}
              hint={tr("تعود الفقاعةُ إلى أقرب حافّةٍ حين تتركها. ولإخفائها اسحبها إلى ✕ أسفل الشاشة.")}
              on={settings.snap}
              onToggle={() => update({ snap: !settings.snap })}
            />
          </>
        ) : null}
        {goalOn ? (
          <label className="t2-srow">
            <span className="t2-srow-main">
              <span className="t2-srow-title">{tr("هدف اليوم")}</span>
              <span className="t2-srow-hint">{tr("حلقةٌ حول الفقاعة تمتلئ بصافي اليوم — للعرض وحدَه.")}</span>
            </span>
            <input
              inputMode="decimal"
              dir="ltr"
              value={goalText}
              placeholder="—"
              aria-label={tr("هدف اليوم")}
              style={{ width: 84, textAlign: "center", font: "inherit", padding: "6px 8px", borderRadius: 10 }}
              onChange={(event) => setGoalText(event.target.value)}
              onBlur={() => {
                const saved = saveSettings({ ...settings, goal: goalText });
                setSettings(saved);
                setGoalText(saved.goal);
              }}
            />
            {currencyLabel ? <span className="t2-srow-value">{currencyLabel}</span> : null}
          </label>
        ) : null}
        {voiceOn ? (
          <Switch
            title={tr("قبول ورفض بالصوت")}
            hint={tr("قل «قبول» أو «رفض» وطلبُ الرحلة ظاهر — يستمع الهاتفُ أثناء العرض وحدَه، ونغمةٌ قصيرةٌ حين يفهم.")}
            on={settings.voice}
            onToggle={() => {
              const next = !settings.voice;
              update({ voice: next });
              if (next) void askPermission("microphone").catch(() => undefined);
            }}
          />
        ) : null}
      </div>
    </section>
  );
}
