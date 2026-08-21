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
 */

import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";

import { ApiError } from "@/api/client";
import { getRide, listRides } from "@/api/endpoints";
import type {
  AdminRideDetail,
  AdminRideRow,
  PaymentMethod,
  RideStatus,
} from "@/api/types";
import { Shell } from "@/components/Shell";
import { Pills, Table } from "@/components/Table";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Field } from "@/components/ui/Field";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { useCountry } from "@/lib/country";
import { moment, money } from "@/lib/format";
import { digits, cn } from "@/lib/utils";

const STATUS_LABEL: Record<RideStatus, string> = {
  requested: "مطلوبة",
  searching: "يُبحث عن سائق",
  accepted: "مقبولة",
  arrived: "وصل السائق",
  at_stop: "وقوفٌ عند محطة",
  in_progress: "جارية",
  completed: "مكتملة",
  cancelled_by_rider: "ألغاها الراكب",
  cancelled_by_driver: "ألغاها السائق",
  no_driver_found: "لم يُوجد سائق",
};

/** نغماتُ الحالات من `DESIGN.md` §2.6 — لا اجتهادَ في اللون. */
const STATUS_TONE: Record<RideStatus, Tone> = {
  requested: "warn",
  searching: "warn",
  accepted: "warn",
  arrived: "warn",
  at_stop: "warn",
  in_progress: "warn",
  completed: "ok",
  cancelled_by_rider: "danger",
  cancelled_by_driver: "danger",
  no_driver_found: "muted",
};

const METHOD_LABEL: Record<PaymentMethod, string> = {
  cash: "كاش",
  cliq: "كليك",
  card: "بطاقة",
  wallet: "محفظة",
  promo: "خصم كوبون",
  // خصمُ المشاركة (12-ي) — تتحمّله الشركة كالكوبون، وقناةٌ مستقلةٌ عنه
  share: "خصم مشاركة",
};

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
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<AdminRideRow[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRows(null);
    setRows(
      await listRides({
        country_code: country,
        ride_status: filter === "all" ? undefined : filter,
        q: query || undefined,
      }),
    );
  }, [country, filter, query]);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة السجل",
      ),
    );
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

      <form
        className="mb-14 flex max-w-modal items-end gap-9"
        onSubmit={(event) => {
          event.preventDefault();
          setQuery(search.trim());
        }}
      >
        <div className="flex-1">
          <Field
            label="بحث"
            placeholder="اسم سائقٍ أو راكب، أو رقم هاتف، أو معرّف رحلة"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <button
          type="submit"
          className="rounded-13 border border-line px-16 py-13 text-13 font-semibold text-ink"
        >
          ابحث
        </button>
      </form>

      <ErrorNote message={error} />

      <div className="mt-12">
        <Table
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
                className="truncate text-start font-semibold text-ink underline"
              >
                {shortId(row.id)}
              </button>

              <span className="text-muted">{moment(row.created_at)}</span>

              <span className="min-w-0 truncate text-ink">{row.rider.name}</span>

              <span className="min-w-0 truncate text-ink">
                {row.driver ? row.driver.name : <span className="text-muted">—</span>}
              </span>

              <span className="min-w-0 truncate text-muted">
                {row.pickup_address ?? "نقطة على الخريطة"} ←{" "}
                {row.dropoff_address ?? "نقطة على الخريطة"}
              </span>

              <span className="font-semibold text-ink">
                {money(row.final_fare ?? row.estimated_fare, row.currency)}
              </span>

              <span className="text-muted">
                {row.payment_methods.length === 0
                  ? "—"
                  : row.payment_methods
                      .map((method) => METHOD_LABEL[method])
                      .join(" + ")}
              </span>

              <span className="flex items-center gap-6">
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

/** النافذة — `DESIGN.md` §3.5: تعتيمٌ ولوحٌ موسَّط بـ`rise`. */
function RideModal({
  rideId,
  onClose,
}: {
  rideId: string;
  onClose: () => void;
}) {
  const [ride, setRide] = useState<AdminRideDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

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
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-dim px-20"
      onClick={onClose}
    >
      <div
        className="scr w-full max-w-modal animate-rise rounded-20 border border-line bg-surface p-24"
        style={{ maxHeight: "86vh" }}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-16 flex items-start gap-12">
          <div className="flex-1">
            <div dir="ltr" className="text-16 font-bold text-ink">
              #{shortId(rideId)}
            </div>
            {ride ? (
              <div className="mt-3 text-12 text-muted">
                {moment(ride.created_at)}
              </div>
            ) : null}
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

        <ErrorNote message={error} />

        {ride === null ? (
          error ? null : <Spinner className="mx-auto my-24" />
        ) : (
          <RideBody ride={ride} />
        )}
      </div>
    </div>
  );
}

function RideBody({ ride }: { ride: AdminRideDetail }) {
  // **الحكمُ يصل محسوباً** (`settlement`، من `services/settlement.py`): كانت
  // المقارنةُ هنا `Number(fare) > Number(paid_amount)` فتقرأ رحلةً ملغاةً
  // بلا أجرةٍ نهائية «مسدَّدة»، ودفعةً منتظِرةً «ناقصة» بلا تمييزٍ عن نزاع
  const unsettled =
    ride.settlement === "due" || ride.settlement === "awaiting";

  return (
    <>
      <div className="mb-16 flex flex-wrap items-center gap-6">
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
        <Row label="الراكب" value={ride.rider.name} hint={ride.rider.phone} />
        <Row
          label="السائق"
          value={ride.driver?.name ?? "لم يُسنَد"}
          hint={ride.driver?.phone ?? undefined}
        />
        {ride.driver?.plate_number ? (
          // اللوحةُ مُعرّفٌ يُقارَن حرفاً بحرف — بلا تعريب خانات
          <Row label="رقم اللوحة" value={ride.driver.plate_number} />
        ) : null}
      </Section>

      <Section title="الطريق">
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
          <p className="text-12 leading-note text-muted">
            لا دفعة على هذه الرحلة بعد.
          </p>
        ) : (
          <ul className="flex flex-col gap-8">
            {ride.payments.map((payment) => (
              <li
                key={payment.id}
                className="flex items-center gap-10 rounded-12 border border-line px-13 py-10"
              >
                <span className="flex-1 text-12.5 text-ink">
                  {METHOD_LABEL[payment.method]} ·{" "}
                  {money(payment.amount, ride.currency)}
                </span>
                <span
                  className={cn(
                    "text-11.5 font-bold",
                    payment.status === "confirmed"
                      ? "text-ok"
                      : payment.status === "disputed" ||
                          payment.status === "failed"
                        ? "text-danger"
                        : "text-warn",
                  )}
                >
                  {PAYMENT_STATUS_LABEL[payment.status]}
                </span>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-8 text-11 leading-note text-muted">
          فصلُ النزاع والاسترداد يقعان على الدفعة في «النزاعات والدعم» — لا على
          الرحلة: رحلةٌ واحدة قد تحمل دفعتين.
        </p>
      </Section>

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
          <p className="text-12.5 leading-note text-ink">
            {ride.cancelled_reason}
          </p>
        </Section>
      ) : null}
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

function Section({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="mb-16">
      <h3 className="mb-8 text-13 font-bold text-muted">{title}</h3>
      {children}
    </section>
  );
}

function Row({
  label,
  value,
  hint,
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="flex items-start gap-10 border-b border-line py-8 last:border-b-0">
      <span className="w-side-sm flex-none text-12 text-muted">{label}</span>
      <span className="min-w-0 flex-1">
        <span className="block text-12.5 text-ink">{value}</span>
        {hint ? (
          <span className="mt-2 block text-11 leading-note text-muted">
            {hint}
          </span>
        ) : null}
      </span>
    </div>
  );
}
