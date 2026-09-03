/** الإعدادات per-country — SPEC القسم 13/6، و`DESIGN.md` §3.2.
 *
 * كلُّ ما في هذه الصفحة **يسري على التطبيقين فور الحفظ** بلا نشر: مفتاحٌ
 * يُطفأ هنا يختفي أثرُه من شاشة الدفع، ونسبةٌ تُغيَّر هنا تُجمَّد على الرحلة
 * القادمة لا على الماضية.
 *
 * **وثلاث قواعد تظهر في الشاشة لأنها تحكم ما يقع:**
 *
 * 1. **`otp_verification_enabled` حارسٌ لا ميزة** — الاستثناء الوحيد لقاعدة
 *    «غياب الصف = معطّل». إطفاؤه إجراءُ طوارئ يفتح باباً، فيطلب **سبباً
 *    مكتوباً** يدخل سجل التدقيق، ويحمل تحذيره في وجهه. ولا يعطّل استعادة
 *    كلمة المرور أبداً.
 * 2. **لا مفتاحَ للعمولة بين المفاتيح**: مصدرها الوحيد `commission_settings`
 *    حيث تسكن نسبتُها ونطاقُها معاً — مفتاحٌ ثانٍ يعني حالتين ماليتين قابلتين
 *    للاختلاف.
 * 3. **صفرُ حدِّ التحويل يعني «لم يُضبط»** فيمنع التحويل، لا «حدٌّ مقداره
 *    صفر». والشاشة تقولها بدل أن يقرأ المشرف صفراً ويظنه سخاءً.
 *
 * ولا تُحسب هنا نسبةٌ ولا مبلغ: الحقولُ تُرسل كما تُكتب، والخلفيةُ تتحقق.
 *
 * **و`key={row.country_code}` على النماذج الثلاثة ليس تفصيلاً في React بل حارسٌ
 * ماليّ**: كلُّ نموذجٍ يبدأ حالتَه من `row`، وReact لا يعيد قراءة قيمةِ
 * `useState` الأولى عند تغيّر الـprop — فمبدّلُ الدولة كان يُبقي أرقامَ السوق
 * السابق في الحقول (النسبة، وحدود التحويل، ومبالغ البقشيش) بينما تحت الحقل
 * سطرٌ يقول القيمةَ الصحيحة. ومن ضغط «حفظ» بعده يكتب **أرقام الأردن في ليبيا**.
 * والمفتاحُ يُعيد تركيبَ النموذج فتُقرأ القيمُ من جديد. كشفه فحصٌ بصريٌّ في
 * متصفح: `tsc` لا يرى حالةً قديمة.
 */

import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";

import { ApiError } from "@/api/client";
import { DurationField } from "@/components/ui/Inputs";
import { Storefront } from "@/components/Storefront";
import { VerificationCampaign } from "@/components/VerificationCampaign";
import {
  listCommission,
  listFeatureFlags,
  getReferralSettings,
  getSharingSettings,
  listPaymentSettings,
  listAdvanceSettings,
  listDispatchSettings,
  listCancellationSettings,
  listOtpExhausted,
  listOtpSettings,
  updateOtpSettings,
  updateCancellationSettings,
  listWalletSettings,
  updateAdvanceSettings,
  updateDispatchSettings,
  setFeatureFlag,
  updateCommission,
  updatePaymentSettings,
  updateReferralSettings,
  updateSharingSettings,
  updateWalletSettings,
  listMapSettings,
  updateMapSettings,
  uploadCliqQr,
} from "@/api/endpoints";
import type {
  AdvanceSetting,
  CountryCode,
  DispatchMode,
  DispatchSetting,
  CancellationSetting,
  OtpExhausted,
  MapSetting,
  OtpSetting,
  UnpaidCancellationOutcome,
  CommissionSetting,
  CountryFeatureFlags,
  FeatureKey,
  PaymentSetting,
  ReferralSetting,
  RideSharingSetting,
  WalletSetting,
} from "@/api/types";
import { Shell } from "@/components/Shell";
import { Button } from "@/components/ui/Button";
import { Checkbox, Field, Select, Switch } from "@/components/ui/Field";
import { ErrorNote, Spinner, SuccessNote } from "@/components/ui/Feedback";
import { useCountry } from "@/lib/country";
import { FormErrors, useFormError } from "@/lib/form-errors";
import { currencyLabel, currencyOf, money } from "@/lib/format";
import { useSession } from "@/lib/session";
import { digits, cn } from "@/lib/utils";

const FLAG_LABEL: Record<FeatureKey, { title: string; hint: string }> = {
  cliq_enabled: {
    title: "الدفع بكليك",
    hint: "يظهر كليك خياراً في شاشة دفع الراكب، ويُفعّل شحن المحفظة به.",
  },
  card_enabled: {
    title: "الدفع بالبطاقة",
    hint: "صفحةُ دفعٍ مستضافة عبر Telr — تحتاج عقداً مفعّلاً في صفحة العقود.",
  },
  wallet_enabled: {
    title: "المحفظة",
    hint: "الشحنُ والدفعُ منها. وإطفاؤه لا يخفي رصيداً قائماً عن صاحبه.",
  },
  vehicle_skins_enabled: {
    title: "مركبات الكراج والمتجر",
    hint: "كراجُ الكبتن ومتجرُ المركبات، والشكلُ الذي يراه الراكبُ على الخريطة. وإطفاؤه يُخفي المتجرَ ويُبقي ما اقتناه الكباتن — فمركبةٌ دُفع ثمنُها لا تُسحب بمفتاح، ويعود الجميعُ إلى البديل المنشور. واضبط الكتالوجَ في «مركبات المتجر».",
  },
  wallet_transfer_enabled: {
    title: "التحويل بين الركّاب",
    hint: "يحتاج حدّي تحويلٍ غير صفريّين أدناه، وإلا رُفض التحويل.",
  },
  driver_advances_enabled: {
    title: "سلف الكباتن",
    hint: "سلفةٌ نقديةٌ تُقتطع من أرباح الرحلات. أساسُ سقفها سعرُ خطتك اليومية، فلا خطةَ يومية = لا سلف ولو أُشعل المفتاح. واضبط الاقتطاعَ والمهلةَ وشروطَ الأهلية في «سياسة السلف» أدناه — والقرارُ سوقٌ واحدٌ أولاً.",
  },
  country_visible: {
    title: "إظهار هذا السوق في التطبيقات",
    hint: "مطفأً: لا يظهر في اختيار الدولة ولا في التسجيل — والخلفيةُ والبياناتُ والإعدادات كما هي. وإشعالُه يُظهره في اللحظة نفسِها بلا تحديث تطبيق. واللوحةُ ترى السوقَ في الحالين.",
  },
  pricing_writes_enabled: {
    title: "الكتابة على التسعير",
    hint: "حارسٌ لا ميزة. مطفأً: **تجميدُ التسعير** — لا يُنشأ صفٌّ ولا يُعدَّل ولا يُحذف، والرحلاتُ تُسعَّر بالصفوف القائمة والطلبُ لا يُرفض. اضغطه حين يدخل رقمٌ خاطئ: كلفتُه صفرٌ على الراكب، ورفعُه بعد التصحيح. ولا يستردّ ما كُتب قبله.",
  },
  withdrawal_payout_enabled: {
    title: "صرف السحوبات",
    hint: "حارسٌ لا ميزة. مطفأً: **المالُ لا يغادر** — والكباتن يطلبون وأنت تعتمد كما كان، والطلبُ يبقى «معتمَداً» حتى تستأنف. والكبتنُ يقرأ على طلبه أن الصرفَ متوقّفٌ مؤقّتاً، فلا يظنّ طلبَه ضاع. وتحويلٌ غادر إلى المزوّد يُكمَل.",
  },
  otp_verification_enabled: {
    title: "التحقق من الرقم",
    hint: "حارسٌ لا ميزة — إطفاؤه للطوارئ فقط، ويسمح بحساباتٍ برقمٍ غير مُثبت.",
  },
  multi_stop_enabled: {
    title: "تعدد الوجهات",
    hint: "يظهر زرُّ «إضافة محطة» في شاشة الطلب — حتى ثلاث وجهات. واضبط رسوم المحطات في «التسعيرة» أولاً، فصفرُها يعني محطاتٍ بلا كلفة. والإطفاءُ يمنع الطلبات الجديدة ولا يقطع رحلةً جارية.",
  },
  tips_enabled: {
    title: "البقشيش",
    hint: "أزرارُ شكرٍ في شاشة تقييم الراكب — يُخصم من محفظته ويصل الكبتنَ كاملاً بلا عمولة. ويشترط المحفظةَ مفعّلةً (قناتُه الوحيدة) ومبالغَ مضبوطةً أدناه؛ وصفرُ السقف يُخفي الميزةَ ولو كان المفتاح مشتعلاً.",
  },
  whatsapp_otp_enabled: {
    title: "التحقق عبر واتساب",
    hint: "يُرسل رمزَ التحقق في واتساب بدل الرسائل القصيرة — ويشترط عقد WhatsApp مفعّلاً في صفحة العقود. ولا تُشعَل قبل اعتماد قالب المصادقة بلغة هذا السوق: قالبٌ غير معتمد يجعل كلَّ تسجيلٍ يرتدّ. وعند فشل الإرسال يُعرض على المستخدم الارتداد إلى الرسائل.",
  },
  email_otp_enabled: {
    title: "التحقق بالبريد",
    hint: "بابٌ بديلٌ يفتح حساباً محدوداً حين تسقط قناةُ الهاتف: البريدُ يُثبت البريدَ لا الرقم — فالرقمُ يُحجز ولا يُملَك، ولا رحلةَ ولا محفظةَ حتى يؤكّده صاحبُه من التطبيق. ويشترط عقدَ مُرسِلٍ مفعّلاً في صفحة العقود: لا يُقبل إشعالُه بدونه، لأن باباً مرسوماً بلا مُرسِلٍ يسقط عند أوّل ضغطة.",
  },
  promo_codes_enabled: {
    title: "رموز الخصم",
    hint: "تظهر ورقةُ «عندي كوبون» في شاشة تأكيد الرحلة. والخصمُ تتحمّله الشركة: يُسجَّل دفعةً بقناة «كوبون» فلا يَنقص أجرةَ الكبتن ولا عمولته. وأنشئ الرموزَ في «العروض والحملات» — مفتاحٌ مشتعلٌ بلا رموز يفتح حقلاً لا يُقبل فيه شيء.",
  },
  driver_referrals_enabled: {
    title: "حافز إحالة السائقات",
    hint: "مكافأةٌ لمن يُحيل سائقةً تُدفع في محفظته بعد اعتماد حسابها وإكمالها عددَ الرحلات المطلوب — واضبط المبلغَ أدناه، فصفرُه يعني «لم يُحدَّد» فلا تُدفع مكافأة ولا يُوعَد بها أحد. والرمزُ يظهر للكبتن على كل حال فالإحالاتُ تُسجَّل ولو كان المفتاح مطفأً.",
  },
  rider_referrals_enabled: {
    title: "حافز إحالة الركاب",
    hint: "مكافأةٌ لمن يُحيل راكباً تُدفع في محفظته بعد إكمال المُحال عددَ الرحلات المطلوب. والرمزُ واحدٌ للبرنامجين: من يسجّل به كبتناً يُقاس ببرنامج السائقين، ومن يسجّل به راكباً بهذا. وصفرُ المبلغ يعني «لم يُحدَّد» فلا تُدفع مكافأة ولا يُوعَد بها أحد.",
  },
  referred_reward_enabled: {
    title: "كوبون ترحيب للمُحال",
    hint: "كوبونٌ يُطبَّق تلقائياً على أول رحلةٍ لمن سجّل برمز إحالة — تتحمّله الشركة. ورمزُ الكوبون خاصٌّ لا يُكتب بيد أحد: تكتبه المنصّةُ باسم صاحبه وحدَه. واختر الكوبونَ أدناه، فمفتاحٌ مشتعلٌ بلا كوبونٍ مختار لا يفعل شيئاً.",
  },
  driver_levels_enabled: {
    title: "المهام والمستويات",
    hint: "مهامٌّ شهريةٌ للكباتن ومستوىً يُحسب منها كلَّ ساعة. وأثرُ المستوى خصمٌ بالأمتار على مسافة البحث — بحدٍّ أقصى 100م، فالأقربُ يبقى الأول والمستوى يفصل بين المتقاربين وحدهم. واضبط الأثرَ أدناه، فصفرُه يعني «بلا أثر» فيبقى الترتيبُ كما هو. ومطفأً: لا ترجيحَ ولا شاشةَ ولا مهمّةَ تُحسب.",
  },
  ride_sharing_enabled: {
    title: "مشاركة الرحلة بين ركاب",
    hint: "راكبان في سيارةٍ واحدة بخصمٍ لكليهما — تتحمّله الشركة فلا يَنقص ما يقبضه الكبتن. واضبط نسبةَ الخصم أدناه، فصفرُها يعني «لم تُحدَّد» فلا تُعرض المشاركة أصلاً. وطلبٌ بتفضيلٍ نسائيٍّ لا يُشارَك إلا باختيارٍ صريحٍ من صاحبته. وإطفاؤه يمنع طلباتٍ جديدة ولا يفكّ مجموعةً سائرةً الآن.",
  },
  subscription_offers_enabled: {
    title: "عروض اشتراكات الكباتن",
    hint: "خصمٌ بالنسبة على سعر الباقة، يُدار من شاشة «عروض الاشتراكات». والتنازلُ إيرادٌ لم يُقبض لا مصروفٌ يُدفع، فلا يُجمع مع خصومات الرحلات. ومطفأً: لا خصمَ يُحسب ولا عرضٌ يُعرض للكبتن — **وعروضٌ قائمةٌ لا تُلغى**، فمن اشترى بخصمٍ احتفظ به.",
  },
  next_instruction_enabled: {
    title: "التعليمة التالية",
    hint: "شريطٌ فوق خريطة الكبتن يقول المسافةَ إلى المنعطف القادم ونصَّه («39 م · الاتجاه نحو اليمين»)، مقروءاً من الخطِّ المجمَّد على الرحلة لا بنداءٍ جديدٍ لكلِّ حركة. **ويختفي عند الانحراف ولا يتجمّد**: تعليمةٌ قديمةٌ تبقى معلَّقةً تقود الكبتنَ إلى منعطفٍ تجاوزه. وإشعالُه يجعل الخلفيةَ تطلب خطواتِ المسار من المزوّد وتخزّنها مع الرحلة.",
  },
  driver_map_nearby_enabled: {
    title: "الكباتن على خريطة الكبتن",
    hint: "يرى الكبتنُ زملاءَه القريبين على خريطته — **مجهَّلين تماماً كما يراهم الراكب**: إحداثياتٌ واتجاهٌ وفئةُ مركبة، بلا اسمٍ ولا لوحةٍ ولا معرّفٍ يثبت بين طلبين. ويُشحن مطفأً لأن أثرَه سوقيٌّ لا عرضيّ: يُقرأ عوناً على اختيار موضعٍ، ويُقرأ مطاردةً على الزحام. ومطفأً يقول البابُ «غيرُ مفعّل» ولا يردّ قائمةً فارغة — الفارغةُ تُقرأ «لا أحدَ حولك» وهي خبرٌ كاذبٌ عن السوق.",
  },
  scheduled_rides_enabled: {
    title: "الرحلات المجدولة",
    hint: "يظهر «حدّد موعداً» في ورقة تأكيد الرحلة، ويبدأ البحثُ عن كبتنٍ قبل الموعد بعشر دقائق. والسعرُ يُحسب عند التنفيذ لا عند الحجز. وإطفاؤه يمنع حجوزاً جديدة ويُنفّذ القائمةَ منها: موعدٌ رتّب صاحبُه صباحَه عليه لا يُلغى بمفتاح.",
  },
  women_service_enabled: {
    title: "خدمة التوصيل النسائي",
    hint: "لا تُشعَل قبل مراجعة أجناس الكباتن المعتمدين — خدمةٌ بلا سائقاتٍ يمكن ترشيحُهنّ تُقرأ ميزةً معطوبة. اعرض «من لم يُثبَّت جنسُه» في صفحة السائقين.",
  },
};

/** المفاتيحُ التي يملك المشرف إطفاءها من هنا، وحارسُها آخرُ القائمة عمداً. */
const FLAGS: FeatureKey[] = [
  "cliq_enabled",
  "card_enabled",
  "wallet_enabled",
  "wallet_transfer_enabled",
  "multi_stop_enabled",
  "women_service_enabled",
  "whatsapp_otp_enabled",
  "email_otp_enabled",
  "tips_enabled",
  "promo_codes_enabled",
  "driver_referrals_enabled",
  "rider_referrals_enabled",
  "referred_reward_enabled",
  "driver_levels_enabled",
  "scheduled_rides_enabled",
  "ride_sharing_enabled",
  "subscription_offers_enabled",
  "vehicle_skins_enabled",
  "driver_advances_enabled",
  "next_instruction_enabled",
  "driver_map_nearby_enabled",
  // **والأخيرةُ حرّاسٌ لا ميزاتٌ تُجرَّب**: سوقٌ، وتحقُّق، وحارسا مال
  "country_visible",
  "otp_verification_enabled",
  "pricing_writes_enabled",
  "withdrawal_payout_enabled",
];

/** المفاتيحُ التي **إطفاؤها يُسقط حماية**، فتشترط سبباً مكتوباً في التدقيق.
 *
 * **مرآةٌ لـ`settings_service.GUARDED_FLAGS`** في الخلفية، ويقارنهما
 * `check:flags` في الاتجاهين — فلا يُضاف حارسٌ هناك ويبقى زرُّه هنا بلا
 * ورقةِ سبب.
 *
 * **وكان هذا شرطاً على مفتاحٍ واحدٍ مكتوبٍ بيده** (`key ===
 * "otp_verification_enabled"`)، فلمّا أُضيف حارسا المال في 2026-08-23 لم
 * يرثا شيئاً: لا وسمَ «حارس»، ولا ورقةَ سبب، **والضغطةُ تُرسل طلباً بلا سببٍ
 * فيرتدّ ٤٢٢** — أي أن المفتاحين **لا يمكن إطفاؤهما من اللوحة أصلاً**.
 * وهو «بابٌ بلا زرّ» في اتجاهٍ واحد: يُشعَل ولا يُطفأ. (قِيس من المتصفح
 * 2026-08-24.)
 */
const GUARDED_FLAGS = [
  "otp_verification_enabled",
  "pricing_writes_enabled",
  "withdrawal_payout_enabled",
] as const satisfies readonly FeatureKey[];

/** **والاتحادُ من المصفوفة لا مكتوباً بجانبها**: `Record<GuardedFlag, …>`
 * أدناه يجعل **المصرّفَ** يرفض حارساً بلا نصِّ أثر — فلا يُضاف اسمٌ هنا
 * ويُنسى أثرُه هناك. وهو ما يفعله `FLAG_LABEL` نفسُه (`check-flags.mjs`). */
type GuardedFlag = (typeof GUARDED_FLAGS)[number];

/** أثرُ الإطفاء بكلماتِ كلِّ حارسٍ على حدة.
 *
 * **ولا يُوحَّد النصّ**: من يجمّد التسعيرَ لا يعنيه كلامٌ عن أرقامٍ غيرِ
 * مُثبتة، **وجملةٌ لا علاقةَ لها بما ضُغط تُقرأ خطأً في اللوحة لا تحذيراً**
 * — وهي العلّةُ التي فُصلت لأجلها `GUARDED_FLAGS` عن `DEFAULT_ENABLED_FLAGS`
 * أصلاً (`settings_service`).
 */
const GUARD_NOTE: Record<GuardedFlag, ReactNode> = {
  otp_verification_enabled: (
    <>
      بعد الإطفاء تُنشأ حساباتٌ برقمٍ غير مُثبت، وتبقى موسومةً وقابلةً للفلترة
      في صفحة الركّاب.{" "}
      <b className="text-ink">
        ولا يُعتمد كبتنٌ غير مُثبت الرقم مهما كان هذا المفتاح
      </b>{" "}
      — رقمُه هو ما تصله عليه حوالاتُ السحب. ولا يمس هذا استعادةَ كلمة المرور
      إطلاقاً.
    </>
  ),
  pricing_writes_enabled: (
    <>
      بعد الإطفاء <b className="text-ink">لا يُنشأ صفُّ تسعيرٍ ولا يُعدَّل ولا
      يُحذف</b> في هذا السوق — والرحلاتُ تُسعَّر بالصفوف القائمة، فلا طلبَ
      يُرفض ولا تقديرَ يتوقف. <b className="text-ink">ولا يستردّ ما كُتب
      قبله</b>: التصحيحُ بالرقم بعد رفع التجميد.
    </>
  ),
  withdrawal_payout_enabled: (
    <>
      بعد الإطفاء <b className="text-ink">لا يغادر المالُ إلى أيِّ كبتن</b> —
      والطلباتُ تُقدَّم وتُعتمد كما هي، ويبقى الطلبُ «معتمَداً» حتى تستأنف.
      والكبتنُ يقرأ على طلبه أن الصرفَ متوقّفٌ مؤقّتاً فلا يظنُّ طلبَه ضاع.
      <b className="text-ink"> وتحويلٌ غادر إلى المزوّد يُكمَل</b> ولا يُقطع.
    </>
  ),
};

export function SettingsScreen() {
  const { country } = useCountry();
  const { isAdmin } = useSession();

  const [flags, setFlags] = useState<CountryFeatureFlags[] | null>(null);
  const [commission, setCommission] = useState<CommissionSetting[]>([]);
  const [wallet, setWallet] = useState<WalletSetting[]>([]);
  const [payment, setPayment] = useState<PaymentSetting[]>([]);
  const [referral, setReferral] = useState<ReferralSetting | null>(null);
  const [sharing, setSharing] = useState<RideSharingSetting | null>(null);
  const [advance, setAdvance] = useState<AdvanceSetting[]>([]);
  const [dispatchRows, setDispatchRows] = useState<DispatchSetting[]>([]);
  const [cancel, setCancel] = useState<CancellationSetting[]>([]);
  const [otp, setOtp] = useState<OtpSetting[]>([]);
  const [mapRows, setMapRows] = useState<MapSetting[]>([]);
  const [burned, setBurned] = useState<OtpExhausted | null>(null);
  const [guard, setGuard] = useState<{ key: FeatureKey } | null>(null);
  // خطأُ النموذج: نصٌّ عامٌّ في الشريط، ووسمٌ على الحقل الذي سمّته الخلفية.
  // وشاشةُ الإعدادات أحوجُ الشاشات إليه: ستةٌ وثلاثون حقلاً، وسطرٌ أحمرُ
  // وحدَه يترك المشرفَ يبحث عن أيِّها رُفض.
  const form = useFormError();
  const error = form.message;
  const setError = form.setMessage;
  const [riderReferral, setRiderReferral] = useState<ReferralSetting | null>(
    null,
  );
  const [done, setDone] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [f, c, w, p, r, rr, sh, adv, dsp, cxl, otpRows, mapRows, spent] =
      await Promise.all([
      listFeatureFlags(),
      listCommission(),
      listWalletSettings(),
      listPaymentSettings(),
      // **منفذُ الإحالة لدولةٍ واحدة** لا قائمة، فيدخل السوقُ في التبعيات —
      // وبغيره يبقى معروضاً إعدادُ السوق الأول بعد تبديل الرأس
      getReferralSettings(country, "driver"),
      getReferralSettings(country, "rider"),
      getSharingSettings(country),
      listAdvanceSettings(),
      listDispatchSettings(),
      listCancellationSettings(),
      listOtpSettings(),
      listMapSettings(),
      listOtpExhausted(),
    ]);
    setFlags(f);
    setCommission(c);
    setWallet(w);
    setPayment(p);
    setReferral(r);
    setRiderReferral(rr);
    setSharing(sh);
    setAdvance(adv);
    setDispatchRows(dsp);
    setCancel(cxl);
    setOtp(otpRows);
    setMapRows(mapRows);
    setBurned(spent);
  }, [country]);

  useEffect(() => {
    load().catch((caught) =>
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر قراءة الإعدادات",
      ),
    );
  }, [load]);

  const current = flags?.find((entry) => entry.country_code === country);
  const commissionRow = commission.find((row) => row.country_code === country);
  // **`null` لا `undefined` مُمرَّرةً**: النموذجُ يعرض الافتراضيَّ للغائب
  const dispatchRow =
    dispatchRows.find((row) => row.country_code === country) ?? null;
  const walletRow = wallet.find((row) => row.country_code === country);
  const paymentRow = payment.find((row) => row.country_code === country);
  const advanceRow = advance.find((row) => row.country_code === country);
  const cancellationRow = cancel.find((row) => row.country_code === country);
  const otpRow = otp.find((row) => row.country_code === country);
  const mapRow = mapRows.find((row) => row.country_code === country);

  async function flip(key: FeatureKey, enabled: boolean, reason?: string) {
    setError(null);
    setDone(null);
    try {
      await setFeatureFlag({
        country_code: country,
        feature_key: key,
        enabled,
        reason,
      });
      await load();
      setDone("حُفظ الإعداد — يسري على التطبيقين الآن");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
    }
  }

  return (
    <FormErrors value={form.field}>
    <Shell
      title="الإعدادات العامة"
      subtitle="إعداداتٌ تسري على تطبيقَي الراكب والسائق فور الحفظ"
    >
      <ErrorNote message={error} />
      <SuccessNote message={done} />

      {flags === null ? (
        <Spinner className="mx-auto" />
      ) : (
        <div className="mt-12 grid gap-14 lg:grid-cols-2">
          <section className="rounded-16 border border-line bg-surface p-18">
            <h2 className="mb-12 text-14 font-bold text-ink">مفاتيح الميزات</h2>
            <ul className="flex flex-col gap-12">
              {FLAGS.map((key) => {
                const on = current?.flags[key] === true;
                const isGuard = (GUARDED_FLAGS as readonly FeatureKey[]).includes(key);
                return (
                  <li key={key} className="flex items-start gap-12">
                    <span className="flex-1">
                      <span className="block text-13 font-semibold text-ink">
                        {FLAG_LABEL[key].title}
                        {isGuard ? (
                          <span className="ms-8 text-10.5 font-bold text-warn">
                            حارس
                          </span>
                        ) : null}
                      </span>
                      <span className="block text-11 leading-snug text-muted">
                        {FLAG_LABEL[key].hint}
                      </span>
                    </span>
                    <Switch
                      checked={on}
                      disabled={!isAdmin}
                      label={FLAG_LABEL[key].title}
                      onChange={() => {
                        // إطفاءُ الحارس وحده يطلب سبباً — والخلفية ترفض بدونه
                        if (isGuard && on) setGuard({ key });
                        else void flip(key, !on);
                      }}
                    />
                  </li>
                );
              })}
            </ul>
          </section>

          <section className="rounded-16 border border-line bg-surface p-18">
            <h2 className="mb-4 text-14 font-bold text-ink">عمولة المنصة</h2>
            <p className="mb-12 text-11 leading-snug text-muted">
              لا مفتاحَ لها بين المفاتيح: المصدرُ واحد — النسبةُ ونطاقُها هنا،
              فلا تختلف حالتان على أمرٍ مالي. والنسبةُ تُجمَّد على الرحلة عند
              إنشائها ولا يُعاد حسابُها بأثرٍ رجعي.
            </p>
            {commissionRow ? (
              <CommissionForm
                key={commissionRow.country_code}
                row={commissionRow}
                disabled={!isAdmin}
                onSaved={(message) => {
                  setDone(message);
                  void load();
                }}
                onError={(caught) => form.capture(caught, "تعذّر الحفظ")}
              />
            ) : (
              <p className="text-12.5 text-muted">
                لا إعداد عمولة لهذه الدولة.
              </p>
            )}
          </section>

          <section className="rounded-16 border border-line bg-surface p-18">
            <h2 className="mb-4 text-14 font-bold text-ink">
              حدود المحفظة والسحب
            </h2>
            <p className="mb-12 text-11 leading-snug text-muted">
              الصفرُ هنا يعني «لم يُضبط» فيمنع التحويل — لا «حدٌّ مقداره صفر».
            </p>
            {walletRow ? (
              <WalletForm
                key={walletRow.country_code}
                row={walletRow}
                disabled={!isAdmin}
                onSaved={(message) => {
                  setDone(message);
                  void load();
                }}
                onError={(caught) => form.capture(caught, "تعذّر الحفظ")}
              />
            ) : (
              <p className="text-12.5 text-muted">
                لا حدود محفوظة لهذه الدولة.
              </p>
            )}
          </section>

          {/* **«سياسات الدفع» لا «مهلة تأكيد كليك»**: البطاقةُ صارت تحمل شيئين
              (المهلةَ ومبالغَ البقشيش)، وعنوانٌ يسمّي أحدَهما يجعل الآخرَ لا
              يُوجد لمن يبحث عنه. والاسمُ هو اسمُ جدولها `payment_settings` —
              نفسُ السبب الذي جعلها جدولاً مستقلاً عن `wallet_settings`. */}
          <section className="rounded-16 border border-line bg-surface p-18">
            <h2 className="mb-4 text-14 font-bold text-ink">سياسات الدفع</h2>
            <h3 className="mb-2 mt-12 text-12.5 font-bold text-ink">
              مهلة تأكيد حوالة كليك
            </h3>
            <p className="mb-12 text-11 leading-snug text-muted">
              بعدها تصير الدفعةُ نزاعاً ويُخطر الطرفان.{" "}
              <b className="text-ink">ولا أثرَ رجعياً</b>: المهلةُ تُجمَّد على
              الدفعة لحظة إدخال المرجع، فتعديلُها هنا يحكم ما يأتي بعده لا ما
              ينتظر الآن.
            </p>
            {paymentRow ? (
              <PaymentForm
                key={paymentRow.country_code}
                row={paymentRow}
                disabled={!isAdmin}
                onSaved={(message) => {
                  setDone(message);
                  void load();
                }}
                onError={(caught) => form.capture(caught, "تعذّر الحفظ")}
              />
            ) : (
              <p className="text-12.5 text-muted">لا إعداد دفعٍ لهذه الدولة.</p>
            )}
          </section>

          {/* حافزُ الإحالة (12-ح) — بطاقةٌ مستقلةٌ لأن جدولَه مستقل
              (`referral_settings`)، ونفسُ سببِ استقلال «سياسات الدفع» عن
              «حدود المحفظة»: حقلٌ يسكن شاشةً غير جدوله يصير البحثُ عنه تخميناً */}
          <section className="rounded-16 border border-line bg-surface p-18">
            <h2 className="mb-4 text-14 font-bold text-ink">حافز إحالة السائقات</h2>
            <p className="mb-12 text-11 leading-snug text-muted">
              مكافأةٌ تُدفع في محفظة من أحال، بعد أن يُعتمد حسابُ المُحالة{" "}
              <b className="text-ink">ويُثبَّت جنسُها</b> وتُكمل عددَ الرحلات
              أدناه. <b className="text-ink">وصفرُ المبلغ يعني «لم يُحدَّد»</b>{" "}
              فلا تُدفع مكافأةٌ ولا يُوعَد بها أحد — والإحالاتُ تُسجَّل على كل
              حال. وتعديلُ الحدِّ يعيد تقييمَ ما لم يُدفع، ولا يمسّ ما دُفع.
            </p>
            {/* **برنامجان في قسمٍ واحد**: الرمزُ واحدٌ عند صاحبه، ومبلغان
                في شاشتين يجعلان المشرفَ يضبط أحدَهما ويظنّ الآخرَ تبعاً له */}
            {referral && riderReferral ? (
              <div className="grid gap-16">
                {[referral, riderReferral].map((program) => (
                  <ReferralForm
                    key={`${program.country_code}:${program.referral_type}`}
                    row={program}
                    disabled={!isAdmin}
                    onSaved={(message) => {
                      setDone(message);
                      void load();
                    }}
                    onError={(caught) => form.capture(caught, "تعذّر الحفظ")}
                  />
                ))}
              </div>
            ) : (
              <p className="text-12.5 text-muted">لا إعداد إحالةٍ لهذه الدولة.</p>
            )}
          </section>

          {/* سياسةُ السلف (البند ١٥) — بطاقةٌ مستقلةٌ لجدولٍ مستقل
              (`advance_settings`): ذاك حدودُ محفظة، وهذه سياسةُ إقراض */}
          <section className="rounded-16 border border-line bg-surface p-18">
            <h2 className="mb-4 text-14 font-bold text-ink">سياسة السلف</h2>
            <p className="mb-12 text-11 leading-snug text-muted">
              <b className="text-ink">سقفُ السلفة الأولى هو سعرُ خطتك اليومية</b>{" "}
              — فلا خطةَ يوميةٌ مفعّلة يعني لا سلف، ولو أُشعل المفتاح. وينمو
              السقفُ بنسبةٍ عن <b className="text-ink">كل سلفةٍ سُدِّدت</b> وحدها،
              محدوداً بالسقف الأقصى؛ وصفرُ النموّ يُبقيه عند اليوميّ — وهو ما
              يجعل أسوأَ خسارةٍ ممكنةٍ اشتراكاً يومياً واحداً. والمهلةُ{" "}
              <b className="text-ink">تُجمَّد على كل سلفةٍ لحظةَ صرفها</b>، فتعديلُها
              يحكم ما يأتي لا ما ينظر إليه كبتنٌ في شاشته الآن.
            </p>
            {advanceRow ? (
              <AdvanceForm
                key={advanceRow.country_code}
                row={advanceRow}
                disabled={!isAdmin}
                onSaved={(message) => {
                  setDone(message);
                  void load();
                }}
                onError={(caught) => form.capture(caught, "تعذّر الحفظ")}
              />
            ) : (
              <p className="text-12.5 text-muted">لا سياسةَ سلفٍ لهذه الدولة.</p>
            )}
          </section>

          {/* بلاطاتُ الخدمات واللافتات (الترحيلة `0063`) — **صفوفٌ لا
              شيفرة**: إضافةُ خدمةٍ أو لافتةٍ **بلا نشر** */}
          <Storefront country={country} onError={setError} />
          <VerificationCampaign country={country} onError={setError} />

          {/* قواعدُ التوزيع (§5.3) — **صارت إعداداً بعد أن كانت ثوابتَ في
              الشيفرة** (قرارُ المالك 2026-08-30)، وعُدِّلت §5.3 معها */}
          <section className="rounded-16 border border-line bg-surface p-18">
            <h2 className="mb-4 text-14 font-bold text-ink">قواعد التوزيع</h2>
            <p className="mb-12 text-11 leading-snug text-muted">
              <b className="text-ink">التسلسليّ</b> يعرض على واحدٍ في كل مرة
              والدورُ محفوظ — أعدلُ للكبتن. <b className="text-ink">والبثّ</b>{" "}
              يعرض على دفعةٍ معاً وأولُ من يقبل يأخذ — أسرعُ للراكب، وأقسى على
              الكبتن لأن أربعةً يرون بطاقةً يفوز بها واحد. والترتيبُ في النمطين
              واحد: الأقربُ أولاً والمستوى يفصل بين المتقاربين. <b className="text-ink">
              وما يُحفظ هنا لا يمسّ بحثاً جارياً</b> — يُقرأ مرةً عند بدء توزيع
              الرحلة، فتبديلُه في منتصف بحثٍ يترك حالاً نصفَ متغيّرة.
            </p>
            <DispatchForm
              key={country}
              row={dispatchRow}
              country={country}
              disabled={!isAdmin}
              onSaved={(message) => {
                setDone(message);
                void load();
              }}
              onError={(caught) => form.capture(caught, "تعذّر الحفظ")}
            />
          </section>

          {/* سقوفُ طلب رمز التحقق — **سياسةُ حسابٍ لا خاصيةُ قناة**:
              تُقاس على الرقم فتسري على واتساب والرسائل معاً، ومن استنفد
              محاولاته لا يلتفّ عليها بتبديل القناة */}
          <section className="rounded-16 border border-line bg-surface p-18">
            <h2 className="mb-4 text-14 font-bold text-ink">خريطة الراكب</h2>
            <p className="mb-12 text-11 leading-snug text-muted">
              <b className="text-ink">حدُّ العرض لا حدُّ التوزيع</b>: هذان
              الرقمان يحكمان كم سيارةً يرى الراكبُ وإلى أيِّ بُعد،{" "}
              <b className="text-ink">ولا يمسّان من يصله الطلب</b> — مدى البحث
              في التوزيع قاعدةُ مواصفةٍ في الكود لا حقلٌ هنا. سوقٌ كثيفٌ
              يضيّق (خمسون سيارةً على شاشةِ هاتفٍ زحمةٌ لا معلومة)، ومتفرّقٌ
              يوسّع وإلا بدت الخريطةُ خاليةً وفيها كباتن.{" "}
              <b className="text-ink">والصفرُ مرفوض</b>: يُطفأ العرضُ بمفتاحه
              لا بتصفير رقمِه.
            </p>
            {mapRow ? (
              <MapForm
                key={mapRow.country_code}
                row={mapRow}
                disabled={!isAdmin}
                onSaved={(message) => {
                  setDone(message);
                  void load();
                }}
                onError={(caught) => form.capture(caught, "تعذّر الحفظ")}
              />
            ) : (
              <p className="text-12.5 text-muted">
                لا حدودَ محفوظةٌ لهذه الدولة — تُكتب بأول حفظ.
              </p>
            )}
          </section>

          <section className="rounded-16 border border-line bg-surface p-18">
            <h2 className="mb-4 text-14 font-bold text-ink">سقوف رمز التحقق</h2>
            <p className="mb-12 text-11 leading-snug text-muted">
              <b className="text-ink">ثلاثةُ سقوفٍ لا واحد</b>: نافذةٌ قصيرةٌ
              تمنع الرشق، ويوميٌّ يمنع من ينتظر الساعةَ ثم يعود،{" "}
              <b className="text-ink">وعمرُ التسجيل</b> — وهو الذي لا يُشترى
              بالصبر، لأن التسجيل حدثٌ مرةً لا حدثٌ متكرر (ويُصفَّر بإنشاء
              الحساب). <b className="text-ink">وصفرُ أيِّها «لا سقف»</b>، وهي
              حرّاسٌ لا ميزات فلا تُفتح بالسكوت. والعدُّ على{" "}
              <b className="text-ink">الرقم لا على الشبكة</b>: مقهىً كاملاً لا
              يخنقه مسيءٌ واحد.
            </p>
            {otpRow ? (
              <OtpForm
                key={otpRow.country_code}
                row={otpRow}
                disabled={!isAdmin}
                onSaved={(message) => {
                  setDone(message);
                  void load();
                }}
                onError={(caught) => form.capture(caught, "تعذّر الحفظ")}
              />
            ) : (
              <p className="text-12.5 text-muted">
                لا سقوفَ محفوظةٌ لهذه الدولة — تُكتب بأول حفظ، والافتراضاتُ
                الحارسةُ سارية.
              </p>
            )}

            {/* **ومؤشّرُ من استنفد اليوم** — رؤيةٌ قبل أن يحرق الرقمَ لا بعده */}
            <div className="mt-14 rounded-12 border border-line bg-surface-2 px-14 py-12">
              <p className="text-12 font-bold text-ink">
                أرقامٌ استنفدت محاولاتها اليوم
                {burned && burned.phones.length > 0
                  ? ` (${digits(String(burned.phones.length))})`
                  : ""}
              </p>
              {burned && burned.phones.length > 0 ? (
                <ul className="mt-8 flex flex-wrap gap-8">
                  {burned.phones.map((phone) => (
                    <li
                      key={phone}
                      dir="ltr"
                      className="rounded-full border border-line px-9 py-3 text-11 text-warn"
                    >
                      {phone}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-4 text-11 text-muted">
                  لا شيء اليوم — وتكرارٌ مشبوهٌ هنا يعني محاولةَ استنزافٍ تُرى
                  قبل أن تُحرق رقمَ الإرسال.
                </p>
              )}
            </div>
          </section>

          {/* سياسةُ رسم الإلغاء (`design/CANCELLATION-FEE.md`) — **ولا حقلَ
              للمبلغ هنا**: قيمتُه في «التسعيرة» لأنها لكل فئةِ مركبة، وهذه
              سياسةٌ لا سعر */}
          <section className="rounded-16 border border-line bg-surface p-18">
            <h2 className="mb-4 text-14 font-bold text-ink">رسم الإلغاء</h2>
            <p className="mb-12 text-11 leading-snug text-muted">
              <b className="text-ink">تعويضٌ لا غرامة</b> — يقبضه الكبتنُ الذي
              تحرّك، لا الشركة. <b className="text-ink">ولا رسمَ على إلغاءٍ لم
              يُتعِب أحداً</b>: يُقاس القربُ من آخر موقعٍ بثّه الكبتن، فمن لم
              يبرح مكانَه لا يُحصَّل له شيء. <b className="text-ink">وقيمةُ الرسم
              في «التسعيرة»</b> لأنها لكل فئةِ مركبة. والأصفارُ هنا تعني «لم
              يُضبط» لا «صفراً»: لا إيقاف، ولا مهلةَ للحامل، ولا إجراءَ على
              دَينٍ قديم.
            </p>
            {cancellationRow ? (
              <CancellationForm
                key={cancellationRow.country_code}
                row={cancellationRow}
                disabled={!isAdmin}
                onSaved={(message) => {
                  setDone(message);
                  void load();
                }}
                onError={(caught) => form.capture(caught, "تعذّر الحفظ")}
              />
            ) : (
              <p className="text-12.5 text-muted">
                لا سياسةَ إلغاءٍ لهذه الدولة بعد — تُكتب بأول حفظ.
              </p>
            )}
          </section>

          {/* مشاركةُ الرحلة (12-ي) — بطاقةٌ مستقلةٌ لجدولٍ مستقل، وأرقامُ
              المعايرةِ الثلاثةُ **مع النسبة لا في شاشةٍ أخرى**: من يضبط الخصم
              يحتاج أن يرى ما يجعل المشاركةَ تقع أصلاً */}
          <section className="rounded-16 border border-line bg-surface p-18">
            <h2 className="mb-4 text-14 font-bold text-ink">مشاركة الرحلة</h2>
            <p className="mb-12 text-11 leading-snug text-muted">
              راكبان في سيارةٍ واحدة بخصمٍ لكليهما{" "}
              <b className="text-ink">تتحمّله الشركة</b> — فلا يَنقص ما يقبضه
              الكبتن. <b className="text-ink">وصفرُ النسبة يعني «لم تُحدَّد»</b>{" "}
              فلا تُعرض المشاركةُ ولو كان المفتاح مشتعلاً. وعاير النسبةَ على
              قاعدةٍ واحدة: ما يقبضه الكبتن من رحلتين أعلى بوضوحٍ مما يقبضه من
              منفردة، وإلا رفض المشاركةَ وهو محقّ. والثلاثةُ الباقيةُ تحكم من
              يُطابَق بمن، وتسري على الطلب التالي لا على رحلةٍ سائرة.
            </p>
            {sharing ? (
              <SharingForm
                key={sharing.country_code}
                row={sharing}
                disabled={!isAdmin}
                onSaved={(message) => {
                  setDone(message);
                  void load();
                }}
                onError={(caught) => form.capture(caught, "تعذّر الحفظ")}
              />
            ) : (
              <p className="text-12.5 text-muted">لا إعداد مشاركةٍ لهذه الدولة.</p>
            )}
          </section>
        </div>
      )}

      {guard ? (
        <GuardModal
          flagKey={guard.key}
          onClose={() => setGuard(null)}
          onConfirm={(reason) => {
            setGuard(null);
            void flip(guard.key, false, reason);
          }}
        />
      ) : null}
    </Shell>
    </FormErrors>
  );
}

function CommissionForm({
  row,
  disabled,
  onSaved,
  onError,
}: {
  row: CommissionSetting;
  disabled: boolean;
  onSaved: (message: string) => void;
  onError: (caught: unknown) => void;
}) {
  const [percent, setPercent] = useState(row.commission_percent);
  const [enabled, setEnabled] = useState(row.commission_enabled);
  const [scope, setScope] = useState(row.applies_to);
  const [busy, setBusy] = useState(false);

  return (
    <>
      <Field
        label="النسبة ٪"
        name="commission_percent"
        dir="ltr"
        inputMode="decimal"
        value={percent}
        disabled={disabled}
        onChange={(event) =>
          setPercent(event.target.value.replace(/[^0-9.]/g, ""))
        }
      />

      <div className="mt-12">
        <span className="label">النطاق</span>
        <div className="flex gap-8">
          {(["all_rides", "cashless_rides"] as const).map((key) => (
            <button
              key={key}
              type="button"
              disabled={disabled}
              onClick={() => setScope(key)}
              className={cn(
                "flex-1 rounded-12 border px-12 py-10 text-12",
                scope === key
                  ? "border-ink font-semibold text-ink"
                  : "border-line text-muted",
              )}
            >
              {key === "all_rides"
                ? "كل الرحلات (ومنها الكاش)"
                : "ما يمر بالمنصة فقط (محفظة وبطاقة)"}
            </button>
          ))}
        </div>
        <p className="mt-6 text-11 leading-snug text-muted">
          «كل الرحلات» تعني أن عمولة رحلة الكاش تُخصم من محفظة الكبتن — وقد
          تُنقص رصيده.
        </p>
      </div>

      {/* مفتاحٌ لا مربّعُ اختيار: الصفحةُ كلُّها مفاتيح، ومربّعٌ خامٌ بينها
          يقرأ كأنه من نموذجٍ آخر */}
      <div className="mt-14 flex items-center gap-10">
        <Switch
          checked={enabled}
          disabled={disabled}
          label="تفعيل العمولة"
          onChange={setEnabled}
        />
        <span className="text-12.5 text-ink">
          {enabled ? "مفعّلة" : "معطّلة"}
        </span>
      </div>

      <Button
        className="mt-14"
        size="sm"
        disabled={disabled}
        loading={busy}
        onClick={() => {
          setBusy(true);
          updateCommission(row.country_code, {
            commission_enabled: enabled,
            commission_percent: percent,
            applies_to: scope,
          })
            .then(() => onSaved("حُفظت العمولة"))
            .catch((caught) =>
              onError(caught),
            )
            .finally(() => setBusy(false));
        }}
      >
        حفظ
      </Button>
    </>
  );
}

function WalletForm({
  row,
  disabled,
  onSaved,
  onError,
}: {
  row: WalletSetting;
  disabled: boolean;
  onSaved: (message: string) => void;
  onError: (caught: unknown) => void;
}) {
  const [daily, setDaily] = useState(row.transfer_daily_limit);
  const [monthly, setMonthly] = useState(row.transfer_monthly_limit);
  const [minimum, setMinimum] = useState(row.min_withdrawal_amount);
  const [reserve, setReserve] = useState(row.withdrawal_reserve_amount);
  const [busy, setBusy] = useState(false);

  const clean = (value: string) => value.replace(/[^0-9.]/g, "");

  return (
    <>
      <Field
        name="transfer_daily_limit"
        label="حد التحويل اليومي"
        dir="ltr"
        inputMode="decimal"
        value={daily}
        disabled={disabled}
        onChange={(event) => setDaily(clean(event.target.value))}
      />
      <div className="mt-12">
        <Field
          name="transfer_monthly_limit"
          label="حد التحويل الشهري"
          dir="ltr"
          inputMode="decimal"
          value={monthly}
          disabled={disabled}
          onChange={(event) => setMonthly(clean(event.target.value))}
        />
      </div>
      <div className="mt-12">
        <Field
          name="min_withdrawal_amount"
          label="الحد الأدنى للسحب"
          dir="ltr"
          inputMode="decimal"
          value={minimum}
          disabled={disabled}
          onChange={(event) => setMinimum(clean(event.target.value))}
        />
      </div>
      <div className="mt-12">
        <Field
          name="withdrawal_reserve_amount"
          label="الرصيد المحتجَز (لا يُسحب)"
          dir="ltr"
          inputMode="decimal"
          value={reserve}
          disabled={disabled}
          onChange={(event) => setReserve(clean(event.target.value))}
        />
        <p className="mt-6 text-11 leading-note text-muted">
          يبقى في محفظة الكبتن ولا يدخل المتاح للسحب، ويُصرف عند إلغاء تفعيل
          حسابه. **وصفرٌ يعني لا احتجاز.**
        </p>
      </div>

      <Button
        className="mt-14"
        size="sm"
        disabled={disabled}
        loading={busy}
        onClick={() => {
          setBusy(true);
          updateWalletSettings(row.country_code, {
            transfer_daily_limit: daily,
            transfer_monthly_limit: monthly,
            min_withdrawal_amount: minimum,
            withdrawal_reserve_amount: reserve,
          })
            .then(() => onSaved("حُفظت الحدود"))
            .catch((caught) =>
              onError(caught),
            )
            .finally(() => setBusy(false));
        }}
      >
        حفظ
      </Button>
    </>
  );
}

/** مبلغُ الحافز وحدُّ الرحلات. **و`key={country}` عليه كبقية النماذج**:
 *  `useState(row.…)` لا يُعاد قراءتُه عند تبدّل الخاصية، فتبديلُ السوق يكتب
 *  رقمَ سوقٍ في سوقٍ آخر — وهو عطبٌ وقع في هذه الشاشة نفسها. */
/** برنامجُ إحالةٍ واحد — والنسائيُّ **علاوةٌ بجانب الأساس لا حقلٌ مستقل**.
 *
 * **حارسُ المالك (2026-08-16)**: مشرفٌ يرى رقمين منفصلين قد يظنّ الثاني بديلاً
 * عن الأول — وهو بالضبط سوءُ الفهم الذي يصنع الفخَّ نفسَه من بابٍ آخر. فالحقلُ
 * لا يُعرض إلا في برنامج السائقين، وتحته جملةٌ تقول **المُحصَّل** لا العلاوة.
 */
function ReferralForm({
  row,
  disabled,
  onSaved,
  onError,
}: {
  row: ReferralSetting;
  disabled: boolean;
  onSaved: (message: string) => void;
  onError: (caught: unknown) => void;
}) {
  const [amount, setAmount] = useState(row.reward_amount);
  const [rides, setRides] = useState(String(row.required_rides));
  const [bonus, setBonus] = useState(row.female_bonus_amount);
  const [cap, setCap] = useState(
    row.monthly_cap === null ? "" : String(row.monthly_cap),
  );
  const [busy, setBusy] = useState(false);

  const isDriver = row.referral_type === "driver";
  const currency = currencyOf(row.country_code);
  const total = (Number(amount) || 0) + (Number(bonus) || 0);

  return (
    <div className="rounded-13 border border-line p-14">
      <h3 className="mb-10 text-13 font-bold text-ink">
        {isDriver ? "من يُحيل كبتناً" : "من يُحيل راكباً"}
      </h3>
      <div className="grid grid-cols-2 gap-10">
        <Field
          name="reward_amount"
          label={`مبلغ المكافأة (${currencyLabel(currency)})`}
          dir="ltr"
          inputMode="decimal"
          value={amount}
          disabled={disabled}
          onChange={(event) =>
            setAmount(event.target.value.replace(/[^0-9.]/g, ""))
          }
        />
        <Field
          name="required_rides"
          label={isDriver ? "رحلات المُحال المطلوبة" : "رحلات المُحال المطلوبة"}
          dir="ltr"
          inputMode="numeric"
          value={rides}
          disabled={disabled}
          onChange={(event) => setRides(event.target.value.replace(/[^0-9]/g, ""))}
        />
        {isDriver ? (
          <Field
            name="female_bonus_amount"
            label={`علاوة إحالة سائقة (${currencyLabel(currency)})`}
            dir="ltr"
            inputMode="decimal"
            value={bonus}
            disabled={disabled}
            onChange={(event) =>
              setBonus(event.target.value.replace(/[^0-9.]/g, ""))
            }
          />
        ) : null}
        <Field
          name="monthly_cap"
          label="سقف شهري لكل مُحيل"
          dir="ltr"
          inputMode="numeric"
          value={cap}
          placeholder="بلا سقف"
          disabled={disabled}
          onChange={(event) => setCap(event.target.value.replace(/[^0-9]/g, ""))}
        />
      </div>

      {/* **الجملةُ تقول المُحصَّل لا العلاوة** — شرطُ المالك بحرفه */}
      {isDriver && Number(bonus) > 0 ? (
        <p className="mt-8 text-11 text-ok">
          المُحصَّل للإحالة النسائية ={" "}
          <b>{money(String(total.toFixed(3)), currency)}</b> — الأساسُ{" "}
          {money(amount || "0", currency)} + العلاوةُ {money(bonus, currency)}.
          والعلاوةُ تُضاف إليه ولا تحلّ محلَّه.
        </p>
      ) : null}

      <p className="mt-6 text-11 text-muted">
        {Number(row.reward_amount) > 0
          ? `الحالي: ${money(row.reward_amount, currency)} بعد ${digits(String(row.required_rides))} رحلات`
          : `لم يُحدَّد مبلغٌ بعد — والشرطُ ${digits(String(row.required_rides))} رحلات`}
        {row.monthly_cap === null
          ? " · بلا سقفٍ شهري"
          : ` · سقفُ ${digits(String(row.monthly_cap))} إحالاتٍ في الشهر لكل مُحيل`}
      </p>
      {/* **والحقلُ الفارغ يعني «بلا سقف» صراحةً** لا «لا تلمسه»: حالتان لا
          يحملهما رقمٌ واحد، فيُرسل `clear_monthly_cap` بدل صفرٍ يُقرأ خطأً */}
      <Button
        className="mt-14"
        size="sm"
        disabled={disabled || amount === "" || rides === ""}
        loading={busy}
        onClick={() => {
          setBusy(true);
          updateReferralSettings(row.country_code, row.referral_type, {
            reward_amount: amount,
            required_rides: Number(rides),
            ...(isDriver ? { female_bonus_amount: bonus || "0" } : {}),
            ...(cap === ""
              ? { clear_monthly_cap: true }
              : { monthly_cap: Number(cap) }),
          })
            .then(() =>
              onSaved("حُفظ الحافز — يُقيَّم ما لم يُدفع بالحدّ الجديد"),
            )
            .catch((caught) =>
              onError(caught),
            )
            .finally(() => setBusy(false));
        }}
      >
        حفظ
      </Button>
    </div>
  );
}


function PaymentForm({
  row,
  disabled,
  onSaved,
  onError,
}: {
  row: PaymentSetting;
  disabled: boolean;
  onSaved: (message: string) => void;
  onError: (caught: unknown) => void;
}) {
  const [hours, setHours] = useState(row.cliq_confirmation_hours);
  const [alias, setAlias] = useState(row.cliq_alias ?? "");
  const [reviewMin, setReviewMin] = useState(row.cliq_review_min_minutes);
  const [reviewMax, setReviewMax] = useState(row.cliq_review_max_minutes);
  // **فارغٌ يعني «لا سقفَ»** — والحقلُ لا يُملأ بصفرٍ ولا بافتراضٍ مخترَع
  const [debtCeiling, setDebtCeiling] = useState(row.driver_debt_ceiling ?? "");
  const [qrBusy, setQrBusy] = useState(false);
  const [small, setSmall] = useState(row.tip_preset_small);
  const [medium, setMedium] = useState(row.tip_preset_medium);
  const [max, setMax] = useState(row.tip_max);
  const [busy, setBusy] = useState(false);

  /** مبلغُ مالٍ كما يُكتب — **بلا أرقامٍ عربية-هندية**: حقلٌ يُكتب فيه لا يُقرأ. */
  const money = (value: string) => value.replace(/[^0-9.]/g, "");

  function save(
    payload: Parameters<typeof updatePaymentSettings>[1],
    message: string,
  ) {
    setBusy(true);
    updatePaymentSettings(row.country_code, payload)
      .then(() => onSaved(message))
      .catch((caught) =>
        onError(caught),
      )
      .finally(() => setBusy(false));
  }

  return (
    <>
      <DurationField
        name="cliq_confirmation_hours"
        label="مهلة تأكيد الحوالة"
        wire="hour"
        value={hours}
        disabled={disabled}
        onChange={setHours}
      />
      <p className="mt-6 text-11 text-muted">
        الحالي: {digits(String(row.cliq_confirmation_hours))} ساعة
      </p>

      <Button
        className="mt-14"
        size="sm"
        disabled={disabled || !hours}
        loading={busy}
        onClick={() =>
          save(
            { cliq_confirmation_hours: hours },
            "حُفظت المهلة — تسري على ما يأتي بعدها",
          )
        }
      >
        حفظ
      </Button>

      {/* **حسابُ كليك المستقبِل ومدّةُ المراجعة** (قرارُ المالك 2026-08-29)
          — سياسةُ دفعٍ لكلِّ سوق، **فبيتُها `payment_settings`** مع مهلة كليك.
          **وتعديلُ حسابٍ يستقبل مالَ الناس لا يكون نشراً.** */}
      <div className="mt-18 border-t border-line pt-14">
        <h3 className="mb-2 text-12.5 font-bold text-ink">استقبال كليك</h3>
        <p className="mb-12 text-11 leading-snug text-muted">
          الحساب الذي يحوّل إليه الكبتن ثمنَ اشتراكه — ويُعرض له كما هو.
          وبلا حساب <strong>تُخفى طريقةُ كليك كلُّها</strong>: شاشةٌ تطلب
          تحويلاً بلا رقمٍ تُنتج حوالةً ضائعة.
        </p>
        <Field
          name="cliq_alias"
          label="حساب كليك (alias)"
          dir="ltr"
          value={alias}
          disabled={disabled}
          maxLength={64}
          onChange={(event) => setAlias(event.target.value)}
        />

        {/* **العددان وعدٌ لمن يدفع** — «خلال ٣ إلى ٥ دقائق» تصير كذباً يومَ
            تكثر الطلباتُ ولا تلحق المراجعة، **فتُعدَّل بلا نشر** */}
        <div className="mt-12 grid grid-cols-2 gap-10">
          <DurationField
            name="cliq_review_min_minutes"
            label="أدنى مدّة المراجعة"
            wire="minute"
            value={reviewMin}
            disabled={disabled}
            onChange={setReviewMin}
          />
          <DurationField
            name="cliq_review_max_minutes"
            label="أعلى مدّة المراجعة"
            wire="minute"
            value={reviewMax}
            disabled={disabled}
            onChange={setReviewMax}
          />
        </div>
        <p className="mt-6 text-11 leading-snug text-muted">
          تظهر للكبتن هكذا: «ستتم المراجعة خلال {digits(reviewMin || "0")} إلى{" "}
          {digits(reviewMax || "0")} دقائق».
        </p>

        {/* **سقفُ الدَّين — فارغٌ عمداً حتى يقرّره المالك** (الترحيلة `0061`).
            **وفارغٌ يعني «لا حجبَ»**، لا «احجب عند صفر». */}
        <div className="mt-16 border-t border-line pt-12">
          <h3 className="mb-2 text-12.5 font-bold text-ink">سقف دَين الكبتن</h3>
          <Field
            name="driver_debt_ceiling"
            label={`فوقه يتوقف استقباله للطلبات (${currencyLabel(currencyOf(row.country_code))})`}
            dir="ltr"
            inputMode="decimal"
            placeholder="اتركه فارغاً: لا سقف"
            value={debtCeiling}
            disabled={disabled}
            onChange={(event) =>
              setDebtCeiling(event.target.value.replace(/[^0-9.]/g, ""))
            }
          />
          <p className="mt-6 text-11 leading-snug text-muted">
            الدَّين هو عمولة الرحلات التي قبض الكبتن أجرتها بيده. الحقل فارغاً
            يعني أنه لا يُحجب أحد مهما بلغ — والدَّين يُسجَّل ويُحصَّل على كل
            حال. وحين يُكتب رقم، يُرفع الحجب عند بلوغ الدَّين صفراً لا عند
            نزوله تحت السقف.
          </p>
        </div>

        <Button
          className="mt-14"
          size="sm"
          disabled={disabled || !reviewMin || !reviewMax}
          loading={busy}
          onClick={() =>
            save(
              {
                cliq_alias: alias.trim(),
                cliq_review_min_minutes: reviewMin,
                cliq_review_max_minutes: reviewMax,
                // **الفارغُ يُرسَل `null` صراحةً** لا يُحذف من الحمولة:
                // حقلٌ محذوفٌ يُقرأ «لم يُمسّ» فلا يُمحى سقفٌ قائم
                driver_debt_ceiling: debtCeiling.trim() || null,
              },
              "حُفظ استقبال كليك",
            )
          }
        >
          حفظ
        </Button>

        {/* **صورةُ الرمز تُرفع ولا تُولَّد**: رمزُ كليك يصدره القابضُ بحقوله
            المعيارية، **وباركودٌ لا يعمل أسوأُ من غيابه**. والشاشةُ تعمل
            بلا صورة — حسابٌ ومبلغٌ ومرجع. */}
        <div className="mt-16 border-t border-line pt-12">
          <h3 className="mb-2 text-12.5 font-bold text-ink">صورة الباركود</h3>
          <p className="mb-10 text-11 leading-snug text-muted">
            ارفع الرمزَ الذي يولّده تطبيقُ بنكك. ولا يُولَّد من الحساب:
            معيارُه يحمل حقولاً لا تُشتقّ منه — وبلا صورةٍ تعمل الشاشةُ
            بالحساب والمبلغ والمرجع.
            {row.cliq_qr_path ? " — مرفوعةٌ الآن." : " — لم تُرفع بعد."}
          </p>
          <input
            type="file"
            accept="image/*"
            disabled={disabled || qrBusy}
            aria-label="صورة باركود كليك"
            className="block w-full text-11 text-muted"
            onChange={(event) => {
              const picked = event.target.files?.[0];
              if (!picked) return;
              setQrBusy(true);
              uploadCliqQr(row.country_code, picked)
                .then(() => onSaved("رُفعت صورة الباركود"))
                .catch((caught) => onError(caught))
                .finally(() => setQrBusy(false));
            }}
          />
        </div>
      </div>

      {/* مبالغُ البقشيش (12-و) — في بطاقة **سياسات الدفع** لا في «التسعيرة»:
          الجدولُ هو `payment_settings`، وحقلٌ يسكن شاشةً غير جدوله يجعل
          البحثَ عنه تخميناً. والصفرُ يُخفي الميزةَ فلا حدَّ أدنى يمنع إطفاءها */}
      <div className="mt-18 border-t border-line pt-14">
        <h3 className="mb-2 text-12.5 font-bold text-ink">مبالغ البقشيش</h3>
        <p className="mb-12 text-11 leading-snug text-muted">
          زرّان يراهما الراكب بعد التقييم، وسقفٌ يحرس من إصبعٍ تزلّ. والصفرُ يعني
          «لم يُضبط» فتُخفى الأزرار — لا بقشيشاً مقداره صفر. ويصل الكبتنَ كاملاً
          بلا عمولة.
        </p>
        <div className="grid grid-cols-3 gap-10">
          <Field
            name="tip_preset_small"
            label="الزر الأول"
            dir="ltr"
            inputMode="decimal"
            value={small}
            disabled={disabled}
            onChange={(event) => setSmall(money(event.target.value))}
          />
          <Field
            name="tip_preset_medium"
            label="الزر الثاني"
            dir="ltr"
            inputMode="decimal"
            value={medium}
            disabled={disabled}
            onChange={(event) => setMedium(money(event.target.value))}
          />
          <Field
            name="tip_max"
            label="السقف"
            dir="ltr"
            inputMode="decimal"
            value={max}
            disabled={disabled}
            onChange={(event) => setMax(money(event.target.value))}
          />
        </div>
        <Button
          className="mt-14"
          size="sm"
          variant="secondary"
          disabled={disabled || !small || !medium || !max}
          loading={busy}
          onClick={() =>
            save(
              {
                tip_preset_small: small,
                tip_preset_medium: medium,
                tip_max: max,
              },
              "حُفظت مبالغ البقشيش",
            )
          }
        >
          حفظ المبالغ
        </Button>
      </div>
    </>
  );
}

/** إطفاءُ الحارس — بتحذيرٍ صريح وسببٍ إلزامي يدخل سجل التدقيق. */
function GuardModal({
  flagKey,
  onClose,
  onConfirm,
}: {
  flagKey: FeatureKey;
  onClose: () => void;
  onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState("");

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-dim px-20"
      onClick={onClose}
    >
      <div
        className="w-modal max-w-full rounded-20 border border-danger bg-surface p-24"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 className="mb-4 text-16 font-bold text-danger">
          إطفاء «{FLAG_LABEL[flagKey].title}» — للطوارئ فقط
        </h2>
        <p className="mb-16 text-12 leading-note text-muted">
          {GUARD_NOTE[flagKey as GuardedFlag]}
        </p>

        <Field
          name="reason"
          label="سبب الإطفاء (يدخل سجل التدقيق)"
          placeholder="ثمانية أحرف على الأقل"
          value={reason}
          maxLength={280}
          onChange={(event) => setReason(event.target.value)}
        />

        <div className="mt-18 flex gap-10">
          <Button
            className="flex-1 border-danger text-danger"
            size="md"
            variant="secondary"
            disabled={reason.trim().length < 8}
            onClick={() => onConfirm(reason.trim())}
          >
            أطفئ الحارس
          </Button>
          <Button className="flex-1" size="md" onClick={onClose}>
            تراجع
          </Button>
        </div>
      </div>
    </div>
  );
}

/** أرقامُ المشاركة الأربعة (12-ي).
 *
 * **والنسبةُ وحدَها في صفٍّ ثم الثلاثةُ تحتها**، لأنها الوحيدةُ التي تعني مالاً:
 * الثلاثةُ الأخرى معايرةٌ تشغيليةٌ لا يراها راكبٌ ولا كبتن. وخلطُها في شبكةٍ
 * واحدةٍ يجعل حقلَ المال يُقرأ كأحدها.
 */
function SharingForm({
  row,
  disabled,
  onSaved,
  onError,
}: {
  row: RideSharingSetting;
  disabled: boolean;
  onSaved: (message: string) => void;
  onError: (caught: unknown) => void;
}) {
  const [percent, setPercent] = useState(row.discount_percent);
  const [corridor, setCorridor] = useState(row.corridor_km);
  const [detour, setDetour] = useState(row.max_detour_minutes);
  const [wait, setWait] = useState(row.partner_wait_seconds);
  const [busy, setBusy] = useState(false);

  return (
    <>
      <Field
        name="discount_percent"
        label="نسبة الخصم ٪"
        dir="ltr"
        inputMode="decimal"
        value={percent}
        disabled={disabled}
        onChange={(event) =>
          setPercent(event.target.value.replace(/[^0-9.]/g, ""))
        }
      />
      <p className="mt-6 text-11 text-muted">
        {Number(row.discount_percent) > 0
          ? `الحالي: خصمٌ ${digits(row.discount_percent)}٪ لكلِّ راكبٍ في المجموعة`
          : "لم تُحدَّد نسبةٌ بعد — والمشاركةُ لا تُعرض على أحد"}
      </p>

      <div className="mt-14 grid grid-cols-3 gap-10">
        <Field
          name="corridor_km"
          label="عرض الممر (كم)"
          dir="ltr"
          inputMode="decimal"
          value={corridor}
          disabled={disabled}
          onChange={(event) =>
            setCorridor(event.target.value.replace(/[^0-9.]/g, ""))
          }
        />
        <DurationField
          name="max_detour_minutes"
          label="أقصى التفاف"
          wire="minute"
          value={detour}
          disabled={disabled}
          onChange={setDetour}
        />
        <DurationField
          name="partner_wait_seconds"
          label="انتظار الشريك"
          value={wait}
          disabled={disabled}
          onChange={setWait}
        />
      </div>
      <p className="mt-6 text-11 leading-snug text-muted">
        الممرُّ يحدّد من يُعرض عليه الالتحاق: نقطتا الراكب الثاني داخل هذه
        المسافة من مسار الأول. والالتفافُ سقفُ ما تطول به رحلةُ{" "}
        <b className="text-ink">من قَبِل أولاً</b> — يحميه هو لا الثاني.
        والانتظارُ كم تبقى رحلتُه مفتوحةً لشريك.
      </p>

      <Button
        className="mt-14"
        size="sm"
        // **والمدّتان خرجتا من الشرط ولم تصيرا `=== 0`** (قِيس في
        // `schemas/sharing.py`): `max_detour_minutes` و`partner_wait_seconds`
        // كلتاهما `ge=0` — **فالصفرُ إعدادٌ صحيح** («لا التفافَ» و«لا انتظار»)،
        // وحقلُ المدّة لا يُترك فارغاً أصلاً. **ومنعُه كان سيمنع ضبطاً تقبله
        // الخلفية.**
        disabled={disabled || percent === "" || corridor === ""}
        loading={busy}
        onClick={() => {
          setBusy(true);
          updateSharingSettings(row.country_code, {
            discount_percent: percent,
            corridor_km: corridor,
            max_detour_minutes: detour,
            partner_wait_seconds: wait,
          })
            .then(() =>
              onSaved("حُفظت المشاركة — تسري على الطلب التالي، ولا تمسّ رحلةً قائمة"),
            )
            .catch((caught) =>
              onError(caught),
            )
            .finally(() => setBusy(false));
        }}
      >
        حفظ
      </Button>
    </>
  );
}


function AdvanceForm({
  row,
  disabled,
  onSaved,
  onError,
}: {
  row: AdvanceSetting;
  disabled: boolean;
  onSaved: (message: string) => void;
  onError: (caught: unknown) => void;
}) {
  const [percent, setPercent] = useState(String(row.deduction_percent));
  const [kept, setKept] = useState(row.min_kept_amount);
  const [term, setTerm] = useState(row.term_days);
  const [rides, setRides] = useState(String(row.min_completed_rides));
  const [rating, setRating] = useState(row.min_rating);
  const [growth, setGrowth] = useState(String(row.growth_percent_per_repaid));
  const [ceiling, setCeiling] = useState(String(row.max_multiplier_percent));
  const [busy, setBusy] = useState(false);

  const digits = (value: string) => value.replace(/[^0-9]/g, "");
  const decimal = (value: string) => value.replace(/[^0-9.]/g, "");

  return (
    <>
      <div className="grid grid-cols-2 gap-10">
        <Field
          name="deduction_percent"
          label="نسبة الاقتطاع من الرحلة (٪)"
          dir="ltr"
          inputMode="numeric"
          value={percent}
          disabled={disabled}
          onChange={(event) => setPercent(digits(event.target.value))}
        />
        <Field
          name="min_kept_amount"
          label={`أقل ما يبقى له من الرحلة (${currencyLabel(currencyOf(row.country_code))})`}
          dir="ltr"
          inputMode="decimal"
          value={kept}
          disabled={disabled}
          onChange={(event) => setKept(decimal(event.target.value))}
        />
        <DurationField
          name="term_days"
          label="مهلة التحصيل"
          wire="day"
          value={term}
          disabled={disabled}
          onChange={setTerm}
        />
        <Field
          name="min_completed_rides"
          label="رحلات مكتملة مطلوبة"
          dir="ltr"
          inputMode="numeric"
          value={rides}
          disabled={disabled}
          onChange={(event) => setRides(digits(event.target.value))}
        />
        <Field
          name="min_rating"
          label="أدنى تقييم مطلوب"
          dir="ltr"
          inputMode="decimal"
          value={rating}
          disabled={disabled}
          onChange={(event) => setRating(decimal(event.target.value))}
        />
        <Field
          name="growth_percent_per_repaid"
          label="نمو السقف عن كل سلفة سُدِّدت (٪)"
          dir="ltr"
          inputMode="numeric"
          value={growth}
          disabled={disabled}
          onChange={(event) => setGrowth(digits(event.target.value))}
        />
        <Field
          name="max_multiplier_percent"
          label="السقف الأقصى (٪ من اليومي)"
          dir="ltr"
          inputMode="numeric"
          value={ceiling}
          disabled={disabled}
          onChange={(event) => setCeiling(digits(event.target.value))}
        />
      </div>
      <p className="mt-6 text-11 leading-note text-muted">
        الاقتطاعُ يقف عند ثلاثةِ حدود: النسبة، والمتبقّي من الدَّين، وما يجب أن
        يبقى للكبتن — فاقتطاعٌ يستنزف أرباحَه يوقفه عن العمل، فيمتنع السدادُ
        نفسُه. وصفرُ «أقل ما يبقى» يعني «لا حدَّ» فالنسبةُ وحدها تحكم.
      </p>
      <Button
        className="mt-14"
        size="sm"
        // **`term_days` صفراً ترفضه الخلفية** (`gt=0` في `schemas/driver.py`)،
        // فالشرطُ يقول ما كانت تقوله الفراغيّةُ نفسَه — **ويقوله قبل النداء**
        disabled={disabled || percent === "" || term === 0}
        loading={busy}
        onClick={() => {
          setBusy(true);
          updateAdvanceSettings(row.country_code, {
            deduction_percent: Number(percent),
            min_kept_amount: kept,
            term_days: term,
            min_completed_rides: Number(rides),
            min_rating: rating,
            growth_percent_per_repaid: Number(growth),
            max_multiplier_percent: Number(ceiling),
          })
            .then(() =>
              onSaved("حُفظت السياسة — تسري على ما يُصرف بعدها لا على سلفةٍ قائمة"),
            )
            .catch((caught) =>
              onError(caught),
            )
            .finally(() => setBusy(false));
        }}
      >
        حفظ
      </Button>
    </>
  );
}

/** سياسةُ رسم الإلغاء — **ولا حقلَ للمبلغ**: قيمتُه في «التسعيرة» لأنها لكل
 *  فئةِ مركبة (`design/CANCELLATION-FEE.md`).
 *
 *  **و`key={country}` عليه كبقية النماذج**: بغيره تبقى أرقامُ السوق السابق في
 *  الحقول بعد تبديل الرأس، فيُحفظ إعدادُ الأردن في ليبيا.
 */
function CancellationForm({
  row,
  disabled,
  onSaved,
  onError,
}: {
  row: CancellationSetting;
  disabled: boolean;
  onSaved: (message: string) => void;
  onError: (caught: unknown) => void;
}) {
  const [metres, setMetres] = useState(String(row.exempt_within_meters));
  const [silent, setSilent] = useState(row.exempt_when_location_unknown);
  const [block, setBlock] = useState(String(row.block_after_unpaid));
  const [grace, setGrace] = useState(row.carrier_grace_hours);
  const [days, setDays] = useState(row.unpaid_after_days);
  const [outcome, setOutcome] = useState<UnpaidCancellationOutcome>(
    row.unpaid_outcome,
  );
  const [busy, setBusy] = useState(false);

  const digits = (value: string) => value.replace(/[^0-9]/g, "");

  return (
    <>
      <div className="grid grid-cols-2 gap-10">
        <Field
          name="exempt_within_meters"
          label="مسافة الإعفاء (متراً)"
          dir="ltr"
          inputMode="numeric"
          value={metres}
          disabled={disabled}
          onChange={(event) => setMetres(digits(event.target.value))}
        />
        <Field
          name="block_after_unpaid"
          label="عدد الرسوم قبل إيقاف الطلب"
          dir="ltr"
          inputMode="numeric"
          value={block}
          disabled={disabled}
          onChange={(event) => setBlock(digits(event.target.value))}
        />
        <DurationField
          name="carrier_grace_hours"
          label="مهلة الكبتن الحامل"
          wire="hour"
          value={grace}
          disabled={disabled}
          onChange={setGrace}
        />
        <DurationField
          name="unpaid_after_days"
          label="مدة الدَّين قبل الإجراء"
          wire="day"
          value={days}
          disabled={disabled}
          onChange={setDays}
        />
      </div>

      <div className="mt-10">
        <Select
          label="مآل الدَّين بعد المدة"
          value={outcome}
          disabled={disabled}
          onChange={(event) =>
            setOutcome(event.target.value as UnpaidCancellationOutcome)
          }
        >
          <option value="keep_pending">يبقى معلّقاً — لا إجراء</option>
          <option value="admin_decides">تشطبه الإدارة يدوياً</option>
          <option value="company_bears">تتحمّله الشركة ويصل الكبتن</option>
        </Select>
      </div>

      {/* **الصمتُ حالةٌ ثالثةٌ لا حالتان**: «لم يتحرك» واقعةٌ مقيسة، و«لا نعرف
          أين كان» جهلٌ — وخلطُهما يجعل مشرفاً يظن أنه يضبط رقماً واحداً */}
      <div className="mt-12">
        <Checkbox checked={silent} disabled={disabled} onChange={setSilent}>
          <span className="text-12.5 text-ink">
            أعفِ الراكب إن لم يكن للكبتن موقعٌ مبثوث
          </span>
        </Checkbox>
      </div>
      <p className="mt-6 text-11 leading-note text-muted">
        بلا موقعٍ مبثوثٍ <b className="text-ink">لا دليلَ على تحرّك</b>، والشكُّ
        لمن سيُخصم منه — ومن تحرّك فعلاً يعترض، فتُعفيه في «رسوم الإلغاء».
        وإطفاؤه يجعل البعدَ يُقاس من نقطة الالتقاء فيُحصَّل على كبتنٍ انقطع
        اتصالُه. <b className="text-ink">ومهلةُ الحامل مجمَّدةٌ لحظةَ قبضه</b>،
        فتقصيرُها هنا يحكم ما يأتي لا ما ينظر إليه كبتنٌ في شاشته الآن.
      </p>

      <Button
        className="mt-14"
        size="sm"
        disabled={disabled || metres === ""}
        loading={busy}
        onClick={() => {
          setBusy(true);
          updateCancellationSettings(row.country_code, {
            exempt_within_meters: Number(metres),
            exempt_when_location_unknown: silent,
            block_after_unpaid: Number(block),
            carrier_grace_hours: grace,
            unpaid_after_days: days,
            unpaid_outcome: outcome,
          })
            .then(() =>
              onSaved("حُفظت السياسة — تسري على ما يقع بعدها لا على رسمٍ قائم"),
            )
            .catch((caught) =>
              onError(caught),
            )
            .finally(() => setBusy(false));
        }}
      >
        حفظ
      </Button>
    </>
  );
}

/** سقوفُ طلب رمز التحقق — **سبعةُ أرقامٍ تحكم بابَ الدخول إلى المنصّة كلِّها**.
 *
 * وتُقرأ حيّةً لا مجمَّدة: توسيعُها يُطلق سراحَ من كان محجوزاً في الحال،
 * وتضييقُها يسري على الطلب التالي — كحدِّ إيقاف رسوم الإلغاء. **ولا يمسّ
 * التعديلُ حجزاً قائماً**: من قيل له «بعد ساعة» لا تُقصَّر تحته ولا تُطال.
 */
/** حدّا خريطة الراكب — **رقمان لا أكثر**، وكلاهما فوق الصفر بقيدٍ في القاعدة. */
function MapForm({
  row,
  disabled,
  onSaved,
  onError,
}: {
  row: MapSetting;
  disabled: boolean;
  onSaved: (message: string) => void;
  onError: (caught: unknown) => void;
}) {
  const [radius, setRadius] = useState(String(Number(row.nearby_radius_km)));
  const [count, setCount] = useState(String(row.nearby_max_count));
  const [busy, setBusy] = useState(false);
  const numeric = (value: string) => value.replace(/[^0-9.]/g, "");

  return (
    <>
      <div className="grid grid-cols-2 gap-10">
        <Field
          name="nearby_radius_km"
          label="مدى العرض (كم)"
          dir="ltr"
          inputMode="decimal"
          value={radius}
          disabled={disabled}
          onChange={(event) => setRadius(numeric(event.target.value))}
        />
        <Field
          name="nearby_max_count"
          label="أقصى عدد سيارات"
          dir="ltr"
          inputMode="numeric"
          value={count}
          disabled={disabled}
          onChange={(event) => setCount(numeric(event.target.value))}
        />
      </div>
      <Button
        className="mt-14"
        size="sm"
        disabled={disabled || radius === "" || count === ""}
        loading={busy}
        onClick={() => {
          setBusy(true);
          updateMapSettings(row.country_code, {
            nearby_radius_km: Number(radius),
            nearby_max_count: Number(count),
          })
            .then(() => onSaved("حُفظت حدودُ الخريطة — تظهر في أول تحديث"))
            .catch((caught) => onError(caught))
            .finally(() => setBusy(false));
        }}
      >
        حفظ
      </Button>
    </>
  );
}

function OtpForm({
  row,
  disabled,
  onSaved,
  onError,
}: {
  row: OtpSetting;
  disabled: boolean;
  onSaved: (message: string) => void;
  onError: (caught: unknown) => void;
}) {
  // **المددُ أعدادٌ لا نصوص**: `DurationField` يحمل العددَ ووحدتَه، **والنصُّ
  // كان يلزم لأن الحقلَ الخامَ يعطي نصّاً** (§39٫١٢٫٢).
  const [windowMinutes, setWindowMinutes] = useState(row.window_minutes);
  const [perWindow, setPerWindow] = useState(String(row.max_per_window));
  const [perDay, setPerDay] = useState(String(row.max_per_day));
  const [perSignup, setPerSignup] = useState(String(row.max_per_registration));
  const [lockout, setLockout] = useState(row.lockout_minutes);
  const [resendBase, setResendBase] = useState(row.resend_base_seconds);
  const [resendMax, setResendMax] = useState(row.resend_max_seconds);
  const [busy, setBusy] = useState(false);

  const digits = (value: string) => value.replace(/[^0-9]/g, "");

  return (
    <>
      <div className="grid grid-cols-2 gap-10">
        <DurationField
          name="window_minutes"
          label="طول النافذة"
          wire="minute"
          value={windowMinutes}
          disabled={disabled}
          onChange={setWindowMinutes}
        />
        <Field
          name="max_per_window"
          label="أقصى طلبات في النافذة"
          dir="ltr"
          inputMode="numeric"
          value={perWindow}
          disabled={disabled}
          onChange={(event) => setPerWindow(digits(event.target.value))}
        />
        <Field
          name="max_per_day"
          label="أقصى طلبات في اليوم"
          dir="ltr"
          inputMode="numeric"
          value={perDay}
          disabled={disabled}
          onChange={(event) => setPerDay(digits(event.target.value))}
        />
        <Field
          name="max_per_registration"
          label="أقصى طلبات لتسجيلٍ واحد"
          dir="ltr"
          inputMode="numeric"
          value={perSignup}
          disabled={disabled}
          onChange={(event) => setPerSignup(digits(event.target.value))}
        />
        <DurationField
          name="lockout_minutes"
          label="الانتظار بعد الاستنفاد"
          wire="minute"
          value={lockout}
          disabled={disabled}
          onChange={setLockout}
        />
        <DurationField
          name="resend_base_seconds"
          label="مهلة الإعادة الأولى"
          value={resendBase}
          disabled={disabled}
          onChange={setResendBase}
        />
        <DurationField
          name="resend_max_seconds"
          label="سقف مهلة الإعادة"
          value={resendMax}
          disabled={disabled}
          onChange={setResendMax}
        />
      </div>
      <p className="mt-6 text-11 leading-note text-muted">
        مهلةُ الإعادة <b className="text-ink">تتضاعف بالتكرار</b> من الأولى حتى
        سقفها — الضغطةُ المكرّرة تُعالَج بثوانٍ، والآلةُ بدقائق. والسقفُ عليها
        ليس تجميلاً: مهلةٌ تتضاعف بلا حدٍّ تبلغ ساعاتٍ فتصير منعاً دائماً لم
        يقرّره أحد. ويرى المستخدم عدّاداً بالثواني، لا زرّاً يُضغط بلا أثر.
      </p>
      <Button
        className="mt-14"
        size="sm"
        // `window_minutes` ge=1 و`resend_base_seconds` ge=5 — والصفرُ مرفوضٌ
        // في الطرفين (`schemas/settings.py`)
        disabled={disabled || windowMinutes === 0 || resendBase === 0}
        loading={busy}
        onClick={() => {
          setBusy(true);
          updateOtpSettings(row.country_code, {
            window_minutes: windowMinutes,
            max_per_window: Number(perWindow),
            max_per_day: Number(perDay),
            max_per_registration: Number(perSignup),
            lockout_minutes: lockout,
            resend_base_seconds: resendBase,
            resend_max_seconds: resendMax,
          })
            .then(() => onSaved("حُفظت السقوف — تسري على الطلب التالي في الحال"))
            .catch((caught) =>
              onError(caught),
            )
            .finally(() => setBusy(false));
        }}
      >
        حفظ
      </Button>
    </>
  );
}

function DispatchForm({
  row,
  country,
  disabled,
  onSaved,
  onError,
}: {
  row: DispatchSetting | null;
  country: CountryCode;
  disabled: boolean;
  onSaved: (message: string) => void;
  onError: (caught: unknown) => void;
}) {
  // **الغائبُ يُعرض بالافتراضيّ لا فارغاً**: سوقٌ بلا صفٍّ **يوزّع فعلاً**
  // بهذه القيم، فحقلٌ فارغٌ كان سيُقرأ «معطَّل» وهو يعمل.
  const [mode, setMode] = useState<DispatchMode>(row?.mode ?? "sequential");
  const [offer, setOffer] = useState(row?.offer_timeout_seconds ?? 7);
  const [attempts, setAttempts] = useState(String(row?.max_attempts ?? 5));
  const [total, setTotal] = useState(row?.total_timeout_seconds ?? 120);
  const [cooldown, setCooldown] = useState(row?.cooldown_seconds ?? 30);
  const [batch, setBatch] = useState(String(row?.broadcast_batch_size ?? 4));
  const [busy, setBusy] = useState(false);

  const digits = (value: string) => value.replace(/[^0-9]/g, "");

  return (
    <>
      <div className="grid grid-cols-2 gap-10">
        <Select
          name="mode"
          label="نمط العرض"
          value={mode}
          disabled={disabled}
          onChange={(event) => setMode(event.target.value as DispatchMode)}
        >
          <option value="sequential">تسلسليّ — واحد في كل مرة</option>
          <option value="broadcast">بثّ — دفعة معاً، وأول من يقبل</option>
        </Select>
        <DurationField
          name="offer_timeout_seconds"
          label="مهلة قبول العرض"
          value={offer}
          disabled={disabled}
          onChange={setOffer}
        />
        <DurationField
          name="cooldown_seconds"
          label="تبريد من صمت أو رفض"
          value={cooldown}
          disabled={disabled}
          onChange={setCooldown}
        />
        <Field
          name="broadcast_batch_size"
          label="كم كبتناً في دفعة البثّ"
          dir="ltr"
          inputMode="numeric"
          value={batch}
          disabled={disabled || mode !== "broadcast"}
          onChange={(event) => setBatch(digits(event.target.value))}
        />
        <Field
          name="max_attempts"
          label="عدد المحاولات"
          dir="ltr"
          inputMode="numeric"
          value={attempts}
          disabled={disabled}
          onChange={(event) => setAttempts(digits(event.target.value))}
        />
        <DurationField
          name="total_timeout_seconds"
          label="مهلة البحث كلّه"
          value={total}
          disabled={disabled}
          onChange={setTotal}
        />
      </div>
      <p className="mt-6 text-11 leading-note text-muted">
        التبريدُ ليس استبعاداً: من صمت أو رفض يعود مرشَّحاً في الطلب نفسه بعد
        انقضائه. واجعله أقصرَ من مهلة البحث كلّها بوضوح — تبريدٌ يساويها يعني
        أنه لن يعود أبداً، وهو الاستبعادُ الدائم بعينه.
      </p>
      <Button
        className="mt-14"
        size="sm"
        // `offer_timeout_seconds` ge=3 و`cooldown_seconds` ge=1 — والصفرُ
        // مرفوضٌ في الطرفين (`schemas/settings.py`)
        disabled={disabled || offer === 0 || cooldown === 0}
        loading={busy}
        onClick={() => {
          setBusy(true);
          updateDispatchSettings(country, {
            mode,
            offer_timeout_seconds: offer,
            max_attempts: Number(attempts),
            total_timeout_seconds: total,
            cooldown_seconds: cooldown,
            broadcast_batch_size: Number(batch),
          })
            .then(() =>
              onSaved(
                "حُفظت قواعد التوزيع — تسري على الرحلة التالية لا على بحثٍ جارٍ",
              ),
            )
            .catch((caught) => onError(caught))
            .finally(() => setBusy(false));
        }}
      >
        حفظ
      </Button>
    </>
  );
}
