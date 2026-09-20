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
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { useCountry } from "@/lib/country";
import { FormErrors, useFormError } from "@/lib/form-errors";
import { moment, money } from "@/lib/format";
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

      <div className="mt-12">
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
              <span className="flex items-center gap-9">
                <span className="flex size-30 flex-none items-center justify-center rounded-full border border-line bg-surface-2 text-11 font-bold text-ink">
                  {row.name.trim().slice(0, 1)}
                </span>
                <span className="min-w-0 truncate font-semibold text-ink">
                  {row.name}
                </span>
              </span>

              <span dir="ltr" className="text-start text-muted">
                {row.phone}
              </span>

              <span className="flex flex-wrap items-center gap-6">
                {row.is_blocked ? (
                  <Badge tone="danger">محظور</Badge>
                ) : (
                  <Badge tone="ok">نشط</Badge>
                )}
                {!row.phone_verified ? (
                  <Badge tone="warn">رقمٌ غير مُثبت</Badge>
                ) : null}
              </span>

              <span className="text-muted">{moment(row.created_at)}</span>

              <span className="flex justify-end">
                <button
                  type="button"
                  onClick={() => setOpen(row)}
                  className="text-11.5 font-semibold text-ink underline"
                >
                  {OPEN_PROFILE_LABEL}
                </button>
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
    <div className="fixed inset-0 z-50 bg-dim" onClick={onClose}>
      <div
        className="scr absolute bottom-0 start-0 top-0 w-drawer max-w-full animate-slidein border-e border-line bg-surface p-22"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="mb-18 flex items-start gap-12">
          <span className="flex size-48 flex-none items-center justify-center rounded-full border border-line bg-surface-2 text-16 font-bold text-ink">
            {user.name.trim().slice(0, 1)}
          </span>
          <div className="flex-1">
            <div className="text-16 font-bold text-ink">{user.name}</div>
            <div dir="ltr" className="text-12 text-muted">
              {user.phone}
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

        <div className="mb-16 flex flex-wrap gap-6">
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
        </div>

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

        <h3 className="mb-10 mt-18 text-13 font-bold text-muted">المحفظة</h3>
        {wallet === null ? (
          <Spinner className="mx-auto" />
        ) : (
          <div className="rounded-14 border border-line bg-surface-2 px-14 py-12">
            <div className="text-22 font-bold text-ink">
              {money(wallet.balance, wallet.currency)}
            </div>
            <p className="mt-4 text-11 leading-note text-muted">
              رصيدٌ محسوبٌ من الدفتر لا عمودٌ مخزَّن — ولا يُعدَّل قيدٌ بل يُكتب
              قيدٌ مضاد.
            </p>
            {canDecide ? (
              <button
                type="button"
                disabled={busy}
                onClick={() => void toggleFreeze()}
                className={cn(
                  "mt-10 w-full rounded-10 border py-8 text-11.5 font-semibold disabled:opacity-60",
                  wallet.frozen
                    ? "border-line text-ink"
                    : "border-warn text-warn",
                )}
              >
                {wallet.frozen ? "رفع التجميد" : "تجميد محفظة الراكب"}
              </button>
            ) : null}
          </div>
        )}

        {ledger && ledger.length > 0 ? (
          <>
            <h3 className="mb-10 mt-16 text-13 font-bold text-muted">
              آخر الحركات
            </h3>
            <ul className="flex flex-col gap-7">
              {ledger.map((entry) => (
                <li
                  key={entry.id}
                  className="flex items-center gap-10 rounded-12 border border-line px-13 py-9"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block text-12.5 text-ink">
                      {TX_LABEL[entry.type] ?? entry.type}
                    </span>
                    <span className="block text-10.5 text-muted">
                      {moment(entry.created_at)}
                    </span>
                  </span>
                  <span
                    className={cn(
                      "text-12.5 font-semibold",
                      entry.amount.startsWith("-") ? "text-danger" : "text-ok",
                    )}
                  >
                    {digits(entry.amount)}
                  </span>
                </li>
              ))}
            </ul>
          </>
        ) : null}

        <ErrorNote message={error} />
        <SuccessNote message={note} />

        {canDecide ? (
          <div className="mt-16">
            <Field
              label="السبب"
              name="reason"
              placeholder="يدخل سجل التدقيق ولا يصل صاحب الحساب — ويصحب الحظر والتجميد معاً"
              value={reason}
              maxLength={255}
              onChange={(event) => setReason(event.target.value)}
            />
            <div className="mt-12">
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
                  variant="secondary"
                  className="border-danger text-danger"
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
            <p className="mt-8 text-11 leading-note text-muted">
              الحظرُ يسري على الجلسة القائمة فوراً: العمود يُقرأ في كل طلب، فلا
              ينتظر انتهاء التوكن.
            </p>
          </div>
        ) : (
          <p className="mt-16 text-11.5 leading-note text-muted">
            الحظرُ والتجميد لـ admin وحده — القسم 13/8 يعطي الدعمَ قراءةً
            ومعالجةَ نزاعات.
          </p>
        )}
      </div>
    </div>
    </FormErrors>
  );
}
