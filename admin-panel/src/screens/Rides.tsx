/** سجل الرحلات — SPEC القسم 13/4، و`DESIGN.md` §3.3/3.5.
 *
 * **شاشةُ قراءةٍ لا قرار، وهذا ليس نقصاً.** لا زرَّ إلغاءٍ ولا استرداد ولا
 * إسنادِ سائقٍ فيها، لأن كلَّ واحدٍ من الثلاثة يقع في مكانٍ آخر بحكم النظام
 * نفسه:
 *
 * - **الاسترداد وفصلُ النزاع يقعان على الدفعة** (`النزاعات والدعم`): صفُّ
 *   الدفعة هو ما يحمل `resolution` ومن فصل ومتى، والرحلةُ سجلٌّ لما جرى.
 *   ورحلةٌ واحدة قد تحمل دفعتين (المختلط)، فزرٌّ على الرحلة لا يعرف أيَّهما
 *   يقصد.
 * - **إسنادُ سائقٍ يدوياً مؤجَّل** (`FUTURE-FEATURES` بند 27): العرضُ يقع على
 *   كبتنٍ واحدٍ في كل لحظة (القسم 5.4)، وزرٌّ يتخطاه يُسند رحلةً إلى من لم
 *   يقبلها.
 * - **والإلغاء فعلُ طرفٍ في الرحلة** لا فعلُ مشرف: `rides.cancel_ride` يرسم
 *   من ألغى في الحالة نفسها (`cancelled_by_rider` / `..._by_driver`)، وثالثٌ
 *   لا اسم له فيها.
 *
 * **والمسارُ الفعلي هو ما تُفتح النافذةُ لأجله**: `ride_route_points` وُجد
 * لغرضين (القسم 5.7) — المسافةُ التي يُعاد عليها حساب الأجرة، **ودليلُ
 * النزاع**. والدليلُ هنا هو المكان الذي يُقرأ فيه. ولذلك يُعرض معه
 * `route_truncated` صراحةً: مسارٌ قُصّ ذيلُه يُقرأ كاملاً دليلٌ يكذب.
 *
 * **وسؤالُ «لماذا اختلفت الأجرة عمّا رآه الراكب» يُجاب من ثلاثة أرقامٍ لا
 * رقمين**، ولا من حسبةٍ يعيدها المشرف: المقدَّرُ، والمسافةُ الفعلية (تُعاد
 * عليها الأجرة عند الانحراف الكبير — القسم 5.7)، **وما وقف الكبتنُ لأجله**
 * (رسمُ المحطات والانتظار والوقفات — §5.10 و§5.10-ب).
 *
 * **والثالثُ أُضيف بعد قياسٍ نفى السطرَ الذي كان هنا** (2026-08-21): كان
 * مكتوباً أن الرقمين يُجيبان، **ومع رسمِ انتظارٍ لا يُجيبان** — فيحمل الفرقُ
 * مبلغاً لا يظهر في أيِّ حقل، ويعيد المشرفُ الحسبةَ بيده وهو ما نفاه السطر
 * نفسُه. **ووعدٌ في توثيقٍ لا يقع أسوأ من غياب الوعد**: من يقرؤه يكفّ عن
 * البحث.
 *
 * **وبلغة TAXO 2.0** (A04 · A04b): الجدولُ من العُدّة، والتفاصيلُ ورقةٌ بأقسامٍ في بطاقات — **و«الطريقُ على الخريطة»** كما
 * طلبه المالكُ في طلب التصميم (§٢، A04): نقاطُ `route` نفسُها التي كانت تُعدّ هنا «N نقطة»، **ترسمها `RouteCanvas`** بين
 * دائرة الانطلاق ومربّع الوجهة — **بلا نداءٍ جديد**: الحمولةُ تحملها منذ القسم 5.7.
 */

import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getRide, listRides } from "@/api/endpoints";
import type {
  AdminRideDetail,
  AdminRideRow,
  RideStatus,
} from "@/api/types";
import { OpenProfile } from "@/components/profile/OpenProfile";
import { RideCallsSection, RideChatTab } from "@/components/RideComms";
import { RouteCanvas } from "@/components/RouteCanvas";
import { Shell } from "@/components/Shell";
import { Pills, Table, TableSearch } from "@/components/Table";
import { Badge } from "@/components/ui/Badge";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { Segmented } from "@/components/ui/Segmented";
import { TestAccountBadge } from "@/components/ui/TestAccountBadge";
import { useConfig } from "@/lib/config";
import { useCountry } from "@/lib/country";
import { TRIP_CHATS_READ, useMyPermissions } from "@/lib/permissions";
import { moment, money } from "@/lib/format";
import { NO_RESULTS, useSearch } from "@/lib/search";

/** دورةُ الاستطلاع — **رقمُ `LiveMap` نفسُه** (`REFRESH_MS`)، فلا رقمان
 *  لدورةٍ واحدة في لوحةٍ واحدة. */
const RIDES_REFRESH_MS = 5_000;
import {
  PAYMENT_METHOD_LABEL,
  RIDE_STATUS_LABEL,
  RIDE_STATUS_TONE,
} from "@/lib/labels";
import { digits, cn } from "@/lib/utils";
import { Icon } from "@/taxo2";

// **الأسماءُ والنغماتُ من `lib/labels.ts`** — بيتٌ واحدٌ منذ 2026-09-02:
// كُتبت هنا وفي المدفوعات والاشتراكات، **وافترقت فعلاً** («كوبون» مقابل
// «خصم كوبون»)، ثم صار الملفُّ الشخصيُّ يعرض الرحلاتِ والدفعاتِ معاً في درج.
const STATUS_LABEL = RIDE_STATUS_LABEL;
const STATUS_TONE = RIDE_STATUS_TONE;

// وخصمُ المشاركة (12-ي) تتحمّله الشركة كالكوبون، وقناةٌ مستقلةٌ عنه
const METHOD_LABEL = PAYMENT_METHOD_LABEL;

const COLUMNS = "0.7fr 1fr 1.1fr 1.1fr 1.6fr 0.9fr 0.9fr 1fr";

/** معرّفُ الرحلة كما يُقرأ في القائمة — **بلا تعريب خانات**.
 *
 * `digits` للكمّيات لا للمعرّفات (`CLAUDE.md`): هذا رقمٌ يُنسخ ويُبحث
 * به ويُقارَن حرفاً بحرف، وتعريبُه يجعل المشرف يطابق نصّاً بنصٍّ آخر الشكل.
 */
function shortId(id: string) {
  return id.slice(0, 8);
}

export function RidesScreen() {
  const { country } = useCountry();

  const [filter, setFilter] = useState<RideStatus | "all">("all");
  // **نموذجُ البحث بزرِّ «ابحث» استُبدل بحقل الشريط** (2026-09-02): زرٌّ
  // يُضغط ليقع البحثُ يجعل من كتب ولم يضغط يقرأ الجدولَ القديمَ نتيجةً —
  // **والمرشِّحُ نفسُه لم يتغيّر**، هو `q` على الباب كما كان.
  const search = useSearch();
  const [rows, setRows] = useState<AdminRideRow[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  // **يفتح ما يقوله العنوان** — وجهةُ البحث العامّ (§39٫١٢٫٤). و`open` هنا
  // معرّفٌ نصّيٌّ لا صفّ، **فلا ينتظر وصولَ القائمة**.
  const [params, setParams] = useSearchParams();
  const wanted = params.get("open");
  const seeded = params.get("q");
  useEffect(() => {
    if (seeded) search.setText(seeded);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seeded]);

  useEffect(() => {
    if (wanted === null) return;
    setOpen(wanted);
    params.delete("open");
    setParams(params, { replace: true });
  }, [wanted, params, setParams]);
  const [error, setError] = useState<string | null>(null);

  // **يستطلع كما تفعل الخريطةُ الحيّة** (عطبٌ مقيسٌ 2026-08-23): كانت الشاشةُ
  // لقطةً تُقرأ متابعةً — الرحلةُ `in_progress` في القاعدة **والسجلُّ يعرضها
  // «مقبولة»** بعد `arrive` وبعد `start`. ولا حارسَ يمسك هذا: البابُ له زرّ،
  // والفعلُ والمسارُ صحيحان — **والسؤالُ سؤالُ زمنٍ لا سؤالُ بنية** (الشكلُ
  // الرابعَ عشر). و٥ ثوانٍ هو رقمُ `LiveMap` نفسُه، فلا رقمان لدورةٍ واحدة.
  const load = useCallback(
    async (silent = false) => {
      // **الصامتُ لا يُفرِّغ الجدول**: `setRows(null)` كلَّ خمسِ ثوانٍ يومض
      // الشاشةَ ويُفقد موضعَ التمرير — فالتفريغُ للتبديل اليدويّ وحدَه
      if (!silent) setRows(null);
      setRows(
        await listRides({
          country_code: country,
          ride_status: filter === "all" ? undefined : filter,
          q: search.term,
        }),
      );
    },
    [country, filter, search.term],
  );

  useEffect(() => {
    const fail = (caught: unknown) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة السجل",
      );
    load().catch(fail);
    const timer = window.setInterval(
      () => void load(true).catch(fail),
      RIDES_REFRESH_MS,
    );
    return () => window.clearInterval(timer);
  }, [load]);

  return (
    <Shell
      title="سجل الرحلات"
      subtitle="كلُّ رحلةٍ بحالها وأطرافها ودفعاتها — والمسارُ الفعلي داخل التفاصيل"
    >
      <Pills
        value={filter}
        onPick={(key) => setFilter(key)}
        options={[
          { key: "all", label: "الكل" },
          { key: "in_progress", label: "جارية" },
          { key: "at_stop", label: "عند محطة" },
          { key: "completed", label: "مكتملة" },
          { key: "cancelled_by_rider", label: "ألغاها الراكب" },
          { key: "cancelled_by_driver", label: "ألغاها السائق" },
          { key: "no_driver_found", label: "بلا سائق" },
        ]}
      />

      <ErrorNote message={error} />

      {/* **عرضٌ أدنى** (`.ad-rides-table`): ثمانيةُ أعمدةٍ على ١٠٢٤ قصّت المعرّفَ والأسماء — فتُمرَّر أفقياً داخل بطاقتها */}
      <div className={cn("ad-rides-table", error && "mt-12")}>
        <Table
          toolbar={
            <TableSearch
              value={search.text}
              onChange={search.setText}
              placeholder="اسم سائقٍ أو راكب، أو رقم هاتف، أو معرّف رحلة…"
            />
          }
          searching={search.searching}
          noResults={NO_RESULTS}
          columns={COLUMNS}
          headers={[
            "الرقم",
            "الوقت",
            "الراكب",
            "السائق",
            "من ← إلى",
            "الأجرة",
            "الدفع",
            "الحالة",
          ]}
          rows={rows}
          keyOf={(row) => row.id}
          empty={{
            title: "لا رحلات في هذه الحال",
            hint: "بدّل الفلترة أو الدولة، أو امسح نصّ البحث.",
          }}
          render={(row) => (
            <>
              <button
                type="button"
                dir="ltr"
                onClick={() => setOpen(row.id)}
                className="ad-link-id"
                aria-label={`تفاصيل الرحلة ${shortId(row.id)}`}
              >
                {shortId(row.id)}
              </button>

              <span className="ad-tone-muted">{moment(row.created_at)}</span>

              {/* **واسمُ الطرف يحمل بابَه** (§39٫١٢٫٤): كان الصفُّ يعرض
                  اسمَ الراكب واسمَ الكبتن **ولا سبيلَ منه إلى ملفِّ أحدهما** —
                  فمن قرأ نزاعاً على رحلةٍ خرج إلى «الأشخاص» وبحث بالاسم من
                  جديد. */}
              <span className="ad-party">
                <span className="ad-party-name">{row.rider.name}</span>
                {/* **طرفُ تجربة** (SPEC §٦٥-ج) — بجانب الاسم في كلِّ جدولٍ يحمله */}
                <TestAccountBadge isTest={row.rider.is_test} />
                <OpenProfile kind="rider" id={row.rider.user_id} />
              </span>

              <span className="ad-party">
                {row.driver ? (
                  <>
                    <span className="ad-party-name">{row.driver.name}</span>
                    <TestAccountBadge isTest={row.driver.is_test} />
                    <OpenProfile
                      kind="driver"
                      id={row.driver.driver_id}
                      search={row.driver.phone}
                    />
                  </>
                ) : (
                  <span className="ad-tone-muted">—</span>
                )}
              </span>

              <span className="ad-ellipsis ad-tone-muted">
                {row.pickup_address ?? "نقطة على الخريطة"} ←{" "}
                {row.dropoff_address ?? "نقطة على الخريطة"}
              </span>

              <span className="ad-fare">
                {money(row.final_fare ?? row.estimated_fare, row.currency)}
              </span>

              <span className="ad-tone-muted">
                {row.payment_methods.length === 0
                  ? "—"
                  : row.payment_methods
                      .map((method) => METHOD_LABEL[method])
                      .join(" + ")}
              </span>

              <span className="ad-chips">
                <Badge tone={STATUS_TONE[row.status]}>
                  {STATUS_LABEL[row.status]}
                </Badge>
                {row.has_open_dispute ? (
                  <Badge tone="danger">نزاع</Badge>
                ) : null}
              </span>
            </>
          )}
        />
      </div>

      {open ? (
        <RideModal rideId={open} onClose={() => setOpen(null)} />
      ) : null}
    </Shell>
  );
}

/** النافذة — **ورقةٌ موسَّطةٌ بأرض الإسفلت وأقسامٍ في بطاقات** (A04b)؛ وعلى الهاتف ورقةٌ من الأسفل (العُدّة). */
function RideModal({
  rideId,
  onClose,
}: {
  rideId: string;
  onClose: () => void;
}) {
  const [ride, setRide] = useState<AdminRideDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  // **A29 — تبويبُ المحادثة لمن يملك `trip_chats.read` وحدَه** (§٦٦-ب/١٠)، ولا يُطلب إلا حين يُختار: كلُّ فتحٍ سطرٌ في التدقيق
  const held = useMyPermissions();
  const canChat = held?.has(TRIP_CHATS_READ) === true;
  const [tab, setTab] = useState<"details" | "chat">("details");

  useEffect(() => {
    getRide(rideId)
      .then(setRide)
      .catch((caught) =>
        setError(
          caught instanceof ApiError ? caught.message : "تعذّر قراءة التفاصيل",
        ),
      );
  }, [rideId]);

  return (
    <div className="ad-modal" onClick={onClose}>
      <div
        className="ad-modal-box ad-sheet"
        role="dialog"
        aria-modal="true"
        aria-label={`الرحلة ${shortId(rideId)}`}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="ad-sheet-head">
          <div className="ad-sheet-titles">
            <p dir="ltr" className="ad-sheet-id">
              #{shortId(rideId)}
            </p>
            {ride ? <p className="ad-sheet-sub">{moment(ride.created_at)}</p> : null}
          </div>
          <button type="button" onClick={onClose} aria-label="إغلاق" className="ad-round">
            <Icon name="close" />
          </button>
        </div>

        <div className="ad-sheet-body">
          {canChat ? (
            <div className="mb-12">
              <Segmented
                label="العرض"
                value={tab}
                onPick={setTab}
                options={[
                  { key: "details", label: "التفاصيل" },
                  { key: "chat", label: "المحادثة" },
                ]}
              />
            </div>
          ) : null}

          {canChat && tab === "chat" ? (
            <RideChatTab rideId={rideId} />
          ) : (
            <>
              <ErrorNote message={error} />

              {ride === null ? (
                error ? null : (
                  <div className="ad-sec-loading">
                    <Spinner />
                  </div>
                )
              ) : (
                <RideBody ride={ride} />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function RideBody({ ride }: { ride: AdminRideDetail }) {
  const { config } = useConfig();
  const token = config?.providers.mapbox?.public_token ?? null;
  // **الحكمُ يصل محسوباً** (`settlement`، من `services/settlement.py`): كانت
  // المقارنةُ هنا `Number(fare) > Number(paid_amount)` فتقرأ رحلةً ملغاةً
  // بلا أجرةٍ نهائية «مسدَّدة»، ودفعةً منتظِرةً «ناقصة» بلا تمييزٍ عن نزاع
  const unsettled =
    ride.settlement === "due" || ride.settlement === "awaiting";

  return (
    <>
      <div className="ad-sec-badges">
        <Badge tone={STATUS_TONE[ride.status]}>{STATUS_LABEL[ride.status]}</Badge>
        {ride.gender_preference !== "any" ? (
          <Badge tone="ink">
            طلبٌ مجنَّس ·{" "}
            {ride.gender_preference === "female" ? "كبتنة" : "كبتن"}
          </Badge>
        ) : null}
        {ride.cancel_reason_code === "gender_mismatch" ? (
          <Badge tone="warn">أُلغيت بلا رسوم — عدم تطابق الجنس</Badge>
        ) : null}
      </div>

      <Section title="الطرفان">
        <Row label="الراكب" value={ride.rider.name} hint={ride.rider.phone} hintLtr />
        <Row
          label="السائق"
          value={ride.driver?.name ?? "لم يُسنَد"}
          hint={ride.driver?.phone ?? undefined}
          hintLtr
        />
        {ride.driver?.plate_number ? (
          // اللوحةُ مُعرّفٌ يُقارَن حرفاً بحرف — بلا تعريب خانات
          <Row label="رقم اللوحة" value={ride.driver.plate_number} ltr />
        ) : null}
      </Section>

      <Section
        title="الطريق"
        lead={
          // **الدليلُ يُرى لا يُعدّ** — المسارُ الفعليُّ بين الدائرة والمربّع (A04b)، وبلا عقد Mapbox سطرٌ يقول السبب
          <div className="ad-sheet-map">
            <RouteCanvas
              token={token}
              pickup={{ lat: ride.pickup_lat, lng: ride.pickup_lng }}
              dropoff={{ lat: ride.dropoff_lat, lng: ride.dropoff_lng }}
              route={ride.route}
              position={null}
            />
          </div>
        }
      >
        <Row label="من" value={ride.pickup_address ?? "نقطة على الخريطة"} />
        <Row label="إلى" value={ride.dropoff_address ?? "نقطة على الخريطة"} />
        <Row
          label="المسافة المقدَّرة"
          value={`${digits(ride.distance_km)} كم`}
        />
        {/* فارغةٌ لا صفر حين لا تكفي النقاط — صفرٌ يُقرأ «سار صفر كيلومتر» */}
        <Row
          label="المسافة الفعلية"
          value={
            ride.actual_distance_km
              ? `${digits(ride.actual_distance_km)} كم`
              : "لم تُسجَّل"
          }
          hint={
            ride.actual_distance_km
              ? undefined
              : "أقلُّ من نقطتين في المسار — يبقى المقدَّر هو الحكم"
          }
        />
        <Row
          label="نقاط المسار"
          value={
            ride.route.length === 0
              ? "لا نقاط"
              : `${digits(String(ride.route.length))} نقطة`
          }
          hint={
            ride.route_truncated
              ? "المعروضُ أولُ ألف نقطة — المسار أطول"
              : undefined
          }
        />
      </Section>

      <Section title="المال">
        <Row
          label="المقدَّرة"
          value={money(ride.estimated_fare, ride.currency)}
        />
        <Row
          label="النهائية"
          value={
            ride.final_fare
              ? money(ride.final_fare, ride.currency)
              : "لم تُحسب بعد"
          }
        />
        {/* **ثالثُ ما يفسّر الفرق** بعد المقدَّر والمسافة (§5.10 و§5.10-ب/و):
            ما وقف الكبتنُ لأجله. **قيمٌ تُقرأ لا تُحسب** — الضربُ والجمع في
            الخلفية (§14)، ومن باب الخدمة نفسِه الذي حسب `final_fare`، فلا
            رقمٌ ثانٍ يشبه الأول ويخالفه. **وصفرٌ لا يُرسم** */}
        {Number(ride.stops_charge) > 0 ? (
          <Row
            label="رسم المحطات"
            value={money(ride.stops_charge, ride.currency)}
            hint={`${digits(String(ride.stops_count))} محطة × ${money(ride.stop_fee, ride.currency)} — مجمَّدٌ لحظة الطلب`}
          />
        ) : null}
        {Number(ride.waiting_charge) > 0 ? (
          <Row
            label="رسم الانتظار عند المحطات"
            value={money(ride.waiting_charge, ride.currency)}
            hint="ما بعد الدقائق المجانية، بالمعدَّل المجمَّد على الرحلة"
          />
        ) : null}
        {Number(ride.pause_charge) > 0 ? (
          <Row
            label="رسم الوقفات أثناء الرحلة"
            value={money(ride.pause_charge, ride.currency)}
            hint="وقفاتٌ ضغطها الكبتن بعد الانطلاق (§5.10-ب)"
          />
        ) : null}
        {/* **وفرقُ التقريب من سجلّه** (SPEC §٧٠-ج/٣ و٤) — داخلَ النهائيّة سطراً بذاته، **للكبتن أو عليه** ولا تمسّه العمولة.
            **يُقرأ ولا يُحسب**: «النهائيّة − المقدَّرة» تخلطه بانحراف الطريق والرسوم. وبلا صفٍّ لا يُرسم */}
        {ride.rounding_amount !== null ? (
          <Row
            label="تقريب"
            value={money(ride.rounding_amount, ride.currency)}
            hint="ما على الراكب بعد الخصم قُرِّب إلى وحدة السوق مرّةً — والفرقُ مقيَّدٌ في سجلّ التقريب"
          />
        ) : null}
        {/* **المحطاتُ بصفوفها** (عطبٌ مقيسٌ 2026-08-23): كان المشرفُ يرى
            «رسم المحطات ١٫٠٠٠ · ٢ محطة» **ولا يرى عند أيِّ محطةٍ وقف ولا كم**
            — فلا يفصل في نزاع انتظارٍ بدليل. وكلُّ رقمٍ هنا **يصل محسوباً**
            من البانِي نفسِه الذي يقرؤه التطبيقان (§14). */}
        {ride.stops.length > 0 ? (
          <div className="ad-stops">
            <p className="ad-stops-title">
              المحطات ({digits(String(ride.stops.length))})
            </p>
            <ol className="ad-stops-list">
              {ride.stops.map((stop) => (
                <li key={stop.id} className="ad-stop">
                  <span className="ad-stop-main">
                    <span className="ad-stop-name">
                      {digits(String(stop.sequence))}.{" "}
                      {stop.address ?? "نقطة على الخريطة"}
                    </span>
                    <span className="ad-stop-when">
                      {stop.arrived_at
                        ? `وصل ${moment(stop.arrived_at)}${
                            stop.resumed_at ? ` · استأنف ${moment(stop.resumed_at)}` : " · لم يستأنف بعد"
                          }`
                        : "لم يصلها بعد"}
                      {stop.over_max_wait ? " · تجاوز السقف" : ""}
                    </span>
                  </span>
                  <span className="ad-stop-side">
                    <span className="ad-stop-amount">
                      {money(stop.waiting_charge, ride.currency)}
                    </span>
                    <span className="ad-stop-when">
                      {digits(stop.waited_minutes)} دقيقة
                    </span>
                  </span>
                </li>
              ))}
            </ol>
          </div>
        ) : null}
        <Row
          label="عمولة المنصة"
          value={`${digits(ride.commission_percent_at_ride)}٪`}
          hint="مجمَّدةٌ لحظة الطلب — لا يعيد تعديلُ الإعداد حسابَها"
        />
        {ride.cancellation_fee ? (
          <Row
            label="رسوم الإلغاء"
            value={money(ride.cancellation_fee, ride.currency)}
          />
        ) : null}
        <Row
          label="المُحصَّل"
          value={money(ride.paid_amount, ride.currency)}
          hint={
            unsettled
              ? ride.settlement === "awaiting"
                ? "صفُّ دفعةٍ قائمٌ بانتظار التأكيد — لم يصل المال بعد"
                : "أقلُّ من الأجرة — الرحلة غير مسدَّدة بالكامل"
              : ride.settlement === "disputed"
                ? "عليها نزاعٌ مفتوح"
              : undefined
          }
        />
      </Section>

      <Section title="الدفعات">
        {ride.payments.length === 0 ? (
          <p className="ad-mini-empty ad-kv-pad">لا دفعة على هذه الرحلة بعد.</p>
        ) : (
          <ul className="ad-mini">
            {ride.payments.map((payment) => (
              <li key={payment.id} className="ad-mini-row">
                <span className="ad-mini-main">
                  {METHOD_LABEL[payment.method]} ·{" "}
                  {money(payment.amount, ride.currency)}
                </span>
                <span
                  className={cn(
                    "ad-pay-status",
                    payment.status === "confirmed"
                      ? "ad-tone-ok"
                      : payment.status === "disputed" ||
                          payment.status === "failed"
                        ? "ad-tone-danger"
                        : "ad-tone-warn",
                  )}
                >
                  {PAYMENT_STATUS_LABEL[payment.status]}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Section>
      <p className="ad-hint">
        فصلُ النزاع والاسترداد يقعان على الدفعة في «النزاعات والدعم» — لا على
        الرحلة: رحلةٌ واحدة قد تحمل دفعتين.
      </p>

      {ride.ratings.length > 0 ? (
        <Section title="التقييمات">
          {ride.ratings.map((rating) => (
            <Row
              key={rating.rater_type}
              label={rating.rater_type === "rider" ? "من الراكب" : "من السائق"}
              value={`★ ${digits(String(rating.stars))}`}
              hint={rating.comment ?? undefined}
            />
          ))}
        </Section>
      ) : null}

      {ride.cancelled_reason ? (
        <Section title="سبب الإلغاء">
          <p className="ad-kv-text">{ride.cancelled_reason}</p>
        </Section>
      ) : null}

      {/* **A34 — المكالمات** (§٦٦-ج/١٦): من اتصل بمن ومتى وكم وكيف انتهت — **و«استماع» لمن يملك صلاحيتَه وحدَه** */}
      <RideCallsSection rideId={ride.id} />
    </>
  );
}

const PAYMENT_STATUS_LABEL: Record<string, string> = {
  pending: "بانتظار التأكيد",
  confirmed: "مؤكدة",
  failed: "فاشلة",
  disputed: "نزاع",
  refunded: "مستردة",
};

/** قسمٌ في الورقة — عنوانٌ وبطاقةٌ بصفوفها، **و`lead` ما يسبق البطاقةَ** (خريطةُ الطريق). */
function Section({
  title,
  lead,
  children,
}: {
  title: string;
  lead?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section>
      <h3 className="ad-dh">{title}</h3>
      {lead}
      <div className="ad-kv">{children}</div>
    </section>
  );
}

function Row({
  label,
  value,
  hint,
  ltr = false,
  hintLtr = false,
}: {
  label: string;
  value: string;
  hint?: string;
  /** **القيمةُ مُعرّفٌ** (اللوحة) — من اليسار، بلا تعريب */
  ltr?: boolean;
  /** **التلميحُ رقمُ هاتف** — من اليسار */
  hintLtr?: boolean;
}) {
  return (
    <div className="ad-kv-row">
      <span className="ad-kv-label">{label}</span>
      <span className="ad-kv-value">
        <span dir={ltr ? "ltr" : undefined} className={ltr ? "ad-ltr" : undefined}>
          {value}
        </span>
        {hint ? (
          <span dir={hintLtr ? "ltr" : undefined} className={hintLtr ? "ad-kv-hint ad-ltr" : "ad-kv-hint"}>
            {hint}
          </span>
        ) : null}
      </span>
    </div>
  );
}
