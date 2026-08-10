/** التسجيل — الخطوة ٣ من ٣: المركبة والمستندات (SPEC القسم 12/1).
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
import { cn } from "@/lib/utils";

const DOC_LABEL: Record<DocumentType, string> = {
  driving_license: "رخصة القيادة",
  national_id: "الهوية الشخصية",
  vehicle_registration: "رخصة المركبة والتأمين",
  vehicle_photo: "صور المركبة",
};

const CATEGORY_LABEL: Record<VehicleCategory, string> = {
  economy: "اقتصادي",
  comfort: "مريح",
};

const ORDER: DocumentType[] = [
  "driving_license",
  "national_id",
  "vehicle_registration",
  "vehicle_photo",
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
  const [uploading, setUploading] = useState<DocumentType | null>(null);
  const [error, setError] = useState<string | null>(null);
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
        setRequired(response.missing_required);
      })
      .catch(() => undefined);
  }, []);

  async function pick(docType: DocumentType, file: File | undefined) {
    if (!file) return;
    setUploading(docType);
    setError(null);
    try {
      await uploadDocument(docType, file);
      setUploaded((current) => new Set(current).add(docType));
      setRequired((current) => current.filter((item) => item !== docType));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر رفع الملف");
    } finally {
      setUploading(null);
    }
  }

  const missing = ORDER.filter(
    (doc) => required.includes(doc) && !uploaded.has(doc),
  );
  const vehicleReady =
    make.trim() && model.trim() && year.trim() && color.trim() && plate.trim();

  async function submit() {
    setBusy(true);
    setError(null);
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
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر إرسال الطلب",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthScreen className="px-26">
      <div className="text-12 text-muted">الخطوة ٣ من ٣</div>
      <h1 className="mb-4 text-22 font-bold text-ink">المركبة والمستندات</h1>
      <p className="mb-18 text-12.5 leading-snug text-muted">
        لا يُعتمد الكبتن قبل مراجعة الإدارة للمستندات.
      </p>

      <section className="mb-12 rounded-16 border border-line bg-surface p-15">
        <h2 className="mb-12 text-13.5 font-bold text-ink">المركبة</h2>
        <div className="mb-8 flex gap-8">
          <Field
            name="make"
            placeholder="الشركة"
            value={make}
            onChange={(event) => setMake(event.target.value)}
          />
          <Field
            name="model"
            placeholder="الطراز"
            value={model}
            onChange={(event) => setModel(event.target.value)}
          />
        </div>
        <div className="mb-8 flex gap-8">
          <Field
            name="year"
            inputMode="numeric"
            placeholder="سنة الصنع"
            value={year}
            onChange={(event) => setYear(event.target.value.replace(/\D/g, ""))}
          />
          <Field
            name="color"
            placeholder="اللون"
            value={color}
            onChange={(event) => setColor(event.target.value)}
          />
        </div>
        <Field
          name="plate"
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
                "flex-1 rounded-13 border p-11 text-13 font-semibold",
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

      <section className="rounded-16 border border-line bg-surface p-15">
        <h2 className="mb-12 text-13.5 font-bold text-ink">المستندات</h2>
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
                    "flex w-full items-center gap-12 rounded-13 border border-dashed p-13 text-start",
                    done ? "border-ok bg-surface-2" : "border-line",
                  )}
                >
                  <span className="block h-30 w-38 shrink-0 rounded-7 bg-stripe" />
                  <span className="flex-1 text-12.5 text-ink">
                    {DOC_LABEL[doc]}
                    {required.includes(doc) && !done ? (
                      <span className="text-muted"> · مطلوب</span>
                    ) : null}
                  </span>
                  <span
                    className={cn(
                      "text-11.5 font-bold",
                      done ? "text-ok" : "text-muted",
                    )}
                  >
                    {uploading === doc
                      ? "…"
                      : done
                        ? "تم الرفع ✓"
                        : "ارفع صورة"}
                  </span>
                </button>
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
