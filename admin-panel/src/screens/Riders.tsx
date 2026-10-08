/** الركّاب — SPEC القسم 13/3، و`DESIGN.md` §3.3/3.5.
 *
 * ثلاثة أشياء يفعلها القسم 13/3 وثلاثةٌ فقط: **قائمة، حظر، تجميد محفظة**.
 * والاثنان الأخيران **بابان لا باب**، والخلط بينهما يفقد نصف المعنى:
 *
 * - **الحظر يغلق الحساب كلَّه**: يُقرأ في كل طلبٍ مُصادَق عليه، فلا دخولَ ولا
 *   رحلة ولا تجديدَ جلسة.
 * - **وتجميدُ المحفظة يوقف حركةَ المال وحدها** ويبقي صاحبَها راكباً يدفع
 *   نقداً (القسم 4/13.3). ذاك عقابٌ على السلوك وهذا احتواءٌ لمالٍ مشبوه،
 *   والدمجُ بينهما يعني إمّا أن يُغلق حسابٌ لأجل شكٍّ مالي أو أن يبقى مالٌ
 *   مشبوهٌ يتحرك لأن صاحبَه لم يستحق الإغلاق.
 *
 * **والحسابُ غير محقق الرقم موسومٌ وقابلٌ للفلترة** (القسم 13/3): حالةٌ لا تقع
 * إلا بإطفاء مفتاح الطوارئ، ولا تُعالَج إن لم تُرَ.
 *
 * **والرصيد يُقرأ في الدرج لا في الصف**: هو مجموعُ الدفتر لا عمود، فنداءٌ لكل
 * صفٍّ في صفحةٍ من خمسين يعني خمسين استعلامَ جمع — نفس السبب الذي جعل عدَّ
 * وثائق الكبتن يقع داخل استعلام القائمة.
 *
 * **ولا زرَّ إنشاء حساب**: الحسابُ يُنشأ بإثبات رقمٍ من التطبيق (القسم 15/أ)،
 * وحسابٌ تفتحه اللوحة حسابٌ بلا إثباتٍ لرقمه.
 */

import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import {
  blockUser,
  freezeWallet,
  getUser,
  getWallet,
  listUsers,
  listWalletTransactions,
  unblockUser,
  unfreezeWallet,
} from "@/api/endpoints";
import type { User, Wallet, WalletTransaction } from "@/api/types";
import {
  AccountSection,
  ChargesSection,
  ControlsSection,
  RidesSection,
} from "@/components/profile/Sections";
import { BulkNotify } from "@/components/BulkNotify";
import { Shell } from "@/components/Shell";
import { Pills, Table, TableSearch } from "@/components/Table";
import { Badge } from "@/components/ui/Badge";
import { TestAccountBadge } from "@/components/ui/TestAccountBadge";
import { Button } from "@/components/ui/Button";
import { Drawer } from "@/components/ui/Drawer";
import { Field } from "@/components/ui/Field";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { useCountry } from "@/lib/country";
import { FormErrors, useFormError } from "@/lib/form-errors";
import { currencyLabel, moment } from "@/lib/format";
import { NO_RESULTS, useSearch } from "@/lib/search";
import { useSession } from "@/lib/session";
import { WALLET_TX_LABEL } from "@/lib/labels";
import { OPEN_PROFILE_LABEL } from "@/components/profile/OpenProfile";
import { digits, cn } from "@/lib/utils";

/** فلترةُ عرضٍ خالصة لا مرآةَ تعدادٍ في الخلفية — ولا قيمةَ فيها تساوي قيمةَ
 * عمود. القيم مسبوقةٌ بـ`only_` عمداً كي لا تتصادم أسماؤها مع `active` في
 * `SubscriptionStatus` ونظائرها: `check:enums` يرفض اتحاداً يخلط قيمةَ تعدادٍ
 * حقيقيةً بقيمةٍ مخترعة — وهي بصمةُ الاتحاد المنسوخ ثم المزيد عليه. وإعفاءٌ
 * بالاسم كان سيُطفئ الحارسَ عن كل اتحادٍ يُسمّى `Filter` بعدها.
 */
type RiderFilter = "only_active" | "only_blocked" | "only_unverified";

// **من `lib/labels.ts`** — و**بمرآةِ التعداد لا `Record<string, string>`**:
// الشكلُ الفضفاضُ كان يمرّر نوعاً جديداً بلا ترجمةٍ فيُعرض خاماً في كشفٍ ماليّ
const TX_LABEL = WALLET_TX_LABEL;

const COLUMNS = "1.6fr 1.2fr 1fr 1fr 1fr";

export function RidersScreen() {
  const { country } = useCountry();
  const { isAdmin } = useSession();

  const [filter, setFilter] = useState<RiderFilter | "all">("all");
  const search = useSearch();
  const [rows, setRows] = useState<User[] | null>(null);
  const [open, setOpen] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  // **الاختيارُ يُمسح كلَّما تغيّرت القائمة** (تحت، في `load`): من اختار
  // خمسةً ثمّ بدّل المرشِّح **لا يرى ما اختار**، وزرُّ فعلٍ يعمل على غائبٍ
  // عن الشاشة هو «لا يُعتمد ما لا يُرى» بعينه
  const [picked, setPicked] = useState<ReadonlySet<string>>(new Set());

  // **يفتح ما يقوله العنوان** — وجهةُ البحث العامّ (§39٫١٢٫٤).
  //
  // **ويُقرأ بمعرّفه لا من الصفحة المعروضة**: `GET /admin/users/{id}` بابٌ
  // قائمٌ منذ §37، **وحسابٌ خارج الصفحة الأولى كان لا يُفتح أبداً** لو انتظرنا
  // القائمة. **وصفرُ بابٍ جديدٍ بُني لهذا.**
  const [params, setParams] = useSearchParams();
  const wanted = params.get("open");
  useEffect(() => {
    if (wanted === null) return;
    let alive = true;
    getUser(wanted)
      .then((user) => {
        if (alive) setOpen(user);
      })
      .catch((caught) =>
        setError(
          caught instanceof ApiError ? caught.message : "تعذّرت قراءةُ الحساب",
        ),
      )
      // **ويُمحى المُعامل بعد فتحه**: عنوانٌ يبقى يقول «افتح» يعيد فتحَ الدرج
      // كلَّما أُغلق — **فيصير الإغلاقُ لا يُغلق**
      .finally(() => {
        if (!alive) return;
        params.delete("open");
        setParams(params, { replace: true });
      });
    return () => {
      alive = false;
    };
  }, [wanted, params, setParams]);

  const load = useCallback(async () => {
    setRows(null);
    // **ولا يبقى اختيارٌ لصفوفٍ لم تعد معروضة** — لا فعلَ على ما لا يُرى
    setPicked(new Set());
    setRows(
      await listUsers({
        role: "rider",
        country_code: country,
        is_blocked:
          filter === "only_blocked"
            ? true
            : filter === "only_active"
              ? false
              : undefined,
        phone_verified: filter === "only_unverified" ? false : undefined,
        q: search.term,
      }),
    );
  }, [country, filter, search.term]);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة القائمة",
      ),
    );
  }, [load]);

  return (
    <Shell
      title="الركّاب"
      subtitle="حظرُ الحساب وتجميدُ المحفظة بابان مختلفان — والأول يغلق كل شيء والثاني يوقف المال وحده"
    >
      <Pills
        value={filter}
        onPick={(key) => setFilter(key)}
        options={[
          { key: "all", label: "الكل" },
          { key: "only_active", label: "نشطون" },
          { key: "only_blocked", label: "محظورون" },
          { key: "only_unverified", label: "رقمٌ غير مُثبت" },
        ]}
      />

      <ErrorNote message={error} />
      <SuccessNote message={done} />

      <div className={error || done ? "mt-12" : undefined}>
        <Table
          toolbar={
            <TableSearch
              value={search.text}
              onChange={search.setText}
              placeholder="ابحث باسم الراكب أو رقمه…"
            />
          }
          searching={search.searching}
          noResults={NO_RESULTS}
          columns={COLUMNS}
          headers={["الراكب", "الهاتف", "الحالة", "منذ", ""]}
          rows={rows}
          keyOf={(row) => row.id}
          // **الاختيارُ للمشرف وحدَه**: الإرسالُ يحتاج `users.manage`،
          // **وعمودٌ يُرى ثمّ يرتدّ ٤٠٣ يعلّم إعادةَ المحاولة** بدل أن يقول
          // إن القرارَ ليس له (قاعدةُ `Drivers.tsx`)
          selection={
            isAdmin
              ? {
                  selected: picked,
                  onChange: setPicked,
                  actions: (selected, clear) => (
                    <BulkNotify
                      userIds={[...selected]}
                      onClear={clear}
                      onDone={setDone}
                    />
                  ),
                }
              : undefined
          }
          empty={{
            title: "لا ركّاب في هذه الحال",
            hint: "بدّل الفلترة أو الدولة، أو امسح نصّ البحث.",
          }}
          render={(row) => (
            <>
              <span className="ad-person">
                <span className="ad-person-avatar" aria-hidden="true">
                  {row.name.trim().slice(0, 1)}
                </span>
                <span className="ad-person-text">
                  <span className="ad-person-name">{row.name}</span>
                </span>
              </span>

              <span dir="ltr" className="ad-ltr ad-tone-muted">
                {row.phone}
              </span>

              <span className="ad-chips">
                {row.is_blocked ? (
                  <Badge tone="danger">محظور</Badge>
                ) : (
                  <Badge tone="ok">نشط</Badge>
                )}
                {!row.phone_verified ? (
                  <Badge tone="warn">رقمٌ غير مُثبت</Badge>
                ) : null}
                {/* **راكبُ تجربة** (SPEC §٦٥-ج) */}
                <TestAccountBadge isTest={row.is_test} />
              </span>

              <span className="ad-tone-muted">{moment(row.created_at)}</span>

              {/* **زرٌّ ثانويٌّ لا رابط** (A06): الملفُّ هو فعلُ الصفّ الوحيد، وكذلك «الوثائق والقرار» في قائمة الكباتن */}
              <span className="ad-row-end">
                <Button size="sm" variant="secondary" onClick={() => setOpen(row)}>
                  {OPEN_PROFILE_LABEL}
                </Button>
              </span>
            </>
          )}
        />
      </div>

      {open ? (
        <RiderDrawer
          user={open}
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

/** الدرج — `DESIGN.md` §3.5. */
function RiderDrawer({
  user,
  canDecide,
  onClose,
  onChanged,
}: {
  user: User;
  canDecide: boolean;
  onClose: () => void;
  onChanged: (message: string) => void;
}) {
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [ledger, setLedger] = useState<WalletTransaction[] | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const form = useFormError();
  const error = form.message;
  const setError = form.setMessage;
  const [note, setNote] = useState<string | null>(null);

  const loadWallet = useCallback(async () => {
    // **ويُعلَن الجانب** (§46٫٦): درجُ الراكب يعرض محفظتَه، **وحسابٌ يحمل
    // الدورين كان يرتدّ `409 wallet_owner_undecided` فتبقى البطاقةُ على
    // دوّارةٍ أبداً**. **والخلفيةُ كانت مُحقّة** — والناقصُ الإعلان.
    setWallet(await getWallet(user.id, "rider"));
    setLedger(await listWalletTransactions(user.id, 10, "rider"));
  }, [user.id]);

  useEffect(() => {
    loadWallet().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة المحفظة",
      ),
    );
  }, [loadWallet]);

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

  /** التجميدُ لا يغلق الدرج: قرارٌ على المحفظة وحدها، والصفحةُ لا تتغيّر به. */
  async function toggleFreeze() {
    if (wallet === null) return;
    setBusy(true);
    setError(null);
    try {
      const written = reason.trim() || undefined;
      // **ومحفظةُ الراكب باسمها** (1-أ/6): هذا درجُ الراكب، والتجميدُ صار
      // صفةَ محفظةٍ — فمحفظةُ كبتنه (إن كان كبتناً) لا تتأثّر، **ولها زرُّها
      // في درجه**. وبلا الإعلان يرتدّ البابُ ٤٠٩ لحاملِ الدورين
      setWallet(
        wallet.frozen
          ? await unfreezeWallet(user.id, written, "rider")
          : await freezeWallet(user.id, written, "rider"),
      );
      setNote(
        wallet.frozen ? "رُفع تجميد محفظة الراكب" : "جُمّدت محفظة الراكب",
      );
    } catch (caught) {
      form.capture(caught, "تعذّر التنفيذ");
    }
    setBusy(false);
  }

  return (
    <FormErrors value={form.field}>
    <Drawer
      name={user.name}
      phone={user.phone}
      badges={
        <>
          {user.is_blocked ? (
            <Badge tone="danger">محظور</Badge>
          ) : (
            <Badge tone="ok">نشط</Badge>
          )}
          {user.phone_verified ? null : (
            <Badge tone="warn">رقمٌ غير مُثبت</Badge>
          )}
          {wallet?.frozen ? (
            <Badge tone="warn">محفظةُ الراكب مجمّدة</Badge>
          ) : null}
          <TestAccountBadge isTest={user.is_test} />
        </>
      }
      onClose={onClose}
    >
        {/* **الملفُّ الشخصيُّ الكامل** (§37، البند ١) — **ومقابلُ درج الكبتن
            لا نسخةٌ منه**: ما يخصّ الكيان (مركبةٌ واشتراكٌ وسلفة) لا وجودَ له
            للراكب، وما يخصّ الشخصَ مشتركٌ في `profile/Sections.tsx`.
            **والمحفظةُ تبقى مرسومةً هنا لا في القسم المشترك**: هي حاملةُ زرِّ
            التجميد وسببِه، **وقسمٌ ثانٍ يعرض الرصيدَ نفسَه** يجعل الرقمَ
            مكتوباً مرّتين في شاشةٍ واحدةٍ ويفترق أوّلَ ما يُحدَّث أحدُهما. */}
        {/* **والصفُّ يُمرَّر لأن الشاشةَ تملكه**: `GET /admin/users` يردّ
            `UserOut` نفسَه — فنداءٌ ثانٍ يعرض دوّارةً لِما هو مرسومٌ فوقه */}
        <AccountSection userId={user.id} known={user} fallbackName={user.name} />
        <RidesSection side="rider" id={user.id} />
        <ChargesSection userId={user.id} country={user.country_code} />
        {/* **البند ١١** (§39٫١١، §46) — **وبلا زرِّ حظرٍ هنا**: الدرجُ يحمله
            أسفلَه ومعه حقلُ سببٍ يشترك فيه مع تجميد المحفظة، **وزرٌّ ثانٍ
            للفعل نفسِه في الدرج نفسِه يجعل نصفَ الحظور بلا سبب** */}
        <ControlsSection
          userId={user.id}
          known={user}
          onChanged={(message) => setNote(message)}
        />

        <h3 className="ad-dh">المحفظة</h3>
        {wallet === null ? (
          <div className="ad-sec-loading">
            <Spinner />
          </div>
        ) : (
          <div className="ad-box">
            {/* **الرصيدُ رقمُ الهوية** (Unbounded) وعملتُه بعده بالخافت — مصوغاً كما وصل من الدفتر */}
            <div className="ad-amount">
              <span className="ad-num ad-balance">{digits(wallet.balance)}</span>
              <span className="ad-cur">{currencyLabel(wallet.currency)}</span>
            </div>
            <p className="ad-box-hint">
              رصيدٌ محسوبٌ من الدفتر لا عمودٌ مخزَّن — ولا يُعدَّل قيدٌ بل يُكتب
              قيدٌ مضاد.
            </p>
            {canDecide ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => void toggleFreeze()}
                className={cn(
                  "ad-btn ad-btn-sm mt-12",
                  wallet.frozen ? "ad-btn-secondary" : "ad-btn-warn",
                )}
              >
                {wallet.frozen ? "رفع التجميد" : "تجميد محفظة الراكب"}
              </button>
            ) : null}
          </div>
        )}

        {ledger && ledger.length > 0 ? (
          <>
            <h3 className="ad-dh">آخر الحركات</h3>
            <div className="ad-box ad-box-list">
              <ul className="ad-mini">
                {ledger.map((entry) => (
                  <li key={entry.id}>
                    <div className="ad-mini-row">
                      <span className="ad-mini-main">
                        <span className="ad-mini-title">
                          {TX_LABEL[entry.type] ?? entry.type}
                        </span>
                        <span className="ad-mini-at">
                          {moment(entry.created_at)}
                        </span>
                      </span>
                      <span
                        className={cn(
                          "ad-ledger-amount",
                          entry.amount.startsWith("-")
                            ? "ad-tone-danger"
                            : "ad-tone-ok",
                        )}
                      >
                        {digits(entry.amount)}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </>
        ) : null}

        {error || note ? (
          <div className="ad-stack mt-12">
            <ErrorNote message={error} />
            <SuccessNote message={note} />
          </div>
        ) : null}

        {canDecide ? (
          <div className="ad-drawer-reason">
            <Field
              label="السبب"
              name="reason"
              placeholder="يدخل سجل التدقيق ولا يصل صاحب الحساب — ويصحب الحظر والتجميد معاً"
              value={reason}
              maxLength={255}
              onChange={(event) => setReason(event.target.value)}
            />
            <div className="ad-decide">
              {user.is_blocked ? (
                <Button
                  size="md"
                  variant="secondary"
                  disabled={busy}
                  onClick={() =>
                    void run(
                      () => unblockUser(user.id, reason.trim() || undefined),
                      "رُفع الحظر عن الحساب",
                    )
                  }
                >
                  رفع الحظر
                </Button>
              ) : (
                <Button
                  size="md"
                  variant="danger"
                  disabled={busy || reason.trim().length < 3}
                  onClick={() =>
                    void run(
                      () => blockUser(user.id, reason.trim()),
                      "حُظر الحساب — لا يدخل ولا يطلب رحلة",
                    )
                  }
                >
                  حظر الحساب
                </Button>
              )}
            </div>
            <p className="ad-hint">
              الحظرُ يسري على الجلسة القائمة فوراً: العمود يُقرأ في كل طلب، فلا
              ينتظر انتهاء التوكن.
            </p>
          </div>
        ) : (
          <p className="ad-drawer-note">
            الحظرُ والتجميد لـ admin وحده — القسم 13/8 يعطي الدعمَ قراءةً
            ومعالجةَ نزاعات.
          </p>
        )}
    </Drawer>
    </FormErrors>
  );
}
