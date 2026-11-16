# أمرُ المالك ٢٠٢٦-١١-١٧ — «شغّل ليبيا» + الأيقونات بالنمط C + إضافتا Dpay (النصُّ كما قاله)

> **كُتب لحظةَ وروده** (قاعدةُ «ما لم يُكتب في ملفٍّ لم يحدث»). وصل والجلسةُ عند حدِّها، فلم يُنفَّذ منه شيءٌ بعد — **يُنفَّذ أوّلَ الجلسة القادمة**.
>
> **ملاحظاتُ القارئ (لا تغيّر النصّ):**
> - **«أمرُ Dpay» الأصليّ لا يوجد في أيّ ملفٍّ في المستودع.** هذه إضافتان إليه فقط، فيُبحث عن نصّه في نصوص الجلسات قبل التنفيذ. وإن لم يوجد يُكتب منه ما يُعرف.
> - **«لا تتواصل مع أيّ مزوّد دفع»** في شروط المهمّة ١ تعارض **«اسأل Dpay مباشرةً»** في الإضافة ٢. والإضافةُ تصرّح بأن شروطها «شروطُ أمر Dpay» لا شروطُ المهمّة ١. **فالقراءةُ المرجّحة**: مراسلةُ Dpay بشأن الأردن وشروط التاجر مأذونة، ولا مزوّدَ غيرُه. ولا تُطلب كلمةُ مرور، ولا يُفتح حساب، ولا يُدفع شيء.
> - **الافتتاح ليس قبل ٠٩:٠٠ بتوقيت ليبيا (UTC+2)** يوم ١٧ نوفمبر.
> - **«لا تنسب جنسيّةً إلى المالك»** شرطٌ دائم.

---

## TASK 1: Prepare Libya completely and OPEN it (first priority)

Owner decision, 2026-11-17: I say it now, «شغّل ليبيا». Prepare Libya fully, test it, and open it to the public yourself. Do not wait for another word from me.

1. Readiness check on production, item by item, for the Libya market (LY). For each: ready / fixed now / blocked, with proof:
   - sign-up and login with +218 numbers, and the verification code arriving on a real Libyan number;
   - the country switch, flag and borders setting for Libya in the panel;
   - currency and number format (د.ل, Latin digits), Arabic texts, and time zone;
   - ride categories and fares for Libya: check that they exist and are complete. Do NOT invent or change any price;
   - commission and subscription settings for Libya: check that they exist. Do not change them;
   - payment methods for Libya, per my provider-as-data pattern (cash, bank transfer with receipt, local card, wallets), wallet top-up, driver payout and withdrawal: each one working or clearly OFF;
   - driver onboarding: documents, review, approval, and the panel screens for the Libya reviewer;
   - the open-source place search for Libya with Mapbox fallback, and places_search_v2;
   - the new rider order sheet, the night map and the small ⓘ map attribution;
   - TAXO cards for Libya (money parts stay as I set them);
   - notifications, in-app chat and calls, ride sharing and the emergency button;
   - privacy policy and terms pages covering Libya;
   - support contact shown to Libyan users;
   - the finance pages in the panel for Libya («مالية الدولة»);
   - Google Play and the download page: are both apps available to users in Libya?
2. Turn ON for Libya every feature switch that is ON in Jordan and Algeria, so the three markets match. List every switch you changed, with the value before and after.
3. Full rehearsal on production with test accounts, while Libya is still hidden: a rider in Tripoli requests a ride, a driver accepts, the ride starts and ends; pay in cash and by wallet; a wallet top-up; a driver payout request; a cancelled ride; a search for 10 well-known places in Tripoli, Benghazi and Misrata. Check the ledger entries of every step are correct. Then clean up the test data the proper way, without deleting ledger rows.
4. Check the server can take the launch: memory, CPU and disk now, the search container limits, today's backup, and the alert that reaches me if the server goes down.
5. Prepare the launch switch as ONE action, and write its exact steps and its rollback steps in HANDOFF.md.
6. OPEN LIBYA yourself when all of these are true:
   - every item in step 1 is ready, or is a feature that is clearly OFF and not needed for a ride;
   - the rehearsal in step 3 passed and the ledger is correct;
   - fares, categories and at least one working payment method exist for Libya;
   - the server check in step 4 is fine;
   - a fresh backup and the money-table fingerprints were taken just before.
   Open it in the morning, not before 09:00 Libya time on 17 November, so I am awake for the first hours.
7. Do NOT open Libya if a launch blocker remains: no fares or categories, the verification code not arriving on Libyan numbers, no working payment method, a wrong ledger entry in the rehearsal, or a failing deploy gate. In that case send me one short message at once with the blocker and what you need, fix what you can yourself, and open as soon as it is solved.
8. Right after opening: remove «قريباً» for Libya everywhere (apps, sign-up, website), take the money-table fingerprints again, run one real check ride flow, and watch production closely for the first 2 hours. If something serious breaks (rides failing, wrong money entries, the server overloaded), close Libya again with the rollback steps and tell me at once.
9. Send me one message when Libya is open (allowed before the end): the time it opened, the readiness list, every switch changed, the rehearsal result, and anything that still needs my decision.

## TASK 2: Icons (continue in parallel, do not delay Task 1)

Owner choice: icon style C (bold duotone) from the 4-direction board, as the base color and fill style only. Redesign ALL the icons in it, including the vehicles, so every icon looks modern, current and beautiful. The C board shapes still look old; keep the C colors and fill, but make new, modern shapes.

1. Vehicles: redesign every vehicle icon as a modern, beautiful car. The current C cars are boxy front views and look old.
   - Modern car shapes in the spirit of 2026 cars: sleek, low, smooth curved lines, slim LED headlights and tail lights, modern wheels.
   - Use a side or three-quarter view.
   - Each category clearly different at a glance: «اقتصادي» a compact modern hatchback or small sedan with a small taxi sign; «مريح» a premium modern sedan, longer and more elegant; every other category in the system its own modern vehicle.
   - Use the new vehicles everywhere a car appears: the category list, the order sheet, the driver marker on the map, ride status screens, and the driver app.
   - The car marker on the map must turn smoothly with the road direction.
2. All other icons: redesign every one with modern, beautiful shapes, not only recolored: wallet, location pin, search, notifications, «خيارات», the online/offline switch, the bottom bar, payment methods, cards, settings, profile, documents, support, share, emergency, success and error states, and empty states.
   - Modern style in the spirit of the best 2026 apps: clean geometry, soft rounded corners, generous inner space, balanced proportions, small refined details, and a subtle depth from the second tone.
   - Simple and instantly understood. No old-fashioned shapes.
   - One consistent family: same grid, same corner radius, same weight, same light direction.
   - Crisp at small sizes, and correct in light and dark mode.
   - Original designs only. Do not copy any app or car brand.
3. Animations: short and smooth on tap, selection and state change; the selected car gently drives in or its wheels turn once; a celebration when a ride ends or a payment succeeds; static icons on slow phones or with «reduce motion» on; taps never wait for an animation.
4. Apply the new set to the rider app, the driver app and the panel, behind the icons_v2 switch, for Jordan, Algeria and Libya.
5. Send me one board image with the final full set (vehicles first, then all icons), old vs new, in light and dark mode, and one short recording. Keep icons_v2 OFF until I approve the board.

AFTER BOTH: continue the rest of my last command (gate 6 fix, the Algiers airport search case, Android stages A, B and C, the panel additions), and send ONE final report at the end.

Conditions:
- Do not create or change any price, fare, commission, subscription price or card value. If one is missing for Libya, that is a launch blocker: tell me and wait for that value only.
- No money-table change without telling me first. Stop on any unplanned money-guard or fingerprint change. Test rides must leave the ledger correct.
- Any deploy goes through all gates, with backup and money-table fingerprints before and after. Never skip or override a gate.
- Do not attribute any nationality to the owner.
- Tests run split on GitHub; do not run the full test run locally. Check the heavy lock is free before any heavy local step.
- Do not contact any payment provider. Never type my passwords; identity, bank and payment steps are mine.
- Google Maps stays OFF.
- Secrets only in C:\Users\loly3\.taxo-secrets\ and the panel's encrypted storage.

## Dpay — more information and two additions to the Dpay command

Owner information:
- Dpay gathers all the Libyan payment methods from the different banks in one place.
- Dpay can also accept international Mastercard and Visa cards in US dollars. So we may be able to use it for Jordan too.

ADDITION 1: Libya, all methods through Dpay
1. List every payment method Dpay offers in Libya: each bank's cards and services, wallets, pay-by-phone-number, purchase codes, and any other. For each: how the payer pays, fees, limits, and settlement time.
2. Build Dpay as ONE integration that offers all of these methods. The methods come from Dpay's data, not from fixed names in our code, so a new bank or method appears without new code.
3. In the panel, per method: a switch, the display order, and the Arabic name and instructions.
4. Compare with the Libyan payment methods we already built by hand. Tell me which ones Dpay replaces and which ones should stay. Do not remove anything; just report.

ADDITION 2: Jordan, international cards in USD through Dpay
5. Find out from Dpay's documentation, and ask Dpay directly in the same message as the merchant requirements:
   - Does Dpay allow a merchant in Libya to accept payments from customers outside Libya, for example drivers in Jordan?
   - Which international cards are accepted (Visa, Mastercard), with 3-D Secure, and from which countries?
   - In which currency is the payer charged, and in which currency does the merchant receive the money: does it stay in USD, or is it converted to Libyan dinar, and at which exchange rate?
   - To which account is it paid, and can a USD balance be kept or transferred abroad?
   - The fees for international cards, any monthly fee, and the minimum payment.
   - Are recurring monthly charges supported, or does the payer pay each month himself?
   - How does the charge appear on the payer's bank statement (merchant name and country)?
6. Check our side too: a driver in Jordan paying a monthly driver subscription priced in JOD, charged in USD. Show the price in JOD with the USD amount clearly, before he pays. Use one exchange-rate source set from the panel, never a number fixed in code.
7. Build it as an option, OFF: «الدفع بالبطاقة» for Jordan driver subscriptions through Dpay international cards, with its own panel switch for Jordan. Driver subscriptions only for now.
8. Do NOT turn it ON for Jordan until: Dpay confirms in writing that cross-border payments are allowed, the settlement currency and rate are known, the merchant account is live, one real test payment from a Jordanian card succeeds, and I approve.
9. Put all the answers in DPAY-REQUIREMENTS.md in Arabic, with a clear section «Dpay للأردن»: allowed or not, the fees, the settlement currency and rate, and your recommendation.

Conditions: the same as the Dpay command.
- Truthful only. When asking Dpay about Jordan, say plainly that TAXO also has drivers in Jordan and we want them to pay subscriptions by international card.
- Do not change any price or subscription amount.
- No card data on our servers. Live keys only in C:\Users\loly3\.taxo-secrets\ and the panel's encrypted storage.
- Dpay does not delay the Libya launch.
