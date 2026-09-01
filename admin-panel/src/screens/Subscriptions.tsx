/** الاشتراكات والباقات — SPEC القسم 8 و13/5 و13/6.
 *
 * لوحان في شاشة، وهما وجها القاعدة نفسها: **الباقة سعرٌ يُعرض، والاشتراك مالٌ
 * وصل**. وأربع قواعد من القسم 8 مرسومةٌ هنا لأنها تحكم ما يقع:
 *
 * 1. **لا حالة «بانتظار الدفع»**: صفُّ الاشتراك لا يُنشأ إلا وقد وصل ماله.
 *    فزرُّ التسجيل يقول «سُجِّل بعد القبض» لا «أنشئ اشتراكاً» — والقناتان
 *    الفوريتان (المحفظة والبطاقة) ليستا هنا أصلاً: يفتحهما الكبتن من تطبيقه
 *    ويشهد عليهما الدفترُ أو المزود.
 * 2. **السريان سؤالٌ عن الساعة لا عن عمود**: المهمة الدورية تمر كل خمس دقائق،
 *    فصفٌّ انقضى وقتُه قد يظل محمولاً على `active` بينهما. ولذلك يُقرأ
 *    «سارٍ/منتهٍ» من `expires_at` مقابل الآن، ويُقال حين يخالف العمودُ الساعة
 *    بدل أن يُعرض العمود وحده فيُقرأ خطأً.
 * 3. **التجديد صفٌّ جديد يُكدَّس**: من جدّد مبكراً له صفّان متتاليان، فلا
 *    يُقرأ الصفُّ الأقدم «انتهى» — والتغطيةُ **أقصى** `expires_at` لا أحدثُها.
 * 4. **حذفُ الباقة لا يمسّ اشتراكاً قائماً**: الاشتراك يحمل مبلغه ومدته
 *    المدفوعة، والباقةُ عرضٌ لما يُشترى بعدُ. ولذلك «تعطيل» أولى من حذف،
 *    والشاشة تقولها.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError } from "@/api/client";
import {
  createPlan,
  deletePlan,
  listDrivers,
  listPlans,
  listSubscriptions,
  recordSubscription,
  updatePlan,
} from "@/api/endpoints";
import type {
  AdminDriverRow,
  CountryCode,
  PaymentMethod,
  Subscription,
  SubscriptionDurationType,
  SubscriptionPlan,
  SubscriptionStatus,
} from "@/api/types";
import { Shell } from "@/components/Shell";
import { Pills, Table } from "@/components/Table";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Checkbox, Field, Select } from "@/components/ui/Field";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { useCountry } from "@/lib/country";
import { FormErrors, useFormError } from "@/lib/form-errors";
import { currencyLabel, day, days, daysUntil, money } from "@/lib/format";
import { useSession } from "@/lib/session";
import { digits } from "@/lib/utils";

const DURATION_LABEL: Record<SubscriptionDurationType, string> = {
  daily: "يومية",
  weekly: "أسبوعية",
  monthly: "شهرية",
};

/** ثوابتُ كودٍ في الخلفية لا إعدادات — «الشهرية» هي مدتُها (القسم 8). */
const DURATION_DAYS: Record<SubscriptionDurationType, number> = {
  daily: 1,
  weekly: 7,
  monthly: 30,
};

const METHOD_LABEL: Record<PaymentMethod, string> = {
  cash: "كاش",
  cliq: "كليك",
  card: "بطاقة",
  wallet: "محفظة",
  // لا تُشترى بها باقةٌ — لكن الخريطةَ شاملةٌ للتعداد فلا تظهر سلسلةٌ خام
  promo: "خصم كوبون",
  share: "خصم مشاركة",
};

/** القناتان اليدويتان وحدهما تُسجَّلان من اللوحة (القسم 8). */
const MANUAL_METHODS: PaymentMethod[] = ["cash", "cliq"];

const SUB_COLUMNS = "1.3fr 1fr 0.9fr 1.1fr 0.9fr 0.9fr";
const PLAN_COLUMNS = "1.4fr 0.9fr 0.9fr 0.8fr 1fr";

/** حالُ الصف كما تقوله **الساعة** — والعمود يُذكر حين يخالفها. */
function coverage(row: Subscription): { label: string; tone: Tone } {
  const left = daysUntil(row.expires_at);
  if (left <= 0) {
    return row.status === "active"
      ? { label: "انقضى — لم يُعلَّم بعد", tone: "warn" }
      : { label: "منتهٍ", tone: "muted" };
  }
  if (left <= 1) return { label: "ينتهي غداً", tone: "warn" };
  return { label: `سارٍ · ${days(left)}`, tone: "ok" };
}

export function SubscriptionsScreen() {
  const { country } = useCountry();
  const { isAdmin } = useSession();

  const [filter, setFilter] = useState<SubscriptionStatus | "all">("all");
  const [rows, setRows] = useState<Subscription[] | null>(null);
  const [plans, setPlans] = useState<SubscriptionPlan[] | null>(null);
  const [recording, setRecording] = useState(false);
  const form = useFormError();
  const error = form.message;
  const setError = form.setMessage;
  const [done, setDone] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRows(null);
    setRows(
      await listSubscriptions({
        country_code: country,
        subscription_status: filter === "all" ? undefined : filter,
      }),
    );
  }, [country, filter]);

  const loadPlans = useCallback(async () => {
    setPlans(await listPlans());
  }, []);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة الاشتراكات",
      ),
    );
  }, [load]);

  useEffect(() => {
    loadPlans().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة الباقات",
      ),
    );
  }, [loadPlans]);

  const countryPlans = useMemo(
    () => (plans ?? []).filter((plan) => plan.country_code === country),
    [plans, country],
  );

  const activeNow = (rows ?? []).filter(
    (row) => daysUntil(row.expires_at) > 0,
  ).length;

  return (
    <FormErrors value={form.field}>
    <Shell
      title="الاشتراكات والباقات"
      subtitle="لا اشتراك ساري = لا رحلات — والفحصُ في التوزيع بالساعة لا بعمود الحالة"
      actions={
        isAdmin ? (
          <button
            type="button"
            onClick={() => setRecording(true)}
            className="rounded-13 border border-line px-16 py-11 text-13 font-semibold text-ink"
          >
            تسجيل اشتراكٍ مقبوض
          </button>
        ) : undefined
      }
    >
      <ErrorNote message={error} />
      <SuccessNote message={done} />

      <section className="mb-22">
        <div className="mb-12 flex items-end justify-between gap-16">
          <h2 className="text-16 font-bold text-ink">المشتركون</h2>
          <span className="text-12 text-muted">
            سارٍ الآن في هذه الصفحة: {digits(String(activeNow))}
          </span>
        </div>

        <Pills
          value={filter}
          onPick={(key) => setFilter(key)}
          options={[
            { key: "all", label: "الكل" },
            { key: "active", label: "نشطة" },
            { key: "expired", label: "منتهية" },
          ]}
        />

        <Table
          columns={SUB_COLUMNS}
          headers={["الباقة", "البداية", "المدة", "الانتهاء", "المبلغ", "الحالة"]}
          rows={rows}
          keyOf={(row) => row.id}
          empty={{
            title: "لا اشتراكات في هذه الحال",
            hint: "بدّل الفلترة أو الدولة من الرأس.",
          }}
          render={(row) => {
            const state = coverage(row);
            return (
              <>
                <span className="min-w-0">
                  <span className="block truncate font-semibold text-ink">
                    {row.plan_name}
                  </span>
                  <span className="block text-10.5 text-muted">
                    {METHOD_LABEL[row.payment_method]}
                    {row.reference ? ` · ${row.reference}` : ""}
                  </span>
                </span>

                <span className="text-muted">{day(row.starts_at)}</span>

                <span className="text-muted">
                  {DURATION_LABEL[row.duration_type]}
                </span>

                <span className="text-muted">{day(row.expires_at)}</span>

                <span className="font-semibold text-ink">
                  {money(row.amount_paid, row.currency)}
                </span>

                <span>
                  <Badge tone={state.tone}>{state.label}</Badge>
                </span>
              </>
            );
          }}
        />
      </section>

      <section>
        <h2 className="mb-12 text-16 font-bold text-ink">الباقات</h2>
        <PlansPanel
          country={country}
          plans={plans === null ? null : countryPlans}
          canEdit={isAdmin}
          onChanged={(message) => {
            setDone(message);
            void loadPlans();
          }}
          onError={(caught) => form.capture(caught, "تعذّر التنفيذ")}
        />
      </section>

      {recording ? (
        <RecordModal
          country={country}
          plans={countryPlans}
          onClose={() => setRecording(false)}
          onDone={(message) => {
            setDone(message);
            setRecording(false);
            void load();
          }}
        />
      ) : null}
    </Shell>
    </FormErrors>
  );
}

function PlansPanel({
  country,
  plans,
  canEdit,
  onChanged,
  onError,
}: {
  country: CountryCode;
  plans: SubscriptionPlan[] | null;
  canEdit: boolean;
  onChanged: (message: string) => void;
  onError: (caught: unknown) => void;
}) {
  const [adding, setAdding] = useState(false);

  async function run(action: () => Promise<unknown>, message: string) {
    try {
      await action();
      onChanged(message);
    } catch (caught) {
      onError(caught);
    }
  }

  return (
    <>
      <Table
        height="auto"
        columns={PLAN_COLUMNS}
        headers={["الباقة", "المدة", "السعر", "الحالة", ""]}
        rows={plans}
        keyOf={(plan) => plan.id}
        empty={{
          title: "لا باقات في هذه الدولة",
          hint: "بلا باقةٍ لا يشتري كبتنٌ اشتراكاً — ولا يستقبل طلباً.",
        }}
        render={(plan) => (
          <>
            <span className="min-w-0 truncate font-semibold text-ink">
              {plan.name}
            </span>
            <span className="text-muted">
              {DURATION_LABEL[plan.duration_type]} ·{" "}
              {days(DURATION_DAYS[plan.duration_type])}
            </span>
            <span className="font-semibold text-ink">
              {money(plan.price, plan.currency)}
            </span>
            <span>
              {plan.is_active ? (
                <Badge tone="ok">مفعّلة</Badge>
              ) : (
                <Badge tone="muted">متوقفة</Badge>
              )}
            </span>
            <span className="flex justify-end gap-10">
              {canEdit ? (
                <>
                  <button
                    type="button"
                    onClick={() =>
                      void run(
                        () => updatePlan(plan.id, { is_active: !plan.is_active }),
                        plan.is_active ? "أُوقفت الباقة" : "فُعّلت الباقة",
                      )
                    }
                    className="text-11.5 font-semibold text-ink underline"
                  >
                    {plan.is_active ? "إيقاف" : "تفعيل"}
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      void run(() => deletePlan(plan.id), "حُذفت الباقة")
                    }
                    className="text-11.5 font-semibold text-danger underline"
                  >
                    حذف
                  </button>
                </>
              ) : null}
            </span>
          </>
        )}
      />

      {canEdit ? (
        <>
          <p className="mt-8 text-11 leading-note text-muted">
            الإيقافُ أولى من الحذف: الباقةُ المتوقفة لا تُشترى وتبقى
            اشتراكاتُها مقروءةً باسمها، والحذفُ ترفضه القاعدة ما دام لها اشتراك.
          </p>
          {adding ? (
            <PlanForm
              country={country}
              onClose={() => setAdding(false)}
              onDone={(message) => {
                setAdding(false);
                onChanged(message);
              }}
              onError={onError}
            />
          ) : (
            <button
              type="button"
              onClick={() => setAdding(true)}
              className="mt-12 rounded-13 border border-line px-16 py-11 text-13 font-semibold text-ink"
            >
              + باقة جديدة
            </button>
          )}
        </>
      ) : null}
    </>
  );
}

function PlanForm({
  country,
  onClose,
  onDone,
  onError,
}: {
  country: CountryCode;
  onClose: () => void;
  onDone: (message: string) => void;
  onError: (caught: unknown) => void;
}) {
  const [name, setName] = useState("");
  const [duration, setDuration] = useState<SubscriptionDurationType>("monthly");
  const [price, setPrice] = useState("");
  const [active, setActive] = useState(true);
  const [busy, setBusy] = useState(false);

  return (
    <div className="mt-14 rounded-16 border border-line bg-surface p-18">
      <div className="grid gap-12 md:grid-cols-3">
        <Field
          label="الاسم"
          name="name"
          value={name}
          maxLength={120}
          onChange={(event) => setName(event.target.value)}
        />
        <Select
          label="المدة"
          name="duration_type"
          value={duration}
          onChange={(event) =>
            setDuration(event.target.value as SubscriptionDurationType)
          }
        >
          {(
            ["daily", "weekly", "monthly"] as SubscriptionDurationType[]
          ).map((value) => (
            <option key={value} value={value}>
              {DURATION_LABEL[value]}
            </option>
          ))}
        </Select>
        <Field
          label={`السعر (${currencyLabel(country === "JO" ? "JOD" : "LYD")})`}
          name="price"
          inputMode="decimal"
          dir="ltr"
          value={price}
          onChange={(event) => setPrice(event.target.value)}
        />
      </div>

      <div className="mt-12 max-w-prose">
        <Checkbox checked={active} onChange={setActive}>
          <span className="text-12.5 text-ink">مفعّلة — تظهر للكباتن للشراء</span>
        </Checkbox>
      </div>

      <p className="mt-10 text-11 leading-note text-muted">
        العملةُ تُشتق من الدولة في الخلفية ولا تُرسل من هنا — والسعرُ يُكتب نصّاً
        كما هو ولا يمر بأي حساب في الواجهة.
      </p>

      <div className="mt-14 flex gap-10">
        <Button
          size="md"
          disabled={busy || name.trim().length < 2 || price.trim() === ""}
          onClick={() => {
            setBusy(true);
            createPlan({
              country_code: country,
              name: name.trim(),
              duration_type: duration,
              price: price.trim(),
              is_active: active,
            })
              .then(() => onDone("أُضيفت الباقة"))
              .catch((caught) => {
                onError(caught);
                setBusy(false);
              });
          }}
        >
          حفظ
        </Button>
        <Button size="md" variant="ghost" onClick={onClose}>
          إلغاء
        </Button>
      </div>
    </div>
  );
}

/** تسجيلُ اشتراكٍ **قُبض** كاشاً أو كليكاً — بعد وصول المال لا قبله. */
function RecordModal({
  country,
  plans,
  onClose,
  onDone,
}: {
  country: CountryCode;
  plans: SubscriptionPlan[];
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [search, setSearch] = useState("");
  const [matches, setMatches] = useState<AdminDriverRow[] | null>(null);
  const [driver, setDriver] = useState<AdminDriverRow | null>(null);
  const [planId, setPlanId] = useState(plans[0]?.id ?? "");
  const [method, setMethod] = useState<PaymentMethod>("cash");
  const [amount, setAmount] = useState("");
  const [reference, setReference] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function find() {
    setError(null);
    try {
      // المعتمدون وحدهم: عدُّ الأيام يبدأ فوراً، فبيعُه لمن ينتظر الموافقة
      // يحرق أيامه في الانتظار (القسم 8)
      setMatches(
        await listDrivers({
          country_code: country,
          status: "approved",
          q: search.trim(),
          limit: 10,
        }),
      );
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر البحث");
    }
  }

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
            <h2 className="text-16 font-bold text-ink">تسجيل اشتراكٍ مقبوض</h2>
            <p className="mt-3 text-11.5 leading-note text-muted">
              يُسجَّل بعد قبض المال: لا حالة «بانتظار الدفع» في هذا الجدول،
              كما لا يتغيّر رصيدٌ قبل تأكيد شحنته.
            </p>
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

        <div className="mt-12 flex items-end gap-9">
          <div className="flex-1">
            <Field
              label="السائق"
              placeholder="اسمٌ أو رقم هاتف"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <button
            type="button"
            onClick={() => void find()}
            className="rounded-13 border border-line px-16 py-13 text-13 font-semibold text-ink"
          >
            ابحث
          </button>
        </div>

        {matches !== null ? (
          matches.length === 0 ? (
            <p className="mt-10 text-11.5 leading-note text-muted">
              لا سائق معتمَدٌ بهذا الاسم — ولا يُباع اشتراكٌ لغير معتمَد: عدُّ
              أيامه يبدأ فوراً فيحترق في الانتظار.
            </p>
          ) : (
            <ul className="mt-10 flex flex-col gap-7">
              {matches.map((row) => (
                <li key={row.driver_id}>
                  <button
                    type="button"
                    onClick={() => setDriver(row)}
                    className={
                      driver?.driver_id === row.driver_id
                        ? "flex w-full items-center gap-10 rounded-12 border border-ink px-13 py-9 text-start"
                        : "flex w-full items-center gap-10 rounded-12 border border-line px-13 py-9 text-start"
                    }
                  >
                    <span className="flex-1 text-12.5 text-ink">{row.name}</span>
                    <span dir="ltr" className="text-11 text-muted">
                      {row.phone}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )
        ) : null}

        <div className="mt-14 grid gap-12 md:grid-cols-2">
          <Select
            label="الباقة"
            value={planId}
            onChange={(event) => setPlanId(event.target.value)}
          >
            <option value="">اختر باقة</option>
            {plans.map((plan) => (
              <option key={plan.id} value={plan.id}>
                {plan.name} — {plan.price} {currencyLabel(plan.currency)}
              </option>
            ))}
          </Select>

          <Select
            label="القناة"
            value={method}
            onChange={(event) =>
              setMethod(event.target.value as PaymentMethod)
            }
          >
            {MANUAL_METHODS.map((value) => (
              <option key={value} value={value}>
                {METHOD_LABEL[value]}
              </option>
            ))}
          </Select>

          <Field
            // **النصُّ صار كاذباً بعد البند ٥٤**: تركُه فارغاً لم يعد يعني
            // «سعر الباقة» بل **المبلغَ بعد خصم العرض** إن انطبق عرضٌ على هذا
            // الكبتن (قِيس: فارغاً أعطى ١٫٢٠٠ لا ١٫٥٠٠). ونصٌّ يصف سلوكاً
            // انتهى يجعل المشرفَ يحصّل رقماً ويسجّل غيرَه.
            label="المبلغ (اتركه فارغاً بالمبلغ المستحق بعد الخصم)"
            inputMode="decimal"
            dir="ltr"
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
          />

          <Field
            label="المرجع (إيصال الكاش أو حوالة كليك)"
            value={reference}
            maxLength={120}
            onChange={(event) => setReference(event.target.value)}
          />
        </div>

        <p className="mt-10 text-11 leading-note text-muted">
          والمحفظةُ والبطاقةُ ليستا هنا: يفتحهما الكبتن من تطبيقه ويشهد عليهما
          الدفترُ أو المزود، فلا شيء فيهما ينتظر إنساناً.
        </p>

        <div className="mt-16">
          <Button
            size="md"
            disabled={busy || driver === null || planId === ""}
            onClick={() => {
              if (driver === null) return;
              setBusy(true);
              recordSubscription({
                driver_id: driver.driver_id,
                plan_id: planId,
                method,
                amount_paid: amount.trim() || null,
                reference: reference.trim() || null,
              })
                .then(() => onDone("سُجّل الاشتراك — بدأ سريانه"))
                .catch((caught) => {
                  setError(
                    caught instanceof ApiError
                      ? caught.message
                      : "تعذّر التسجيل",
                  );
                  setBusy(false);
                });
            }}
          >
            تسجيل
          </Button>
        </div>
      </div>
    </div>
  );
}
