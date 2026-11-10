/** **درجةُ جودة الكبتن** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٣) — الأوزانُ والمفتاحُ وأثرُها في التوزيع لكلِّ دولة.
 *
 * **المفتاحُ يحكم الأثرَ وحدَه**: الدرجةُ تُحسب كلَّ ليلةٍ في الحالين، فيُرى أثرُ الأوزان في صفحة كلِّ كبتنٍ **قبل** أن تمسّ ترتيباً.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { listQualitySettings, updateQualitySettings } from "@/api/endpoints";
import type { CountryCode, QualitySetting } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Feedback";
import { Field, Switch } from "@/components/ui/Field";

const WEIGHTS: { key: keyof QualitySetting; label: string }[] = [
  { key: "w_acceptance", label: "قبول العروض" },
  { key: "w_cancellation", label: "الإلغاء بعد القبول" },
  { key: "w_rating", label: "تقييم الركّاب" },
  { key: "w_complaints", label: "اعتراضات الدفع" },
  { key: "w_completed", label: "الرحلات المكتملة" },
];

const NUMBER_KEYS = [...WEIGHTS.map((item) => item.key), "dispatch_bonus_m", "warn_below"] as const;

export function QualitySettings({
  country,
  disabled,
  onError,
  onSaved,
}: {
  country: CountryCode;
  disabled: boolean;
  onError: (message: string) => void;
  onSaved: (message: string) => void;
}) {
  const [row, setRow] = useState<QualitySetting | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [enabled, setEnabled] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setRow(null);
    const rows = await listQualitySettings();
    const found = rows.find((item) => item.country_code === country) ?? null;
    setRow(found);
    if (found) {
      setEnabled(found.enabled);
      setDraft(Object.fromEntries(NUMBER_KEYS.map((key) => [key, String(found[key as keyof QualitySetting])])));
    }
  }, [country]);

  useEffect(() => {
    void load().catch((caught: Error) => onError(caught.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  const set = (key: string, value: string) => setDraft((current) => ({ ...current, [key]: value.replace(/[^0-9]/g, "") }));

  return (
    <section className="rounded-16 border border-line bg-surface p-18">
      <div className="mb-4 flex items-center justify-between gap-10">
        <h2 className="text-14 font-bold text-ink">درجة جودة الكبتن</h2>
        {row ? <Switch label="درجة الجودة" checked={enabled} disabled={disabled} onChange={setEnabled} /> : null}
      </div>
      <p className="mb-12 text-11 leading-snug text-muted">
        درجةٌ من 0 إلى 100 لكلِّ كبتنٍ آخرَ 30 يوماً من خمسة مكوّنات بأوزانها أدناه، تُحسب كلَّ ليلة.{" "}
        <b className="text-ink">والمفتاحُ يحكم أثرَها وحدَه</b>: حين يُشعل تقدّم الكبتنَ في ترتيب التوزيع بقدر «أمتار
        التقديم» × الدرجة ÷ 100 — <b className="text-ink">فالأقربُ يبقى الأوّلَ</b> بين المتباعدين — ويصل من دون العتبة
        إشعارٌ بنصائح مرّةً في الأسبوع. والكبتنُ الجديدُ بلا بياناتٍ كافيةٍ لا يُعاقَب.
      </p>
      {row === null ? (
        <Spinner className="mx-auto" />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-10 md:grid-cols-5">
            {WEIGHTS.map((item) => (
              <Field
                key={item.key}
                name={item.key}
                label={"وزن " + item.label}
                dir="ltr"
                inputMode="numeric"
                value={draft[item.key] ?? ""}
                disabled={disabled}
                onChange={(event) => set(item.key, event.target.value)}
              />
            ))}
          </div>
          <div className="mt-10 grid grid-cols-2 gap-10">
            <Field
              name="dispatch_bonus_m"
              label="أمتار التقديم للدرجة 100"
              dir="ltr"
              inputMode="numeric"
              value={draft.dispatch_bonus_m ?? ""}
              disabled={disabled}
              onChange={(event) => set("dispatch_bonus_m", event.target.value)}
            />
            <Field
              name="warn_below"
              label="عتبة الإنذار (دونها إشعارُ نصائح)"
              dir="ltr"
              inputMode="numeric"
              value={draft.warn_below ?? ""}
              disabled={disabled}
              onChange={(event) => set("warn_below", event.target.value)}
            />
          </div>
          {disabled ? null : (
            <Button
              className="mt-12"
              size="sm"
              loading={busy}
              onClick={() => {
                setBusy(true);
                const numbers = Object.fromEntries(NUMBER_KEYS.map((key) => [key, Number(draft[key] || 0)]));
                updateQualitySettings(country, { ...numbers, enabled })
                  .then(() => {
                    onSaved("حُفظت إعداداتُ درجة الجودة");
                    return load();
                  })
                  .catch((caught) => onError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ"))
                  .finally(() => setBusy(false));
              }}
            >
              حفظ
            </Button>
          )}
        </>
      )}
    </section>
  );
}
