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

type FieldKey = (typeof FIELDS)[number]["key"];

const EMPTY: Record<FieldKey, string> = {
  base_fare: "",
  price_per_km: "",
  price_per_min: "",
  minimum_fare: "",
  cancellation_fee: "",
};

export function PricingScreen() {
  const { country } = useCountry();
  const { isAdmin } = useSession();

  const [rules, setRules] = useState<PricingRule[] | null>(null);
  const [error, setError] = useState<string | null>(null);
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
    <Shell
      title="التسعيرة"
      subtitle="السعرُ يُحسب في الخلفية وحدها — وهذه الحقول ما تُحسب منه"
    >
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
              canEdit={isAdmin}
              onDone={(message) => {
                setDone(message);
                setError(null);
                void load();
              }}
              onError={setError}
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
  onError: (message: string) => void;
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
          }
        : EMPTY,
    );
  }, [rule]);

  const currency = currencyLabel(country === "JO" ? "JOD" : "LYD");
  const filled = FIELDS.every(({ key }) => values[key].trim() !== "");

  async function save() {
    setBusy(true);
    try {
      if (rule) {
        await updatePricing(rule.id, values);
        onDone(`حُفظت تسعيرة ${CATEGORY_LABEL[category]}`);
      } else {
        await createPricing({
          country_code: country,
          vehicle_category: category,
          ...values,
        });
        onDone(`ضُبطت تسعيرة ${CATEGORY_LABEL[category]}`);
      }
    } catch (caught) {
      onError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
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
