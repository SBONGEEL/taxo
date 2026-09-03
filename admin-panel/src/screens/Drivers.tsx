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
  driverDocumentBlob,
  getDriverDocuments,
  listDrivers,
  rejectDriver,
  reviewDocument,
  setAdvanceCap,
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
import { Advances } from "@/components/Advances";
import {
  AccountSection,
  ChargesSection,
  ControlsSection,
  RidesSection,
  WalletSection,
} from "@/components/profile/Sections";
import {
  ActiveRideSection,
  MoneyOwedSection,
  SubscriptionSection,
  VehiclesSection,
} from "@/components/profile/DriverSections";
import { DriverDebts } from "@/components/DriverDebts";
import { Deactivations } from "@/components/Deactivations";
import { Shell } from "@/components/Shell";
import { Pills, Table, TableSearch } from "@/components/Table";
import { Button } from "@/components/ui/Button";
import { Checkbox, Field } from "@/components/ui/Field";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { useCountry } from "@/lib/country";
import { FormErrors, useFormError } from "@/lib/form-errors";
import { NO_RESULTS, useSearch } from "@/lib/search";
import { useSession } from "@/lib/session";
import { digits, cn } from "@/lib/utils";

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
  profile_photo: "الصورة الشخصية",
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

/** معاينةُ وثيقةٍ داخل الدرج — **تُجلب بالمفتاح ثم تُعرض من `blob:`**.
 *
 * و`<img src>` لا يحمل ترويسةَ `Authorization`، والمسارُ يتحقق من الدور —
 * فالجلبُ يدويٌّ لا لأن الصورةَ خاصة فحسب، بل لأن البابَ لا يفتح بغير مفتاح.
 *
 * **ولا تُفتح إلا بطلب**: درجٌ فيه تسعُ وثائقَ يجلبها كلَّها عند الفتح يحمّل
 * تسعَ صورٍ لا ينظر المشرفُ إلى أكثرها. **ومن فتح يغلق** — `revokeObjectURL`
 * عند الإغلاق، وإلا بقيت الوثائقُ في ذاكرة التبويب حتى يُغلق.
 */
/** معاينةُ الوثيقة، **ومعها حقلُ التاريخ عائماً فوقها** (البند ب).
 *
 * **وموضعُه فوق الصورة لا تحتها**: المشرفُ يقارن رقماً مكتوباً على الورقة برقمٍ
 * في خانة، **وعينُه تنتقل بينهما**. وخانةٌ تحت صورةٍ بارتفاع ١٧٠ تعني أن أحدَهما
 * خارج مجال النظر حين يُقرأ الآخر — فيُحفظ الرقمُ في الذاكرة ويُكتب، وهو بعينه
 * ما يُخطئ فيه الإنسان.
 */
function DocumentPreview({
  driverId,
  documentId,
  expiry,
  onExpiryChange,
}: {
  driverId: string;
  documentId: string;
  expiry: string;
  onExpiryChange: (value: string) => void;
}) {
  const [url, setUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [url]);

  if (url) {
    return (
      <div className="mt-10">
        <div className="relative">
          <img
            src={url}
            alt="الوثيقة"
            className="max-h-170 w-full rounded-12 border border-line object-contain"
          />
          {/* عائمٌ على الحافة العليا — يُقرأ مع الورقة في نظرةٍ واحدة */}
          <label className="absolute inset-x-8 top-8 flex items-center gap-8 rounded-10 bg-dim px-10 py-6 backdrop-blur">
            <span className="shrink-0 text-11 font-semibold text-inv">
              تنتهي في
            </span>
            <input
              type="date"
              value={expiry}
              onChange={(event) => onExpiryChange(event.target.value)}
              className="fld flex-1 py-4 text-11.5"
            />
          </label>
        </div>
        <button
          type="button"
          onClick={() => {
            URL.revokeObjectURL(url);
            setUrl(null);
          }}
          className="mt-6 text-11.5 font-semibold text-muted"
        >
          إخفاء
        </button>
      </div>
    );
  }

  return (
    <div className="mt-10">
      <button
        type="button"
        disabled={busy}
        onClick={() => {
          setBusy(true);
          setFailed(null);
          driverDocumentBlob(driverId, documentId)
            .then(setUrl)
            .catch((caught: Error) => setFailed(caught.message))
            .finally(() => setBusy(false));
        }}
        className="text-11.5 font-semibold text-ink underline disabled:opacity-60"
      >
        {busy ? "جارٍ الفتح…" : "اعرض الوثيقة"}
      </button>
      {failed ? (
        <p className="mt-4 text-11 text-danger">{failed}</p>
      ) : null}
    </div>
  );
}

/** سقفُ سلفةِ كبتنٍ بعينه — **بابٌ بلا زرّ حتى 2026-08-19** (قرارُ المالك).
 *
 * والعلّةُ أنه مال **يُقرَض**: سقفٌ عامٌّ بلا سقفٍ فرديٍّ يعني كبتناً واحداً
 * يستنزف ما لم يُقصد له، ولا سبيلَ لتضييقه عليه وحدَه.
 *
 * **ولا يرفع السقفَ العام أبداً، وذلك بالبناء لا بفحصٍ عند الكتابة**:
 * `advances.cap_for` تعيد `min(computed, override)` — فالتخصيصُ يخفض ولا يرفع.
 * وفحصٌ عند الكتابة كان سيكون خاطئاً: المحسوبُ **ينمو** بما سدَّده الكبتن، فرقمٌ
 * يتجاوزه اليومَ قد يقلّ عنه بعد شهر.
 *
 * **وثلاثُ حالاتٍ لا اثنتان**: فارغٌ = لا تخصيص (المحسوبُ وحدَه)، وصفرٌ = **منعٌ
 * من السلف**، ورقمٌ = سقفٌ أضيق. ورقمٌ واحدٌ لا يحمل الأولَيَن — درسُ أصفار
 * `wallet_settings`، فالشاشةُ تقولهما نصّاً.
 */
function AdvanceCap({
  row,
  canDecide,
  onChanged,
}: {
  row: AdminDriverRow;
  canDecide: boolean;
  onChanged: (message: string) => void;
}) {
  const [cap, setCap] = useState(row.advance_cap_override ?? "");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);

  const current =
    row.advance_cap_override === null
      ? "لا تخصيص — يُطبَّق المحسوبُ وحدَه"
      : Number(row.advance_cap_override) === 0
        ? "ممنوعٌ من السلف"
        : `سقفٌ خاصّ: ${digits(row.advance_cap_override)}`;

  return (
    <>
      <h3 className="mb-10 mt-18 text-13 font-bold text-muted">سقف السلفة</h3>
      <div className="rounded-14 border border-line bg-surface-2 px-14 py-12">
        <p className="text-13 font-semibold text-ink">{current}</p>
        <p className="mt-6 text-11 leading-note text-muted">
          <b className="text-ink">يخفض ولا يرفع</b>: السقفُ المطبَّق هو الأدنى بين
          المحسوب (من قيمة الاشتراك اليوميّ، ينمو بما سُدّد) وهذا. فارغٌ = لا
          تخصيص، و<b className="text-ink">صفرٌ = منعٌ من السلف</b>.
        </p>

        {canDecide ? (
          <>
            <div className="mt-10 grid gap-10">
              <Field
                label="السقف (فارغ = لا تخصيص)"
                dir="ltr"
                inputMode="decimal"
                value={cap}
                onChange={(event) =>
                  setCap(event.target.value.replace(/[^0-9.]/g, ""))
                }
              />
              <Field
                label="السبب (إلزاميّ — يدخل سجلّ التدقيق)"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            </div>
            {failed ? (
              <p className="mt-6 text-11 text-danger">{failed}</p>
            ) : null}
            <Button
              className="mt-10"
              size="sm"
              loading={busy}
              disabled={reason.trim().length < 3}
              onClick={() => {
                setBusy(true);
                setFailed(null);
                setAdvanceCap(row.driver_id, {
                  cap: cap.trim() === "" ? null : cap.trim(),
                  reason: reason.trim(),
                })
                  .then(() => {
                    setReason("");
                    onChanged("ضُبط سقفُ السلفة");
                  })
                  .catch((caught) =>
                    setFailed(
                      caught instanceof ApiError
                        ? caught.message
                        : "تعذّر الضبط",
                    ),
                  )
                  .finally(() => setBusy(false));
              }}
            >
              احفظ السقف
            </Button>
          </>
        ) : (
          <p className="mt-8 text-11 leading-note text-muted">
            الضبطُ لـ admin وحده — هذا مالٌ يُقرَض.
          </p>
        )}
      </div>
    </>
  );
}

export function DriversScreen() {
  const { country } = useCountry();
  const { isAdmin } = useSession();

  const [filter, setFilter] = useState<DriverStatus | "all">("pending");
  // محورٌ ثانٍ مستقل عن الحالة — لا حبّةٌ سادسة بينها: «معتمدون» و«بلا جنسٍ
  // مثبت» سؤالان يُسألان معاً، وحبّةٌ واحدة تجعلهما بديلين
  const [unverifiedGender, setUnverifiedGender] = useState(false);
  const [rows, setRows] = useState<AdminDriverRow[] | null>(null);
  const search = useSearch();
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
        // **من الخادم لا في المتصفح**: القائمةُ مرقَّمةٌ بخمسين، وبحثٌ محلّيٌّ
        // يقرأ الصفحةَ المعروضةَ وحدَها فيبدو معطوباً لمن يعرف أن الصفَّ موجود
        q: search.term,
      }),
    );
  }, [country, filter, unverifiedGender, search.term]);

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
          toolbar={
            <TableSearch
              value={search.text}
              onChange={search.setText}
              placeholder="ابحث باسم الكبتن أو رقمه…"
            />
          }
          searching={search.searching}
          noResults={NO_RESULTS}
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
                    {digits(String(row.documents_pending))} بانتظار
                    المراجعة
                  </span>
                ) : row.missing_required.length > 0 ? (
                  <span className="text-danger">
                    ينقص {digits(String(row.missing_required.length))}
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
                  : `★ ${digits(row.rating_avg)}`}
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
      <Advances onError={setError} />
      <DriverDebts onError={setError} />

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
          // **بتّةُ مستندٍ لا تُغلق الدرج** (عطبٌ مقيس 2026-08-25): للكبتن
          // ثلاثةُ مستنداتٍ مطلوبةٍ فأكثر، وإغلاقُ الدرج بعد كلِّ اعتمادٍ
          // يُجبر المشرفَ على فتحه ثلاثَ مرّاتٍ لكبتنٍ واحد. **وهو شكلُ سجلِّ
          // الرحلات نفسُه**: فعلٌ داخل سطحٍ يهدم السطحَ الذي يقف عليه فاعلُه.
          // والدرجُ يحمل تحميلَه الخاصّ (`getDriverDocuments`) فيُحدِّث نفسَه،
          // **والقائمةُ خلفَه تُحدَّث أيضاً** لأن حالَ الكبتن قد تتغيّر ببتّة.
          onDone={(message) => {
            setDone(message);
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
  onDone,
}: {
  row: AdminDriverRow;
  canDecide: boolean;
  onClose: () => void;
  onChanged: (message: string) => void;
  onDone: (message: string) => void;
}) {
  const [docs, setDocs] = useState<DriverDocuments | null>(null);
  const [busy, setBusy] = useState(false);
  const form = useFormError();
  const error = form.message;
  const setError = form.setMessage;
  const [reason, setReason] = useState("");
  // **تاريخُ كلِّ مستندٍ على حدة** (البند ب) — يُبتدأ ممّا أقرّه الكبتن ويُرسَل
  // مع البتّة. ومفتاحُه معرّفُ المستند لا نوعُه: الدرجُ يعرض المستنداتِ كلَّها.
  const [expiry, setExpiry] = useState<Record<string, string>>({});

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
      form.capture(caught, "تعذّر التنفيذ");
      setBusy(false);
    }
  }

  /** كـ`run` **ولا يُغلق الدرج** — لبتّةِ مستندٍ من عدّة مستندات. */
  async function runStay(action: () => Promise<unknown>, message: string) {
    setBusy(true);
    setError(null);
    try {
      await action();
      onDone(message);
    } catch (caught) {
      form.capture(caught, "تعذّر التنفيذ");
    } finally {
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
    <FormErrors value={form.field}>
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

        {/* **الملفُّ الشخصيُّ الكامل** (§37، البند ١): أقسامٌ تُفتح بطلبٍ
            وتقرأ **من بابِ كلِّ مفهوم** — لا بابٌ جامعٌ يصير مصدراً ثانياً
            (§5-ج: «الصفحةُ تقرأ ولا تحسب من جديد»). **وترتيبُها ترتيبُ
            القرار**: من هو، ثمّ بمَ يعمل، ثمّ ماذا عليه — والوثائقُ تحتها
            لأنها سببُ فتح هذا الدرج في أكثر الأحيان. */}
        <AccountSection userId={row.user_id} fallbackName={row.name} />
        {/* **الرحلةُ الجارية ثانيةً** (البند ٦، §39٫٦): هي أسرعُ ما يبلى في
            هذا الدرج — رصيدٌ ووثيقةٌ يبقيان إلى الغد، وموضعُه بعد دقيقةٍ خبرٌ
            آخر. **ولـ`admin` وحدَه**، فالقسمُ يختفي عن الدعم بنفسه */}
        <ActiveRideSection driverId={row.driver_id} />
        <VehiclesSection driverId={row.driver_id} />
        <SubscriptionSection driverId={row.driver_id} />
        <WalletSection userId={row.user_id} />
        <MoneyOwedSection driverId={row.driver_id} />
        <RidesSection side="driver" id={row.driver_id} />
        <ChargesSection userId={row.user_id} country={row.country_code} />
        {/* **البند ١١** (§39٫١١، §46): تصحيحُ البيانات ورسالةٌ فرديّة —
            **ومعها الحظرُ هنا وحدَه**: `POST /admin/users/{id}/block` بابٌ لم
            يكن يبلغه أحدٌ من درج الكبتن، فحسابُ كبتنٍ لا يُحظر من اللوحة
            البتّة (شاشةُ الركّاب تفرز `role=rider`، والمستخدمون يفرزون
            الموظّفين). ودرجُ الراكب يحمل زرَّه سلفاً فلا يُرسم له ثانٍ */}
        <ControlsSection
          userId={row.user_id}
          showBlock
          onChanged={(message) => onDone(message)}
        />

        <h3 className="mb-10 mt-18 text-13 font-bold text-muted">الوثائق</h3>
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

                {/* **ولا يُعتمد ما لا يُرى**: كان القرارُ يُتَّخذ على نوعِ
                    الوثيقة وحالها — رخصةٌ تُقبل ولا يراها أحد. والمسارُ مبنيٌّ
                    منذ 9-ب ولم يصل إليه زرٌّ قط. */}
                <DocumentPreview
                  driverId={row.driver_id}
                  documentId={document.id}
                  expiry={expiry[document.id] ?? document.expires_on ?? ""}
                  onExpiryChange={(value) =>
                    setExpiry((current) => ({ ...current, [document.id]: value }))
                  }
                />

                {/* **الأزرارُ للمنتظِر وحدَه**: `documents.review` يرفض ما بُتّ
                    فيه بـ409، فزرٌّ باقٍ على مستندٍ مقبولٍ زرٌّ يعمل ثم يرتدّ —
                    وهو ما يعلّم المشرفَ إعادةَ المحاولة بدل أن يقول له إن
                    القرار وقع. **وتغييرُ القرار بابُه رفعُ الكبتن من جديد**، لا
                    ضغطةٌ ثانيةٌ هنا. (وجدته المرحلةُ ١٣: تسعُ ضغطاتٍ على تسعة
                    مستندات أرسلت تسعَ مراجعاتٍ لمعرّفٍ واحدٍ كلُّها ٤٠٩) */}
                {canDecide && document.review_status === "pending" ? (
                  <div className="mt-10 flex gap-8">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        void runStay(
                          () =>
                            reviewDocument(
                              row.driver_id,
                              document.id,
                              true,
                              undefined,
                              expiry[document.id] ?? document.expires_on ?? undefined,
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
                        void runStay(
                          () =>
                            reviewDocument(
                              row.driver_id,
                              document.id,
                              false,
                              reason.trim(),
                              expiry[document.id] ?? document.expires_on ?? undefined,
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

        <AdvanceCap row={row} canDecide={canDecide} onChanged={onChanged} />

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
            name="reason"
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
    </FormErrors>
  );
}
