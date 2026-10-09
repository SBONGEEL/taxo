/** «الأماكن» — أماكنُ المالك على خرائط التطبيقين وفي أوّل البحث (SPEC §٧١-د/١٤).
 *
 * **صفحةُ «المرافق الحيويّة» صارت «الأماكن»** بقسمين (§٧١-ز/د): الأماكنُ هنا، **والمطاراتُ برسومها في صفحتها كما هي** — رابطٌ لا
 * نسخة: رسمُ المطار مالٌ، ومكانٌ يُضاف ليُقرأ اسمُه لا يقف على بُعد حقلٍ منه. **والمطاراتُ المفعَّلةُ تظهر على الخرائط مع الأماكن**
 * من بيتها، فلا تُضاف هنا ثانية.
 *
 * **وثلاثةٌ تقولها الشاشة**:
 * 1. **لا يظهر شيءٌ قبل المفتاح**: «أسماءُ الأماكن على الخريطة» في الإعدادات — مطفأً تبقى الخرائطُ كما كانت.
 * 2. **ولا زرَّ حذف**: الإخفاءُ هو الإيقاف — والمكانُ يبقى في القائمة.
 * 3. **والموقعُ يُلصق كما يُنسخ من خرائط Google** («31.9765, 35.8435»: خطُّ العرض أوّلاً) — ويُفحص هنا ويُرفض في الخلفية بنصِّها.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { NavLink } from "react-router-dom";

import { ApiError } from "@/api/client";
import { createMapPlace, listMapPlaces, updateMapPlace } from "@/api/endpoints";
import type { CountryCode, MapPlace, MapPlaceCategory } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Table } from "@/components/Table";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { Field, Select, Switch } from "@/components/ui/Field";
import { Modal } from "@/components/ui/Modal";
import { useCountry } from "@/lib/country";
import { FormErrors, useFormError } from "@/lib/form-errors";
import { day } from "@/lib/format";
import { useSession } from "@/lib/session";
import { digits } from "@/lib/utils";
import { Icon } from "@/taxo2";

/** **مرآةُ `MAP_PLACE_CATEGORIES`** بترتيب الخلفية — والاسمُ العربيُّ لكلٍّ. */
export const CATEGORY_LABEL: Record<MapPlaceCategory, string> = {
  market: "سوق",
  shop: "محلّ",
  mall: "مول",
  mosque: "مسجد",
  church: "كنيسة",
  hospital: "مستشفى",
  clinic: "عيادة",
  school: "مدرسة",
  university: "جامعة",
  hotel: "فندق",
  restaurant: "مطعم",
  landmark: "معلَم",
  government: "دائرة حكومية",
  station: "محطّة",
  neighborhood: "حيّ",
  street: "شارع",
  other: "أخرى",
  airport: "مطار",
};

/** **أصلُ المستورد في OpenStreetMap** — رابطٌ يفتح العنصرَ نفسَه للمراجعة. */
const osmUrl = (ref: string) => `https://www.openstreetmap.org/${ref}`;

const NAME_MAX = 80;

/** «31.9765, 35.8435» أو «31.9765 35.8435» — **خطُّ العرض أوّلاً** كما تنسخه خرائطُ Google. و`null` لما لا يُقرأ موقعاً. */
export function parsePoint(text: string): { lat: number; lng: number } | null {
  const parts = text.trim().split(/[\s,،]+/).filter(Boolean);
  if (parts.length !== 2) return null;
  const [lat, lng] = parts.map(Number);
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
  if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return null;
  return { lat, lng };
}

const pointText = (place: Pick<MapPlace, "lat" | "lng">) => `${place.lat.toFixed(6)}, ${place.lng.toFixed(6)}`;

export function PlacesScreen() {
  const { country } = useCountry();
  const { isAdmin } = useSession();
  const [rows, setRows] = useState<MapPlace[] | null>(null);
  const [query, setQuery] = useState("");
  // **المستوردُ يُراجَع** (§٧١-ح/٤): مصفاةٌ تعرضه وحدَه
  const [origin, setOrigin] = useState<"all" | "owner" | "osm">("all");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [editing, setEditing] = useState<MapPlace | "new" | null>(null);

  const load = useCallback(async () => {
    setRows(await listMapPlaces(country));
  }, [country]);

  useEffect(() => {
    setRows(null);
    setError(null);
    setDone(null);
    load().catch((caught) => setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة الأماكن"));
  }, [load]);

  const shown = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!rows) return rows;
    return rows.filter(
      (row) =>
        (origin === "all" || row.source === origin) &&
        (!needle || row.name_ar.includes(needle) || (row.name_en ?? "").toLowerCase().includes(needle)),
    );
  }, [rows, query, origin]);
  const imported = rows?.filter((row) => row.source === "osm").length ?? 0;

  return (
    <Shell
      title="الأماكن"
      subtitle="أسماءٌ تظهر على خرائط التطبيقين فوق أسماء الخريطة، وتتقدّم البحثَ حين تطابق"
      actions={
        isAdmin ? (
          <Button size="sm" onClick={() => setEditing("new")}>
            إضافة مكان
          </Button>
        ) : null
      }
    >
      <div className="ad-fac-note">
        <Icon name="info" />
        <span className="ad-fac-note-text">
          لا يظهر شيءٌ على الخرائط قبل إشعال «أسماء الأماكن على الخريطة» من الإعدادات. والمطاراتُ المفعَّلةُ تظهر معها من صفحتها
          برسومها.
        </span>
        <NavLink to="/settings" className="ad-fac-note-link">
          الإعدادات
        </NavLink>
        <NavLink to="/facilities" className="ad-fac-note-link">
          المطارات ورسومها
        </NavLink>
      </div>

      <ErrorNote message={error} />
      <SuccessNote message={done} />

      <div className="mb-12 flex flex-wrap items-end gap-12">
        <div className="w-full max-w-[360px]">
          <Field
            label="ابحث في الأماكن"
            name="places_query"
            value={query}
            placeholder="بالعربيّة أو الإنجليزيّة"
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
        <div className="w-full max-w-[220px]">
          <Select
            label="المصدر"
            name="places_origin"
            value={origin}
            onChange={(event) => setOrigin(event.target.value as typeof origin)}
          >
            <option value="all">الكلّ</option>
            <option value="owner">أضفتُها بيدي</option>
            <option value="osm">مستوردة للمراجعة</option>
          </Select>
        </div>
      </div>
      {imported ? (
        <p className="ad-hint mb-12">
          {digits(imported)} مكاناً مستورداً من OpenStreetMap بمواقعه الدقيقة — <b>للبحث</b>: يتقدّم نتائجَ البحث ولا يُرسم على الخريطة
          (أسماءُ OpenStreetMap في الخريطة أصلاً). راجِعه وعدّله أو أخفِه. بياناتُه © مساهمو OpenStreetMap، برخصة ODbL.
        </p>
      ) : null}

      <Table
        columns="1.5fr 1.2fr 0.7fr 1.1fr 0.7fr 0.9fr auto"
        headers={["الاسم", "بالإنجليزيّة", "الفئة", "الموقع", "الحال", "آخر تعديل", ""]}
        rows={shown}
        keyOf={(row) => row.id}
        empty={{
          title: query ? "لا مكانَ بهذا الاسم" : "لا أماكن في هذا السوق بعد",
          hint: "أضف مكاناً باسمه العربيّ وموقعه — ويظهر على الخرائط حين يُشعَل مفتاحُه.",
        }}
        render={(row) => (
          <>
            {isAdmin ? (
              <button type="button" className="ad-fac-name" onClick={() => setEditing(row)}>
                {row.name_ar}
              </button>
            ) : (
              <span className="ad-fac-name">{row.name_ar}</span>
            )}
            <span className="ad-tone-muted" dir="ltr">
              {row.name_en ?? "—"}
            </span>
            <span className="ad-tone-muted">
              {CATEGORY_LABEL[row.category] ?? row.category}
              {row.source === "osm" && row.osm_ref ? (
                <>
                  {" · "}
                  <a href={osmUrl(row.osm_ref)} target="_blank" rel="noreferrer">
                    مستورد
                  </a>
                </>
              ) : null}
            </span>
            <span className="ad-tone-muted" dir="ltr">
              {pointText(row)}
            </span>
            <Badge tone={row.is_hidden ? "muted" : "ok"}>{row.is_hidden ? "مخفيّ" : "ظاهر"}</Badge>
            <span className="ad-tone-muted">{day(row.updated_at)}</span>
            {isAdmin ? (
              <Button size="sm" variant="secondary" className="w-auto" onClick={() => setEditing(row)}>
                حرّر
              </Button>
            ) : (
              <span />
            )}
          </>
        )}
      />

      {editing ? (
        <PlaceEditor
          place={editing === "new" ? null : editing}
          country={country}
          onClose={() => setEditing(null)}
          onSaved={(message) => {
            setEditing(null);
            setDone(message);
            setError(null);
            void load();
          }}
        />
      ) : null}
    </Shell>
  );
}

/** محرِّرُ المكان — **الإنشاءُ والتعديلُ ورقةٌ واحدة**، والتعديلُ يرسل ما تغيّر وحدَه (فالتدقيقُ يقول ما تغيّر حقاً). */
function PlaceEditor({
  place,
  country,
  onClose,
  onSaved,
}: {
  place: MapPlace | null;
  country: CountryCode;
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const [nameAr, setNameAr] = useState(place?.name_ar ?? "");
  const [nameEn, setNameEn] = useState(place?.name_en ?? "");
  const [category, setCategory] = useState<MapPlaceCategory>(place?.category ?? "landmark");
  const [where, setWhere] = useState(place ? pointText(place) : "");
  const [hidden, setHidden] = useState(place?.is_hidden ?? false);
  const [busy, setBusy] = useState(false);
  const form = useFormError();

  const ar = nameAr.trim().replace(/\s+/g, " ");
  const en = nameEn.trim().replace(/\s+/g, " ");
  const point = parsePoint(where);
  const ready = ar.length >= 2 && ar.length <= NAME_MAX && point !== null;

  const changes: Parameters<typeof updateMapPlace>[1] = {};
  if (place) {
    if (ar !== place.name_ar) changes.name_ar = ar;
    if ((en || null) !== place.name_en) changes.name_en = en || null;
    if (category !== place.category) changes.category = category;
    if (point && point.lat !== place.lat) changes.lat = point.lat;
    if (point && point.lng !== place.lng) changes.lng = point.lng;
    if (hidden !== place.is_hidden) changes.is_hidden = hidden;
  }
  const dirty = place ? Object.keys(changes).length > 0 : ar !== "" || where.trim() !== "";

  async function save() {
    if (!point) return;
    setBusy(true);
    form.clear();
    try {
      if (place) {
        await updateMapPlace(place.id, changes);
        onSaved(`حُفظ تعديلُ «${ar}»`);
      } else {
        await createMapPlace({
          country_code: country,
          name_ar: ar,
          name_en: en || null,
          category,
          lat: point.lat,
          lng: point.lng,
          is_hidden: hidden,
        });
        onSaved(`أُضيف «${ar}»`);
      }
    } catch (caught) {
      form.capture(caught, "تعذّر الحفظ");
    } finally {
      setBusy(false);
    }
  }

  return (
    <FormErrors value={form.field}>
      <Modal title={place ? `تعديل «${place.name_ar}»` : "مكانٌ جديد"} onClose={dirty ? () => undefined : onClose}>
        <div className="grid gap-12">
          <Field
            label="الاسم بالعربيّة"
            name="name_ar"
            value={nameAr}
            maxLength={NAME_MAX}
            placeholder="مكة مول"
            onChange={(event) => setNameAr(event.target.value)}
          />
          <Field
            label="الاسم بالإنجليزيّة (اختياري)"
            name="name_en"
            dir="ltr"
            value={nameEn}
            maxLength={NAME_MAX}
            placeholder="Mecca Mall"
            onChange={(event) => setNameEn(event.target.value)}
          />
          <Select
            label="الفئة"
            name="category"
            value={category}
            onChange={(event) => setCategory(event.target.value as MapPlaceCategory)}
          >
            {(Object.keys(CATEGORY_LABEL) as MapPlaceCategory[]).map((key) => (
              <option key={key} value={key}>
                {CATEGORY_LABEL[key]}
              </option>
            ))}
          </Select>
          <Field
            label="الموقع"
            name="lat"
            dir="ltr"
            value={where}
            placeholder="31.976500, 35.843500"
            onChange={(event) => setWhere(event.target.value)}
            error={where.trim() !== "" && !point ? "خطُّ العرض ثمّ خطُّ الطول، بينهما فاصلة — كما تنسخه خرائطُ Google" : undefined}
          />
          <p className="ad-hint">
            انقر بالزرّ الأيمن على المكان في خرائط Google، وانسخ الرقمين الظاهرين في أوّل القائمة، والصقهما هنا.
          </p>
          <div className="ad-fac-switch">
            <Switch checked={!hidden} label="ظاهر" onChange={(next) => setHidden(!next)} />
            <span className="ad-fac-switch-text">
              {hidden ? "مخفيّ — لا يُرسم ولا يُبحث، ويبقى هنا" : "ظاهر — على الخرائط وفي البحث"}
            </span>
          </div>
        </div>

        <ErrorNote message={form.message} />

        <div className="ad-modal-actions">
          <Button size="md" loading={busy} disabled={!ready || !dirty} onClick={() => void save()}>
            {place ? "حفظ التعديل" : "أضف المكان"}
          </Button>
          <Button size="md" variant="secondary" onClick={onClose}>
            تراجع
          </Button>
        </div>
      </Modal>
    </FormErrors>
  );
}
