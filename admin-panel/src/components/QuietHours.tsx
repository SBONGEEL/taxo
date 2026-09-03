/** ساعاتُ الهدوء ومنطقتُها الزمنية — **بابٌ كان يُقرأ ولا يُكتب** (2026-08-19).
 *
 * `PUT /admin/campaigns/settings/{country}` مبنيٌّ منذ المرحلة ٨ **ومصرَّحٌ به في
 * `api/endpoints.ts` ولا ينادِيه أحد**: كانت الشاشةُ تعرض النافذةَ من `/config`
 * ولا تملك تغييرَها. وهو الشكلُ نفسُه الذي أوقف خريطةَ الراكب في البند ٧ — مسارٌ
 * مصرَّحٌ به وبلا نداء.
 *
 * **ومنطقةُ الزمن أخطرُ من النافذة**: بها يُحسب «يومُ الدولة» في `services/stats.py`
 * وفي تقارير الشهر وفي جدولة النسخ — فخادمٌ بـUTC يقصّ ثلاثَ ساعاتٍ من أول يومٍ
 * في عمّان ويضيف ثلاثاً من أمس. وكانت تُعرض ولا تُحرَّر.
 *
 * **والحفظُ لا يُجزَّأ**: الخلفيةُ تشترط الحقولَ الثلاثة معاً (`PUT` لا `PATCH`)،
 * فالشاشةُ ترسلها ثلاثتَها — وحقلٌ يُرسل وحدَه يمحو ما جاوره بقيمةٍ افتراضية.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { getQuietHours, setQuietHours } from "@/api/endpoints";
import type { CountryCode } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Spinner } from "@/components/ui/Feedback";
import { useSession } from "@/lib/session";

/** مناطقُ السوقين وحدَهما — قائمةٌ عالميةٌ تجعل الاختيارَ بحثاً لا قراراً. */
const ZONES = ["Asia/Amman", "Africa/Tripoli", "UTC"];

export function QuietHours({
  country,
  onError,
  onSaved,
}: {
  country: CountryCode;
  onError: (message: string) => void;
  onSaved: (message: string) => void;
}) {
  const { isAdmin } = useSession();
  const [start, setStart] = useState<string | null>(null);
  const [end, setEnd] = useState("");
  const [zone, setZone] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setStart(null);
    const row = await getQuietHours(country);
    setStart(row.quiet_hours_start);
    setEnd(row.quiet_hours_end);
    setZone(row.timezone);
  }, [country]);

  useEffect(() => {
    void load().catch((caught: Error) => onError(caught.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  return (
    <section className="mb-14 rounded-14 border border-line bg-surface px-16 py-12">
      <div className="mb-8 flex flex-wrap items-baseline gap-10">
        <span className="text-13 font-bold text-ink">ساعات الهدوء</span>
        <span className="text-11.5 leading-note text-muted">
          حملةٌ تقع داخلها تُؤجَّل إلى النافذة التالية، ولا تُلغى ولا تُرسل ناقصة.
          والتقسيم بالدولة، فحملةٌ للسوقين تُرسل في كلٍّ منهما بنافذته.
        </span>
      </div>

      {start === null ? (
        <Spinner className="mx-auto" />
      ) : (
        <>
          <div className="grid gap-10 md:grid-cols-3">
            <Field
              label="من"
              dir="ltr"
              value={start}
              disabled={!isAdmin}
              onChange={(event) => setStart(event.target.value)}
            />
            <Field
              label="إلى"
              dir="ltr"
              value={end}
              disabled={!isAdmin}
              onChange={(event) => setEnd(event.target.value)}
            />
            <Field
              label="المنطقة الزمنية"
              dir="ltr"
              list="taxo-zones"
              value={zone}
              disabled={!isAdmin}
              onChange={(event) => setZone(event.target.value)}
            />
            <datalist id="taxo-zones">
              {ZONES.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
          </div>

          <p className="mt-8 text-11 leading-note text-muted">
            بهذه المنطقة يُحسب <b className="text-ink">«يومُ الدولة»</b> في كلِّ
            تقرير وفي جدولة النسخ الاحتياطي — لا بتوقيت الخادم. وصيغةُ الساعة{" "}
            <span dir="ltr">HH:MM</span>.
          </p>

          {isAdmin ? (
            <Button
              className="mt-10"
              size="sm"
              loading={busy}
              onClick={() => {
                setBusy(true);
                setQuietHours(country, {
                  quiet_hours_start: start,
                  quiet_hours_end: end,
                  timezone: zone.trim(),
                })
                  .then(() =>
                    onSaved(
                      "حُفظت ساعاتُ الهدوء — ولا تُرسل حملةٌ داخلها بعد الآن",
                    ),
                  )
                  .catch((caught) =>
                    onError(
                      caught instanceof ApiError
                        ? caught.message
                        : "تعذّر الحفظ",
                    ),
                  )
                  .finally(() => setBusy(false));
              }}
            >
              حفظ
            </Button>
          ) : null}
        </>
      )}
    </section>
  );
}
