/** المركبة والمستندات — SPEC القسم 12/1، وشكلُها من `DESIGN.md` §5.3.
 *
 * **والمركبةُ تُحرَّر الآن** (`FUTURE-FEATURES` بند 43): كانت تُعرض ولا
 * تُحرَّر لأن لا منفذَ في الخلفية، وصار `PATCH /drivers/me/vehicles/{id}`.
 * والسؤالُ الذي أخّرها — «هل يعيد تغييرُ اللوحة الكبتنَ إلى المراجعة؟» —
 * جوابُه **نفسُ سياسة 9-ب**: رخصةُ المركبة أحدُ المستندات الثلاثة، فتغييرُ
 * ما تشهد عليه هو استبدالُ مستندٍ بحرفه. **فحقولُ الهوية تُسقط الاعتماد
 * واللونُ لا** — وتقول الشاشةُ ذلك **قبل الحفظ لا بعده**، كما تقوله عن
 * استبدال المستند.
 *
 * **والمستندُ يُستبدل، والاستبدالُ له ثمن**: رفعُ نوعٍ ثانيةً يستبدل صفّه
 * ويعيده `pending`، **ويعيد الكبتن المعتمد إلى «قيد المراجعة»** حتى تُراجَع
 * الوثيقة الجديدة (سياسة 9-ب في SPEC). فالشاشة تقول ذلك قبل الرفع لا بعده،
 * والخلفيةُ ترفض الاستبدال أثناء رحلةٍ جارية.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/api/client";
import { listDocuments, updateVehicle, uploadDocument } from "@/api/endpoints";
import { describeShrink, shrinkImage } from "@/lib/shrink";
import type { DocumentType, DriverDocuments, Vehicle } from "@/api/types";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { useDriver } from "@/lib/driver";
import { CATEGORY_LABEL } from "@/lib/rideFormat";
import { digits, cn } from "@/lib/utils";
import { useGoBack } from "@/lib/back";
import { useConfig } from "@/lib/config";
import { rulesFor } from "@/lib/validation";
import {
  VEHICLE_COLORS,
  VEHICLE_MAKES,
  VEHICLE_MODELS,
  vehicleYears,
} from "@/lib/vehicle-options";

const DOC_LABEL: Record<DocumentType, string> = {
  driving_license: "رخصة القيادة",
  national_id: "الهوية الشخصية",
  vehicle_registration: "رخصة المركبة",
  vehicle_photo: "صورة المركبة",
  vehicle_front: "المركبة من الأمام",
  vehicle_back: "المركبة من الخلف",
  vehicle_side_right: "الجانب الأيمن",
  vehicle_side_left: "الجانب الأيسر",
  vehicle_interior: "من الداخل",
  vehicle_plate: "لوحة المركبة",
  profile_photo: "الصورة الشخصية",
};

const REVIEW_LABEL = {
  approved: { text: "مقبول", tone: "text-ok", dot: "bg-ok" },
  pending: { text: "قيد المراجعة", tone: "text-warn", dot: "bg-warn" },
  rejected: { text: "مرفوض", tone: "text-danger", dot: "bg-danger" },
} as const;

export function VehicleScreen() {
  const goBack = useGoBack();
  const { profile, refresh } = useDriver();
  const [state, setState] = useState<DriverDocuments | null>(null);
  const [busy, setBusy] = useState<DocumentType | null>(null);
  const [editing, setEditing] = useState(false);
  const [reverted, setReverted] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setState(await listDocuments());
  }, []);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة المستندات",
      ),
    );
  }, [load]);

  async function replace(docType: DocumentType, file: File) {
    setBusy(docType);
    setError(null);
    setDone(null);
    try {
      // نفسُ الضغط — والبيتُ واحدٌ فلا تفترق شاشتان في حجمِ ما ترفعان
      const shrunk = await shrinkImage(file);
      const result = await uploadDocument(docType, shrunk.file);
      await load();
      await refresh();
      // **يُلحق بالرسالة ولا يأخذ سطراً ثانياً**: الشاشةُ تعرض رسالةً واحدةً
      // في مكانٍ واحد، وسطرٌ ثانٍ بجانبها يزاحم خبرَ «عاد قيد المراجعة» —
      // وهو الأهمُّ للكبتن
      const shrunkNote = describeShrink(shrunk);
      setDone(
        (result.approval_reverted
          ? "رُفع المستند — وحسابك عاد «قيد المراجعة» حتى تُراجَع الوثيقة"
          : "رُفع المستند — بانتظار المراجعة") +
          (shrunkNote ? ` · ${shrunkNote}` : ""),
      );
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الرفع");
    } finally {
      setBusy(null);
    }
  }

  const vehicle = profile?.vehicles[0];
  // **الوثائقُ ثم صورُ المركبة الستّ** (البند ١١) — نفسُ ترتيب شاشة التسجيل،
  // فمن رفع هناك يجد الترتيبَ نفسَه هنا حين يستبدل
  const types: DocumentType[] = [
    "driving_license",
    "national_id",
    "vehicle_registration",
    "vehicle_front",
    "vehicle_back",
    "vehicle_plate",
    "vehicle_side_right",
    "vehicle_side_left",
    "vehicle_interior",
  ];

  return (
    <div className="scr h-full bg-bg px-16 pb-12 pt-safe">
      <div className="mb-16 mt-6 flex items-center gap-10">
        <button
          type="button"
          onClick={() => goBack()}
          aria-label="رجوع"
          className="pressable text-18 text-muted"
        >
          →
        </button>
        <h1 className="text-20 font-bold text-ink">المركبة والمستندات</h1>
      </div>

      <section className="mb-12 card p-15">
        {vehicle ? (
          <>
            <div className="mb-11 flex items-baseline justify-between">
              <span className="text-15 font-bold text-ink">
                {vehicle.make} {vehicle.model}
              </span>
              <span className="text-12 text-muted">
                {CATEGORY_LABEL[vehicle.category]}
              </span>
            </div>
            {editing ? (
              <VehicleForm
                vehicle={vehicle}
                approved={profile?.driver.status === "approved"}
                onCancel={() => setEditing(false)}
                onSaved={(reverted) => {
                  setEditing(false);
                  setReverted(reverted);
                  void refresh();
                }}
              />
            ) : (
              <>
                <Pair
                  label="سنة الصنع"
                  value={digits(String(vehicle.year))}
                />
                <Pair label="اللون" value={vehicle.color} />
                {/* اللوحةُ معرّفٌ مطبوعٌ على المركبة — تُعرض كما هي */}
                <Pair label="رقم اللوحة" value={vehicle.plate_number} ltr last />
                <button
                  type="button"
                  onClick={() => setEditing(true)}
                  className="pressable mt-11 w-full rounded-12 border border-line py-9 text-center text-12 font-semibold text-ink"
                >
                  تعديل بيانات المركبة
                </button>
                {reverted ? (
                  <p className="mt-9 rounded-12 border border-warn bg-surface-2 px-12 py-10 text-11 leading-note text-warn">
                    غُيّرت بياناتٌ في رخصة المركبة، فعاد حسابُك «قيد المراجعة»
                    حتى يعتمدها المشرف — ولا تصلك طلباتٌ حتى ذلك.
                  </p>
                ) : null}
              </>
            )}
          </>
        ) : (
          <p className="text-12.5 leading-note text-muted">
            لا مركبة مسجّلة على حسابك. راجع الدعم لتسجيلها.
          </p>
        )}
      </section>

      <h2 className="mb-10 mt-16 px-2 text-13 font-bold text-muted">
        المستندات
      </h2>

      <ErrorNote message={error} />
      <SuccessNote message={done} />

      {state === null && !error ? <Spinner className="mx-auto" /> : null}

      <div className="mt-10 flex flex-col gap-9">
        {types.map((docType) => {
          const document = state?.documents.find(
            (entry) => entry.doc_type === docType,
          );
          const review = document ? REVIEW_LABEL[document.review_status] : null;
          return (
            <DocumentRow
              key={docType}
              label={DOC_LABEL[docType]}
              review={review}
              note={document?.review_note ?? null}
              busy={busy === docType}
              onPick={(file) => void replace(docType, file)}
            />
          );
        })}
      </div>

      <p className="mt-14 text-11.5 leading-note text-muted">
        رفعُ مستندٍ من جديد يستبدل القديم ويعيده «قيد المراجعة». وإن كان حسابك
        معتمداً فسيعود قيد المراجعة حتى تُقبل الوثيقة الجديدة.
      </p>
    </div>
  );
}

function DocumentRow({
  label,
  review,
  note,
  busy,
  onPick,
}: {
  label: string;
  review: (typeof REVIEW_LABEL)[keyof typeof REVIEW_LABEL] | null;
  note: string | null;
  busy: boolean;
  onPick: (file: File) => void;
}) {
  const input = useRef<HTMLInputElement | null>(null);

  return (
    <div className="rounded-14 border border-line bg-surface px-14 py-12">
      <div className="flex items-center gap-10">
        <span
          className={cn(
            "block size-8 flex-none rounded-full",
            review ? review.dot : "bg-line",
          )}
        />
        <span className="flex-1 text-13 font-semibold text-ink">{label}</span>
        <span
          className={cn(
            "text-11.5 font-bold",
            review ? review.tone : "text-muted",
          )}
        >
          {review ? review.text : "لم يُرفع"}
        </span>
      </div>

      {note ? (
        <p className="mt-8 text-11 leading-snug text-danger">{note}</p>
      ) : null}

      <input
        ref={input}
        type="file"
        accept="image/jpeg,image/png,image/webp,application/pdf"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onPick(file);
          event.target.value = "";
        }}
      />
      <button
        type="button"
        disabled={busy}
        onClick={() => input.current?.click()}
        className="pressable mt-10 w-full rounded-12 border border-dashed border-line py-10 text-center text-12 font-semibold text-muted disabled:opacity-60"
      >
        {busy ? "…" : review ? "استبدال الملف" : "ارفع صورة"}
      </button>
    </div>
  );
}

function Pair({
  label,
  value,
  ltr = false,
  last = false,
}: {
  label: string;
  value: string;
  ltr?: boolean;
  last?: boolean;
}) {
  return (
    <div className={cn("flex justify-between text-12.5", last ? "" : "mb-8")}>
      <span className="text-muted">{label}</span>
      <span dir={ltr ? "ltr" : undefined} className="font-medium text-ink">
        {value}
      </span>
    </div>
  );
}


/** نموذجُ تعديل المركبة — **يقول ثمنَ التعديل قبل الحفظ**.
 *
 * حقولُ الهوية (اللوحة والطراز والصنع والسنة والفئة) تُسقط الاعتماد؛ واللونُ
 * لا. والتحذيرُ يظهر **حين يمسّ التعديلُ هويةً فعلاً** لا دائماً: تحذيرٌ
 * يظهر مع تصحيح لونٍ يُقرأ ضجيجاً ثم لا يُقرأ حين يهمّ.
 */
function VehicleForm({
  vehicle,
  approved,
  onCancel,
  onSaved,
}: {
  vehicle: Vehicle;
  approved: boolean;
  onCancel: () => void;
  onSaved: (reverted: boolean) => void;
}) {
  const [form, setForm] = useState({
    make: vehicle.make,
    model: vehicle.model,
    year: String(vehicle.year),
    color: vehicle.color,
    plate_number: vehicle.plate_number,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // نفس مجموعة `services/vehicles.py::IDENTITY_FIELDS` — والفئةُ لا تُحرَّر
  // من هذه الشاشة (تحدّد التسعيرة، فتغييرُها قرارُ إدارة)
  const identityChanged =
    form.make !== vehicle.make ||
    form.model !== vehicle.model ||
    form.year !== String(vehicle.year) ||
    form.plate_number !== vehicle.plate_number;

  /** الاقتراحاتُ نفسُها التي في شاشة التسجيل (البند د).
   *
   * **ولمَ هنا أيضاً؟** لأن التسجيلَ والتعديلَ **بابان ينشران الشيءَ نفسَه**:
   * قائمةٌ في أحدهما وحقلٌ عارٍ في الآخر تجعل الكبتنَ يكتب «Toyota» هنا و
   * «تويوتا» هناك، **فيصير للمركبة الواحدة اسمان**. وهو الشكلُ الثامن بعينه.
   */
  const { config } = useConfig();
  const yearRule = rulesFor(config?.validation, "vehicle_create").year;
  const yearOptions = vehicleYears(
    typeof yearRule?.min === "number" ? yearRule.min : 1990,
    typeof yearRule?.max === "number" ? yearRule.max : 2100,
  );

  function optionsFor(key: keyof typeof form): readonly string[] {
    if (key === "make") return VEHICLE_MAKES;
    if (key === "model") return VEHICLE_MODELS[form.make.trim()] ?? [];
    if (key === "color") return VEHICLE_COLORS;
    if (key === "year") return yearOptions;
    return [];
  }

  function field(key: keyof typeof form, label: string, ltr = false) {
    const options = optionsFor(key);
    const listId = options.length > 0 ? `veh-${key}-options` : undefined;
    return (
      <label className="mb-9 block">
        <span className="mb-4 block text-11 text-muted">{label}</span>
        <input
          dir={ltr ? "ltr" : undefined}
          list={listId}
          value={form[key]}
          onChange={(event) =>
            setForm((current) => ({ ...current, [key]: event.target.value }))
          }
          className="w-full rounded-12 border border-line bg-bg px-12 py-10 text-13 text-ink"
        />
        {listId ? (
          <datalist id={listId}>
            {options.map((option) => (
              <option key={option} value={option} />
            ))}
          </datalist>
        ) : null}
      </label>
    );
  }

  return (
    <div>
      {field("make", "الصنع")}
      {field("model", "الطراز")}
      {field("year", "سنة الصنع", true)}
      {field("color", "اللون")}
      {field("plate_number", "رقم اللوحة", true)}

      {identityChanged && approved ? (
        <p className="mb-10 rounded-12 border border-warn bg-surface-2 px-12 py-10 text-11 leading-note text-warn">
          هذه بياناتٌ في رخصة المركبة — حفظُها يعيد حسابك «قيد المراجعة» حتى
          يعتمدها المشرف، ولا تصلك طلباتٌ حتى ذلك.
        </p>
      ) : null}

      <ErrorNote message={error} />

      <div className="mt-10 flex gap-8">
        <button
          type="button"
          disabled={saving}
          onClick={() => {
            setSaving(true);
            setError(null);
            updateVehicle(vehicle.id, {
              make: form.make.trim(),
              model: form.model.trim(),
              year: Number(form.year),
              color: form.color.trim(),
              plate_number: form.plate_number.trim(),
            })
              .then((result) => onSaved(result.approval_reverted))
              .catch((caught) => {
                setError(
                  caught instanceof ApiError ? caught.message : "تعذّر الحفظ",
                );
                setSaving(false);
              });
          }}
          className="flex-1 rounded-12 bg-brand py-10 text-center text-13 font-bold text-brand-ink disabled:opacity-60"
        >
          حفظ
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="pressable flex-1 rounded-12 border border-line py-10 text-center text-13 font-semibold text-muted"
        >
          إلغاء
        </button>
      </div>
    </div>
  );
}
