/** **الميزاتُ الجديدة** (أمرُ المالك ٢٠٢٦-١١-١٠، البند ٢٠) — صفحةٌ واحدةٌ تسرد العشرين: ما تفعله كلٌّ منها، **وأين إعدادُها في
 * اللوحة**، ومفتاحُها إن كان لها مفتاح، **وما ينتظر قرارَ المالك**.
 *
 * **وحالُ المفتاح يُقرأ من الخادم لا من هذا الملفّ** (`GET /admin/settings/feature-flags` للدولة المختارة): نصٌّ يقول «مفعّل» يبلى يومَ
 * يُطفأ المفتاح، فالصفحةُ لا تدّعي حالاً لا تقيسه. وما لا مفتاحَ له يُكتب «يعمل دائماً» أو «مع إصدار التطبيق» بحسب حقيقته.
 *
 * **والأربعُ الماليّةُ (٤ و١٣ و١٤ و١٦) تُشحن مطفأةً وتنتظر مبالغَ المالك**: لا قيمةَ مالٍ تُضبط من هنا ولا من الوكيل — تُقترح وتُعرض.
 */

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listFeatureFlags } from "@/api/endpoints";
import { Shell } from "@/components/Shell";
import { Badge } from "@/components/ui/Badge";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { useCountry } from "@/lib/country";

interface Feature {
  n: number;
  title: string;
  what: string;
  /** أين يُضبط أو يُرى — نصٌّ ورابطٌ إلى الصفحة. */
  where: string;
  to: string | null;
  /** مفتاحُ الميزة في «الإعدادات ← مفاتيح الميزات» إن كان لها مفتاح. */
  flag?: string;
  /** حين لا مفتاح: ما يحكم ظهورَها. */
  always?: string;
  /** ما ينتظر قرارَ المالك — مبالغُ أو قاعدة. */
  awaits?: string;
}

const FEATURES: Feature[] = [
  {
    n: 0,
    title: "الإحالة",
    what: "رابطُ دعوةٍ وخانةُ رمزٍ في التطبيقين، ومكافأةٌ للداعي، وكوبونٌ للمدعوّ.",
    where: "الإعدادات ← حافز الإحالة",
    to: "/settings",
    always: "يعمل بالمبالغ المضبوطة لكلِّ دولة",
  },
  {
    n: 1,
    title: "الاعتمادُ الاستثنائيّ",
    what: "اعتمادُ كبتنٍ قبل اكتمال وثائقه بسببٍ مكتوب، ثمّ تذكيرٌ ومهلةٌ وتجميدٌ آليٌّ إن لم تكتمل.",
    where: "السائقون والوثائق ← الاعتماد الاستثنائيّ",
    to: "/drivers",
    always: "بصلاحيّة «الاعتماد الاستثنائيّ» يمنحها المالك",
  },
  {
    n: 2,
    title: "انتهاءُ الوثائق",
    what: "تذكيرُ الكبتن قبل انتهاء وثيقته بأيّامٍ تضبطها لكلِّ دولة، وقائمةُ «وثائق تنتهي قريباً».",
    where: "السائقون والوثائق",
    to: "/drivers",
    always: "يعمل دائماً",
  },
  {
    n: 3,
    title: "درجةُ جودة الكبتن",
    what: "خمسةُ مكوّناتٍ بأوزانٍ لكلِّ دولة (قبولُ العروض، والإلغاءُ بعد القبول، وتقييمُ الركّاب، والاعتراضات، والرحلاتُ المكتملة)، ويرى الكبتنُ «درجتي».",
    where: "الإعدادات ← قواعد التوزيع ← درجة الجودة",
    to: "/settings",
    always: "مفتاحُها في بطاقة الأوزان نفسِها لكلِّ دولة",
  },
  {
    n: 4,
    title: "تجاربُ الأسعار",
    what: "نسبةٌ على الأجرة لجزءٍ من ركّاب الدولة أو لدائرةٍ منها لعددِ أيّام، ومقارنتُها بالسعر العاديّ، ثمّ تطبيقُ الفائز أو الإلغاء.",
    where: "التسعيرة ← تجارب الأسعار",
    to: "/pricing",
    flag: "price_experiments_enabled",
    awaits: "قرارُك: أيُّ نسبةٍ ولأيِّ جزءٍ ولكم يوماً — ثمّ إشعالُ المفتاح وبدءُ التجربة بيدك",
  },
  {
    n: 5,
    title: "الأعلامُ وحالُ الدولة",
    what: "منتقي الدولة بالأعلام والبحث عند التسجيل، وأربعُ حالاتٍ لكلِّ دولة، ولا رمزَ تحقّقٍ لدولةٍ غيرِ نشطة.",
    where: "الدول",
    to: "/markets",
    always: "يعمل دائماً — وليبيا «قريباً» حتى تقول",
  },
  {
    n: 6,
    title: "تقييمُ المتجر داخل التطبيق",
    what: "نافذةُ Google للتقييم بعد الرحلة الثانية للراكب والثالثة للكبتن، مرّةً كلَّ 120 يوماً على الأكثر.",
    where: "لا إعدادَ له",
    to: null,
    always: "مع إصدار التطبيقين اللذين يحملانه",
  },
  {
    n: 7,
    title: "مشاركةُ الرحلة والطوارئ",
    what: "رابطُ تتبّعٍ لكلِّ رحلةٍ جارية بالاسم الأوّل وحدَه، وزرُّ «طوارئ» للطرفين يصل الطاقمَ بالموقع الحيّ ويتّصل برقم الدولة.",
    where: "الطوارئ (ومنها رقمُ الطوارئ وواتسابُ الدعم لكلِّ دولة)",
    to: "/emergencies",
    always: "يعمل دائماً",
  },
  {
    n: 8,
    title: "«تواصل معنا» و«طلباتي»",
    what: "واتسابُ الدعم لكلِّ دولة، ومحادثةٌ مع فريق الدعم داخل التطبيقين، وتردّ من اللوحة وبجانبك الحسابُ وآخرُ رحلاته.",
    where: "الطلبات والشكاوى",
    to: "/support",
    always: "يعمل دائماً",
  },
  {
    n: 9,
    title: "الشكاوى والمفقودات",
    what: "«نسيت شيئاً» بمحادثةٍ مع الكبتن بلا أرقام، و«شكوى» بفئةٍ وصورة، وطابورٌ بالحال، والحسمُ بسببٍ مكتوب.",
    where: "الطلبات والشكاوى",
    to: "/support",
    always: "يعمل دائماً",
  },
  {
    n: 10,
    title: "الطلبُ بالصوت",
    what: "زرُّ ميكروفونٍ في «إلى أين؟» يكتب ما قاله الراكبُ في البحث، والتأكيدُ في الورقة كالمكتوب؛ ولا صوتَ يصلنا.",
    where: "الإعدادات ← مفاتيح الميزات",
    to: "/settings",
    flag: "voice_order_enabled",
  },
  {
    n: 11,
    title: "نقاطُ الالتقاط المقترحة",
    what: "تحت «من» بطاقةٌ تقترح أقربَ نقطة التقاطٍ من أماكنك ومن الالتقاطات الفعليّة المجمَّعة.",
    where: "الأماكن (فئة «نقطة التقاط») · الإعدادات ← خريطة الراكب",
    to: "/places",
    always: "مفتاحُها في «خريطة الراكب» لكلِّ دولة",
  },
  {
    n: 12,
    title: "دقّةُ وقت الوصول",
    what: "كلُّ اقترابٍ يُقاس، ويُصحَّح الوقتُ المعروض بحسب الساعة واليوم، وشاشةٌ تقارن المتوقَّعَ بالفعليّ.",
    where: "دقّة وقت الوصول",
    to: "/eta-accuracy",
    always: "يعمل دائماً",
  },
  {
    n: 13,
    title: "اشتراكاتُ الركّاب",
    what: "خططٌ بثمنٍ ومدّةٍ ونسبةِ خصمٍ بحدّين، يشتريها الراكبُ من محفظته، والخصمُ آليٌّ عند الإنهاء.",
    where: "التسعيرة ← اشتراكات الركّاب",
    to: "/pricing",
    flag: "rider_plans_enabled",
    awaits: "مبالغُك: الثمن، والمدّة، ونسبةُ الخصم، والحدّان، ومن يتحمّل الخصم",
  },
  {
    n: 14,
    title: "نقاطُ الولاء",
    what: "نقاطٌ لكلِّ رحلةٍ مكتملة، ومستويان بزيادة، وانتهاء، واستبدالٌ رصيداً في المحفظة.",
    where: "الحملات ← نقاط الولاء",
    to: "/campaigns",
    flag: "loyalty_enabled",
    awaits: "قاعدتُك: النقاطُ لكلِّ رحلة، والانتهاء، والمستويان، وكم نقطةً بكم رصيداً",
  },
  {
    n: 15,
    title: "«وجهتي» للكبتن",
    what: "يختار الكبتنُ وجهتَه أربعَ ساعات فتأتيه الطلباتُ التي على طريقه.",
    where: "الإعدادات ← قواعد التوزيع (مرّاتُ اليوم، و0 يطفئ)",
    to: "/settings",
    always: "يعمل بما ضُبط في قواعد التوزيع",
  },
  {
    n: 16,
    title: "أهدافُ الكبتن بمكافأة",
    what: "عددُ رحلاتٍ في مدّة، ومكافأةٌ تُصرف إلى محفظة الكبتن آليّاً مرّةً واحدة، ولا تتجاوز سقفَ الميزانيّة.",
    where: "الحملات ← أهداف الكبتن",
    to: "/campaigns",
    flag: "driver_goals_enabled",
    awaits: "مبالغُك: المكافأة، والهدف، والمدّة، وسقفُ الميزانيّة",
  },
  {
    n: 17,
    title: "ملخّصُ الكبتن الأسبوعيّ",
    what: "الأسبوعُ الماضي ومقارنتُه، وأفضلُ يومٍ وساعات، وإشعارُ السبت بلا أرقام.",
    where: "لا إعدادَ له — يُرى في «أرباحي» عند الكبتن",
    to: null,
    always: "يعمل دائماً",
  },
  {
    n: 18,
    title: "الخريطةُ الحراريّة",
    what: "خلايا الطلب آخرَ نصف ساعة: الكبتنُ يرى مستوىً بلا أرقام، واللوحةُ ترى العددَ وغيرَ المخدوم.",
    where: "الخريطة الحيّة",
    to: "/live-map",
    always: "يعمل دائماً",
  },
  {
    n: 19,
    title: "حملاتُ الإشعارات",
    what: "حدٌّ أسبوعيٌّ لكلِّ دولة، ومرشِّحا المدينة والحال، وإحصاءُ الحملة بمن وصله ومن فتح وأسباب التخطّي.",
    where: "الحملات",
    to: "/campaigns",
    always: "يعمل دائماً",
  },
  {
    n: 20,
    title: "هذه الصفحة",
    what: "العشرون في مكانٍ واحد، وشرحٌ عربيٌّ بجانب كلِّ إعدادٍ جديد في صفحته.",
    where: "الميزات الجديدة",
    to: null,
    always: "—",
  },
];

export function NewFeaturesScreen() {
  const { country } = useCountry();
  const [flags, setFlags] = useState<Record<string, boolean> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setFlags(null);
    setError(null);
    listFeatureFlags()
      .then((rows) => setFlags(rows.find((row) => row.country_code === country)?.flags ?? {}))
      .catch((caught: unknown) => setError(caught instanceof Error ? caught.message : "تعذّر التحميل"));
  }, [country]);

  const waiting = FEATURES.filter((feature) => feature.awaits);

  return (
    <Shell title="الميزات الجديدة" subtitle="العشرون ميزة: ما تفعله كلٌّ منها، وأين إعدادُها، وما ينتظر قرارك">
      <ErrorNote message={error} />

      <section className="ad-card mb-16 p-16">
        <h2 className="mb-8 text-14 font-bold text-ink">ما ينتظر قرارك</h2>
        <p className="mb-12 text-13 text-muted">
          هذه الأربع تمسّ المال، فشُحنت مطفأةً بلا مبالغ. لا تعمل حتى تضع مبالغَها في صفحتها ثمّ تُشعل مفتاحَها من «الإعدادات ← مفاتيح
          الميزات».
        </p>
        <ul className="grid gap-8">
          {waiting.map((feature) => (
            <li key={feature.n} className="text-13">
              <span className="font-semibold text-ink">{feature.title}</span>
              <span className="text-muted"> — {feature.awaits}</span>
            </li>
          ))}
        </ul>
      </section>

      {flags === null && !error ? <Spinner /> : null}

      <section className="ad-card overflow-x-auto">
        <table className="ad-table w-full text-13">
          <thead>
            <tr>
              <th className="p-8 text-start">#</th>
              <th className="p-8 text-start">الميزة</th>
              <th className="p-8 text-start">ما تفعله</th>
              <th className="p-8 text-start">أين إعدادُها</th>
              <th className="p-8 text-start">حالُها في هذه الدولة</th>
            </tr>
          </thead>
          <tbody>
            {FEATURES.map((feature) => (
              <tr key={feature.n} className="align-top">
                <td className="p-8">{feature.n}</td>
                <td className="p-8 font-semibold text-ink">{feature.title}</td>
                <td className="p-8 text-muted">{feature.what}</td>
                <td className="p-8">
                  {feature.to ? (
                    <Link className="text-accent underline" to={feature.to}>
                      {feature.where}
                    </Link>
                  ) : (
                    feature.where
                  )}
                </td>
                <td className="p-8">
                  <FeatureState feature={feature} flags={flags} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </Shell>
  );
}

function FeatureState({ feature, flags }: { feature: Feature; flags: Record<string, boolean> | null }) {
  if (!feature.flag) return <span className="text-muted">{feature.always}</span>;
  if (flags === null) return <span className="text-muted">…</span>;
  const on = flags[feature.flag] === true;
  return (
    <span className="grid gap-4">
      <Badge tone={on ? "ok" : feature.awaits ? "warn" : "muted"}>{on ? "مفعّل" : "مطفأ"}</Badge>
      {!on && feature.awaits ? <span className="text-12 text-muted">ينتظر مبالغك</span> : null}
    </span>
  );
}
