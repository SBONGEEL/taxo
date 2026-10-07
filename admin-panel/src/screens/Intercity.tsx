/** مساراتُ بين المدن (SPEC §٦٣-ج/٧): مدينتان بنقطتي تجمّعٍ وسعرين — **يعلن عليها الكباتنُ المصرَّح لهم رحلاتِهم**.
 *
 * **وأربعةُ أشياء تقولها الشاشةُ لأنها تحكم ما يقع فعلاً:**
 *
 * 1. **المسارُ لا يُعلَن عليه بالمسار وحدَه**: سوقٌ لم يُشعل «بين المدن» من الإعدادات لا يُعلن فيه شيءٌ ولو كان المسارُ مفعَّلاً،
 *    ولا يعلن إلا كبتنٌ مُنح تصريحاً من ملفّه في «السائقون والوثائق». **فيُقال ذلك سطراً أعلى الشاشة** — ومن يضيف مساراً ولا يرى
 *    عليه رحلةً يظنّ شيئاً تعطّل.
 * 2. **ولا زرَّ حذف**: المسارُ يُطفأ ولا يُمحى — رحلاتٌ وحجوزٌ تشير إليه، وحذفُ صفٍّ يمسّ المال ممنوعٌ على الإنتاج. والخلفيةُ لا
 *    تملك بابَ حذفٍ أصلاً.
 * 3. **والمدينتان والإحداثيّاتُ لا تُعدَّل بعد الإنشاء** (`RoutePatch` لا يحملها): مسارُ عمّان–إربد لا يصير عمّان–العقبة تحت رحلاتٍ
 *    أُعلنت عليه — **مسارٌ آخرُ يُضاف**. والتعديلُ يرسل ما تغيّر وحدَه كأخته «المرافق الحيوية».
 * 4. **والسعران يُجمَّدان على الرحلة لحظةَ إعلانها** — فتعديلُهما يحكم ما يُعلن بعده لا رحلةً قائمة.
 *
 * **والمالُ نصٌّ لا رقم** (§14): السعران يُكتبان ويُرسلان كما كُتبا، ويُفحص شكلُهما هنا ولا تُحسب منهما قيمة. **والإحداثيّاتُ أرقامٌ
 * تُكتب** (خطُّ عرضٍ وخطُّ طول) — الخريطةُ اختياريّةٌ في هذا البند، **ونقطةُ التجمّع تُقرأ للكبتن والراكب باسمها لا بإحداثيّاتها**.
 */

import { useCallback, useEffect, useState } from "react";
import { NavLink } from "react-router-dom";

import { ApiError } from "@/api/client";
import { createIntercityRoute, listIntercityRoutes, updateIntercityRoute } from "@/api/endpoints";
import type { CountryCode, IntercityRoute } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Table } from "@/components/Table";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { Field, Switch } from "@/components/ui/Field";
import { MoneyField } from "@/components/ui/Inputs";
import { Modal } from "@/components/ui/Modal";
import { useCountry } from "@/lib/country";
import { FormErrors, useFormError } from "@/lib/form-errors";
import { currencyOf, money } from "@/lib/format";
import { useSession } from "@/lib/session";
import { Icon } from "@/taxo2";

/** **شكلُ المال على السلك** — ستُّ خاناتٍ صحيحةٍ وثلاثٌ عشريةٌ على الأكثر، كحدِّ `NUMERIC(12,3)` (نمطُ «المرافق الحيوية»). */
const PRICE_SHAPE = /^\d{1,6}(\.\d{1,3})?$/;

/** حدودُ المخطط (`RouteIn`) — **ونسختُها هنا لتعطيل الزرّ لا لتقرير القبول**: الخلفيةُ هي التي ترفض بنصّها. */
const CITY = { min: 2, max: 60 };
const POINT = { min: 2, max: 255 };

const within = (text: string, bound: { min: number; max: number }) => {
  const length = text.trim().length;
  return length >= bound.min && length <= bound.max;
};

/** **إحداثيّةٌ مكتوبة** — رقمٌ في حدِّه (العرضُ ±٩٠ والطولُ ±١٨٠)، و`null` لما لم يُكتب أو خرج عنه. */
function coordinate(text: string, limit: number): number | null {
  const value = Number(text.trim());
  return text.trim() !== "" && Number.isFinite(value) && Math.abs(value) <= limit ? value : null;
}

export function IntercityScreen() {
  const { country } = useCountry();
  const { isAdmin } = useSession();
  const [rows, setRows] = useState<IntercityRoute[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  // `"new"` إنشاءٌ، ومسارٌ تعديلٌ له، و`null` مغلق
  const [editing, setEditing] = useState<IntercityRoute | "new" | null>(null);

  const load = useCallback(async () => {
    setRows(await listIntercityRoutes(country));
  }, [country]);

  useEffect(() => {
    // **السوقُ تبدّل فالقائمةُ قائمةُ غيره** — تُفرَّغ قبل أن تصل (قاعدةُ «المرافق الحيوية»)
    setRows(null);
    setError(null);
    setDone(null);
    load().catch((caught) =>
      setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة المسارات"),
    );
  }, [load]);

  return (
    <Shell
      title="مسارات بين المدن"
      subtitle="مدينتان بنقطتي تجمّعٍ وسعرين — يعلن عليها الكباتنُ المصرَّح لهم رحلاتِهم بمقاعدها"
      actions={
        isAdmin ? (
          <Button size="sm" onClick={() => setEditing("new")}>
            إضافة مسار
          </Button>
        ) : null
      }
    >
      {/* **شرطا الإعلان سطرٌ لا يُغلق** (رأسُ الملفّ ١) — والمفتاحُ في الإعدادات لا هنا: مفتاحُ سوقٍ واحدٌ في بيتٍ واحد */}
      <div className="ad-fac-note">
        <Icon name="info" />
        <span className="ad-fac-note-text">
          لا تُعلن رحلةٌ على مسارٍ إلا في سوقٍ أشعل «بين المدن» من الإعدادات، ومن كبتنٍ مُنح تصريحاً من ملفّه في «السائقون
          والوثائق» بعد فحص مركبته.
        </span>
        <NavLink to="/settings" className="ad-fac-note-link">
          الإعدادات
        </NavLink>
      </div>

      <ErrorNote message={error} />
      <SuccessNote message={done} />

      <Table
        columns="1.3fr 1.8fr 0.8fr 0.8fr 0.6fr auto"
        headers={["المسار", "نقطتا التجمّع", "المقعد", "السيارة", "الحال", ""]}
        rows={rows}
        keyOf={(row) => row.id}
        empty={{
          title: "لا مسارات في هذا السوق بعد",
          hint: "أضف مساراً بمدينتيه ونقطتي التجمّع وسعري المقعد والسيارة — ويُعلن عليه حين يُشعَل «بين المدن».",
        }}
        render={(row) => (
          <>
            {/* **المسارُ بابُ المحرِّر** — كاسم المرفق في أخته */}
            {isAdmin ? (
              <button type="button" className="ad-fac-name" onClick={() => setEditing(row)}>
                {row.from_city} ← {row.to_city}
              </button>
            ) : (
              <span className="ad-fac-name">
                {row.from_city} ← {row.to_city}
              </span>
            )}
            <span className="ad-ic-points">
              <span>{row.from_point}</span>
              <span className="ad-tone-muted">{row.to_point}</span>
            </span>
            {/* **الرمزُ لا العلامة** (`check:money`): `money` تحلّ العملةَ بنفسها */}
            <span className="ad-fare">{money(row.price_seat, currencyOf(row.country_code))}</span>
            <span className="ad-fare">{money(row.price_car, currencyOf(row.country_code))}</span>
            <Badge tone={row.is_active ? "ok" : "muted"}>{row.is_active ? "مفعَّل" : "مطفأ"}</Badge>
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
        <RouteEditor
          route={editing === "new" ? null : editing}
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

/** **ضلعُ المسار** — المدينةُ ونقطةُ التجمّع بإحداثيّتيها. **والمدينةُ والإحداثيّتان للإنشاء وحدَه** (رأسُ الملفّ ٣). */
function Side({
  title,
  prefix,
  city,
  point,
  lat,
  lng,
  locked,
  onCity,
  onPoint,
  onLat,
  onLng,
}: {
  title: string;
  prefix: "from" | "to";
  city: string;
  point: string;
  lat: string;
  lng: string;
  locked: boolean;
  onCity: (value: string) => void;
  onPoint: (value: string) => void;
  onLat: (value: string) => void;
  onLng: (value: string) => void;
}) {
  // **المصفاةُ لا تحسب**: تمنع حرفاً لا يكون إحداثيّةً، والحدُّ يُفحص تحت
  const clean = (text: string) => text.replace(/[^0-9.\-]/g, "");
  return (
    <fieldset className="ad-ic-side">
      <legend className="ad-ic-legend">{title}</legend>
      <Field
        label="المدينة"
        name={`${prefix}_city`}
        value={city}
        maxLength={CITY.max}
        disabled={locked}
        onChange={(event) => onCity(event.target.value)}
      />
      <Field
        label="نقطة التجمّع"
        name={`${prefix}_point`}
        value={point}
        maxLength={POINT.max}
        placeholder="مجمّع الشمال — بوّابةُ الحافلات"
        onChange={(event) => onPoint(event.target.value)}
      />
      <div className="ad-ic-coords">
        <Field
          label="خطّ العرض"
          name={`${prefix}_lat`}
          dir="ltr"
          inputMode="decimal"
          value={lat}
          disabled={locked}
          placeholder="31.9539"
          onChange={(event) => onLat(clean(event.target.value))}
        />
        <Field
          label="خطّ الطول"
          name={`${prefix}_lng`}
          dir="ltr"
          inputMode="decimal"
          value={lng}
          disabled={locked}
          placeholder="35.9106"
          onChange={(event) => onLng(clean(event.target.value))}
        />
      </div>
    </fieldset>
  );
}

/** محرِّرُ المسار — **الإنشاءُ والتعديلُ ورقةٌ واحدة** كمحرِّر المرفق. **والمسوّدةُ لا تُمحى بنقرةٍ خارج الحوار**: ما دام فيه تغييرٌ
 *  لم يُحفظ، «تراجع» وحدَه يُغلقه. **ورفضُ الخلفية تحت حقله** (`FormErrors`) أو تحت النموذج. */
function RouteEditor({
  route,
  country,
  onClose,
  onSaved,
}: {
  /** مسارٌ قائمٌ ⇒ تعديل، و`null` ⇒ إنشاءٌ في السوق المختار. */
  route: IntercityRoute | null;
  country: CountryCode;
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const market = route?.country_code ?? country;
  const [fromCity, setFromCity] = useState(route?.from_city ?? "");
  const [toCity, setToCity] = useState(route?.to_city ?? "");
  const [fromPoint, setFromPoint] = useState(route?.from_point ?? "");
  const [toPoint, setToPoint] = useState(route?.to_point ?? "");
  const [fromLat, setFromLat] = useState(route ? String(route.from_lat) : "");
  const [fromLng, setFromLng] = useState(route ? String(route.from_lng) : "");
  const [toLat, setToLat] = useState(route ? String(route.to_lat) : "");
  const [toLng, setToLng] = useState(route ? String(route.to_lng) : "");
  const [priceSeat, setPriceSeat] = useState(route?.price_seat ?? "");
  const [priceCar, setPriceCar] = useState(route?.price_car ?? "");
  // **مفعَّلٌ افتراضاً كما في المخطط** (`RouteIn.is_active = True`) — والمفتاحُ تحت يده قبل الحفظ
  const [active, setActive] = useState(route?.is_active ?? true);
  const [busy, setBusy] = useState(false);
  const form = useFormError();

  const seatText = priceSeat.trim();
  const carText = priceCar.trim();
  const coords = {
    fromLat: coordinate(fromLat, 90),
    fromLng: coordinate(fromLng, 180),
    toLat: coordinate(toLat, 90),
    toLng: coordinate(toLng, 180),
  };
  const valid =
    within(fromCity, CITY) &&
    within(toCity, CITY) &&
    within(fromPoint, POINT) &&
    within(toPoint, POINT) &&
    Object.values(coords).every((value) => value !== null) &&
    PRICE_SHAPE.test(seatText) &&
    PRICE_SHAPE.test(carText);

  /** ما تغيّر عن المحفوظ — **وهو حمولةُ `PATCH` بعينها**. */
  const changes: Parameters<typeof updateIntercityRoute>[1] = {};
  if (route) {
    if (fromPoint.trim() !== route.from_point) changes.from_point = fromPoint.trim();
    if (toPoint.trim() !== route.to_point) changes.to_point = toPoint.trim();
    if (seatText !== route.price_seat) changes.price_seat = seatText;
    if (carText !== route.price_car) changes.price_car = carText;
    if (active !== route.is_active) changes.is_active = active;
  }
  const dirty = route
    ? Object.keys(changes).length > 0
    : [fromCity, toCity, fromPoint, toPoint, fromLat, fromLng, toLat, toLng, priceSeat, priceCar].some(
        (text) => text.trim() !== "",
      );
  const ready = valid && dirty;
  const name = `${fromCity.trim()} ← ${toCity.trim()}`;

  async function save() {
    setBusy(true);
    form.clear();
    try {
      if (route) {
        await updateIntercityRoute(route.id, changes);
        onSaved(`حُفظ تعديلُ «${name}» — والسعران يحكمان ما يُعلن بعده`);
      } else {
        const { fromLat: from_lat, fromLng: from_lng, toLat: to_lat, toLng: to_lng } = coords;
        if (from_lat === null || from_lng === null || to_lat === null || to_lng === null) return;
        await createIntercityRoute({
          country_code: market,
          from_city: fromCity.trim(),
          to_city: toCity.trim(),
          from_lat,
          from_lng,
          from_point: fromPoint.trim(),
          to_lat,
          to_lng,
          to_point: toPoint.trim(),
          price_car: carText,
          price_seat: seatText,
          is_active: active,
        });
        onSaved(`أُضيف «${name}»`);
      }
    } catch (caught) {
      form.capture(caught, "تعذّر الحفظ");
    } finally {
      setBusy(false);
    }
  }

  return (
    <FormErrors value={form.field}>
      <Modal wide title={route ? `تعديل «${route.from_city} ← ${route.to_city}»` : "مسارٌ جديد"} onClose={dirty ? () => undefined : onClose}>
        <div className="ad-ic-edit">
          <Side
            title="من"
            prefix="from"
            city={fromCity}
            point={fromPoint}
            lat={fromLat}
            lng={fromLng}
            locked={route !== null}
            onCity={setFromCity}
            onPoint={setFromPoint}
            onLat={setFromLat}
            onLng={setFromLng}
          />
          <Side
            title="إلى"
            prefix="to"
            city={toCity}
            point={toPoint}
            lat={toLat}
            lng={toLng}
            locked={route !== null}
            onCity={setToCity}
            onPoint={setToPoint}
            onLat={setToLat}
            onLng={setToLng}
          />
        </div>
        {route ? (
          <p className="ad-hint ad-ic-locked">
            المدينتان والإحداثيّاتُ لا تُعدَّل بعد الإنشاء — رحلاتٌ أُعلنت على هذا المسار. ولمسارٍ آخر أضِفه جديداً.
          </p>
        ) : null}

        <div className="ad-ic-prices">
          <MoneyField
            label="سعر المقعد"
            name="price_seat"
            value={priceSeat}
            onChange={(next) => setPriceSeat(next.replace(/[^0-9.]/g, ""))}
            currency={currencyOf(market)}
            error={seatText !== "" && !PRICE_SHAPE.test(seatText) ? "السعرُ رقمٌ بثلاث خاناتٍ عشريةٍ على الأكثر — مثل 3.500" : null}
            hint="يُدفع من محفظة الراكب لحظةَ الحجز، ويحفظه TAXO حتى تنتهي الرحلة"
          />
          <MoneyField
            label="سعر السيارة كاملة"
            name="price_car"
            value={priceCar}
            onChange={(next) => setPriceCar(next.replace(/[^0-9.]/g, ""))}
            currency={currencyOf(market)}
            error={carText !== "" && !PRICE_SHAPE.test(carText) ? "السعرُ رقمٌ بثلاث خاناتٍ عشريةٍ على الأكثر — مثل 12.000" : null}
            hint="نقداً للكبتن عند الانطلاق — حين لا مقعدَ محجوزٌ بعد"
          />
        </div>

        <div className="ad-fac-switch ad-ic-switch">
          <Switch checked={active} label="مفعَّل" onChange={setActive} />
          <span className="ad-fac-switch-text">
            {active ? "مفعَّل — يُعلن عليه الكباتن" : "مطفأ — لا يُعلن عليه جديد"}
          </span>
        </div>
        <p className="ad-hint">
          والإطفاءُ بديلُ الحذف: المسارُ يبقى في القائمة وفي رحلاته المعلَنة وحجوزها، ولا يمسّ ما أُعلن.
        </p>

        <ErrorNote message={form.message} />

        <div className="ad-modal-actions">
          <Button size="md" loading={busy} disabled={!ready} onClick={() => void save()}>
            {route ? "حفظ التعديل" : "أضف المسار"}
          </Button>
          <Button size="md" variant="secondary" onClick={onClose}>
            تراجع
          </Button>
        </div>
      </Modal>
    </FormErrors>
  );
}
