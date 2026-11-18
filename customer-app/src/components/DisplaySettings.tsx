/** **صفّا «النصّ الكبير» و«التباين العالي»** في الإعدادات (SPEC §١٠٣ C/40) — يظهران حيث يشتعل مفتاحُ السوق. نسخةُ التطبيق الآخر حرفاً. */
import { bigTextAvailable, DISPLAY_FLAG, setDisplayChoice, useDisplayChoices } from "@/lib/display";
import { useFeature } from "@/lib/config";
import { tr } from "@/lib/i18n";
import type { CountryCode } from "@/api/types";

function Row({ icon, title, hint, on, onToggle }: { icon: string; title: string; hint: string; on: boolean; onToggle: () => void }) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={title} onClick={onToggle} className="t2-srow">
      <span className="t2-icon t2-srow-icon" aria-hidden="true">
        {icon}
      </span>
      <span className="t2-srow-main">
        <span className="t2-srow-title">{title}</span>
        <span className="t2-srow-hint">{hint}</span>
      </span>
      <span className={on ? "t2-switch on" : "t2-switch"} aria-hidden="true">
        <span className="t2-switch-knob" />
      </span>
    </button>
  );
}

export function DisplaySettings({ country }: { country: CountryCode | undefined }) {
  const on = useFeature(country, DISPLAY_FLAG);
  const { big, contrast } = useDisplayChoices();
  if (!on) return null;
  return (
    <>
      {bigTextAvailable() ? (
        <Row
          icon="format_size"
          title={tr("نص كبير")}
          hint={tr("يكبّر كلَّ نصوص التطبيق ليُقرأ أسهل.")}
          on={big}
          onToggle={() => setDisplayChoice("big", !big)}
        />
      ) : null}
      <Row
        icon="contrast"
        title={tr("تباين عالٍ")}
        hint={tr("يجعل النصوصَ الباهتة والحوافَّ أوضح.")}
        on={contrast}
        onToggle={() => setDisplayChoice("contrast", !contrast)}
      />
    </>
  );
}
