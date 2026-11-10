/** **«درجتي»** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٣) — تحت «أرباحي»، وإليها يفتح إشعارُ «درجتك تحتاج انتباهاً».
 *
 * **الأرقامُ كما تصل** من `GET /drivers/me/quality` (الحسابُ في الخلفية)، **والنصائحُ بمفاتيحها** تُترجَم هنا — لا نصُّ الخلفية،
 * فكبتنُ الجزائر بالفرنسية يقرؤها بلغته. **ولا تُرسم حيث المفتاحُ مطفأ**: درجةٌ لا أثرَ لها تُقلق ولا تُفيد.
 */

import { useEffect, useState } from "react";

import { getMyQuality, type MyQuality } from "@/api/endpoints";
import { tr } from "@/lib/i18n";
import { digits } from "@/lib/utils";

const PARTS: { key: string; label: string }[] = [
  { key: "acceptance", label: "قبول الطلبات" },
  { key: "cancellation", label: "الالتزام بعد القبول" },
  { key: "rating", label: "تقييم الركّاب" },
  { key: "complaints", label: "خلوّ من اعتراضات الدفع" },
  { key: "completed", label: "الرحلات المكتملة" },
];

const TIPS: Record<string, string> = {
  acceptance: "اقبل ما يصلك من طلباتٍ أكثر — كلُّ عرضٍ يمرّ بلا ردٍّ يُحسب.",
  cancellation: "لا تلغِ بعد القبول إلا لضرورة — الإلغاءُ يؤخّر الراكبَ ويُحسب عليك.",
  rating: "اعتنِ بنظافة السيارة والتحيّة والقيادة الهادئة — التقييمُ يأتي منها.",
  complaints: "اتّفق مع الراكب على الدفع بوضوحٍ قبل نهاية الرحلة — الاعتراضاتُ تُحسب عليك.",
  completed: "رحلاتٌ مكتملةٌ أكثر ترفع درجتك — اتّصل في ساعات الذروة.",
};

export function QualityT2() {
  const [data, setData] = useState<MyQuality | null>(null);

  useEffect(() => {
    getMyQuality()
      .then(setData)
      .catch(() => undefined);
  }, []);

  if (data === null || !data.enabled) return null;

  return (
    <section className="t2-wal-break" id="my-quality" aria-labelledby="my-quality-title">
      <h2 id="my-quality-title" className="t2-wal-line" style={{ fontWeight: 700 }}>
        <span>{tr("درجتي")}</span>
        <span dir="ltr">{digits(`${data.score} / 100`)}</span>
      </h2>
      {PARTS.map((part) => (
        <div key={part.key} className="t2-wal-line">
          <span>{tr(part.label)}</span>
          <span dir="ltr">{digits(`${Math.round((data.parts[part.key] ?? 0) * 100)}%`)}</span>
        </div>
      ))}
      {data.tips.map((tip) =>
        TIPS[tip.component] ? (
          <p key={tip.component} className="t2-wal-hint">
            {tr(TIPS[tip.component])}
          </p>
        ) : null,
      )}
      <p className="t2-wal-hint">
        {tr("آخر 30 يوماً. الدرجةُ الأعلى تقدّمك قليلاً في ترتيب الطلبات بين القريبين، والأقربُ يبقى الأوّل.")}
      </p>
    </section>
  );
}
