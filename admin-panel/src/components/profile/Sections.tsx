/** أقسامُ الملفِّ الشخصيِّ المشتركة بين الراكب والكبتن (§37، البند ١).
 *
 * **ولمَ مشتركة**: «حسابٌ ورحلاتٌ ومحفظةٌ ورسومُ إلغاء» أسئلةٌ تُسأل عن أيِّ
 * شخصٍ في المنصة، **والشخصُ قد يكون الاثنين معاً** — نموذجُ الأدوار مجموعةٌ
 * لا عمود (§21). **ونسختان لهذه الأقسام كانتا ستفترقان** كما افترقت خرائطُ
 * الأسماء قبل أن تُجمع في `lib/labels.ts`.
 */

import { useState } from "react";

import { ApiError } from "@/api/client";
import {
  blockUser,
  freezeWallet,
  getUser,
  getWallet,
  listCancellationCharges,
  listRides,
  listWalletTransactions,
  notifyUser,
  unblockUser,
  unfreezeWallet,
  updateUserProfile,
} from "@/api/endpoints";
import type { CountryCode, User, WalletOwnerType } from "@/api/types";
import {
  CappedNote,
  Facts,
  MiniList,
  MiniRow,
  ProfileSection,
  useLoader,
} from "@/components/Profile";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
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
            {/* **حالٌ ثالثةٌ لا تُخلط بالحظر** (§32٫٤): الحظرُ قرارُ مشرفٍ
                بسببٍ مكتوب، **وهذا إيقافٌ آليٌّ يشفي نفسَه بتأكيد الرقم**.
                **وكان الموقوفُ بالحملة يُقرأ هنا «نشطاً»** — والحقلُ تنشره
                الخلفيةُ منذ §32 ولم يقرأه أحد */}
            {user.suspension ? (
              <Badge tone="warn">موقوفٌ بحملة تأكيد الأرقام</Badge>
            ) : null}
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
 * **وصار فيه زرُّ التجميد** (1-أ/6) — وكان مكتوباً هنا أنه لا زرَّ فيه لأن
 * البابَ في درج الراكب **وكان يجمّد الحساب كلَّه، فيقع على محفظة الكبتن
 * ضمناً**. وبعد أن صار التجميدُ صفةَ محفظةٍ، **زرُّ درج الراكب يجمّد محفظةَ
 * الراكب وحدَها** — فلو بقي وحدَه لَما بقي في اللوحة طريقٌ إلى محفظة الكبتن
 * أصلاً: **بابٌ بلا زرّ**، ومحفظةٌ مشبوهةٌ لا يملك مشرفُ المال إيقافَها.
 *
 * **وسببُه معه لا بعده**: تجميدٌ بلا سببٍ في سجلّ التدقيق نصفُ قيد.
 */
export function WalletSection({
  userId,
  side,
  canDecide = false,
}: {
  userId: string;
  /** **أيملك الناظرُ قرارَ المال؟** — والزرُّ يختفي عمّن لا يملكه. */
  canDecide?: boolean;
  /** **أيُّ محفظةٍ يعرض هذا الدرج** — درجُ الكبتن محفظتَه، ودرجُ الراكب
   *  محفظتَه. **وحسابٌ يحمل الدورين بلا إعلانٍ يرتدّ ٤٠٩** فتبقى البطاقةُ
   *  على دوّارةٍ أبداً (§46٫٦). */
  side: WalletOwnerType;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [frozen, setFrozen] = useState<boolean | null>(null);
  const load = useLoader(
    async () => ({
      wallet: await getWallet(userId, side),
      ledger: await listWalletTransactions(userId, LEDGER_CAP, side),
    }),
    [userId, side],
  );
  return (
    <ProfileSection
      title="المحفظة والدفتر"
      hint="رصيدٌ محسوبٌ من الدفتر لا عمودٌ مخزَّن — ولا يُعدَّل قيدٌ بل يُكتب قيدٌ مضاد."
      load={load}
    >
      {({ wallet, ledger }) => {
        const isFrozen = frozen ?? wallet.frozen;
        return (
        <>
          <div className="rounded-14 border border-line bg-surface-2 px-14 py-12">
            <div className="text-22 font-bold text-ink">
              {money(wallet.balance, wallet.currency)}
            </div>
            {isFrozen ? (
              <p className="mt-6">
                <Badge tone="warn">
                  {side === "driver" ? "محفظةُ الكبتن مجمّدة" : "محفظةٌ مجمّدة"}
                </Badge>
              </p>
            ) : null}
            {canDecide ? (
              <>
                <div className="mt-10">
                  <Field
                    label="السبب"
                    name="freeze-reason"
                    placeholder="يدخل سجل التدقيق ولا يصل صاحب الحساب"
                    value={reason}
                    maxLength={255}
                    onChange={(event) => setReason(event.target.value)}
                  />
                </div>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    setBusy(true);
                    const written = reason.trim() || undefined;
                    void (
                      isFrozen
                        ? unfreezeWallet(userId, written, side)
                        : freezeWallet(userId, written, side)
                    )
                      .then((next) => setFrozen(next.frozen))
                      .finally(() => setBusy(false));
                  }}
                  className={cn(
                    "mt-10 w-full rounded-10 border py-8 text-11.5 font-semibold disabled:opacity-60",
                    isFrozen ? "border-line text-ink" : "border-warn text-warn",
                  )}
                >
                  {isFrozen ? "رفع التجميد" : "تجميد محفظة الكبتن"}
                </button>
              </>
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
        );
      }}
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


/** قسمُ «التحكّم والتواصل» — **البند ١١ (§39٫١١، §46)**.
 *
 * **ثلاثةُ أفعالٍ في مكانٍ واحدٍ هو الملفُّ نفسُه**: تصحيحُ بياناته، وإيقافُه
 * ورفعُه بسببٍ مكتوب، ورسالةٌ إليه. **ومن أراد واحداً منها كان يبحث عن شاشةٍ
 * أخرى** — أو لا يجد باباً أصلاً.
 *
 * ## وثلاثةُ حدودٍ مكتوبة
 *
 * **١) الحقلان لا أكثر**: الهاتفُ مُعرِّفُ الدخول، والسوقُ يُختم على كلِّ
 * رحلةٍ ودفعة، **والأدوارُ والحظرُ وجنسُ الكبتن لكلٍّ بابُه وحارسُه** —
 * وحقلٌ رابعٌ هنا يقفز فوق واحدٍ منها.
 *
 * **٢) وكتابةُ البريد تُسقط إثباتَه**: المُثبَتُ وحدَه يحجز العنوان ويصلح
 * قناةَ استرجاع (§31)، **فبريدٌ يكتبه مشرفٌ ويبقى مُثبَتاً بابُ استيلاءٍ على
 * حساب**. **والخلفيةُ هي من تُسقطه، والشاشةُ تقول ذلك ولا تفعله.**
 *
 * **٣) والرسالةُ ليست حملة**: تمرّ بمسار FCM القائم — صندوقُ الوارد ثمّ Push
 * لمن كان تطبيقُه مغلقاً — **ونصُّها يدخل سجلَّ التدقيق كاملاً**.
 */
export function ControlsSection({
  userId,
  known,
  onChanged,
  showBlock = false,
}: {
  userId: string;
  /** الصفُّ نفسُه حين تملكه الشاشةُ — **فلا يُنادى بابٌ لِما بين اليد**. */
  known?: User;
  onChanged: (message: string) => void;
  /** **الإيقافُ يُرسم حيث لا زرَّ له سلفاً**: درجُ الراكب يحمل زرَّه ومعه
   *  حقلُ سببٍ يشترك فيه مع تجميد المحفظة — **وزرٌّ ثانٍ للفعل نفسِه في
   *  الدرج نفسِه يجعل نصفَ الحظور بلا سبب**. **ودرجُ الكبتن لا زرَّ فيه
   *  أصلاً**: `POST /admin/users/{id}/block` بابٌ لم يكن يبلغه أحدٌ من هناك،
   *  فحسابُ كبتنٍ لا يُحظر من اللوحة البتّة. */
  showBlock?: boolean;
}) {
  const load = useLoader(
    () => (known ? Promise.resolve(known) : getUser(userId)),
    [userId, known],
  );
  return (
    <ProfileSection<User>
      title="التحكّم والتواصل"
      hint="تصحيحُ بياناته، ورسالةٌ إليه — والهاتفُ والسوقُ لا يُحرَّران من هنا."
      load={load}
    >
      {(user, reload) => (
        <Controls
          user={user}
          showBlock={showBlock}
          onChanged={(message) => {
            reload();
            onChanged(message);
          }}
        />
      )}
    </ProfileSection>
  );
}

/** جسدُ القسم — **مفصولٌ لأن الحالةَ تُبتدأ من صفٍّ وصل**، ومكوّنٌ يبتدئ
 *  حالتَه من خاصيّةٍ تصل متأخّرةً يبقى على القيمة الأولى. */
function Controls({
  user,
  onChanged,
  showBlock,
}: {
  user: User;
  onChanged: (message: string) => void;
  showBlock: boolean;
}) {
  const [name, setName] = useState(user.name);
  const [email, setEmail] = useState(user.email ?? "");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  async function run(action: () => Promise<unknown>, message: string) {
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      await action();
      setNote(message);
      onChanged(message);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر التنفيذ");
    } finally {
      setBusy(false);
    }
  }

  const edited =
    name.trim() !== user.name || email.trim() !== (user.email ?? "");

  return (
    <section className="mt-14 rounded-14 border border-line bg-surface-2 p-14">
      <h3 className="mb-10 text-13 font-bold text-ink">التحكّم والتواصل</h3>
      <ErrorNote message={error} />
      <SuccessNote message={note} />

      <div className="grid grid-cols-2 gap-10">
        <Field
          label="الاسم"
          name="profile_name"
          value={name}
          maxLength={120}
          onChange={(event) => setName(event.target.value)}
        />
        <Field
          label="البريد"
          name="profile_email"
          dir="ltr"
          value={email}
          maxLength={320}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>
      <p className="mt-6 text-10.5 leading-note text-muted">
        وكتابةُ بريدٍ من هنا تُسقط إثباتَه — يبقى بياناً يُراسَل به حتى يُثبته
        صاحبُه. والهاتفُ والسوقُ لا يُحرَّران: أوّلُهما مُعرّفُ الدخول،
        والثاني مختومٌ على كلِّ رحلةٍ ودفعة.
      </p>
      <Button
        className="mt-10"
        size="sm"
        variant="secondary"
        disabled={busy || !edited || name.trim().length < 2}
        onClick={() =>
          void run(
            () =>
              updateUserProfile(user.id, {
                name: name.trim(),
                email: email.trim() || null,
              }),
            "حُفظ التعديل — والقيمةُ قبل وبعد في سجل التدقيق.",
          )
        }
      >
        احفظ البيانات
      </Button>

      <h4 className="mb-8 mt-16 text-11.5 font-bold text-muted">
        رسالةٌ إلى صاحب الحساب
      </h4>
      <Field
        label="العنوان"
        name="message_title"
        value={title}
        maxLength={80}
        onChange={(event) => setTitle(event.target.value)}
      />
      <div className="mt-8">
        <label className="mb-6 block text-11.5 text-muted">النص</label>
        <textarea
          name="message_body"
          rows={3}
          value={body}
          maxLength={600}
          onChange={(event) => setBody(event.target.value)}
          className="w-full rounded-12 border border-line bg-surface px-12 py-10 text-12 leading-note text-ink"
        />
      </div>
      <p className="mt-6 text-10.5 leading-note text-muted">
        تصل صندوقَ الوارد في تطبيقه، وتُدفع إلى جهازه إن كان مغلقاً — ونصُّها
        يُحفظ في سجل التدقيق كما كُتب.
      </p>
      <Button
        className="mt-10"
        size="sm"
        variant="secondary"
        disabled={busy || title.trim().length < 2 || body.trim().length < 2}
        onClick={() =>
          void run(async () => {
            await notifyUser(user.id, {
              title: title.trim(),
              body: body.trim(),
            });
            setTitle("");
            setBody("");
          }, "أُرسلت الرسالة إلى صندوق وارده.")
        }
      >
        أرسِل
      </Button>

      {showBlock ? (
        <>
          <h4 className="mb-8 mt-16 text-11.5 font-bold text-muted">
            حالُ الحساب
          </h4>
          <Field
            label="السبب"
            name="block_reason"
            placeholder="يدخل سجل التدقيق ولا يصل صاحب الحساب"
            value={reason}
            maxLength={255}
            onChange={(event) => setReason(event.target.value)}
          />
          <div className="mt-10">
            {user.is_blocked ? (
              <Button
                size="sm"
                variant="secondary"
                disabled={busy}
                onClick={() =>
                  void run(
                    () => unblockUser(user.id, reason.trim() || undefined),
                    "رُفع الحظر عن الحساب.",
                  )
                }
              >
                رفع الحظر
              </Button>
            ) : (
              <Button
                size="sm"
                variant="secondary"
                className="border-danger text-danger"
                disabled={busy || reason.trim().length < 3}
                onClick={() =>
                  void run(
                    () => blockUser(user.id, reason.trim()),
                    "حُظر الحساب — لا يدخل ولا يطلب رحلة.",
                  )
                }
              >
                احظر الحساب
              </Button>
            )}
          </div>
          <p className="mt-8 text-10.5 leading-note text-muted">
            الحظرُ يسري على الجلسة القائمة فوراً — العمودُ يُقرأ في كلِّ طلب.
            **وهو غيرُ إيقاف حملة تأكيد الأرقام**: ذاك يُفكّ بتأكيد الرقم
            وحدَه، بلا مشرف.
          </p>
        </>
      ) : null}
    </section>
  );
}
