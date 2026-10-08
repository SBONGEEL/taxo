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
import { DurationField, MoneyField } from "@/components/ui/Inputs";
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
  listServiceSettings,
  updateServiceSettings,
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
  ServiceSetting,
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
  eta_enabled: {
    title: "زمن الوصول",
    hint: "«تصل خلال 3 د» قبل الطلب، و«4 د حتى الراكب» على بطاقة الطلب عند الكبتن، و«في الطريق إليك · 5 د» في التتبّع. **وكلفتُه نداءاتٌ إلى Mapbox تُحصى لكلِّ يوم**: مسارٌ لكلِّ عرضٍ يُفتح، ويصير مسارَ الاقتراب إن قُبل فلا يُطلب ثانيةً، وأقربُ كبتنٍ لكلِّ فئةٍ مخزَّناً دقيقةً لكلِّ حيّ — **والوقتُ المتبقّي يُحسب في الهاتف** لا بسؤالٍ كلَّ دقيقة. ومطفأً لا نداءَ ولا رقمٌ في أيِّ شاشة.",
  },
  ride_code_enabled: {
    title: "رمز الرحلة",
    hint: "للرحلات النسائية وحدَها: تُعطى الراكبةُ أربعَ خاناتٍ عند القبول، **ولا تبدأ الكبتنةُ الرحلةَ قبل أن تُدخلها** — فلا تركب الراكبةُ إلا السيارةَ التي قبلت طلبها. **والرمزُ لا يصل الكبتنةَ في أيِّ شاشة**، والتخمينُ مسقوفٌ بخمس محاولاتٍ كلَّ عشر دقائق. وإشعالُه يغيّر بدءَ الرحلة؛ **وتطبيقُ كبتنٍ أقدمُ من هذه النسخة لا يعرض الخانات**، فيُشعَل بعد التحديث الإلزاميّ. ومطفأً لا رمزَ ولا شرط.",
  },
  ride_for_other_enabled: {
    title: "رحلة لشخص آخر",
    hint: "يطلب الراكبُ رحلةً يركبها غيرُه: يكتب اسمَه ورقمَه، ويختار من يدفع — هو بالمحفظة أو البطاقة، أو الراكبُ نقداً عند الوصول. **ورسمُ الإلغاء على الطالب** ولو كان الراكبُ يدفع نقداً. ويرى الكبتنُ اسمَ الراكب ورقمَه بعد القبول وحدَه، **ويُمحيان بعد ثلاثين يوماً** من انتهاء الرحلة. **ويرسل الطالبُ رابطَ تتبّعٍ بنفسه** يُظهر اسمَ الكبتن وسيارتَه ولوحتَها وموقعَه حتى تنتهي الرحلة. **ولا يُشعَل قبل نشر سطرَي الخصوصية** (اسمُ الراكب ورقمُه، ورابطُ التتبّع). ومطفأً يُرفض الطلبُ لغيره ورابطُه، والرحلاتُ القائمةُ تكمل.",
  },
  airport_enabled: {
    title: "المطار",
    hint: "رحلةٌ تبدأ أو تنتهي داخل منطقة مرفقٍ في «المرافق الحيوية» تحمل رسمَه للكبتن سطراً مستقلاً في السعر — **يصله كاملاً ولا تُقتطع منه العمولة**، ولا يمسّه خصم. **ولا يصلها إلا كبتنٌ أشعل «طلبات المطار» بنفسه**. ومرفقٌ مطفأٌ أو رسمُه صفرٌ لا يُطبَّق. ومطفأً لا رسمَ ولا تصفية، والرحلاتُ القائمةُ برسمها تكمل.",
  },
  guaranteed_booking_enabled: {
    title: "الحجز المضمون",
    hint: "يختار الراكبُ عند حجز موعدٍ قبل ساعتين فأكثر أن يكون مضموناً: يُحفظ رسمُ الضمان من محفظته لحظةَ الحجز، ويقبله مسبقاً كبتنٌ مشتركٌ من «عروضٌ تنتظرك» ثمّ يؤكّد قبل الموعد، فيعرف الراكبُ اسمَ كبتنه قبل موعده. والرسمُ للكبتن حين تتمّ الرحلةُ معه في وقتها — يصله كاملاً ولا تُقتطع منه العمولة — ويُردّ إلى الراكب إن لم يوجد كبتنٌ أو تأخّر أو أُلغي الحجز. واعتذارُ الكبتن بعد التأكيد يأخذ منه الرسمَ للراكب ويُنذره، وتكرارُه يحجبه عن الحجوز المضمونة مدّةً. والأرقامُ في «الخدمات الجديدة» أدناه، ورسمٌ صفرٌ يُخفي الخدمةَ ولو اشتعل المفتاح. ومطفأً لا يُطلب حجزٌ مضمونٌ جديد، والقائمُ يكمل برسمه.",
  },
  parcel_enabled: {
    title: "الطرد",
    hint: "يطلب الراكبُ توصيلَ غرضٍ بسيارةٍ اقتصاديّة: يقرأ شروطَ الطرد ويُقرّ بها قبل الطلب، ويكتب اسمَ المستلم ورقمَه وعنوانَ التسليم، ويختار من يدفع — هو، أو المستلمُ نقداً عند التسليم. ورسمُ الطرد فوق سعر الاقتصادي للكبتن — يصله كاملاً ولا تُقتطع منه العمولة، ولا يمسّه خصم. ويرى الكبتنُ المستلمَ بعد القبول وحدَه، ويُمحى بعد ثلاثين يوماً من انتهاء الرحلة. وللكبتن أن يرفض الطردَ عند الاستلام فتُلغى الرحلةُ بلا مالٍ على أحد. والرسمُ في «الخدمات الجديدة» أدناه، ورسمٌ صفرٌ يُخفي الخدمةَ ولو اشتعل المفتاح. ومطفأً يُرفض طلبُ الطرد، والقائمُ يكمل برسمه.",
  },
  hourly_enabled: {
    title: "بالساعة",
    hint: "يحجز الراكبُ سيارةً اقتصاديّةً بالساعة: يختار عددَ الساعات حتى سقفٍ تضبطه، ووجهتُه اختياريّةٌ يقولها للكبتن في الطريق. والمحجوزُ — الساعاتُ في سعرها — يُدفع عند البدء: من محفظته يُسوّى فوراً ورصيدٌ لا يكفيه يمنع البدء، أو نقداً يؤكّد الكبتنُ استلامَه. وما زاد على كيلومترات الساعات أو دقائقها يُحسب عند الإنهاء بتعرفة الاقتصادي العاديّة، وتُقتطع العمولةُ من أجرتها كأيِّ رحلة. وإلغاءُ الراكب بعد وصول الكبتن يكلّفه دقائقَ من سعر الساعة تذهب إلى الكبتن. والأرقامُ في «الخدمات الجديدة» أدناه، وسعرٌ صفرٌ يُخفي الخدمةَ ولو اشتعل المفتاح. ومطفأً يُرفض طلبُها، والقائمةُ تكمل بأسعارها.",
  },
  rider_subscription_enabled: {
    title: "المشوار الثابت",
    hint: "يشترك الراكبُ في مشوارٍ يوميٍّ لشهرٍ من يوم البدء: يختار نقطتين وأيامَ الأسبوع ووقتَ الذهاب ووقتَ عودةٍ إن شاء، ويدفع الشهرَ مقدّماً من محفظته بسعرٍ للرحلة مجمَّد — تقديرُ الطريق بسعر الاقتصادي ناقصاً الخصم، لا تمسّه ذروةٌ ولا مسافةٌ فعليّة. وتُولَّد رحلاتُه حجوزاً لليوم التالي، يأخذها كبتنُه المعتمد — من اعتمد المشوارَ من عروضه — إن كان متاحاً، وإلا تُعرض على الجميع. وكلُّ رحلةٍ تكتمل تُدفع للكبتن من المحفوظ وتُقتطع منها العمولةُ كأيِّ أجرة، وللكبتن المعتمد حافزٌ من TAXO لكلِّ رحلةٍ إن ضبطته. وللراكب أن يعلّق يوماً فيُرحَّل إلى ما بعد آخر يوم، وأن يستبدل كبتنَه، وأن يلغي فيعود ما لم يُستعمل رصيداً في محفظته لا نقداً — وكذلك ما لم يكتمل عند نهاية الشهر. والأرقامُ في «الخدمات الجديدة» أدناه، وخصمٌ صفرٌ يُخفي الخدمةَ ولو اشتعل المفتاح. ومطفأً لا يُشترى اشتراكٌ جديد، والقائمُ يكمل شهرَه.",
  },
  intercity_enabled: {
    title: "بين المدن",
    hint: "لا يُشعَل قبل أن يتحقّق المالكُ من القانون في السوق. رحلاتٌ بين المدن يعلنها الكبتنُ نفسُه على مسارٍ تضيفه في «مسارات بين المدن» — بمقاعدها وأقلِّ عددٍ ينطلق به — ولا يعلنها إلا كبتنٌ منحه مشرفٌ تصريحاً من ملفّه بعد فحص مركبته: 2015 فأحدث، وأربعةُ مقاعدَ على الأقل، وتأمينٌ سارٍ. ويحجز الراكبُ مقاعدَ تُدفع من محفظته يحفظها TAXO حتى تنتهي الرحلة، أو السيارةَ كاملةً نقداً للكبتن، بسعري المسار المجمَّدين على الرحلة لحظةَ إعلانها. وإلغاءُ الراكب قبل الانطلاق يعيد مالَه كاملاً، وللكبتن أن يلغي قبل المهلة بلا أثرٍ عليه ويُردّ للركّاب كاملاً، وعند المهلة تُلغى وحدَها رحلةٌ لم يبلغ محجوزُها حدَّها. وعند الإنهاء يصل الكبتنَ مالُ المقاعد وتُقتطع منه العمولةُ كأيِّ أجرة، وعمولةُ السيارة النقديّة دَينٌ عليه كرحلات النقد. والمهلةُ في «الخدمات الجديدة» أدناه. ومطفأً لا تُعلن رحلةٌ ولا يُحجز مقعدٌ جديد، والقائمُ يكمل.",
  },
  weekly_cashback_enabled: {
    title: "الاسترداد الأسبوعي",
    hint: "رحلةٌ كلَّ يومٍ لأسبوعٍ يبدأ من أوّل رحلةٍ للراكب — الجمعةُ لا تُطلب ولا تقطع، وفواتُ يومٍ يُعيد العدّ — ومبلغٌ ثابتٌ ينزل في محفظته في اليوم الأخير، من TAXO لا من الكبتن. وتُحسب رحلاتُ الطالب أيّاً كانت قناةُ دفعها، ويرى الراكبُ في الرئيسية نارَه وأيامَه الباقيةَ والمبلغَ المنتظَر، وتذكّره ثلاثةُ إشعاراتٍ عن الأيام لا عن المال: صباحاً، ومساءً، وقبل أن يفوته اليوم. والمبلغُ وأيامُ الأسبوع في «الخدمات الجديدة» أدناه، ومبلغٌ صفرٌ يُخفي الخدمةَ ولو اشتعل المفتاح. ومطفأً لا يُحسب يومٌ ولا تُرسم نار.",
  },
  work_hours_enabled: {
    title: "ساعات العمل",
    hint: "نحسب كلَّ يومٍ كم دقيقةً كان الكبتنُ متصلاً يستقبل الطلبات — ومعها وقتُ رحلاته — فيرى ساعاتِ يومه في الرئيسية وساعاتِ نافذته في الأرباح، وتراها الإدارةُ في ملفّه. لا نحفظ موقعَه وهو ينتظر، الرقمُ وحدَه؛ ويُحفظ يومياً ثلاثةَ عشرَ شهراً ثمّ يُجمع شهرياً. والمفتاحُ يحكم الجمعَ نفسَه: مطفأً لا تُحسب دقيقة، فلا يُشعَل قبل نشر سطره في سياسة الخصوصية.",
  },
  unconfirmed_payments_enabled: {
    title: "المدفوعات غير المؤكدة",
    hint: "الطريقةُ التي يختارها الراكبُ في ورقة الطلب تُرسل معه ويراها الكبتنُ على بطاقة العرض، ويولد صفُّ الدفع مع نهاية الرحلة. ويُعرض للطرفين عند كلِّ فتحٍ ما ينتظر تأكيدَهما: الراكبُ يُقرّ بتسليم الكاش أو يُدخل مرجعَ الحوالة أو يبدّل الطريقة، والكبتنُ يؤكّد الاستلام أو يعترض — وتصلهما تذكيراتٌ بمواعيدها. ومن تأخّر فوق الحدّ يُمنع: الراكبُ من طلبٍ جديد، والكبتنُ من العروض الجديدة، ويُرفع المنعُ فورَ الحسم؛ ومن حُكم عليه مرّتين بأنه لم يدفع تُطفأ له قناةُ الكاش مدّةَ النافذة. وما لم يُحسم يصل «المدفوعات غير المؤكدة» لتحسمه بسببٍ مكتوب. والأرقامُ في «سياسات الدفع» أدناه. ولا يُكتب في الدفتر شيءٌ إلا بتأكيدٍ أو حكم. ومطفأً يبقى كلُّ شيءٍ كما كان، وما تراكم قبله يُحسم من الطابور.",
  },
  cash_auto_confirm_enabled: {
    title: "الإتمام الآلي للكاش",
    hint: "يُشعَل بعد أن يُرى طابورُ «المدفوعات غير المؤكدة» أسبوعاً. كاشٌ أقرّ الراكبُ بتسليمه وصمت عنه الكبتنُ رغم أربعة تذكيراتٍ آخرُها التحذير، تحت سقف المبلغ أدناه، ولا حكمَ «لم يدفع» على الراكب في تسعين يوماً ولا نزاعَ على الرحلة — يُعدّ مستلَماً ويُكتب ما يكتبه تأكيدُ الكبتن حرفاً، ومعاييرُه مجمَّدةٌ على الدفعة. وللكبتن نافذةُ اعتراضٍ لا يُعكس فيها شيءٌ قبل حكمك. ولا يمسّ كليك أبداً، ولا يعمل إلا مع «المدفوعات غير المؤكدة» مشتعلاً.",
  },
  trip_chat_enabled: {
    title: "المحادثة داخل الرحلة",
    hint: "يراسل الراكبُ والكبتنُ أحدُهما الآخرَ من قبول الكبتن حتى انتهاء الرحلة، نصّاً حتى 300 حرف بلا صورٍ ولا ملفّات. وترفض الخلفيةُ قبل الحفظ كلَّ رسالةٍ فيها رقمُ هاتفٍ بأيِّ صيغةٍ أو رابط، ولا يُرسَل نصُّ الرسالة في الإشعار. وبعد انتهاء الرحلة تبقى مقروءةً للطرفين ولا يُكتب فيها، وتُحذف بعد مدّة الاحتفاظ. ولا يُشعَل قبل نشر قسم «محادثةُ الرحلة ومكالمتُها» في سياستَي الخصوصية للراكب وللكبتن — يرفض الخادمُ الإشعالَ قبله.",
  },
  ride_calls_enabled: {
    title: "المكالمة داخل التطبيق",
    hint: "يتّصل الراكبُ والكبتنُ صوتاً داخل التطبيق من قبول الكبتن حتى انتهاء الرحلة، ولا يرى أحدُهما رقمَ الآخر. ويُحفظ وقتُ المكالمة ومدّتُها ومن اتصل بمن — ولا يُسجَّل الصوتُ ما دام التسجيلُ مطفأً. ولا يُشعَل قبل نشر قسم «محادثةُ الرحلة ومكالمتُها» في السياستين.",
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
  "eta_enabled",
  "ride_code_enabled",
  "ride_for_other_enabled",
  "airport_enabled",
  "guaranteed_booking_enabled",
  "parcel_enabled",
  "hourly_enabled",
  "rider_subscription_enabled",
  "intercity_enabled",
  "weekly_cashback_enabled",
  "work_hours_enabled",
  "driver_map_nearby_enabled",
  // **المدفوعاتُ غيرُ المؤكَّدة** (§٦٤-ز) — المسارُ ثمّ إتمامُه الآليّ **بترتيب إشعالهما**: الثاني بعد أسبوعٍ من الأول
  "unconfirmed_payments_enabled",
  "cash_auto_confirm_enabled",
  // **محادثةُ الرحلة ومكالمتُها** (§٦٦) — والخادمُ يرفض إشعالَهما قبل نشر سطرهما في السياستين
  "trip_chat_enabled",
  "ride_calls_enabled",
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
  const [services, setServices] = useState<ServiceSetting[]>([]);
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
    const [f, c, w, p, r, rr, sh, adv, dsp, cxl, svc, otpRows, mapRows, spent] =
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
      listServiceSettings(),
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
    setServices(svc);
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
  const serviceRow = services.find((row) => row.country_code === country);
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
              <>
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
                {/* **المدفوعاتُ غيرُ المؤكَّدة** (`design/PAYMENTS-UNCONFIRMED.md` §٩، SPEC §٦٤-ز) — عتباتُها العشرُ من الصفِّ نفسِه
                    (`payment_settings`) **بنموذجٍ مستقلٍّ بحفظه**: حفظُها لا يمسّ مهلةَ كليك ولا البقشيش. **وتُرسم ولو كان مفتاحُها
                    مطفأً** — الأرقامُ تُضبط قبل الإشعال لا بعده */}
                <UnconfirmedForm
                  key={`unconfirmed-${paymentRow.country_code}`}
                  row={paymentRow}
                  disabled={!isAdmin}
                  onSaved={(message) => {
                    setDone(message);
                    void load();
                  }}
                  onError={(caught) => form.capture(caught, "تعذّر الحفظ")}
                />
              </>
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

          {/* **الخدماتُ الجديدة** (§٦٣، `service_settings`) — بطاقةٌ لجدولها كبقية البطاقات، **والحجزُ المضمونُ أوّلُها**.
              **وتُرسم ولو كان مفتاحُه مطفأً**: الأرقامُ تُضبط قبل الإشعال لا بعده — ورسمٌ صفرٌ يُخفي الخدمةَ ولو اشتعلت */}
          <section className="rounded-16 border border-line bg-surface p-18">
            <h2 className="mb-4 text-14 font-bold text-ink">الخدمات الجديدة</h2>
            <h3 className="mb-2 mt-12 text-12.5 font-bold text-ink">
              الحجز المضمون
            </h3>
            <p className="mb-12 text-11 leading-snug text-muted">
              كبتنٌ يُحجز للراكب مسبقاً ويؤكّد قبل موعده.{" "}
              <b className="text-ink">رسمُ الضمان يُحفظ من محفظة الراكب لحظةَ الحجز</b>{" "}
              ويصل الكبتنَ كاملاً حين تتمّ الرحلةُ معه في وقتها، أو يُردّ.{" "}
              <b className="text-ink">وصفرُه يُخفي الخدمة</b> ولو اشتعل مفتاحُها.{" "}
              <b className="text-ink">ولا أثرَ رجعياً</b>: الرسمُ مجمَّدٌ على الحجز
              لحظةَ طلبه، فتعديلُه هنا يحكم ما يأتي لا ما ينتظر الآن.
            </p>
            {serviceRow ? (
              <GuaranteeForm
                key={serviceRow.country_code}
                row={serviceRow}
                disabled={!isAdmin}
                onSaved={(message) => {
                  setDone(message);
                  void load();
                }}
                onError={(caught) => form.capture(caught, "تعذّر الحفظ")}
              />
            ) : (
              <p className="text-12.5 text-muted">
                لا إعدادَ خدماتٍ لهذه الدولة.
              </p>
            )}

            {/* **الطرد** (§٦٣-ج/٤) — رقمٌ واحدٌ من الصفِّ نفسِه، **ونموذجٌ مستقلٌّ بحفظه**: حفظُ الرسم لا يمسّ أرقامَ الضمان */}
            {serviceRow ? (
              <div className="mt-18 border-t border-line pt-14">
                <h3 className="mb-2 text-12.5 font-bold text-ink">الطرد</h3>
                <p className="mb-12 text-11 leading-snug text-muted">
                  رحلةٌ اقتصاديّةٌ تحمل غرضاً، برسمٍ للكبتن فوق سعرها.{" "}
                  <b className="text-ink">وصفرُه يُخفي الخدمة</b> ولو اشتعل مفتاحُها.{" "}
                  <b className="text-ink">ولا أثرَ رجعياً</b>: الرسمُ مجمَّدٌ على الرحلة
                  لحظةَ طلبها.
                </p>
                <ParcelForm
                  key={serviceRow.country_code}
                  row={serviceRow}
                  disabled={!isAdmin}
                  onSaved={(message) => {
                    setDone(message);
                    void load();
                  }}
                  onError={(caught) => form.capture(caught, "تعذّر الحفظ")}
                />
              </div>
            ) : null}

            {/* **بالساعة** (§٦٣-ج/٥) — أربعةُ أرقامٍ من الصفِّ نفسِه **بنموذجٍ مستقلٍّ بحفظه** كالطرد: حفظُها لا يمسّ أرقامَ غيرها */}
            {serviceRow ? (
              <div className="mt-18 border-t border-line pt-14">
                <h3 className="mb-2 text-12.5 font-bold text-ink">بالساعة</h3>
                <p className="mb-12 text-11 leading-snug text-muted">
                  سيارةٌ اقتصاديّةٌ تُحجز بالساعات، يُدفع محجوزُها عند البدء وما زاد في
                  النهاية بالتعرفة العاديّة.{" "}
                  <b className="text-ink">وسعرٌ صفرٌ يُخفي الخدمة</b> ولو اشتعل مفتاحُها.{" "}
                  <b className="text-ink">ولا أثرَ رجعياً</b>: السعرُ والكيلومتراتُ ودقائقُ
                  الإلغاء مجمَّدةٌ على الرحلة لحظةَ طلبها.
                </p>
                <HourlyForm
                  key={serviceRow.country_code}
                  row={serviceRow}
                  disabled={!isAdmin}
                  onSaved={(message) => {
                    setDone(message);
                    void load();
                  }}
                  onError={(caught) => form.capture(caught, "تعذّر الحفظ")}
                />
              </div>
            ) : null}

            {/* **المشوارُ الثابت** (§٦٣-ج/٦) — ثلاثةُ أرقامٍ من الصفِّ نفسِه **بنموذجٍ مستقلٍّ بحفظه** كأخويه */}
            {serviceRow ? (
              <div className="mt-18 border-t border-line pt-14">
                <h3 className="mb-2 text-12.5 font-bold text-ink">المشوار الثابت</h3>
                <p className="mb-12 text-11 leading-snug text-muted">
                  اشتراكٌ شهريٌّ لمشوارٍ يوميّ، يدفعه الراكبُ مقدّماً من محفظته بسعرٍ للرحلة مجمَّد.{" "}
                  <b className="text-ink">وخصمٌ صفرٌ يُخفي الخدمة</b> ولو اشتعل مفتاحُها.{" "}
                  <b className="text-ink">ولا أثرَ رجعياً</b>: الخصمُ مجمَّدٌ في سعر الاشتراك لحظةَ
                  شرائه، والحافزُ يُقرأ عند اكتمال كلِّ رحلة.
                </p>
                <CommuteForm
                  key={serviceRow.country_code}
                  row={serviceRow}
                  disabled={!isAdmin}
                  onSaved={(message) => {
                    setDone(message);
                    void load();
                  }}
                  onError={(caught) => form.capture(caught, "تعذّر الحفظ")}
                />
              </div>
            ) : null}

            {/* **بين المدن** (§٦٣-ج/٧) — رقمٌ واحدٌ من الصفِّ نفسِه **بنموذجٍ مستقلٍّ بحفظه** كإخوته؛ والمساراتُ وأسعارُها في صفحتها */}
            {serviceRow ? (
              <div className="mt-18 border-t border-line pt-14">
                <h3 className="mb-2 text-12.5 font-bold text-ink">بين المدن</h3>
                <p className="mb-12 text-11 leading-snug text-muted">
                  رحلاتٌ يعلنها الكباتنُ بتصريحٍ على مساراتٍ وأسعارٍ تضيفها في «مسارات بين المدن».{" "}
                  <b className="text-ink">والمهلةُ تُقرأ حيّةً لا مجمَّدة</b>: تعديلُها يحكم الرحلاتِ المعلَنةَ القائمةَ
                  كذلك — إلغاءَ الكبتن قبلها، والإلغاءَ الآليَّ عندها.
                </p>
                <IntercityForm
                  key={serviceRow.country_code}
                  row={serviceRow}
                  disabled={!isAdmin}
                  onSaved={(message) => {
                    setDone(message);
                    void load();
                  }}
                  onError={(caught) => form.capture(caught, "تعذّر الحفظ")}
                />
              </div>
            ) : null}

            {/* **الاسترداد الأسبوعي** (§٦٣-ج/٨) — رقمان من الصفِّ نفسِه **بنموذجٍ مستقلٍّ بحفظه** كإخوته */}
            {serviceRow ? (
              <div className="mt-18 border-t border-line pt-14">
                <h3 className="mb-2 text-12.5 font-bold text-ink">الاسترداد الأسبوعي</h3>
                <p className="mb-12 text-11 leading-snug text-muted">
                  رحلةٌ كلَّ يومٍ لأسبوعٍ بلا جمعته، ومبلغٌ ثابتٌ للراكب في يومه الأخير{" "}
                  <b className="text-ink">من TAXO لا من الكبتن</b>.{" "}
                  <b className="text-ink">ومبلغٌ صفرٌ يُخفي الخدمة</b> ولو اشتعل مفتاحُها.{" "}
                  <b className="text-ink">ولا أثرَ رجعياً</b>: المبلغُ والأيامُ مجمَّدان على السلسلة لحظةَ
                  بدئها، فتعديلُهما يحكم ما يبدأ بعده.
                </p>
                <CashbackForm
                  key={serviceRow.country_code}
                  row={serviceRow}
                  disabled={!isAdmin}
                  onSaved={(message) => {
                    setDone(message);
                    void load();
                  }}
                  onError={(caught) => form.capture(caught, "تعذّر الحفظ")}
                />
              </div>
            ) : null}
          </section>

          {/* **A35 — المحادثة والمكالمة** (§٦٦) — مدّتا الحفظ والتسجيلُ لسوقٍ واحد، من صفِّ الخدمات نفسِه (`service_settings`).
              **والمفتاحان في «مفاتيح الميزات»** لا هنا: `check:flags` يُلزم كلَّ مفتاحٍ بزرٍّ في قائمتها، **وزرّان لمفتاحٍ واحدٍ
              بابان يفترقان** — فيُشار إليهما بالاسم */}
          <section className="rounded-16 border border-line bg-surface p-18">
            <h2 className="mb-4 text-14 font-bold text-ink">المحادثة والمكالمة</h2>
            <p className="mb-12 text-11 leading-snug text-muted">
              مفتاحا «المحادثة داخل الرحلة» و«المكالمة داخل التطبيق» في «مفاتيح الميزات» —{" "}
              <b className="text-ink">ويرفض الخادمُ إشعالَهما قبل نشر قسمهما في سياستَي الخصوصية</b> للراكب وللكبتن.
              وهنا كم يبقى ما يُحفظ، وتسجيلُ المكالمات.
            </p>
            {serviceRow ? (
              <ChatCallForm
                key={serviceRow.country_code}
                row={serviceRow}
                disabled={!isAdmin}
                onSaved={(message) => {
                  setDone(message);
                  void load();
                }}
                onError={(caught) => form.capture(caught, "تعذّر الحفظ")}
              />
            ) : (
              <p className="text-12.5 text-muted">لا إعدادَ خدماتٍ لهذه الدولة.</p>
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
            .then(() =>
              onSaved(
                // **سندُها ثابتٌ مكتوب**: `rides.commission_percent_at_ride`
                // تُجمَّد عند إنشاء الرحلة ولا تُحسب بأثرٍ رجعيّ
                "حُفظت العمولة — تسري على الرحلة التالية، ولا تمسّ رحلةً"
                  + " قائمةً جُمّدت نسبتُها عند إنشائها",
              ),
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

/** **ترتيبُ التذكيرات الأربعة** — نصوصُها في التصميم (§٣) لكلِّ موعد: «١٠ د» سؤالٌ، و«٢ س» إعادتُه، و«١٢ س» إنذارُ الحدّ، و«٢٣ س»
 *  التحذيرُ الأخير («بعد ساعةٍ يُعدّ المبلغُ مستلَماً» حين يصدق). */
const REMINDER_LABEL = ["التذكير الأول", "التذكير الثاني", "التذكير الثالث", "التحذير الأخير"];

/** **عتباتُ المدفوعات غير المؤكَّدة** — عشرةُ أعمدةٍ في `payment_settings` بقيم التصميم الابتدائية (`design/PAYMENTS-UNCONFIRMED.md` §٩،
 *  SPEC §٦٤-ز).
 *
 * **المدّةُ عددٌ ووحدة** (`DurationField`) بوحدة عمودها على السلك — والمواعيدُ الأربعةُ بالدقائق بعد نهاية الرحلة (للكبتن على كاشٍ
 * أقرّ به الراكبُ: من الإقرار). **ولا أثرَ رجعيّ** على ما جُمّد على صفّ (نافذةُ الاعتراض ومعاييرُ الإتمام الآليّ)، **وما يُشتقّ حيّاً
 * يسري من لحظته** (الحجبُ والمواعيد) — والخلفيةُ تحرس الحدود وتصاعدَ المواعيد وتردّ برسالتها تحت الحقل.
 */
function UnconfirmedForm({
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
  const [reminders, setReminders] = useState<number[]>(row.payment_reminder_minutes);
  const [autoHours, setAutoHours] = useState(row.cash_auto_confirm_hours);
  const [autoMax, setAutoMax] = useState(row.cash_auto_confirm_max_amount);
  const [referenceMinutes, setReferenceMinutes] = useState(row.cliq_reference_minutes);
  const [blockCount, setBlockCount] = useState(String(row.driver_unconfirmed_block_count));
  const [blockHours, setBlockHours] = useState(row.driver_unconfirmed_block_hours);
  const [riderMinutes, setRiderMinutes] = useState(row.rider_unconfirmed_block_minutes);
  const [rulings, setRulings] = useState(String(row.rider_unpaid_rulings_cash_off));
  const [rulingsDays, setRulingsDays] = useState(row.rider_unpaid_rulings_window_days);
  const [objectionHours, setObjectionHours] = useState(row.dispute_window_hours);
  const [busy, setBusy] = useState(false);
  const currency = currencyOf(row.country_code);
  // **متصاعدةٌ كلٌّ بعد سابقه** — والخلفيةُ تحرسه أيضاً (`_reminders_ascend`)؛ هنا يُعطَّل الحفظُ ويُقال قبل الارتداد
  const ascending = reminders.length === 4 && reminders.slice(1).every((minutes, at) => minutes > reminders[at]);

  function setReminder(at: number, minutes: number) {
    setReminders((current) => current.map((value, index) => (index === at ? minutes : value)));
  }

  return (
    <div className="mt-18 border-t border-line pt-14">
      <h3 className="mb-2 text-12.5 font-bold text-ink">المدفوعات غير المؤكدة</h3>
      <p className="mb-12 text-11 leading-snug text-muted">
        تذكيراتٌ ثمّ حدٌّ يمنع العملَ الجديد ويُرفع فورَ الحسم.{" "}
        <b className="text-ink">والمواعيدُ بعد نهاية الرحلة</b> — وللكبتن على كاشٍ أقرّ به الراكبُ: بعد الإقرار.{" "}
        <b className="text-ink">ولا أثرَ رجعياً</b> على ما جُمّد على دفعة: نافذةُ الاعتراض ومعاييرُ الإتمام الآليّ.
      </p>

      <h4 className="mb-6 text-12 font-bold text-ink">مواعيد التذكير</h4>
      <div className="grid grid-cols-2 gap-10">
        {reminders.map((minutes, at) => (
          <DurationField
            key={REMINDER_LABEL[at] ?? at}
            name={`payment_reminder_minutes_${at}`}
            label={REMINDER_LABEL[at]}
            wire="minute"
            value={minutes}
            disabled={disabled}
            onChange={(next) => setReminder(at, next)}
          />
        ))}
      </div>
      <p className={ascending ? "mt-6 text-11 text-muted" : "mt-6 text-11 text-warn"}>
        {ascending
          ? "أربعةُ مواعيدَ متصاعدة — لكلٍّ نصُّه، والرابعُ التحذيرُ الأخيرُ قبل الحدّ."
          : "المواعيدُ متصاعدةٌ — كلٌّ بعد سابقه."}
      </p>

      <h4 className="mb-6 mt-14 text-12 font-bold text-ink">الحدّان</h4>
      <div className="grid grid-cols-2 gap-10">
        <Field
          name="driver_unconfirmed_block_count"
          label="يُحجب الكبتنُ عند (معلَّقات)"
          dir="ltr"
          inputMode="numeric"
          value={blockCount}
          disabled={disabled}
          onChange={(event) => setBlockCount(event.target.value.replace(/[^0-9]/g, ""))}
        />
        <DurationField
          name="driver_unconfirmed_block_hours"
          label="أو حين يبلغ عمرُ أقدمها"
          wire="hour"
          value={blockHours}
          disabled={disabled}
          onChange={setBlockHours}
        />
        <DurationField
          name="rider_unconfirmed_block_minutes"
          label="يُمنع الراكبُ من الطلب بعد"
          wire="minute"
          value={riderMinutes}
          disabled={disabled}
          onChange={setRiderMinutes}
        />
        <DurationField
          name="cliq_reference_minutes"
          label="مهلةُ مرجع كليك قبل التذكير"
          wire="minute"
          value={referenceMinutes}
          disabled={disabled}
          onChange={setReferenceMinutes}
        />
      </div>

      <h4 className="mb-6 mt-14 text-12 font-bold text-ink">إطفاءُ الكاش لراكبٍ لا يدفع</h4>
      <div className="grid grid-cols-2 gap-10">
        <Field
          name="rider_unpaid_rulings_cash_off"
          label="عند أحكام «لم يدفع»"
          dir="ltr"
          inputMode="numeric"
          value={rulings}
          disabled={disabled}
          onChange={(event) => setRulings(event.target.value.replace(/[^0-9]/g, ""))}
        />
        <DurationField
          name="rider_unpaid_rulings_window_days"
          label="في نافذة"
          wire="day"
          value={rulingsDays}
          disabled={disabled}
          onChange={setRulingsDays}
        />
      </div>

      <h4 className="mb-6 mt-14 text-12 font-bold text-ink">الإتمامُ الآليُّ للكاش والاعتراض</h4>
      <div className="grid grid-cols-2 gap-10">
        <DurationField
          name="cash_auto_confirm_hours"
          label="يُعدّ مستلَماً بعد الإقرار بـ"
          wire="hour"
          value={autoHours}
          disabled={disabled}
          onChange={setAutoHours}
        />
        <MoneyField
          name="cash_auto_confirm_max_amount"
          label="سقفُ الإتمام الآليّ"
          currency={currency}
          value={autoMax}
          disabled={disabled}
          onChange={setAutoMax}
        />
        <DurationField
          name="dispute_window_hours"
          label="نافذةُ اعتراض الكبتن"
          wire="hour"
          value={objectionHours}
          disabled={disabled}
          onChange={setObjectionHours}
        />
      </div>
      <p className="mt-6 text-11 leading-snug text-muted">
        فوق السقف لا يُتمّ آلياً أبداً — يذهب إلى «المدفوعات غير المؤكدة». الحالي:{" "}
        <b className="text-ink" dir="ltr">
          {money(row.cash_auto_confirm_max_amount, currency)}
        </b>
        . ولا يعمل الإتمامُ إلا بمفتاحه («الإتمام الآلي للكاش»).
      </p>

      <Button
        className="mt-14"
        size="sm"
        disabled={disabled || !ascending || blockCount === "" || rulings === "" || autoMax === ""}
        loading={busy}
        onClick={() => {
          setBusy(true);
          updatePaymentSettings(row.country_code, {
            payment_reminder_minutes: reminders,
            cash_auto_confirm_hours: autoHours,
            cash_auto_confirm_max_amount: autoMax,
            cliq_reference_minutes: referenceMinutes,
            driver_unconfirmed_block_count: Number(blockCount),
            driver_unconfirmed_block_hours: blockHours,
            rider_unconfirmed_block_minutes: riderMinutes,
            rider_unpaid_rulings_cash_off: Number(rulings),
            rider_unpaid_rulings_window_days: rulingsDays,
            dispute_window_hours: objectionHours,
          })
            .then(() => onSaved("حُفظت عتباتُ المدفوعات غير المؤكدة — يسري الحجبُ والمواعيدُ من الآن"))
            .catch((caught) => onError(caught))
            .finally(() => setBusy(false));
        }}
      >
        حفظ العتبات
      </Button>
    </div>
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

/** **الحجزُ المضمون** (§٦٣-ج/٣) — سبعةُ أرقامٍ لسوقٍ واحد: الرسمُ مالاً، والستّةُ مُدَداً وعدّاً.
 *
 * **ويُرسل ما تغيّر وحدَه** (`PATCH` جزئيّ): حقلٌ لم يلمسه المشرفُ لا يُكتب فوق ما كتبه غيرُه بين القراءة والحفظ، **وسجلُّ
 * التدقيق يقول ما عُدِّل فعلاً** لا الصفَّ كلَّه. **والحدودُ في الخلفية** (`ServiceSettingUpdate`) — ورفضُها يُقال تحت حقله.
 *
 * **و`key={country}` عليه كبقية النماذج** — بغيره تبقى أرقامُ السوق السابق في الحقول بعد تبديل الرأس.
 */
function GuaranteeForm({
  row,
  disabled,
  onSaved,
  onError,
}: {
  row: ServiceSetting;
  disabled: boolean;
  onSaved: (message: string) => void;
  onError: (caught: unknown) => void;
}) {
  const [fee, setFee] = useState(row.guarantee_fee);
  const [late, setLate] = useState(row.guarantee_late_minutes);
  const [confirmAt, setConfirmAt] = useState(row.guarantee_confirm_minutes);
  const [answerWindow, setAnswerWindow] = useState(row.guarantee_confirm_window_minutes);
  const [offerHours, setOfferHours] = useState(row.guarantee_offer_hours);
  const [threshold, setThreshold] = useState(String(row.guarantee_ban_threshold));
  const [banDays, setBanDays] = useState(row.guarantee_ban_days);
  const [busy, setBusy] = useState(false);

  // **الفرقُ يُحسب بالمقارنة لا بعلَمٍ يُرفع عند الكتابة**: من كتب ثمّ أعاد القيمةَ كما كانت لم يغيّر شيئاً
  const changes: Partial<Omit<ServiceSetting, "country_code">> = {};
  if (fee.trim() !== row.guarantee_fee) changes.guarantee_fee = fee.trim();
  if (late !== row.guarantee_late_minutes) changes.guarantee_late_minutes = late;
  if (confirmAt !== row.guarantee_confirm_minutes) changes.guarantee_confirm_minutes = confirmAt;
  if (answerWindow !== row.guarantee_confirm_window_minutes)
    changes.guarantee_confirm_window_minutes = answerWindow;
  if (offerHours !== row.guarantee_offer_hours) changes.guarantee_offer_hours = offerHours;
  if (Number(threshold) !== row.guarantee_ban_threshold)
    changes.guarantee_ban_threshold = Number(threshold);
  if (banDays !== row.guarantee_ban_days) changes.guarantee_ban_days = banDays;
  const dirty = Object.keys(changes).length > 0;

  return (
    <>
      <div className="grid grid-cols-2 gap-10">
        <MoneyField
          name="guarantee_fee"
          label="رسم الضمان"
          value={fee}
          onChange={(next) => setFee(next.replace(/[^0-9.,]/g, ""))}
          currency={currencyOf(row.country_code)}
          disabled={disabled}
          hint="من محفظة الراكب لحظةَ الحجز — وصفرٌ يُخفي الخدمة"
        />
        <DurationField
          name="guarantee_late_minutes"
          label="مهلة تأخّر الكبتن"
          wire="minute"
          value={late}
          disabled={disabled}
          onChange={setLate}
          hint="بعدها يُردّ الرسمُ ويُلغي الراكبُ مجّاناً"
        />
        <DurationField
          name="guarantee_confirm_minutes"
          label="السؤال قبل الموعد"
          wire="minute"
          value={confirmAt}
          disabled={disabled}
          onChange={setConfirmAt}
          hint="«هل أنت في الطريق؟» — ومنه يُفتح التأكيد"
        />
        <DurationField
          name="guarantee_confirm_window_minutes"
          label="مهلة الجواب"
          wire="minute"
          value={answerWindow}
          disabled={disabled}
          onChange={setAnswerWindow}
          hint="بلا ردٍّ فيها يُسحب منه بلا عقوبة"
        />
        <DurationField
          name="guarantee_offer_hours"
          label="ظهوره في «عروضٌ تنتظرك»"
          wire="hour"
          value={offerHours}
          disabled={disabled}
          onChange={setOfferHours}
          hint="قبل الموعد بهذه المدّة"
        />
        <Field
          name="guarantee_ban_threshold"
          label="اعتذاراتٌ بعد التأكيد تحجبه"
          dir="ltr"
          inputMode="numeric"
          value={threshold}
          disabled={disabled}
          onChange={(event) => setThreshold(event.target.value.replace(/[^0-9]/g, ""))}
        />
        <DurationField
          name="guarantee_ban_days"
          label="مدّة الحجب ونافذةُ العدّ"
          wire="day"
          value={banDays}
          disabled={disabled}
          onChange={setBanDays}
          hint="تُعدّ الاعتذاراتُ فيها، ويُحجب مثلَها"
        />
      </div>
      <p className="mt-6 text-11 leading-note text-muted">
        اعتذارُ الكبتن بعد التأكيد يأخذ منه مبلغاً يساوي الرسمَ للراكب بقدر رصيده،
        ويُسجَّل عليه إنذار — وبلوغُ العدد في المدّة يحجبه عن الحجوز المضمونة.
        واعتذارُه قبل التأكيد بلا أثر.
      </p>
      <Button
        className="mt-14"
        size="sm"
        disabled={disabled || !dirty || fee.trim() === "" || threshold === ""}
        loading={busy}
        onClick={() => {
          setBusy(true);
          updateServiceSettings(row.country_code, changes)
            .then(() =>
              onSaved("حُفظ الحجز المضمون — يسري على ما يُحجز بعده لا على حجزٍ قائم"),
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

/** **رسمُ الطرد** (§٦٣-ج/٤) — رقمٌ واحدٌ لسوقٍ واحد، **ويُرسل وحدَه** (`PATCH` جزئيّ كأخيه): حفظُه لا يكتب فوق أرقام الضمان ولو
 *  غيّرها مشرفٌ آخرُ بين القراءة والحفظ. **والحدُّ في الخلفية** (`ServiceSettingUpdate.parcel_fee` ≥ ٠ بثلاث خانات) — ورفضُه يُقال
 *  تحت حقله. و`key={country}` عليه كبقية النماذج. */
function ParcelForm({
  row,
  disabled,
  onSaved,
  onError,
}: {
  row: ServiceSetting;
  disabled: boolean;
  onSaved: (message: string) => void;
  onError: (caught: unknown) => void;
}) {
  const [fee, setFee] = useState(row.parcel_fee);
  const [busy, setBusy] = useState(false);
  // **الفرقُ بالمقارنة** — من كتب ثمّ أعاد الرقمَ كما كان لم يغيّر شيئاً
  const dirty = fee.trim() !== row.parcel_fee;

  return (
    <>
      <div className="grid grid-cols-2 gap-10">
        <MoneyField
          name="parcel_fee"
          label="رسم الطرد"
          value={fee}
          onChange={(next) => setFee(next.replace(/[^0-9.,]/g, ""))}
          currency={currencyOf(row.country_code)}
          disabled={disabled}
          hint="فوق سعر الاقتصادي، للكبتن كاملاً ولا تُقتطع منه العمولة. وصفرٌ يُخفي الخدمة."
        />
      </div>
      <Button
        className="mt-14"
        size="sm"
        disabled={disabled || !dirty || fee.trim() === ""}
        loading={busy}
        onClick={() => {
          setBusy(true);
          updateServiceSettings(row.country_code, { parcel_fee: fee.trim() })
            .then(() => onSaved("حُفظ رسم الطرد — يسري على ما يُطلب بعده لا على رحلةٍ قائمة"))
            .catch((caught) => onError(caught))
            .finally(() => setBusy(false));
        }}
      >
        حفظ
      </Button>
    </>
  );
}

/** **بالساعة** (§٦٣-ج/٥) — أربعةُ أرقامٍ لسوقٍ واحد: سعرُ الساعة مالاً، وكيلومتراتُها عدّاً، ودقائقُ الإلغاء مدّةً، وأقصى الساعات عدّاً.
 *
 * **ويُرسل ما تغيّر وحدَه** (`PATCH` جزئيّ كأخويه): حقلٌ لم يُلمس لا يُكتب فوق ما كتبه غيرُه بين القراءة والحفظ، وسجلُّ التدقيق
 * يقول ما عُدِّل فعلاً. **والحدودُ في الخلفية** (`ServiceSettingUpdate`: كيلومتراتٌ ٠–٢٠٠، دقائقُ ٠–٢٤٠، ساعاتٌ ١–٢٤) — ورفضُها
 * يُقال تحت حقله. **ولا مبلغَ يُحسب هنا**: «نصفُ ساعةٍ من السعر» تقوله الخلفيةُ عند الإلغاء من المجمَّد على الرحلة. و`key={country}`
 * عليه كبقية النماذج.
 */
function HourlyForm({
  row,
  disabled,
  onSaved,
  onError,
}: {
  row: ServiceSetting;
  disabled: boolean;
  onSaved: (message: string) => void;
  onError: (caught: unknown) => void;
}) {
  const [rate, setRate] = useState(row.hourly_rate);
  const [km, setKm] = useState(String(row.hourly_km_per_hour));
  const [cancelMinutes, setCancelMinutes] = useState(row.hourly_cancel_minutes);
  const [maxHours, setMaxHours] = useState(String(row.hourly_max_hours));
  const [busy, setBusy] = useState(false);

  // **الفرقُ بالمقارنة** — من كتب ثمّ أعاد القيمةَ كما كانت لم يغيّر شيئاً
  const changes: Partial<Omit<ServiceSetting, "country_code">> = {};
  if (rate.trim() !== row.hourly_rate) changes.hourly_rate = rate.trim();
  if (Number(km) !== row.hourly_km_per_hour) changes.hourly_km_per_hour = Number(km);
  if (cancelMinutes !== row.hourly_cancel_minutes) changes.hourly_cancel_minutes = cancelMinutes;
  if (Number(maxHours) !== row.hourly_max_hours) changes.hourly_max_hours = Number(maxHours);
  const dirty = Object.keys(changes).length > 0;

  return (
    <>
      <div className="grid grid-cols-2 gap-10">
        <MoneyField
          name="hourly_rate"
          label="سعر الساعة"
          value={rate}
          onChange={(next) => setRate(next.replace(/[^0-9.,]/g, ""))}
          currency={currencyOf(row.country_code)}
          disabled={disabled}
          hint="شاملاً كيلومتراتِ الساعة — وصفرٌ يُخفي الخدمة"
        />
        {/* **والتلميحُ تحت الحقل بصنف أخويه** (`ad-hint`) — `Field` لا يحمل تلميحاً، والعددُ بلا وحدةٍ يُقرأ ملتبساً */}
        <div>
          <Field
            name="hourly_km_per_hour"
            label="كيلومترات الساعة"
            dir="ltr"
            inputMode="numeric"
            value={km}
            disabled={disabled}
            onChange={(event) => setKm(event.target.value.replace(/[^0-9]/g, ""))}
          />
          <p className="ad-hint">المشمولةُ في سعر الساعة — وما زاد بسعر الكيلومتر العاديّ</p>
        </div>
        <DurationField
          name="hourly_cancel_minutes"
          label="رسم إلغاء الراكب"
          wire="minute"
          value={cancelMinutes}
          disabled={disabled}
          onChange={setCancelMinutes}
          hint="إلغاءُ الراكب بعد وصول الكبتن: هذه الدقائقُ من سعر الساعة للكبتن"
        />
        <div>
          <Field
            name="hourly_max_hours"
            label="أقصى الساعات في الطلب"
            dir="ltr"
            inputMode="numeric"
            value={maxHours}
            disabled={disabled}
            onChange={(event) => setMaxHours(event.target.value.replace(/[^0-9]/g, ""))}
          />
          <p className="ad-hint">سقفُ عدّاد الساعات عند الراكب — من 1 إلى 24</p>
        </div>
      </div>
      <Button
        className="mt-14"
        size="sm"
        disabled={disabled || !dirty || rate.trim() === "" || km === "" || maxHours === ""}
        loading={busy}
        onClick={() => {
          setBusy(true);
          updateServiceSettings(row.country_code, changes)
            .then(() => onSaved("حُفظت الرحلةُ بالساعة — تسري على ما يُطلب بعدها لا على رحلةٍ قائمة"))
            .catch((caught) => onError(caught))
            .finally(() => setBusy(false));
        }}
      >
        حفظ
      </Button>
    </>
  );
}

/** **المشوارُ الثابت** (§٦٣-ج/٦) — ثلاثةُ أرقامٍ لسوقٍ واحد: الخصمُ نسبةً، وحافزُ الكبتن المعتمد مالاً، وأقصى أيام التعليق عدّاً.
 *
 * **ويُرسل ما تغيّر وحدَه** (`PATCH` جزئيّ كإخوته) — **والنسبةُ والمالُ نصّان كما وصلا** فلا يمرّان بعائم: «10.00» تبقى «10.00»
 * ما لم تُلمس. **والحدودُ في الخلفية** (`ServiceSettingUpdate`: خصمٌ من ٠ إلى ما دون ١٠٠، حافزٌ لا سالب، تعليقٌ ٠–٣١) — ورفضُها
 * يُقال تحت حقله. **ولا مبلغَ يُحسب هنا**: سعرُ الرحلة المجمَّد يحسبه التسعيرُ في الخلفية لحظةَ الشراء. و`key={country}` كإخوته.
 */
function CommuteForm({
  row,
  disabled,
  onSaved,
  onError,
}: {
  row: ServiceSetting;
  disabled: boolean;
  onSaved: (message: string) => void;
  onError: (caught: unknown) => void;
}) {
  const [discount, setDiscount] = useState(row.commute_discount_percent);
  const [incentive, setIncentive] = useState(row.commute_captain_incentive);
  const [suspendDays, setSuspendDays] = useState(String(row.commute_max_suspend_days));
  const [busy, setBusy] = useState(false);

  // **الفرقُ بالمقارنة** — من كتب ثمّ أعاد القيمةَ كما كانت لم يغيّر شيئاً
  const changes: Partial<Omit<ServiceSetting, "country_code">> = {};
  if (discount.trim() !== row.commute_discount_percent) changes.commute_discount_percent = discount.trim();
  if (incentive.trim() !== row.commute_captain_incentive) changes.commute_captain_incentive = incentive.trim();
  if (Number(suspendDays) !== row.commute_max_suspend_days) changes.commute_max_suspend_days = Number(suspendDays);
  const dirty = Object.keys(changes).length > 0;

  return (
    <>
      <div className="grid grid-cols-2 gap-10">
        {/* **والتلميحُ تحت الحقل بصنف أخويه** (`ad-hint`) — `Field` لا يحمل تلميحاً */}
        <div>
          <Field
            name="commute_discount_percent"
            label="الخصم ٪"
            dir="ltr"
            inputMode="decimal"
            value={discount}
            disabled={disabled}
            onChange={(event) => setDiscount(event.target.value.replace(/[^0-9.]/g, ""))}
          />
          <p className="ad-hint">يتقاسمه الكبتنُ وTAXO بقدر نسبة العمولة — وصفرٌ يُخفي الخدمة</p>
        </div>
        <MoneyField
          name="commute_captain_incentive"
          label="حافز الكبتن لكلِّ رحلة"
          value={incentive}
          onChange={(next) => setIncentive(next.replace(/[^0-9.,]/g, ""))}
          currency={currencyOf(row.country_code)}
          disabled={disabled}
          hint="من TAXO للكبتن المعتمد لكلِّ رحلة — وصفرٌ لا حافز (الشارةُ والأولويّة)"
        />
        <div>
          <Field
            name="commute_max_suspend_days"
            label="أقصى أيام التعليق"
            dir="ltr"
            inputMode="numeric"
            value={suspendDays}
            disabled={disabled}
            onChange={(event) => setSuspendDays(event.target.value.replace(/[^0-9]/g, ""))}
          />
          <p className="ad-hint">لكلِّ اشتراك — ويُرحَّل كلُّ يومٍ معلَّقٍ إلى ما بعد آخر يوم</p>
        </div>
      </div>
      <Button
        className="mt-14"
        size="sm"
        disabled={disabled || !dirty || discount.trim() === "" || incentive.trim() === "" || suspendDays === ""}
        loading={busy}
        onClick={() => {
          setBusy(true);
          updateServiceSettings(row.country_code, changes)
            .then(() => onSaved("حُفظ المشوارُ الثابت — الخصمُ يسري على ما يُشترى بعده لا على اشتراكٍ قائم"))
            .catch((caught) => onError(caught))
            .finally(() => setBusy(false));
        }}
      >
        حفظ
      </Button>
    </>
  );
}

/** **بين المدن** (§٦٣-ج/٧) — رقمٌ واحدٌ لسوقٍ واحد: **مهلةُ الإلغاء بالساعات قبل الانطلاق**. قبلها يلغي الكبتنُ رحلتَه بلا أثر،
 * **وعندها تُلغى وحدَها رحلةٌ لم يبلغ محجوزُها أقلَّ ما ينطلق به** ويُردّ للركّاب كاملاً.
 *
 * **ويُرسل ما تغيّر وحدَه** كإخوته، **والحدُّ في الخلفية** (`ServiceSettingUpdate`: ١–٤٨) ورفضُه تحت حقله. **ولا تُجمَّد على الرحلة**
 * — فالحفظُ يقول إنها تحكم القائمَ كذلك. و`key={country}` كإخوته.
 */
function IntercityForm({
  row,
  disabled,
  onSaved,
  onError,
}: {
  row: ServiceSetting;
  disabled: boolean;
  onSaved: (message: string) => void;
  onError: (caught: unknown) => void;
}) {
  const [hours, setHours] = useState(String(row.intercity_cancel_deadline_hours));
  const [busy, setBusy] = useState(false);
  const changes: Partial<Omit<ServiceSetting, "country_code">> = {};
  if (Number(hours) !== row.intercity_cancel_deadline_hours) changes.intercity_cancel_deadline_hours = Number(hours);
  const dirty = Object.keys(changes).length > 0;

  return (
    <>
      <div className="grid grid-cols-2 gap-10">
        <div>
          <Field
            name="intercity_cancel_deadline_hours"
            label="مهلة الإلغاء بالساعات"
            dir="ltr"
            inputMode="numeric"
            value={hours}
            disabled={disabled}
            onChange={(event) => setHours(event.target.value.replace(/[^0-9]/g, ""))}
          />
          <p className="ad-hint">قبل الانطلاق — من 1 إلى 48. وتُعلَن الرحلةُ قبل موعدها بأكثرَ منها</p>
        </div>
      </div>
      <Button
        className="mt-14"
        size="sm"
        disabled={disabled || !dirty || hours === ""}
        loading={busy}
        onClick={() => {
          setBusy(true);
          updateServiceSettings(row.country_code, changes)
            .then(() => onSaved("حُفظت مهلةُ بين المدن — وتحكم الرحلاتِ المعلَنةَ القائمةَ كذلك"))
            .catch((caught) => onError(caught))
            .finally(() => setBusy(false));
        }}
      >
        حفظ
      </Button>
    </>
  );
}

/** **الاسترداد الأسبوعي** (§٦٣-ج/٨) — رقمان لسوقٍ واحد: **المبلغُ الثابت** مالاً من TAXO، **وأيامُ الأسبوع بلا جمعته** عدّاً.
 *
 * **ويُرسل ما تغيّر وحدَه** (`PATCH` جزئيّ كإخوته) — **والمالُ نصٌّ كما وصل** فلا يمرّ بعائم. **والحدودُ في الخلفية**
 * (`ServiceSettingUpdate`: مبلغٌ لا سالب، أيامٌ ٢–١٤) ورفضُها تحت حقله. **ولا مبلغَ يُحسب هنا**: ما ينزل في المحفظة هو المجمَّدُ على
 * السلسلة كما هو. و`key={country}` كإخوته.
 */
function CashbackForm({
  row,
  disabled,
  onSaved,
  onError,
}: {
  row: ServiceSetting;
  disabled: boolean;
  onSaved: (message: string) => void;
  onError: (caught: unknown) => void;
}) {
  const [amount, setAmount] = useState(row.cashback_amount);
  const [days, setDays] = useState(String(row.cashback_days));
  const [busy, setBusy] = useState(false);

  // **الفرقُ بالمقارنة** — من كتب ثمّ أعاد القيمةَ كما كانت لم يغيّر شيئاً
  const changes: Partial<Omit<ServiceSetting, "country_code">> = {};
  if (amount.trim() !== row.cashback_amount) changes.cashback_amount = amount.trim();
  if (Number(days) !== row.cashback_days) changes.cashback_days = Number(days);
  const dirty = Object.keys(changes).length > 0;

  return (
    <>
      <div className="grid grid-cols-2 gap-10">
        <MoneyField
          name="cashback_amount"
          label="مبلغ الاسترداد"
          value={amount}
          onChange={(next) => setAmount(next.replace(/[^0-9.,]/g, ""))}
          currency={currencyOf(row.country_code)}
          disabled={disabled}
          hint="مبلغٌ ثابتٌ ينزل في محفظة الراكب في اليوم الأخير من أسبوعه — من TAXO. وصفرٌ يُخفي الخدمة."
        />
        {/* **والتلميحُ تحت الحقل بصنف إخوته** (`ad-hint`) — `Field` لا يحمل تلميحاً */}
        <div>
          <Field
            name="cashback_days"
            label="أيام الأسبوع"
            dir="ltr"
            inputMode="numeric"
            value={days}
            disabled={disabled}
            onChange={(event) => setDays(event.target.value.replace(/[^0-9]/g, ""))}
          />
          <p className="ad-hint">أيامُ الأسبوع بلا جمعته — 6 افتراضاً</p>
        </div>
      </div>
      <Button
        className="mt-14"
        size="sm"
        disabled={disabled || !dirty || amount.trim() === "" || days === ""}
        loading={busy}
        onClick={() => {
          setBusy(true);
          updateServiceSettings(row.country_code, changes)
            .then(() => onSaved("حُفظ الاسترداد الأسبوعي — يسري على ما يبدأ من سلاسلَ بعده لا على سلسلةٍ قائمة"))
            .catch((caught) => onError(caught))
            .finally(() => setBusy(false));
        }}
      >
        حفظ
      </Button>
    </>
  );
}

/** **A35 — المحادثة والمكالمة** (§٦٦-ب/١٢، §٦٦-ج/١٦) — لسوقٍ واحد: كم تبقى المحادثةُ بعد انتهاء الرحلة (٩٠ افتراضاً)، **وتسجيلُ
 *  المكالمات مطفأً افتراضاً** ومدّةُ حفظ ملفّاته.
 *
 *  **والتسجيلُ مفتاحٌ يُكتب لحظةَ قلبه** (كمفاتيح الميزات) — **ولا يُشعَل قبل نشر سطره**: الخادمُ يرفض بنصٍّ يقول أيَّ السياستين
 *  تنقصه (`trip_chat.require_published_line`)، **فيُقال تحته بحرفه**. والتحذيرُ الثابتُ فوقه بحرف التصميم. **ولا يُشعله إلا
 *  المالك** — والشاشةُ لا تقرّر شيئاً عنه. والمدّتان تُرسلان ما تغيّر وحدَه (`PATCH` جزئيّ كإخوته)، والحدودُ في الخلفية (١–٣٦٥٠). */
function ChatCallForm({
  row,
  disabled,
  onSaved,
  onError,
}: {
  row: ServiceSetting;
  disabled: boolean;
  onSaved: (message: string) => void;
  onError: (caught: unknown) => void;
}) {
  const [chatDays, setChatDays] = useState(String(row.chat_retention_days));
  const [recordingDays, setRecordingDays] = useState(String(row.call_recording_retention_days));
  const [busy, setBusy] = useState(false);
  const [switching, setSwitching] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);

  const changes: Partial<Omit<ServiceSetting, "country_code">> = {};
  if (Number(chatDays) !== row.chat_retention_days) changes.chat_retention_days = Number(chatDays);
  if (Number(recordingDays) !== row.call_recording_retention_days) {
    changes.call_recording_retention_days = Number(recordingDays);
  }
  const dirty = Object.keys(changes).length > 0;

  return (
    <>
      <div>
        <Field
          name="chat_retention_days"
          label="مدّة حفظ الرسائل (أيام)"
          dir="ltr"
          inputMode="numeric"
          value={chatDays}
          disabled={disabled}
          onChange={(event) => setChatDays(event.target.value.replace(/[^0-9]/g, ""))}
        />
        <p className="ad-hint">
          90 افتراضاً — تُحذف المحادثةُ وسجلُّ مكالماتها بعدها آلياً، إلا ما فيه بلاغٌ مفتوحٌ فحتى يُعالَج ثمّ المدّة.
        </p>
      </div>

      <div className="mt-18 flex items-start gap-12">
        <span className="flex-1">
          <span className="block text-13 font-semibold text-ink">تسجيل المكالمات</span>
          {/* **التحذيرُ الثابت بحرف التصميم** (§٦ A35) — فوق المفتاح لا بعد قلبه */}
          <span className="block text-11 leading-snug text-warn">
            إشعالُه يُسمِع الطرفين تنبيهاً قبل كلِّ مكالمة، ويحتاج سطراً في سياسة الخصوصية يُنشر قبله.
          </span>
        </span>
        <Switch
          checked={row.call_recording_enabled}
          disabled={disabled || switching}
          label="تسجيل المكالمات"
          onChange={(next) => {
            setSwitching(true);
            setRefusal(null);
            updateServiceSettings(row.country_code, { call_recording_enabled: next })
              .then(() =>
                onSaved(next ? "اشتعل تسجيلُ المكالمات — يسبقه التنبيهُ عند الطرفين" : "أُطفئ تسجيلُ المكالمات"),
              )
              .catch((caught) => {
                setRefusal(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
                onError(caught);
              })
              .finally(() => setSwitching(false));
          }}
        />
      </div>
      {refusal ? <ErrorNote message={refusal} /> : null}

      <div className="mt-14">
        <Field
          name="call_recording_retention_days"
          label="مدّة حفظ التسجيلات (أيام)"
          dir="ltr"
          inputMode="numeric"
          value={recordingDays}
          disabled={disabled}
          onChange={(event) => setRecordingDays(event.target.value.replace(/[^0-9]/g, ""))}
        />
        <p className="ad-hint">تُجمَّد على التسجيل لحظةَ رفعه، ثمّ يُحذف ملفُّه آلياً — والسجلُّ الوصفيُّ يبقى بمدّة المحادثة.</p>
      </div>

      <Button
        className="mt-14"
        size="sm"
        disabled={disabled || !dirty || chatDays === "" || recordingDays === ""}
        loading={busy}
        onClick={() => {
          setBusy(true);
          updateServiceSettings(row.country_code, changes)
            .then(() => onSaved("حُفظت مدّتا الحفظ — تسريان على الحذف الآليّ القادم"))
            .catch((caught) => onError(caught))
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
