/** المرافق الحيوية — المطاراتُ وأمثالُها (SPEC §٦٣-ج/٢): اسمٌ ومنطقةٌ على الخريطة ورسمٌ للكبتن.
 *
 * **وثلاثةُ أشياء تقولها الشاشةُ لأنها تحكم ما يقع فعلاً:**
 *
 * 1. **الرسمُ لا يُطبَّق بالمرفق وحدَه**: سوقٌ لم يُشعل «المطار» من الإعدادات لا رسمَ فيه ولو كان المرفقُ مفعَّلاً، ومرفقٌ رسمُه
 *    صفرٌ لا يُطبَّق ولو كان السوقُ مشتعلاً (`services/facilities.py::fee_for`). **فيُقال ذلك سطراً أعلى الشاشة** — ومن يضبط
 *    مرفقاً ولا يرى رسمَه على رحلةٍ يظنّ شيئاً تعطّل.
 * 2. **ولا زرَّ حذف**: المرفقُ يُطفأ ولا يُمحى — رحلاتٌ قديمةٌ تشير إليه، وحذفُ صفٍّ يمسّ المال ممنوعٌ على الإنتاج. والخلفيةُ
 *    لا تملك بابَ حذفٍ أصلاً، **فزرٌّ يُرسم له بابٌ بلا خادم**.
 * 3. **والتعديلُ يرسل ما تغيّر وحدَه** — والمنطقةُ منه إن تغيّرت فقط: كلُّ كتابةٍ تُختم في التدقيق بما تغيّر قبلاً وبعداً،
 *    **وحمولةٌ كاملةٌ في كلِّ حفظٍ تجعل «غيّر الرسم» يُقرأ «أعاد رسمَ المطار»**.
 *
 * **والمالُ نصٌّ لا رقم** (§14): الرسمُ يُكتب ويُرسل كما كُتب، ويُفحص شكلُه هنا (`^\d{1,6}(\.\d{1,3})?$`) ولا تُحسب منه قيمة.
 * **ورسالةُ الرفض من الخلفية كما هي** — أقلُّ من ثلاث نقاط، ومضلّعٌ يتقاطع، ونقطةٌ خارج الخريطة: تُسمّى هناك بالعربية.
 */

import { useCallback, useEffect, useState } from "react";
import { NavLink } from "react-router-dom";

import { ApiError } from "@/api/client";
import { createFacility, listFacilities, updateFacility } from "@/api/endpoints";
import type { CountryCode, Facility, FacilityKind, LngLat } from "@/api/types";
import { AreaCanvas } from "@/components/AreaCanvas";
import { Shell } from "@/components/Shell";
import { Table } from "@/components/Table";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { Field, Switch } from "@/components/ui/Field";
import { MoneyField } from "@/components/ui/Inputs";
import { Modal } from "@/components/ui/Modal";
import { useConfig } from "@/lib/config";
import { useCountry } from "@/lib/country";
import { FormErrors, useFormError } from "@/lib/form-errors";
import { currencyOf, day, money } from "@/lib/format";
import { useSession } from "@/lib/session";
import { counted } from "@/lib/utils";
import type { CountedForms } from "@/lib/utils";
import { Icon } from "@/taxo2";

const KIND_LABEL: Record<FacilityKind, string> = { airport: "مطار" };

/** **مطارُ العاصمة** — حيث يبدأ رسمُ مرفقٍ جديد. لا عاصمةُ الخريطة الحيّة (`LiveMap::CENTER`): المشرفُ هنا يرسم مطاراً،
 *  **وخريطةٌ تفتح على وسط المدينة تُلزمه بالبحث عنه قبل أوّل نقرة**. */
const AIRPORT_CENTER: Record<CountryCode, LngLat> = {
  JO: [35.9932, 31.7226], // مطار الملكة علياء الدولي
  LY: [13.276, 32.8941], // مطار معيتيقة الدولي
};

/** **شكلُ المال على السلك** — ستُّ خاناتٍ صحيحةٍ وثلاثٌ عشريةٌ على الأكثر، كحدِّ `NUMERIC(12,3)` الذي يعرفه المشرف. */
const FEE_SHAPE = /^\d{1,6}(\.\d{1,3})?$/;

/** حدُّ الاسم في المخطط (`FacilityIn.name`) — **ونسختُه هنا لتعطيل الزرّ لا لتقرير القبول**: الخلفيةُ هي التي ترفض بنصّها. */
const NAME_MIN = 2;
const NAME_MAX = 80;

const POINT_FORMS: CountedForms = {
  one: "نقطةٌ واحدة",
  two: "نقطتان",
  few: "نقاط",
  many: "نقطة",
  bare: "نقطة",
};

/** **أتغيّرت المنطقة؟** — نقطةً نقطة، فالحفظُ لا يرسل مضلّعاً لم يُلمس. */
function sameArea(a: LngLat[], b: LngLat[]): boolean {
  return (
    a.length === b.length &&
    a.every((point, index) => point[0] === b[index][0] && point[1] === b[index][1])
  );
}

export function FacilitiesScreen() {
  const { country } = useCountry();
  const { isAdmin } = useSession();
  const [rows, setRows] = useState<Facility[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  // `"new"` إنشاءٌ، ومرفقٌ تعديلٌ له، و`null` مغلق
  const [editing, setEditing] = useState<Facility | "new" | null>(null);

  const load = useCallback(async () => {
    setRows(await listFacilities(country));
  }, [country]);

  useEffect(() => {
    // **السوقُ تبدّل فالقائمةُ قائمةُ غيره** — تُفرَّغ قبل أن تصل، لا تُعرض مرافقُ سوقٍ تحت اسم آخر
    setRows(null);
    setError(null);
    setDone(null);
    load().catch((caught) =>
      setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة المرافق"),
    );
  }, [load]);

  return (
    <Shell
      title="المرافق الحيوية"
      subtitle="المطاراتُ وأمثالُها — منطقةٌ على الخريطة ورسمٌ للكبتن على كلِّ رحلةٍ تبدأ فيها أو تنتهي"
      actions={
        isAdmin ? (
          <Button size="sm" onClick={() => setEditing("new")}>
            إضافة مرفق
          </Button>
        ) : null
      }
    >
      {/* **شرطا التطبيق سطرٌ لا يُغلق** (رأسُ الملفّ ١) — والمفتاحُ في الإعدادات لا هنا: مفتاحُ سوقٍ واحدٌ في بيتٍ واحد */}
      <div className="ad-fac-note">
        <Icon name="info" />
        <span className="ad-fac-note-text">
          رسمُ المطار لا يُطبَّق إلا في سوقٍ أشعل «المطار» من الإعدادات، وعلى
          مرفقٍ مفعَّلٍ رسمُه أكبر من صفر.
        </span>
        <NavLink to="/settings" className="ad-fac-note-link">
          الإعدادات
        </NavLink>
      </div>

      <ErrorNote message={error} />
      <SuccessNote message={done} />

      <Table
        columns="1.6fr 0.6fr 1fr 0.7fr 0.9fr auto"
        headers={["الاسم", "النوع", "الرسم", "الحال", "آخر تعديل", ""]}
        rows={rows}
        keyOf={(row) => row.id}
        empty={{
          title: "لا مرافق في هذا السوق بعد",
          hint: "أضف مطاراً وارسم منطقتَه على الخريطة — ورسمُه يبدأ حين يُشعَل «المطار» من الإعدادات.",
        }}
        render={(row) => (
          <>
            {/* **الاسمُ بابُ المحرِّر** — النقرُ على الصفِّ يفتحه، والزرُّ في آخره للعين التي تبحث عن «حرّر» */}
            {isAdmin ? (
              <button
                type="button"
                className="ad-fac-name"
                onClick={() => setEditing(row)}
              >
                {row.name}
              </button>
            ) : (
              <span className="ad-fac-name">{row.name}</span>
            )}
            <span className="ad-tone-muted">{KIND_LABEL[row.kind] ?? row.kind}</span>
            {/* **الرمزُ لا العلامة** (`check:money`): `money` تحلّ العملةَ بنفسها — والصفرُ يُقال «لا يُطبَّق» لا يُترك رقماً يُقرأ رسماً */}
            <span className="ad-fac-fee">
              <span className="ad-fare">{money(row.fee, currencyOf(row.country_code))}</span>
              {Number(row.fee) === 0 ? (
                <span className="ad-fac-fee-off">لا يُطبَّق</span>
              ) : null}
            </span>
            <Badge tone={row.is_active ? "ok" : "muted"}>
              {row.is_active ? "مفعَّل" : "مطفأ"}
            </Badge>
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
        <FacilityEditor
          facility={editing === "new" ? null : editing}
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

/** محرِّرُ المرفق — **الإنشاءُ والتعديلُ ورقةٌ واحدة**، كمؤلِّف الحملات: نسختان تفترقان أوّلَ حقلٍ يُضاف.
 *
 * **والمسوّدةُ لا تُمحى بنقرةٍ خارج الحوار**: منطقةٌ رُسمت بعشرين نقرةً تضيع بنقرةٍ على الظلّ — فما دام فيه تغييرٌ لم
 * يُحفظ، **«تراجع» وحدَه يُغلقه**. */
function FacilityEditor({
  facility,
  country,
  onClose,
  onSaved,
}: {
  /** مرفقٌ قائمٌ ⇒ تعديل، و`null` ⇒ إنشاءٌ في السوق المختار. */
  facility: Facility | null;
  country: CountryCode;
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const { config } = useConfig();
  // **التوكنُ من حيث تأخذه الخريطةُ الحيّة** — لا مصدرَ ثانٍ
  const token = config?.providers.mapbox?.public_token ?? null;
  const market = facility?.country_code ?? country;

  const [name, setName] = useState(facility?.name ?? "");
  const [fee, setFee] = useState(facility?.fee ?? "");
  // **مفعَّلٌ افتراضاً كما في المخطط** (`FacilityIn.is_active = True`) — والمفتاحُ تحت يده قبل الحفظ
  const [active, setActive] = useState(facility?.is_active ?? true);
  const [points, setPoints] = useState<LngLat[]>(facility?.area ?? []);
  const [busy, setBusy] = useState(false);
  const form = useFormError();

  const trimmed = name.trim();
  const feeText = fee.trim();
  const nameOk = trimmed.length >= NAME_MIN && trimmed.length <= NAME_MAX;
  const feeOk = FEE_SHAPE.test(feeText);
  const areaOk = points.length >= 3;

  /** ما تغيّر عن المحفوظ — **وهو حمولةُ `PATCH` بعينها** (رأسُ الملفّ ٣). */
  const changes: Parameters<typeof updateFacility>[1] = {};
  if (facility) {
    if (trimmed !== facility.name) changes.name = trimmed;
    if (feeText !== facility.fee) changes.fee = feeText;
    if (active !== facility.is_active) changes.is_active = active;
    if (!sameArea(points, facility.area)) changes.area = points;
  }
  const dirty = facility
    ? Object.keys(changes).length > 0
    : trimmed !== "" || feeText !== "" || points.length > 0;
  const ready = nameOk && feeOk && areaOk && dirty;

  async function save() {
    setBusy(true);
    form.clear();
    try {
      if (facility) {
        await updateFacility(facility.id, changes);
        onSaved(`حُفظ تعديلُ «${trimmed}»`);
      } else {
        await createFacility({
          country_code: market,
          name: trimmed,
          area: points,
          fee: feeText,
          is_active: active,
        });
        onSaved(`أُضيف «${trimmed}»`);
      }
    } catch (caught) {
      form.capture(caught, "تعذّر الحفظ");
    } finally {
      setBusy(false);
    }
  }

  return (
    <FormErrors value={form.field}>
      <Modal
        wide
        title={facility ? `تعديل «${facility.name}»` : "مرفقٌ جديد"}
        onClose={dirty ? () => undefined : onClose}
      >
        <div className="ad-fac-edit">
          <div className="ad-fac-form">
            <Field
              label="الاسم"
              name="name"
              value={name}
              maxLength={NAME_MAX}
              placeholder="مطار الملكة علياء الدولي"
              onChange={(event) => setName(event.target.value)}
            />
            <p className="ad-fac-kind">
              النوع: <b>{KIND_LABEL.airport}</b> — والمطارُ وحدَه اليوم.
            </p>
            <MoneyField
              label="الرسم"
              name="fee"
              value={fee}
              // **المصفاةُ لا تحسب**: تمنع حرفاً لا يكون مالاً، والشكلُ يُفحص بنمطه تحت
              onChange={(next) => setFee(next.replace(/[^0-9.]/g, ""))}
              currency={currencyOf(market)}
              error={
                feeText !== "" && !feeOk
                  ? "الرسمُ رقمٌ بثلاث خاناتٍ عشريةٍ على الأكثر — مثل 1.500"
                  : null
              }
              hint="رسمٌ للكبتن على كلِّ رحلةٍ تبدأ أو تنتهي داخل المنطقة — يصله كاملاً، ولا تُقتطع منه العمولة. وصفرٌ لا يُطبَّق."
            />
            <div className="ad-fac-switch">
              <Switch checked={active} label="مفعَّل" onChange={setActive} />
              <span className="ad-fac-switch-text">
                {active ? "مفعَّل — يُطبَّق رسمُه" : "مطفأ — لا يُطبَّق رسمُه"}
              </span>
            </div>
            <p className="ad-hint">
              والإطفاءُ بديلُ الحذف: المرفقُ يبقى في القائمة وفي الرحلات التي
              حملت رسمَه، ولا يمسّ ما يأتي.
            </p>
          </div>

          <div className="ad-fac-area">
            <div className="ad-fac-area-head">
              <span className="label">المنطقة على الخريطة</span>
              <span className="ad-fac-count" aria-live="polite">
                {counted(points.length, POINT_FORMS)}
              </span>
            </div>
            <div className="ad-fac-map">
              <AreaCanvas
                token={token}
                center={facility?.area[0] ?? AIRPORT_CENTER[market]}
                points={points}
                onChange={setPoints}
              />
            </div>
            <p className="ad-hint">
              {areaOk
                ? "اسحب نقطةً لتحرّكها، أو انقر لتضيف أخرى بعد آخر نقطة. والحلقةُ تُغلق وحدَها."
                : "انقر على الخريطة لتضيف نقاطَ المنطقة بالترتيب — ثلاثٌ على الأقل، والحلقةُ تُغلق وحدَها."}
            </p>
            <div className="ad-fac-tools">
              <Button
                size="sm"
                variant="secondary"
                disabled={points.length === 0}
                onClick={() => setPoints((current) => current.slice(0, -1))}
              >
                تراجع عن آخر نقطة
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={points.length === 0}
                onClick={() => setPoints([])}
              >
                مسح المنطقة
              </Button>
            </div>
          </div>
        </div>

        <ErrorNote message={form.message} />

        <div className="ad-modal-actions">
          <Button size="md" loading={busy} disabled={!ready} onClick={() => void save()}>
            {facility ? "حفظ التعديل" : "أضف المرفق"}
          </Button>
          <Button size="md" variant="secondary" onClick={onClose}>
            تراجع
          </Button>
        </div>
      </Modal>
    </FormErrors>
  );
}
