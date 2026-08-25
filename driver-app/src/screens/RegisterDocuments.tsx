/** التسجيل — الخطوة 3 من 3: المركبة والمستندات (SPEC القسم 12/1).
 *
 * الخطوة الوحيدة التي تقع **بعد** فتح الحساب: رفعُ المستندات يحتاج جلسة،
 * ولذلك تُنشأ الجلسة في الخطوة السابقة ثم تُرفع الوثائق تحتها. والكبتن هنا
 * `pending` بحكم القاعدة، فلا يستقبل شيئاً حتى تُراجَع وثائقه.
 *
 * **ثلاثةُ مستنداتٍ مطلوبة** يقولها `missing_required` من الخلفية لا قائمةٌ
 * مكتوبةٌ هنا: من غيّر المطلوب في `models/driver.py` لا يترك شاشةً تسأل
 * غيره. و«صور المركبة» رابعٌ اختياري يظهر بلا وسم «مطلوب».
 *
 * والشكل من `design/DESIGN.md` §5.3: بطاقتان بنصف قطر 16 وحشوة 15، وصناديقُ
 * رفعٍ متقطّعة تتحوّل إلى «تم الرفع ✓» بلون `--ok`.
 */

import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { describeShrink, shrinkImage } from "@/lib/shrink";
import {
  addVehicle,
  listDocuments,
  updateDriver,
  uploadDocument,
} from "@/api/endpoints";
import type { DocumentType, VehicleCategory } from "@/api/types";
import { AuthScreen } from "@/components/ui/AuthScreen";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { Field } from "@/components/ui/Field";
import { useConfig } from "@/lib/config";
import { useDriver } from "@/lib/driver";
import { useSession } from "@/lib/session";
import { cn, toLatinDigits } from "@/lib/utils";
import { checkForm, rulesFor } from "@/lib/validation";

const DOC_LABEL: Record<DocumentType, string> = {
  driving_license: "رخصة القيادة",
  national_id: "الهوية الشخصية",
  vehicle_registration: "رخصة المركبة والتأمين",
  // مهجورٌ ولا يُعرض — بقي للصفوف القديمة (البند ١١)
  vehicle_photo: "صورة المركبة",
  vehicle_front: "المركبة من الأمام",
  vehicle_back: "المركبة من الخلف",
  vehicle_side_right: "الجانب الأيمن",
  vehicle_side_left: "الجانب الأيسر",
  vehicle_interior: "من الداخل",
  vehicle_plate: "لوحة المركبة",
  profile_photo: "الصورة الشخصية",
};

/** **ما يُقرأ تحت اسم كل صورة**: صورةٌ تُرفض لأنها من زاويةٍ خطأ تُعاد مرتين،
 *  وسطرٌ واحدٌ يقول ما المطلوب يوفّر الدورتين. */
const DOC_HINT: Partial<Record<DocumentType, string>> = {
  // **ويُقال إنها تُعرض** — فهذا ما يجعله يختار صورةً تليق من أول مرة
  profile_photo: "وجهُك واضحاً — يراها الراكب قبل الرحلة",
  vehicle_front: "الواجهة كاملةً واللوحة ظاهرة",
  vehicle_back: "الخلف كاملاً واللوحة ظاهرة",
  vehicle_side_right: "الجانب الأيمن كاملاً",
  vehicle_side_left: "الجانب الأيسر كاملاً",
  vehicle_interior: "المقاعد الأمامية والخلفية",
  vehicle_plate: "اللوحة وحدها، واضحةَ الأرقام",
};

const CATEGORY_LABEL: Record<VehicleCategory, string> = {
  economy: "اقتصادي",
  comfort: "مريح",
};

/** **الوثائقُ أولاً ثم صورُ المركبة** — قسمان لا قائمةٌ من تسعة.
 *
 * والمطلوبُ للاعتماد ثلاثةُ وثائق وثلاثُ صور (الأمام والخلف واللوحة)، والباقي
 * يزيد الثقة ولا يحبس اعتماداً (قرارُ المالك 2026-08-14). **ويُقال ذلك في
 * الشاشة**: «اختياري» مكتوبةٌ بجانبه — فمن يراه مطلوباً يظنّ نفسَه ممنوعاً.
 */
const PAPERS: DocumentType[] = [
  // **الصورةُ الشخصية أولاً** (البند ٥٢): هي الوحيدةُ التي **يراها الراكب**،
  // فوضعُها بين أوراق المركبة يجعلها تُقرأ ورقةً إداريةً أخرى. ومن يعرف أنها
  // تُعرض يختار صورةً تليق — ومن لا يعرف يرفع أوّلَ ما في هاتفه ثم تُرفض.
  "profile_photo",
  "driving_license",
  "national_id",
  "vehicle_registration",
];

const VEHICLE_PHOTOS: DocumentType[] = [
  "vehicle_front",
  "vehicle_back",
  "vehicle_plate",
  "vehicle_side_right",
  "vehicle_side_left",
  "vehicle_interior",
];

const ORDER: DocumentType[] = [...PAPERS, ...VEHICLE_PHOTOS];

/** ما **له تاريخُ انتهاء** — والباقي لا خانةَ له (البند ب).
 *
 * **وليست «كلَّ مستند»**: صورةُ المركبة من الأمام لا تنتهي، والصورةُ الشخصيةُ
 * لا تنتهي — وخانةُ تاريخٍ تحتهما تسأل عمّا لا جواب له، **فتُملأ بأيِّ شيءٍ
 * ليمرّ النموذج**. والثلاثةُ هنا تحمل تاريخاً مطبوعاً على الورقة نفسِها.
 */
const EXPIRING: DocumentType[] = [
  "driving_license",
  "national_id",
  "vehicle_registration",
];


export function RegisterDocumentsScreen() {
  const navigate = useNavigate();
  const { config } = useConfig();
  const { user } = useSession();
  const { refresh } = useDriver();

  const categories = config?.countries.find(
    (entry) => entry.country_code === user?.country_code,
  )?.vehicle_categories ?? ["economy"];

  const [make, setMake] = useState("");
  const [model, setModel] = useState("");
  const [year, setYear] = useState("");
  const [color, setColor] = useState("");
  const [plate, setPlate] = useState("");
  const [category, setCategory] = useState<VehicleCategory>(categories[0]);
  const [alias, setAlias] = useState("");

  const [uploaded, setUploaded] = useState<Set<DocumentType>>(new Set());
  const [required, setRequired] = useState<DocumentType[]>([]);
  // **القائمةُ الكاملة من الخلفية** (البند ١١): بها وحدها يُعرف الاختياريُّ من
  // المرفوع — والناقصُ لا يفرّق بينهما
  const [requiredAll, setRequiredAll] = useState<DocumentType[]>([]);
  const [uploading, setUploading] = useState<DocumentType | null>(null);
  // **نسبةُ الرفع وبابُ إلغائه** — ورفعٌ بلا مهلةٍ يلزمه الاثنان معاً: النسبةُ
  // تقول «يتقدّم»، والزرُّ يقول «تستطيع الخروج». وشاشةٌ بلا مخرجٍ هي العطبُ
  // الذي يصلحه هذا العقد.
  const [progress, setProgress] = useState(0);
  const uploadAbort = useRef<AbortController | null>(null);
  // **آخرُ محاولةٍ فاشلة تبقى محفوظةً** ليكون للخطأ زرٌّ لا نصٌّ وحدَه: من
  // انقطع رفعُه لا يجد `input[type=file]` مفتوحاً، وإعادةُ اختيار الملف من
  // معرض الصور خطواتٌ يفقد بينها الغرض. **ورفضٌ بلا مخرجٍ ليس رفضاً.**
  const [retry, setRetry] = useState<{ doc: DocumentType; file: File } | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  /** ما صُغِّر ولمن — سطرٌ تحت الوثيقة بعد رفعها. */
  const [shrunkNote, setShrunkNote] = useState<Partial<Record<DocumentType, string>>>(
    {},
  );
  // **خطأُ حقلٍ بعينه كما سمّته الخلفية** (عقدُ الأخطاء، SPEC ١٧.٧): الجسمُ
  // يحمل `field` و`message`، فيُعلَّم الحقلُ ويُنقل إليه التركيز — بدل شريطٍ
  // أعلى النموذج يقول «تعذّر الإرسال» ويترك صاحبَه يبحث عن الحقل بين ستة.
  //
  // **والنصُّ من الخلفية لا من هنا**: قاعدةُ «لا تخترع الواجهةُ نصّاً لخطأٍ
  // سمّته الخلفية» — ونصٌّ نكتبه هنا يخالف نصَّها أوّلَ تعديلٍ في المخطط.
  const [fieldError, setFieldError] = useState<{
    field: string;
    message: string;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const pickers = useRef<
    Partial<Record<DocumentType, HTMLInputElement | null>>
  >({});

  // ما رُفع فعلاً وما بقي مطلوباً — من الخلفية، فإعادةُ فتح الشاشة لا تبدأ
  // من الصفر ولا تطلب ما رُفع
  useEffect(() => {
    listDocuments()
      .then((response) => {
        setUploaded(new Set(response.documents.map((item) => item.doc_type)));
        // **ما عليه هو** لا ما ينقص الحارس: المرفوعُ المنتظِرُ مراجعةً
        // لا يُوسم «مطلوب»، وإلا رفعه صاحبُه مرةً ثانية
        setRequired(response.awaiting_upload);
        setRequiredAll(response.required);
      })
      .catch(() => undefined);
  }, []);

  // تاريخُ الانتهاء لكلِّ نوعٍ يحمله — يُقرأ عند الرفع ويُرسَل معه
  const [expiry, setExpiry] = useState<Partial<Record<DocumentType, string>>>({});

  async function pick(docType: DocumentType, file: File | undefined) {
    if (!file) return;
    setUploading(docType);
    setProgress(0);
    setError(null);
    setRetry(null);
    const controller = new AbortController();
    uploadAbort.current = controller;
    try {
      // **يُضغط قبل أن يخرج** (`lib/shrink.ts`): وثيقةٌ تُقرأ بالعين لا تحتاج
      // اثنَي عشرَ ميجابكسل، والكبتنُ يرفع إحدى عشرةَ وثيقة — فالفرقُ بين
      // الضغط وتركِه هو الفرقُ بين ٥٥ ميجا و١٨ للحساب الواحد
      const shrunk = await shrinkImage(file);
      await uploadDocument(docType, shrunk.file, {
        onProgress: setProgress,
        signal: controller.signal,
        expiresOn: expiry[docType],
      });
      // **يُقال بعد نجاح الرفع لا قبله**: سطرٌ يعلن التصغير ثم يفشل الرفعُ
      // يترك الكبتنَ يظنّ أن وثيقتَه ذهبت مصغَّرةً وهي لم تذهب أصلاً
      setShrunkNote((current) => ({
        ...current,
        [docType]: describeShrink(shrunk) ?? undefined,
      }));
      setUploaded((current) => new Set(current).add(docType));
      setRequired((current) => current.filter((item) => item !== docType));
    } catch (caught) {
      // من ألغى يعرف أنه ألغى — ورسالةٌ حمراءُ بعده تجعله يظنّ شيئاً انكسر
      if ((caught as Error)?.name === "AbortError") return;
      setError(caught instanceof ApiError ? caught.message : "تعذّر رفع الملف");
      setRetry({ doc: docType, file });
    } finally {
      uploadAbort.current = null;
      setUploading(null);
      setProgress(0);
    }
  }

  const missing = ORDER.filter(
    (doc) => required.includes(doc) && !uploaded.has(doc),
  );
  const vehicleReady =
    make.trim() && model.trim() && year.trim() && color.trim() && plate.trim();

  async function submit() {
    // **تحقّقٌ فوريٌّ بالقواعد المنشورة قبل رحلة الشبكة** (SPEC ١٧.٣).
    // ونصُّه نصُّ الخلفية بعينه، فلا يقرأ المستخدمُ رسالتين لشرطٍ واحد.
    const rejected = checkForm(rulesFor(config?.validation, "vehicle_create"), {
      make,
      model,
      year,
      color,
      plate_number: plate,
      category,
    });
    if (rejected) {
      setFieldError(rejected);
      setError(null);
      document
        .querySelector<HTMLInputElement>(`[name="${rejected.field}"]`)
        ?.focus();
      return;
    }

    setBusy(true);
    setError(null);
    setFieldError(null);
    try {
      await addVehicle({
        make: make.trim(),
        model: model.trim(),
        year: Number(year),
        color: color.trim(),
        plate_number: plate.trim(),
        category,
      });
      if (alias.trim()) await updateDriver({ cliq_alias: alias.trim() });
      await refresh();
      navigate("/", { replace: true });
    } catch (caught) {
      if (caught instanceof ApiError) {
        const field = caught.field("field");
        if (field) {
          setFieldError({ field, message: caught.message });
          // التركيزُ إلى أوّل حقلٍ مرفوض — والشريطُ يبقى فارغاً كي لا يُقرأ
          // الخطأُ مرتين في موضعين
          setError(null);
          document
            .querySelector<HTMLInputElement>(`[name="${field}"]`)
            ?.focus();
        } else {
          setFieldError(null);
          setError(caught.message);
        }
      } else {
        setFieldError(null);
        setError("تعذّر الاتصال بالخادم — تحقّق من شبكتك ثم أعد المحاولة");
      }
    } finally {
      setBusy(false);
    }
  }

  /** رسالةُ الحقل إن كان هو المرفوض — تُمسح بأوّل تعديلٍ عليه. */
  const errorFor = (field: string) =>
    fieldError?.field === field ? fieldError.message : null;

  return (
    <AuthScreen className="px-26">
      <div className="text-12 text-muted">الخطوة 3 من 3</div>
      <h1 className="mb-4 text-22 font-bold text-ink">المركبة والمستندات</h1>
      <p className="mb-18 text-12.5 leading-snug text-muted">
        لا يُعتمد الكبتن قبل مراجعة الإدارة للمستندات.
      </p>

      <section className="mb-12 card p-15">
        <h2 className="mb-12 text-13.5 font-bold text-ink">المركبة</h2>
        <div className="mb-8 flex gap-8">
          <Field
            name="make"
            error={errorFor("make")}
            placeholder="الشركة"
            value={make}
            onChange={(event) => setMake(event.target.value)}
          />
          <Field
            name="model"
            error={errorFor("model")}
            placeholder="الطراز"
            value={model}
            onChange={(event) => setModel(event.target.value)}
          />
        </div>
        <div className="mb-8 flex gap-8">
          <Field
            name="year"
            error={errorFor("year")}
            inputMode="numeric"
            placeholder="سنة الصنع"
            value={year}
            // **يقبل ٠١٢٣ كما يقبل 0123.** كان `\D` يمحو الأرقامَ العربية
            // كلَّها لأنها ليست `[0-9]` — فيبقى الحقلُ فارغاً وزرُّ الإرسال
            // معطَّلاً **بلا سبب مكتوب**، في تطبيقٍ كلُّ أرقامه عربية.
            onChange={(event) => setYear(toLatinDigits(event.target.value))}
          />
          <Field
            name="color"
            error={errorFor("color")}
            placeholder="اللون"
            value={color}
            onChange={(event) => setColor(event.target.value)}
          />
        </div>
        <Field
          name="plate_number"
          error={errorFor("plate_number")}
          dir="ltr"
          className="mb-8"
          placeholder="رقم اللوحة"
          value={plate}
          onChange={(event) => setPlate(event.target.value)}
        />
        <div className="flex gap-8">
          {categories.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setCategory(value)}
              className={cn(
                "pressable flex-1 rounded-13 border p-11 text-13 font-semibold",
                value === category
                  ? "border-ink bg-surface-2 text-ink"
                  : "border-line text-ink",
              )}
            >
              {CATEGORY_LABEL[value]}
            </button>
          ))}
        </div>
      </section>

      <section className="card p-15">
        <h2 className="mb-12 text-13.5 font-bold text-ink">المستندات</h2>
        {retry && !uploading ? (
          <button
            type="button"
            className="mb-12 text-11.5 font-bold text-accent-ink"
            onClick={() => void pick(retry.doc, retry.file)}
          >
            أعد رفع «{DOC_LABEL[retry.doc]}»
          </button>
        ) : null}
        {uploading ? (
          <div className="mb-12 flex items-center gap-10">
            {/* شريطُ تقدّمٍ يقول «يتقدّم»، لا دوّامةٌ تقول «انتظر» */}
            <div className="h-6 flex-1 overflow-hidden rounded-13 bg-surface-2">
              <div
                className="h-full bg-ok transition-[width] duration-200"
                style={{ width: `${progress}%` }}
              />
            </div>
            <button
              type="button"
              className="text-11.5 font-bold text-danger"
              onClick={() => uploadAbort.current?.abort()}
            >
              إلغاء
            </button>
          </div>
        ) : null}
        <div className="flex flex-col gap-10">
          {ORDER.map((doc) => {
            const done = uploaded.has(doc);
            return (
              <div key={doc}>
                <button
                  type="button"
                  onClick={() => pickers.current[doc]?.click()}
                  disabled={uploading !== null}
                  className={cn(
                    "pressable flex w-full items-center gap-12 rounded-13 border border-dashed p-13 text-start",
                    done ? "border-ok bg-surface-2" : "border-line",
                  )}
                >
                  <span className="block h-30 w-38 shrink-0 rounded-7 bg-stripe" />
                  <span className="flex-1 text-12.5 text-ink">
                    {DOC_LABEL[doc]}
                    {/* **«اختياري» تُقال، و«مطلوب» تُقال للناقص وحدَه**: من رأى
                        صورةً بلا وسمٍ ظنّها مطلوبةً فانتظر اعتماداً يحبسه شيءٌ
                        لا يحبسه. والقائمةُ من الخلفية لا من نسخةٍ هنا */}
                    {requiredAll.length > 0 && !requiredAll.includes(doc) ? (
                      <span className="text-muted"> · اختياري</span>
                    ) : required.includes(doc) && !done ? (
                      <span className="text-muted"> · مطلوب</span>
                    ) : null}
                    {DOC_HINT[doc] ? (
                      <span className="mt-2 block text-11 leading-snug text-muted">
                        {DOC_HINT[doc]}
                      </span>
                    ) : null}
                    {shrunkNote[doc] ? (
                      <span className="mt-2 block text-11 leading-snug text-ok">
                        {shrunkNote[doc]}
                      </span>
                    ) : null}
                  </span>
                  <span
                    className={cn(
                      "text-11.5 font-bold",
                      done ? "text-ok" : "text-muted",
                    )}
                  >
                    {uploading === doc
                      ? `${progress}٪`
                      : done
                        ? "تم الرفع ✓"
                        : "ارفع صورة"}
                  </span>
                </button>
                {/* **تحت المستند لا داخلَ زرّه**: الزرُّ يفتح منتقيَ الملفات،
                    وخانةٌ داخلَه تُفتح المنتقيَ عند كلِّ لمسة. والتاريخُ
                    يُملأ **قبل** الرفع فيذهب معه في الطلب نفسِه — ولو مُلئ
                    بعده لاحتاج نداءً ثانياً وبابين لشيءٍ واحد. */}
                {EXPIRING.includes(doc) ? (
                  <label className="mt-6 flex items-center gap-8 ps-13 text-11.5 text-muted">
                    <span className="shrink-0">تنتهي في</span>
                    <input
                      type="date"
                      value={expiry[doc] ?? ""}
                      onChange={(event) =>
                        setExpiry((current) => ({
                          ...current,
                          [doc]: event.target.value || undefined,
                        }))
                      }
                      className="fld flex-1 py-6 text-12"
                    />
                  </label>
                ) : null}
                <input
                  ref={(element) => {
                    pickers.current[doc] = element;
                  }}
                  type="file"
                  accept="image/jpeg,image/png,image/webp,application/pdf"
                  className="hidden"
                  onChange={(event) => {
                    void pick(doc, event.target.files?.[0]);
                    event.target.value = "";
                  }}
                />
              </div>
            );
          })}
        </div>
      </section>

      <div className="mt-14">
        <Field
          label="alias كليك"
          name="cliq-alias"
          dir="ltr"
          value={alias}
          onChange={(event) => setAlias(event.target.value)}
        />
      </div>

      <div className="mt-18 flex flex-col gap-12">
        <ErrorNote message={error} />
        <Button
          size="md"
          loading={busy}
          disabled={!vehicleReady || missing.length > 0}
          onClick={() => void submit()}
        >
          إرسال الطلب
        </Button>
      </div>
    </AuthScreen>
  );
}
