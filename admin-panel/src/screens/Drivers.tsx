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
import { useSearchParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import {
  activateDriver,
  approveDriver,
  clearDriverInspection,
  driverDocumentBlob,
  getDriverDocuments,
  listDrivers,
  passDriverInspection,
  rejectDriver,
  reviewDocument,
  scheduleDriverInspection,
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
import { PendingDeletions } from "@/components/PendingDeletions";
import { Shell } from "@/components/Shell";
import { Pills, Table, TableSearch } from "@/components/Table";
import { Badge } from "@/components/ui/Badge";
import type { Tone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Drawer } from "@/components/ui/Drawer";
import { Checkbox, Field, FieldError } from "@/components/ui/Field";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { useCountry } from "@/lib/country";
import { FormErrors, useFormError } from "@/lib/form-errors";
import { NO_RESULTS, useSearch } from "@/lib/search";
import { useSession } from "@/lib/session";
import { DISPLAY_LOCALE, digits, cn } from "@/lib/utils";
import { DateField, Icon } from "@/taxo2";

const STATUS_LABEL: Record<DriverStatus, string> = {
  pending: "بانتظار الاعتماد",
  approved: "معتمد",
  rejected: "مرفوض",
  suspended: "موقوف",
  // **و«ألغى تفعيله» لا «موقوف»**: الإيقافُ قرارُ إدارةٍ، وإلغاءُ التفعيل
  // **طلبُ الكبتن نفسِه** (`deactivation_requests`، البند ١٣) — واسمٌ واحدٌ
  // لهما يجعل المشرفَ يقرأ عقوبةً حيث لا عقوبة.
  deactivated: "ألغى تفعيله",
};

/** **الحالُ شارةٌ بنغمتها** (A05) — كانت نصّاً ملوَّناً. */
const STATUS_TONE: Record<DriverStatus, Tone> = {
  pending: "warn",
  approved: "ok",
  rejected: "danger",
  suspended: "danger",
  // **ولونُه محايدٌ لا خطر**: خروجٌ بطلبه لا عقوبةٌ عليه.
  deactivated: "muted",
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
  onSeen,
}: {
  driverId: string;
  documentId: string;
  expiry: string;
  onExpiryChange: (value: string) => void;
  /** **يقع حين تصل الورقةُ فعلاً لا حين يُضغط الزرّ** — والفرقُ هو المعنى:
   *  نداءٌ فشل ليس معاينة. */
  onSeen: () => void;
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
      <div className="ad-doc-preview">
        <img src={url} alt="الوثيقة" className="ad-doc-img" />
        {/* عائمٌ على الحافة العليا — يُقرأ مع الورقة في نظرةٍ واحدة */}
        <div className="ad-doc-expiry">
          <span className="ad-doc-expiry-label" aria-hidden="true">
            تنتهي في
          </span>
          {/* **حقلُ التاريخ من نظام التصميم لا الأصليُّ عارياً** (§٦٢-ب/١٥): الأصليُّ في صفحةٍ عربيّةٍ يرسم «يوم/شهر/سنة»
              بحروفٍ معكوسة — **وقِيس هنا كذلك ولو بـ`dir="ltr"`** («ةنس/رهش/موي» في لقطة الدرج). **والقيمةُ والحدثُ كما
              كانا**: نصُّ `YYYY-MM-DD` يُرسل مع البتّة، ومنتقي النظام نفسُه يُفتح */}
          <DateField
            value={expiry}
            onChange={onExpiryChange}
            label="تنتهي في"
          />
        </div>
        <button
          type="button"
          onClick={() => {
            URL.revokeObjectURL(url);
            setUrl(null);
          }}
          className="ad-doc-hide"
        >
          إخفاء
        </button>
      </div>
    );
  }

  return (
    <div>
      <button
        type="button"
        disabled={busy}
        onClick={() => {
          setBusy(true);
          setFailed(null);
          driverDocumentBlob(driverId, documentId)
            .then((blob) => {
              setUrl(blob);
              onSeen();
            })
            .catch((caught: Error) => setFailed(caught.message))
            .finally(() => setBusy(false));
        }}
        className="ad-doc-view"
      >
        <Icon name="visibility" />
        {busy ? "جارٍ الفتح…" : "اعرض الوثيقة"}
      </button>
      {failed ? <p className="ad-doc-fail">{failed}</p> : null}
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
      <h3 className="ad-dh">سقف السلفة</h3>
      <div className="ad-box">
        <p className="ad-box-state">{current}</p>
        <p className="ad-box-hint">
          <b>يخفض ولا يرفع</b>: السقفُ المطبَّق هو الأدنى بين المحسوب (من قيمة
          الاشتراك اليوميّ، ينمو بما سُدّد) وهذا. فارغٌ = لا تخصيص، و
          <b>صفرٌ = منعٌ من السلف</b>.
        </p>

        {canDecide ? (
          <>
            <div className="ad-box-fields">
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
            {failed ? <FieldError message={failed} /> : null}
            <div className="ad-box-actions">
              <Button
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
            </div>
          </>
        ) : (
          <p className="ad-box-hint">الضبطُ لـ admin وحده — هذا مالٌ يُقرَض.</p>
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

  // **يفتح ما يقوله العنوان** — وجهةُ البحث العامّ (§39٫١٢٫٤).
  //
  // **ولا بابَ يقرأ كبتناً واحداً**: `AdminDriverRow` يُبنى في القائمة بعدِّ
  // مستنداتٍ ومطلوبٍ ناقص، **ونسخُ ذلك في بابٍ ثانٍ يجعل صفَّين لشيءٍ واحد**
  // يفترقان أوّلَ تعديل (الشكلُ الثامن). **فيُضيَّق البحثُ برقمه** — يأتي به
  // البحثُ العامُّ في `q` — **ثمّ يُفتح صفُّه بمعرّفه**.
  const [params, setParams] = useSearchParams();
  const wanted = params.get("open");
  const seeded = params.get("q");
  useEffect(() => {
    // **واللسانُ يُفتح على «الكلّ» حين تأتي وجهة** (عطبٌ أمسكته جولةُ متصفّح
    // ٢٠٢٦-٠٩-٠٤): الشاشةُ تفتح على «بانتظار الاعتماد»، **فكبتنٌ معتمَدٌ
    // يُقفز إليه لا يظهر في القائمة ولا يُفتح درجُه** — والعنوانُ يقول «افتح»
    // والشاشةُ تقول «لا نتائج لبحثك». **ولا يُقاس هذا من الشيفرة**: كلُّ سطرٍ
    // فيها صحيحٌ منفرداً.
    if (wanted !== null) setFilter("all");
    if (seeded) search.setText(seeded);
    // **مرّةً واحدةً عند الوصول**: إعادةُ الزرع في كلِّ رسمٍ تمحو ما يكتبه
    // المشرفُ بعدها تحت إصبعه
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seeded, wanted]);

  useEffect(() => {
    if (wanted === null || rows === null) return;
    const row = rows.find((candidate) => candidate.driver_id === wanted);
    if (row === undefined) return;
    setOpen(row);
    params.delete("open");
    setParams(params, { replace: true });
  }, [wanted, rows, params, setParams]);
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
      <div className="ad-filters">
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

        <div className="ad-toggle-card">
          <Checkbox checked={unverifiedGender} onChange={setUnverifiedGender}>
            <span className="ad-toggle-title">من لم يُثبَّت جنسُه بعد</span>
            <span className="ad-toggle-hint">
              المتراكمُ الذي تبقى الخدمة النسائية مطفأةً حتى يُفرَّغ — تشغيلُها
              قبله يعني خدمةً بلا سائقاتٍ يمكن ترشيحُهنّ.
            </span>
          </Checkbox>
        </div>
      </div>

      <ErrorNote message={error} />
      <SuccessNote message={done} />

      <div className={error || done ? "mt-12" : undefined}>
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
              <span className="ad-person">
                <span className="ad-person-avatar" aria-hidden="true">
                  {row.name.trim().slice(0, 1)}
                </span>
                <span className="ad-person-text">
                  <span className="ad-person-name">{row.name}</span>
                  {!row.phone_verified ? (
                    <span className="ad-person-note">
                      رقمٌ غير مُثبت — لا يُعتمد
                    </span>
                  ) : null}
                </span>
              </span>

              <span dir="ltr" className="ad-ltr ad-tone-muted">
                {row.phone}
              </span>

              <span>
                <Badge tone={STATUS_TONE[row.status]}>
                  {STATUS_LABEL[row.status]}
                </Badge>
              </span>

              <span>
                {row.documents_pending > 0 ? (
                  <span className="ad-tone-warn">
                    {digits(String(row.documents_pending))} بانتظار
                    المراجعة
                  </span>
                ) : row.missing_required.length > 0 ? (
                  <span className="ad-tone-danger">
                    ينقص {digits(String(row.missing_required.length))}
                  </span>
                ) : (
                  <span className="ad-tone-ok">مكتملة</span>
                )}
              </span>

              {/* المطابقةُ تقرأ المختوم وحده، فغيرُ المختوم «لم يُثبَّت» لا
                  «ذكر» — عرضُ قيمةٍ بلا ختمٍ يجعلها تبدو معتبَرة وهي ليست */}
              <span>
                {row.gender_verified && row.gender ? (
                  <span>{GENDER_LABEL[row.gender]}</span>
                ) : (
                  <span className="ad-tone-warn">لم يُثبَّت</span>
                )}
              </span>

              <span className="ad-tone-muted">
                {row.rating_avg === "0.00" ? (
                  "—"
                ) : (
                  <span className="ad-rating">
                    <Icon name="star" fill />
                    {digits(row.rating_avg)}
                  </span>
                )}
              </span>

              <span className="ad-row-end">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => setOpen(row)}
                >
                  الوثائق والقرار
                </Button>
              </span>
            </>
          )}
        />
      </div>

      {/* **طلباتُ إلغاء التفعيل تحت قائمة الكباتن** (البند ١٣): هنا يُقرأ حالُ
          الكبتن أصلاً، وقرارٌ يُخرجه من التوزيع يسكن حيث تُقرأ حالتُه — لا في
          «المالية» رغم أنه يُطلق مالاً محتجَزاً */}
      <div className="ad-section-gap" />
      <PendingDeletions onError={setError} />
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

  /** **ما فُتحت ورقتُه في هذه الجلسة** — ومنه وحدَه يُبنى الفعلُ الجماعيّ.
   *
   * **العلّةُ قاعدةٌ مكتوبةٌ في هذا الملفّ**: «**ولا يُعتمد ما لا يُرى**» —
   * كان القرارُ يُتَّخذ على نوع الوثيقة وحالها، **فرخصةٌ تُقبل ولا يراها
   * أحد**. **وزرُّ «اعتمِد الكلّ» يعيد ذلك العطبَ بضغطةٍ واحدة**، فيُقصر على
   * ما رآه المشرفُ بعينه.
   *
   * **وهو تضييقٌ لنصِّ §39٫١٢٫٣ لا مخالفةٌ له**: «أفعالٌ جماعيةٌ **حيث تكون
   * آمنة**» — والأمانُ هنا أن يكون القرارُ على ورقةٍ رُئيت.
   */
  const [seen, setSeen] = useState<Set<string>>(new Set());

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
    <Drawer
      name={row.name}
      phone={row.phone}
      badges={
        <Badge tone={STATUS_TONE[row.status]}>{STATUS_LABEL[row.status]}</Badge>
      }
      onClose={onClose}
    >
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
        {/* **وزرُّ التجميد هنا** (1-أ/6): التجميدُ صار صفةَ محفظةٍ، وزرُّ
            درج الراكب يجمّد محفظةَ الراكب وحدَها — فبغير هذا لا طريقَ في
            اللوحة إلى محفظة الكبتن. **ولـ`admin` وحدَه** كبقيّة قرارات المال */}
        <WalletSection
          userId={row.user_id}
          side="driver"
          canDecide={canDecide}
        />
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

        <h3 className="ad-dh">الوثائق</h3>
        <BulkApprove
          docs={docs}
          seen={seen}
          canDecide={canDecide}
          busy={busy}
          onApprove={(ids) =>
            void runStay(async () => {
              // **واحدةً بعد أخرى لا معاً**: `Promise.all` يرسل خمسةَ نداءاتٍ
              // تتسابق على صفِّ الكبتن نفسِه — و`drivers_service.lock` يقفله،
              // **فأربعةٌ منها تنتظر قفلاً ثمّ تُعيد حساب الحال من قراءةٍ
              // قديمة**. والتسلسلُ يجعل كلَّ بتّةٍ ترى ما قبلها.
              for (const id of ids) {
                await reviewDocument(
                  row.driver_id,
                  id,
                  true,
                  undefined,
                  expiry[id] ?? undefined,
                );
              }
              await load();
            }, approvedMessage(ids.length, pendingIds(docs).length))
          }
        />
        {docs === null ? (
          <div className="ad-sec-loading">
            <Spinner />
          </div>
        ) : docs.documents.length === 0 ? (
          <p className="ad-mini-empty">لم يرفع أيّ مستند بعد.</p>
        ) : (
          <ul className="ad-mini-reset">
            {docs.documents.map((document) => (
              <li key={document.id} className="ad-doc">
                <div className="ad-doc-top">
                  <span className="ad-tile">
                    <Icon name="description" />
                  </span>
                  <span className="ad-doc-title">
                    {DOC_LABEL[document.doc_type]}
                  </span>
                  <Badge
                    tone={
                      document.review_status === "approved"
                        ? "ok"
                        : document.review_status === "rejected"
                          ? "danger"
                          : "warn"
                    }
                  >
                    {document.review_status === "approved"
                      ? "مقبولة"
                      : document.review_status === "rejected"
                        ? "مرفوضة"
                        : "بانتظار المراجعة"}
                  </Badge>
                </div>
                {document.review_note ? (
                  <p className="ad-doc-note">{document.review_note}</p>
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
                  onSeen={() =>
                    setSeen((current) => new Set(current).add(document.id))
                  }
                />

                {/* **الأزرارُ للمنتظِر وحدَه**: `documents.review` يرفض ما بُتّ
                    فيه بـ409، فزرٌّ باقٍ على مستندٍ مقبولٍ زرٌّ يعمل ثم يرتدّ —
                    وهو ما يعلّم المشرفَ إعادةَ المحاولة بدل أن يقول له إن
                    القرار وقع. **وتغييرُ القرار بابُه رفعُ الكبتن من جديد**، لا
                    ضغطةٌ ثانيةٌ هنا. (وجدته المرحلةُ ١٣: تسعُ ضغطاتٍ على تسعة
                    مستندات أرسلت تسعَ مراجعاتٍ لمعرّفٍ واحدٍ كلُّها ٤٠٩) */}
                {canDecide && document.review_status === "pending" ? (
                  <div className="ad-doc-actions">
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
                      className="ad-btn ad-btn-sm ad-btn-ok"
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
                      className="ad-btn ad-btn-sm ad-btn-danger"
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

        <Inspection row={row} canDecide={canDecide} onChanged={onChanged} />

        <h3 className="ad-dh">توثيق الجنس</h3>
        <div className="ad-box">
          <div className="ad-box-row">
            <p className="ad-box-state">
              {row.gender_verified && row.gender
                ? `مُثبت — ${GENDER_LABEL[row.gender]}`
                : "لم يُثبَّت بعد"}
            </p>
            <Badge tone={row.gender_verified ? "ok" : "warn"}>
              {row.gender_verified ? "مختوم" : "بانتظار المشرف"}
            </Badge>
          </div>

          <p className="ad-box-hint">
            {PREFERENCE_LABEL[row.gender_preference]} — تفضيلٌ دائم يضبطه صاحبُ
            الحساب من تطبيقه.
          </p>

          {canDecide ? (
            <>
              <div className="ad-gender">
                {(["female", "male"] as Gender[]).map((value) => (
                  <button
                    key={value}
                    type="button"
                    disabled={busy}
                    aria-pressed={row.gender_verified && row.gender === value}
                    onClick={() =>
                      void run(
                        () => setDriverGender(row.driver_id, value),
                        `ثُبّت الجنس: ${GENDER_LABEL[value]}`,
                      )
                    }
                    className={cn(
                      "ad-btn ad-btn-sm ad-btn-secondary",
                      row.gender_verified && row.gender === value && "on",
                    )}
                  >
                    {GENDER_LABEL[value]}
                  </button>
                ))}
              </div>
              <p className="ad-box-hint">
                يُقرأ من الهوية المرفوعة أعلاه، لا من قول صاحبه: بلا ختمِ مشرفٍ
                يصير بلوغُ صفة «سائقة للنساء» كتابةَ كلمةٍ في حقل. والضبطُ لا
                يعيد دورة اعتماد — الوثائق مراجَعةٌ أصلاً.
              </p>
            </>
          ) : (
            <p className="ad-box-hint">
              الضبطُ لـ admin وحده — إعلانُ جنس الكبتن يقيّد أمان غيره
              (القسم 13/8).
            </p>
          )}
        </div>

        {canDecide ? (
          <div className="ad-drawer-reason">
            <Field
              label="سبب الرفض أو الإيقاف"
              name="reason"
              placeholder="يصل نصُّه إلى السائق"
              value={reason}
              maxLength={255}
              onChange={(event) => setReason(event.target.value)}
            />
            <p className="ad-hint">
              الرفضُ بلا سببٍ يجعل السائق يعيد رفع الصورة نفسها وينتظر بلا
              نهاية.
            </p>
          </div>
        ) : null}

        {error ? (
          <div className="mt-12">
            <ErrorNote message={error} />
          </div>
        ) : null}

        {canDecide ? (
          <div className="ad-decide">
            {row.status !== "approved" ? (
              <>
                {blockers.length > 0 ? (
                  <div className="ad-note warn" role="status">
                    <Icon name="lock" fill />
                    <span>لا يمكن الاعتماد بعد: {blockers.join(" · ")}</span>
                  </div>
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
                variant="danger"
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
          <p className="ad-drawer-note">
            القرارُ لـ admin وحده — مراجعةٌ تفتح باب العمل على المنصة ليست إجراء
            دعمٍ فني (القسم 13/8).
          </p>
        )}
    </Drawer>
    </FormErrors>
  );
}


/** الفعلُ الجماعيُّ الوحيدُ في هذه الشاشة — **ولا يظهر إلا حين يفيد**.
 *
 * **زرٌّ لوثيقةٍ واحدةٍ ليس فعلاً جماعياً**: هو زرُّها نفسُه بمكانٍ ثانٍ،
 * **وزرّان لفعلٍ واحدٍ يجعلان المشرفَ يسأل أيُّهما يفعل ماذا**. فالحدُّ اثنتان.
 *
 * **ولا فعلَ جماعيَّ على رفض**: الرفضُ يحتاج **سبباً لكلِّ ورقة** يصل صاحبَها
 * في الإشعار، **وسببٌ واحدٌ لخمسِ أوراقٍ سببٌ لا يخصّ واحدةً منها** — ومن
 * قرأه لم يعرف ما يصلح في ورقته. وهذا هو «حيث تكون آمنة» بحرفه.
 */
function BulkApprove({
  docs,
  seen,
  canDecide,
  busy,
  onApprove,
}: {
  docs: DriverDocuments | null;
  seen: Set<string>;
  canDecide: boolean;
  busy: boolean;
  onApprove: (ids: string[]) => void;
}) {
  if (!canDecide || docs === null) return null;
  const ready = pendingIds(docs).filter((id) => seen.has(id));
  if (ready.length < 2) return null;

  const rest = pendingIds(docs).length - ready.length;

  return (
    <div className="ad-bulk">
      <button
        type="button"
        disabled={busy}
        onClick={() => onApprove(ready)}
        className="ad-btn ad-btn-sm ad-btn-ok"
      >
        اعتمِد ما عاينتَه ({ready.length})
      </button>
      <p className="ad-bulk-note">
        {rest > 0
          ? `ويبقى ${rest} لم تُفتح ورقتُها — ولا يُعتمد ما لا يُرى.`
          : "وكلُّ ما ينتظر قد عُوين."}
      </p>
    </div>
  );
}

/** الوثائقُ المنتظِرةُ بمعرّفاتها — **بيتٌ واحدٌ يقرؤه الزرُّ والرسالة**. */
function pendingIds(docs: DriverDocuments | null): string[] {
  return (docs?.documents ?? [])
    .filter((document) => document.review_status === "pending")
    .map((document) => document.id);
}

/** **يقول ماذا وقع بالضبط** (§39٫١٢٫٥) — والعددُ لاتينيٌّ بحكم `${}`. */
function approvedMessage(done: number, before: number): string {
  const rest = before - done;
  return rest > 0
    ? `اعتُمدت ${done} وثائق ممّا عاينتَه — ويبقى ${rest} لم تُفتح ورقتُها`
    : `اعتُمدت ${done} وثائق — ولم يبقَ منتظِر`;
}

/** **فحصُ المركبة** (§61-ط/٥) — موعدٌ ومكانٌ يراهما الكبتن في «طلبك قيد المراجعة»، و«اجتاز الفحص».
 *
 * **ولا يشترطه الاعتماد**: زرُّ «اعتماد» أعلاه كما هو — والمشرفُ يقرّر متى يعتمد. **وموعدٌ جديدٌ يُسقط اجتيازاً سابقاً**: فحصٌ
 * يُعاد يُقرأ من جديد. **والوقتُ بمنطقة متصفّح المشرف** يُرسل بمنطقته (`toISOString`)، فلا يُقرأ بساعتين خطأً في سوقٍ آخر. */
function Inspection({
  row,
  canDecide,
  onChanged,
}: {
  row: AdminDriverRow;
  canDecide: boolean;
  onChanged: (message: string) => void;
}) {
  const [at, setAt] = useState("");
  const [place, setPlace] = useState(row.inspection_place ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<unknown>, message: string) {
    setBusy(true);
    setError(null);
    try {
      await action();
      onChanged(message);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
    } finally {
      setBusy(false);
    }
  }

  const when = (iso: string) =>
    new Date(iso).toLocaleString(DISPLAY_LOCALE, { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });
  const status = row.inspection_passed_at
    ? `اجتاز الفحص — ${when(row.inspection_passed_at)}`
    : row.inspection_at
      ? `الموعد: ${when(row.inspection_at)} — ${row.inspection_place ?? ""}`
      : "لا موعد بعد";

  return (
    <>
      <h3 className="ad-dh">فحص المركبة</h3>
      <div className="ad-box">
        <p className="ad-box-state">{status}</p>
        <p className="ad-box-hint">
          يراه الكبتن في «طلبك قيد المراجعة» ويصله إشعارٌ بالموعد. ولا يشترطه الاعتماد.
        </p>
        {canDecide ? (
          <div className="ad-box-fields">
            {/* **الموعدُ بحقل التاريخ المشترك** (§٦٢-ب/١٥) — الأصليُّ يرسم خاناتِه معكوسةً في صفحةٍ عربيّة */}
            <div>
              <label className="label" htmlFor="inspection-at">
                اليوم والساعة
              </label>
              <DateField
                id="inspection-at"
                kind="datetime-local"
                value={at}
                onChange={setAt}
                label="اليوم والساعة"
              />
            </div>
            <Field label="المكان" value={place} maxLength={160} onChange={(event) => setPlace(event.target.value)} />
            <div className="ad-box-actions">
              <Button
                size="sm"
                disabled={busy || !at || !place.trim()}
                onClick={() =>
                  void run(
                    () => scheduleDriverInspection(row.driver_id, new Date(at).toISOString(), place.trim()),
                    "حُدِّد موعدُ الفحص — وأُخبر الكبتن",
                  )
                }
              >
                حفظ الموعد
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={busy || Boolean(row.inspection_passed_at)}
                onClick={() => void run(() => passDriverInspection(row.driver_id), "اجتاز الفحص")}
              >
                اجتاز الفحص
              </Button>
              <Button
                size="sm"
                variant="ghost"
                disabled={busy || (!row.inspection_at && !row.inspection_passed_at)}
                onClick={() => void run(() => clearDriverInspection(row.driver_id), "أُلغي موعدُ الفحص")}
              >
                إلغاء الموعد
              </Button>
            </div>
            <ErrorNote message={error} />
          </div>
        ) : null}
      </div>
    </>
  );
}
