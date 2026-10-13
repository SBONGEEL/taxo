/** **«مناطق التسعير»** (SPEC §٧٤-أ/٥) — سعرٌ موحَّدٌ لكلِّ الولايات **إلا الوعرة**: لكلِّ منطقةٍ وسمُ «منطقة وعرة»، **وللموسومة نسبةٌ على
 * سعر كلِّ رحلة** (افتراضاً +25%) **أو جدولُ أسعارٍ مستقلٌّ كامل**. **ولايةُ الانطلاق تحكم**، والراكبُ يرى السطرَ قبل الطلب.
 *
 * **مبنيّةٌ عامّةً لأيِّ دولة**: تتبع مبدّلَ الدولة في الرأس، **وسوقٌ بلا مناطقَ سعرُه موحَّدٌ** ويُقال ذلك. **والكتابةُ كالتسعيرة**
 * (`settings.write`، وتجميدُ التسعير يجمّدها) — **والخادمُ يحكم**، والشاشةُ تقول ردَّه بنصِّه.
 *
 * **وعرضٌ من العُدّة القائمة** (جدولٌ وحبّاتٌ ومفتاحٌ وحقلُ مال) **وخريطةٌ تعرض الحدودَ** والوعرةَ بالجمر — لا حسابَ مالٍ هنا.
 */
import { useCallback, useEffect, useMemo, useState } from "react";

import { getPricingZoneMap, listPricingZones, setZoneRule, updatePricingZone } from "@/api/endpoints";
import type { PricingZone, PricingZones, VehicleCategory } from "@/api/types";
import { Shell } from "@/components/Shell";
import { ZonesCanvas } from "@/components/ZonesCanvas";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { Field, Switch } from "@/components/ui/Field";
import { MoneyField } from "@/components/ui/Inputs";
import { Segmented } from "@/components/ui/Segmented";
import { useConfig, useCountryConfig } from "@/lib/config";
import { useCountry } from "@/lib/country";
import { useSession } from "@/lib/session";

type Mode = PricingZone["adjustment_mode"];

const RULE_FIELDS: Array<{ key: "base_fare" | "price_per_km" | "price_per_min" | "minimum_fare"; label: string }> = [
  { key: "base_fare", label: "الأساس" },
  { key: "price_per_km", label: "الكيلومتر" },
  { key: "price_per_min", label: "الدقيقة" },
  { key: "minimum_fare", label: "الحدّ الأدنى" },
];

function messageOf(caught: unknown, fallback: string): string {
  return caught instanceof Error && caught.message ? caught.message : fallback;
}

function ZoneEditor({
  zone,
  currency,
  categories,
  disabled,
  onSaved,
  onError,
}: {
  zone: PricingZone;
  currency: string | undefined;
  categories: VehicleCategory[];
  disabled: boolean;
  onSaved: (next: PricingZones, message: string) => void;
  onError: (message: string) => void;
}) {
  const [percent, setPercent] = useState(zone.adjustment_percent);
  const [drafts, setDrafts] = useState<Record<string, Record<string, string>>>(() =>
    Object.fromEntries(
      categories.map((category) => {
        const rule = zone.rules.find((row) => row.vehicle_category === category);
        return [category, Object.fromEntries(RULE_FIELDS.map((field) => [field.key, rule?.[field.key] ?? ""]))];
      }),
    ),
  );
  const [busy, setBusy] = useState(false);

  async function save(work: () => Promise<PricingZones>, message: string) {
    setBusy(true);
    try {
      onSaved(await work(), message);
    } catch (caught) {
      onError(messageOf(caught, "تعذّر الحفظ"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="flex flex-col gap-14 rounded-20 border border-line bg-surface p-18" aria-label={`منطقة ${zone.name_ar}`}>
      <div className="flex items-center gap-12">
        <div className="flex flex-1 flex-col">
          <h2 className="text-17 font-bold text-ink">
            <span className="num">{zone.code}</span> · {zone.name_ar}
          </h2>
          {zone.note ? <span className="text-11.5 text-muted">{zone.note}</span> : null}
        </div>
        <Badge tone={zone.rugged ? "warn" : "muted"}>{zone.rugged ? "منطقة وعرة" : "سعرٌ موحَّد"}</Badge>
      </div>

      <div className="flex items-center gap-12 rounded-16 bg-surface-2 px-14 py-12">
        <span className="flex flex-1 flex-col">
          <span className="text-13.5 font-semibold text-ink">منطقة وعرة</span>
          <span className="text-11.5 text-muted">ولايةُ الانطلاق تحكم — والراكبُ يرى «تسعيرة المناطق الوعرة» سطراً قبل الطلب</span>
        </span>
        <Switch
          checked={zone.rugged}
          label={`${zone.name_ar} منطقةٌ وعرة`}
          disabled={disabled || busy}
          onChange={(next) => void save(() => updatePricingZone(zone.id, { rugged: next }), next ? "وُسمت منطقةً وعرة" : "عادت إلى السعر الموحَّد")}
        />
      </div>

      {zone.rugged ? (
        <>
          <Segmented<Mode>
            label="وجهُ التعديل"
            value={zone.adjustment_mode}
            options={[
              { key: "percent", label: "نسبةٌ على سعر الرحلة" },
              { key: "table", label: "جدولُ أسعارٍ مستقلّ" },
            ]}
            onPick={(mode) =>
              !disabled && !busy && mode !== zone.adjustment_mode
                ? void save(() => updatePricingZone(zone.id, { adjustment_mode: mode }), mode === "percent" ? "بالنسبة" : "بالجدول")
                : undefined
            }
          />
          {zone.adjustment_mode === "percent" ? (
            <div className="flex flex-wrap items-end gap-8">
              <Field
                label="الزيادة (٪) على سعر كلِّ رحلةٍ تبدأ هنا"
                name="zone-percent"
                dir="ltr"
                inputMode="decimal"
                value={percent}
                disabled={disabled}
                onChange={(event) => setPercent(event.target.value)}
              />
              <Button
                size="md"
                disabled={disabled || busy || percent.trim() === zone.adjustment_percent}
                onClick={() => void save(() => updatePricingZone(zone.id, { adjustment_percent: percent.trim() }), "حُفظت النسبة")}
              >
                حفظ
              </Button>
            </div>
          ) : (
            <div className="flex flex-col gap-12">
              <p className="text-11.5 text-muted">
                يحلّ محلَّ تسعيرة الدولة لكلِّ فئة — والمحطاتُ والانتظارُ والوقفاتُ من تسعيرة الدولة. وفئةٌ بلا جدولٍ تبقى بتسعيرة الدولة.
              </p>
              {categories.map((category) => (
                <div key={category} className="flex flex-col gap-8 rounded-14 border border-line p-12">
                  <span className="text-12.5 font-semibold text-ink">{category === "economy" ? "اقتصادي" : category === "comfort" ? "مريحة" : category}</span>
                  <div className="grid gap-8 sm:grid-cols-4">
                    {RULE_FIELDS.map((field) => (
                      <MoneyField
                        key={field.key}
                        label={field.label}
                        name={`${category}-${field.key}`}
                        currency={currency}
                        value={drafts[category]?.[field.key] ?? ""}
                        disabled={disabled}
                        onChange={(next) =>
                          setDrafts((current) => ({ ...current, [category]: { ...current[category], [field.key]: next } }))
                        }
                      />
                    ))}
                  </div>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={disabled || busy || RULE_FIELDS.some((field) => !(drafts[category]?.[field.key] ?? "").trim())}
                    onClick={() =>
                      void save(
                        () =>
                          setZoneRule(zone.id, category, {
                            base_fare: drafts[category].base_fare,
                            price_per_km: drafts[category].price_per_km,
                            price_per_min: drafts[category].price_per_min,
                            minimum_fare: drafts[category].minimum_fare,
                          }),
                        "حُفظ جدولُ المنطقة",
                      )
                    }
                  >
                    حفظ الجدول
                  </Button>
                </div>
              ))}
            </div>
          )}
        </>
      ) : null}
    </section>
  );
}

export function PricingZonesScreen() {
  const { country } = useCountry();
  const { isAdmin } = useSession();
  const { config } = useConfig();
  const described = useCountryConfig(country);
  const token = config?.providers.mapbox?.public_token ?? null;
  const [data, setData] = useState<PricingZones | null>(null);
  const [map, setMap] = useState<GeoJSON.FeatureCollection | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  const load = useCallback(() => {
    setData(null);
    setMap(null);
    setError(null);
    listPricingZones(country)
      .then(setData)
      .catch((caught) => setError(messageOf(caught, "تعذّر قراءة المناطق")));
    getPricingZoneMap(country)
      .then(setMap)
      .catch(() => setMap(null));
  }, [country]);
  useEffect(load, [load]);

  const zones = useMemo(() => {
    const all = data?.zones ?? [];
    const needle = query.trim();
    return needle ? all.filter((zone) => zone.name_ar.includes(needle) || zone.code.includes(needle) || (zone.name_fr ?? "").toLowerCase().includes(needle.toLowerCase())) : all;
  }, [data, query]);
  const zone = data?.zones.find((row) => row.id === picked) ?? null;
  const rugged = data?.zones.filter((row) => row.rugged).length ?? 0;

  return (
    <Shell title="مناطق التسعير" subtitle="سعرٌ موحَّدٌ لكلِّ الولايات إلا الوعرة — ولايةُ الانطلاق تحكم، والتقريبُ بعدها">
      <ErrorNote message={error} />
      <SuccessNote message={done} />
      {data === null ? (
        <Spinner className="mx-auto" />
      ) : data.zones.length === 0 ? (
        <p className="mt-12 text-13 text-muted">لا مناطقَ لهذا السوق — سعرُه موحَّدٌ في كلِّ مكان.</p>
      ) : (
        <div className="mt-12 grid gap-16 lg:grid-cols-2">
          <div className="flex flex-col gap-12">
            {token ? <ZonesCanvas token={token} data={map} picked={picked} onPick={setPicked} /> : null}
            {data.attribution ? <p className="text-10.5 text-muted">{data.attribution}</p> : null}
            <div className="flex items-center gap-8">
              <Field label="بحث" name="zone-search" value={query} placeholder="اسمُ الولاية أو رقمُها" onChange={(event) => setQuery(event.target.value)} />
              <span className="text-12 text-muted">
                <span className="num">{data.zones.length}</span> منطقة · <span className="num">{rugged}</span> وعرة
              </span>
            </div>
            <ul className="flex max-h-[420px] flex-col gap-6 overflow-y-auto">
              {zones.map((row) => (
                <li key={row.id}>
                  <button
                    type="button"
                    onClick={() => setPicked(row.id)}
                    aria-pressed={row.id === picked}
                    className={`flex w-full items-center gap-10 rounded-12 border px-12 py-10 text-start text-13 ${row.id === picked ? "border-ink bg-surface-2" : "border-line bg-surface"}`}
                  >
                    <span className="num w-[28px] text-muted">{row.code}</span>
                    <span className="flex-1 text-ink">{row.name_ar}</span>
                    {row.rugged ? (
                      <Badge tone="warn">{row.adjustment_mode === "percent" ? `+${Number(row.adjustment_percent)}٪` : "جدول"}</Badge>
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>
          </div>
          {zone ? (
            <ZoneEditor
              key={zone.id + zone.adjustment_mode + zone.rugged}
              zone={zone}
              currency={described?.currency}
              categories={(described?.vehicle_categories ?? ["economy", "comfort"]) as VehicleCategory[]}
              disabled={!isAdmin}
              onSaved={(next, message) => {
                setData(next);
                setDone(`${zone.name_ar}: ${message}`);
                setError(null);
                getPricingZoneMap(country).then(setMap).catch(() => undefined);
              }}
              onError={setError}
            />
          ) : (
            <p className="text-13 text-muted">اختر منطقةً من الخريطة أو القائمة.</p>
          )}
        </div>
      )}
    </Shell>
  );
}
