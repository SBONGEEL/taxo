/** **بثُّ موقع الكبتن** (SPEC §٧٥-ج) — **عامٌّ لكلِّ الدول**: ما يُحمى هو الخادمُ الواحد، وعددُه عددُ كلِّ المتّصلين عليه.
 *
 * ## ثلاثةُ أشياءَ في هذه البطاقة مقصودة
 *
 * **١) «ما يعمل الآن» غيرُ «ما كُتب».** في الطور الآليّ يحسب الخادمُ فاصلَ المتاحين من عدد المتّصلين — **فالرقمُ المكتوبُ في حقل
 * «المتاح» لا يعمل**، والسطرُ الحيُّ يقول ما يعمل فعلاً ومتى قِيس. **وحقلٌ يُرى عاملاً وليس كذلك** هو العطبُ الذي يمنعه هذا الفصل.
 *
 * **٢) والآليُّ لا يمسّ إلا المتاحين.** فاصلُ «في الطريق» والرحلةُ ونقاطُها والسكونُ والنبضةُ تُكتب هنا في الطورين — **والجدولُ
 * وحدَه ما يتبع العدد**، وحدّاه الصلبان ١٥–٤٥ في الخادم لا في هذه الشاشة.
 *
 * **٣) وما يُحفظ يصل الكباتنَ فوراً** — بلا تحديثٍ ولا إعادةِ تشغيل؛ **والسجلُّ** يقول كلَّ تغييرٍ في فاصل المتاحين: متى، وبكم متّصلاً،
 * ومن أين إلى أين، ومن سبّبه.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { getBroadcastSettings, updateBroadcastSettings } from "@/api/endpoints";
import type { BroadcastSettings as Settings, BroadcastStep } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { Segmented } from "@/components/ui/Segmented";
import { moment } from "@/lib/format";

const FIELDS: { key: keyof Settings; label: string; unit: string }[] = [
  { key: "available_seconds", label: "متاحٌ ينتظر (الطورُ اليدويّ)", unit: "ثانية · 15–45" },
  { key: "heading_seconds", label: "في الطريق إلى الراكب", unit: "ثانية" },
  { key: "trip_send_seconds", label: "في الرحلة — دفعةٌ كلَّ", unit: "ثانية" },
  { key: "trip_record_seconds", label: "في الرحلة — نقطةٌ كلَّ", unit: "ثانية" },
  { key: "move_meters", label: "قاعدةُ السكون — لا إرسالَ قبل أن يبتعد", unit: "متراً" },
  { key: "heartbeat_seconds", label: "نبضةُ «ما زلتُ متّصلاً»", unit: "ثانية" },
  // **إنذارُ السعة** (§٧٦/٢): متّصلون في اللحظة نفسِها يبلغون هذا ⇒ تنبيهٌ في «نظرة عامة» وإشعارٌ للمشرفين — **٧٠٪ من السعة الآمنة المقيسة**
  { key: "alert_captains", label: "إنذارُ السعة — كباتنُ متّصلون معاً", unit: "كبتناً" },
  { key: "alert_riders", label: "إنذارُ السعة — ركّابٌ متّصلون معاً", unit: "راكباً" },
];

type Numbers = Record<string, string>;

/** **أرقامٌ لاتينيّةٌ وحدَها** — والعربيّةُ-الهنديّةُ تُحوَّل قبل أن يُنزع ما سواها */
const numeric = (value: string) =>
  value
    .replace(/[\u0660-\u0669]/g, (d) => String(d.charCodeAt(0) - 0x0660))
    .replace(/[^0-9]/g, "");

export function BroadcastSettings({ disabled, onError, onSaved }: {
  disabled: boolean;
  onError: (message: string) => void;
  onSaved: (message: string) => void;
}) {
  const [row, setRow] = useState<Settings | null>(null);
  const [mode, setMode] = useState<"manual" | "automatic">("automatic");
  const [values, setValues] = useState<Numbers>({});
  const [steps, setSteps] = useState<{ max: string; seconds: string }[]>([]);
  const [busy, setBusy] = useState(false);

  const adopt = useCallback((next: Settings) => {
    setRow(next);
    setMode(next.mode);
    setValues(Object.fromEntries(FIELDS.map(({ key }) => [key, String(next[key])])));
    setSteps(next.auto_steps.map((step) => ({ max: step.max_online === null ? "" : String(step.max_online), seconds: String(step.seconds) })));
  }, []);

  const load = useCallback(() => {
    getBroadcastSettings()
      .then(adopt)
      .catch((caught) => onError(caught instanceof ApiError ? caught.message : "تعذّر تحميلُ إعدادات البثّ"));
  }, [adopt, onError]);

  useEffect(() => {
    load();
    // **حيّةٌ ما دامت مفتوحة**: الطورُ الآليُّ يدور كلَّ نصف دقيقة
    const timer = window.setInterval(() => {
      getBroadcastSettings()
        .then((next) => setRow(next))
        .catch(() => undefined);
    }, 30_000);
    return () => window.clearInterval(timer);
  }, [load]);

  if (!row) return null;

  const save = () => {
    const auto_steps: BroadcastStep[] = steps.map((step, index) => ({
      max_online: index === steps.length - 1 ? null : Number(step.max),
      seconds: Number(step.seconds),
    }));
    setBusy(true);
    updateBroadcastSettings({
      mode,
      ...Object.fromEntries(FIELDS.map(({ key }) => [key, Number(values[key])])),
      auto_steps,
    })
      .then((next) => {
        adopt(next);
        onSaved("حُفظت إعداداتُ البثّ — ووصلت الكباتنَ المتّصلين الآن");
      })
      .catch((caught) => onError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ"))
      .finally(() => setBusy(false));
  };

  const live = row.live;
  return (
    <section className="rounded-16 border border-line bg-surface p-18">
      <h2 className="mb-4 text-14 font-bold text-ink">بثُّ موقع الكبتن — لكلِّ الدول</h2>
      <p className="mb-12 text-11 leading-snug text-muted">
        كم مرّةً يرسل تطبيقُ الكبتن موقعَه في كلِّ حال. <b className="text-ink">والآليُّ يغيّر فاصلَ المتاحين وحدَه</b> بعدد
        المتّصلين، بلا تذبذب: يطول فوراً حين يعبر العددُ حدَّ درجته، ويقصر بعد خمس دقائق وعددٍ دونه بعشرة بالمئة.{" "}
        <b className="text-ink">وما يُحفظ يصل كلَّ كبتنٍ متّصلٍ فوراً.</b>
      </p>

      <div className="mb-14 rounded-12 border border-line p-12 text-12 text-ink" data-broadcast-live>
        يعمل الآن: <b>{live.mode === "automatic" ? "آليّ" : "يدويّ"}</b> · فاصلُ المتاحين{" "}
        <b dir="ltr">{live.available_seconds}</b> ثانية · المتّصلون <b dir="ltr">{live.online ?? "—"}</b> · مهلةُ الحضور{" "}
        <b dir="ltr">{live.presence_ttl}</b> ثانية
        {live.checked_at ? <span className="text-muted"> · قِيس {moment(live.checked_at)}</span> : null}
      </div>

      <Segmented
        label="طورُ البثّ"
        value={mode}
        options={[
          { key: "automatic", label: "آليّ — بعدد المتّصلين" },
          { key: "manual", label: "يدويّ — بما يُكتب هنا" },
        ]}
        onPick={(next) => !disabled && setMode(next)}
      />

      <div className="mt-12 grid grid-cols-2 gap-10">
        {FIELDS.map(({ key, label, unit }) => (
          <Field
            key={key}
            name={key}
            label={`${label} (${unit})`}
            dir="ltr"
            inputMode="numeric"
            value={values[key] ?? ""}
            disabled={disabled || (key === "available_seconds" && mode === "automatic")}
            onChange={(event) => setValues((current) => ({ ...current, [key]: numeric(event.target.value) }))}
          />
        ))}
      </div>

      <h3 className="mb-6 mt-14 text-12.5 font-bold text-ink">جدولُ الطور الآليّ — فاصلُ المتاحين بعدد المتّصلين</h3>
      <div className="grid gap-6">
        {steps.map((step, index) => (
          <div key={index} className="grid grid-cols-2 gap-10">
            {index === steps.length - 1 ? (
              <p className="self-center text-12 text-muted">فوق ذلك</p>
            ) : (
              <Field
                name={`step-max-${index}`}
                label="حتى (متّصلاً)"
                dir="ltr"
                inputMode="numeric"
                value={step.max}
                disabled={disabled}
                onChange={(event) =>
                  setSteps((current) => current.map((s, i) => (i === index ? { ...s, max: numeric(event.target.value) } : s)))
                }
              />
            )}
            <Field
              name={`step-seconds-${index}`}
              label="الفاصل (ثانية · 15–45)"
              dir="ltr"
              inputMode="numeric"
              value={step.seconds}
              disabled={disabled}
              onChange={(event) =>
                setSteps((current) => current.map((s, i) => (i === index ? { ...s, seconds: numeric(event.target.value) } : s)))
              }
            />
          </div>
        ))}
      </div>

      <Button className="mt-14" size="sm" disabled={disabled} loading={busy} onClick={save}>
        حفظ
      </Button>

      <h3 className="mb-6 mt-18 text-12.5 font-bold text-ink">سجلُّ آخر التغييرات</h3>
      {row.changes.length === 0 ? (
        <p className="text-12 text-muted">لا تغييرَ بعد.</p>
      ) : (
        <ul className="grid gap-4 text-12 text-ink" data-broadcast-changes>
          {row.changes.map((change) => (
            <li key={change.created_at}>
              <span className="text-muted">{moment(change.created_at)}</span> ·{" "}
              {change.source === "automatic" ? "آليّ" : "مشرف"} · المتّصلون <span dir="ltr">{change.online_count}</span> ·{" "}
              <span dir="ltr">{change.old_seconds ?? "—"}</span> ← <span dir="ltr">{change.new_seconds}</span> ثانية
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
