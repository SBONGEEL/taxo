/** أقسامُ الملفِّ الشخصيِّ المشتركة بين الراكب والكبتن (§37، البند ١).
 *
 * **ولمَ مشتركة**: «حسابٌ ورحلاتٌ ومحفظةٌ ورسومُ إلغاء» أسئلةٌ تُسأل عن أيِّ
 * شخصٍ في المنصة، **والشخصُ قد يكون الاثنين معاً** — نموذجُ الأدوار مجموعةٌ
 * لا عمود (§21). **ونسختان لهذه الأقسام كانتا ستفترقان** كما افترقت خرائطُ
 * الأسماء قبل أن تُجمع في `lib/labels.ts`.
 */

import {
  getUser,
  getWallet,
  listCancellationCharges,
  listRides,
  listWalletTransactions,
} from "@/api/endpoints";
import type { CountryCode, User } from "@/api/types";
import {
  CappedNote,
  Facts,
  MiniList,
  MiniRow,
  ProfileSection,
  useLoader,
} from "@/components/Profile";
import { Badge } from "@/components/ui/Badge";
import { day, moment, money } from "@/lib/format";
import {
  CHARGE_STATUS_LABEL,
  CHARGE_STATUS_TONE,
  PAYMENT_METHOD_LABEL,
  RIDE_STATUS_LABEL,
  RIDE_STATUS_TONE,
  WALLET_TX_LABEL,
} from "@/lib/labels";
import { cn, digits } from "@/lib/utils";

/** كم صفّاً يعرضه قسمٌ في الملفّ — **والباقي في شاشته**.
 *
 * **خمسةٌ لا خمسون**: الملفُّ يجيب «من هذا وما حالُه»، **لا يستبدل الشاشةَ
 * التي تفرز وتُرقّم**. وقائمةٌ طويلةٌ داخل درجٍ تجعل القرارَ الذي فُتح الدرجُ
 * لأجله يهرب تحت التمرير.
 */
const CAP = 5;
/** والدفترُ أطولُ قليلاً — قراءةُ الرصيد تُفهَم بحركاتٍ لا بواحدة. */
const LEDGER_CAP = 8;

const ROLE_LABEL: Record<string, string> = {
  rider: "راكب",
  driver: "كبتن",
  admin: "مشرف",
  support: "دعم",
};

/** قسمُ «الحساب» — **حقائقُ الشخص لا حقائقُ دوره**.
 *
 * **وهذا ما كان ناقصاً حرفياً**: صفُّ الكبتن لا يحمل `is_blocked`، **فكبتنٌ
 * محظورُ الحساب يُقرأ في درجه «معتمد»** — وحالُه أنه لا يستطيع الدخول أصلاً.
 */
export function AccountSection({
  userId,
  known,
  fallbackName,
}: {
  userId: string;
  /** الصفُّ نفسُه حين تملكه الشاشةُ أصلاً — **فلا يُنادى بابٌ لِما بين اليد**.
   *
   *  **وشاشةُ الركّاب تملكه**: صفوفُها `UserOut` من `GET /admin/users` —
   *  **الحمولةُ نفسُها التي يردّها `GET /admin/users/{id}` حرفاً**. فنداءٌ
   *  ثانٍ يعرض دوّارةً لِما هو مرسومٌ في الصفّ فوقه.
   *
   *  **وشاشةُ الكباتن لا تملكه**: صفُّها `AdminDriverRow` بلا `is_blocked`
   *  ولا بريدٍ ولا أدوار — **فالبابُ هناك ليس ترفاً**. */
  known?: User;
  /** الاسمُ كما يعرفه الصفُّ — يُعرض في الشارة قبل أن يُفتح القسم. */
  fallbackName?: string;
}) {
  const load = useLoader(
    () => (known ? Promise.resolve(known) : getUser(userId)),
    [userId, known],
  );
  return (
    <ProfileSection<User>
      title="الحساب"
      hint="حالُ الحساب نفسِه — لا حالُ دوره. وحسابٌ محظورٌ لا يدخل ولا يطلب رحلةً مهما كان اعتمادُه."
      load={load}
      open
    >
      {(user) => (
        <>
          <div className="mb-9 flex flex-wrap gap-6">
            {user.is_blocked ? (
              <Badge tone="danger">محظور</Badge>
            ) : (
              <Badge tone="ok">نشط</Badge>
            )}
            {user.phone_pending ? (
              <Badge tone="warn">رقمٌ محجوز — حسابٌ محدود</Badge>
            ) : user.phone_verified ? null : (
              <Badge tone="warn">رقمٌ غير مُثبت</Badge>
            )}
            {user.roles.map((role) => (
              <Badge key={role} tone="ink">
                {ROLE_LABEL[role] ?? role}
              </Badge>
            ))}
          </div>
          <Facts
            rows={[
              { label: "الاسم", value: user.name || fallbackName },
              { label: "الهاتف", value: user.phone, ltr: true },
              { label: "البريد", value: user.email, ltr: true },
              { label: "السوق", value: user.country_code, ltr: true },
              { label: "تاريخ الإنشاء", value: day(user.created_at) },
              {
                label: "الإشعارُ التسويقيّ",
                value: user.marketing_push_enabled ? "مسموح" : "موقوف بطلبه",
              },
            ]}
          />
        </>
      )}
    </ProfileSection>
  );
}

/** قسمُ «المحفظة والدفتر» — **الرصيدُ مجموعُ الدفتر لا عمود**.
 *
 * **ولا زرَّ تجميدٍ هنا**: للتجميد بابُه في درج الراكب حيث يُكتب سببُه —
 * **وزرٌّ ثانٍ للفعل نفسِه** يجعل نصفَ التجميدات بلا سبب.
 */
export function WalletSection({ userId }: { userId: string }) {
  const load = useLoader(
    async () => ({
      wallet: await getWallet(userId),
      ledger: await listWalletTransactions(userId, LEDGER_CAP),
    }),
    [userId],
  );
  return (
    <ProfileSection
      title="المحفظة والدفتر"
      hint="رصيدٌ محسوبٌ من الدفتر لا عمودٌ مخزَّن — ولا يُعدَّل قيدٌ بل يُكتب قيدٌ مضاد."
      load={load}
    >
      {({ wallet, ledger }) => (
        <>
          <div className="rounded-14 border border-line bg-surface-2 px-14 py-12">
            <div className="text-22 font-bold text-ink">
              {money(wallet.balance, wallet.currency)}
            </div>
            {wallet.frozen ? (
              <p className="mt-6">
                <Badge tone="warn">محفظةٌ مجمّدة</Badge>
              </p>
            ) : null}
          </div>
          <div className="mt-9">
            <MiniList
              rows={ledger}
              keyOf={(entry) => entry.id}
              empty="لا حركةَ في هذا الدفتر بعد."
              render={(entry) => (
                <div className="flex items-center gap-10">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-ink">
                      {WALLET_TX_LABEL[entry.type] ?? entry.type}
                    </span>
                    <span className="block text-10.5 text-muted">
                      {moment(entry.created_at)}
                    </span>
                  </span>
                  <span
                    className={cn(
                      "shrink-0 font-semibold",
                      entry.amount.startsWith("-") ? "text-danger" : "text-ok",
                    )}
                  >
                    {digits(entry.amount)}
                  </span>
                </div>
              )}
            />
            <CappedNote shown={ledger.length} cap={LEDGER_CAP} />
          </div>
        </>
      )}
    </ProfileSection>
  );
}

/** قسمُ «آخرُ الرحلات» — **طرفٌ واحدٌ لا الاثنان**.
 *
 * **و`side` ليس تجميلاً**: حسابٌ بدورين له رحلاتٌ راكباً ورحلاتٌ كبتناً،
 * **وخلطُهما في قائمةٍ واحدةٍ يجعل «ألغاها الراكب» غامضةً** — أهو من ألغى
 * أم أُلغيت عليه.
 */
export function RidesSection({
  side,
  id,
}: {
  side: "rider" | "driver";
  /** `users.id` للراكب، و**`drivers.id` للكبتن** — عمودان مختلفان على `rides`. */
  id: string;
}) {
  const load = useLoader(
    () =>
      listRides(
        side === "rider"
          ? { rider_id: id, limit: CAP }
          : { driver_id: id, limit: CAP },
      ),
    [side, id],
  );
  return (
    <ProfileSection
      title={side === "rider" ? "آخرُ رحلاته راكباً" : "آخرُ رحلاته كبتناً"}
      load={load}
    >
      {(rows) => (
        <>
          <MiniList
            rows={rows}
            keyOf={(ride) => ride.id}
            empty="لا رحلةَ لهذا الطرف بعد."
            render={(ride) => (
              <MiniRow
                title={ride.dropoff_address ?? "بلا عنوانِ وجهة"}
                at={ride.created_at}
                value={RIDE_STATUS_LABEL[ride.status]}
                tone={RIDE_STATUS_TONE[ride.status]}
                note={
                  <>
                    {money(ride.final_fare ?? ride.estimated_fare, ride.currency)}
                    {ride.payment_methods.length > 0
                      ? ` · ${ride.payment_methods
                          .map((method) => PAYMENT_METHOD_LABEL[method])
                          .join("، ")}`
                      : null}
                    {ride.has_open_dispute ? " · نزاعٌ مفتوح" : null}
                  </>
                }
              />
            )}
          />
          <CappedNote shown={rows.length} cap={CAP} />
        </>
      )}
    </ProfileSection>
  );
}

/** قسمُ «رسومُ الإلغاء» — **الطرفان معاً بمعرِّف الشخص**.
 *
 * **وهي أوّلُ دَينٍ بين مستخدمَين** (`services/cancellation.py`): الشخصُ قد
 * يكون الدافعَ أو المستفيد أو **الحاملَ** — فقائمتُه تُقرأ بمعرِّفه لا بدوره.
 */
export function ChargesSection({
  userId,
  country,
}: {
  userId: string;
  country: CountryCode;
}) {
  const load = useLoader(
    () => listCancellationCharges(country, undefined, undefined, userId),
    [country, userId],
  );
  return (
    <ProfileSection
      title="رسومُ الإلغاء"
      hint="دَينٌ بين طرفين تحمله المنصةُ ولا تملكه — ولا يُحصَّل من غير مسار تحصيله."
      load={load}
    >
      {(rows) => (
        <MiniList
          rows={rows}
          keyOf={(charge) => charge.id}
          empty="لا رسمَ إلغاءٍ على هذا الحساب ولا له."
          render={(charge) => (
            <MiniRow
              title={money(charge.amount, charge.currency)}
              at={charge.created_at}
              value={CHARGE_STATUS_LABEL[charge.status]}
              tone={CHARGE_STATUS_TONE[charge.status]}
              note={
                <>
                  {charge.payer_name ? `دافعُه ${charge.payer_name}` : null}
                  {charge.beneficiary_name
                    ? ` · لصالح ${charge.beneficiary_name}`
                    : null}
                  {charge.carrier_name
                    ? ` · بيد ${charge.carrier_name}`
                    : null}
                </>
              }
            />
          )}
        />
      )}
    </ProfileSection>
  );
}
