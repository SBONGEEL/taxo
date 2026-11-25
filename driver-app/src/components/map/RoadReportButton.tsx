/** **«بلّغ» بلمسةٍ واحدة** (أمرُ المالك ٢٠٢٦-١١-١٨ السابع، المهمّة ٣-٣): صيانة · طريق مغلق · حادث · ازدحام — من موقع الكبتن الآن.
 *  **ولا يظهر للناس حتى يؤكّده كبتنٌ آخر أو يوافق المشرف**، وينتهي وحدَه بعد ساعات؛ والكبتنُ يُقال له ذلك. ومطفأً لا زرّ. */
import { useState } from "react";

import { api } from "@/api/client";
import type { Coordinates } from "@/api/types";
import { Icon } from "@/taxo2";
import { tr } from "@/lib/i18n";
import { REPORT_LABEL, useOpenFlags } from "@/lib/open-layers";

const KINDS = ["works", "closed", "accident", "jam"] as const;

export function RoadReportButton({ position }: { position: Coordinates | null }) {
  const { reports } = useOpenFlags();
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  if (!reports || !position) return null;

  async function send(kind: (typeof KINDS)[number]) {
    if (!position) return;
    setOpen(false);
    try {
      const ack = await api.post<{ visible: boolean; counted: boolean }>("/map/road-reports", { kind, lat: position.lat, lng: position.lng });
      setNote(
        !ack.counted
          ? tr("بلّغتَ عن هذا من قبل")
          : ack.visible
            ? tr("شكراً — البلاغُ ظاهرٌ الآن على الخريطة")
            : tr("شكراً — يظهر حين يؤكّده كابتنٌ آخر"),
      );
    } catch {
      setNote(tr("تعذّر الإرسال"));
    }
    window.setTimeout(() => setNote(null), 4000);
  }

  return (
    <div className="t2-hm-report">
      {open ? (
        <div className="t2-hm-report-kinds">
          {KINDS.map((kind) => (
            <button key={kind} type="button" className="t2-hm-report-kind" onClick={() => void send(kind)}>
              {tr(REPORT_LABEL[kind])}
            </button>
          ))}
        </div>
      ) : null}
      {note ? <p className="t2-hm-report-note">{note}</p> : null}
      <button
        type="button"
        className={open ? "t2-hm-traffic on" : "t2-hm-traffic"}
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-label={tr("بلّغ عن الطريق")}
        title={tr("بلّغ عن الطريق")}
      >
        <Icon name="error" />
      </button>
    </div>
  );
}
