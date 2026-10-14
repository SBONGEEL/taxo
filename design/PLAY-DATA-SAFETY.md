# أجوبةُ Play Console — «أمان البيانات» وإقراراتُ الأذونات (SPEC §٧٦/٣)

**للمالك يملؤها بنفسه** — لا يُغيَّر شيءٌ في Play Console من جهتي (شرطُ §٧٦-أ). **والأجوبةُ بالإنجليزيّة لأن النموذجَ إنجليزيّ**، وكلُّ جوابٍ
**يطابق سياسةَ الخصوصية المنشورة لفظاً** (`backend/scripts/policy_texts_76.py` — الإنجليزيّةُ منها هي ما يقرؤه المراجع). **ولا يُذكر بلدٌ في
أيِّ جواب** (أمرُ المالك ٢٠٢٦-١٠-١٤ عن وصف المتجر — والنموذجُ لا يسأل عن البلد أصلاً).

**روابطُ السياسة لكلِّ تطبيق** (حقلُ «Privacy policy» في Play Console — **لا تغيّرها إن كانت هذه نفسَها**):
- الراكب: `https://taxo.tajora.ly/privacy` — والإنجليزيّة: `https://taxo.tajora.ly/privacy-en`
- الكبتن: `https://taxo.tajora.ly/driver-privacy` — والإنجليزيّة: `https://taxo.tajora.ly/driver-privacy-en`
- رابطُ حذف الحساب (للتطبيقين): `https://taxo.tajora.ly/delete-account` — والإنجليزيّة: `https://taxo.tajora.ly/delete-account-en`

> **مصطلحُ Google**: ما يُرسَل إلى **مزوّد خدمةٍ يعالج نيابةً عنّا** (Mapbox · Firebase Cloud Messaging · WhatsApp · Cloudflare · Contabo ·
> Chargily) **ليس «مشاركة» (sharing)** في تعريف Google — ولذلك جوابُ المشاركة «لا» في كلِّ صنف. والإفصاحُ للسلطات بأمرٍ قانونيٍّ مستثنى كذلك.

---

## 1) Data collection and security (the first page)

| Question | Rider app (ly.tajora.rider) | Captain app (ly.tajora.driver) |
|---|---|---|
| Does your app collect or share any of the required user data types? | **Yes** | **Yes** |
| Is all of the user data collected by your app encrypted in transit? | **Yes** (HTTPS/TLS) | **Yes** (HTTPS/TLS) |
| Which of the following methods of account creation does your app support? | **Username and password** (the username is the phone number) — and the app **allows users to create an account** | same |
| Delete account URL | `https://taxo.tajora.ly/delete-account` | same |
| Do you provide a way for users to request that some or all of their data is deleted, without requiring them to delete their account? | **Yes** — by email to privacy@tajora.ly, and in-app (profile photo, saved places) | **Yes** — same |
| Has your app undergone an independent security review (MASA)? | **No** | **No** |

## 2) Data types — Rider app

For every row: **Shared = No** (only service providers acting on our behalf). "Ephemeral" = No unless stated.

| Data type | Collected | Required / Optional | Purposes |
|---|---|---|---|
| **Location → Precise location** | Yes | Required | App functionality; Fraud prevention, security, and compliance |
| **Location → Approximate location** | Yes | Required | App functionality |
| **Personal info → Name** | Yes | Required | App functionality; Account management |
| **Personal info → Email address** | Yes | **Optional** | Account management |
| **Personal info → Phone number** | Yes | Required | Account management; App functionality; Fraud prevention, security, and compliance |
| **Personal info → User IDs** | Yes | Required | Account management |
| **Personal info → Other info** (declared gender — women-only service) | Yes | **Optional** | App functionality |
| **Financial info → Purchase history** (rides paid, wallet top-ups, subscriptions) | Yes | Required | App functionality; Account management; Fraud prevention, security, and compliance |
| **Financial info → Other financial info** (wallet ledger, transfer references, uploaded payment receipts) | Yes | **Optional** | App functionality; Fraud prevention, security, and compliance |
| **Messages → Other in-app messages** (trip chat, where available) | Yes | **Optional** | App functionality; Fraud prevention, security, and compliance |
| **Audio → Voice or sound recordings** (recorded in-app calls, only after a notice both parties acknowledge) | Yes | **Optional** | Fraud prevention, security, and compliance |
| **Photos and videos → Photos** (profile photo, feedback screenshot, payment receipt — all chosen by the user) | Yes | **Optional** | App functionality |
| **App activity → Other user-generated content** (ratings and comments, "Send feedback" text) | Yes | **Optional** | App functionality |
| **App info and performance → Crash logs** | Yes | **Optional** (can be turned off in Settings) | App functionality (fixing crashes) |
| **App info and performance → Diagnostics** (app version, OS type, screen without identifiers) | Yes | **Optional** | App functionality |
| **Device or other IDs** (notification token, random app identifier) | Yes | Required | App functionality |

**Not collected**: Contacts · Calendar · Health and fitness · Web browsing · Files and docs · Videos · Music · Payment info (card numbers are entered on the payment provider's page, never in TAXO) · Race/ethnicity · Political or religious beliefs · Sexual orientation · Credit score · Installed apps · Search history.

## 3) Data types — Captain app

Everything in the rider table, **plus**:

| Data type | Collected | Required / Optional | Purposes |
|---|---|---|---|
| **Location → Precise location** — **including in the background while online** | Yes | Required | App functionality; Fraud prevention, security, and compliance |
| **Photos and videos → Photos** (personal photo, vehicle front/back/plate) | Yes | **Required** | App functionality; Fraud prevention, security, and compliance |
| **Files and docs** (driving licence, identity document, vehicle registration — image or PDF) | Yes | **Required** | App functionality; Fraud prevention, security, and compliance |
| **Personal info → Other info** (vehicle details; gender confirmed by staff for the women-only service) | Yes | Required (vehicle) / Optional (gender) | App functionality |
| **Financial info → Other financial info** (earnings, commissions, subscriptions, advances, payout account entered for withdrawals) | Yes | Required | App functionality; Account management; Fraud prevention, security, and compliance |

(For the captain app, **Purchase history** = subscription purchases.)

## 4) Background location declaration (Captain app only)

Play Console → App content → **Sensitive app permissions → Location permissions**.

- **Does your app access location in the background?** Yes.
- **Which feature uses background location?** *Receiving nearby ride requests while online.*
- **Describe the feature** (paste as is):
  > TAXO Captain is a ride-hailing app for drivers ("captains"). When the captain taps "Start receiving" (ابدأ الاستقبال), the app starts a foreground service with a persistent notification "Online — receiving requests" (متصل — تستقبل الطلبات) and sends the captain's current location about every 20 seconds, even when the app is in the background or the screen is off, so that the nearest ride request reaches the captain while they drive with the phone in their pocket or on a navigation app. Location is also used to show the captain's approach to the rider who booked, and to calculate the actual distance and fare of the trip. Location is collected only while the captain is online; it stops when the captain taps "Stop receiving" (إيقاف الاستقبال) or removes the app from recent apps. It is never collected while the captain is offline, never sold, and never used for advertising.
- **Why is background access necessary?** Without it, a captain who switches to a navigation app or turns off the screen drops out of dispatch within about 30 seconds and stops receiving ride requests.
- **Prominent disclosure**: a full screen shown before Android's settings page (`driver-app/src/lib/permission-walk.ts`, `BACKGROUND_STEP`): «TAXO يحتاج موقعك طوال الوقت» — "TAXO needs your location all the time: when you tap «استقبال», TAXO sends your location to our server with the screen off — so the nearest request is offered to you and your rider sees your car on the map until the end of the ride. It stops as soon as you tap «إيقاف الاستقبال»." — then the button «افتح الإعدادات واختر «السماح طوال الوقت»». The persistent notification is always visible while online.
- **Video** (required by Google — **the owner records it**, 30–60 s, on a phone):
  1. Open TAXO Captain → the screen «TAXO يحتاج موقعك طوال الوقت» appears → tap «افتح الإعدادات واختر «السماح طوال الوقت»» → in Android settings choose "Allow all the time".
  2. Tap «ابدأ الاستقبال» — show the notification «متصل — تستقبل الطلبات» appearing in the status bar.
  3. Press Home, open Google Maps (navigation) — a test ride request arrives on top while the app is in the background.
  4. Return to TAXO Captain, tap «إيقاف الاستقبال» — show the notification disappearing.

## 5) Foreground service declaration (Captain app — Android 14)

Play Console → App content → **Foreground service permissions**.
- Permission: `FOREGROUND_SERVICE_LOCATION` — type **location**.
- Task: *Keeps the captain's location updates and ride-request connection alive while the captain is online.*
- User-initiated: **Yes** — starts only when the captain taps «ابدأ الاستقبال», stops when they go offline. A persistent notification is shown the whole time.
- Impact if deferred or interrupted: the captain stops receiving ride requests and riders cannot see the captain approach.
- Video: the same video as section 4.

## 6) Full-screen intent declaration (both apps — Android 14)

Play Console → App content → **Full-screen intent permission**.
- Rider app: **Calling** — incoming in-app call from the assigned captain (where in-app calls are available).
- Captain app: **Calling** — incoming in-app calls from the rider; and the incoming **ride request** alert, which must be answered within seconds while the phone is locked.

## 7) Other permissions (no declaration form, listed for consistency with the policy)

| Permission | App | Why (as in the policy) |
|---|---|---|
| `RECORD_AUDIO`, `MODIFY_AUDIO_SETTINGS` | both | In-app calls only |
| `POST_NOTIFICATIONS` | both | Ride, wallet and request notifications |
| `SYSTEM_ALERT_WINDOW` | captain | Show an incoming request over a navigation app |
| `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` | captain | Keep the connection alive while online |
| `ACCESS_COARSE_LOCATION` / `ACCESS_FINE_LOCATION` | both | Map, pickup point, dispatch |
| `ACCESS_BACKGROUND_LOCATION` | captain | Section 4 |

---

**ومن أين كلُّ جوابٍ في الشيفرة** (للمراجعة لا للنسخ): الأذوناتُ من `AndroidManifest.xml` للتطبيقين · خدمةُ الموقع من
`driver-app/android/.../OnlineService.java` (`BROADCAST_MS = 20_000`، `foregroundServiceType="location"`، `onTaskRemoved` يوقفها) ·
المزوّدون المفعَّلون من `provider_credentials` على الإنتاج (Mapbox · FCM · WhatsApp · Chargily للجزائر؛ Telr وSMS والبريدُ مطفأة) · تقاريرُ
الأعطال ومفتاحُها من `lib/crash-reports.ts` · ملاحظاتُ المستخدم من `services/feedback.py`.
