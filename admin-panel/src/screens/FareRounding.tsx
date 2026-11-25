/** **تقريبُ الأسعار وعرضُها** (أمرُ المالك ٢٠٢٦-١١-١٩، `design/OWNER-2026-11-19-FARE-ROUNDING.md`) — لكلِّ دولة، من مصدرٍ واحدٍ
 *  تقرؤه الخلفيّةُ والتطبيقان واللوحة. **كلُّ حسابٍ هنا من الخلفية** (§14): المعاينةُ `POST …/preview`، والصفحةُ ترسم ما يعود.
 *  **والتغييرُ للرحلات الجديدة وحدَها**، والحفظُ ورقةُ تأكيدٍ بأمثلةٍ قبل/بعد ثمّ سجلُّ التدقيق. */
import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { getFareRounding, previewFareRounding, saveFareRounding } from "@/api/endpoints";
import type { FareRounding, FareRoundingInput, FareRoundingPreview, RoundingModeKey } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Table } from "@/components/Table";
import { Button } from "@/components/ui/Button";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { Field, Switch } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { Segmented } from "@/components/ui/Segmented";
import { useCountry } from "@/lib/country";
import { currencyLabel } from "@/lib/format";
import { digits } from "@/lib/utils";
import { useSession } from "@/lib/session";

const STEPS = ["none", "0.01", "0.05", "0.10", "0.25", "0.50", "1", "custom"] as const;
type StepKey = (typeof STEPS)[number];
const STEP_LABEL: Record<StepKey, string> = {
  none: "بلا تقريب",
  "0.01": "0.01",
  "0.05": "0.05",
  "0.10": "0.10",
  "0.25": "0.25",
  "0.50": "0.50",
  "1": "1",
  custom: "مخصّصة",
};
const MODES: { key: RoundingModeKey; label: string }[] = [
  { key: "nearest", label: "الأقرب" },
  { key: "up", label: "للأعلى" },
  { key: "down", label: "للأدنى" },
];
const SURFACES: { key: keyof Pick<FareRoundingInput, "on_estimate" | "on_final" | "on_negotiation" | "on_cancellation">; label: string; hint: string }[] = [
  { key: "on_estimate", label: "تقديرُ الأجرة", hint: "ما يراه الراكبُ قبل الطلب وعدّادُ الرحلة" },
  { key: "on_final", label: "الأجرةُ النهائيّة", hint: "ما يُحصَّل عند الإنهاء — ويُجمَّد على الرحلة عند طلبها" },
  { key: "on_negotiation", label: "أسعارُ التفاوض", hint: "عرضُ الراكب، وعرضُ الكابتن المقابل، والحدُّ الأدنى والخطوة" },
  { key: "on_cancellation", label: "رسمُ الإلغاء", hint: "ما يُحصَّل من الراكب عند إلغاءٍ متأخّر" },
];

const num = (text: string) => Number(text);
const stepKeyOf = (step: string | null): StepKey => {
  if (step === null) return "none";
  const match = STEPS.find((key) => key !== "none" && key !== "custom" && num(key) === num(step));
  return match ?? "custom";
};

function toInput(value: FareRounding): FareRoundingInput {
  return {
    decimals: value.decimals,
    step: value.step,
    mode: value.mode,
    on_estimate: value.on_estimate,
    on_final: value.on_final,
    on_negotiation: value.on_negotiation,
    on_cancellation: value.on_cancellation,
    trim_whole: value.trim_whole ?? false,
  };
}

export function FareRoundingScreen() {
  const { country } = useCountry();
  const { isAdmin } = useSession();
  const [saved, setSaved] = useState<FareRounding | null>(null);
  const [draft, setDraft] = useState<FareRoundingInput | null>(null);
  const [stepKey, setStepKey] = useState<StepKey>("none");
  const [custom, setCustom] = useState("");
  const [amount, setAmount] = useState("1.725");
  const [preview, setPreview] = useState<FareRoundingPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    const value = await getFareRounding(country);
    setSaved(value);
    setDraft(toInput(value));
    const key = stepKeyOf(value.step);
    setStepKey(key);
    setCustom(key === "custom" && value.step ? value.step : "");
  }, [country]);

  useEffect(() => {
    setSaved(null);
    setDraft(null);
    setPreview(null);
    setError(null);
    setDone(null);
    load().catch((caught) => setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة الإعداد"));
  }, [load]);

  // **المعاينةُ حيّةٌ مع كلِّ تغيير** — من الخلفية، ولا تكتب شيئاً
  useEffect(() => {
    if (!draft) return;
    const handle = window.setTimeout(() => {
      const trimmed = amount.trim();
      previewFareRounding(country, { ...draft, amount: /^\d+(\.\d{1,3})?$/.test(trimmed) ? trimmed : null })
        .then(setPreview)
        .catch((caught) => setError(caught instanceof ApiError ? caught.message : "تعذّرت المعاينة"));
    }, 250);
    return () => window.clearTimeout(handle);
  }, [country, draft, amount]);

  function pickStep(key: StepKey) {
    setStepKey(key);
    if (!draft) return;
    if (key === "none") setDraft({ ...draft, step: null });
    else if (key === "custom") setDraft({ ...draft, step: /^\d+(\.\d{1,3})?$/.test(custom) && num(custom) > 0 ? custom : draft.step });
    else setDraft({ ...draft, step: key });
  }

  async function save() {
    if (!draft) return;
    setSaving(true);
    setError(null);
    try {
      await saveFareRounding(country, draft);
      setConfirming(false);
      setDone("حُفظ — يسري على الرحلات الجديدة وحدَها، والقائمةُ بتقريبها الذي طُلبت به");
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
    } finally {
      setSaving(false);
    }
  }

  const currency = saved ? currencyLabel(saved.currency) : "";
  const fitError = preview?.fit_error ?? null;
  const changed = saved && draft && JSON.stringify(toInput(saved)) !== JSON.stringify(draft);

  return (
    <Shell
      title="تقريب الأسعار وعرضها"
      subtitle="خاناتُ العرض وخطوةُ تقريب الأجرة واتجاهُها لكلِّ دولة — للرحلات الجديدة وحدَها. لا يمسّ معادلةَ الأجرة ولا قيمَها ولا الاشتراكاتِ ولا العمولةَ ولا المحافظَ والدفتر"
    >
      <ErrorNote message={error} />
      <SuccessNote message={done} />

      {draft && saved ? (
        <div className="grid gap-6">
          <section className="ad-card grid gap-4 p-5">
            <h2 className="text-14 font-bold text-ink">الخاناتُ المعروضة</h2>
            <Segmented
              label="الخانات المعروضة"
              value={String(draft.decimals) as "0" | "1" | "2" | "3"}
              options={(["0", "1", "2", "3"] as const).map((key) => ({ key, label: digits(key) }))}
              onPick={(key) => setDraft({ ...draft, decimals: Number(key) })}
            />
            <label className="flex items-center justify-between gap-4">
              <span>
                <span className="block font-bold">المبلغُ الصحيحُ بلا كسور</span>
                <span className="ad-tone-muted text-12">
                  {digits("8")} {currency} لا {digits("8.000")} — وبكسرٍ يُرسم بالخانات المختارة ({digits("8.50")}). للعرض وحدَه
                </span>
              </span>
              <Switch
                label="المبلغ الصحيح بلا كسور"
                checked={draft.trim_whole}
                onChange={(next) => setDraft({ ...draft, trim_whole: next })}
              />
            </label>
            <p className="ad-tone-muted text-12">
              العرضُ لا يُخفي خانةً غيرَ صفريّةٍ أبداً: مبلغٌ قديمٌ مثل {digits("1.725")} يبقى {digits("1.725")} — لا يُقرَّب صامتاً.
            </p>

            <h2 className="text-14 font-bold text-ink">خطوةُ التقريب</h2>
            <Segmented label="خطوة التقريب" value={stepKey} options={STEPS.map((key) => ({ key, label: STEP_LABEL[key] }))} onPick={pickStep} />
            {stepKey === "custom" ? (
              <Field
                label={`الخطوةُ المخصّصة (${currency})`}
                dir="ltr"
                inputMode="decimal"
                value={custom}
                onChange={(event) => {
                  const text = event.target.value.trim();
                  setCustom(text);
                  if (/^\d+(\.\d{1,3})?$/.test(text) && num(text) > 0) setDraft({ ...draft, step: text });
                }}
              />
            ) : null}

            <h2 className="text-14 font-bold text-ink">الاتجاه</h2>
            <Segmented label="اتجاه التقريب" value={draft.mode} options={MODES} onPick={(mode) => setDraft({ ...draft, mode })} />

            <h2 className="text-14 font-bold text-ink">أين يُطبَّق</h2>
            <div className="grid gap-3">
              {SURFACES.map((surface) => (
                <label key={surface.key} className="flex items-center justify-between gap-4">
                  <span>
                    <span className="block font-bold">{surface.label}</span>
                    <span className="ad-tone-muted text-12">{surface.hint}</span>
                  </span>
                  <Switch
                    label={surface.label}
                    checked={draft[surface.key]}
                    disabled={draft.step === null}
                    onChange={(next) => setDraft({ ...draft, [surface.key]: next })}
                  />
                </label>
              ))}
            </div>
          </section>

          <section className="ad-card grid gap-4 p-5">
            <h2 className="text-14 font-bold text-ink">المعاينة — قبل الحفظ</h2>
            {fitError ? <ErrorNote message={fitError} /> : null}
            <Field
              label={`جرّب مبلغاً (${currency})`}
              dir="ltr"
              inputMode="decimal"
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
            />
            {preview?.amount ? (
              <p className="text-14">
                {digits(preview.amount.amount)} ⇐ <b dir="ltr">{digits(preview.amount.after_text)}</b> {currency}
              </p>
            ) : null}
            <Table
              columns="0.8fr 0.8fr 1fr 1fr 1fr"
              headers={["المسافة (كم)", "الزمن (د)", "الدقيقة", "قبل", "بعد"]}
              rows={preview?.samples ?? null}
              keyOf={(row) => `${row.distance_km}-${row.duration_min}`}
              height="auto"
              empty={{ title: "لا تسعيرةَ لهذه الدولة", hint: "تُحسب الأمثلةُ من تسعيرة الدولة المحفوظة" }}
              render={(row) => (
                <>
                  <span dir="ltr">{digits(row.distance_km)}</span>
                  <span dir="ltr">{digits(row.duration_min)}</span>
                  <span dir="ltr" className="ad-tone-muted">{digits(row.precise)}</span>
                  <span dir="ltr">{digits(row.before_text)}</span>
                  <span dir="ltr" className="font-bold">{digits(row.after_text)}</span>
                </>
              )}
            />
            {isAdmin ? (
              <Button className="w-auto" disabled={!changed || Boolean(fitError)} onClick={() => setConfirming(true)}>
                احفظ
              </Button>
            ) : (
              <p className="ad-tone-muted text-12">الحفظُ لمن يملك صلاحيّةَ كتابة الإعدادات.</p>
            )}
          </section>
        </div>
      ) : null}

      {confirming && draft && preview ? (
        <Modal title="تأكيدُ تقريب الأسعار" onClose={() => setConfirming(false)}>
          <p className="mb-3 text-14">
            يسري على <b>الرحلات الجديدة وحدَها</b> — الرحلاتُ القائمةُ والقديمةُ والمحافظُ والدفترُ لا تُمسّ. ويُكتب في سجلّ التدقيق.
          </p>
          <ul className="mb-4 grid gap-2 text-14">
            {preview.samples.slice(0, 5).map((row) => (
              <li key={`${row.distance_km}-${row.duration_min}`}>
                {digits(row.distance_km)} كم · {digits(row.duration_min)} د: <span dir="ltr">{digits(row.before_text)}</span> ⇐{" "}
                <b dir="ltr">{digits(row.after_text)}</b> {currency}
              </li>
            ))}
          </ul>
          <div className="flex gap-2">
            <Button className="w-auto" loading={saving} onClick={() => void save()}>
              أكّد الحفظ
            </Button>
            <Button className="w-auto" variant="secondary" onClick={() => setConfirming(false)}>
              تراجع
            </Button>
          </div>
        </Modal>
      ) : null}
    </Shell>
  );
}
