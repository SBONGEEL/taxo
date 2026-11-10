/** التسعيرة — SPEC القسم 4 (`pricing_rules`) و13/6.
 *
 * **صفٌّ لكل (دولة، فئة مركبة)**، وهو ما تفرضه القاعدة بقيدٍ فريد: فئةٌ بلا
 * صفٍّ ليست «مجانية» بل **لا تُسعَّر أصلاً** — طلبُ رحلةٍ بها يرتدّ. ولذلك
 * تعرض الشاشة الفئتين دائماً وتقول عن الغائبة إنها غير مضبوطة، بدل أن تُخفيها
 * فيبدو الجدولُ مكتملاً.
 *
 * **ولا حسابَ هنا إطلاقاً.** الصيغة `base + km×سعر + دقيقة×سعر` بحدٍّ أدنى،
 * وتُحسب في `services/pricing.py` وحدها (القسم 5/14). **والمثالُ الحيُّ يأتي من
 * الخلفية** (`POST /admin/settings/pricing/example`، أمرُ المالك ٢٠٢٦-١١-٠٢) —
 * بدوالّ الرحلة الحقيقيّة نفسِها، فالمثالُ والأجرةُ لا يفترقان. وأمثلةُ الشرح
 * تحت كلِّ حقلٍ أسطرُ ذلك المثال نفسِه، لا ضربٌ تجريه الشاشة.
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
import type { ReactNode } from "react";

import { ApiError } from "@/api/client";
import {
  createPricing,
  deletePricing,
  getDisplayDecimals,
  listPricing,
  listRideCategories,
  pricingExample,
  setDisplayDecimals,
  updatePricing,
} from "@/api/endpoints";
import type { CountryCode, DisplayDecimals, PricingExample, PricingRule, VehicleCategory } from "@/api/types";
import { Shell } from "@/components/Shell";
import { PriceExperiments } from "@/components/PriceExperiments";
import { RiderPlans } from "@/components/RiderPlans";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { useCountry } from "@/lib/country";
import { FormErrors, useFormError } from "@/lib/form-errors";
import { currencyLabel, currencyOf, isZeroAmount, money } from "@/lib/format";
import { useSession } from "@/lib/session";

/** **المدمجتان دائماً** — وما أضافه المشرفُ في «فئات الرحلة» بعدهما (SPEC §٦٧): لكلِّ فئةٍ صفُّ أسعارها هنا. */
const BUILTINS: VehicleCategory[] = ["economy", "comfort"];

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

/** **الرحلةُ المفترضةُ لأمثلة الشرح** — ثابتةٌ لكلِّ الحقول فتُقرأ الأمثلةُ معاً. والقصيرةُ لمثال الحدّ الأدنى وحدَه. */
const SAMPLE = { distance_km: "10", duration_min: "15", stops: 1, wait_minutes_per_stop: "8", pause_minutes: "4", arrival_wait_minutes: "7" };
const SHORT = { distance_km: "1", duration_min: "3" };

/** أسطرُ المثال بأسمائها — `quantity` لتسمية السطر وحدَها، **ولا يُضرب في شيء**. */
function lineLabel(kind: string, quantity: string | null): string {
  switch (kind) {
    case "base":
      return "التعرفة الأساسية";
    case "distance":
      return `المسافة · ${quantity ?? ""} كم`;
    case "time":
      return `الزمن · ${quantity ?? ""} دقيقة`;
    case "stops":
      return `المحطات الوسيطة · ${quantity ?? ""}`;
    case "minimum":
      return "تكملة الحدّ الأدنى";
    default:
      return kind;
  }
}

function lineAmount(example: PricingExample | null, kind: string): string | null {
  return example?.lines.find((line) => line.kind === kind)?.amount ?? null;
}

/** **الشرحُ تحت كلِّ حقل** (أمرُ المالك ٢٠٢٦-١١-٠٢): ما هو · كيف يدخل الأجرة · لماذا · ومثالٌ بعملة الدولة.
 *  **والمثالُ أسطرُ الخلفية** (`sample` و`short`) لا حسابُ الشاشة — وما لم يصل بعدُ يُكتب «…» لا رقمٌ مخترع. */
function explain(
  key: FieldKey,
  sample: PricingExample | null,
  short: PricingExample | null,
  values: Record<FieldKey, string>,
  currency: string | undefined,
): ReactNode {
  const amount = (value: string | null | undefined) => (value && currency ? money(value, currency) : "…");
  const trip = `رحلةٍ مفترضةٍ ${SAMPLE.distance_km} كم في ${SAMPLE.duration_min} دقيقة`;
  switch (key) {
    case "base_fare":
      return (
        <>
          <b>ما هو:</b> مبلغٌ ثابتٌ يبدأ به كلُّ مشوارٍ قبل أن يتحرّك العدّاد — «فتحُ العدّاد».
          <br /><b>كيف يدخل الأجرة:</b> يُضاف مرّةً واحدةً إلى كلِّ رحلة، قصيرةً كانت أو طويلة.
          <br /><b>لماذا:</b> يغطّي قدومَ الكبتن ووقتَه قبل أوّل كيلومتر.
          <br /><b>مثال:</b> في {trip} سطرُه {amount(lineAmount(sample, "base"))}.
        </>
      );
    case "price_per_km":
      return (
        <>
          <b>ما هو:</b> سعرُ الكيلومتر الواحد من الطريق المحسوب على الخريطة.
          <br /><b>كيف يدخل الأجرة:</b> يُضرب في كيلومترات الطريق ويُضاف. وإن انحرف الطريقُ الفعليُّ كثيراً عن المقدَّر أُعيد الحسابُ بالمسافة الفعليّة.
          <br /><b>لماذا:</b> المسافةُ أكبرُ كلفةٍ على الكبتن: وقودٌ واستهلاكُ سيارة.
          <br /><b>مثال:</b> {SAMPLE.distance_km} كم ← {amount(lineAmount(sample, "distance"))}.
        </>
      );
    case "price_per_min":
      return (
        <>
          <b>ما هو:</b> سعرُ الدقيقة من زمن الرحلة المقدَّر.
          <br /><b>كيف يدخل الأجرة:</b> يُضرب في دقائق الرحلة المقدَّرة ويُضاف إلى المسافة.
          <br /><b>لماذا:</b> رحلةٌ قصيرةٌ في زحامٍ تأخذ وقتَ الكبتن وإن قلّت كيلومتراتُها.
          <br /><b>مثال:</b> {SAMPLE.duration_min} دقيقة ← {amount(lineAmount(sample, "time"))}.
        </>
      );
    case "minimum_fare":
      return (
        <>
          <b>ما هو:</b> أقلُّ أجرةٍ يدفعها الراكبُ لأيّ رحلة.
          <br /><b>كيف يدخل الأجرة:</b> إن خرج مجموعُ الأساس والمسافة والزمن أقلَّ منه رُفعت الأجرةُ إليه بسطرٍ ظاهرٍ اسمُه «تكملة الحدّ الأدنى».
          <br /><b>لماذا:</b> كي لا يُستدعى كبتنٌ لمشوارٍ لا يغطّي قدومَه.
          <br /><b>مثال:</b> رحلةٌ {SHORT.distance_km} كم في {SHORT.duration_min} دقائق{" "}
          {short === null
            ? "…"
            : short.minimum_fare_applied
              ? <>أجرتُها {amount(short.fare)}، منها تكملةٌ {amount(lineAmount(short, "minimum"))}.</>
              : <>أجرتُها {amount(short.fare)} — فوق الحدّ الأدنى فلا تكملة.</>}
        </>
      );
    case "cancellation_fee":
      return (
        <>
          <b>ما هو:</b> رسمٌ على الراكب إن ألغى بعد أن قَبِل الكبتنُ الطلبَ أو وصل.
          <br /><b>كيف يدخل:</b> ليس جزءاً من أجرة رحلة — يُستحقّ عند الإلغاء وحدَه. ولا رسمَ على إلغاءٍ قبل القبول، ولا على الراكب إن ألغى الكبتن، والإعفاءاتُ في «الإعدادات › الإلغاء».
          <br /><b>لماذا:</b> يعوّض الكبتنَ عن طريقٍ قطعه إلى راكبٍ ألغى.
          <br /><b>مثال:</b> راكبٌ ألغى بعد وصول الكبتن يُستحقّ عليه {amount(values.cancellation_fee.trim() || null)}.
        </>
      );
    case "stop_fee":
      return (
        <>
          <b>ما هو:</b> رسمٌ مقطوعٌ لكلِّ محطةٍ وسيطةٍ يضيفها الراكبُ قبل الطلب.
          <br /><b>كيف يدخل الأجرة:</b> يُضرب في عدد المحطات ويدخل التقديرَ الذي يراه الراكبُ قبل أن يطلب.
          <br /><b>لماذا:</b> التوقّفُ والعودةُ إلى الطريق جهدٌ ووقتٌ على الكبتن.
          <br /><b>مثال:</b> محطةٌ واحدة ←{" "}
          {sample === null ? "…" : lineAmount(sample, "stops") === null ? "لا رسم (صفر)" : amount(lineAmount(sample, "stops"))}.
        </>
      );
    case "stop_free_minutes":
      return (
        <>
          <b>ما هو:</b> دقائقُ انتظارٍ مجانيّةٌ عند كلِّ محطةٍ وسيطة.
          <br /><b>كيف يدخل الأجرة:</b> لا يُحاسَب على الانتظار حتى تنقضي، ثمّ يبدأ «لكل دقيقة انتظار بعدها». والمهلةُ لكلِّ محطةٍ على حدة لا للرحلة كلِّها.
          <br /><b>لماذا:</b> نزولُ الراكب دقيقتين حقُّه بلا كلفة.
          <br /><b>مثال:</b> انتظارُ {SAMPLE.wait_minutes_per_stop} دقائق والمهلةُ {values.stop_free_minutes || "0"} ← يُحاسَب على ما زاد عليها، ومبلغُه في الحقل التالي.
        </>
      );
    case "stop_price_per_min":
      return (
        <>
          <b>ما هو:</b> سعرُ دقيقة الانتظار عند المحطة بعد الدقائق المجانيّة.
          <br /><b>كيف يدخل الأجرة:</b> لا يُعرف قبل الرحلة، فيُضاف إلى الأجرة النهائيّة عند الإنهاء، والراكبُ يراه يمشي وهو واقف.
          <br /><b>لماذا:</b> وقتُ الكبتن الواقف وقتُ عمل.
          <br /><b>مثال:</b> انتظارُ {SAMPLE.wait_minutes_per_stop} دقائق عند محطة ← {amount(sample?.waiting_charge)}.
        </>
      );
    case "stop_max_wait_minutes":
      return (
        <>
          <b>ما هو:</b> أطولُ انتظارٍ عند محطةٍ قبل أن يُنبَّه الطرفان ويُفتح للكبتن مخرج.
          <br /><b>كيف يدخل الأجرة:</b> لا يدخلها — حدُّ صبرٍ لا حدُّ فاتورة. وصفرٌ يعني بلا سقف.
          <br /><b>لماذا:</b> كي لا يبقى كبتنٌ واقفاً بلا نهاية.
        </>
      );
    case "pause_price_per_min":
      return (
        <>
          <b>ما هو:</b> سعرُ دقيقة الوقوف حين يضغط الكبتنُ «وقفة» أثناء الرحلة، وسعرُ انتظاره عند نقطة الالتقاء بعد المهلة.
          <br /><b>كيف يدخل الأجرة:</b> يُضاف إلى الأجرة النهائيّة. الوقفةُ أثناء الرحلة بلا مهلةٍ مجانيّة، وانتظارُ الوصول بمهلته.
          <br /><b>لماذا:</b> دقيقةُ الكبتن الواقف واحدةٌ أينما وقف.
          <br /><b>مثال:</b> وقفةُ {SAMPLE.pause_minutes} دقائق ← {amount(sample?.pause_charge)}.
        </>
      );
    case "arrival_free_minutes":
      return (
        <>
          <b>ما هو:</b> دقائقُ مجانيّةٌ ينتظر فيها الكبتنُ الراكبَ بعد أن يضغط «وصلت».
          <br /><b>كيف يدخل الأجرة:</b> بعدها يُحاسَب بـ«لكل دقيقة وقوف». ولا يبدأ العدّادُ إن كان الكبتنُ خارج نطاق الالتقاء.
          <br /><b>لماذا:</b> نزولُ الراكب يأخذ دقائق، وما زاد عليها وقتُ الكبتن.
          <br /><b>مثال:</b> انتظارُ {SAMPLE.arrival_wait_minutes} دقائق عند الوصول ← {amount(sample?.arrival_charge)}.
        </>
      );
    case "pause_max_minutes":
      return (
        <>
          <b>ما هو:</b> أطولُ وقفةٍ واحدةٍ قبل أن يُنبَّه الطرفان.
          <br /><b>كيف يدخل الأجرة:</b> لا يدخلها ولا يُنهي رحلة — الإنهاءُ فعلُ الكبتن. وصفرٌ يعني بلا سقف.
          <br /><b>لماذا:</b> تنبيهٌ لطرفين نسيا الوقفةَ مفتوحة.
        </>
      );
  }
}

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

  const [categories, setCategories] = useState<VehicleCategory[]>(BUILTINS);
  const load = useCallback(async () => {
    setRules(null);
    const [nextRules, rows] = await Promise.all([listPricing(country), listRideCategories(country)]);
    for (const row of rows) if (!BUILTINS.includes(row.key)) CATEGORY_LABEL[row.key] = row.name;
    setCategories([...BUILTINS, ...rows.filter((row) => !BUILTINS.includes(row.key)).map((row) => row.key)]);
    setRules(nextRules);
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

      <div className="mt-12 rounded-16 border border-line bg-surface p-18 text-12 leading-note text-muted">
        <h2 className="mb-6 text-14 font-bold text-ink">كيف تُحسب الأجرة</h2>
        <p>
          <b className="text-ink">الأجرةُ المقدَّرة = التعرفة الأساسية + (الكيلومترات × لكل كيلومتر) + (الدقائق × لكل دقيقة) + (المحطات × رسم المحطة)</b>،
          ولا تنزل عن «الحد الأدنى». ثمّ يُضاف عند الإنهاء ما لا يُعرف قبله: انتظارُ المحطات والوقفاتُ وانتظارُ الوصول.
          وإن كان «التقريب» مشتعلاً في هذه الدولة قُرّب المجموعُ بوحدته واتجاهه. تحت كلِّ حقلٍ شرحُه ومثالٌ بعملة الدولة
          من الحساب نفسِه، والصندوقُ أسفلَ كلِّ فئةٍ يحسب رحلةً تختارها أنت.
        </p>
      </div>

      <DisplayDecimalsCard country={country} canEdit={isAdmin} />

      {rules === null ? (
        <Spinner className="mx-auto my-38" />
      ) : (
        <div className="mt-12 grid gap-16 lg:grid-cols-2">
          {categories.map((category) => (
            <CategoryCard
              key={category}
              country={country}
              category={category}
              rule={rules.find((rule) => rule.vehicle_category === category)}
              isAdmin={isAdmin}
              frozen={frozen}
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

      {/* **تجاربُ الأسعار** (البند ٤) — تحت التسعيرة التي تجرّب عليها */}
      <PriceExperiments onError={(message) => setError(message)} isAdmin={isAdmin} />
      {/* **اشتراكاتُ الركّاب** (البند ١٣) */}
      <RiderPlans onError={(message) => setError(message)} isAdmin={isAdmin} />
    </Shell>
    </FormErrors>
  );
}

/** **خاناتُ عرض المبالغ** (SPEC §٧٣-ج/٧) — لكلِّ دولة، **للعرض وحدَه**. والحدُّ الأدنى خاناتُ العملة كما تنشرها الخلفية. */
function DisplayDecimalsCard({ country, canEdit }: { country: CountryCode; canEdit: boolean }) {
  const [state, setState] = useState<DisplayDecimals | null>(null);
  const [chosen, setChosen] = useState<number | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const currency = currencyOf(country);

  useEffect(() => {
    setState(null);
    setNote(null);
    setFailure(null);
    getDisplayDecimals(country)
      .then((value) => {
        setState(value);
        setChosen(value.display_decimals);
      })
      .catch((caught) => setFailure(caught instanceof ApiError ? caught.message : "تعذّر قراءة خانات العرض"));
  }, [country]);

  async function save() {
    if (chosen === null) return;
    setBusy(true);
    try {
      const value = await setDisplayDecimals(country, chosen);
      setState(value);
      setNote("حُفظت — والتطبيقان واللوحةُ يرسمون بها من أوّل فتحٍ بعد الآن.");
      setFailure(null);
    } catch (caught) {
      setFailure(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
    }
    setBusy(false);
  }

  // **الخياراتُ من الخلفية**: من خانات العملة إلى ثلاث — فلا يُعرض خيارٌ تردّه
  const options = state ? [0, 1, 2, 3].filter((value) => value >= state.currency_decimals) : [];

  return (
    <div className="mt-12 rounded-16 border border-line bg-surface p-18">
      <h2 className="text-14 font-bold text-ink">عدد الخانات العشرية في عرض المبالغ</h2>
      <p className="mt-6 text-12 leading-note text-muted">
        كم رقماً يُرسم بعد الفاصلة في التطبيقين واللوحة لعملة {currency ? currencyLabel(currency) : "هذه الدولة"}.
        <b className="text-ink"> لا يغيّر مبلغاً محفوظاً ولا رصيداً ولا معاملةً سابقة</b> — المالُ يُحسب ويُحفظ كما كان
        حرفاً، وهذا رسمُه وحدَه. والإدخالُ يقبل خاناتِ العملة وحدَها، فلا يُكتب مبلغٌ بخاناتٍ لا يحملها.
      </p>
      <p className="mt-6 text-12 leading-note text-muted">
        <b className="text-ink">وصلتُه بالتقريب:</b> «التقريب» في «الإعدادات › الدفع» (الوحدة والاتجاه){" "}
        <b className="text-ink">يغيّر المبلغ الذي يُدفع فعلاً</b> — مثلاً لأقرب نصف دينارٍ للأعلى. أمّا هذا فلا يغيّر مبلغاً،
        يقرّر الرسمَ وحدَه. ولذلك <b className="text-ink">لا ينزل عن خانات العملة{state ? ` (${state.currency_decimals} هنا)` : ""}</b>:
        لو رُسم مبلغٌ من ثلاث خاناتٍ بخانتين لرأى الراكبُ رقماً غيرَ الذي يُخصم منه. ومتى كان التقريبُ مشتعلاً صارت الأجرةُ
        المدفوعةُ مضاعفاتِ وحدته، وتبقى الأرصدةُ والعمولاتُ بخانات العملة كاملة.
      </p>
      {failure ? <p className="mt-8 text-12 text-danger">{failure}</p> : null}
      {note ? <p className="mt-8 text-12 text-ok">{note}</p> : null}
      {state === null ? (
        failure ? null : <Spinner className="my-12" />
      ) : (
        <div className="mt-12 flex flex-wrap items-center gap-10">
          {options.map((value) => (
            <Button
              key={value}
              size="md"
              variant={chosen === value ? "primary" : "ghost"}
              disabled={!canEdit || busy}
              onClick={() => setChosen(value)}
            >
              {value === 0 ? "بلا كسور" : `${value} خانات`}
              {value === state.currency_decimals ? " · خاناتُ العملة" : ""}
            </Button>
          ))}
          {canEdit ? (
            <Button size="md" disabled={busy || chosen === state.display_decimals} onClick={() => void save()}>
              حفظ
            </Button>
          ) : (
            <span className="text-11.5 text-muted">التعديلُ لـ admin وحده.</span>
          )}
        </div>
      )}
    </div>
  );
}

function CategoryCard({
  country,
  category,
  rule,
  isAdmin,
  frozen,
  onDone,
  onError,
}: {
  country: CountryCode;
  category: VehicleCategory;
  rule: PricingRule | undefined;
  /** صلاحيةٌ — ومن لا يملكها لا يرى أزرارَ التعديل أصلاً (القسم 13/8). */
  isAdmin: boolean;
  /** حارسٌ مطفأ — **والزرُّ يُعطَّل ولا يُخفى** (`GuardBanner`). */
  frozen: boolean;
  onDone: (message: string) => void;
  onError: (caught: unknown) => void;
}) {
  // **السببان مفصولان عمداً**: غيابُ الصلاحية يُخفي الأزرار (اصطلاحُ اللوحة
  // مع `support`)، **والتجميدُ يُعطّلها ولا يُخفيها** — فزرٌّ يختفي يُقرأ
  // عطباً في اللوحة، وهي قاعدةٌ مكتوبةٌ في `GuardBanner` وكانت هذه الشاشةُ
  // وحدَها تخالفها بينما `Finance.tsx` تتبعها (قِيس من المتصفح 2026-08-24).
  const canEdit = isAdmin && !frozen;
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

  const currency = currencyOf(country);
  const unit = currencyLabel(currency);
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

  // **أمثلةُ الشرح من الخلفية بالقيم المكتوبة الآن** — تتبع الكتابةَ بعد سكونٍ قصير، ولا يُحفظ منها شيء
  const [sample, setSample] = useState<PricingExample | null>(null);
  const [short, setShort] = useState<PricingExample | null>(null);
  const draftKey = JSON.stringify(values);
  useEffect(() => {
    if (!filled) {
      setSample(null);
      setShort(null);
      return;
    }
    const timer = window.setTimeout(() => {
      const base = { country_code: country, vehicle_category: category, draft: payload() };
      Promise.all([pricingExample({ ...base, ...SAMPLE }), pricingExample({ ...base, ...SHORT })])
        .then(([one, two]) => {
          setSample(one);
          setShort(two);
        })
        .catch(() => {
          setSample(null);
          setShort(null);
        });
    }, 450);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draftKey, country, category, filled]);

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

  function field(key: FieldKey, text: string, suffix: string) {
    return (
      <div key={key}>
        <Field
          name={key}
          label={`${text} (${suffix})`}
          inputMode="decimal"
          dir="ltr"
          disabled={!canEdit}
          value={values[key]}
          onChange={(event) =>
            setValues((current) => ({ ...current, [key]: event.target.value }))
          }
        />
        <p className="mt-6 rounded-12 bg-surface-2 px-10 py-8 text-11.5 leading-note text-muted">
          {explain(key, sample, short, values, currency)}
        </p>
      </div>
    );
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

      <div className="grid gap-14">
        {FIELDS.map(({ key, label }) => field(key, label, unit))}
      </div>

      <h3 className="mb-10 mt-18 text-13 font-bold text-muted">
        المحطات الوسيطة
      </h3>
      <div className="grid gap-14">
        {STOP_FIELDS.map(({ key, label, kind }) => field(key, label, kind === "money" ? unit : "دقيقة"))}
      </div>
      <p className="mt-8 text-11 leading-note text-muted">
        صفرٌ في الرسمين يعني «بلا رسم»، وصفرٌ في السقف يعني لا سقف لا سقفاً
        مقداره صفر. والأربعةُ تُجمَّد على الرحلة لحظة الطلب، فتعديلُها يحكم ما
        يأتي لا رحلةً واقفةً الآن.
      </p>

      <h3 className="mb-10 mt-18 text-13 font-bold text-muted">
        الوقوف غير المخطَّط
      </h3>
      <div className="grid gap-14">
        {PAUSE_FIELDS.map(({ key, label, kind }) => field(key, label, kind === "money" ? unit : "دقيقة"))}
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

      <ExampleBox country={country} category={category} draft={filled ? payload() : null} saved={Boolean(rule)} />

      {isAdmin ? (
        <div className="mt-16 flex gap-10">
          <Button
            size="md"
            disabled={frozen || busy || !filled}
            onClick={() => void save()}
          >
            حفظ التغييرات
          </Button>
          {rule ? (
            <Button
              size="md"
              variant="ghost"
              disabled={frozen || busy}
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

/** **مثالٌ حيّ** (أمرُ المالك ٢٠٢٦-١١-٠٢) — مسافةٌ وزمنٌ يكتبهما المالكُ فتعود الأجرةُ مفصَّلةً حقلاً حقلاً **من الخلفية**،
 *  بالقيم المكتوبة الآن (ولو لم تُحفظ). **ولا رقمَ هنا تحسبه الشاشة**: كلُّ مبلغٍ يُرسم كما وصل. */
function ExampleBox({
  country,
  category,
  draft,
  saved,
}: {
  country: CountryCode;
  category: VehicleCategory;
  draft: Record<string, string | number> | null;
  saved: boolean;
}) {
  const [trip, setTrip] = useState({ distance_km: "8", duration_min: "18", stops: "0", wait: "0", pause: "0", arrival: "0" });
  const [result, setResult] = useState<PricingExample | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const key = JSON.stringify([trip, draft]);

  useEffect(() => {
    if (draft === null) {
      setResult(null);
      return;
    }
    const timer = window.setTimeout(() => {
      pricingExample({
        country_code: country,
        vehicle_category: category,
        distance_km: trip.distance_km || "0",
        duration_min: trip.duration_min || "0",
        stops: Number(trip.stops || 0),
        wait_minutes_per_stop: trip.wait || "0",
        pause_minutes: trip.pause || "0",
        arrival_wait_minutes: trip.arrival || "0",
        draft,
      })
        .then((value) => {
          setResult(value);
          setFailure(null);
        })
        .catch((caught) => {
          setResult(null);
          setFailure(caught instanceof ApiError ? caught.message : "تعذّر حسابُ المثال");
        });
    }, 450);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, country, category]);

  const input = (name: keyof typeof trip, text: string) => (
    <Field
      name={`example_${name}`}
      label={text}
      inputMode="decimal"
      dir="ltr"
      value={trip[name]}
      onChange={(event) => setTrip((current) => ({ ...current, [name]: event.target.value }))}
    />
  );

  const row = (text: string, amount: string, strong = false) => (
    <div className={`flex justify-between gap-12 py-4 ${strong ? "font-bold text-ink" : ""}`}>
      <span>{text}</span>
      <span dir="ltr">{money(amount, result?.currency)}</span>
    </div>
  );

  return (
    <div className="mt-18 rounded-16 border border-line bg-surface-2 p-14">
      <h3 className="text-13 font-bold text-ink">مثالٌ حيّ — كم يدفع الراكب؟</h3>
      <p className="mt-4 text-11.5 leading-note text-muted">
        اكتب مسافةً وزمناً، فتُحسب الأجرةُ في الخلفية بالدالّة نفسِها التي تسعّر الرحلات
        {saved ? " — وبالقيم المكتوبة أعلاه ولو لم تُحفظ بعد." : " — بالقيم المكتوبة أعلاه."}
      </p>
      <div className="mt-10 grid grid-cols-2 gap-10 md:grid-cols-3">
        {input("distance_km", "المسافة (كم)")}
        {input("duration_min", "الزمن (دقيقة)")}
        {input("stops", "محطات وسيطة")}
        {input("wait", "انتظارٌ عند كلِّ محطة (دقيقة)")}
        {input("pause", "وقفةٌ أثناء الرحلة (دقيقة)")}
        {input("arrival", "انتظارٌ عند الوصول (دقيقة)")}
      </div>
      {draft === null ? (
        <p className="mt-10 text-12 text-muted">اكتب الحقولَ الخمسة الأولى ليُحسب المثال.</p>
      ) : failure ? (
        <p className="mt-10 text-12 text-danger">{failure}</p>
      ) : result === null ? (
        <Spinner className="my-12" />
      ) : (
        <div className="mt-12 text-12 text-muted">
          {result.lines.map((line) => (
            <div key={line.kind}>{row(lineLabel(line.kind, line.quantity), line.amount)}</div>
          ))}
          {row("= أجرةُ الطريق (التقديرُ قبل الطلب)", result.fare, true)}
          {isZeroAmount(result.waiting_charge) ? null : row("+ انتظارُ المحطات", result.waiting_charge)}
          {isZeroAmount(result.pause_charge) ? null : row("+ الوقفةُ أثناء الرحلة", result.pause_charge)}
          {isZeroAmount(result.arrival_charge) ? null : row("+ الانتظارُ عند الوصول", result.arrival_charge)}
          {row("= الأجرةُ النهائيّة", result.total, true)}
          {result.rounding_enabled ? row("ما يدفعه الراكبُ بعد التقريب", result.payable, true) : null}
          <p className="mt-8 text-11 leading-note">
            {result.rounding_enabled
              ? "التقريبُ مشتعلٌ في هذه الدولة، فالسطرُ الأخير ما يُدفع فعلاً."
              : "التقريبُ مطفأٌ في هذه الدولة، فالأجرةُ النهائيّةُ ما يُدفع."}{" "}
            ولا يدخل المثالَ ما له بابُه: رسومُ الكبتن (المطار)، والمنطقةُ الوعرة، والخصوماتُ والقسائم.
          </p>
        </div>
      )}
    </div>
  );
}
