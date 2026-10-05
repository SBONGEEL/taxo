/** التسجيل — **الخطوتان «المركبة» ثمّ «الوثائق»** (SPEC القسم 12/1)، **بلغة C02** (Claude Design «TAXO 2.0 - Captain»):
 * «الوثائق» كما رُسمت — بطاقةُ المركبة و«تعديل»، والصفوفُ بحالاتها الثلاث (مرفوعة · مرفوضة وسببُها · لم تُرفع)، والزرُّ المعطَّلُ
 * وسطرُه — **و«المركبة» لم تُرسم** فرُسمت بلغتها (`RegisterTop` وحقولُ C01).
 *
 * الخطوتان الوحيدتان اللتان تقعان **بعد** فتح الحساب: رفعُ المستندات يحتاج جلسة، ولذلك تُنشأ الجلسة في «الحساب» ثم تُرفع
 * الوثائق تحتها. والكبتن هنا `pending` بحكم القاعدة، فلا يستقبل شيئاً حتى تُراجَع وثائقه.
 *
 * **والنداءاتُ كما كانت حرفاً وبترتيبها**: `GET /drivers/me/documents` عند الفتح، وكلُّ وثيقةٍ تُرفع **لحظةَ اختيارها**
 * (`POST /drivers/me/documents/{type}` مضغوطةً، بنسبتها وإلغائها وتاريخ انتهائها)، **والمركبةُ لا تُنشأ إلا بالزرّ الأخير** —
 * `POST /drivers/me/vehicles` ثمّ `PATCH /drivers/me` للـalias إن كُتب ثمّ إعادةُ قراءة الملف. **فخطوةُ «المركبة» تحفظ ما كُتب
 * في الشاشة ولا تنادي شيئاً**، وتفحصه بالقواعد المنشورة نفسِها قبل أن تمضي (§17.3) — ثمّ يُفحص ثانيةً قبل الإرسال كما كان.
 *
 * **ومن له مركبةٌ مسجَّلةٌ** (جاء من «قيد المراجعة» ليكمل ما ينقص) يبدأ من «الوثائق» ويرى مركبتَه فيها، **ولا يُعرض عليه نموذجُ
 * مركبةٍ وزرُّ إرسالٍ** ينشئان مركبةً ثانية (`POST /drivers/me/vehicles` لا يعرف مركبةً قائمة) — ورجوعُه إلى حيث جاء.
 *
 * **ثلاثةُ مستنداتٍ وثلاثُ صورٍ مطلوبة** يقولها `required`/`awaiting_upload` من الخلفية لا قائمةٌ مكتوبةٌ هنا: من غيّر المطلوب
 * في `models/driver.py` لا يترك شاشةً تسأل غيره. والباقي يُوسم «اختياري».
 */

import { useEffect, useId, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { addVehicle, listDocuments, updateDriver, uploadDocument } from "@/api/endpoints";
import type { DocumentType, VehicleCategory } from "@/api/types";
import { DocumentRow } from "@/components/t2/DocumentRow";
import type { DocumentState } from "@/components/t2/DocumentRow";
import { RegisterTop } from "@/components/t2/RegisterTop";
import { useGoBack } from "@/lib/back";
import { useConfig } from "@/lib/config";
import { useDriver } from "@/lib/driver";
import { useSession } from "@/lib/session";
import { describeShrink, shrinkImage } from "@/lib/shrink";
import { toLatinDigits } from "@/lib/utils";
import { checkForm, rulesFor } from "@/lib/validation";
import { VEHICLE_COLORS, VEHICLE_MAKES, VEHICLE_MODELS, vehicleYears } from "@/lib/vehicle-options";
import { AuthBlock, AuthChoice, AuthError, AuthInput, AuthPage, DateField, Icon } from "@/taxo2";

import "@/components/t2/captain-auth.css";

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

/** **الوثائقُ أولاً ثم صورُ المركبة** — قسمان لا قائمةٌ من عشرة.
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
const EXPIRING: DocumentType[] = ["driving_license", "national_id", "vehicle_registration"];

/** حقولُ المركبة كما تسمّيها الخلفية — خطأٌ يسمّي واحداً منها يُعرض تحته في «المركبة». */
const VEHICLE_FIELDS = ["make", "model", "year", "color", "plate_number", "category"];

type Stage = "vehicle" | "documents";

/** قائمةُ الاقتراحات تحت حقلٍ (`datalist`) — **اقتراحٌ لا حصر**: يُنتقى منها أو يُكتب فيه (`lib/vehicle-options.ts`). */
function Suggestions({ id, options }: { id: string; options: readonly string[] }) {
  if (options.length === 0) return null;
  return (
    <datalist id={id}>
      {options.map((option) => (
        <option key={option} value={option} />
      ))}
    </datalist>
  );
}

export function RegisterDocumentsScreen() {
  const navigate = useNavigate();
  const goBack = useGoBack("/");
  const { config } = useConfig();
  const { user } = useSession();
  const { profile, refresh } = useDriver();
  const page = useRef<HTMLDivElement>(null);
  const listBase = useId();

  const categories =
    config?.countries.find((entry) => entry.country_code === user?.country_code)?.vehicle_categories ?? ["economy"];

  const [make, setMake] = useState("");
  const [model, setModel] = useState("");
  const [year, setYear] = useState("");
  const [color, setColor] = useState("");
  const [plate, setPlate] = useState("");
  const [category, setCategory] = useState<VehicleCategory>(categories[0]);
  const [alias, setAlias] = useState("");

  // **أمسجَّلةٌ له مركبةٌ قبل أن يفتح الشاشة؟** — يُقرأ مرّةً حين يُعرف الملف، ولا يتبدّل بعد إنشاء المركبة هنا
  const [returning, setReturning] = useState<boolean | null>(() =>
    profile ? profile.vehicles.length > 0 : null,
  );
  useEffect(() => {
    if (returning === null && profile) setReturning(profile.vehicles.length > 0);
  }, [profile, returning]);
  const [chosen, setChosen] = useState<Stage | null>(null);
  const stage: Stage = chosen ?? (returning ? "documents" : "vehicle");

  const [uploaded, setUploaded] = useState<Set<DocumentType>>(new Set());
  const [required, setRequired] = useState<DocumentType[]>([]);
  // **القائمةُ الكاملة من الخلفية** (البند ١١): بها وحدها يُعرف الاختياريُّ من
  // المرفوع — والناقصُ لا يفرّق بينهما
  const [requiredAll, setRequiredAll] = useState<DocumentType[]>([]);
  // **ما رُفض وسببُه** (C02: «أعد الرفع» وسطرُ السبب) — من القراءة نفسِها، ويزول برفعه من جديد.
  // **ولا يغيّر شرطَ الزرّ**: المرفوضُ له صفٌّ فلا يُعدّ ناقصاً، كما كان
  const [rejections, setRejections] = useState<Partial<Record<DocumentType, string | null>>>({});
  const [uploading, setUploading] = useState<DocumentType | null>(null);
  // **نسبةُ الرفع وبابُ إلغائه** — ورفعٌ بلا مهلةٍ يلزمه الاثنان معاً: النسبةُ
  // تقول «يتقدّم»، والزرُّ يقول «تستطيع الخروج». وشاشةٌ بلا مخرجٍ هي العطبُ
  // الذي يصلحه هذا العقد.
  const [progress, setProgress] = useState(0);
  const uploadAbort = useRef<AbortController | null>(null);
  // **آخرُ محاولةٍ فاشلة تبقى محفوظةً** ليكون للخطأ زرٌّ لا نصٌّ وحدَه: من
  // انقطع رفعُه لا يجد `input[type=file]` مفتوحاً، وإعادةُ اختيار الملف من
  // معرض الصور خطواتٌ يفقد بينها الغرض. **ورفضٌ بلا مخرجٍ ليس رفضاً.**
  // **وسببُه تحت صفِّ وثيقته** لا في أسفل الشاشة (§٦٢/٢٠).
  const [retry, setRetry] = useState<{ doc: DocumentType; file: File; message: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  /** ما صُغِّر ولمن — سطرٌ تحت الوثيقة بعد رفعها. */
  const [shrunkNote, setShrunkNote] = useState<Partial<Record<DocumentType, string>>>({});
  // **خطأُ حقلٍ بعينه كما سمّته الخلفية** (عقدُ الأخطاء، SPEC ١٧.٧): الجسمُ
  // يحمل `field` و`message`، فيُعلَّم الحقلُ ويُنقل إليه التركيز — بدل شريطٍ
  // أعلى النموذج يقول «تعذّر الإرسال» ويترك صاحبَه يبحث عن الحقل بين ستة.
  //
  // **والنصُّ من الخلفية لا من هنا**: قاعدةُ «لا تخترع الواجهةُ نصّاً لخطأٍ
  // سمّته الخلفية» — ونصٌّ نكتبه هنا يخالف نصَّها أوّلَ تعديلٍ في المخطط.
  const [fieldError, setFieldError] = useState<{ field: string; message: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const pickers = useRef<Partial<Record<DocumentType, HTMLInputElement | null>>>({});
  // تاريخُ الانتهاء لكلِّ نوعٍ يحمله — يُقرأ عند الرفع ويُرسَل معه
  const [expiry, setExpiry] = useState<Partial<Record<DocumentType, string>>>({});

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
        const notes: Partial<Record<DocumentType, string | null>> = {};
        for (const item of response.documents) {
          if (item.review_status === "rejected") notes[item.doc_type] = item.review_note;
        }
        setRejections(notes);
      })
      .catch(() => undefined);
  }, []);

  // الخطوةُ الجديدةُ تُفتح من أعلاها لا من حيث توقّف التمرير
  useEffect(() => {
    if (page.current) page.current.scrollTop = 0;
  }, [stage]);

  // **حدُّ السنة من القاعدة المنشورة لا من هنا** (§17.3): رقمان في موضعين
  // يفترقان أوّلَ تعديل — وقد وقع في هذا المشروع مرّةً (سقفُ واتساب ٣ ثمّ ٢٠).
  const yearRule = rulesFor(config?.validation, "vehicle_create").year;
  const yearOptions = vehicleYears(
    typeof yearRule?.min === "number" ? yearRule.min : 1990,
    typeof yearRule?.max === "number" ? yearRule.max : 2100,
  );

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
      setRejections((current) => {
        const next = { ...current };
        delete next[docType];
        return next;
      });
    } catch (caught) {
      // من ألغى يعرف أنه ألغى — ورسالةٌ حمراءُ بعده تجعله يظنّ شيئاً انكسر
      if ((caught as Error)?.name === "AbortError") return;
      setRetry({
        doc: docType,
        file,
        message: caught instanceof ApiError ? caught.message : "تعذّر رفع الملف",
      });
    } finally {
      uploadAbort.current = null;
      setUploading(null);
      setProgress(0);
    }
  }

  const missing = ORDER.filter((doc) => required.includes(doc) && !uploaded.has(doc));
  const vehicleReady = make.trim() && model.trim() && year.trim() && color.trim() && plate.trim();

  /** **تحقّقٌ فوريٌّ بالقواعد المنشورة قبل رحلة الشبكة** (SPEC ١٧.٣) — ونصُّه نصُّ الخلفية بعينه، فلا يقرأ المستخدمُ رسالتين
   *  لشرطٍ واحد. */
  function vehicleRejection() {
    return checkForm(rulesFor(config?.validation, "vehicle_create"), {
      make,
      model,
      year,
      color,
      plate_number: plate,
      category,
    });
  }

  /** التركيزُ إلى الحقل المرفوض **بعد أن يُرسم** — قد يكون في الخطوة الأخرى. */
  function focusField(name: string) {
    window.setTimeout(() => document.querySelector<HTMLInputElement>(`[name="${name}"]`)?.focus(), 0);
  }

  function toDocuments(event: FormEvent) {
    event.preventDefault();
    if (!vehicleReady) return;
    const rejected = vehicleRejection();
    if (rejected) {
      setFieldError(rejected);
      focusField(rejected.field);
      return;
    }
    setFieldError(null);
    setChosen("documents");
  }

  async function submit() {
    const rejected = vehicleRejection();
    if (rejected) {
      setFieldError(rejected);
      setError(null);
      setChosen("vehicle");
      focusField(rejected.field);
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
        if (field && (VEHICLE_FIELDS.includes(field) || field === "cliq_alias")) {
          // **تحت حقله** — حقولُ المركبة في خطوتها فيُعاد إليها، والـalias هنا؛ والشريطُ يبقى فارغاً
          // كي لا يُقرأ الخطأُ مرتين في موضعين
          setFieldError({ field, message: caught.message });
          setError(null);
          if (field === "cliq_alias") {
            focusField("cliq-alias");
          } else {
            setChosen("vehicle");
            focusField(field);
          }
        } else {
          // حقلٌ لا موضعَ له في الشاشة — أو لا حقل: سطرٌ فوق الزرّ، لا رسالةٌ تضيع
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

  /** رسالةُ الحقل إن كان هو المرفوض. */
  const errorFor = (field: string) => (fieldError?.field === field ? fieldError.message : null);

  /** حالُ الصفّ: رُفعت (ولم تُرفض) · رُفضت وسببُها · لم تُرفع. */
  const stateOf = (doc: DocumentType): DocumentState =>
    doc in rejections ? "refused" : uploaded.has(doc) ? "uploaded" : "missing";

  function renderRow(doc: DocumentType) {
    const state = stateOf(doc);
    // **«اختياري» تُقال، و«مطلوب» تُقال للناقص وحدَه**: من رأى صورةً بلا وسمٍ ظنّها مطلوبةً فانتظر اعتماداً يحبسه شيءٌ لا
    // يحبسه. والقائمةُ من الخلفية لا من نسخةٍ هنا
    const tag =
      requiredAll.length > 0 && !requiredAll.includes(doc)
        ? " · اختياري"
        : required.includes(doc) && !uploaded.has(doc)
          ? " · مطلوب"
          : null;
    const note = rejections[doc];
    return (
      <DocumentRow
        key={doc}
        label={DOC_LABEL[doc]}
        tag={tag}
        sub={DOC_HINT[doc] ?? (state === "missing" ? "صورة أو PDF" : null)}
        shrunk={shrunkNote[doc] ?? null}
        state={state}
        percent={uploading === doc ? progress : null}
        disabled={uploading !== null}
        onOpen={() => pickers.current[doc]?.click()}
      >
        {state === "refused" && note ? <AuthError message={note} /> : null}

        {retry?.doc === doc && !uploading ? (
          <>
            <AuthError message={retry.message} />
            <button type="button" className="cap-doc-retry" onClick={() => void pick(retry.doc, retry.file)}>
              أعد رفع «{DOC_LABEL[retry.doc]}»
            </button>
          </>
        ) : null}

        {uploading === doc ? (
          <div className="cap-doc-progress">
            {/* شريطُ تقدّمٍ يقول «يتقدّم»، لا دوّامةٌ تقول «انتظر» */}
            <span
              className="cap-doc-bar"
              role="progressbar"
              aria-label={`رفع ${DOC_LABEL[doc]}`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progress}
            >
              <span style={{ width: `${progress}%` }} />
            </span>
            <button type="button" className="cap-doc-cancel" onClick={() => uploadAbort.current?.abort()}>
              إلغاء
            </button>
          </div>
        ) : null}

        {/* **تحت المستند لا داخلَ زرّه**: الزرُّ يفتح منتقيَ الملفات، وخانةٌ داخلَه تُفتح المنتقيَ عند كلِّ لمسة. والتاريخُ يُملأ
            **قبل** الرفع فيذهب معه في الطلب نفسِه — ولو مُلئ بعده لاحتاج نداءً ثانياً وبابين لشيءٍ واحد. */}
        {EXPIRING.includes(doc) ? (
          <div className="cap-doc-expiry">
            <span aria-hidden="true">تنتهي في</span>
            {/* **لا `<input type="date">` ظاهراً**: كان يرسم «يوم/شهر/سنة» بحروفٍ معكوسة (§٦٢/٢٠) — `DateField` */}
            <DateField
              label={`تنتهي في — ${DOC_LABEL[doc]}`}
              value={expiry[doc] ?? ""}
              onChange={(value) =>
                setExpiry((current) => ({
                  ...current,
                  [doc]: value || undefined,
                }))
              }
            />
          </div>
        ) : null}

        <input
          ref={(element) => {
            pickers.current[doc] = element;
          }}
          type="file"
          accept="image/jpeg,image/png,image/webp,application/pdf"
          hidden
          onChange={(event) => {
            void pick(doc, event.target.files?.[0]);
            event.target.value = "";
          }}
        />
      </DocumentRow>
    );
  }

  function section(title: string, docs: DocumentType[]) {
    const done = docs.filter((doc) => stateOf(doc) === "uploaded").length;
    return (
      <section className="cap-sec-wrap">
        <div className="cap-sec">
          <h2 className="cap-sec-title">{title}</h2>
          <span className="cap-sec-count">
            {done} من {docs.length}
          </span>
        </div>
        <div className="cap-docs">{docs.map(renderRow)}</div>
      </section>
    );
  }

  if (stage === "vehicle") {
    const listId = (key: string) => `${listBase}-${key}`;
    const modelOptions = VEHICLE_MODELS[make.trim()] ?? [];
    return (
      <div ref={page} className="cap-auth cap-reg scr">
        <AuthPage>
          {/* **بلا رجوع**: الحسابُ فُتح ولا خطوةَ قبل هذه تُعاد */}
          <RegisterTop step={2} />

          <form onSubmit={toDocuments} className="t2-auth-form" noValidate>
            <AuthBlock label="الشركة" htmlFor="make" error={errorFor("make")}>
              <AuthInput
                id="make"
                name="make"
                list={listId("make")}
                value={make}
                invalid={Boolean(errorFor("make"))}
                onChange={(event) => setMake(event.target.value)}
              />
              <Suggestions id={listId("make")} options={VEHICLE_MAKES} />
            </AuthBlock>

            {/* **طُرزُ الشركة المختارة وحدَها** — ومن كتب شركةً ليست في القائمة يجد حقلَ الطراز بلا اقتراحات، **وهو يكتب فيه كما
                يكتب اليوم**. */}
            <AuthBlock label="الطراز" htmlFor="model" error={errorFor("model")}>
              <AuthInput
                id="model"
                name="model"
                list={modelOptions.length > 0 ? listId("model") : undefined}
                value={model}
                invalid={Boolean(errorFor("model"))}
                onChange={(event) => setModel(event.target.value)}
              />
              <Suggestions id={listId("model")} options={modelOptions} />
            </AuthBlock>

            <AuthBlock label="سنة الصنع" htmlFor="year" error={errorFor("year")}>
              <AuthInput
                id="year"
                name="year"
                inputMode="numeric"
                list={listId("year")}
                value={year}
                invalid={Boolean(errorFor("year"))}
                // **يقبل ٠١٢٣ كما يقبل 0123.** كان `\D` يمحو الأرقامَ العربية
                // كلَّها لأنها ليست `[0-9]` — فيبقى الحقلُ فارغاً وزرُّ الإرسال
                // معطَّلاً **بلا سبب مكتوب**، في تطبيقٍ كلُّ أرقامه عربية.
                onChange={(event) => setYear(toLatinDigits(event.target.value))}
              />
              <Suggestions id={listId("year")} options={yearOptions} />
            </AuthBlock>

            <AuthBlock label="اللون" htmlFor="color" error={errorFor("color")}>
              <AuthInput
                id="color"
                name="color"
                list={listId("color")}
                value={color}
                invalid={Boolean(errorFor("color"))}
                onChange={(event) => setColor(event.target.value)}
              />
              <Suggestions id={listId("color")} options={VEHICLE_COLORS} />
            </AuthBlock>

            <AuthBlock label="رقم اللوحة" htmlFor="plate_number" error={errorFor("plate_number")}>
              <AuthInput
                id="plate_number"
                name="plate_number"
                dir="ltr"
                value={plate}
                invalid={Boolean(errorFor("plate_number"))}
                onChange={(event) => setPlate(event.target.value)}
              />
            </AuthBlock>

            <AuthBlock label="الفئة" error={errorFor("category")}>
              <AuthChoice
                label="الفئة"
                value={category}
                options={categories.map((value) => ({ value, label: CATEGORY_LABEL[value] }))}
                onChange={setCategory}
              />
            </AuthBlock>

            <div className="t2-auth-push" />
            <div className="t2-auth-actions">
              <button type="submit" className="t2-button primary" disabled={!vehicleReady}>
                التالي
              </button>
            </div>
          </form>
        </AuthPage>
      </div>
    );
  }

  // بطاقةُ المركبة: ما كُتب في «المركبة» — **أو المسجَّلةُ لمن جاء ليكمل وثائقه**
  const registered = returning ? profile?.vehicles[0] ?? null : null;
  const car = vehicleReady
    ? { make: make.trim(), model: model.trim(), year: year.trim(), color: color.trim(), plate: plate.trim() }
    : registered
      ? {
          make: registered.make,
          model: registered.model,
          year: String(registered.year),
          color: registered.color,
          plate: registered.plate_number,
        }
      : null;

  return (
    <div ref={page} className="cap-auth cap-reg scr">
      <AuthPage>
        {/* الرجوعُ إلى «المركبة» — ومن جاء ليكمل وثائقه يعود إلى حيث جاء */}
        <RegisterTop step={3} onBack={returning ? goBack : () => setChosen("vehicle")} />

        <div className="t2-auth-form">
          {car ? (
            <div className="cap-car">
              <Icon name="directions_car" className="cap-car-icon" />
              <div className="cap-car-main">
                <div className="cap-car-name">
                  {car.make} {car.model} <span dir="ltr">{car.year}</span> · {car.color}
                </div>
                <div className="cap-car-plate" dir="ltr">
                  {car.plate}
                </div>
              </div>
              {returning ? null : (
                <button type="button" className="cap-car-edit" onClick={() => setChosen("vehicle")}>
                  تعديل
                </button>
              )}
            </div>
          ) : null}

          {section("الوثائق المطلوبة", PAPERS)}
          {section("صور المركبة", VEHICLE_PHOTOS)}

          {returning ? null : (
            <div className="cap-alias">
              <AuthBlock
                label="حساب CliQ للسحب"
                htmlFor="cliq-alias"
                error={errorFor("cliq_alias")}
                hint="عليه تستلم تحويلات السحب — تأكد من مطابقته لبنكك."
              >
                <AuthInput
                  id="cliq-alias"
                  name="cliq-alias"
                  dir="ltr"
                  value={alias}
                  invalid={Boolean(errorFor("cliq_alias"))}
                  onChange={(event) => setAlias(event.target.value)}
                />
              </AuthBlock>
            </div>
          )}

          {error ? (
            <div className="t2-auth-banner" role="alert">
              <Icon name="error" />
              <span>{error}</span>
            </div>
          ) : null}

          <div className="t2-auth-push" />

          {returning ? null : (
            <>
              <div className="t2-auth-actions">
                <button
                  type="button"
                  className="t2-button primary"
                  disabled={busy || !vehicleReady || missing.length > 0}
                  onClick={() => void submit()}
                >
                  {busy ? "لحظة…" : "إرسال للمراجعة"}
                </button>
              </div>
              <p className="cap-after">
                {missing.length > 0
                  ? "أكمل الوثائق الناقصة ليتفعّل الإرسال."
                  : "لا يُعتمد الكبتن قبل مراجعة الإدارة للمستندات."}
              </p>
            </>
          )}
        </div>
      </AuthPage>
    </div>
  );
}
