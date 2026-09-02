/** أقسامُ الملفِّ التي تخصّ الكبتنَ وحدَه (§37، البند ١).
 *
 * **والفرقُ بينها وبين المشتركة ليس الدور بل الكيان**: مركبةٌ واشتراكٌ وسلفةٌ
 * ومستحقٌّ أشياءُ لا وجودَ لها إلا لصفٍّ في `drivers` — **ومعرِّفُها
 * `drivers.id` لا `users.id`**، وهو الفرقُ الذي أسقط ثلاثةَ بحوثٍ في هذه
 * الشجرة (`ARCHITECTURE.md`: «passing the latter silently returns zero»).
 */

import { useEffect, useRef } from "react";

import {
  getDriverLiveRide,
  listAdvances,
  listDriverDebts,
  listDriverVehicles,
  listSubscriptions,
} from "@/api/endpoints";
import type { DriverLiveRide } from "@/api/types";
import {
  CappedNote,
  Facts,
  MiniList,
  MiniRow,
  ProfileSection,
  useLoader,
} from "@/components/Profile";
import { RouteCanvas } from "@/components/RouteCanvas";
import { Badge } from "@/components/ui/Badge";
import { useConfig } from "@/lib/config";
import { day, days, daysUntil, moment, money } from "@/lib/format";
import {
  ADVANCE_STATUS_LABEL,
  ADVANCE_STATUS_TONE,
  DEBT_STATUS_LABEL,
  DEBT_STATUS_TONE,
  PAYMENT_METHOD_LABEL,
  RIDE_STATUS_LABEL,
  RIDE_STATUS_TONE,
  SUBSCRIPTION_DURATION_LABEL,
} from "@/lib/labels";
import { useSession } from "@/lib/session";
import { digits } from "@/lib/utils";

const CAP = 5;

const CATEGORY_LABEL: Record<string, string> = {
  economy: "اقتصادية",
  comfort: "مريحة",
};

/** قسمُ «المركبة» — **ولم يكن للوحة بابٌ يقرؤها قبل اليوم**.
 *
 * فكان المشرفُ يبتّ في وثيقةٍ اسمُها «رخصة المركبة» **ولا يرى اللوحةَ ولا
 * السنةَ اللتين يقارن بهما الصورةَ** — يقرأ الصورةَ ويصدّقها أو لا، بلا مرجع.
 *
 * **ولا خاناتٍ عربيةً في اللوحة** (`CLAUDE.md`): رقمُ اللوحة يُقارَن حرفاً
 * بحرفٍ بلوحةٍ معدنيةٍ في صورة، **وتعريبُه يجعل المطابقةَ بين شكلين**.
 * والسنةُ كمّيةٌ فتُعرَّب بالمصفاة كبقية الكمّيات.
 */
export function VehiclesSection({ driverId }: { driverId: string }) {
  const load = useLoader(() => listDriverVehicles(driverId), [driverId]);
  return (
    <ProfileSection
      title="المركبة"
      hint="يكتبها صاحبُها من تطبيقه، وتحريرُ هوّيتها يُسقط اعتمادَه إلى «بانتظار المراجعة» — فلا تُحرَّر من هنا."
      load={load}
    >
      {(rows) => (
        <>
          {rows.length === 0 ? (
            <p className="text-11.5 leading-note text-muted">
              لا مركبةَ مسجَّلةٌ بعد — ولا يُعتمد كبتنٌ بلا رخصةِ مركبةٍ مقبولة.
            </p>
          ) : (
            <div className="flex flex-col gap-9">
              {rows.map((vehicle) => (
                <Facts
                  key={vehicle.id}
                  rows={[
                    { label: "الصنع والطراز", value: `${vehicle.make} ${vehicle.model}` },
                    { label: "اللوحة", value: vehicle.plate_number, ltr: true },
                    { label: "السنة", value: digits(String(vehicle.year)) },
                    { label: "اللون", value: vehicle.color },
                    {
                      label: "الفئة",
                      value: CATEGORY_LABEL[vehicle.category] ?? vehicle.category,
                    },
                    { label: "أُضيفت", value: day(vehicle.created_at) },
                  ]}
                />
              ))}
            </div>
          )}
        </>
      )}
    </ProfileSection>
  );
}

/** قسمُ «الاشتراك» — **والحالُ تقولها الساعةُ لا العمود**.
 *
 * `coverage_condition` في الخلفية هو `active AND starts_at <= now AND
 * expires_at > now`، **والكنسُ كلَّ خمس دقائق** — فصفٌّ يقول `active` وقد
 * انقضى أمسِ يُقرأ هنا «انقضى — لم يُعلَّم بعد» لا «سارٍ».
 */
export function SubscriptionSection({ driverId }: { driverId: string }) {
  const load = useLoader(
    () => listSubscriptions({ driver_id: driverId, limit: CAP }),
    [driverId],
  );
  return (
    <ProfileSection
      title="الاشتراك"
      hint="لا يصل الكبتنَ عرضٌ بلا اشتراكٍ ساري — والتجديدُ صفٌّ جديدٌ يبدأ من نهاية ما قبله لا من اليوم."
      load={load}
    >
      {(rows) => (
        <>
          <MiniList
            rows={rows}
            keyOf={(row) => row.id}
            empty="لا اشتراكَ لهذا الكبتن — ولا تصله عروضُ رحلات."
            render={(row) => {
              const left = daysUntil(row.expires_at);
              return (
                <MiniRow
                  title={`${row.plan_name} · ${SUBSCRIPTION_DURATION_LABEL[row.duration_type]}`}
                  at={row.starts_at}
                  value={
                    left <= 0
                      ? row.status === "active"
                        ? "انقضى — لم يُعلَّم بعد"
                        : "منتهٍ"
                      : `سارٍ · ${days(left)}`
                  }
                  tone={left <= 0 ? (row.status === "active" ? "warn" : "muted") : "ok"}
                  note={
                    <>
                      {money(row.amount_paid, row.currency)} ·{" "}
                      {PAYMENT_METHOD_LABEL[row.payment_method]} · ينتهي{" "}
                      {day(row.expires_at)}
                    </>
                  }
                />
              );
            }}
          />
          <CappedNote shown={rows.length} cap={CAP} />
        </>
      )}
    </ProfileSection>
  );
}

/** قسمُ «ما عليه» — **السلفةُ والمستحقُّ في مكانٍ واحد، وهما ليسا شيئاً واحداً**.
 *
 * **السلفةُ مالُ المنصة أقرضته له**، **والمستحقُّ عمولةُ رحلةٍ نقديةٍ قبضها
 * ولم تصل** — أوّلُهما قرارُ إقراضٍ والثاني أثرُ رحلة. **وجمعُهما في رقمٍ
 * واحدٍ يمحو الفرق**، فيُعرضان صفّين تحت عنوانٍ واحدٍ لا مجموعاً.
 *
 * **ولا زرَّ شطبٍ هنا**: الشطبُ اعترافٌ بخسارةٍ باسمِ من قرّرها وسببُه
 * إلزاميّ، وبابُه جدولُه تحت قائمة الكباتن — **وزرٌّ ثانٍ يجعل نصفَ الشطوب
 * بلا سبب**، وهي القاعدةُ نفسُها التي تمنع زرَّ تجميدٍ في قسم المحفظة.
 */
export function MoneyOwedSection({ driverId }: { driverId: string }) {
  const load = useLoader(
    async () => ({
      advances: await listAdvances(undefined, undefined, driverId),
      debts: await listDriverDebts(undefined, undefined, driverId),
    }),
    [driverId],
  );
  return (
    <ProfileSection
      title="ما عليه — السلف والمستحقّات"
      hint="السلفةُ مالٌ أقرضته المنصة، والمستحقُّ عمولةُ رحلةٍ نقديةٍ قبضها ولم تصل. ولا يُجمعان في رقم."
      load={load}
    >
      {({ advances, debts }) => (
        <>
          <h4 className="mb-7 text-11.5 font-bold text-muted">السلف</h4>
          <MiniList
            rows={advances}
            keyOf={(row) => row.id}
            empty="لا سلفةَ صُرفت له."
            render={(row) => (
              <MiniRow
                title={money(row.amount, row.currency)}
                at={row.created_at}
                value={ADVANCE_STATUS_LABEL[row.status]}
                tone={ADVANCE_STATUS_TONE[row.status]}
                note={
                  <>
                    المتبقّي {money(row.remaining, row.currency)} · المهلة{" "}
                    {day(row.due_at)}
                    {row.overdue ? " · انقضت" : null}
                  </>
                }
              />
            )}
          />

          <h4 className="mb-7 mt-12 text-11.5 font-bold text-muted">
            المستحقّات
          </h4>
          <MiniList
            rows={debts}
            keyOf={(row) => row.id}
            empty="لا مستحقَّ على هذا الكبتن."
            render={(row) => (
              <MiniRow
                title={money(row.amount, row.currency)}
                at={row.created_at}
                value={DEBT_STATUS_LABEL[row.status]}
                tone={DEBT_STATUS_TONE[row.status]}
                note={<>حُصِّل منه {money(row.collected, row.currency)}</>}
              />
            )}
          />

          {advances.length + debts.length === 0 ? null : (
            <p className="mt-9">
              <Badge tone="warn">قائمٌ عليه مالٌ للمنصة</Badge>
            </p>
          )}
        </>
      )}
    </ProfileSection>
  );
}

/** كم ثانيةً بين استطلاعين — **خمسٌ كالخريطة الحيّة**، والسؤالُ واحد. */
const LIVE_REFRESH_MS = 5_000;

/** قسمُ «الرحلة الجارية» — **البند ٦ (§39٫٦)**.
 *
 * **خريطةٌ داخل الملفّ تعرض الرحلةَ الجارية ومسارَها وموقعَه الحيّ، وتصمت بلا
 * رحلةٍ نشطة** — لا خريطةً فارغة: خريطةٌ بلا شيءٍ عليها تُقرأ عطباً في اللوحة
 * لا «لا رحلةَ الآن»، وهي «لا نتائج» التي ليست «لا بيانات» (§36).
 *
 * **وعلى البثِّ القائم لا على بنيةٍ ثانية**: المسارُ `ride_route_points` نفسُه
 * الذي يُفصل به في النزاع، والموضعُ من مفتاح الحضور في Redis — **ولا عمودَ
 * موقعٍ يُكتب لأجل هذه الشاشة**.
 *
 * **ولـ`admin` وحدَه**: بابُه يقرن هويةً بموقع كالخريطة الحيّة، **والدعمُ لا
 * يفتحه**. وإخفاؤه هنا **راحةٌ لا حماية** — الخلفيةُ ترفض، كما في كلِّ اللوحة.
 */
export function ActiveRideSection({ driverId }: { driverId: string }) {
  const { isAdmin } = useSession();
  // **يُلفّ الجوابُ في كائن**: `ProfileSection` تقرأ `null` «لم يصل بعد»
  // وتعرض دوّارة، **و`null` من هذا الباب تعني «لا رحلة»** — وخلطُ الحالتين
  // هو بعينه ما تحذّر منه هي في رأسها
  const load = useLoader(
    async () => ({ ride: await getDriverLiveRide(driverId) }),
    [driverId],
  );

  if (!isAdmin) return null;

  return (
    <ProfileSection
      title="الرحلة الجارية"
      hint="من بثِّ الموقع نفسِه الذي ترسمه الخريطة الحيّة — وفتحُها مُسجَّلٌ في سجل التدقيق باسمك."
      load={load}
    >
      {({ ride }, reload) => <ActiveRide ride={ride} reload={reload} />}
    </ProfileSection>
  );
}

/** **الاستطلاعُ هنا لا في `ProfileSection`**: بقيةُ الأقسام تقرأ صفوفاً
 *  تتغيّر بفعلِ مشرفٍ، وهذا يقرأ موضعاً يتحرّك بلا أن يفعل أحدٌ شيئاً.
 *
 *  **و`reload` في مرجعٍ لا في اعتمادية**: هي إغلاقٌ جديدٌ في كلِّ رسمة، فوضعُها
 *  في `deps` يهدم المؤقّتَ ويبنيه عند كلِّ جوابٍ يصل — **فيصير الاستطلاعُ
 *  متسارعاً بلا حدّ**.
 */
function ActiveRide({
  ride,
  reload,
}: {
  ride: DriverLiveRide | null;
  reload: () => void;
}) {
  const { config } = useConfig();
  const token = config?.providers.mapbox?.public_token ?? null;
  const latest = useRef(reload);
  latest.current = reload;

  useEffect(() => {
    const timer = window.setInterval(() => latest.current(), LIVE_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, []);

  if (ride === null) {
    return (
      <p className="text-11.5 leading-note text-muted">
        {/* **بلا ضميرٍ يذكر الجنس** (قاعدةُ العربية المجنَّسة): «له» تُقرأ
            خطأً على سائقةٍ معتمدة، **وقِيس ذلك بالعين على درج «هناء
            السائقة»** — والجملةُ تستقيم بلا الضمير أصلاً */}
        لا رحلةَ جاريةً الآن — ولا خريطةَ بلا رحلة. وسجلُّ الرحلات تحت هذا
        القسم.
      </p>
    );
  }

  return (
    <>
      <div className="mb-9 flex flex-wrap items-center gap-6">
        <Badge tone={RIDE_STATUS_TONE[ride.status]}>
          {RIDE_STATUS_LABEL[ride.status]}
        </Badge>
        {/* **«منذ كم» لا «متى»**: القسمُ يُستفتى كلَّ خمس ثوانٍ، والمشرفُ
            يسأل عن الطزاجة. و«لا بثّ» ليست «عند الصفر» */}
        {ride.position === null ? (
          <Badge tone="warn">لا بثَّ الآن</Badge>
        ) : ride.position.stale ? (
          <Badge tone="warn">بثُّه توقّف</Badge>
        ) : (
          <Badge tone="ok">يبثّ الآن</Badge>
        )}
      </div>

      <RouteCanvas
        token={token}
        pickup={{ lat: ride.pickup_lat, lng: ride.pickup_lng }}
        dropoff={{ lat: ride.dropoff_lat, lng: ride.dropoff_lng }}
        route={ride.route}
        position={ride.position}
      />

      <div className="mt-9">
        <Facts
          rows={[
            { label: "من", value: ride.pickup_address ?? "نقطة على الخريطة" },
            { label: "إلى", value: ride.dropoff_address ?? "نقطة على الخريطة" },
            {
              label: "قَبِلها",
              value: ride.accepted_at ? moment(ride.accepted_at) : null,
            },
            {
              label: "انطلقت",
              value: ride.started_at ? moment(ride.started_at) : "لم تنطلق بعد",
            },
            {
              label: "نقاط المسار",
              value:
                ride.route.length === 0
                  ? "لا نقاط بعد"
                  : `${digits(String(ride.route.length))} نقطة`,
            },
            {
              label: "آخر بثّ",
              value:
                ride.position === null
                  ? "لا بثَّ الآن"
                  : ride.position.seconds_since_update === null
                    ? "غير معلوم"
                    : `منذ ${digits(String(ride.position.seconds_since_update))} ثانية`,
            },
          ]}
        />
      </div>

      {ride.route_truncated ? (
        <p className="mt-7 text-10.5 leading-note text-muted">
          المعروضُ أولُ ألف نقطة — المسارُ أطول، وما بعدها لا يُرسم.
        </p>
      ) : null}
    </>
  );
}
