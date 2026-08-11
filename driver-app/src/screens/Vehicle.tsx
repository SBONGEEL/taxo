/** المركبة والمستندات — SPEC القسم 12/1، وشكلُها من `DESIGN.md` §5.3.
 *
 * **المركبةُ تُعرض ولا تُحرَّر**: النموذج يرسم حقولاً قابلةً للكتابة، ولا
 * منفذَ في الخلفية لتعديل مركبة — `POST /drivers/me/vehicles` يضيف فقط. وحقلٌ
 * يكتب فيه الكبتن ثم لا يُحفظ أسوأ من حقلٍ لا يوجد؛ ولو حُفظ لكان تغييرُ
 * اللوحة بعد الاعتماد تغييراً للمركبة التي رُوجعت أوراقُها، وذلك قرارُ
 * مراجعةٍ لا حقلُ نصّ (`FUTURE-FEATURES.md` بند 43).
 *
 * **والمستندُ يُستبدل، والاستبدالُ له ثمن**: رفعُ نوعٍ ثانيةً يستبدل صفّه
 * ويعيده `pending`، **ويعيد الكبتن المعتمد إلى «قيد المراجعة»** حتى تُراجَع
 * الوثيقة الجديدة (سياسة 9-ب في SPEC). فالشاشة تقول ذلك قبل الرفع لا بعده،
 * والخلفيةُ ترفض الاستبدال أثناء رحلةٍ جارية.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { listDocuments, uploadDocument } from "@/api/endpoints";
import type { DocumentType, DriverDocuments } from "@/api/types";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { useDriver } from "@/lib/driver";
import { arabicDigits, cn } from "@/lib/utils";

const DOC_LABEL: Record<DocumentType, string> = {
  driving_license: "رخصة القيادة",
  national_id: "الهوية الشخصية",
  vehicle_registration: "رخصة المركبة",
  vehicle_photo: "صورة المركبة",
};

const REVIEW_LABEL = {
  approved: { text: "مقبول", tone: "text-ok", dot: "bg-ok" },
  pending: { text: "قيد المراجعة", tone: "text-warn", dot: "bg-warn" },
  rejected: { text: "مرفوض", tone: "text-danger", dot: "bg-danger" },
} as const;

const CATEGORY_LABEL: Record<string, string> = {
  economy: "اقتصادي",
  comfort: "مريح",
};

export function VehicleScreen() {
  const navigate = useNavigate();
  const { profile, refresh } = useDriver();
  const [state, setState] = useState<DriverDocuments | null>(null);
  const [busy, setBusy] = useState<DocumentType | null>(null);
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
      const result = await uploadDocument(docType, file);
      await load();
      await refresh();
      setDone(
        result.approval_reverted
          ? "رُفع المستند — وحسابك عاد «قيد المراجعة» حتى تُراجَع الوثيقة"
          : "رُفع المستند — بانتظار المراجعة",
      );
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الرفع");
    } finally {
      setBusy(null);
    }
  }

  const vehicle = profile?.vehicles[0];
  const types: DocumentType[] = [
    "driving_license",
    "national_id",
    "vehicle_registration",
    "vehicle_photo",
  ];

  return (
    <div className="scr h-full bg-bg px-16 pb-12 pt-safe">
      <div className="mb-16 mt-6 flex items-center gap-10">
        <button
          type="button"
          onClick={() => navigate(-1)}
          aria-label="رجوع"
          className="text-18 text-muted"
        >
          →
        </button>
        <h1 className="text-20 font-bold text-ink">المركبة والمستندات</h1>
      </div>

      <section className="mb-12 rounded-16 border border-line bg-surface p-15">
        {vehicle ? (
          <>
            <div className="mb-11 flex items-baseline justify-between">
              <span className="text-15 font-bold text-ink">
                {vehicle.make} {vehicle.model}
              </span>
              <span className="text-12 text-muted">
                {CATEGORY_LABEL[vehicle.category] ?? vehicle.category}
              </span>
            </div>
            <Pair
              label="سنة الصنع"
              value={arabicDigits(String(vehicle.year))}
            />
            <Pair label="اللون" value={vehicle.color} />
            {/* اللوحةُ معرّفٌ مطبوعٌ على المركبة — تُعرض كما هي */}
            <Pair label="رقم اللوحة" value={vehicle.plate_number} ltr last />
            <p className="mt-11 text-11 leading-snug text-muted">
              تعديلُ بيانات المركبة يمر بالإدارة — أوراقُها مربوطةٌ باعتمادك.
            </p>
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
        className="mt-10 w-full rounded-12 border border-dashed border-line py-10 text-center text-12 font-semibold text-muted disabled:opacity-60"
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
