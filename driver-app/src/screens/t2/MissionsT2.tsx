/** «المستوى والمهام» — TAXO 2.0 «C13» (Claude Design «Captain»)، **في الداكن المرسوم وحدَه** (افتراضُ الكبتن).
 *
 * **الطلبُ هو هو** (`screens/Missions.tsx`): `GET /drivers/me/progress` عند الفتح، ولا غيره. **والجملُ هي هي**:
 * أثرُ المستوى بالأمتار أو «لا أثر»، و«للمستوى التالي: …» من أوّل مهمّةٍ ناقصة، و«أنجزتَ مهامَّ الشهر كلَّها».
 *
 * **وما تغيّر طبقةُ العرض**: بطاقةُ المستوى بالكهرمان وشريطاها وسلّمُ المستويات (منجَزٌ · حاليّ · مقفل)، والمهامُّ
 * بطاقاتٍ بشريط تقدّمها، والمنجَزةُ بالأخضر.
 *
 * **وما رسمته اللوحةُ ولم يُبنَ — بعلّته** (`TAXO2-DESIGN-CORRECTIONS.md` §١٨):
 * - **النقاطُ** («1,240 / 1,500 نقطة · 260 حتى بلاتيني» و«+150 نقطة»): لا نقاطَ في التطبيق — المستوى من المهامّ.
 * - **مزايا المستوى** («أولوية في طلبات المطار» · «خصم 10% في المتجر»): **القاعدةُ الأولى في الشاشة القائمة تمنعها** —
 *   «الأثرُ يُقال بصدق أو لا يُقال»؛ والأثرُ المقيسُ (الأمتار) هو ما يُكتب.
 * - **مكافأةُ المهمّة وزرُّ «استلم»**: لا مكافأةَ في المهمّة ولا بابَ استلام.
 * - **«مهام هذا الأسبوع · تنتهي بعد يومين»**: المهامُّ شهريةٌ في التطبيق — فبقي «مهامُّ هذا الشهر».
 * - **أسماءُ المستويات** (برونزي · فضي · ذهبي · بلاتيني): بقيت أسماءُ التطبيق (مبتدئ · فضّي · ذهبي · ماسيّ).
 *
 * **وما فيها اليومَ ولم يُرسم يبقى**: وصفُ المهمّة، و«شاراتي» بتواريخها، وزرُّ الرجوع (الشاشةُ تحت «حسابي» لا تبويب).
 */

import { useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { getMyProgress } from "@/api/endpoints";
import type { MyProgress } from "@/api/types";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { digits } from "@/lib/utils";
import { LEVEL_LABEL, nextStep } from "@/screens/Missions";

import "@/taxo2";
import "./t2.css";

export function MissionsT2Screen() {
  const [data, setData] = useState<MyProgress | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMyProgress()
      .then(setData)
      .catch((caught) =>
        setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة المهام"),
      );
  }, []);

  // سلّمُ المستويات: كلُّ ما في الجدول حتى أعلاه — **الاسمُ من بيته الواحد** (`LEVEL_LABEL`)
  const ladder = data
    ? Array.from({ length: Math.max(data.max_level + 1, data.level + 1) }, (_, index) => index)
    : [];
  const next = data ? nextStep(data.missions) : null;

  return (
    <div className="t2 t2-missions scr">
      {/* **تبويبٌ لا صفحةٌ داخليّة** (C04، §٦٢-ب/٢٦) — فلا رجوعَ والشريطُ تحته */}
      <div className="t2-head">
        <h1 className="t2-title">المستوى والمهام</h1>
      </div>

      <ErrorNote message={error} />
      {data === null ? (
        <Spinner />
      ) : (
        <>
          {data.enabled ? (
            <section className="t2-level">
              <span className="t2-level-stripe a" aria-hidden="true" />
              <span className="t2-level-stripe b" aria-hidden="true" />
              <div className="t2-level-head">
                <span className="t2-icon t2-level-medal" aria-hidden="true">workspace_premium</span>
                <div>
                  <div className="t2-level-k">مستواك</div>
                  <div className="t2-level-v">
                    {LEVEL_LABEL[data.level] ?? `المستوى ${digits(String(data.level))}`}
                  </div>
                </div>
              </div>

              <div className="t2-ladder">
                {ladder.map((index) => (
                  <span
                    key={index}
                    className={index < data.level ? "t2-rung done" : index === data.level ? "t2-rung now" : "t2-rung"}
                  >
                    <span className="t2-icon" aria-hidden="true">
                      {index < data.level ? "check_circle" : index === data.level ? "radio_button_checked" : "lock"}
                    </span>
                    {LEVEL_LABEL[index] ?? digits(String(index))}
                  </span>
                ))}
              </div>

              {/* **الأثرُ بالأمتار — جملةٌ مقيسة لا وعد** (القاعدةُ الأولى في الشاشة القائمة) */}
              {data.level_effect_meters > 0 ? (
                <p className="t2-level-note ok">
                  يقرّبك من الطلبات القريبة {digits(String(data.level_effect_meters))} متراً — والأقربُ إليك يبقى
                  الأوّلَ دائماً.
                </p>
              ) : (
                <p className="t2-level-note">لا أثرَ لمستواك على ترتيب الطلبات في سوقك حالياً.</p>
              )}
              {/* **ومستوىً بلا «كم بقي» شارةٌ لا حافز** */}
              {next ? (
                <p className="t2-level-next">للمستوى التالي: {next}</p>
              ) : data.missions_total > 0 ? (
                <p className="t2-level-note ok">
                  أنجزتَ مهامَّ الشهر كلَّها — {digits(String(data.missions_done))} من{" "}
                  {digits(String(data.missions_total))}.
                </p>
              ) : null}
            </section>
          ) : null}

          {data.enabled ? (
            <section>
              <div className="t2-section">مهامُّ هذا الشهر</div>
              {data.missions.length === 0 ? (
                <p className="t2-empty">لا مهامَّ هذا الشهر بعد.</p>
              ) : (
                <div className="t2-missions-list">
                  {data.missions.map((item) => {
                    // شريطُ التقدّم — **عرضٌ محسوبٌ من حقيقتين** لا قيمةٌ ترسلها الخلفية: نسبةُ رسمٍ لا رقمُ عمل
                    const ratio = Math.min(1, Number(item.value) / Math.max(1e-9, Number(item.target)));
                    return (
                      <div key={item.mission.id} className={item.done ? "t2-mission done" : "t2-mission"}>
                        <div className="t2-mission-top">
                          <span className="t2-icon" aria-hidden="true">
                            {item.mission.metric === "min_rating" ? "star" : "flag"}
                          </span>
                          <div className="t2-mission-main">
                            <div className="t2-mission-title">{item.mission.title}</div>
                            {item.mission.description ? (
                              <div className="t2-mission-desc">{item.mission.description}</div>
                            ) : null}
                          </div>
                        </div>
                        <div className="t2-mission-bar">
                          <div className="t2-mission-track">
                            <div className="t2-mission-fill" style={{ width: `${Math.round(ratio * 100)}%` }} />
                          </div>
                          <span dir="ltr" className="t2-mission-count">
                            {digits(item.value)}/{digits(item.target)}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          ) : null}

          {/* **الشاراتُ تُعرض ولو كان المفتاحُ مطفأً** — تقديرٌ نالَه صاحبُه (الشاشةُ القائمة) */}
          <section>
            <div className="t2-section">شاراتي</div>
            {data.badges.length === 0 ? (
              <p className="t2-empty">لم تُمنح شاراتٍ بعد.</p>
            ) : (
              <div className="t2-list">
                {data.badges.map((row) => (
                  <div key={row.badge.id} className="t2-badge-row">
                    <span className="t2-icon" aria-hidden="true">verified</span>
                    <span className="t2-badge-main">
                      <span className="t2-badge-label">{row.badge.label}</span>
                      {row.badge.description ? (
                        <span className="t2-badge-desc">{row.badge.description}</span>
                      ) : null}
                    </span>
                    <span className="t2-badge-date" dir="ltr">
                      {digits(row.granted_at.slice(0, 10))}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
