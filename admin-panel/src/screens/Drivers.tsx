/** السائقون واعتماد الوثائق — SPEC القسم 13/2، و`DESIGN.md` §3.3/3.5.
 *
 * **الشاشة التي تفتح باب العمل على المنصة.** كبتنٌ لا يُعتمد لا يستقبل طلباً،
 * ولا يُعتمد إلا بحارسَين تفرضهما الخلفية ولا تفرضهما هذه الشاشة:
 *
 * 1. **رقمٌ مُثبت** مهما كان مفتاح التحقق — رقمُه هو ما تصله عليه حوالات كليك.
 * 2. **المستنداتُ المطلوبة الثلاثة مقبولة** — لا رخصةٌ ناقصة ولا هويةٌ معلّقة.
 *
 * ولذلك يُعرض الحارسان **قبل** زرّ الاعتماد لا بعد أن يرتدّ بخطأ: الصفُّ يقول
 * كم مستنداً ينتظر وأيُّها ناقص، والدرجُ يعطّل «اعتماد» ويكتب سببَ التعطيل.
 * زرٌّ يعمل ثم يرتدّ برسالةٍ يجعل المشرف يجرّب؛ وزرٌّ معطّلٌ يقول لماذا يجعله
 * يُصلح.
 *
 * **والرفضُ يوجب سبباً مكتوباً** يصل صاحبه في الإشعار (المرحلة 9-ب): كبتنٌ
 * يعرف أن رخصته رُفضت ولا يعرف لماذا يعيد رفع الصورة نفسها ويبقى ينتظر.
 *
 * **والقرار لـ admin وحده** (القسم 13/8) — والحمايةُ في الخلفية؛ ما تخفيه
 * الشاشة عن `support` راحةٌ لا حماية.
 *
 * **وتوثيقُ الجنس بابٌ ثانٍ في نفس الدرج** (المرحلة 10-ج). الخلفية تملكه منذ
 * تلك المرحلة (`PUT /admin/drivers/{id}/gender` و`?gender_verified=false`)
 * ولم يكن له في اللوحة زرٌّ — وقاعدةٌ بلا باب لا تُستعمل. وثلاثة أشياء تجعله
 * ما هو:
 *
 * - **فرزُه محورٌ مستقل عن الحالة** فلا يُدسّ في حبّات الحالة: «معتمدون» و«بلا
 *   جنسٍ مثبت» سؤالان يُسألان معاً لا بديلين. ولذلك مفتاحٌ بجانب الحبّات.
 * - **الجنسُ عمودٌ في القائمة** لا حقلٌ يُكتشف بفتح كل ملف: المتراكم الذي
 *   يبقى `women_service_enabled` مطفأً حتى يُفرَّغ لا يُفرَّغ إن لم يُرَ.
 * - **والحفظُ يعيد قراءة القائمة**: ردُّ المسار `DriverOut` والجنسُ عمودٌ على
 *   `users`، فلا يحمله الردُّ ولا تخمّنه الشاشة.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  activateDriver,
  approveDriver,
  getDriverDocuments,
  listDrivers,
  rejectDriver,
  reviewDocument,
  setDriverGender,
  suspendDriver,
} from "@/api/endpoints";
import type {
  AdminDriverRow,
  DocumentType,
  DriverDocuments,
  DriverStatus,
  Gender,
  GenderPreference,
} from "@/api/types";
import { Deactivations } from "@/components/Deactivations";
import { Shell } from "@/components/Shell";
import { Pills, Table } from "@/components/Table";
import { Button } from "@/components/ui/Button";
import { Checkbox, Field } from "@/components/ui/Field";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { useCountry } from "@/lib/country";
import { useSession } from "@/lib/session";
import { arabicDigits, cn } from "@/lib/utils";

const STATUS_LABEL: Record<DriverStatus, string> = {
  pending: "بانتظار الاعتماد",
  approved: "معتمد",
  rejected: "مرفوض",
  suspended: "موقوف",
};

const STATUS_TONE: Record<DriverStatus, string> = {
  pending: "text-warn",
  approved: "text-ok",
  rejected: "text-danger",
  suspended: "text-danger",
};

const DOC_LABEL: Record<DocumentType, string> = {
  driving_license: "رخصة القيادة",
  national_id: "الهوية الشخصية",
  vehicle_registration: "رخصة المركبة",
  vehicle_photo: "صورة المركبة (قديم)",
  vehicle_front: "المركبة من الأمام",
  vehicle_back: "المركبة من الخلف",
  vehicle_side_right: "الجانب الأيمن",
  vehicle_side_left: "الجانب الأيسر",
  vehicle_interior: "من الداخل",
  vehicle_plate: "لوحة المركبة",
};

const GENDER_LABEL: Record<Gender, string> = {
  male: "ذكر",
  female: "أنثى",
};

/** تفضيلُ الكبتن **دائمٌ لا لكل رحلة**، ويفسّر جفافَ الطلبات عن حسابٍ قيّد نفسه. */
const PREFERENCE_LABEL: Record<GenderPreference, string> = {
  any: "يقبل كل الركاب",
  male: "لا يقلّ إلا الرجال",
  female: "لا تقلّ إلا النساء",
};

const COLUMNS = "1.6fr 1.1fr 0.9fr 1fr 0.8fr 0.6fr 1.2fr";

export function DriversScreen() {
  const { country } = useCountry();
  const { isAdmin } = useSession();

  const [filter, setFilter] = useState<DriverStatus | "all">("pending");
  // محورٌ ثانٍ مستقل عن الحالة — لا حبّةٌ سادسة بينها: «معتمدون» و«بلا جنسٍ
  // مثبت» سؤالان يُسألان معاً، وحبّةٌ واحدة تجعلهما بديلين
  const [unverifiedGender, setUnverifiedGender] = useState(false);
  const [rows, setRows] = useState<AdminDriverRow[] | null>(null);
  const [open, setOpen] = useState<AdminDriverRow | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRows(null);
    setRows(
      await listDrivers({
        country_code: country,
        status: filter === "all" ? undefined : filter,
        gender_verified: unverifiedGender ? false : undefined,
      }),
    );
  }, [country, filter, unverifiedGender]);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة القائمة",
      ),
    );
  }, [load]);

  return (
    <Shell
      title="السائقون واعتماد الوثائق"
      subtitle="لا يعمل كبتنٌ قبل المراجعة — والاعتماد يشترط رقماً مُثبتاً ومستنداتٍ مقبولة"
    >
      <Pills
        value={filter}
        onPick={(key) => setFilter(key)}
        options={[
          { key: "pending", label: "بانتظار الاعتماد" },
          { key: "approved", label: "معتمدون" },
          { key: "suspended", label: "موقوفون" },
          { key: "rejected", label: "مرفوضون" },
          { key: "all", label: "الكل" },
        ]}
      />

      <div className="mb-14 max-w-prose">
        <Checkbox checked={unverifiedGender} onChange={setUnverifiedGender}>
          <span className="block text-12.5 font-semibold text-ink">
            من لم يُثبَّت جنسُه بعد
          </span>
          <span className="block text-11 leading-note text-muted">
            المتراكمُ الذي تبقى الخدمة النسائية مطفأةً حتى يُفرَّغ — تشغيلُها
            قبله يعني خدمةً بلا سائقاتٍ يمكن ترشيحُهنّ.
          </span>
        </Checkbox>
      </div>

      <ErrorNote message={error} />
      <SuccessNote message={done} />

      <div className="mt-12">
        <Table
          columns={COLUMNS}
          headers={[
            "السائق",
            "الهاتف",
            "الحالة",
            "الوثائق",
            "الجنس",
            "التقييم",
            "",
          ]}
          rows={rows}
          keyOf={(row) => row.driver_id}
          empty={{
            title: "لا سائقين في هذه الحال",
            hint: "بدّل الفلترة أو الدولة من الرأس.",
          }}
          render={(row) => (
            <>
              <span className="flex items-center gap-9">
                <span className="flex size-30 flex-none items-center justify-center rounded-full border border-line bg-surface-2 text-11 font-bold text-ink">
                  {row.name.trim().slice(0, 1)}
                </span>
                <span className="min-w-0">
                  <span className="block truncate font-semibold text-ink">
                    {row.name}
                  </span>
                  {!row.phone_verified ? (
                    <span className="block text-10.5 text-danger">
                      رقمٌ غير مُثبت — لا يُعتمد
                    </span>
                  ) : null}
                </span>
              </span>

              <span dir="ltr" className="text-start text-muted">
                {row.phone}
              </span>

              <span className={cn("font-semibold", STATUS_TONE[row.status])}>
                {STATUS_LABEL[row.status]}
              </span>

              <span className="text-muted">
                {row.documents_pending > 0 ? (
                  <span className="text-warn">
                    {arabicDigits(String(row.documents_pending))} بانتظار
                    المراجعة
                  </span>
                ) : row.missing_required.length > 0 ? (
                  <span className="text-danger">
                    ينقص {arabicDigits(String(row.missing_required.length))}
                  </span>
                ) : (
                  <span className="text-ok">مكتملة</span>
                )}
              </span>

              {/* المطابقةُ تقرأ المختوم وحده، فغيرُ المختوم «لم يُثبَّت» لا
                  «ذكر» — عرضُ قيمةٍ بلا ختمٍ يجعلها تبدو معتبَرة وهي ليست */}
              <span>
                {row.gender_verified && row.gender ? (
                  <span className="text-ink">{GENDER_LABEL[row.gender]}</span>
                ) : (
                  <span className="text-warn">لم يُثبَّت</span>
                )}
              </span>

              <span className="text-ink">
                {row.rating_avg === "0.00"
                  ? "—"
                  : `★ ${arabicDigits(row.rating_avg)}`}
              </span>

              <span className="flex justify-end">
                <button
                  type="button"
                  onClick={() => setOpen(row)}
                  className="text-11.5 font-semibold text-ink underline"
                >
                  الوثائق والقرار
                </button>
              </span>
            </>
          )}
        />
      </div>

      {/* **طلباتُ إلغاء التفعيل تحت قائمة الكباتن** (البند ١٣): هنا يُقرأ حالُ
          الكبتن أصلاً، وقرارٌ يُخرجه من التوزيع يسكن حيث تُقرأ حالتُه — لا في
          «المالية» رغم أنه يُطلق مالاً محتجَزاً */}
      <Deactivations onError={setError} />

      {open ? (
        <DriverDrawer
          row={open}
          canDecide={isAdmin}
          onClose={() => setOpen(null)}
          onChanged={(message) => {
            setDone(message);
            setOpen(null);
            void load();
          }}
        />
      ) : null}
    </Shell>
  );
}

/** الدرج — `DESIGN.md` §3.5: 440px من حافة البداية، بوثائقَ ثم قرار. */
function DriverDrawer({
  row,
  canDecide,
  onClose,
  onChanged,
}: {
  row: AdminDriverRow;
  canDecide: boolean;
  onClose: () => void;
  onChanged: (message: string) => void;
}) {
  const [docs, setDocs] = useState<DriverDocuments | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reason, setReason] = useState("");

  const load = useCallback(async () => {
    setDocs(await getDriverDocuments(row.driver_id));
  }, [row.driver_id]);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة الوثائق",
      ),
    );
  }, [load]);

  async function run(action: () => Promise<unknown>, message: string) {
    setBusy(true);
    setError(null);
    try {
      await action();
      onChanged(message);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر التنفيذ");
      setBusy(false);
    }
  }

  // الحارسان كما تفرضهما الخلفية — يُقرآن هنا ليُعرض سببُ التعطيل لا ليُستبدلا
  const blockers = [
    !row.phone_verified ? "رقمه غير مُثبت" : null,
    row.missing_required.length > 0
      ? `مستندات لم تُقبل: ${row.missing_required.map((type) => DOC_LABEL[type]).join("، ")}`
      : null,
  ].filter(Boolean) as string[];

  return (
    <div className="fixed inset-0 z-50 bg-dim" onClick={onClose}>
      <div
        className="scr absolute bottom-0 start-0 top-0 w-drawer max-w-full animate-slidein border-e border-line bg-surface p-22"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-18 flex items-start gap-12">
          <span className="flex size-48 flex-none items-center justify-center rounded-full border border-line bg-surface-2 text-16 font-bold text-ink">
            {row.name.trim().slice(0, 1)}
          </span>
          <div className="flex-1">
            <div className="text-16 font-bold text-ink">{row.name}</div>
            <div dir="ltr" className="text-12 text-muted">
              {row.phone}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="إغلاق"
            className="text-18 text-muted"
          >
            ✕
          </button>
        </div>

        <h3 className="mb-10 text-13 font-bold text-muted">الوثائق</h3>
        {docs === null ? (
          <Spinner className="mx-auto" />
        ) : docs.documents.length === 0 ? (
          <p className="text-12.5 leading-note text-muted">
            لم يرفع أيّ مستند بعد.
          </p>
        ) : (
          <ul className="flex flex-col gap-9">
            {docs.documents.map((document) => (
              <li
                key={document.id}
                className="rounded-14 border border-line bg-surface-2 px-14 py-12"
              >
                <div className="flex items-center gap-10">
                  <span className="flex-1 text-13 font-semibold text-ink">
                    {DOC_LABEL[document.doc_type]}
                  </span>
                  <span
                    className={cn(
                      "text-11.5 font-bold",
                      document.review_status === "approved"
                        ? "text-ok"
                        : document.review_status === "rejected"
                          ? "text-danger"
                          : "text-warn",
                    )}
                  >
                    {document.review_status === "approved"
                      ? "مقبولة"
                      : document.review_status === "rejected"
                        ? "مرفوضة"
                        : "بانتظار المراجعة"}
                  </span>
                </div>
                {document.review_note ? (
                  <p className="mt-6 text-11 leading-snug text-danger">
                    {document.review_note}
                  </p>
                ) : null}

                {canDecide ? (
                  <div className="mt-10 flex gap-8">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        void run(
                          () =>
                            reviewDocument(
                              row.driver_id,
                              document.id,
                              true,
                            ).then(load),
                          "اعتُمدت الوثيقة ✓",
                        )
                      }
                      className="flex-1 rounded-10 border border-line py-8 text-11.5 font-semibold text-ok disabled:opacity-60"
                    >
                      اعتماد
                    </button>
                    <button
                      type="button"
                      disabled={busy || reason.trim().length < 3}
                      onClick={() =>
                        void run(
                          () =>
                            reviewDocument(
                              row.driver_id,
                              document.id,
                              false,
                              reason.trim(),
                            ).then(load),
                          "رُفضت الوثيقة — أُبلغ السائق",
                        )
                      }
                      className="flex-1 rounded-10 border border-line py-8 text-11.5 font-semibold text-danger disabled:opacity-60"
                    >
                      رفض
                    </button>
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}

        <h3 className="mb-10 mt-18 text-13 font-bold text-muted">
          توثيق الجنس
        </h3>
        <div className="rounded-14 border border-line bg-surface-2 px-14 py-12">
          <div className="flex items-center gap-10">
            <span className="flex-1 text-13 font-semibold text-ink">
              {row.gender_verified && row.gender
                ? `مُثبت — ${GENDER_LABEL[row.gender]}`
                : "لم يُثبَّت بعد"}
            </span>
            <span
              className={cn(
                "text-11.5 font-bold",
                row.gender_verified ? "text-ok" : "text-warn",
              )}
            >
              {row.gender_verified ? "مختوم" : "بانتظار المشرف"}
            </span>
          </div>

          <p className="mt-6 text-11 leading-note text-muted">
            {PREFERENCE_LABEL[row.gender_preference]} — تفضيلٌ دائم يضبطه صاحبُ
            الحساب من تطبيقه.
          </p>

          {canDecide ? (
            <>
              <div className="mt-10 flex gap-8">
                {(["female", "male"] as Gender[]).map((value) => (
                  <button
                    key={value}
                    type="button"
                    disabled={busy}
                    onClick={() =>
                      void run(
                        () => setDriverGender(row.driver_id, value),
                        `ثُبّت الجنس: ${GENDER_LABEL[value]}`,
                      )
                    }
                    className={cn(
                      "flex-1 rounded-10 border py-8 text-11.5 font-semibold disabled:opacity-60",
                      row.gender_verified && row.gender === value
                        ? "border-ink text-ink"
                        : "border-line text-muted",
                    )}
                  >
                    {GENDER_LABEL[value]}
                  </button>
                ))}
              </div>
              <p className="mt-8 text-11 leading-note text-muted">
                يُقرأ من الهوية المرفوعة أعلاه، لا من قول صاحبه: بلا ختمِ مشرفٍ
                يصير بلوغُ صفة «سائقة للنساء» كتابةَ كلمةٍ في حقل. والضبطُ لا
                يعيد دورة اعتماد — الوثائق مراجَعةٌ أصلاً.
              </p>
            </>
          ) : (
            <p className="mt-8 text-11 leading-note text-muted">
              الضبطُ لـ admin وحده — إعلانُ جنس الكبتن يقيّد أمان غيره
              (القسم 13/8).
            </p>
          )}
        </div>

        {canDecide ? (
          <div className="mt-14">
            <Field
              label="سبب الرفض أو الإيقاف"
              placeholder="يصل نصُّه إلى السائق"
              value={reason}
              maxLength={255}
              onChange={(event) => setReason(event.target.value)}
            />
            <p className="mt-6 text-11 leading-note text-muted">
              الرفضُ بلا سببٍ يجعل السائق يعيد رفع الصورة نفسها وينتظر بلا
              نهاية.
            </p>
          </div>
        ) : null}

        <ErrorNote message={error} />

        {canDecide ? (
          <div className="mt-16 flex flex-col gap-9">
            {row.status !== "approved" ? (
              <>
                {blockers.length > 0 ? (
                  <p className="rounded-12 border border-warn bg-surface-2 px-13 py-11 text-11.5 leading-note text-muted">
                    لا يمكن الاعتماد بعد: {blockers.join(" · ")}
                  </p>
                ) : null}
                <Button
                  size="md"
                  disabled={busy || blockers.length > 0}
                  onClick={() =>
                    void run(
                      () =>
                        row.status === "suspended"
                          ? activateDriver(row.driver_id)
                          : approveDriver(row.driver_id),
                      "اعتُمد السائق — صار يستقبل الطلبات",
                    )
                  }
                >
                  {row.status === "suspended" ? "إعادة التفعيل" : "اعتماد"}
                </Button>
              </>
            ) : null}

            {row.status === "approved" || row.status === "pending" ? (
              <Button
                size="md"
                variant="secondary"
                className="border-danger text-danger"
                disabled={busy || reason.trim().length < 3}
                onClick={() =>
                  void run(
                    () =>
                      row.status === "approved"
                        ? suspendDriver(row.driver_id, reason.trim())
                        : rejectDriver(row.driver_id),
                    row.status === "approved"
                      ? "أُوقف السائق"
                      : "رُفض طلب الانضمام",
                  )
                }
              >
                {row.status === "approved" ? "إيقاف" : "رفض الطلب"}
              </Button>
            ) : null}
          </div>
        ) : (
          <p className="mt-16 text-11.5 leading-note text-muted">
            القرارُ لـ admin وحده — مراجعةٌ تفتح باب العمل على المنصة ليست إجراء
            دعمٍ فني (القسم 13/8).
          </p>
        )}
      </div>
    </div>
  );
}
