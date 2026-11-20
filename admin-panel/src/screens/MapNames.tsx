/** «أماكن بلا اسم عربي» — ما على خرائط التطبيقين بلا اسمٍ عربيٍّ في أيِّ مصدرٍ مفتوح، والمشرفُ يكتبه (أمرُ المالك ٢٠٢٦-١١-٢٠، SPEC §١٠٩-ب).
 *
 * **ثلاثةٌ تقولها الشاشة**:
 * 1. **القائمةُ من بناء الخريطة** (OSM وOverture وWikidata وGeoNames، شهريّاً) — الأهمُّ أوّلاً، لكلِّ مدينة.
 * 2. **الاسمُ بالعربيّة وحدَها، ويكتبه إنسان** — لا ترجمةَ آليّة. **والعلاماتُ التجاريّةُ ليست هنا**: تبقى كما تكتبها.
 * 3. **يظهر في التطبيقين خلال دقائق** فوق اسم الخريطة، ويُختم في سجلّ التدقيق؛ و«ما كُتب» يُراجَع ويُزال من تحت.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import { deleteMapName, listMapNameFixes, listMissingArabicPlaces, putMapName } from "@/api/endpoints";
import type { MapNameFix, MissingArabicPage, MissingArabicPlace } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Table } from "@/components/Table";
import { Button } from "@/components/ui/Button";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { Field, Select } from "@/components/ui/Field";
import { useCountry } from "@/lib/country";
import { day } from "@/lib/format";
import { useSession } from "@/lib/session";
import { digits } from "@/lib/utils";

const PAGE = 50;
const ARABIC = /[؀-ۿ]/;
const LATIN = /[A-Za-z]/;

/** **اسمٌ عربيٌّ خالص** — المرآةُ في الواجهة لقاعدة الخلفية (`map_names.clean_name`)، والخلفيّةُ تحكم */
export function arabicNameProblem(value: string): string | null {
  const name = value.trim();
  if (!name) return "اكتب الاسمَ العربيّ";
  if (!ARABIC.test(name) || LATIN.test(name)) return "بالعربيّة وحدَها — بلا أحرفٍ لاتينيّة";
  return null;
}

export function MapNamesScreen() {
  const { country } = useCountry();
  const { isAdmin } = useSession();
  const [city, setCity] = useState("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<MissingArabicPage | null>(null);
  const [fixes, setFixes] = useState<MapNameFix[] | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [unreachable, setUnreachable] = useState(false);

  /** **تحميلان مستقلّان**: «ما كُتب» من قاعدتنا، والقائمةُ من خدمة الأماكن — سقوطُ الخدمة لا يُخفي ما كُتب
   *  ولا يُبقي الجدولَ هيكلَ تحميلٍ إلى الأبد (قِيس على مكدّس التطوير ٢٠٢٦-١١-٢٠) */
  const load = useCallback(async () => {
    const [missing, written] = await Promise.allSettled([
      listMissingArabicPlaces(country, city, offset, PAGE),
      listMapNameFixes(country),
    ]);
    setPage(missing.status === "fulfilled" ? missing.value : { built: true, total: 0, cities: [], items: [] });
    setUnreachable(missing.status === "rejected");
    setFixes(written.status === "fulfilled" ? written.value : []);
    const failed = [missing, written].find((r): r is PromiseRejectedResult => r.status === "rejected");
    if (failed) throw failed.reason;
  }, [country, city, offset]);

  useEffect(() => {
    setPage(null);
    setFixes(null);
    setError(null);
    load().catch((caught) => setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة القائمة"));
  }, [load]);

  useEffect(() => {
    setCity("");
    setOffset(0);
  }, [country]);

  async function save(place: MissingArabicPlace) {
    const name = drafts[place.okey] ?? "";
    const problem = arabicNameProblem(name);
    if (problem) {
      setError(`${place.name}: ${problem}`);
      return;
    }
    setBusy(place.okey);
    setError(null);
    try {
      await putMapName(place.okey, { country_code: country, name_ar: name, original_name: place.name, city: place.city });
      setDone(`كُتب «${name.trim()}» مكانَ «${place.name}» — يظهر في التطبيقين خلال دقائق`);
      setDrafts(({ [place.okey]: _gone, ...rest }) => rest);
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر حفظ الاسم");
    } finally {
      setBusy(null);
    }
  }

  async function unset(fix: MapNameFix) {
    setBusy(fix.okey);
    setError(null);
    try {
      await deleteMapName(fix.okey);
      setDone(`أُزيل «${fix.name_ar}» — يعود «${fix.original_name || "الاسم الأصليّ"}»`);
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّرت الإزالة");
    } finally {
      setBusy(null);
    }
  }

  const total = page?.total ?? 0;
  const cityOptions = [
    { value: "", label: `كلُّ المدن (${digits(String(page?.cities.reduce((sum, c) => sum + c.count, 0) ?? 0))})` },
    ...(page?.cities ?? []).map((c) => ({ value: c.city, label: `${c.city} (${digits(String(c.count))})` })),
  ];

  return (
    <Shell title="أماكن بلا اسم عربي" subtitle="أماكنُ على خرائط التطبيقين لا اسمَ عربيّاً لها في أيِّ مصدرٍ مفتوح — اكتب اسمها كما يعرفه الناس">
      <ErrorNote message={error} />
      <SuccessNote message={done} />

      {page && !page.built ? (
        <p className="ad-tone-muted mb-12">القائمةُ تظهر بعد رفع بناء الخريطة القادم — الفهرسُ على الخادم أقدمُ منها.</p>
      ) : null}

      <div className="mb-12 flex flex-wrap items-end gap-12">
        <div className="w-full max-w-[360px]">
          <Select
            label="المدينة"
            name="map_names_city"
            value={city}
            onChange={(event) => {
              setCity(event.target.value);
              setOffset(0);
            }}
          >
            {cityOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </div>
        <span className="ad-tone-muted">
          {digits(String(total))} مكاناً — الأهمُّ أوّلاً · لا ترجمةَ آليّة، والعلاماتُ التجاريّةُ تبقى كما تكتبها
        </span>
      </div>

      <Table
        height="compact"
        columns="1.4fr 1fr 1fr 1.6fr auto"
        headers={["الاسمُ على الخريطة", "المدينة", "النوع", "الاسمُ العربيّ", ""]}
        rows={page?.items ?? null}
        keyOf={(row) => row.okey}
        empty={
          unreachable
            ? { title: "لم تُقرأ القائمة", hint: "خدمةُ الأماكن لا تجيب الآن — لا يعني هذا أنّ كلَّ مكانٍ له اسمٌ عربيّ." }
            : { title: "لا مكانَ بلا اسمٍ عربيّ هنا", hint: "كلُّ ما على الخريطة في هذه المدينة له اسمٌ عربيّ." }
        }
        render={(row) => (
          <>
            <a
              dir="ltr"
              href={`https://www.google.com/maps?q=${row.lat},${row.lng}`}
              target="_blank"
              rel="noreferrer"
              className="ad-fac-name"
            >
              {row.name}
            </a>
            <span className="ad-tone-muted">{row.city}</span>
            <span className="ad-tone-muted" dir="ltr">
              {row.tag}
            </span>
            {isAdmin ? (
              <Field
                label="الاسمُ العربيّ"
                name={`ar_${row.okey}`}
                value={drafts[row.okey] ?? ""}
                onChange={(event) => setDrafts((all) => ({ ...all, [row.okey]: event.target.value }))}
                maxLength={120}
              />
            ) : (
              <span className="ad-tone-muted">—</span>
            )}
            {isAdmin ? (
              <Button
                size="sm"
                className="w-auto"
                disabled={busy === row.okey || !(drafts[row.okey] ?? "").trim()}
                onClick={() => void save(row)}
              >
                احفظ
              </Button>
            ) : (
              <span />
            )}
          </>
        )}
      />

      <div className="mt-12 flex items-center gap-12">
        <Button size="sm" variant="secondary" className="w-auto" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
          السابق
        </Button>
        <span className="ad-tone-muted">
          {digits(String(Math.min(total, offset + 1)))}–{digits(String(Math.min(total, offset + PAGE)))} من {digits(String(total))}
        </span>
        <Button size="sm" variant="secondary" className="w-auto" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>
          التالي
        </Button>
      </div>

      <h2 className="mb-8 mt-24 text-15 font-bold">ما كُتب</h2>
      <Table
        height="auto"
        columns="1.4fr 1.4fr 1fr 0.8fr auto"
        headers={["الاسمُ العربيّ", "كان", "المدينة", "آخر تعديل", ""]}
        rows={fixes}
        keyOf={(row) => row.okey}
        empty={{ title: "لم يُكتب اسمٌ بعد", hint: "ما تكتبه فوق يظهر هنا، ويمكن إزالتُه فيعود الاسمُ الأصليّ." }}
        render={(row) => (
          <>
            <span className="ad-fac-name">{row.name_ar}</span>
            <span className="ad-tone-muted" dir="ltr">
              {row.original_name || "—"}
            </span>
            <span className="ad-tone-muted">{row.city || "—"}</span>
            <span className="ad-tone-muted">{day(row.updated_at)}</span>
            {isAdmin ? (
              <Button size="sm" variant="secondary" className="w-auto" disabled={busy === row.okey} onClick={() => void unset(row)}>
                أزِل
              </Button>
            ) : (
              <span />
            )}
          </>
        )}
      />
    </Shell>
  );
}
