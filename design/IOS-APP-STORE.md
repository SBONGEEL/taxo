# iOS — App Store للتطبيقين (أمرُ المالك ٢٠٢٦-١١-١٧)

**ملفُّ العمل الواحد لنسخة iPhone**: حسابُ Apple، وجوابُ المدفوعات، وأجوبةُ الخصوصية، وملاحظاتُ المراجِع، وبطاقةُ المتجر بلغتين.
**والقراراتُ المسجَّلة باقية** (SPEC §٥٨): الشاشاتُ داخل الحزمة لا من عنوانٍ بعيد · شاشةُ إقلاعٍ بلونٍ بلا شعار · حسابُ المطوّر **باسم المالك فرداً**.
**ولا بلدَ في أيِّ نصٍّ للمتجر** (أمرُ المالك ٢٠٢٦-١٠-١٤ — كبطاقة Play)، **ولا جنسيّةَ تُنسب إلى المالك في أيِّ جواب** (شرطُ أمر ١٧/١١).
**وليبيا كما يضبطها الوكيلُ الرئيسيّ**: البلدانُ تُختار في App Store Connect لا في النصّ، والتطبيقُ يقرأ أسواقَه من الخادم.

---

## ١) حسابُ Apple Developer — **غيرُ موجودٍ** (قِيس ٢٠٢٦-١١-١٧)

لا شيءَ في `~/.taxo-secrets`، ولا رسالةَ من Apple في البريد المتّصل، و`HANDOFF.md` وSPEC §٥٨-د يذكرانه منتظَراً من المالك.

### ما يفعله المالكُ بنفسه — خطوةً خطوة

1. **Apple ID بالتحقّق بخطوتين** (إن لم يكن) — من iPhone: الإعدادات ← اسمُك ← تسجيلُ الدخول والأمان ← المصادقةُ بخطوتين.
2. **تطبيقُ Apple Developer على iPhone** (من App Store) ← «Account» ← **Enroll Now** ← **Individual / Sole Proprietor**.
3. **الاسمُ القانونيُّ كما في الهويّة**: «Mohammad Alsaidat» — وهو الاسمُ الذي سيظهر بائعاً تحت التطبيقين في المتجر.
4. **صورةُ الهويّة** يطلبها التطبيقُ ويتحقّق منها بالكاميرا.
5. **الرسم: ٩٩ دولاراً في السنة**، يُدفع ببطاقة المالك داخل التطبيق ويتجدّد سنويّاً. **لا أدفعه ولا أكتب بيانات بطاقة.**
6. **المدّة**: عادةً **من يومٍ إلى يومين** بعد الدفع؛ وقد تطول **أسبوعاً أو أكثر** إن طلبت Apple وثيقةً إضافيّة أو اتّصلت للتحقّق.
7. **بعد القبول**: App Store Connect ← «Agreements, Tax, and Banking» ← قبولُ **اتفاقيّة التطبيقات المجانيّة** (التطبيقان مجانيّان — لا حاجةَ لاتفاقيّة المدفوعات ولا بيانات بنك).

### وما أفعله أنا فورَ وجوده (لا يحتاج كلمةَ مرور المالك)

| الخطوة | من يفعلها |
|---|---|
| مفتاحُ **App Store Connect API** (دورُ **Admin** — الشهاداتُ لا تُنشأ بأقلّ؛ الخطواتُ للمالك في `DesktopAPPLE-ACCOUNT-STEPS.md`) يُنشئه المالكُ ويضعه في `~/.taxo-secrets/apple/` | المالك (دقيقتان) |
| تسجيلُ المعرّفات: `ly.tajora.rider` · `ly.tajora.driver` (+ `.widgets` لكلٍّ) وقدراتُها: Push · Time Sensitive · App Groups | أنا بالمفتاح |
| مفتاحُ **APNs (.p8)** ← يُرفع في Firebase للتطبيقين ← يُنزَّل `GoogleService-Info.plist` | المالك يُنشئه، وأنا أكمل |
| شهادةُ التوزيع وملفّاتُ التزويد ← **أسرارُ GitHub المشفّرة** وحدَها | أنا بالمفتاح |
| وظيفةُ `ios-release` في CI: أرشيفٌ موقَّع ← TestFlight | أنا |
| سجلّاتُ التطبيقين في App Store Connect، والبطاقة، والصور، وملاحظاتُ المراجِع | أنا بالمفتاح |
| **الإرسالُ للمراجعة** | أنا — بعد أن يخضرَّ كلُّ ما في §٨ |

---

## ٢) المدفوعات — **الجوابُ من نصِّ الإرشادات** (قُرئ ٢٠٢٦-١١-١٧ من developer.apple.com/app-store/review/guidelines)

| ما يُدفع في التطبيق | الحكم | النصّ |
|---|---|---|
| **أجرةُ الرحلة** (نقد · محفظة · بطاقة · CliQ) | **خارج الشراء داخل التطبيق — وجوباً لا جوازاً** | **3.1.3(e)**: «If your app enables people to purchase physical goods or services that will be consumed outside of the app, you **must** use purchase methods other than in-app purchase» |
| **شحنُ المحفظة** — رصيدٌ لا يُنفق إلا على رحلات | **خارجه** — تابعٌ لما يُشترى به (خدمةٌ ماديّة) | 3.1.3(e) |
| **التحويلُ بين راكبَين** | **خارجه** — مالٌ بين شخصين لا محتوى رقميّ | 3.1.3(e) · ويُنظر 3.2.1(viii) أدناه |
| **البقشيش للكبتن** | **خارجه** | **3.2.1(vii)**: هديّةٌ اختياريّة وتصل كاملةً للمستلم |
| **بطاقاتُ TAXO** (QR) — تشحن المحفظة | **خارجه** — رصيدُ رحلات؛ و3.1.1 يمنع رمزَ QR يفتح **ميزةً رقميّة**، وهذه لا تفتح ميزة | 3.1.1 · 3.1.3(e) |
| **اشتراكُ الكبتن** | **لا نصَّ يسمّيه** — انظر تحت | — |
| **الشحنُ بالعملات الرقميّة** (`moonpay_rider_enabled`، مطفأٌ أو مضاءٌ من اللوحة) | **خطر** — انظر تحت | 3.1.5 |

### اشتراكُ الكبتن — ما يقوله النصُّ وما لا يقوله

- **ما يُشترى**: حقُّ استقبال طلبات الرحلات — **والعملُ نفسُه يقع في الطريق لا في التطبيق**. فأقربُ قراءةٍ **3.1.3(e)**: خدمةٌ تُستهلك خارج التطبيق.
- **وما قد تقرؤه Apple**: **3.1.1** — «If you want to unlock features or functionality within your app (by way of example: subscriptions…) you must use in-app purchase» — فاستقبالُ الطلبات **ميزةٌ في التطبيق** يفتحها الاشتراك.
- **والنصُّ لا يحسم بين القراءتين**، والسوابقُ (تطبيقاتُ سائقين تشحن رصيدَ عمولتها ببطاقة) سوابقُ لا نصّ — **فلا أكتب «مسموح» بلا دليل** (شرطُ الأمر: «لا تخمّن»).

**قرارُ المالك ٢٠٢٦-١١-١٨ (أقرّ ما يلي كما هو):** يُشرح الاشتراكُ للمراجِع بوضوح؛ وإن رفضت Apple الدفعَ بالبطاقة له **يُخفى الدفعُ بالبطاقة لاشتراك الكبتن على iPhone وحدَه**؛ **ولا شراءَ داخل التطبيق من Apple (IAP) أبداً.**

**والعملُ الذي اخترته (المديرُ العامّ — يُبلَّغ ولا يُسأل)**: **لا يتغيّر في التطبيق شيء**، ويُكتب الاشتراكُ **صراحةً** في ملاحظات المراجِع
(§٦) بعلّته: «رسمُ منصّةٍ يدفعه سائقٌ مستقلّ ليعرض خدمةَ نقلٍ ماديّة — 3.1.3(e)». **فإن رفضته Apple** يقول ردُّها النصَّ الحاكم، وعندها:
**يُخفى شراءُ الاشتراك بالبطاقة في نسخة iOS وحدَها** (يبقى بالمحفظة والنقد وCliQ — وكلُّها خارج التطبيق)، **وأندرويد لا يُمسّ**.
**ولا سعرَ ولا قاعدةَ مالٍ تتغيّر في أيِّ الطريقين** — فهو قرارُ عرضٍ لا قرارُ مال.

### العملاتُ الرقميّة — 3.1.5 والحسابُ الفرديّ

**3.1.5(i)**: «Apps may facilitate virtual currency storage, provided they are offered by developers **enrolled as an organization**».
**وهو اليوم مطفأٌ في كلِّ الدول بقرار المالك** (٢٠٢٦-١١-١٥ — `moonpay_rider_enabled` · `moonpay_driver_enabled` · `nowpay_card_enabled`
false، `HANDOFF.md`)، **فلا يراه المراجِع ولا يُذكر له**. TAXO لا يخزّن عملةً رقميّة — يصل الرصيدُ بالدينار عبر مزوّد — فليس «محفظةَ عملاتٍ»
بنصّ البند؛ **لكنّ الحسابَ فرديّ**، فإن أُعيد إشعالُه يومَ تكون نسخةُ iOS في المتجر **فخطرُ رفضٍ عند المراجعة التالية** يُقال للمالك قبل الإشعال.

---

## ٣) حذفُ الحساب — **مبنيٌّ، وأقرّه المالك ٢٠٢٦-١١-١٨** (SPEC §٥٩-ح)

**5.1.1(v)**: «If your app supports account creation, you must also offer account deletion within the app» — **مستوفى** في التطبيقين،
**والشاشاتُ نفسُها تعمل على iOS بلا تغيير** (الحزمةُ الواحدة):

1. الحساب ← «حذفُ الحساب» ← شاشةٌ تقول ما يُمحى وما يبقى (`lib/deletion-text.ts`).
2. **مهلةُ ٣٠ يوماً** — يُلغى الحذفُ بالدخول خلالها.
3. **يُمحى**: الاسمُ والهاتفُ والصورةُ والأماكنُ المحفوظة ورمزُ الإشعار، و`cliq_alias` على صفِّ الكبتن.
4. **يبقى مجهَّلاً**: سجلُّ الرحلات والمعاملات الماليّة (لأسبابٍ قانونيّةٍ ومحاسبيّة — والنصُّ يقوله للمستخدم صراحةً).
5. **الرصيد** (قرارُ المالك ٢٠٢٦-١١-١٨): **قبل أن يبدأ الحذف** يُعرض على الراكب صاحبِ الرصيد **تحويلُه إلى مستخدمٍ آخر**، أو **يؤكّد صراحةً ضياعَه** بكتابة المبلغ نفسِه — وبلا أحدهما لا يبدأ الحذف (`DeleteAccount.tsx` · `account_deletion.request` يرفض بـ`DeletionBalanceUnacknowledged`). مقيسٌ في الشيفرة يومَ القرار: هذا هو المبنيُّ، فلا تغييرَ فيه.
6. **وبابٌ على الويب أيضاً**: `https://taxo.tajora.ly/delete-account` (و`-en`) — لحقل «Account deletion URL» إن طُلب.

**وقرارٌ واحدٌ ما زال للمالك ولا يمسّ Apple**: نسخةُ لوحة المركبة على الرحلة لحظةَ القبول (§٥٩-ح/٢) — **Apple لا تشترطه**.

---

## ٤) App Privacy — «Data Used to Track You» و«Data Linked to You»

**التتبّع (Tracking)**: **لا** — لا إعلانات، ولا معرّفَ إعلانيّ، ولا SDK تتبّع، **فلا شاشةَ ATT** (لا `NSUserTrackingUsageDescription`).
**وكلُّ ما يُجمع «Linked to You»** (مربوطٌ بالحساب)، **وغرضُه App Functionality** إلا ما يُذكر غيرُه. مأخوذٌ صنفاً صنفاً من `design/PLAY-DATA-SAFETY.md`
**ومن السياسة المنشورة** (`/privacy-en` · `/driver-privacy-en`) — فلا يفترق المتجران.

| فئةُ Apple | الراكب | الكبتن | الأغراض |
|---|---|---|---|
| Contact Info → Name · Phone Number | ✓ | ✓ | App Functionality · Account |
| Contact Info → Email Address | ✓ اختياريّ | ✓ اختياريّ | Account |
| Location → Precise Location | ✓ | ✓ (**وفي الخلفية متّصلاً**) | App Functionality · Fraud Prevention |
| Location → Coarse Location | ✓ | ✓ | App Functionality |
| Financial Info → Other Financial Info (الدفتر، المراجع، الإيصالات) | ✓ | ✓ (الأرباح، السلَف، حسابُ السحب) | App Functionality · Fraud Prevention |
| Purchases → Purchase History (رحلات، شحن، اشتراكات) | ✓ | ✓ | App Functionality |
| User Content → Audio Data (مكالمةٌ مسجَّلة بعد إشعارٍ يُقرّه الطرفان) | ✓ اختياريّ | ✓ اختياريّ | Fraud Prevention |
| User Content → Photos or Videos | ✓ اختياريّ | ✓ **مطلوب** (صورةٌ ومركبة) | App Functionality · Fraud Prevention |
| User Content → Other User Content (التقييم، «أرسل ملاحظة»، الدردشة) | ✓ | ✓ | App Functionality |
| Sensitive Info (الجنسُ المصرَّح به لخدمة النساء) | ✓ اختياريّ | ✓ اختياريّ | App Functionality |
| Identifiers → User ID · Device ID (رمزُ الإشعار، معرّفُ تطبيقٍ عشوائيّ) | ✓ | ✓ | App Functionality |
| Diagnostics → Crash Data · Other Diagnostic Data | ✓ | ✓ | App Functionality |
| **Other Data → وثائقُ الكبتن** (رخصة، هويّة، تسجيلُ مركبة) | — | ✓ **مطلوب** | App Functionality · Fraud Prevention |

**ولا يُجمع**: Contacts · Health · Browsing History · Search History · **Payment Info** (رقمُ البطاقة يُكتب في صفحة المزوّد لا في TAXO).
**وسياسةُ الخصوصية**: الراكب `https://taxo.tajora.ly/privacy-en` · الكبتن `https://taxo.tajora.ly/driver-privacy-en`.

### نصوصُ الأذونات — **مطابقةٌ لما يفعله التطبيقُ فعلاً** (في `Info.plist` بالعربيّة و`fr.lproj` بالفرنسيّة)

| المفتاح | الراكب | الكبتن |
|---|---|---|
| الموقع أثناء الاستعمال | نقطةُ الالتقاط والكباتنُ القريبون | ظهورُك للركّاب القريبين والملاحة |
| الموقع دائماً | — (**لا يُطلب**) | استقبالُ الطلبات ومشاركةُ موقعك مع الراكب والتطبيقُ في الخلفية |
| الكاميرا | صورتُك، **ومسحُ QR لبطاقة TAXO** | صورتُك ووثائقُك عند التسجيل |
| الصور | صورتُك | صورتُك ووثائقُك |
| الميكروفون | المكالمةُ مع الكبتن **والبحثُ بالصوت** | المكالمةُ مع الراكب |
| التعرّفُ على الكلام | البحثُ عن الوجهة بالصوت | — |
| Face ID | الدخولُ بدل كلمة المرور | نفسُه |

---

## ٥) الموقعُ في الخلفية — للكبتن وحدَه (2.5.4)

**2.5.4**: «Multitasking apps may only use background services for their intended purposes: VoIP, audio playback, **location**…»

- **`UIBackgroundModes`** للكبتن: `location` و`remote-notification` **وحدَهما**. والراكبُ: `remote-notification` وحدَه — **لا موقعَ له في الخلفية**.
- **يبدأ بفعل الكبتن**: «ابدأ الاستقبال» — **ويقف** بـ«إيقاف الاستقبال» أو بالخروج. **والمؤشّرُ الأزرق** ظاهرٌ طوال الوقت (`showsBackgroundLocationIndicator`).
- **والحارسُ** `check:ios`: كلُّ وضعٍ خلفيٍّ مصرَّحٍ به يجب أن يكون له فعلٌ في الشيفرة — `location` بلا `allowsBackgroundLocationUpdates = true` يُسقط البناء.

**نصُّ التبرير لملاحظات المراجِع** (بالإنجليزيّة — يُلصق كما هو):

> TAXO Captain is the driver side of a ride-hailing service. Background location is used **only while the driver is online** — after they tap
> "Start receiving" (ابدأ الاستقبال) — so that nearby ride requests are dispatched to them and, during a trip, the rider sees the car approaching.
> It stops when the driver goes offline. The blue location indicator is shown the whole time. Without it, a driver who switches to a navigation
> app drops out of dispatch within about 30 seconds.

---

## ٦) ملاحظاتُ المراجِع (App Review Information) — بالإنجليزيّة

**وضعُ الضيف** (SPEC §٧٦-ن): زرُّ «جرّب التطبيق» في الترحيب يفتح عرضاً كاملاً **بلا حساب** — خريطةٌ ورحلةٌ محاكاة، **ولا ينادي الإنتاجَ بشيءٍ يكتب**.
**وحسابُ تجربةٍ حقيقيّ** لكلِّ تطبيقٍ يُنشئه **الوكيلُ الرئيسيّ** على الإنتاج (لا ألمس بيانات الإنتاج) ويضعه في `~/.taxo-secrets/apple-review.txt`
— **والتحقّقُ برمزٍ يصل الهاتف**، فرقمُ الحساب يُسجَّل بمسار «رمزٍ ثابتٍ للمراجِع» إن كان مبنيّاً، **وإلا فالضيفُ وحدَه** ويُقال ذلك.

```
Sign-in: phone number + password (the username is the phone number). There is no third-party login,
so Sign in with Apple is not required (4.8).

Quick look without an account: on the welcome screen tap "Try the app" (جرّب التطبيق). It opens a full
simulated demo — map, ride request, live tracking — with no account and no real ride.

Demo account: <from apple-review.txt>

Payments (3.1.3(e)): rides are physical transport consumed outside the app. Riders pay cash, from a wallet
that can only be spent on rides, by card on the payment provider's page, or by bank transfer. No digital
content is sold. Drivers pay a platform fee (subscription) to offer that physical service; it is paid the
same ways and unlocks no digital content.

Driver app background location: see the note above (used only while online; blue indicator shown).

Account deletion: Account → Delete account (in-app, 30-day grace period).

Languages: Arabic (default) and French.
```

---

## ٧) بطاقةُ المتجر — عربيّة وإنجليزيّة

**الحدود**: الاسم ≤ ٣٠ · العنوانُ الفرعيّ ≤ ٣٠ · الكلماتُ المفتاحيّة ≤ ١٠٠ بايت · النصُّ الترويجيّ ≤ ١٧٠ · الوصف ≤ ٤٠٠٠.
**وقواعدُ بطاقة Play باقيةٌ هنا**: لا بلد · لا «أرخص/أسرع/الأفضل» · لا رقمَ سعرٍ ولا خصم · **لا «صفر عمولة»** (`check:commission-text`).

### الراكب — `ly.tajora.rider`

| الحقل | العربيّة | English |
|---|---|---|
| الاسم | TAXO | TAXO |
| العنوانُ الفرعيّ | اطلب رحلتك وتابعها | Request a ride, track it live |
| الكلمات | تاكسي,رحلة,سيارة,كبتن,توصيل,مشوار,أجرة,محفظة,تنقل,خرائط | taxi,ride,car,driver,cab,trip,wallet,transport,map,booking |
| الترويجيّ | اطلب سيارةً، تابعها على الخريطة، وادفع نقداً أو من محفظتك. | Request a car, watch it arrive on the map, and pay in cash or from your wallet. |
| الفئة | Travel (والثانية Navigation) | |

**الوصفُ العربيّ**: نصُّ `design/PLAY-LISTING.md` §١ الكامل **حرفاً** (المتجران بنصٍّ واحد)، **ويُضاف قبل «حسابُك بيدك»**:

```
على iPhone
ترى رحلتك على شاشة القفل وفي Dynamic Island، وتردّ على مكالمة الكبتن كمكالمةٍ عاديّة.
```

**English description**:

```
TAXO connects you with a nearby captain in minutes.

Request your ride
Set your pickup and destination on the map and choose the vehicle class that suits you.
You see the price before you confirm.

Track your car
Watch the car approach on the map with the captain's name, plate and colour. On iPhone,
the ride stays on your Lock Screen and in the Dynamic Island.

Pay your way
Cash to the captain, from your in-app wallet, or by card. Top up your wallet and send
balance to another rider.

All in one place
Save home and work, book a ride in advance, review your rides and payments, and rate
your trip when it ends.

Your account, your call
Edit your details, choose your notifications, and delete your account from inside the app.
```

### الكبتن — `ly.tajora.driver`

| الحقل | العربيّة | English |
|---|---|---|
| الاسم | TAXO كبتن | TAXO Captain |
| العنوانُ الفرعيّ | استقبل الرحلات واعمل بوقتك | Receive rides, drive your hours |
| الكلمات | كبتن,سائق,رحلات,تاكسي,دخل,عمل,سيارة,طلبات,توصيل,أرباح | driver,captain,rides,taxi,earn,work,car,requests,trips,income |
| الترويجيّ | استقبل طلبات الرحلات القريبة، ووجّه إلى الراكب، واجمع أجرتك. | Receive nearby ride requests, navigate to the rider, and collect your fare. |
| الفئة | Business (والثانية Navigation) | |

**English description**:

```
TAXO Captain is the app for TAXO drivers.

Go online when you want
Tap "Start receiving" and nearby ride requests reach you — even with another app open.
On iPhone you can accept or decline a request right from the notification.

Every trip, step by step
Navigate to the pickup, let the rider know you have arrived, and follow the route to the
destination. The trip stays on your Lock Screen and in the Dynamic Island.

Your earnings
See every trip and payment in your wallet, request a withdrawal, and review your history.

Calls and chat
Call or message the rider inside the app; on iPhone the call rings like a normal call.

Sign-up in the app
Register with your vehicle and documents; our team reviews them before you start.
```

### الصور — المقاساتُ المطلوبة (iPhone وحدَه — `TARGETED_DEVICE_FAMILY = 1`)

| الشاشة | البكسل | الحال |
|---|---|---|
| **6.9 بوصة** (iPhone 17 Pro Max) — **إلزاميّة** | 1320 × 2868 | تُلتقط في `ios.yml › smoke` على المحاكي، بالعربيّة والفرنسيّة |
| 6.5 بوصة — اختياريّةٌ إن وُجدت 6.9 | 1284 × 2778 | تُشتقّ من نفس التشغيل |
| أصغرُ iPhone (SE) — **للقياس لا للمتجر** | 750 × 1334 | المناطقُ الآمنة ولوحةُ المفاتيح |

**وصورُ المتجر من شاشاتٍ حقيقيّةٍ في وضع الضيف** — لا واجهاتٌ مولَّدة ولا تصميمٌ لم يُبنَ (قاعدةُ بطاقة Play).

### تصنيفُ العمر — أجوبةُ الاستبيان (يُجاب صدقاً، والنتيجةُ ما تحسبه Apple)

عنفٌ · محتوى جنسيّ · مقامرة · كحول · رعب: **None** · **Unrestricted Web Access: No** (لا متصفّحَ عامّ) ·
**User-Generated Content / Messaging: Yes** — دردشةُ الرحلة ومكالمتُها بين راكبٍ وكبتن.
**وقِيس ٢٠٢٦-١١-١٧**: (١) **البلاغُ عن رسالةٍ قائمٌ** — لمسةٌ مطوّلةٌ على رسالة الطرف الآخر ← سببٌ ← «أبلغ» (`CommsT2.tsx › ReportSheetT2`)،
وهو ما يطلبه **1.2** لمحتوى المستخدمين؛ (٢) **السياسةُ تقول ١٨ سنةً فما فوق** (`policy_texts_76.py`: «TAXO is for adults (18 and over)») —
فيُجاب «Age Assurance» بذلك إن ظهر.

### الدعمُ والروابط

| | |
|---|---|
| Support URL | `https://taxo.tajora.ly` |
| Marketing URL | `https://taxo.tajora.ly` |
| Privacy Policy | الراكب `/privacy-en` · الكبتن `/driver-privacy-en` |
| Copyright | `2026 Mohammad Alsaidat` |
| رابطُ iOS في taxo.tajora.ly | **بعد قبول Apple وحدَه** — ويرفعه الوكيلُ الرئيسيّ |

---

## ٨) قبلَ الإرسال — كلُّها خضراء أو لا إرسال

1. `ios.yml` أخضر: بناءُ الأربع، والإقلاعُ على أصغر iPhone وأكبره بالعربيّة والفرنسيّة.
2. حسابُ Apple، ومفتاحُ APNs في Firebase، و`GoogleService-Info.plist` للتطبيقين (لا إشعاراتَ بدونه — والبناءُ يعمل بدونه).
3. **TestFlight على iPhone حقيقيّ** — قائمةُ المالك في `HANDOFF.md` «iOS» (١٠ بنود، ربعُ ساعة).
4. رمزُ Mapbox لـiOS (الخريطةُ في WebView تقرأ رمزَ الويب نفسَه — **يُقاس على TestFlight**؛ رمزٌ مقيَّدٌ بنطاقٍ قد لا يقبل `capacitor://localhost`).
5. حسابُ المراجِع في `apple-review.txt`.
6. الأيقونة: مجموعةُ الوكيل الرئيسيّ **icons_v2 (C)** بعد اعتمادها — **لا أصمّم مجموعةً ثانية**؛ وإلى ذلك تبقى الأيقونةُ الحاليّة.
