/** أقسامُ الملفِّ التي تخصّ الكبتنَ وحدَه (§37، البند ١).
 *
 * **والفرقُ بينها وبين المشتركة ليس الدور بل الكيان**: مركبةٌ واشتراكٌ وسلفةٌ
 * ومستحقٌّ أشياءُ لا وجودَ لها إلا لصفٍّ في `drivers` — **ومعرِّفُها
 * `drivers.id` لا `users.id`**، وهو الفرقُ الذي أسقط ثلاثةَ بحوثٍ في هذه
 * الشجرة (`ARCHITECTURE.md`: «passing the latter silently returns zero»).
 */

import {
  listAdvances,
  listDriverDebts,
  listDriverVehicles,
  listSubscriptions,
} from "@/api/endpoints";
import {
  CappedNote,
  Facts,
  MiniList,
  MiniRow,
  ProfileSection,
  useLoader,
} from "@/components/Profile";
import { Badge } from "@/components/ui/Badge";
import { day, days, daysUntil, money } from "@/lib/format";
import {
  ADVANCE_STATUS_LABEL,
  ADVANCE_STATUS_TONE,
  DEBT_STATUS_LABEL,
  DEBT_STATUS_TONE,
  PAYMENT_METHOD_LABEL,
  SUBSCRIPTION_DURATION_LABEL,
} from "@/lib/labels";
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
