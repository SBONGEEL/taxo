# سطورُ الخصوصية وتصريحاتُ Play — الفقاعتان والودجات (أمرُ المالك ٢٠٢٦-١١-٢٠ الرابع، SPEC §١١٠)

> **لماذا هنا لا في الصفحة**: نصُّ السياسة يُحرَّر من اللوحة («السياسات») ويُخبز في `site/` وقتَ الرفع (`site/scripts/inline-policy.mjs`).
> **ونشرُ نسخةٍ جديدةٍ يحتاج دخولَ حساب المالك بالعامل الثاني** — فالنصُّ جاهزٌ للّصق، والنشرُ مع أوّل جلسةٍ له في اللوحة.
> **ولا شيءَ من هذا يعمل قبل إشعال مفتاحه** — فالسياسةُ الحاليّةُ صادقةٌ حتى يُشعل.

## سياسةُ الكبتن — يُضاف تحت «الأذونات» (الأردن · ليبيا · الجزائر)

**العربيّة**

- **الظهور فوق التطبيقات**: لعرض فقاعة TAXO وقائمتها وطلب الرحلة وأنت في تطبيقٍ آخر. لا تقرأ الفقاعةُ ما على شاشتك ولا ما تكتبه.
- **الميكروفون**: للمكالمة مع الراكب داخل التطبيق، **وإن اخترتَ «قبول ورفض بالصوت»** فللاستماع إلى كلمتَي «قبول» و«رفض» **وشاشةُ طلب الرحلة
  ظاهرةٌ وحدَها**. يُفهم الكلامُ بمعرِّف الكلام في نظام هاتفك، **ولا نسجّل صوتك ولا نرسله إلى خوادمنا ولا نحفظه**. ويتوقّف الاستماعُ لحظةَ
  تُغلق الشاشة.
- **الودجة والفقاعة**: تعرضان أرقامك (صافي اليوم، رحلاتُه، أيّامُ الاشتراك، هدفُك) **على هاتفك وحدَه** — والهدفُ رقمٌ تكتبه أنت ولا يُرسل.
- **أقربُ منطقةٍ مزدحمة**: من عدد الطلبات في مربّعاتٍ بنحو كيلومتر في آخر نصف ساعة، **مجمَّعاً بلا هويّة أحد** — لا يظهر فيه راكبٌ ولا مكانُه.

**English**

- **Display over other apps**: to show the TAXO bubble, its menu and ride offers while you use another app. The bubble does not read your screen or what you type.
- **Microphone**: for in-app calls with the rider and, **only if you turn on “Accept or decline by voice”**, to hear the words “accept”/“decline” **while the ride-offer screen is showing**. Speech is recognised by your phone’s system speech service; **we do not record, upload or store your voice**. Listening stops when the screen closes.
- **Widget and bubble**: show your figures (today’s net, rides, subscription days, your goal) **on your phone only**; the goal is a number you type and is never sent.
- **Nearest busy area**: from ride-request counts in roughly 1 km squares over the last 30 minutes, **aggregated and anonymous** — no rider or location of a rider is shown.

**Français (Algérie)**

- **Affichage par-dessus les autres applis** : pour afficher la bulle TAXO, son menu et les demandes de course pendant que vous utilisez une autre appli. La bulle ne lit ni votre écran ni ce que vous tapez.
- **Microphone** : pour appeler le passager dans l’appli et, **seulement si vous activez « Accepter ou refuser à la voix »**, pour entendre « accepter » / « refuser » **pendant l’affichage de la demande**. La reconnaissance est faite par le service vocal du téléphone ; **nous n’enregistrons, n’envoyons ni ne conservons votre voix**.
- **Widget et bulle** : vos chiffres (net du jour, courses, jours d’abonnement, objectif) **restent sur votre téléphone** ; l’objectif est un nombre que vous tapez et n’est jamais envoyé.
- **Zone animée la plus proche** : à partir du nombre de demandes par carrés d’environ 1 km sur les 30 dernières minutes, **agrégé et anonyme**.

## سياسةُ الراكب — يُضاف تحت «الأذونات»

**العربيّة**

- **الظهور فوق التطبيقات (اختياريّ)**: **حين تُشعل «فقاعة الرحلة» من الإعدادات وحدَها** — فقاعةٌ صغيرةٌ أثناء البحث والرحلة فقط وأنت في تطبيقٍ آخر:
  وقتُ الوصول والمركبةُ ولوحتُها والاسمُ الأوّلُ للكابتن، والاتّصالُ والرسائلُ بأرقامٍ مخفيّة. لا تقرأ ما على شاشتك.
- **الودجة**: تعرض «إلى أين؟» وأسماءَ آخر وجهاتك وحالَ رحلتك **على هاتفك وحدَه**؛ **ولا تطلب رحلةً بلا تأكيدك في التطبيق**.

**English**

- **Display over other apps (optional)**: **only if you turn on “Ride bubble” in Settings** — a small bubble during search and the ride only, while you use another app: ETA, car, plate and the captain’s first name, plus call and chat with hidden numbers. It does not read your screen.
- **Widget**: shows “Where to?”, the names of your recent destinations and your ride status **on your phone only**; **it never requests a ride without your confirmation in the app**.

**Français**

- **Affichage par-dessus les autres applis (facultatif)** : **seulement si vous activez « Bulle de course »** — une petite bulle pendant la recherche et la course : heure d’arrivée, véhicule, plaque et prénom du capitaine, appel et messages avec numéros masqués.
- **Widget** : « Où allez-vous ? », vos dernières destinations et l’état de la course **sur votre téléphone uniquement** ; **aucune course sans votre confirmation dans l’appli**.

## تصريحاتُ Google Play

| البند | الكبتن | الراكب | ما يُكتب |
|---|---|---|---|
| `SYSTEM_ALERT_WINDOW` | مُعلَنٌ من قبل (الفقاعة القديمة) | **جديد** | ليس إذناً بنموذج تصريح؛ يُمنح من إعدادات النظام ويطلبه التطبيقُ بعد شرح. لا تغييرَ في الكونسول. |
| `RECORD_AUDIO` | مُعلَنٌ من قبل (المكالمة) | مُعلَنٌ من قبل (المكالمة والبحث بالصوت) | **سلامةُ البيانات — الصوت**: «لا يُجمع» يبقى صحيحاً: المعرِّفُ في النظام، ولا يصل خوادمنا شيء. إن سأل المراجع: الاستماعُ في شاشة العرض الظاهرة وحدَها وباختيار الكبتن. |
| خدمةُ المقدّمة | **لا نوعَ جديد** — الاستماعُ في نشاطٍ ظاهر لا في خدمة، فلا `microphone` FGS ولا تصريح | لا شيء | — |
| الموقع في الخلفيّة | التصريحُ القائم يغطّيه (الاستقبال) — **بلاغُ الطريق يقرأ آخرَ موقعٍ معروف** ولا يطلب جديداً | لا شيء | — |
| الودجات | لا تصريح | لا تصريح | — |

**وما يُراجَع بعد الإشعال**: إن رأت Google Play في «قبول بالصوت» ما يستوجب تصريحاً، يبقى مفتاحُ `voice_offer_answer` مطفأً — وهو مطفأٌ أصلاً.
