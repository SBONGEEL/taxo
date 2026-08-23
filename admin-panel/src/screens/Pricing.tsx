/** التسعيرة — SPEC القسم 4 (`pricing_rules`) و13/6.
 *
 * **صفٌّ لكل (دولة، فئة مركبة)**، وهو ما تفرضه القاعدة بقيدٍ فريد: فئةٌ بلا
 * صفٍّ ليست «مجانية» بل **لا تُسعَّر أصلاً** — طلبُ رحلةٍ بها يرتدّ. ولذلك
 * تعرض الشاشة الفئتين دائماً وتقول عن الغائبة إنها غير مضبوطة، بدل أن تُخفيها
 * فيبدو الجدولُ مكتملاً.
 *
 * **ولا حسابَ هنا إطلاقاً.** الصيغة `base + km×سعر + دقيقة×سعر` بحدٍّ أدنى،
 * وتُحسب في `services/pricing.py` وحدها (القسم 5/14). فما في هذه الشاشة حقولٌ
 * تُرسل كما تُكتب — ولا «معاينة سعر رحلةٍ نموذجية» تحسبها الواجهة: رقمٌ
 * تحسبه اللوحة يخالف ما يدفعه الراكب يوماً، وأسوأُ من غيابه أن يُصدَّق.
 *
 * **والعمولةُ ليست هنا** وإن كانت في نفس بند القسم 13/6: مصدرها الوحيد
 * `commission_settings` حيث تسكن نسبتُها ونطاقُها معاً، وبابُها شاشة
 * «الإعدادات». وجودُها في شاشتين يعني حقلين ماليين قابلين للاختلاف.
 *
 * **والتعديل يحكم ما يأتي لا ما مضى**: `rides.commission_percent_at_ride`
 * مجمَّدة، والأجرةُ تُحسب لحظة الطلب — فرحلةٌ جارية لا تتغيّر أجرتُها بحفظٍ
 * يقع الآن.
 */

import { GuardBanner } from "@/components/GuardBanner";
import { useCountryConfig } from "@/lib/config";
import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import {
  createPricing,
  deletePricing,
  listPricing,
  updatePricing,
} from "@/api/endpoints";
import type { CountryCode, PricingRule, VehicleCategory } from "@/api/types";
import { Shell } from "@/components/Shell";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { useCountry } from "@/lib/country";
import { FormErrors, useFormError } from "@/lib/form-errors";
import { currencyLabel } from "@/lib/format";
import { useSession } from "@/lib/session";

const CATEGORIES: VehicleCategory[] = ["economy", "comfort"];

const CATEGORY_LABEL: Record<VehicleCategory, string> = {
  economy: "اقتصادية",
  comfort: "مريحة",
};

/** البنودُ الخمسة كما يسمّيها `DESIGN.md` §5.4، بترتيب الصيغة نفسه. */
const FIELDS = [
  { key: "base_fare", label: "التعرفة الأساسية" },
  { key: "price_per_km", label: "لكل كيلومتر" },
  { key: "price_per_min", label: "لكل دقيقة" },
  { key: "minimum_fare", label: "الحد الأدنى" },
  { key: "cancellation_fee", label: "رسوم الإلغاء" },
] as const;

/** حقولُ المحطات الوسيطة (المرحلة 12-ب) — **مجموعةٌ على حدة** لأنها لا تُقرأ
 * مع الخمسة: تلك تسعّر الطريق وهذه تسعّر الوقوف، ومن خلطهما قرأ سبعةَ حقولٍ
 * لا يعرف أيُّها يعمل متى. و`money` منها ما هو مبلغ و`minutes` ما هو زمن. */
const STOP_FIELDS = [
  { key: "stop_fee", label: "رسم المحطة الواحدة", kind: "money" },
  { key: "stop_free_minutes", label: "دقائق مجانية لكل محطة", kind: "minutes" },
  { key: "stop_price_per_min", label: "لكل دقيقة انتظار بعدها", kind: "money" },
  { key: "stop_max_wait_minutes", label: "سقف الانتظار للمحطة", kind: "minutes" },
] as const;

/** حقولُ الوقفة غير المخطَّطة (§5.10-ب) — **مجموعةٌ ثالثةٌ على حدة**.
 *
 * وهي ليست المحطات: تلك يطلبها **الراكبُ قبل الطلب** فتدخل التقدير، وهذه
 * يضغطها **الكبتنُ أثناء الرحلة** بعد أن قُدِّرت الأجرة. وخلطُ المجموعتين يجعل
 * المشرفَ يضبط رقماً ويظنّ أنه ضبط الآخر.
 *
 * **وقيمةُ الدقيقة واحدةٌ للحالتين** — وقفةٍ في منتصف الرحلة وانتظارٍ عند
 * الوصول: دقيقةُ الكبتن الواقف تساوي دقيقتَه الواقفة، ورقمان لمفهومٍ واحدٍ
 * يفترقان. **والمهلةُ المجانيةُ للوصول وحدَه**: الوقفةَ يطلبها الراكبُ صراحةً.
 */
const PAUSE_FIELDS = [
  { key: "pause_price_per_min", label: "لكل دقيقة وقوف", kind: "money" },
  {
    key: "arrival_free_minutes",
    label: "دقائق مجانية عند الوصول",
    kind: "minutes",
  },
  { key: "pause_max_minutes", label: "سقف الوقفة الواحدة", kind: "minutes" },
] as const;

type FieldKey =
  | (typeof FIELDS)[number]["key"]
  | (typeof STOP_FIELDS)[number]["key"]
  | (typeof PAUSE_FIELDS)[number]["key"];

const EMPTY: Record<FieldKey, string> = {
  base_fare: "",
  price_per_km: "",
  price_per_min: "",
  minimum_fare: "",
  cancellation_fee: "",
  stop_fee: "0",
  stop_free_minutes: "0",
  stop_price_per_min: "0",
  stop_max_wait_minutes: "0",
  pause_price_per_min: "0",
  arrival_free_minutes: "0",
  pause_max_minutes: "0",
};

export function PricingScreen() {
  const { country } = useCountry();
  // **تجميدُ التسعير**: يوقف الكتابةَ لا التسعير — والأزرارُ تُعطَّل بعلّتها
  const frozen = useCountryConfig(country)?.features.pricing_writes_enabled === false;
  const { isAdmin } = useSession();

  const [rules, setRules] = useState<PricingRule[] | null>(null);
  // خطأُ النموذج: نصٌّ عامٌّ في الشريط، ووسمٌ على الحقل الذي سمّته الخلفية
  const form = useFormError();
  const error = form.message;
  const setError = form.setMessage;
  const [done, setDone] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRules(null);
    setRules(await listPricing(country));
  }, [country]);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة التسعيرة",
      ),
    );
  }, [load]);

  return (
    <FormErrors value={form.field}>
      <Shell
        title="التسعيرة"
        subtitle="السعرُ يُحسب في الخلفية وحدها — وهذه الحقول ما تُحسب منه"
      >
      <GuardBanner on={frozen} title="التسعيرُ مجمَّد">
        لا يُنشأ صفٌّ ولا يُعدَّل ولا يُحذف حتى يُرفع التجميد من «الإعدادات».
        <b className="text-ink"> والرحلاتُ تُسعَّر بالصفوف القائمة كما هي</b> —
        فلا شيءَ توقّف على الراكب. ورفعُ التجميد لا يستردّ ما كُتب قبله.
      </GuardBanner>
      <ErrorNote message={error} />
      <SuccessNote message={done} />

      {rules === null ? (
        <Spinner className="mx-auto my-38" />
      ) : (
        <div className="mt-12 grid gap-16 lg:grid-cols-2">
          {CATEGORIES.map((category) => (
            <CategoryCard
              key={category}
              country={country}
              category={category}
              rule={rules.find((rule) => rule.vehicle_category === category)}
              canEdit={isAdmin && !frozen}
              onDone={(message) => {
                setDone(message);
                setError(null);
                void load();
              }}
              onError={(caught) => form.capture(caught, "تعذّر الحفظ")}
            />
          ))}
        </div>
      )}

      <p className="mt-16 max-w-prose text-11.5 leading-note text-muted">
        نسبةُ العمولة ونطاقُها في «الإعدادات» لا هنا: مصدرها الوحيد جدولُ
        إعدادات العمولة، حيث يسكن التفعيل والنسبة والنطاق في صفٍّ واحد — فلا
        تنشأ حالتان ماليّتان قابلتان للاختلاف.
      </p>
    </Shell>
    </FormErrors>
  );
}

function CategoryCard({
  country,
  category,
  rule,
  canEdit,
  onDone,
  onError,
}: {
  country: CountryCode;
  category: VehicleCategory;
  rule: PricingRule | undefined;
  canEdit: boolean;
  onDone: (message: string) => void;
  onError: (caught: unknown) => void;
}) {
  const [values, setValues] = useState<Record<FieldKey, string>>(EMPTY);
  const [busy, setBusy] = useState(false);

  // الصفُّ يصل بعد الحفظ أو بعد تبديل الدولة، فتُعاد القيم إليه
  useEffect(() => {
    setValues(
      rule
        ? {
            base_fare: rule.base_fare,
            price_per_km: rule.price_per_km,
            price_per_min: rule.price_per_min,
            minimum_fare: rule.minimum_fare,
            cancellation_fee: rule.cancellation_fee,
            stop_fee: rule.stop_fee,
            stop_free_minutes: String(rule.stop_free_minutes),
            stop_price_per_min: rule.stop_price_per_min,
            stop_max_wait_minutes: String(rule.stop_max_wait_minutes),
            pause_price_per_min: rule.pause_price_per_min,
            arrival_free_minutes: String(rule.arrival_free_minutes),
            pause_max_minutes: String(rule.pause_max_minutes),
          }
        : EMPTY,
    );
  }, [rule]);

  const currency = currencyLabel(country === "JO" ? "JOD" : "LYD");
  const filled = FIELDS.every(({ key }) => values[key].trim() !== "");

  /** الدقائقُ أعدادٌ صحيحة والمبالغُ نصوص — والخلفيةُ ترفض النصَّ مكان العدد. */
  function payload() {
    return {
      base_fare: values.base_fare,
      price_per_km: values.price_per_km,
      price_per_min: values.price_per_min,
      minimum_fare: values.minimum_fare,
      cancellation_fee: values.cancellation_fee,
      stop_fee: values.stop_fee || "0",
      stop_price_per_min: values.stop_price_per_min || "0",
      stop_free_minutes: Number(values.stop_free_minutes || 0),
      stop_max_wait_minutes: Number(values.stop_max_wait_minutes || 0),
      // **والوقفةُ تُرسل مع الحفظ** — حقلٌ يُعرض ولا يُرسل هو حقلٌ يُكتب فيه
      // ثم يعود كما كان، وهو أسوأُ من غيابه
      pause_price_per_min: values.pause_price_per_min || "0",
      arrival_free_minutes: Number(values.arrival_free_minutes || 0),
      pause_max_minutes: Number(values.pause_max_minutes || 0),
    };
  }

  async function save() {
    setBusy(true);
    try {
      if (rule) {
        await updatePricing(rule.id, payload());
        onDone(`حُفظت تسعيرة ${CATEGORY_LABEL[category]}`);
      } else {
        await createPricing({
          country_code: country,
          vehicle_category: category,
          ...payload(),
        });
        onDone(`ضُبطت تسعيرة ${CATEGORY_LABEL[category]}`);
      }
    } catch (caught) {
      onError(caught);
    }
    setBusy(false);
  }

  return (
    <div className="rounded-16 border border-line bg-surface p-18">
      <div className="mb-14 flex items-start gap-12">
        <div className="flex-1">
          <h2 className="text-16 font-bold text-ink">
            {CATEGORY_LABEL[category]}
          </h2>
          <p className="mt-3 text-11.5 leading-note text-muted">
            {rule
              ? "الصفُّ مضبوط — والتعديل يحكم الطلبات القادمة لا رحلةً جارية."
              : "لا تسعيرة لهذه الفئة: طلبُ رحلةٍ بها يرتدّ — «غير مضبوطة» لا «مجانية»."}
          </p>
        </div>
        {rule ? null : (
          <span className="rounded-full border border-warn bg-surface-2 px-10 py-4 text-11 font-semibold text-warn">
            غير مضبوطة
          </span>
        )}
      </div>

      <div className="grid gap-12 md:grid-cols-2">
        {FIELDS.map(({ key, label }) => (
          <Field
            key={key}
            name={key}
            label={`${label} (${currency})`}
            inputMode="decimal"
            dir="ltr"
            disabled={!canEdit}
            value={values[key]}
            onChange={(event) =>
              setValues((current) => ({ ...current, [key]: event.target.value }))
            }
          />
        ))}
      </div>

      <h3 className="mb-10 mt-18 text-13 font-bold text-muted">
        المحطات الوسيطة
      </h3>
      <div className="grid gap-12 md:grid-cols-2">
        {STOP_FIELDS.map(({ key, label, kind }) => (
          <Field
            key={key}
            name={key}
            label={`${label} (${kind === "money" ? currency : "دقيقة"})`}
            inputMode="decimal"
            dir="ltr"
            disabled={!canEdit}
            value={values[key]}
            onChange={(event) =>
              setValues((current) => ({ ...current, [key]: event.target.value }))
            }
          />
        ))}
      </div>
      <p className="mt-8 text-11 leading-note text-muted">
        صفرٌ في الرسمين يعني «بلا رسم»، وصفرٌ في السقف يعني لا سقف لا سقفاً
        مقداره صفر. والأربعةُ تُجمَّد على الرحلة لحظة الطلب، فتعديلُها يحكم ما
        يأتي لا رحلةً واقفةً الآن.
      </p>

      <h3 className="mb-10 mt-18 text-13 font-bold text-muted">
        الوقوف غير المخطَّط
      </h3>
      <div className="grid gap-12 md:grid-cols-2">
        {PAUSE_FIELDS.map(({ key, label, kind }) => (
          <Field
            key={key}
            name={key}
            label={`${label} (${kind === "money" ? currency : "دقيقة"})`}
            inputMode="decimal"
            dir="ltr"
            disabled={!canEdit}
            value={values[key]}
            onChange={(event) =>
              setValues((current) => ({ ...current, [key]: event.target.value }))
            }
          />
        ))}
      </div>
      <p className="mt-8 text-11 leading-note text-muted">
        وقفةٌ يضغطها <b className="text-ink">الكبتنُ أثناء الرحلة</b> — غيرُ
        المحطات التي يطلبها الراكبُ قبلها. <b className="text-ink">وقيمةُ
        الدقيقة واحدةٌ لوقفةِ الطريق ولانتظار الوصول</b>، والمهلةُ المجانيةُ
        للوصول وحدَه: الوقفةَ يطلبها الراكبُ صراحةً بعد أن قُدِّرت أجرتُه.
        وعدّادُ الوصول <b className="text-ink">لا يبدأ إن كان الكبتنُ خارج نطاق
        الالتقاء</b> — وإلا صار «وصلت» الكاذبُ باباً للكسب. والسقفُ يُنبِّه
        الطرفين <b className="text-ink">ولا يُنهي رحلة</b>؛ الإنهاءُ فعلُ الكبتن.
      </p>

      {canEdit ? (
        <div className="mt-16 flex gap-10">
          <Button size="md" disabled={busy || !filled} onClick={() => void save()}>
            حفظ التغييرات
          </Button>
          {rule ? (
            <Button
              size="md"
              variant="ghost"
              disabled={busy}
              onClick={() => {
                setBusy(true);
                deletePricing(rule.id)
                  .then(() => onDone("حُذفت التسعيرة — لا تُطلب هذه الفئة بعدها"))
                  .catch((caught) => {
                    onError(
                      caught instanceof ApiError ? caught.message : "تعذّر الحذف",
                    );
                    setBusy(false);
                  });
              }}
            >
              حذف
            </Button>
          ) : null}
        </div>
      ) : (
        <p className="mt-14 text-11.5 leading-note text-muted">
          التعديلُ لـ admin وحده (القسم 13/8).
        </p>
      )}
    </div>
  );
}
