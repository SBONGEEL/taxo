/** «مهامّي ومستواي» — مهامُّ الشهر وتقدّمي وشاراتي (البند ٥٣، §٦).
 *
 * **وثلاثُ قواعدَ فيها تحمل قراراتٍ لا تفاصيلَ عرض:**
 *
 * 1. **الأثرُ يُقال بصدق أو لا يُقال**: «يقرّبك من الطلبات القريبة ٥٠ متراً»
 *    جملةٌ **مقيسة** — والخلفيةُ ترسل الرقم. و«أولويةٌ في الطلبات» وعدٌ يقرؤه
 *    الكبتنُ بطلباتٍ أكثر، ثم يعدُّها فلا يجدها، فيقرأ النظامَ كذباً.
 * 2. **ومستوىً بلا «كم بقي» شارةٌ لا حافز**: تحت المستوى جملةٌ واحدةٌ صريحة
 *    تقول ما يلزم للتالي — ورقمٌ بلا طريقٍ إليه يُقرأ ولا يُحرّك أحداً.
 * 3. **والشاراتُ بلا سببِ منحها**: السببُ كلامُ مشرفٍ لمشرفٍ في سجل التدقيق،
 *    وتحويلُه رسالةً لصاحبه يجعل حكماً إدارياً خطاباً — قاعدةُ سبب سحب الوضع
 *    النسائي نفسُها.
 *
 * **والشاراتُ تُعرض ولو كان المفتاح مطفأً**: تقديرٌ نالَه صاحبُه فعلاً، ولا
 * علاقةَ له بالمستوى ولا بالتوزيع — وإخفاؤها بمفتاح غيرها يسحب اعترافاً نالَه.
 */

import { useEffect, useState } from "react";
import { Award, Target } from "lucide-react";

import { ApiError } from "@/api/client";
import { getMyProgress } from "@/api/endpoints";
import type { MissionProgress, MyProgress } from "@/api/types";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { Stagger, StaggerItem } from "@/components/ui/Motion";
import { useGoBack } from "@/lib/back";
import { digits, cn } from "@/lib/utils";

const LEVEL_LABEL = ["مبتدئ", "فضّي", "ذهبي", "ماسيّ"];

/** «كم بقي» — **أوّلُ مهمّةٍ ناقصةٍ هي الجواب**، وسردُ الثلاثة يخفي المطلوب. */
function nextStep(items: MissionProgress[]): string | null {
  const pending = items.find((item) => !item.done);
  if (!pending) return null;
  if (pending.mission.metric === "min_rating") {
    return `ارفع تقييمك إلى ${digits(pending.target)}`;
  }
  const left = Number(pending.target) - Number(pending.value);
  return `أكمل ${digits(String(left))} رحلات أخرى`;
}

export function MissionsScreen() {
  const goBack = useGoBack();
  const [data, setData] = useState<MyProgress | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMyProgress()
      .then(setData)
      .catch((caught) =>
        setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة المهام"),
      );
  }, []);

  return (
    <div className="scr h-full bg-bg px-16 pb-12 pt-safe">
      <div className="mb-16 mt-6 flex items-center gap-10">
        <button
          type="button"
          onClick={() => goBack()}
          aria-label="رجوع"
          className="pressable text-18 text-muted"
        >
          →
        </button>
        <h1 className="text-20 font-bold text-ink">مهامّي ومستواي</h1>
      </div>

      <ErrorNote message={error} />
      {data === null ? (
        <Spinner />
      ) : (
        <div className="space-y-14">
          {data.enabled ? (
            <section className="card p-16 text-center">
              <p className="text-12 text-muted">مستواك الحالي</p>
              <p className="mt-6 text-22 font-bold text-ink">
                {LEVEL_LABEL[data.level] ??
                  `المستوى ${digits(String(data.level))}`}
              </p>
              {/* **الأثرُ بالأمتار — جملةٌ مقيسة لا وعد** */}
              {data.level_effect_meters > 0 ? (
                <p className="mt-8 text-11.5 text-ok">
                  يقرّبك من الطلبات القريبة{" "}
                  {digits(String(data.level_effect_meters))} متراً — والأقربُ
                  إليك يبقى الأوّلَ دائماً.
                </p>
              ) : (
                <p className="mt-8 text-11.5 text-muted">
                  لا أثرَ لمستواك على ترتيب الطلبات في سوقك حالياً.
                </p>
              )}
              {/* **ومستوىً بلا «كم بقي» شارةٌ لا حافز** */}
              {nextStep(data.missions) ? (
                <p className="mt-10 rounded-13 bg-surface-2 p-10 text-12 text-ink">
                  للمستوى التالي: {nextStep(data.missions)}
                </p>
              ) : data.missions_total > 0 ? (
                <p className="mt-10 text-12 text-ok">
                  أنجزتَ مهامَّ الشهر كلَّها —{" "}
                  {digits(String(data.missions_done))} من{" "}
                  {digits(String(data.missions_total))}.
                </p>
              ) : null}
            </section>
          ) : null}

          {data.enabled ? (
            <section>
              <h2 className="mb-8 flex items-center gap-6 text-13.5 font-bold text-ink">
                <Target size={16} />
                مهامُّ هذا الشهر
              </h2>
              {data.missions.length === 0 ? (
                <p className="card p-16 text-center text-12.5 text-muted">
                  لا مهامَّ هذا الشهر بعد.
                </p>
              ) : (
                <Stagger className="space-y-8">
                  {data.missions.map((item) => {
                    const ratio = Math.min(
                      1,
                      Number(item.value) / Math.max(1e-9, Number(item.target)),
                    );
                    return (
                      <StaggerItem
                        key={item.mission.id}
                        className="rounded-13 border border-line bg-surface p-12"
                      >
                        <div className="flex items-start justify-between gap-10">
                          <span className="text-12.5 font-semibold text-ink">
                            {item.mission.title}
                          </span>
                          <span
                            className={cn(
                              "shrink-0 text-11.5 font-bold",
                              item.done ? "text-ok" : "text-muted",
                            )}
                          >
                            {digits(item.value)} / {digits(item.target)}
                          </span>
                        </div>
                        {item.mission.description ? (
                          <p className="mt-4 text-11.5 text-muted">
                            {item.mission.description}
                          </p>
                        ) : null}
                        {/* شريطُ التقدّم — **عرضٌ محسوبٌ من حقيقتين** لا قيمةٌ
                            ترسلها الخلفية: نسبةُ رسمٍ لا رقمُ عمل */}
                        <div className="mt-8 h-6 overflow-hidden rounded-full bg-surface-2">
                          <div
                            className={cn(
                              "h-full rounded-full",
                              item.done ? "bg-ok" : "bg-ink",
                            )}
                            style={{ width: `${Math.round(ratio * 100)}%` }}
                          />
                        </div>
                      </StaggerItem>
                    );
                  })}
                </Stagger>
              )}
            </section>
          ) : null}

          <section>
            <h2 className="mb-8 flex items-center gap-6 text-13.5 font-bold text-ink">
              <Award size={16} />
              شاراتي
            </h2>
            {data.badges.length === 0 ? (
              <p className="card p-16 text-center text-12.5 text-muted">
                لم تُمنح شاراتٍ بعد.
              </p>
            ) : (
              <Stagger className="space-y-8">
                {data.badges.map((row) => (
                  <StaggerItem
                    key={row.badge.id}
                    className="flex items-center justify-between gap-10 rounded-13 border border-line bg-surface p-12"
                  >
                    <span>
                      <span className="block text-12.5 font-semibold text-ink">
                        {row.badge.label}
                      </span>
                      {row.badge.description ? (
                        <span className="mt-2 block text-11 text-muted">
                          {row.badge.description}
                        </span>
                      ) : null}
                    </span>
                    <span className="shrink-0 text-11 text-muted" dir="ltr">
                      {digits(row.granted_at.slice(0, 10))}
                    </span>
                  </StaggerItem>
                ))}
              </Stagger>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
