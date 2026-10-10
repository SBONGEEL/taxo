/** **فئاتُ الرحلة** (A40، SPEC §٦٧، لوحتُها في Claude Design «فئات الرحلة») — لكلِّ دولة.
 *
 * **المدمجتان أوّلاً قراءةً**: «اقتصادي» و«مريح» تعملان كما اليوم حرفاً وتتبعان فئةَ المركبة، فلا تُعدَّلان من هنا. **ثمّ الجديدة**: إضافةٌ
 * وتعديلٌ وتشغيلٌ وإطفاءٌ وترتيب، وشروطُ المركبة، **ومنحُ كبتنٍ أو نزعُها منه**. **والأسعارُ في «التسعيرة»** — والخادمُ يرفض تشغيلَ فئةٍ بلا
 * أسعارٍ موجبة ويقول علّتَه، فلا تُعيد الشاشةُ القاعدة.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  createRideCategory,
  listCategoryAccess,
  listDrivers,
  listRideCategories,
  setCategoryAccess,
  updateRideCategory,
} from "@/api/endpoints";
import type { CategoryAccess, RideCategory, VehicleBodyType, VehicleFuel } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Button } from "@/components/ui/Button";
import { Checkbox, Field, Select } from "@/components/ui/Field";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { Picker, type PickerOption } from "@/components/ui/Picker";
import { useCountry } from "@/lib/country";
import { FormErrors, useFormError } from "@/lib/form-errors";
import { digits } from "@/lib/utils";

/** **الأيقوناتُ المسموحة** — مرآةُ `CategoryIcon` في الخلفية: خطُّ الأيقونات مقتطَعٌ بأسمائه في التطبيقين. */
const ICONS: Array<{ value: string; label: string }> = [
  { value: "local_taxi", label: "سيارة أجرة" },
  { value: "directions_car", label: "سيارة" },
  { value: "airport_shuttle", label: "فان عائلي" },
  { value: "electric_car", label: "كهربائية" },
  { value: "diamond", label: "مميّزة" },
  { value: "accessible", label: "ذوو الإعاقة" },
];

export const BODY_LABEL: Record<VehicleBodyType, string> = {
  sedan: "سيدان",
  hatchback: "هاتشباك",
  suv: "دفع رباعي",
  minivan: "فان صغير",
  van: "فان",
};

export const FUEL_LABEL: Record<VehicleFuel, string> = {
  petrol: "بنزين",
  diesel: "ديزل",
  hybrid: "هجين",
  electric: "كهرباء",
};

interface Draft {
  key: string;
  name: string;
  icon: string;
  description: string;
  seats: string;
  sort_order: string;
  allowed_body_types: VehicleBodyType[];
  allowed_fuels: VehicleFuel[];
  min_year: string;
  min_seats: string;
}

const EMPTY: Draft = {
  key: "",
  name: "",
  icon: "local_taxi",
  description: "",
  seats: "4",
  sort_order: "10",
  allowed_body_types: [],
  allowed_fuels: [],
  min_year: "",
  min_seats: "",
};

const draftOf = (row: RideCategory): Draft => ({
  key: row.key,
  name: row.name,
  icon: row.icon,
  description: row.description ?? "",
  seats: String(row.seats),
  sort_order: String(row.sort_order),
  allowed_body_types: row.allowed_body_types,
  allowed_fuels: row.allowed_fuels,
  min_year: row.min_year === null ? "" : String(row.min_year),
  min_seats: row.min_seats === null ? "" : String(row.min_seats),
});

const numberOrNull = (value: string) => (value.trim() === "" ? null : Number(value));

export function RideCategoriesScreen() {
  const { country } = useCountry();
  const form = useFormError();
  const [rows, setRows] = useState<RideCategory[] | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setRows(await listRideCategories(country));
  }, [country]);

  useEffect(() => {
    setRows(null);
    load().catch((caught) => form.capture(caught, "تعذّر قراءة الفئات"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  const saved = (message: string) => {
    setDone(message);
    form.clear();
    void load();
  };

  return (
    <FormErrors value={form.field}>
      <Shell
        title="فئات الرحلة"
        subtitle="لكلِّ دولة — والأسعارُ في «التسعيرة». الفئةُ الجديدةُ تولد مطفأةً وتُشغَّل بعد أسعارها."
        actions={
          <Button size="sm" onClick={() => setCreating((value) => !value)}>
            {creating ? "إغلاق" : "فئة جديدة"}
          </Button>
        }
      >
        <ErrorNote message={form.message} />
        <SuccessNote message={done} />

        {creating ? (
          <CategoryForm
            initial={EMPTY}
            fresh
            onSubmit={async (draft) => {
              await createRideCategory({
                country_code: country,
                key: draft.key.trim(),
                name: draft.name.trim(),
                icon: draft.icon,
                description: draft.description.trim() || null,
                seats: Number(draft.seats),
                allowed_body_types: draft.allowed_body_types,
                allowed_fuels: draft.allowed_fuels,
                min_year: numberOrNull(draft.min_year),
                min_seats: numberOrNull(draft.min_seats),
              });
              setCreating(false);
              saved(`أُضيفت «${draft.name.trim()}» مطفأةً — ضع أسعارَها في «التسعيرة» ثمّ شغّلها`);
            }}
            onError={(caught) => form.capture(caught, "تعذّر الحفظ")}
          />
        ) : null}

        {rows === null ? (
          <Spinner className="mx-auto my-38" />
        ) : (
          <div className="mt-12 grid gap-12">
            {rows.length === 0 ? (
              <p className="text-12 text-muted">لا فئاتَ مسجّلةٌ لهذه الدولة بعد — «اقتصادي» و«مريح» تعملان كما هما حيث لهما أسعار.</p>
            ) : null}
            {rows.map((row) => (
              <CategoryCard
                key={row.id}
                row={row}
                onSaved={saved}
                onError={(caught) => form.capture(caught, "تعذّر الحفظ")}
              />
            ))}
          </div>
        )}
      </Shell>
    </FormErrors>
  );
}

function CategoryCard({
  row,
  onSaved,
  onError,
}: {
  row: RideCategory;
  onSaved: (message: string) => void;
  onError: (caught: unknown) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const conditions = [
    row.allowed_body_types.length ? `الهيكل: ${row.allowed_body_types.map((b) => BODY_LABEL[b]).join("، ")}` : null,
    row.allowed_fuels.length ? `الوقود: ${row.allowed_fuels.map((f) => FUEL_LABEL[f]).join("، ")}` : null,
    row.min_year !== null ? `أدنى سنة: ${digits(String(row.min_year))}` : null,
    row.min_seats !== null ? `أدنى مقاعد: ${digits(String(row.min_seats))}` : null,
  ].filter(Boolean);

  return (
    <div className="rounded-16 border border-line bg-surface p-18">
      <div className="flex items-start gap-12">
        <div className="flex-1">
          <h2 className="text-16 font-bold text-ink">
            {row.name}{" "}
            <span className="text-11 text-muted" dir="ltr">
              · {row.key}
            </span>
            {row.is_builtin ? <span className="text-11 text-muted"> · مدمجة</span> : null}
          </h2>
          <p className="mt-3 text-11.5 leading-note text-muted">
            {row.is_builtin
              ? "تتبع فئةَ المركبة كما اليوم — يأخذها كلُّ كبتنٍ مركبتُه من فئتها، ولا تُعدَّل من هنا."
              : `${row.description ?? "بلا وصف"} · ${digits(String(row.seats))} مقاعد · الترتيب ${digits(String(row.sort_order))}`}
          </p>
        </div>
        <span
          className={`rounded-full border px-10 py-4 text-11 font-semibold ${row.is_active ? "border-line text-ink" : "border-warn text-warn"}`}
        >
          {row.is_active ? "مشتعلة" : "مطفأة"}
        </span>
      </div>

      {row.is_builtin ? null : (
        <>
          <h3 className="mb-6 mt-14 text-13 font-bold text-muted">شروطُ المركبة</h3>
          <p className="text-12 text-ink">
            {conditions.length
              ? conditions.join(" · ")
              : "بلا شرط — فلا يأخذها إلا من مُنحها يدوياً أدناه."}
          </p>
          <AccessPanel category={row} onError={onError} />
          <div className="mt-14 flex flex-wrap gap-8">
            <Button
              size="sm"
              variant={row.is_active ? "secondary" : "primary"}
              loading={busy}
              onClick={() => {
                setBusy(true);
                updateRideCategory(row.id, { is_active: !row.is_active })
                  .then(() =>
                    onSaved(
                      row.is_active
                        ? `أُطفئت «${row.name}» — لا تُطلب بعد الآن، والجاريةُ تكمل`
                        : `شُغّلت «${row.name}» — تظهر للركّاب في اختيار الفئة`,
                    ),
                  )
                  .catch(onError)
                  .finally(() => setBusy(false));
              }}
            >
              {row.is_active ? "إطفاء" : "تشغيل"}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing((value) => !value)}>
              {editing ? "إغلاق التعديل" : "تعديل"}
            </Button>
          </div>
          {editing ? (
            <CategoryForm
              initial={draftOf(row)}
              onSubmit={async (draft) => {
                await updateRideCategory(row.id, {
                  name: draft.name.trim(),
                  icon: draft.icon,
                  description: draft.description.trim() || null,
                  seats: Number(draft.seats),
                  sort_order: Number(draft.sort_order),
                  allowed_body_types: draft.allowed_body_types,
                  allowed_fuels: draft.allowed_fuels,
                  min_year: numberOrNull(draft.min_year),
                  min_seats: numberOrNull(draft.min_seats),
                });
                setEditing(false);
                onSaved(`حُفظت «${draft.name.trim()}»`);
              }}
              onError={onError}
            />
          ) : null}
        </>
      )}
    </div>
  );
}

function CategoryForm({
  initial,
  fresh = false,
  onSubmit,
  onError,
}: {
  initial: Draft;
  /** **فئةٌ جديدة** — وحدَها تكتب مفتاحَها؛ ومفتاحُ القائمة لا يتغيّر. */
  fresh?: boolean;
  onSubmit: (draft: Draft) => Promise<void>;
  onError: (caught: unknown) => void;
}) {
  const [draft, setDraft] = useState<Draft>(initial);
  const [busy, setBusy] = useState(false);
  const set = (patch: Partial<Draft>) => setDraft((current) => ({ ...current, ...patch }));
  const toggle = <T extends string>(list: T[], value: T) =>
    list.includes(value) ? list.filter((item) => item !== value) : [...list, value];

  return (
    <div className="mt-14 rounded-13 border border-line p-14">
      <div className="grid gap-12 md:grid-cols-2">
        {fresh ? (
          <Field
            name="key"
            label="المفتاح (لاتينيٌّ صغير، لا يتغيّر)"
            dir="ltr"
            placeholder="family"
            value={draft.key}
            onChange={(event) => set({ key: event.target.value.toLowerCase() })}
          />
        ) : null}
        <Field name="name" label="الاسم" value={draft.name} onChange={(event) => set({ name: event.target.value })} />
        <Select name="icon" label="الأيقونة" value={draft.icon} onChange={(event) => set({ icon: event.target.value })}>
          {ICONS.map((icon) => (
            <option key={icon.value} value={icon.value}>
              {icon.label}
            </option>
          ))}
        </Select>
        <Field
          name="description"
          label="وصفٌ قصيرٌ يراه الراكب"
          value={draft.description}
          onChange={(event) => set({ description: event.target.value })}
        />
        <Field name="seats" label="المقاعد" inputMode="numeric" dir="ltr" value={draft.seats} onChange={(event) => set({ seats: event.target.value })} />
        <Field
          name="sort_order"
          label="الترتيب"
          inputMode="numeric"
          dir="ltr"
          value={draft.sort_order}
          onChange={(event) => set({ sort_order: event.target.value })}
        />
        <Field
          name="min_year"
          label="أدنى سنة صنع (اختياري)"
          inputMode="numeric"
          dir="ltr"
          value={draft.min_year}
          onChange={(event) => set({ min_year: event.target.value })}
        />
        <Field
          name="min_seats"
          label="أدنى مقاعد للمركبة (اختياري)"
          inputMode="numeric"
          dir="ltr"
          value={draft.min_seats}
          onChange={(event) => set({ min_seats: event.target.value })}
        />
      </div>
      <h4 className="mb-6 mt-12 text-12 font-bold text-muted">أنواعُ الهيكل المسموحة (لا شيء = أيّ نوع)</h4>
      <div className="flex flex-wrap gap-10">
        {(Object.keys(BODY_LABEL) as VehicleBodyType[]).map((body) => (
          <Checkbox
            key={body}
            checked={draft.allowed_body_types.includes(body)}
            onChange={() => set({ allowed_body_types: toggle(draft.allowed_body_types, body) })}
          >
            {BODY_LABEL[body]}
          </Checkbox>
        ))}
      </div>
      <h4 className="mb-6 mt-12 text-12 font-bold text-muted">الوقودُ المسموح (لا شيء = أيّ وقود)</h4>
      <div className="flex flex-wrap gap-10">
        {(Object.keys(FUEL_LABEL) as VehicleFuel[]).map((fuel) => (
          <Checkbox
            key={fuel}
            checked={draft.allowed_fuels.includes(fuel)}
            onChange={() => set({ allowed_fuels: toggle(draft.allowed_fuels, fuel) })}
          >
            {FUEL_LABEL[fuel]}
          </Checkbox>
        ))}
      </div>
      <Button
        className="mt-14"
        size="sm"
        loading={busy}
        disabled={draft.name.trim().length < 2 || (fresh && draft.key.trim().length < 2)}
        onClick={() => {
          setBusy(true);
          onSubmit(draft)
            .catch(onError)
            .finally(() => setBusy(false));
        }}
      >
        حفظ
      </Button>
    </div>
  );
}

/** **منحٌ ونزعٌ يدويّ** (§٦٧-ب/٥) — بسببٍ مكتوب، **ورفعُ القرار يعيد قاعدةَ الشروط وحدَها**. */
function AccessPanel({ category, onError }: { category: RideCategory; onError: (caught: unknown) => void }) {
  const { country } = useCountry();
  const [rows, setRows] = useState<CategoryAccess[] | null>(null);
  const [driver, setDriver] = useState<PickerOption | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    listCategoryAccess(category.id).then(setRows).catch(onError);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [category.id]);

  const findDrivers = useCallback(
    (query: string) =>
      listDrivers({ country_code: country, status: "approved", q: query, limit: 10 }).then((list) =>
        list.map((row) => ({ id: row.driver_id, label: row.name, hint: row.phone })),
      ),
    [country],
  );

  const decide = (driverId: string, granted: boolean | null, why: string) => {
    setBusy(true);
    setCategoryAccess(category.id, { driver_id: driverId, granted, reason: why })
      .then((next) => {
        setRows(next);
        setDriver(null);
        setReason("");
      })
      .catch((caught) => onError(caught instanceof ApiError ? caught : caught))
      .finally(() => setBusy(false));
  };

  return (
    <>
      <h3 className="mb-6 mt-14 text-13 font-bold text-muted">منحٌ ونزعٌ يدويّ</h3>
      {rows === null ? (
        <Spinner />
      ) : rows.length === 0 ? (
        <p className="text-12 text-muted">لا قرارَ يدويّاً — يأخذها من تستوفي مركبتُه شروطَها.</p>
      ) : (
        <div className="flex flex-col gap-6">
          {rows.map((row) => (
            <div key={row.driver_id} className="flex flex-wrap items-center gap-8 text-12 text-ink">
              <b>{row.driver_name ?? "كبتن"}</b>
              <span dir="ltr" className="text-muted">
                {row.driver_phone}
              </span>
              <span className={row.granted ? "text-ink" : "text-warn"}>{row.granted ? "مُنح" : "نُزع"}</span>
              {row.reason ? <span className="text-muted">«{row.reason}»</span> : null}
              <Button size="sm" variant="ghost" disabled={busy} onClick={() => decide(row.driver_id, null, "رفعُ القرار اليدويّ")}>
                رفعُ القرار
              </Button>
            </div>
          ))}
        </div>
      )}
      <div className="mt-10 grid gap-10 md:grid-cols-2">
        <Picker label="كبتن" placeholder="اسمٌ أو رقم هاتف" value={driver} onPick={setDriver} search={findDrivers} />
        <Field name="reason" label="السبب" value={reason} onChange={(event) => setReason(event.target.value)} />
      </div>
      <div className="mt-8 flex gap-8">
        <Button size="sm" disabled={!driver || reason.trim().length < 4 || busy} onClick={() => driver && decide(driver.id, true, reason.trim())}>
          منح
        </Button>
        <Button
          size="sm"
          variant="danger"
          disabled={!driver || reason.trim().length < 4 || busy}
          onClick={() => driver && decide(driver.id, false, reason.trim())}
        >
          نزع
        </Button>
      </div>
    </>
  );
}
