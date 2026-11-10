/** **تجاربُ الأسعار** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٤، SPEC §٩٧/٤).
 *
 * **لا شيءَ يعمل افتراضيّاً**: تُنشأ مسوّدة، وتبدأ بنقرة، وتوقف بنقرة، ثمّ القرار: **تطبيقُ الفائز** (النسبةُ على تسعيرة الدولة كلِّها)
 * **أو الإلغاء**. **والمقارنةُ كلُّها من الخلفية** — الطلباتُ والمكتملةُ والإلغاءاتُ ودخلُ الكباتن والإيرادُ ونسبُها؛ لا جمعَ ولا قسمةَ هنا.
 */

import { useCallback, useEffect, useState } from "react";

import { createPriceExperiment, listPriceExperiments, movePriceExperiment } from "@/api/endpoints";
import type { PriceExperiment, PriceExperimentStatus } from "@/api/types";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { useCountry } from "@/lib/country";
import { currencyOf, money, moment } from "@/lib/format";
import { digits } from "@/lib/utils";

const STATUS: Record<PriceExperimentStatus, { label: string; tone: Tone }> = {
  draft: { label: "مسوّدة", tone: "muted" },
  running: { label: "تعمل", tone: "ok" },
  stopped: { label: "موقوفة — تنتظر القرار", tone: "warn" },
  applied: { label: "طُبِّق الفائز", tone: "ink" },
  cancelled: { label: "أُلغيت", tone: "muted" },
};

export function PriceExperiments({ onError, isAdmin }: { onError: (message: string) => void; isAdmin: boolean }) {
  const { country } = useCountry();
  const currency = currencyOf(country);
  const [rows, setRows] = useState<PriceExperiment[] | null>(null);
  const [name, setName] = useState("");
  const [percent, setPercent] = useState("");
  const [share, setShare] = useState("50");
  const [days, setDays] = useState("7");
  const [lat, setLat] = useState("");
  const [lng, setLng] = useState("");
  const [radius, setRadius] = useState("");
  const [busy, setBusy] = useState(false);
  const signed = (value: string) => value.replace(/[^0-9.-]/g, "");
  const numeric = (value: string) => value.replace(/[^0-9.]/g, "");

  const load = useCallback(() => {
    listPriceExperiments(country)
      .then(setRows)
      .catch((caught: Error) => onError(caught.message));
  }, [country, onError]);

  useEffect(load, [load]);

  const area = lat && lng && radius;
  const create = () => {
    setBusy(true);
    createPriceExperiment(country, {
      name: name.trim(),
      adjust_percent: percent,
      share_percent: Number(share),
      days: Number(days),
      ...(area ? { center_lat: Number(lat), center_lng: Number(lng), radius_km: radius } : {}),
    })
      .then(() => {
        setName("");
        setPercent("");
        load();
      })
      .catch((caught: Error) => onError(caught.message))
      .finally(() => setBusy(false));
  };

  const act = (id: string, action: "start" | "stop" | "apply" | "cancel") =>
    movePriceExperiment(id, action)
      .then(load)
      .catch((caught: Error) => onError(caught.message));

  return (
    <section className="mt-24 rounded-card border border-line bg-surface p-16" aria-labelledby="price-experiments-title">
      <h2 id="price-experiments-title" className="text-15 font-bold text-ink">
        تجارب الأسعار
      </h2>
      <p className="mt-4 max-w-prose text-11 leading-snug text-muted">
        نسبةٌ على أجرة الطريق (حدُّها خمسون بالمئة زيادةً أو خصماً؛ السالبةُ خصم) لنسبةٍ من ركّاب الدولة، أو لدائرةٍ حول نقطة. الراكبُ نفسُه في الذراع
        نفسِها كلَّ مرّة، ومن في النطاق ولم يقع فيها يُحسب «مقارنة» بالسعر العاديّ. لا تعمل تجربةٌ حتى تبدأها، ولا تُسعِّر شيئاً
        ومفتاحُ «تجارب الأسعار» في الإعدادات مطفأ. و«تطبيق الفائز» يضرب تسعيرةَ الدولة كلَّها (الأساس والكيلومتر والدقيقة والحدّ
        الأدنى) في النسبة — للتجربة على الدولة كلِّها وحدَها.
      </p>
      {isAdmin ? (
        <div className="mt-12 grid grid-cols-2 gap-10 lg:grid-cols-4">
          <Field name="exp_name" label="اسم التجربة" value={name} onChange={(e) => setName(e.target.value)} />
          <Field name="exp_percent" label="النسبة على الأجرة (٪)" dir="ltr" inputMode="decimal" placeholder="10 أو -10" value={percent} onChange={(e) => setPercent(signed(e.target.value))} />
          <Field name="exp_share" label="نسبة الركّاب في التجربة (٪)" dir="ltr" inputMode="numeric" value={share} onChange={(e) => setShare(numeric(e.target.value))} />
          <Field name="exp_days" label="المدّة (أيام)" dir="ltr" inputMode="numeric" value={days} onChange={(e) => setDays(numeric(e.target.value))} />
          <Field name="exp_lat" label="خط العرض (اختياري)" dir="ltr" inputMode="decimal" value={lat} onChange={(e) => setLat(signed(e.target.value))} />
          <Field name="exp_lng" label="خط الطول (اختياري)" dir="ltr" inputMode="decimal" value={lng} onChange={(e) => setLng(signed(e.target.value))} />
          <Field name="exp_radius" label="نصف القطر كم (اختياري)" dir="ltr" inputMode="decimal" value={radius} onChange={(e) => setRadius(numeric(e.target.value))} />
          <div className="flex items-end">
            <Button size="sm" loading={busy} disabled={!name.trim() || !percent || !share || !days} onClick={create}>
              إنشاء مسوّدة
            </Button>
          </div>
        </div>
      ) : null}
      <ul className="mt-14 space-y-12">
        {(rows ?? []).map((row) => (
          <li key={row.id} className="border-t border-line pt-10 text-13">
            <div className="flex flex-wrap items-center justify-between gap-8">
              <span>
                <span className="font-semibold text-ink">{row.name}</span>{" "}
                <Badge tone={row.expired ? "warn" : STATUS[row.status].tone}>
                  {row.expired ? "انتهت مدّتها — أوقفها وقرّر" : STATUS[row.status].label}
                </Badge>
                <span className="block text-11 text-muted">
                  <span dir="ltr">{digits(row.adjust_percent)}٪</span> لـ{digits(String(row.share_percent))}٪ من الركّاب ·{" "}
                  {row.radius_km === null ? "الدولة كلُّها" : `دائرةٌ ${digits(row.radius_km)} كم`} · {digits(String(row.days))} يوماً
                  {row.ends_at ? ` · حتى ${moment(row.ends_at)}` : ""}
                </span>
              </span>
              {isAdmin ? (
                <span className="flex flex-wrap gap-6">
                  {row.status === "draft" ? (
                    <Button size="sm" onClick={() => void act(row.id, "start")}>
                      ابدأ
                    </Button>
                  ) : null}
                  {row.status === "running" ? (
                    <Button size="sm" variant="secondary" onClick={() => void act(row.id, "stop")}>
                      أوقف
                    </Button>
                  ) : null}
                  {row.can_apply ? (
                    <Button size="sm" onClick={() => void act(row.id, "apply")}>
                      طبّق الفائز على التسعيرة
                    </Button>
                  ) : null}
                  {row.status === "draft" || row.status === "running" || row.status === "stopped" ? (
                    <Button size="sm" variant="secondary" onClick={() => void act(row.id, "cancel")}>
                      ألغِ
                    </Button>
                  ) : null}
                </span>
              ) : null}
            </div>
            {row.status !== "draft" ? (
              <table className="mt-8 w-full text-11.5">
                <thead className="text-muted">
                  <tr>
                    <th className="text-start font-medium">الذراع</th>
                    <th className="text-start font-medium">طلبات</th>
                    <th className="text-start font-medium">مكتملة</th>
                    <th className="text-start font-medium">إلغاءات</th>
                    <th className="text-start font-medium">متوسّط الأجرة</th>
                    <th className="text-start font-medium">دخل الكباتن</th>
                    <th className="text-start font-medium">الإيراد (العمولة)</th>
                  </tr>
                </thead>
                <tbody>
                  {row.arms.map((arm) => (
                    <tr key={arm.arm}>
                      <td>{arm.arm === "test" ? "التجربة" : "المقارنة"}</td>
                      <td>{digits(String(arm.requests))}</td>
                      <td>
                        {digits(String(arm.completed))}
                        {arm.completion_percent !== null ? ` (${digits(String(arm.completion_percent))}٪)` : ""}
                      </td>
                      <td>
                        {digits(String(arm.cancelled))}
                        {arm.cancel_percent !== null ? ` (${digits(String(arm.cancel_percent))}٪)` : ""}
                      </td>
                      <td>{arm.average_fare !== null ? money(arm.average_fare, currency) : "—"}</td>
                      <td>{money(arm.captains, currency)}</td>
                      <td>{money(arm.commission, currency)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : null}
          </li>
        ))}
        {rows !== null && rows.length === 0 ? <li className="text-12 text-muted">لا تجاربَ بعد.</li> : null}
      </ul>
    </section>
  );
}
