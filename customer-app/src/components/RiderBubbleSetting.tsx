/** **«فقاعة الرحلة»** (أمرُ المالك ٢٠/١١ الرابع، الجزء ٢، SPEC §١١٠) — **اختياريّةٌ يشعلها الراكبُ بنفسه**، وحينها وحدَها يُسأل إذنُ
 *  «الظهور فوق التطبيقات». تظهر أثناء البحث والرحلة وحين يخرج من التطبيق وحدَهما. ويُرسم حيث يشتعل `rider_bubble` لدولته وفي
 *  التطبيق المثبَّت على أندرويد وحدَه — فلا مفتاحَ يُحفظ ولا يفعل شيئاً. */
import { useState } from "react";
import { Capacitor } from "@capacitor/core";

import type { CountryCode } from "@/api/types";
import { useFeature } from "@/lib/config";
import { tr } from "@/lib/i18n";
import { riderBubbleChosen, setRiderBubbleChosen } from "@/lib/rider-bubble";
import { Icon, Switch } from "@/taxo2";

export function RiderBubbleSetting({ country }: { country: CountryCode | undefined }) {
  const on = useFeature(country, "rider_bubble");
  const [enabled, setEnabled] = useState(riderBubbleChosen);
  if (!on || Capacitor.getPlatform() !== "android") return null;

  return (
    <section>
      <div className="t2-group">{tr("فقاعة الرحلة")}</div>
      <div className="t2-list t2-sgroup">
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          aria-label={tr("فقاعة الرحلة")}
          className="t2-srow"
          onClick={() => {
            setRiderBubbleChosen(!enabled);
            setEnabled(!enabled);
          }}
        >
          <Icon name="local_taxi" className="t2-srow-icon" />
          <span className="t2-srow-main">
            <span className="t2-srow-title">{tr("فقاعة الرحلة")}</span>
            <span className="t2-srow-hint">
              {tr("فقاعةٌ صغيرةٌ فوق التطبيقات أثناء البحث والرحلة: وقتُ الوصول والمركبة، والاتصالُ والرسائلُ والمشاركة. تحتاج إذنَ «الظهور فوق التطبيقات».")}
            </span>
          </span>
          <Switch on={enabled} />
        </button>
      </div>
    </section>
  );
}
