# قراراتُ المالك على التقرير ٢ — ٢٠٢٦-١١-١٦ (نصُّه كما وصل، يُقرأ قبل أيِّ عملٍ في الورقة أو الخريطة أو الأيقونات)

> لاحقٌ بأوامر ١٦/١١ الثلاثة (§١٠٢، §١٠٣، §١٠٤) ولا يلغي شيئاً منها. ملخّصُه في SPEC §١٠٥.

Owner decisions on report 2, 2026-11-16:

1. Rider order sheet: approved. After the deploy, turn it ON in Jordan and Algeria.
2. Long sheet with an extra stop: fix it.
   - Shorten the stop explanation to one line.
   - Make the balance note and the top-up button one small compact line.
   - Make the sheet draggable with a finger, with two heights: half screen and full screen. It opens at half, so the map and the route stay visible.
   - Nothing is removed; everything stays reachable.

3. BUG: night mode on the map is broken. When the app is in night (dark) mode:
   - the map stays a daytime map instead of turning into a night map;
   - and some text turns black only, so it cannot be read on the dark screen, while the map stays light.
   Fix it everywhere a map appears (rider app, driver app, panel; current map and the new MapLibre map):
   - Add a real night map style that matches the TAXO dark theme: dark roads, dark land, readable water and parks, and the route line still bright and clear.
   - The map follows the app theme automatically: day map in light mode, night map in dark mode, and it switches at once when the theme changes, without reloading the screen.
   - Map labels (streets, districts, landmarks) in Arabic stay readable in both modes: light text with a dark outline at night, dark text with a light outline by day.
   - All text and icons on top of the map (search box, order sheet, buttons, markers, chips, the ETA and price labels) use the theme colors, never a fixed black or white. Check every screen in both modes and fix any text that is hard to read.
   - Feature 16 (automatic night driving mode) must use this same night map.
   - Add a test that renders each map screen in light and dark mode and fails if text contrast is too low.
   - Send me screenshots of Amman and Algiers, day and night, on the home screen, the order sheet and the driver's ride screen.

4. NEW: a complete new icon set, modern, beautiful and fresh, and brought to life with animation. Rider app, driver app and panel.

   A. New modern icons:
   - Redesign ALL icons in the three apps as one new, modern, original icon set for TAXO. Replace the old icons everywhere: category icons (economy, comfort, etc.), bottom bar, «خيارات», payment methods, wallet, notifications, search result types, settings, profile, documents, cards, the online/offline switch, success and error states, and empty states.
   - Modern style in the spirit of 2026 apps: clean, soft rounded shapes, balanced weight, a light two-tone or gradient touch in the TAXO brand colors, and clear at small sizes.
   - One consistent family: same line weight, same corner radius, same grid, same colors. It must look like one designer made every icon.
   - Category vehicles as attractive, modern car illustrations, each one clearly different.
   - Original designs only. Do not copy icons from other apps or brands.
   - Sharp vector format (SVG) that looks crisp on every screen, and correct in both light and dark mode.

   B. Bring them to life:
   - A short, smooth animation on tap, on selection and on a state change.
   - A gentle idle motion only on the one element that needs attention (for example the car on the selected category, or «ابحث عن كابتن» while searching).
   - A celebration animation when the ride ends or a payment succeeds.
   - Use a lightweight animation format (for example Lottie or Rive, or CSS/SVG animation). Choose it yourself. Keep each file small.

   C. Performance and control:
   - Smooth on weak phones: no frame drops on Note 20. If the phone is slow or «reduce motion» is on, show the static icon instead.
   - Animations never delay a button or a request. The tap works at once; the animation only decorates it.
   - Behind a panel switch, per country, so I can return to the old icons from the panel at any time.

   D. Approval:
   - Send me one board image with the full new icon set (old vs new side by side, in light and dark mode), and a short screen recording of the rider and driver apps, before and after.
   - After my approval, turn it ON.

5. Then deploy everything together through all five gates, with backup and money-table fingerprints before and after:
   - the search fix;
   - «وجهتي»;
   - the order sheet with the draggable change;
   - the night-map fix (ON right after the deploy, because it is a bug fix);
   - the new animated icons (OFF until I approve the board and the recording).
   Tie the new map to the app build number from the app-versions panel, as you planned.

6. Then continue as planned: the search rebuild (the follow-up command), stage A of the Android features, then the panel item 4. Do not stop until all are finished.

Conditions:
- No change to fares, routes or pricing. No money-table change. Stop on any unplanned money-guard or fingerprint change.
- Never skip or override a deploy gate.
- Tests run split on GitHub; do not run the full test run locally. Check the heavy lock is free before any heavy local step.
- Google Maps stays OFF. Libya stays hidden «قريباً».
- Secrets only in C:\Users\loly3\.taxo-secrets\ and the panel's encrypted storage.

Map attribution: hide the big white bar «MapLibre | OpenFreeMap © OpenStreetMap ⓘ» from the map in the rider app, the driver app and the panel.

- Replace it with only a small ⓘ button in a map corner: small, semi-transparent, in the theme colors (dark at night, light by day).
- Collapsed by default. The full text appears only when the user taps ⓘ, and collapses again on the next tap or after a few seconds.
- It must never sit on top of the route, the markers or the order sheet.
- Put the full credits on an «حول التطبيق / التراخيص» page in both apps.
- Do not remove the attribution completely: the OpenStreetMap and OpenFreeMap licenses require it. Check their current attribution rules and follow them exactly.
- Send me a screenshot of the same Amman route, day and night, after the change.
- Deploy it with the next deploy, through all five gates.

Conditions: no change to fares, routes, pricing or money tables. Never skip a deploy gate.

«واكمل بدون توقف»
