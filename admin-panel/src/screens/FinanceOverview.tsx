/** **«المالية العامة»** (SPEC §٧٤-أ/٩ — لوحةُ «اللوحة — المالية العامة» في Claude Design): **كلُّ الدول متجاورةً، كلٌّ بعملته**.
 *
 * **ولا يُجمع في الشاشة شيء** (§14): كلُّ عمودٍ صفحةُ «مالية الدولة» نفسُها من الخلفية، **والمجموعُ التقريبيُّ عمودٌ تحسبه الخلفيةُ** بأسعارٍ
 * يضعها المالك، **موسوماً «تقريبي — بسعر صرف تضعه الإدارة»** ومعه كلُّ سعرٍ وتاريخُه — **وعملةٌ بلا سعرٍ تُسمّى** ولا يُرسم المجموعُ كاملاً.
 *
 * **والنزولُ من أيِّ رقمٍ** يفتح «مالية الدولة» بدولته — حيث المستخدمون والمعاملات وراءه. **والمطابقةُ مع الدفتر لكلِّ دولةٍ وحكمٌ واحدٌ على
 * الكلّ**، والتحذيرُ يسمّي الدولةَ التي لا تطابق. **والمنعُ من الخادم**: ٤٠٣ ⇒ صفحةُ «تحتاج الصلاحية».
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "@/api/client";
import { exportFinanceOverview, getExchangeRates, getFinanceOverview, setExchangeRates } from "@/api/endpoints";
import type { Currency, ExchangeRates, FinanceOverview, FinanceOverviewQuery, FinanceSummary } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { Field } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { useCountries } from "@/lib/countries";
import { day, money } from "@/lib/format";
import { digits } from "@/lib/utils";
import { AUDIT_LINE, Denied, FilterBar, INITIAL } from "@/screens/FinanceSummary";
import type { Filters } from "@/screens/FinanceSummary";
import { Icon } from "@/taxo2";

function queryOf(filters: Filters): FinanceOverviewQuery | null {
  if (filters.period === "custom" && (!filters.from || !filters.to)) return null;
  return {
    period: filters.period,
    from_date: filters.period === "custom" ? filters.from : undefined,
    to_date: filters.period === "custom" ? filters.to : undefined,
    user_type: filters.userType === "all" ? undefined : filters.userType,
    method: filters.method === "all" ? undefined : filters.method,
    status: filters.status === "all" ? undefined : filters.status,
  };
}

function messageOf(caught: unknown, fallback: string): string {
  return caught instanceof Error && caught.message ? caught.message : fallback;
}

function RatesEditor({ current, currencies, onSaved, onClose }: {
  current: ExchangeRates;
  currencies: Currency[];
  onSaved: (next: ExchangeRates) => void;
  onClose: () => void;
}) {
  const [reference, setReference] = useState(current.reference ?? "USD");
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(currencies.map((code) => [code, current.rates.find((row) => row.currency === code)?.rate ?? ""])),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function save() {
    setBusy(true);
    setError(null);
    try {
      const rates = currencies
        .filter((code) => values[code]?.trim())
        .map((code) => ({ currency: code, rate: values[code].trim() }));
      onSaved(await setExchangeRates({ reference: reference.trim().toUpperCase(), rates }));
    } catch (caught) {
      setError(messageOf(caught, "تعذّر الحفظ"));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="أسعار الصرف — للمجموع التقريبيّ وحدَه" onClose={onClose}>
      <p className="mb-12 text-12.5 leading-relaxed text-muted">
        كم وحدةً من العملة المرجعيّة لوحدةٍ واحدةٍ من عملة كلِّ سوق. لا يُحوَّل بها مال — يُضرب بها المجموعُ المعروضُ وحدَه، ويُحفظ كلُّ
        سعرٍ بتاريخه.
      </p>
      <ErrorNote message={error} />
      <div className="flex flex-col gap-10">
        <Field label="العملة المرجعيّة (USD · EUR)" name="rate-reference" dir="ltr" value={reference} onChange={(event) => setReference(event.target.value)} />
        {currencies.map((code) => (
          <Field
            key={code}
            label={`1 ${code} = … ${reference.trim().toUpperCase() || "?"}`}
            name={`rate-${code}`}
            dir="ltr"
            inputMode="decimal"
            value={values[code] ?? ""}
            onChange={(event) => setValues((now) => ({ ...now, [code]: event.target.value }))}
          />
        ))}
      </div>
      <div className="mt-14 flex gap-8">
        <Button disabled={busy || reference.trim().length !== 3} onClick={() => void save()}>
          حفظ
        </Button>
        <Button variant="secondary" onClick={onClose}>
          تراجع
        </Button>
      </div>
    </Modal>
  );
}

export function FinanceOverviewScreen() {
  const { rows } = useCountries();
  const [filters, setFilters] = useState<Filters>(INITIAL);
  const [data, setData] = useState<FinanceOverview | null>(null);
  const [rates, setRates] = useState<ExchangeRates | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [denied, setDenied] = useState(false);
  const [editing, setEditing] = useState(false);
  const [exporting, setExporting] = useState(false);
  const query = useMemo(() => queryOf(filters), [filters]);

  const load = useCallback(() => {
    setData(null);
    setError(null);
    if (!query) return;
    getFinanceOverview(query)
      .then(setData)
      .catch((caught) => {
        if (caught instanceof ApiError && caught.status === 403) setDenied(true);
        else setError(messageOf(caught, "تعذّر قراءة المالية العامة"));
      });
    getExchangeRates()
      .then(setRates)
      .catch(() => setRates(null));
  }, [query]);
  useEffect(load, [load]);

  if (denied) {
    return (
      <Shell title="المالية العامة">
        <Denied />
      </Shell>
    );
  }

  const name = (code: string) => rows?.find((row) => row.country_code === code)?.name ?? code;
  const countries: FinanceSummary[] = data?.countries ?? [];
  const first = countries[0];
  const unreconciled = countries.filter((country) => !country.reconciliation.reconciled);
  const combined = data?.combined ?? null;
  const currencies = countries.map((country) => country.window.currency);

  return (
    <Shell
      title="المالية العامة"
      subtitle="كلُّ الدول متجاورةً — كلٌّ بعملته، ولا تُجمع العملات. حساباتُ التجربة مستثناةٌ دائماً"
      actions={
        <div className="flex gap-8">
          <Button size="sm" variant="secondary" disabled={!rates} onClick={() => setEditing(true)}>
            أسعار الصرف
          </Button>
          <Button
            size="sm"
            loading={exporting}
            disabled={!data || !query}
            onClick={() => {
              if (!query) return;
              setExporting(true);
              exportFinanceOverview(query)
                .catch((caught) => setError(messageOf(caught, "تعذّر تصديرُ الملفّ")))
                .finally(() => setExporting(false));
            }}
          >
            تصدير Excel
          </Button>
        </div>
      }
    >
      <FilterBar filters={filters} onChange={setFilters} />
      <ErrorNote message={error} />
      <SuccessNote message={done} />
      {query === null ? (
        <p className="mt-18 text-12.5 text-muted">اختر تاريخَي البداية والنهاية — بيوم كلِّ سوق.</p>
      ) : data === null ? (
        error ? null : <Spinner className="mx-auto my-38" />
      ) : (
        <>
          {data.reconciled ? (
            <div className="ad-note ok" role="status">
              <Icon name="check_circle" fill />
              <span>المجاميعُ تطابق الدفتر في كلِّ الدول</span>
            </div>
          ) : (
            <div className="ad-note danger" role="alert">
              <Icon name="error" fill />
              <span>
                المجاميعُ لا تطابق الدفتر في: {unreconciled.map((country) => name(country.window.country_code)).join(" · ")} — افتح «مالية الدولة»
                لترى الفرق
              </span>
            </div>
          )}
          <section className="mt-12 overflow-hidden rounded-20 border border-line bg-surface">
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-13">
                <thead>
                  <tr className="bg-surface-2">
                    <th className="px-16 py-12 text-start font-semibold text-muted">البند</th>
                    {countries.map((country) => (
                      <th key={country.window.country_code} className="px-16 py-12 text-end">
                        <Link to={`/finance/country/${country.window.country_code}`} className="font-bold text-ink">
                          {name(country.window.country_code)}
                        </Link>
                        <div className="text-11 font-normal text-muted">{country.window.currency}</div>
                      </th>
                    ))}
                    {combined ? (
                      <th className="bg-[var(--t2-accent-soft)] px-16 py-12 text-end">
                        <span className="font-bold text-ink">المجموع · {combined.reference}</span>
                        <div className="text-11 font-semibold text-[var(--t2-accent-text)]">{combined.note}</div>
                      </th>
                    ) : null}
                  </tr>
                </thead>
                <tbody>
                  {first?.groups.map((group) => (
                    <GroupRows key={group.key} group={group} countries={countries} combined={combined} />
                  ))}
                </tbody>
              </table>
            </div>
            {combined ? (
              <p className="border-t border-line px-16 py-12 text-11.5 text-muted">
                الأسعار:{" "}
                {combined.rates.map((rate) => `1 ${rate.currency} = ${rate.rate} ${combined.reference} (${digits(day(rate.set_at))})`).join(" · ")}
              </p>
            ) : (
              <p className="border-t border-line px-16 py-12 text-11.5 text-muted">
                لا مجموعَ يجمع عملتين — اضبط أسعارَ الصرف ليظهر مجموعٌ تقريبيٌّ بعملةٍ مرجعيّة.
              </p>
            )}
          </section>
        </>
      )}
      <p className="mt-22 text-11.5 text-muted">
        <Icon name="history" /> {AUDIT_LINE}
      </p>
      {editing && rates ? (
        <RatesEditor
          current={rates}
          currencies={currencies.length ? currencies : (["JOD", "LYD", "DZD"] as Currency[])}
          onClose={() => setEditing(false)}
          onSaved={(next) => {
            setRates(next);
            setEditing(false);
            setDone("حُفظت أسعارُ الصرف");
            load();
          }}
        />
      ) : null}
    </Shell>
  );
}

function GroupRows({
  group,
  countries,
  combined,
}: {
  group: FinanceSummary["groups"][number];
  countries: FinanceSummary[];
  combined: FinanceOverview["combined"];
}) {
  return (
    <>
      <tr>
        <td colSpan={countries.length + (combined ? 2 : 1)} className="bg-[var(--t2-sunken)] px-16 py-10 text-12 font-bold text-muted">
          {group.title}
        </td>
      </tr>
      {group.metrics.map((metric) => {
        const approx = combined?.metrics.find((row) => row.key === metric.key);
        return (
          <tr key={metric.key} className="border-t border-line">
            <td className="px-16 py-12 text-ink">{metric.label}</td>
            {countries.map((country) => {
              const value = country.groups.flatMap((row) => row.metrics).find((row) => row.key === metric.key);
              return (
                <td key={country.window.country_code} className="num px-16 py-12 text-end" dir="ltr">
                  {value?.applicable ? (
                    <Link to={`/finance/country/${country.window.country_code}`} className="text-ink">
                      {money(value.amount, country.window.currency)}
                    </Link>
                  ) : (
                    <span className="text-muted">—</span>
                  )}
                </td>
              );
            })}
            {combined ? (
              <td className="num bg-[var(--t2-accent-soft)] px-16 py-12 text-end" dir="ltr">
                {approx?.approx_value != null ? (
                  `${approx.approx_value} ${combined.reference}`
                ) : (
                  <span className="text-12 text-muted" dir="rtl">
                    ينقصه سعرُ {approx?.missing.join(" · ")}
                  </span>
                )}
              </td>
            ) : null}
          </tr>
        );
      })}
    </>
  );
}
