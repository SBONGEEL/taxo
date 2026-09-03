/** عروضُ اشتراكات الكباتن — البند ٥٤، والفروعُ الستةُ كما أُجيبت.
 *
 * **وشاشةٌ مستقلةٌ لا لوحٌ في «الاشتراكات»**: تلك تعرض ما وقع (باقاتٌ بيعت
 * واشتراكاتٌ سُجّلت)، وهذه تُنشئ **قراراً مالياً** — نسبةً وميزانيةَ تنازل.
 * وخلطُهما يجعل زرَّ «أنشئ عرضاً» بجوار جدولِ ما بيع، فيُضغط بحسبانه تسجيلاً.
 *
 * **وثلاثةُ أشياء تُرسم هنا لأنها قرارات:**
 *
 * 1. **جدولُ التنازل يقول «إيرادٌ لم يُقبض» لا «مصروف»**: خصمُ الرحلة تتحمّله
 *    الشركةُ عن الراكب فهو مصروف، وهذا تنازلٌ عن إيرادنا. وخلطُهما في تقريرٍ
 *    واحدٍ يجعل محاسباً يجمع رقمين لا يُجمعان.
 * 2. **وسمُ «تسويةٍ يدوية»**: عددُ اشتراكاتٍ خالف فيها المشرفُ المبلغَ
 *    المعبَّأ — يُعرض ولا يُمنع ولا يُطلب له سبب. التقريرُ يفرّق بين خصم العرض
 *    وقرار المشرف، ولا يصادر قراره.
 * 3. **الإطفاءُ لا الحذف**: عرضٌ اشترى به عشرون كبتناً يمحو حذفُه سببَ خصومهم،
 *    والقاعدةُ ترفضه أصلاً (`RESTRICT`). فالزرُّ «أطفئ» ولا زرَّ حذف.
 */

import { useCallback, useEffect, useState } from "react";

import {
  createSubscriptionOffer,
  listPlans,
  listSubscriptionOffers,
  deleteOffer,
  updateSubscriptionOffer,
} from "@/api/endpoints";
import type { SubscriptionOffer, SubscriptionPlan } from "@/api/types";
import { OfferGrants } from "@/components/OfferGrants";
import { Badge } from "@/components/ui/Badge";
import { ConfirmDelete } from "@/components/ui/ConfirmDelete";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { Field, Select } from "@/components/ui/Field";
import { DurationField, MoneyField } from "@/components/ui/Inputs";
import { Shell } from "@/components/Shell";
import { useCountry } from "@/lib/country";
import { currencyOf, day, money } from "@/lib/format";
import { digits } from "@/lib/utils";
import { FormErrors, useFormError } from "@/lib/form-errors";
import { useSession } from "@/lib/session";

const AUDIENCE_LABEL: Record<SubscriptionOffer["audience"], string> = {
  all: "كل الكباتن",
  new_driver: "من لم يشترك قطُّ",
  lapsed: "المنقطعون",
  manual: "بمنحٍ يدوي",
};

export function OffersScreen() {
  const { country } = useCountry();
  const { isAdmin } = useSession();
  const form = useFormError();
  const [rows, setRows] = useState<SubscriptionOffer[] | null>(null);
  const [granting, setGranting] = useState<SubscriptionOffer | null>(null);
  const [deleting, setDeleting] = useState<SubscriptionOffer | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [name, setName] = useState("");
  const [percent, setPercent] = useState("");
  const [audience, setAudience] =
    useState<SubscriptionOffer["audience"]>("all");
  const [lapsedDays, setLapsedDays] = useState("30");
  const [maxUses, setMaxUses] = useState("1");
  const [budget, setBudget] = useState("");
  // **الخطّةُ هي المدّة**: عرضٌ على الأسبوعيِّ أسبوعٌ مجّاني، وعلى الشهريِّ شهر
  const [planId, setPlanId] = useState("");
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);

  // **سقط `currency` حين صار الحقلُ `MoneyField`**: كان علامةً محلولةً تُقحَم
  // في نصِّ التسمية، **والحقلُ يعرض عملتَه بنفسه** — ولا موضعَ آخرَ يقرؤها.
  // **والسوقُ يُقرأ من `currencyOf` لا من شرطٍ مكتوبٍ بيد** (`JO ? JOD : LYD`
  // كان سيكذب أوّلَ سوقٍ ثالث).

  const load = useCallback(async () => {
    setRows(null);
    // **الخطّةُ من سوقها**: الخلفيةُ ترفض خطّةً من سوقٍ آخر، والقائمةُ هنا
    // تمنع أن يُعرض الخطأُ أصلاً — فلا يُختبر بالرفض
    const [offers, allPlans] = await Promise.all([
      listSubscriptionOffers(country),
      listPlans(),
    ]);
    setPlans(allPlans.filter((plan) => plan.country_code === country));
    setRows(offers);
  }, [country]);

  useEffect(() => {
    load().catch((caught) => form.capture(caught, "تعذّر قراءة العروض"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]);

  async function create() {
    setBusy(true);
    form.clear();
    setDone(null);
    try {
      await createSubscriptionOffer(country, {
        name: name.trim(),
        discount_value: percent,
        audience,
        lapsed_days: audience === "lapsed" ? Number(lapsedDays) : null,
        max_uses_per_driver: Number(maxUses),
        total_budget: budget.trim() || null,
        plan_id: planId || null,
      });
      setName("");
      setPercent("");
      setBudget("");
      setDone("أُنشئ العرض — ولا يُطبَّق حتى يُشعَل مفتاحُ العروض في الإعدادات");
      await load();
    } catch (caught) {
      form.capture(caught, "تعذّر إنشاء العرض");
    } finally {
      setBusy(false);
    }
  }

  /** **تبديلُ المدّة على عرضٍ قائم** — وهو ما لم يكن ممكناً بأيِّ باب:
   *  `OfferUpdate` لم يكن فيه `plan_id`، فالمدّةُ تُختار مرّةً وتُقفل. */
  async function setPlan(offer: SubscriptionOffer, value: string) {
    try {
      await updateSubscriptionOffer(offer.id, { plan_id: value || null });
      setDone("بُدّلت مدّةُ العرض — ومن اشترى بخصمه احتفظ به");
      await load();
    } catch (caught) {
      form.capture(caught, "تعذّر التعديل");
    }
  }

  async function toggle(offer: SubscriptionOffer) {
    try {
      await updateSubscriptionOffer(offer.id, { is_active: !offer.is_active });
      setDone(
        offer.is_active
          ? "أُطفئ العرض — ومن اشترى بخصمه احتفظ به"
          : "أُعيد تشغيل العرض",
      );
      await load();
    } catch (caught) {
      form.capture(caught, "تعذّر التعديل");
    }
  }

  const ready = name.trim().length >= 2 && Number(percent) > 0;

  return (
    <FormErrors value={form.field}>
      <Shell
        title="عروض الاشتراكات"
        subtitle="خصمٌ بالنسبة على سعر الباقة — والتنازلُ إيرادٌ لم يُقبض لا مصروف"
      >
        <ErrorNote message={form.message} />
        <SuccessNote message={done} />

        {isAdmin ? (
          <section className="mb-18 rounded-16 border border-line bg-surface p-18">
            <h2 className="mb-14 text-16 font-bold text-ink">عرضٌ جديد</h2>
            <div className="grid grid-cols-2 gap-12">
              <Field
                label="اسم العرض"
                name="name"
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
              <Field
                label="نسبة الخصم ٪"
                name="discount_value"
                dir="ltr"
                inputMode="decimal"
                value={percent}
                onChange={(event) =>
                  setPercent(event.target.value.replace(/[^0-9.]/g, ""))
                }
              />
              {/* **الخطّةُ هي مدّةُ العرض** (قرارُ المالك 2026-08-29): «شهرٌ
                  مجانيّ» و«أسبوعٌ مجانيّ» ليسا إعدادَين مختلفَين بل خصمٌ واحدٌ
                  على خطّةٍ مختلفة. **وكان هذا الحقلُ غائباً عن الشاشة كلِّها**،
                  فالمدّةُ تُختار مرّةً في الإنشاء ولا تُبدَّل — بابٌ بلا زرّ. */}
              <Select
                label="الخطّة (هي المدّة)"
                name="plan_id"
                value={planId}
                onChange={(event) => setPlanId(event.target.value)}
              >
                <option value="">كل الخطط</option>
                {plans.map((plan) => (
                  <option key={plan.id} value={plan.id}>
                    {plan.name}
                  </option>
                ))}
              </Select>
              <Select
                label="الجمهور"
                name="audience"
                value={audience}
                onChange={(event) =>
                  setAudience(
                    event.target.value as SubscriptionOffer["audience"],
                  )
                }
              >
                {(
                  Object.keys(AUDIENCE_LABEL) as SubscriptionOffer["audience"][]
                ).map((key) => (
                  <option key={key} value={key}>
                    {AUDIENCE_LABEL[key]}
                  </option>
                ))}
              </Select>
              {audience === "lapsed" ? (
                <DurationField
                  label="انقطعت تغطيته منذ"
                  name="lapsed_days"
                  wire="day"
                  value={Number(lapsedDays) || 0}
                  onChange={(next) => setLapsedDays(String(next))}
                />
              ) : (
                <Field
                  label="مرات الاستعمال لكل كبتن (صفر = بلا حدّ)"
                  name="max_uses_per_driver"
                  dir="ltr"
                  inputMode="numeric"
                  value={maxUses}
                  onChange={(event) =>
                    setMaxUses(event.target.value.replace(/\D/g, ""))
                  }
                />
              )}
              {/* **العملةُ من الحقل لا من التسمية** (§39٫١٢٫٢): كانت
                  مقحمةً في نصِّ التسمية، **فتُقرأ جزءاً من اسم الحقل لا وحدةً
                  للرقم**. والمصفاةُ باقيةٌ — `MoneyField` لا يمنع حرفاً. */}
              <MoneyField
                label="سقف التنازل الكلي — فارغٌ = بلا سقف"
                name="total_budget"
                value={budget}
                onChange={(next) => setBudget(next.replace(/[^0-9.]/g, ""))}
                // **الرمزُ لا العلامة**: `currency` أعلاه **علامةٌ محلولة**
                // (`currencyLabel`)، و`MoneyField` يحلّها بنفسه — **فتمريرُها
                // يعطي فراغاً**، وهو عينُ ما يمنعه `check:money`
                currency={currencyOf(country)}
              />
            </div>
            <p className="mt-10 text-11.5 leading-note text-muted">
              الخصمُ يُحسب في الخلفية على القنوات الأربع. والكاشُ وكليك تُعبَّأ
              فيهما القيمةُ ولا تُفرض — وما يُسجَّل هو ما قُبض فعلاً.
            </p>
            <Button
              className="mt-14"
              size="md"
              disabled={!ready}
              loading={busy}
              onClick={() => void create()}
            >
              أنشئ العرض
            </Button>
          </section>
        ) : null}

        {rows === null ? (
          <Spinner className="mx-auto my-38" />
        ) : rows.length === 0 ? (
          <p className="py-30 text-center text-13 text-muted">
            لا عروضَ في هذه الدولة بعد.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-16 border border-line">
            <table className="w-full text-13">
              <thead className="bg-surface-2 text-11.5 text-muted">
                <tr>
                  <th className="p-12 text-right">العرض</th>
                  <th className="p-12 text-right">الجمهور</th>
                  <th className="p-12 text-right">الخصم</th>
                  <th className="p-12 text-right">بيع</th>
                  <th className="p-12 text-right">المدّة</th>
                  <th className="p-12 text-right">قبل الخصم</th>
                  <th className="p-12 text-right">تنازلنا</th>
                  <th className="p-12 text-right">تسويات يدوية</th>
                  <th className="p-12 text-right">الحال</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((offer) => (
                  <tr key={offer.id} className="border-t border-line">
                    <td className="p-12 font-bold text-ink">{offer.name}</td>
                    <td className="p-12 text-muted">
                      {AUDIENCE_LABEL[offer.audience]}
                      {offer.audience === "lapsed" && offer.lapsed_days
                        ? ` (${offer.lapsed_days} يوماً)`
                        : ""}
                    </td>
                    {/* عرفُ اللوحة: أرقامٌ عربيةٌ وعلامةُ ٪ عربية — كما في
                        `Rides` و`Reports`، لا `%` لاتينية */}
                    <td className="p-12">
                      {digits(offer.discount_value)}٪
                    </td>
                    <td className="p-12">{offer.subscriptions_sold}</td>
                    <td className="p-12">
                      {isAdmin ? (
                        <Select
                          label=""
                          name={`plan_${offer.id}`}
                          value={offer.plan_id ?? ""}
                          onChange={(event) =>
                            void setPlan(offer, event.target.value)
                          }
                        >
                          <option value="">كل الخطط</option>
                          {plans.map((plan) => (
                            <option key={plan.id} value={plan.id}>
                              {plan.name}
                            </option>
                          ))}
                        </Select>
                      ) : (
                        <span className="text-muted">
                          {plans.find((plan) => plan.id === offer.plan_id)?.name ??
                            "كل الخطط"}
                        </span>
                      )}
                    </td>
                    {/* **العملةُ تُمرَّر خاماً**: `money` تحلّ التسميةَ بنفسها،
                        وتمريرُ تسميةٍ محلولةٍ يطبع الرقمَ عارياً */}
                    <td className="p-12">
                      {money(offer.total_list_price, country === "JO" ? "JOD" : "LYD")}
                    </td>
                    <td className="p-12 font-bold text-ink">
                      {money(offer.total_given_up, country === "JO" ? "JOD" : "LYD")}
                    </td>
                    <td className="p-12">
                      {offer.manual_adjustments > 0 ? (
                        <Badge tone="warn">{offer.manual_adjustments}</Badge>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                    <td className="p-12">
                      <div className="flex items-center gap-10">
                        <Badge tone={offer.is_active ? "ok" : "muted"}>
                          {offer.is_active ? "يعمل" : "مُطفأ"}
                        </Badge>
                        {isAdmin ? (
                          <button
                            type="button"
                            className="text-11.5 font-bold text-accent-ink"
                            onClick={() => void toggle(offer)}
                          >
                            {offer.is_active ? "أطفئ" : "شغّل"}
                          </button>
                        ) : null}
                        {/* **والمنحُ للجمهور اليدويِّ وحدَه**: زرٌّ على عرضٍ
                            جمهورُه محسوبٌ يعمل ثم يرتدّ بـ٤٢٢، وهو ما يعلّم
                            المشرفَ إعادةَ المحاولة بدل أن يقول له إن الباب
                            ليس هنا */}
                        {isAdmin && offer.audience === "manual" ? (
                          <button
                            type="button"
                            className="text-11.5 font-bold text-accent-ink"
                            onClick={() => setGranting(offer)}
                          >
                            امنح
                          </button>
                        ) : null}
                        {/* **الحذفُ لِما لم يُستعمل** (§39٫٤): `RESTRICT` في
                            القاعدة يمنع محوَ عرضٍ اشترى به أحد، **والخادمُ
                            يجيب بالعربية ويقول العدد** بدل خطأ قيدٍ لا يُفهم */}
                        {isAdmin ? (
                          <button
                            type="button"
                            className="text-11.5 font-bold text-danger"
                            onClick={() => setDeleting(offer)}
                          >
                            احذف
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {rows && rows.length > 0 ? (
          <p className="mt-14 text-11.5 leading-note text-muted">
            «تنازلنا» إيرادٌ لم يُقبض لا مصروفٌ دُفع — ولا يُجمع مع خصومات
            الرحلات في تقريرٍ واحد. و«تسويةٌ يدوية» أن المشرفَ سجّل مبلغاً غيرَ
            المعبَّأ عند الكاش أو كليك، وهي حريتُه لا خطؤه.
            {rows.some((row) => row.ends_at)
              ? ` وأقربُ عرضٍ ينتهي: ${day(
                  rows.filter((row) => row.ends_at).sort()[0].ends_at as string,
                )}.`
              : ""}
          </p>
        ) : null}

        {deleting ? (
          <ConfirmDelete
            what={`عرض «${deleting.name}»`}
            count={deleting.subscriptions_sold}
            note="ومن اشترى بخصمه لا يُمسّ — والبديلُ إطفاؤه، فيبقى سببُ خصومهم مقروءاً."
            onClose={() => setDeleting(null)}
            onConfirm={async () => {
              try {
                await deleteOffer(deleting.id);
                setDeleting(null);
                setDone("حُذف العرض — ولم يكن قد استُعمل");
                await load();
              } catch (caught) {
                form.capture(caught, "تعذّر الحذف");
                setDeleting(null);
              }
            }}
          />
        ) : null}

        {granting ? (
          <OfferGrants
            offerId={granting.id}
            offerName={granting.name}
            country={country}
            onClose={() => setGranting(null)}
            onError={(message) => form.setMessage(message)}
            onGranted={setDone}
          />
        ) : null}
      </Shell>
    </FormErrors>
  );
}
