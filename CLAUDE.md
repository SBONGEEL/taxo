# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Where the project stands

TAXO is a two-country (Jordan/Libya) ride-hailing platform: a FastAPI backend, two rider/driver
PWAs, and an operations panel. `SPEC.md` §16 is a strict ordered plan; this is where it has got to.

**Done — stages 1 through 11, plus 10-ج, and every part of stage 12 except ride sharing.**
Infrastructure and auth; per-country settings and encrypted provider contracts; rides and Mapbox
pricing; Redis-GEO dispatch and the tracking sockets; the wallet ledger; payments, route points and
ratings (6-أ); the Telr card channel (6-ب); driver subscriptions (7); the provider integrations and
campaigns (8); the rider PWA (9); document upload/review and the notification inbox (9-ب); the driver
PWA (10); the women's transport service end to end (10-ج); and **the admin panel (11), complete** —
login, overview, live map, rides log, drivers/documents, riders, disputes, finance,
subscriptions/plans, pricing, reports, campaigns, per-country settings, provider contracts, users &
permissions, audit log. Every nav entry has a screen.

**Stage 12, item by item**: 12-أ the rider app's migration onto the design system · 12-ب multi-stop ·
12-ج the `FUTURE-FEATURES` bundles sitting on 12-ب (saved places / recent destinations / re-order =
items 1–3; the driver's earnings summary = 17; the dispute badge in both ride logs = 19; vehicle
editing and the CliQ alias = 43/18) ·
12-د two-factor login for the panel · 12-هـ WhatsApp as a third phone verifier · 12-و tipping ·
12-ز coupons · 12-ح the female-driver referral incentive · 12-ط scheduled rides · plus the two
maintenance jobs. **12-ي — ride sharing — is built end to end** (`SPEC.md` §5.12): the seat-based
indexes and their concurrency tests, the geographic matching, dispatch integration, the panel's four
numbers and both PWAs — all opened in a browser. **Surge the owner decided not to build** (with no
real demand data it would be tuned wrong and turn riders away), so **stage 12 is closed and stage 13
is next**. One money question inside sharing stays open by his decision: whether the company bears the
remaining rider's difference **before** departure.

**762 backend tests pass** across 71 test files — measured, not estimated, on 2026-08-15. All three
frontends build with `check:scale`, `check:enums`, `check:config` and (in the panel) `check:flags`
green.

**`check:config` covers `GET /config` *and the auth responses*, and it closes the «field with no mirror» debt** — the shape
where a backend field is published, arrives on every call, and is discarded because the TypeScript type
never mirrored it (`quiet_hours_*` did exactly that from stage 8 to 12-هـ). It compares
`CountryConfigOut` and `ConfigOut` in `backend/app/schemas/config.py` against `CountryConfig` and
`AppConfig` in each app's `api/types.ts`, **in both directions and by field name only**: a missing
mirror is data thrown away, and an extra one is a type promising a value that reads `undefined` at
runtime — the `awaiting_confirmation` shape. Types are deliberately not compared: `providers` is an
open dict each app narrows to what it reads, and `auth` is inline in the panel and named in the two
PWAs. It sits in **all three** apps because all three call `GET /config`. Verified by reproducing both
directions and both models before being trusted.

**And widened again in 12-ي to `RideEstimateOut`** — the first watched pair that is neither config nor
auth, added the moment the estimate started carrying **money** (`share_discount`/`share_fare`,
computed in the backend per §14). It is the same shape as the rest: a field the backend publishes and
the app types by hand, whose silent absence draws a "share and save" row with no number. Not
`required`, since only the rider app estimates a fare. Verified by deleting `share_fare` from the
mirror and watching it fail.

**It was widened to the auth responses after `LoginResponse` shipped unmirrored** in both PWAs: the
backend answers `POST /auth/login` with `{totp_required, user: null, tokens: null}` when a second factor
is due, while both apps typed it as `AuthResponse` with non-nullable tokens — so `tokens.save(undefined)`
was one confirmed factor away. Latent (only `admin`/`support` can enroll, via `SecuritySelfUser`) but
the guard is on the **account**, not the role. Widening it then found two more dormant lies in the same
pass: `TokenPair.expires_in` in the driver app and the panel (the backend sends `expires_at`, so the
first proactive-refresh feature would have read `undefined`) and a missing `ChallengeResponse.expires_in`.
`MIRRORS` now carries a `required` flag — `LoginResponse` is required in all three because all three
call `/auth/login`, while `ChallengeResponse` is checked only where declared (the panel has no phone
verification).

**And it immediately found a seventh flag with no button**: `scheduled_rides_enabled` (12-ط) was never
added to the panel's `FeatureKey` union or its `FLAGS` array, so the panel build was **already red** —
`check:flags` (built in 12-ح for exactly this) had been failing on master and the switch did not exist.
Fixed in the same session. The guard works; what failed was running it.

**The rider design-matching work is finished**: `customer-app` was matched to the rider prototype in
five packages the owner ordered هـ ← ج ← د ← ب ← أ, one per session, and **all five are delivered** —
see "Rider design-matching" below for what each settled. **Sharing (12-ي) followed them and is
done**, so nothing is queued before stage 13.

**Stage 13 is done** (2026-08-15): the scenario test (`tests/test_stage13_scenario.py`) **and** the full
manual run on two phones — a driver created from the app's own screens, approved, subscribed, driving a
real ride for a rider on the second phone, paid, rated, and withdrawing money the admin then transferred.
Five defects came out of it and are fixed; see "Stage 13 — the full manual run" below.

**Stage 12-ب — multi-stop — is done end to end** (SPEC §5.10 / §16): backend, both apps, and a visual pass on the running ride. Up to three
destinations per ride: two intermediate rows in `ride_stops`, the last one staying
`rides.dropoff_point` (moving it would mean either touching pricing, dispatch, the offer card, the
admin log and the socket frames, or keeping the column as a *mirror* of the last row — and a value
with two homes diverges). Waiting is three admin-managed per-country fields plus a cap, all four
**frozen on the ride** exactly like `commission_percent_at_ride`. The clock is stamped in the
backend (`ride_stops.arrived_at`/`resumed_at`, no `waited_minutes` column — two columns for one
time diverge); the app renders elapsed *time* locally and receives the *amount* computed by the
backend, because showing time is a time calculation and showing money is a money calculation.
Behind `multi_stop_enabled`, off by default, seeded explicitly, and **not** in
`DEFAULT_ENABLED_FLAGS` — that list is guards only. Turning it off hides the "add stop" button
entirely (the `women_service_enabled` rule) and blocks new requests only: rides already running
finish normally.

**`FUTURE-FEATURES` items 1–3 are built** on top of it: `saved_places` (a table, capped per user,
unique label, ownership checked on every route) with shortcuts on Home, a section in the search
sheet, and a page under the menu; recent destinations **derived from `GET /rides/me` with no table**,
folded by rounded coordinates rather than address text (the same point gets two spellings from
Geocoding) and with saved places filtered out so one sheet never lists a destination twice; and
"re-order" from a finished ride, which starts a **new request** at the same two points — the price
is recomputed, stops are not copied, and the preference is read from the profile.

**`FUTURE-FEATURES` items 17, 19 and 43/18 are built too.** Three rules in them are worth carrying
forward. **The driver's earnings screen shows three numbers, not two** (`services/earnings.py`):
what entered the wallet, what left it as commission, and **what he took in his hand** — cash and
CliQ never pass through the wallet (SPEC §9), so a statement that omits them hides half his income;
and **the net is allowed to be negative and is never clipped at zero**, because an all-cash day
under `all_rides` commission leaves commission with no earnings against it, and hiding that leaves
him watching his balance fall for no visible reason. The window is the **country's day**, and the
sums are computed in the database, like `services/stats.py`.

**`GET /rides/me` now returns `RideListItem`** — the ride plus `has_open_dispute`,
`payment_methods` and `paid_amount` — which is what the driver's «نزاع» badge reads. The summary is
a **second query over the whole page**, never a join into the first: mixed payment is two rows on
one ride (there is no unique index on `payments.ride_id`), so joining multiplies the ride and drops
part of it out of a capped page — the same reasoning as `services/ride_log.py`. `Ride` itself was
left alone: it is broadcast in every socket frame, and a payment summary is work nobody reads there.

**Editing a vehicle follows stage 9-ب's document policy, not a new one** (`services/vehicles.py`).
The vehicle registration is one of the three required documents, so changing what it attests to —
`IDENTITY_FIELDS`: plate, make, model, year, category — sends an approved driver back to
`pending_review`, while colour does not. Three details make it honest rather than merely strict: the
comparison is against what **actually changed**, not what was submitted (re-sending the same plate
is not a change); the screen states the cost **before** the save and only when the edit really
touches identity (a warning that fires on a colour correction reads as noise and then goes unread
when it matters); and the edit is refused mid-ride. **Category is not editable from the app at all**
— it decides the tariff, so it is an admin decision. The CliQ alias half of item 18 needed nothing:
`PATCH /drivers/me` and the settings field shipped in stage 10.

**Stage 12-د — two-factor login for the panel (TOTP) — is done end to end**: backend, the two-step
login screen, the «الأمان» screen (enroll → QR drawn **in the browser** → confirm → the ten recovery
codes shown once, plus the recovery proof and the enforcement switch), and the browser-side idle
timer. Three panel-side rules are worth keeping. **The idle timer measures the human, not the
network** — `lib/idle.ts` listens for pointerdown/keydown/wheel/touch and deliberately **not**
`mousemove` (a mouse nudged by a desk vibration keeps a session alive with nobody there), and it
compares a **timestamp on an interval** rather than resetting a `setTimeout`, because a laptop with
a closed lid freezes timers — it would wake with an unexpired timer and resume an hour-old session,
while a timestamp read on wake logs out immediately. Its duration comes from
`GET /auth/me/totp.session_idle_timeout_minutes`, never from a constant in the panel: a number in
the browser diverges from `security_settings` the first time it is edited, and `support` needs it
while being unable to read `GET /admin/security`. And **`totp_enrollment_required` is translated in
the HTTP client, once** — the backend guard reads the row on every request so *any* call can bounce,
and per-screen handling would paint a red error on every card instead of opening the one door;
`/security` itself is exempt from that gate, or the loop never opens. It is the first item of the owner-approved bundle
**12-د → البقشيش (13) → الكوبونات (12) → إحالة السائقات (46)**, and it is first because it is the
only one of the four that touches neither `pricing`, nor `payments`, nor the ledger: the money doors
the other three open are all fields written by whoever got into the panel. SPEC §14.1 has the rules;
three are worth knowing before touching it. **The secret is encrypted and the recovery codes are
hashed** — verification *reads* the first (we regenerate the code from it) and *compares* the
second; and the hash is HMAC-SHA256, not bcrypt, because high-entropy codes buy nothing from a slow
KDF while a deterministic digest allows an indexed single-row lookup — which is what lets the lock
sit on **one** row instead of ten. **`security_settings` is a global single-row table**, the one
settings table in the project that is not per-country: a staff account belongs to one country while
the panel serves both, so enforcement read from the account's country would be dodged by an account
whose country is the other one. And **its default is `false`, which does not contradict
`DEFAULT_ENABLED_FLAGS`**: that rule covers flags where silence switches a protection *off*, and
here silence would switch a lock *on* over a door with no key — a missing row read as "required"
locks every admin out with no way back in from inside.

Two more, both learned by running it. **`last_step` is written under the row lock** (a code accepted
once is never accepted again), which means **the confirm step burns its own step** — so the first
login right after enrolling must use the next code, and that is why confirming does **not** revoke
sessions while disabling does: the access token cannot be revoked before it expires anyway, so
revoking on confirm only kills the refresh (a silent logout fifteen minutes later) and lands the
user on a burned code. And `tests/test_admin_totp.py::test_the_codes_match_the_rfc_6238_vectors` is
the only test in that file whose data comes from outside this codebase — every other one generates
the code with `code_at` and verifies it with `match_step`, so a wrong HOTP truncation would have
both sides agreeing on the same error and nobody able to log in with Google Authenticator. That is
literally the `awaiting_confirmation` failure shape.

**Stage 12-هـ — WhatsApp as a third phone verifier — is done end to end**: `services/whatsapp/`
(base + `cloud_api.py` as the only file that knows Meta's wire format + mock + a single decision
point), migration `0021` for the `ProviderKey` value, the per-country `whatsapp_otp_enabled` flag
seeded explicitly off, the flag's switch in the panel's settings screen, and the channel label plus
the fallback button in both PWAs. Its rules are in the architecture notes below. **Adding an enum
value needs the running backend recreated, not just migrated** — asyncpg caches the type per
connection, so `alembic upgrade head` alone leaves the live container answering
`invalid input value for enum provider_key`. This is the same cache trap `test_migrations` handles
with `engine.dispose()`; on the dev stack it is `docker compose restart backend`.

**Stage 12-و — tipping — is done end to end** (`SPEC.md` §6.5, the `tips` table and three
`payment_settings` fields in §4, `services/tips.py`, the rating-screen buttons, the earnings line, and
the panel's amount fields). The owner settled the money questions — the rider funds it, the driver
keeps all of it with no commission — and approved narrowing his own answer once he saw the number:
**wallet only, no card**, because a card tip of half a dinar costs more in gateway fees than it
collects. Four rules are worth defending in review.

**A tip is never a `payments` row** — "don't pay the ride twice" is the sum of
`OWING_PAYMENT_STATUSES` against `final_fare`, so a tip row there makes a fully-paid ride look
overpaid, or an unconfirmed tip look like a debt. **The ≥4-stars rule is a UI narrowing, not a backend
constraint** (the women's-service distinction): someone who rated 3 and wants to thank the driver for
carrying a suitcase is not refused by a rule that exists only to avoid asking at a bad moment, and
money must not follow a rating that can be edited — `test_a_low_rating_does_not_block_a_tip` is what
stops a later "completion" from adding it. The tip is **the driver's only income with no commission
against it**, so it gets its own line in his earnings screen; an amount that raises "what entered the
wallet" without raising "what left as commission" makes the two numbers stop reconciling for anyone
who adds them by hand. And **the table has no `status` and no `method` column** — a simplification
found while building: the wallet settles in the same transaction, so a failed debit rolls the whole
row back and `failed` could never be written. A value that can never be written is exactly
`awaiting_confirmation`; the row's existence *is* the money having moved, as with
`driver_subscriptions`. When card arrives, `method` arrives with it defaulting to `wallet`.

**The tip concurrency test taught something about which lock owns what.** Deleting *either* the
advisory lock in `wallet.record` or the sorted pre-lock in `tips.create` leaves both tests passing —
each serialises on its own. Deleting **both** turns two 1.500 tips on a 2.000 balance into
`[201, 201]`: money from nothing. So what the sorted pre-lock owns is **lock ordering** (deadlock
avoidance), not the double read — the same shape as the driver-row lock being redundant on the wallet
subscription path and the only guard on the manual one. Verify a lock by deleting it, and if nothing
fails, look for the other lock before believing the test.

**Stage 12-ز — coupons — is done end to end** (`SPEC.md` §6.6, `promo_codes` + four frozen ride
columns in §4, `services/promo.py`, the rider's coupon sheet, the receipt line, and the panel's codes
table). **The decision the whole feature turns on came from reading the code, not from taste**:
`ride_earning` and `commission` are both computed from `payment.amount` in `payments.settle`, so a
discount that reduced `final_fare` would reduce what the *driver* earns — and the owner decided the
*company* bears it. So the discount is **a second payment row with method `promo`**, created and
auto-confirmed by the platform at completion; the mixed-payment machinery from 6-أ then does all the
arithmetic with no new money rule. `promo` sits in **neither** method tuple — like card: not in
`DIRECTLY_COLLECTED_METHODS` so the driver is credited, not in `WALLET_FUNDED_METHODS` so **the rider
is never debited** (putting it there would make the rider pay their own coupon, which
`test_the_riders_wallet_is_never_touched_by_the_discount` now prevents). A side effect worth knowing:
"first ride free" needs no special case — a full discount makes `outstanding` zero and
`create_payment` refuses on its own, so no second door writes money at completion.

**Three columns deliberately absent**, each from an earlier lesson: no `budget_spent` (the spend is
the sum of `promo` payments — the "no balance column" rule), no redemptions table (the ride carries
the code, the payment carries the amount), and no `bearer` (one possible value today; the panel says
"تتحمّلها الشركة" in words — the same reasoning that removed `status` from `tips`).

**And the concurrency test found the budget cap guarding nothing.** It measured *spent* — confirmed
`promo` payments — which only exist at completion, so three simultaneous requests on a
one-ride budget all passed (`[201, 201, 201]`). The cap now measures **committed exposure**: confirmed
payments + the discount of each in-flight ride computed on its estimate + the ride being requested.
Verified by deletion: dropping `for_update` gives `[201, 201, 404]`. The per-user test, by contrast,
**passes without the lock** — `uq_rides_active_rider` means one rider can never have two in-flight
rides — so it is documented as guarding behaviour, not the lock.

**All three surfaces were then opened in a browser, including the receipt** — which meant driving a
real ride end to end over the API (approve a driver with three uploaded documents, record a cash
subscription, go online and broadcast a location, request with the code, accept the offer, arrive,
start, complete) because **the `promo` row does not exist until `complete_ride` runs**, and a
hand-written fixture that agrees with your own assumptions is what let `awaiting_confirmation` pass a
full visual review. The receipt shows the discount as a row with `−` and the ok colour, no status and
no date, beside the cash row for the remainder, while `final_fare` stays the *undiscounted* fare —
that last part is the SPEC decision made visible, not a bug.

Two facts found in that pass, both of which nearly became "fixes":

- **`customer-app` has no `arabicDigits` at all.** Its `formatMoney` groups and pads *textually* and
  leaves Latin digits, on every money surface; the driver app and the panel convert. So Latin digits
  in the rider app are its convention — changing one screen to Arabic-Indic would make that screen
  the odd one, and changing all of them is a design decision, not a defect fix.
- **The four frozen promo columns are exposed by no schema** — not `RideOut`, not the panel's ride
  detail. They exist for correctness (an admin editing a code must not move a running ride's
  discount), and what any human reads is the amount on the `promo` payment row. Guarding them is
  `tests/test_promo.py`, which reads the database.

**Stage 12-ح — the female-driver referral incentive — is done** (`SPEC.md` §9.1, `driver_referrals`
+ `referral_settings` in §4, migration `0024`, `services/referrals.py`, `tasks/referrals.py`, the
driver's «أَحِلْ سائقة» screen, the panel's table and its two settings fields). It **ships dormant
twice over** by the owner's decision: the flag is off and the amount is zero, and zero reads as "not
decided yet" — so the mechanism records and measures while no ledger entry is written and **no screen
promises money nobody has decided**.

Four rules in it are worth carrying forward:

- **The qualification is a live comparison, never a stamped column.** There is no `qualified_at` and
  no `status`: rides-completed is counted against a settings threshold at read time, so lowering the
  threshold in the panel pays everyone who was waiting without touching a row — the same rule as
  "flagged" in the gender-mismatch reports. **Only the payment is frozen** (`rewarded_at`,
  `reward_amount`, `reward_currency`, `transaction_id`, written together or not at all, enforced by an
  all-or-nothing CHECK), because money is not re-evaluated.
- **The gender condition applies to the referred driver only, and only with the admin's stamp.** A
  referrer of any gender qualifies — a captain signing up his sister grows the supply exactly as a
  female captain does, and restricting the referrer halves the reach while protecting nothing. That
  deviation from `FUTURE-FEATURES` 46's wording was **approved by the owner on 2026-08-13** — "the
  guard sits on the referred driver, where it matters" — and is recorded in SPEC.
- **The reward is paid by a periodic task, never on the ride path.** A failed bonus write must not
  fail a ride completion, and must not be swallowed the way a failed route-point capture is —
  money is not a trace. A separate cycle makes failure a retry.
- **The code is consumed at signup and nowhere else.** There is no route that attaches a referral to
  an existing account: retroactive attribution is the one manipulation door that cannot be closed
  after it is opened. A rider who sends `referral_code` is **refused, not ignored** (the `gender`-on-
  the-driver-path rule).

`referral_bonus` is a credit with **no matching debit** — the company bears it, as with the coupon
discount, and the company's pot is not a wallet in this system.

**The concurrency test taught the same lesson twice over.** The first version passed with the lock
deleted, because an `asyncio.Event` woke the holder at the exact moment the second call started, so
the commit landed first and the second read a committed row. Rewritten with explicit delays (the
stage-8 shape: the writer holds its transaction open for 400ms, the second starts after 100ms), the
deletion now fails it — and **what it produces is not an exception**: `['paid', 'paid']`, because
`wallet.record` finds the idempotency key and returns the *existing* entry silently, so the second
call stamps `rewarded_at` again and reports a payment that does not exist in the ledger. The platform
would believe it paid twice while the ledger holds one entry — worse than a crash, because a crash is
visible in the log and this is read as a number in a cost report.

**And building it found a defect in stage 12-ز that had already shipped**: `promo_codes_enabled` was
never added to the panel's `FeatureKey` union, so **coupons could not be switched on from the panel at
all** — the sixth flag this project has shipped with no button, with the rule written in this file the
whole time. So the rule is now a **build guard**, by the owner's decision ("a written rule is not
enough; a guard is"): `admin-panel/scripts/check-flags.mjs`, wired into `npm run build` as
`check:flags`.

It makes **two** comparisons, because the defect arrives through two doors and `tsc` sees neither.
The union in `api/types.ts` must equal the backend's `FeatureKey` exactly — **a union that is merely
*smaller* is valid TypeScript**, so nothing but this check notices a missing member, and while it is
missing the button cannot even be written. And the `FLAGS` array in `screens/Settings.tsx` — the list
that actually draws the switches — must contain every key: **an array missing an element is not a type
error**, which is precisely the "value missing from an *array* rather than a union" failure this file
already warned about. `FLAG_LABEL` needs no check; it is a `Record<FeatureKey, …>` and the compiler
owns it. Both halves were verified by reproducing them (and the union half caught a real clobbering of
`types.ts` minutes after being written).

**Stage 12-ط — scheduled rides — is done in the backend and the rider app** (`SPEC.md` §5.11,
`ride_bookings` in §4, migration `0025`, `services/bookings.py`, `tasks/bookings.py`, the rider's
«حدّد موعداً» sheet and «رحلاتي المجدولة» screen). Behind `scheduled_rides_enabled`, per-country, off
by default and seeded explicitly.

**The decision the whole stage rests on: a booking is not a ride** (owner-approved). `ride_bookings`
is its own row and the `rides` row is born at execution, because a `scheduled` ride sitting in wait
would break `uq_rides_active_rider` (you book tomorrow, and today you cannot order), freeze
`commission_percent_at_ride` a week early, and teach a new status to every active-status list — the
`at_stop` lesson. `test_a_booking_creates_no_ride_row` and
`test_a_rider_in_a_ride_can_still_book_for_tomorrow` are the two halves of that.

Five rules worth carrying forward:

- **Execution calls `rides.request_ride`; there is no second door to create a ride.** Every rule
  lives there — the active-ride index, the stops guard, the gender preference, the commission freeze.
  A second creation path is a rule checked in one place and forgotten in the other.
- **The status set is four values and excludes the outcome.** `pending → dispatched`, plus `missed`
  and `cancelled`. No `fulfilled`, no `no_driver`: **what happened after hand-off is what the ride
  says**, and a column here would diverge the first time a ride with a driver gets cancelled. This
  corrected the first draft of §5.11, which had listed both — the correction is recorded there.
- **Three things are reported rather than swallowed**, all because the booker is asleep, not watching
  a screen: a booking whose owner is mid-ride at execution becomes `missed` **with a notice**; a
  dispatch that finds nobody gets a booking-shaped notice (the instant-ride text says nothing about
  *which* booking, and `no_driver_found` is only visible to someone watching); and a booking whose
  gendered preference can no longer be honoured **is dispatched without it and the rider is told** —
  refusing strands her at a time she planned around, and silently dropping it puts her in a car she
  did not accept. All three go through `services/notifications.py` like every other notice, so the
  inbox row and the push stay one door.
- **Turning the flag off blocks new bookings and honours standing ones** (the `multi_stop_enabled`
  rule): a flag must not silently cancel a promise someone arranged their morning around.
- **Cancelling before dispatch is free with no new money rule.** The cancellation fee compensates a
  driver who drove; before hand-off there is no driver. After hand-off it is an ordinary ride cancel
  at the ordinary fee.

**Both concurrency tests own exactly one lock each, verified by deleting them — and what deletion
produces is worse than an exception, in both cases a row that lies to its owner.** Deleting the
execute lock leaves the booking `missed` **while its ride exists**, so the rider is told "we did not
order you a car" with a car on the way. Deleting the cancel lock yields `['created', 'cancelled']` — a
ride created and the booking marked cancelled, so the rider is in a ride they cancelled, and pays the
fee if they cancel it again after acceptance. Neither raises, neither logs.

**The driver's offer card carries the booked time** (`rides.scheduled_for`, migration `0026`), and the
owner's reasoning is the one to keep: **this is a freeze, not a second home**. The ride carries *what
was shown to the captain*, exactly as it carries `commission_percent_at_ride` — the booking is the
source and may change, the offer that was accepted may not. The operational reason came first: a
captain who arrives and finds the rider not ready cancels and complains, and a pill he reads *before*
accepting prevents that — which is why it sits above the fare like the women's-service badge, for the
same reason. And because the offer frame is pure `RideOut.from_ride` serialization, the badge reaches
him with no extra query. The test asserts the value in the row **and** in the route output, because a
field the app reads and nobody sends is a badge that never appears — this project has shipped that
exact shape before.

Two smaller things the build caught. `pricing.estimate` returns `.fare`, not `.estimated_fare`, and my
first `except Exception` around it **swallowed the AttributeError and stored NULL** — the swallow is
now narrowed to provider errors, which is the rule the project already had. And `BookingOut` carries
`currency` beside the amount: a money value serialized without its currency prints bare in the app,
which is exactly what shipped in the panel's coupon table two days earlier.

### Stage 13 — the full manual run on two phones (2026-08-15)

**A fresh driver was created from the app's own screens and taken all the way to a paid withdrawal**:
registration (3 steps) → vehicle + nine documents → admin review and approval in the panel → wallet
topup → subscription bought from the screen → online → a real ride from the rider's phone (offer card,
accept, arrive, start, complete) → payment from the rider's screen → rating → withdrawal request →
admin approve + "record the transfer". **The verdict is the ledger, not the status codes**: four entries,
sum 10.804 = the last `balance_after`, nothing negative.

**Five defects, and four of them are the same shape — a screen answering a question nobody asked it.**

1. **The driver app had no door to step 3.** `Register` navigates to `/register/documents` after
   `signIn()`, but `Anonymous` redirects a now-logged-in user to `/`, and the root showed **Pending** to
   every unapproved driver. So a new captain landed on «طلبك قيد المراجعة» **with no vehicle and no
   documents** — the admin reviewing nothing, and no button anywhere in the app leading to the upload
   screen. Fixed where the decision belongs: **the root routes on state** (`profile.vehicles.length === 0`
   → the documents step), so the race, a closed app mid-signup, and a reinstall all land correctly.
   `PendingScreen` also gained a CTA for what is still missing or rejected.
2. **`missing_required` was answering the guard's question and being read as the driver's.** It counts
   types with no **approved** document — right for `drivers.approve`, wrong for «ماذا أرفع؟»: after
   uploading all nine, the app told him the six required were still missing and offered «أكمِل ما ينقص».
   Now `documents.awaiting_upload` (no row **or** rejected) is its own function and its own field, and
   both driver screens read it. Same shape as the rider payment screen from package (ب).
3. **The panel kept the review buttons on a decided document.** Nine clicks sent nine reviews for the
   **first** document (`Counter` of 409s) because approved cards still rendered «اعتماد»/«رفض», and
   `documents.review` refuses anything not `pending`. The buttons now render only for `pending` — the
   "a disabled button that says why beats a button that works and then 409s" rule.
4. **The withdrawal sheet offered two amounts that both 409.** With `min_withdrawal_amount` above
   `available_for_withdrawal` (which the item-13 reserve can cause), «الحد الأدنى» exceeds the balance and
   «كل المتاح» is under the minimum. The sheet now states all three numbers and disables the submit.
5. **`localhost` is a coin flip on this machine and it hung the whole panel.** With a session the panel
   sat on its splash forever: measured, `/auth/me` completed while `/config` and `/auth/me/totp` **started
   and never finished**. Cause: `http://[::1]:8001` accepts the connection and never answers (Docker
   publishes IPv4 only), and Chrome resolves `localhost` to IPv6 for some connections. The dev fallback in
   all three clients and the compose env are now `127.0.0.1:8001`. Nothing was wrong with the backend —
   curl answered every one of those calls in under 40ms.

**Two more found by driving a cash ride and reading the inbox, both money-adjacent.**

6. **A cash payment had exactly one confirmation door, and it disappears.** `RideDetails` labels a
   pending cash payment «بانتظار تأكيدك» but built the CTA for `cliq` only — the real button lives on the
   Collect card inside Home, which is gone the moment the app is reopened (a completed ride is not
   "active", so `getActiveRide` never restores it). A captain who took the cash and closed his app could
   never confirm it: the payment stays `pending`, so the ride reads as **unpaid** and its `outstanding` is
   still owed. `RideDetails` now carries «استلمت المبلغ كاش» for `cash && pending` — **with no dispute
   button beside it**, because `dispute_by_driver` refuses anything but CliQ.
7. **`DOCUMENT_TYPE_LABEL` never learned item 11's six new types**, so `label_for` fell through to
   `doc_type.value` and the driver's inbox read «vehicle_plate: مقبولة» — a raw enum inside the one place
   the backend writes a sentence for a human (`title`/`body` for the OS tray; everything else is raw
   `data`). Nothing catches a missing dict key: not `tsc`, not `check:enums`, not a build.
   `test_every_document_type_has_an_arabic_label` iterates the enum and now does.

8. **One `PushMessage` was sent to both parties, and it was written for the rider.** The captain's inbox
   read «تم قبول رحلتك — الكبتن في طريقه إلى نقطة الانطلاق» **about himself**, and «شاشة الدفع بانتظارك»
   for a fare he is owed. The rule was already in this file — `stop_wait_exceeded` was pushed *out* of
   `RIDE_EVENT_TEXT` in 12-ب precisely because two parties are not told the same thing — it just had never
   been applied to the ride events themselves. `DRIVER_RIDE_EVENT_TEXT` now decides per event, and
   **`None` means "not his business"**: what he did with his own hand (accepted, arrived, started) writes
   him no row, while what happens *to* him (the rider cancelled, the ride ended) reaches him in his own
   words. A test asserts every event in the rider map has a decision in the driver map, so a new event
   cannot inherit the rider's sentence by default.

**And the cash path was verified against the ledger on the device**: with commission at 10%, a cash ride
writes **`commission −0.980` and no `ride_earning`** — the balance goes 10.804 → 9.824, which is the
documented case of a cash ride leaving a captain's balance lower than it started, seen on a real phone.

**And one thing that is not a defect: closing the driver's socket switches him offline** (`ws/routes.py`
marks `go_offline` in its `finally`). Reloading the page from the harness did it, and it looked like the
app switching itself off.

**Two operational facts for the next device run.** Firebase phone auth answers
`auth/billing-not-enabled`, so **no one can register through it** — a mock SMS contract was activated on
the dev stack to get past it, and per the priority chain (`whatsapp ← sms ← firebase`) an active SMS
contract silently outranks Firebase. And CDP's `DOM.setFileInputFiles` cannot hand the WebView a readable
file under Android scoped storage: the upload path is exercised by building a `File` from a canvas blob
and setting `input.files` via `DataTransfer`, which runs **the app's own upload code**; only the SAF
picker itself stays a human tap.

### The cash-payment round trip, measured on both phones (2026-08-15)

**Re-running the cash flow from scratch after the item-6 fix found three more gaps, all on the far side
of the confirmation.** The fix gave the captain a door; nothing told either party what happened through it.

- **`POST /payments/{id}/confirm` published nothing at all.** The row changed and no one was told: the
  rider's open screen kept saying «سلّم المبلغ للكبتن» — measured at 15 seconds, unchanged — after the
  cash was handed over *and* confirmed, and his inbox held no trace that the ride was settled. Now
  `notifications.publish_payment_confirmed` runs after the commit, to **the rider only** (the captain
  pressed the button; nobody is told what they just did — the `DRIVER_RIDE_EVENT_TEXT` rule).
- **The rider's payment screen now polls while — and only while — a payment of his is `pending`.** Five
  seconds, stopping the moment nothing awaits, which is the panel's live-map argument applied to a
  question whose answer is only ever "has he confirmed yet?". Measured after: the screen turned itself to
  «اكتمل دفع هذه الرحلة» **4 seconds** after the captain pressed, with nobody touching it.
- **Neither ride log showed payment state, and `paid_amount` had been arriving in every list call with no
  reader** — its own schema comment says «يُقارَن بالأجرة فتُقرأ الرحلةُ غيرَ مسدَّدة». A rider saw the
  same row for a settled ride and one he never paid; a captain reopening his app had **nothing pointing at
  the money he still had to confirm**. Both logs now carry a badge, and both distinguish the two cases the
  same way: **payments exist but the sum is short → «بانتظار التأكيد»/«بانتظار تأكيدك»; no payment row at
  all → «لم تُدفع»**. That distinction is not cosmetic — one means the captain has a button to press, the
  other means he has nothing to do and the rider does.

**What the restart tests established** (force-stop, relaunch, re-attach — a real close-and-open): the
captain's confirm door survives a restart and the Home collect card does not, which is exactly why the
door had to live on the ride's own screen; the rider's screen reads «اكتمل» after a restart in either
direction; and **the only button left on a settled ride is «قيّم رحلتك»** — there is no second payment
door. Both ledgers reconcile after every step: sum of entries = last `balance_after`, nothing negative.

### `check:target` / `check:dist` — the build guard for "which backend is this bundle talking to" (2026-08-15)

**`dist` on this machine is not a check artifact; it is what the container serves to the phones over
the tunnel.** So a plain `npm run build` — no `VITE_API_BASE_URL` — silently overwrites it with a bundle
that calls `http://localhost:8001`, an address that does not exist inside the phone. The app then sits on
the splash saying «الشبكة ضعيفة — جارٍ المحاولة» while the network is fine and a raw `fetch` from the same
WebView returns 200. **Nothing else can see it**: the build succeeds, `tsc` passes, and `check:scale`,
`check:enums` and `check:config` are all green, because the defect is not in the code — it is a variable
that was not passed. It cost this session twice.

**It is two gates, and their order is the difference between a warning and a guard.** `check:target`
(`--intent`) runs **before** `vite build` and refuses an undeclared target, so the wrong `dist` is never
written — a post-build check alone lets the damage land and then tells you about it while the container
is already serving it. `check:dist` (`--dist`) runs after and measures the output: the declared host must
appear in the bundle, and no `localhost`/`127.0.0.1` URL may survive anywhere in it — which catches a
*stale file left in the directory* from an earlier build, something the variable cannot know about.

**The default is the safe one and the intent is declared**: a local build needs `DEV_BUILD=1`, and
type-checking alone was never a reason to build — `npm run lint` does that. It sits in both PWAs and
**not** in the panel, which is served on `127.0.0.1:5175` by design.

### Item 15 — driver advances, the first money the platform lends (2026-08-14)

**Nine decisions were answered before the first line** (`design/DRIVER-ADVANCES.md` §9, `SPEC.md` §9.2),
by the owner's instruction. The one the whole feature rests on: **a debt is not a negative balance.**
`balance_after >= 0` is a CHECK in the database itself, and lifting it would drop a guard protecting
*every* money path to serve one feature — "a price not paid". So: `driver_advances` is its own table,
and the ledger carries two entries — `advance` (credit at disbursement) and `advance_repayment` (debit
at each deduction). **The remaining amount is summed from the ledger, never a column** (the wallet rule),
which is what `wallet_transactions.advance_id` exists for.

Five rules worth carrying forward:

- **Eligibility is named metrics, never a "credibility score"** (decision 1). `Requirement(key, met,
  value, needed)` goes back to the screen as a list: someone refused reads «رحلاتٌ مكتملة ٣١ / ٥٠» and
  knows what to do; «مصداقيتك ٣٫٢» tells him nothing. And a requirement whose threshold is zero prints
  its value alone — «٧ / ٠» invents a comparison where there is no requirement.
- **"A weekly or monthly subscription that has *passed*" means `expires_at <= now`, not `starts_at`.**
  My first cut read the start date, which let a subscription an hour old qualify — the exact case the
  owner's decision exists to exclude ("bought a monthly today and asks for an advance an hour later has
  proven nothing"). Caught by opening the screen on the phone and reading the condition back against his
  words. `test_a_subscription_still_running_does_not_qualify` is now the guard.
- **The deduction lives inside `payments.settle`'s `not in DIRECTLY_COLLECTED_METHODS` branch.** Cash and
  CliQ never enter the wallet, so there is nothing there to deduct from — and it **never fails a
  settlement**: an insufficient balance defers the deduction to the next ride, the debt stays in its table.
- **Dispatch reads a prepared column** (`drivers.advance_blocked`), written by a 10-minute job — a ledger
  sum in `eligible_driver_ids` would put a money calculation in the path every request and every rider's
  map takes. **But it is cleared in the repayment path itself**, not by the next cycle: someone who paid
  and stays blocked for ten minutes reads the payment as having had no effect.
- **The reserve-vs-debt decision needed no code.** The reserve is a condition on *withdrawal* and a
  deduction is not a withdrawal, and an outstanding advance blocks closing the account anyway — so "the
  debt is taken from the reserve first, the rest is paid out" is what already happens.

**And the concurrency test repeated the tips lesson exactly.** Three guards, and deleting them one at a
time proves nothing: the partial index `uq_advance_outstanding` owns **disbursement** alone (both locks
deleted, still green), while the driver-row lock and the advance-row lock each own **repayment** and
**either suffices**. Only deleting both turns two simultaneous repayments into `Counter({200: 2})` —
4.000 debited from a wallet for a 2.000 debt, with no exception and no log line. Measure, then write down
what you measured.

**Write-off is an admin act with a written reason, and writes no ledger entry**: no money moved in
anyone's wallet, and a fake "settlement" entry would make the statement say he repaid. 90 days makes it
*available*, never automatic.

**The two stage-12 maintenance jobs are done** (`tasks/maintenance.py`; the beat schedule now holds
nine jobs).
Neither is interesting except for one rule each, and both rules are about what the job must *not* do.

**The inbox trim deletes by age alone, read or unread** (`inbox.trim`, 90 days, 5000 rows a cycle).
An unread notification older than three months will not be read, and the inbox is **the trace of an
event, not its source** — the ride, its payments and the ledger hold the truth and are never trimmed.
Keeping unread rows forever would grow the table by exactly the people who never open the app. The
retention is a module constant, not a per-country setting: an operational number no user sees and no
market differs on, so a field for it in the panel is a second state that can disagree with behaviour
nobody measures.

**The stale-order sweep asks the provider and never invents a verdict** (`order_maintenance.sweep`).
What it exists to fix is not litter: an abandoned card order leaves a `pending` payment, and `pending`
is in `OWING_PAYMENT_STATUSES` — so the ride reads as paid by a payment that will never confirm, and
its owner cannot pay by any other channel. That is `card_payments._mark_failed`'s own docstring, and
this job is what runs it when nobody returns to the page. But **`apply_state` refuses anything that is
not `created`**, so a locally-written `cancelled` would make the provider's later webhook be ignored —
a card charged and a wallet never credited. Hence: orders **with** a provider ref are re-asked
(`reconcile`) and left open if the provider still says open; orders **without** one never reached the
provider, so they are dropped through their own channel's door (`drop_unopened`, which releases the
payment) after 30 minutes — long enough that an interrupted open call's webhook has landed, and the
residual risk is written down rather than denied. Each order commits in its own transaction, so one
provider outage cannot undo what was already settled.

**Stage 12-ي — ride sharing — is now built end to end and opened in a browser** (backend, matching,
dispatch, the panel's numbers, both PWAs). The passage below is the record of how it was built, in
order; the two paragraphs after "Still unbuilt" are what has since landed.

**Stage 12-ي's data layer came first and its guard was measured.** What exists (migration `0027`, `models/sharing.py`,
`tests/test_ride_sharing_index.py`, the `ride_sharing_enabled` flag and its panel switch, seeded off
with a zero discount) is the piece the owner ordered first, and it produced a correction to his own
decision.

**The index he approved was inverted, and only the test showed it.** SPEC proposed
`UNIQUE(driver_id, COALESCE(share_group_id, id))`. Measured, it **rejects the two rides it exists to
allow** (same group → same key) and **permits both things it exists to forbid**: two solo rides on one
driver (each keyed by its own id, so the keys differ — i.e. it *deletes the guard it was extending*)
and two separate groups on one driver. None of that would have failed an existing test, because the
old guard had no concurrency test of its own — which is exactly why the owner put this first.

**What actually guards is the seat, not the group.** `rides.share_seat` is 1 for the first ride **and
for every solo ride**, 2 for its partner. Then `uq_rides_active_driver` is
`UNIQUE(driver_id, share_seat)` over the same partial predicate: a driver holds at most one seat of
each number, and **two solo rides collide on seat 1, so the old guarantee survives verbatim** rather
than being replaced. `uq_rides_active_share_group` is `UNIQUE(share_group_id, share_seat)` and bounds
the *group* to two riders however their drivers differ — the one case the driver index cannot see,
which is why it needed its own test after deletion showed no other test owned it. A CHECK keeps seat 2
from existing without a group.

**What the database cannot own, and the service must**: that the partner's group is *the driver's own*
group. No unique index compares two rows, and the failure mode is mis-grouping rather than money from
nothing — so it is written down as the service's job under the lock, not assumed to be covered.

**The money path is now built and tested too** (`services/sharing.py`, migration `0028`,
`tests/test_ride_sharing.py`). A rider sends `share: true`; the per-country percent is **frozen on the
ride** (`share_discount_percent_at_ride`, zero meaning "not shared" — so there is no second boolean
that can disagree with it); at completion a **company-borne payment row with method `share`** is
created and confirmed through `payments.settle`, exactly as the coupon does. The driver is paid on the
undiscounted fare and the rider's wallet is never touched, which is decision 3's whole point — and
**the discount applies even with no partner**, because decision 3 says the promise is kept.

**`share` is its own `PaymentMethod`, and the reason is not the label.** `promo.spent()` measures a
coupon's budget by summing `promo` rows, so a share discount written on that channel would eat the
**coupon's** budget — a money cap consumed by something that isn't it. The label follows: «خصم كوبون»
on a ride with no coupon is a lie.

**And the same mistake then appeared in two more places, so the concept is now named once.**
`stats._payment_mix` excluded `promo` *by name* to answer "what do people pay with"; `share` is the
same kind and silently entered the mix as if riders had chosen it (`test_admin_stats` caught it). The
rider app's `PayableMethod = Exclude<PaymentMethod, "promo">` had the identical shape and put `share`
in the payment picker — caught by `tsc` at the `CTA` record. Both now read from a named concept:
`models/payment.py::PLATFORM_WRITTEN_METHODS` in the backend, `PlatformWrittenMethod` in the app.

**The cancellation rules are built** (`sharing.on_member_cancelled`, decisions 5–8). Whoever cancels
pays the ordinary fee alone — which needed **no new code at all**, because `rides.cancel_ride` already
charges exactly that; that is what shape (ب) bought. The remaining rider's ride has its frozen percent
zeroed **before departure only** (zeroing it *is* raising the price: `settle_discount` reads it at
completion), keeps it after (decision 6 — raising a price with no alternative is the rejected option),
and is told either way. **It is one conditional `UPDATE`, not a second row lock**: locking the partner's
row after the canceller's opens a real deadlock when both riders cancel at once, which happens when a
driver is late. The statement takes and releases its own lock, and its status predicate makes it
idempotent — the second cancel matches no row because the first moved it out of the active statuses.

**Group formation and matching are built, and the concurrency test came before either** — and it
corrected a second assumption in the same decision. `tests/test_ride_sharing_join_concurrency.py`
fires two joiners at one lead: one seat is filled and the other is refused — **but deleting the lead's
`with_for_update` leaves it green**, because the partial index `(driver_id, share_seat)` is what
catches the second. So the seat belongs to the index, and that test guards *behaviour* (the refusal
code a rider reads), like 12-ز's per-user coupon test. **What the lock alone owns is the lead's state
between the check and the write**: a captain departing in that gap leaves a rider attached to a car
that has left — a perfectly valid row saying what never happened, with no exception and no log line.
Deleting it yields `ok` instead of `share_group_unavailable`.

**The matching is a corridor in the database and a detour cap from Mapbox** (`sharing.find_lead`).
The corridor is `ST_DWithin` around the **straight line** between the lead's two points — a filter,
not the verdict, and it exists so one request does not call Mapbox once per open ride in the country.
Dropping **both** `geography` casts puts a ride 70 km away inside a 2 km corridor (measured; two tests
fail), though **either cast alone suffices** — PostGIS casts the other side implicitly, which is
exactly why both are written rather than relying on a conversion only its author knows about. The
itinerary measured is **the worst ordering for the lead** (lead pickup → partner → partner's drop →
lead's drop), **one call per candidate**, at most **three candidates, oldest first**: so the cap holds
however the captain actually drives, and whoever waited longest is served first. Its home is
`dispatch._run` — after `searching`, before the first offer — because the request must answer
immediately and a Mapbox call must not stand in front of the reply; any failure there falls back to
ordinary dispatch, since sharing is a **possible bonus**, not a condition of the ride.

**The captain is notified, not asked, and that rests on the badge**: the offer card carries «مشتركة —
قد ينضم راكب ثانٍ» *above* the fare, so accepting is consent to the second seat — the women's-badge
argument exactly. A card that does not draw it invalidates the decision, which is why the three
`RideOut` fields are mirrored in both apps' `Ride` types (they were in neither: a field with no
mirror). And `join_group` reads `ALLOWED_TRANSITIONS` from `services/rides.py` rather than copying it,
so there is no second door to `accepted`.

**Verified in a browser, end to end**: two riders requested sharing, the second joined the first's
car with no new offer, and the first rider's badge changed from «بانتظار شريك» to «رحلة مشتركة» —
plus the confirm sheet's share row in dark/light/pink (with the separate gendered consent), the
panel's four numbers in both themes, and the captain's offer and active cards. That pass also found a
wording collision — the tracking sheet's old «مشاركة الرحلة» button now sits under a «رحلة مشتركة»
badge meaning something else — so the older label became «أرسل تفاصيل رحلتك» (decision 56).

**Still open in 12-ي**: whether the company bears the remaining rider's difference **before**
departure (the owner's one deferred money question, SPEC §5.12), and the captain-consent decision is
recorded there as the one of the six implementation decisions that is his to confirm.

**The original text of this section follows, and is still the design.** `SPEC.md` §5.12 holds the design and the
owner's four decisions, and a fresh session can start from there: **two riders to a group** keyed by
`rides.share_group_id`; the driver-side index becomes the composite
`(driver_id, COALESCE(share_group_id, id))` **and its concurrency test comes before any screen** —
that index is what stops a shared ride from being read as two active rides for one driver, and it is
the one place the whole feature can produce money from nothing; a **flat per-country discount
percentage**, sized so the driver's share of two rides is clearly above a solo ride, with **the
company bearing the gap in the first cut** (the coupon rule: a discount must not reduce what the
driver earns); and the safety rule the owner strengthened himself — **a gendered request is not
shareable by default, even with another woman, and becomes shareable only by an explicit choice she
makes**, because "she would probably accept" is not consent and silence is not a decision in a safety
question.

**The cancellation fee is now decided too** (owner, 2026-08-13, SPEC §5.12 decision 5) — **two halves,
because the incident has two parties and only one of them acted**. **Whoever cancels pays the ordinary
fee alone**: no new sharing fee and no doubling, their row cancels through `rides.cancel_ride` and its
frozen fee exactly as a solo ride would — which is precisely what shape (ب) was bought for, each ride
row settling on its own. **Whoever remains has their ride converted to solo at its full price and is
told explicitly**: the discount was the price of a sharing that did not happen, and keeping it once its
reason is gone is a discount for nothing. **The explicit notice is what separates this from the option
§5.12 rejects** — the rejected one is being told *at the end of the ride* that the price changed; being
told *when it happens* is question 3's option (b), applied to the cancellation case rather than the
never-found-a-partner case. That is why it does not contradict decision 3: decision 3 governs a partner
who never existed (promise honoured, company bears it), this governs a partner who existed and left.

**The three branches that decision opened are now decided too** (owner, 2026-08-13, SPEC §5.12
decisions 6–8), and the first of them sharpened decision 5 itself.

- **A remaining rider already `in_progress` keeps the discounted price and the company bears the
  difference.** Raising it mid-route is the rejected option verbatim — and what makes it rejected is not
  the amount but **the absence of an alternative**: someone told the price while sitting in the car can
  neither accept nor refuse, so the telling is notification of a fait accompli, not a notice a decision
  rests on. So decision 5's condition is not "he is told" but **"he is told while he can still act"**.
- **No fee waiver for a remaining rider who refuses the new price.** Two reasons: a **second** waiver in
  a system with exactly one opens a door — and `gender_mismatch` rests on a condition verifiable from
  the row itself, while "I refused a price" is a state anyone who cancels for any reason can claim; and
  **he was shown the price before he proceeded**, so cancelling after it is an ordinary cancellation
  made knowingly. **The two decisions complete rather than collide**: decision 6 forbids raising the
  price where there is no alternative, so all that is left for decision 7 is the case where there *is*
  one — before departure, where the notice precedes the going and refusing is free by its own nature
  (cancelling before acceptance carries no fee at all; after it, the ordinary fee like any ride).
- **No search for a third partner in the first cut** — two riders, and a second waiting window would
  lengthen the remaining rider's trip for a discount that no longer applies to him.

**What stays open is now only half of the cost question**: whether the company bears the difference for
a remaining rider **before** departure. After departure decision 6 settles it. Both answers run through
12-ز's mechanism, so the difference between them is **a setting, not a build**.

**Every screen these stages added has been opened in a browser**, including the panel's seven and each
of the design packages below. Keep doing that before calling one done: the failures `tsc`, `check:scale` and
`check:enums` cannot see — a value missing from an *array* rather than a union, a dropped
tailwind-merge class, a marker that never renders, a button that works and then 409s — are exactly
the ones this project has shipped before, and every one found since has been of that shape.

### The queue the owner set (2026-08-13), in order

**② sound → ③ motion → ④ map effects.** Each is a session.

1. **Sound** — the motif is **approved and written down** (`DESIGN.md` §9): `A4→D5→E5` in D
   pentatonic, every cue derived from it, generated with Web Audio oscillators (no asset files), the
   splash signature moved to **the first tap after login** because browsers block audio before a
   gesture and a chime nobody hears on first launch is the launch that forms the impression. Two
   device-level switches; the driver's incoming-request tone survives the general switch and only its
   own switch silences it. The iOS silent-switch caveat goes in `README` and is never claimed as a
   guarantee.
2. **Motion** — `DESIGN.md` §8 already defines the tokens (three durations, two curves,
   `motion-reduce`) and `BottomNav` already uses them. What remains: route transitions by direction,
   sheets, press feedback, list stagger, and **a skeleton for ride details** (it shows a bare spinner
   for ~8s while three calls resolve).
3. **Map effects** — pulse on own location, heading rotation smoothed, `easeTo` framing, pulse on the
   pickup pin while searching. The owner's constraint — **CSS/SVG, never a render loop** — is to be
   *measured* in the browser, not assumed: a captain's battery runs for hours.

**Also still open**: the splash changes he asked for (longer minimum, network-loss and weak-network
states with real disconnection testing, continuous `O` spin) — the sound part of those is gated on §9,
the rest is not.

### The splash screen and the app icons

**The splash lives in `index.html`, not in React, and that is the whole point** (`DESIGN.md` §7). The
JS bundle is deferred, so anything a component draws appears *after* the moment the splash exists to
fill. It therefore carries its own copy of the four tokens it needs (`--bg`/`--tx`/`--mut`/`--brand`
values from §1.1) inside a `<style>` in the same file — `index.css` is in the bundle too. That copy is
the one place in the project where duplicating design values is allowed, and its price is that
`check:scale` cannot see them (it reads `.tsx`/`.ts`).

`TAXO` is four stroked SVG paths, each `pathLength="100"` so the dash maths is a percentage rather than
a measured length. They draw in sequence (520ms each, 170ms apart) — **drawn, not revealed**; four at
once reads as one flash. Then the `O` alone becomes the loading indicator: `tx-open` widens the dash
gap once (a full circle rotating is invisible, so the arc has to open) and `tx-rotate` spins forever,
both starting at exactly the state the draw ended in, so there is no jump. `prefers-reduced-motion`
removes all three and shows a still logo with a plain «جارٍ التحميل…» line.

Four things in it are worth carrying forward:

- **It is removed when the app is ready, not when the animation ends** (`lib/splash.ts::hideSplash`,
  called from `Boot`). The animation fills a wait; it must never create one. And `Boot` no longer draws
  its own logo-and-spinner — two loading screens in a row read as a stumble.
- **A pre-paint script sets the theme class**, or the splash paints light and flips dark one frame
  later, every launch, for everyone who chose dark.
- **The pink theme reaches it through a written hint, not a guess.** `pink` requires
  `user.gender === "female"`, which lives in a session the splash cannot wait for; guessing from the
  raw choice would paint a pink logo for someone it is not offered to. So `BrandProvider` writes the
  **computed** value to `taxo.pink.active` in the same effect that toggles the class — a paint hint
  that cannot disagree with what it mirrors, because it is written from it.
- **`stroke-linecap: round` draws a dot on a fully-offset dash**, so every letter showed a stray pen
  point before its turn. The letters are `opacity: 0` until their own keyframes start. Caught by
  opening the screen, not by reading the CSS.

**The icons were off-palette and are rebuilt** at ten `any` sizes plus two `maskable` plus an
apple-touch icon, per app, carrying `RIDER`/`DRIVER` under the wordmark. The old one was `#facc15` on
`#0b0f14` — the yellow dropped in 12-أ over a background that was never in §1.1 — and the rider
manifest still declared that background as its `theme_color`. They are rendered from one master SVG per
app by a scratch Playwright script rather than by adding an image dependency. First attempt set
`stroke-width` to 26 directly instead of letting the ×1.375 group scale the splash's 8; the letters
fused into a blob, which the file viewer showed and no check would have.

### Stage 13 — the trial run, and what only a real ride could show (2026-08-14)

**`tests/test_stage13_scenario.py` drives the whole journey through real doors**: registration, a
vehicle, **a refused approval with no documents** (409 `documents_incomplete`), three uploads and three
reviews, approval through `drivers.approve` — its only door — a subscription bought with money that was
topped up, a ride through real dispatch and a real offer, location broadcasts, a mixed payment, a
rating, then a withdrawal approved and paid. Every other test file shortcuts this with
`helpers.approved_driver`, which writes `approved` and a subscription row directly — correct setup for
a feature test, wrong for the question stage 13 asks. **The verdict is not "200 everywhere" but that
the ledger adds up**: each wallet's balance equals the sum of its entries, no `balance_after` is
negative, and what entered the driver's wallet is the wallet-funded part alone — not the whole fare.

**And the browser run found the captain's collect screen was dead.** `getRidePayments` called
`/payments/rides/{id}/payments` while the payments router carries **no prefix**, so the real path is
`/rides/{id}/payments`. The 404 left the screen rendering nothing — a **blank screen at the moment he
collects cash**. It had shipped since stage 10 because reaching it needs a completed ride with a real
driver, which no visual pass had ever done. Now it draws the fare, the split, the commission line and
the "the rider has not chosen a method yet" note.

**The three screens listed as never-opened are now opened**: the «طلب نسائي» badge above the fare on a
live gendered offer, the cancel-reason sheet with «الراكب ليس أنثى — عدم تطابق» (shown only to a captain
who restricted her rides), and the preference strip on her home — which appears only once she has
actually restricted, so the probe had to set it from her own settings screen first.

### The device trial list, items 7 and 8 (2026-08-14)

**The owner tests on a real phone now** (both apps are Capacitor shells around the live tunnel), and his
numbered list drives the work. Items 1–3, 5 and 6 shipped earlier; 7 and 8 landed here.

**Item 7 — "drivers do not appear on the rider's map" — was not a broken chain.** Measured with a real
captain broadcasting: `GET /drivers/nearby` returns him, and the socket delivers `nearby_drivers`
frames. What was wrong is *when*: the app drew cars **only** from the socket, so the map stayed empty
until connect + viewport + first frame — 3634ms on localhost, far worse through the tunnel, and
**forever if the socket never opens**. And the REST snapshot the SPEC prescribes for exactly this
(§10: "for the first paint and after a socket drop") was declared in `api/endpoints.ts` and **called by
nobody** — this project's signature failure, a route with no door. `setViewport` now fetches it while
`framesSeen` is still zero, a socket close resets that counter (so the snapshot is a door again after a
drop), and an in-flight ref stops a pan from firing N calls. Measured after: snapshot at 1952ms, socket
frame at 2139ms — REST first, which is the whole point. A late snapshot can never overwrite a newer
frame, because the counter is captured before the call and compared after it.

**Item 8 — the route line — was one parameter away the whole time.** `services/directions.py` has
called Mapbox Directions since stage 3 and passed **`overview=false`** with a comment saying the shape
was not needed. So the geometry was never requested, never stored, and both maps drew a dashed straight
line. Now `fetch_route(..., with_geometry=True)` asks for `geometries=geojson&overview=simplified`, and
**`services/route_line.py` stores it on `rides.route_polyline` once, at acceptance** (owner's decision):
not on the estimate path, which is called on every pin drag and would ship a payload to someone who has
not ordered a ride yet; and **never re-fetched**, because a second call on a busier road returns a
different line and the rider would see one route while his captain sees another — the freeze rule that
governs `commission_percent_at_ride`. Failure is not fatal: `ensure` catches provider errors only
(never a bare `except`, the 12-ط lesson) and returns `None`, the endpoint answers `points: []`, and the
apps fall back to the dashed straight line. **Dashed vs solid is the honest distinction**: dashed says
"between you two", solid says "this is the road" — which is why `DESIGN-DECISIONS` 38 is not contradicted
(it forbids a line *we* invent, not one Mapbox returned).

Three things worth carrying forward from building it:

- **The accept route builds its response before the extra commit.** `route_line.ensure` + `commit`
  after `_to_out` expired `pickup_lat`/`dropoff_lat` (they are `column_property` expressions) and the
  serializer then lazy-loaded outside the greenlet — `MissingGreenlet`, the exact trap `_flush_and_reload`
  exists for. Build the output first, then commit.
- **One shared test fake hid behind 252 failures.** `conftest.stub_mapbox` is the *only* place the suite
  patches `fetch_route`, and its signature did not accept the new keyword — so every ride test raised
  `TypeError`. It now mirrors the provider (geometry only when asked) rather than simplifying it: a fake
  that always returns a shape would let a test pass while the estimate path asks for one.
- **Progress tracking is a trim, not a re-fetch.** `lib/route-line.ts` (one copy per app, like
  `BottomNav`) slices the stored line at the nearest vertex to the driver. Drawing is not a money
  calculation, so §14 is untouched — the same split as the waiting clock in 12-ب.

**And the device harness is `adb` + raw CDP, not Playwright.** Android WebView publishes no
browser-level endpoint (`/json/version` carries no `webSocketDebuggerUrl`), so `connectOverCDP` times
out; attaching to the **page** target's socket works. Two operational facts cost time: a **dozing**
phone freezes the WebView so every CDP call hangs (wake it and `svc power stayon usb`), and **injecting
a refresh token into the app rotates it**, invalidating the harness's copy and sending every probe back
to the rate-limited login door — inject the access token alone.

**Two defects from the floating-bar package surfaced here too, both about layering over decisions.**
The bar swallowed «قبول» on the offer card — `elementFromPoint` at the button's centre returned the bar
— because the route sheet carries a `transform` and therefore its own stacking context, so `z-50`
inside it never beats `z-30` outside. And the women's-mode notice stood over «ابدأ الاستقبال» and then
over a cancel *reason*. Both now follow one rule: **nothing overlays a decision** — the bar and the
notice hide while a ride or an offer owns the screen. The notice also went back to `--acc`; its own
docstring had said pink would make it announce itself twice, and that was still right.

### The floating bottom bar, and three defects the browser found (2026-08-13)

**The bar is one component in `App`, above the route transition — not one per screen.** The owner
asked for an indicator that *slides* between tabs (`layoutId`). It didn't: every screen drew its own
`BottomNav`, so each navigation tore one down and built another, and **`layoutId` only animates
between two elements that existed in the same moment**. Measured: 3 sampled positions in the rider
app, none at all in the driver app; after hoisting, 6 and 8. It sits *outside* `RouteTransition` too,
so it does not slide away with the page it navigates to.

**Which routes carry it is declared per app, and the two lists point opposite ways on purpose.**
`customer-app/src/lib/tabs.ts` uses a **deny** list (rider sub-pages keep the bar — decision 53), the
driver app an **allow** list (its sub-pages cover it). So in each app the *default* is what its own
prototype says, and a forgotten new screen lands on the right side of the line.

**`spacing.nav` went 66 → 84** (62 bar + 14 below + **8 above**). The 8 is not padding for taste: with
76 the bottom sheet ended exactly at the bar's top edge (measured 768 = 768), so a floating pill read
as attached to it.

**`MotionConfig reducedMotion="user"` cancels the animation, not the starting value.** With reduced
motion the route sheet still painted one frame at `x: -24` before settling — a jump for someone who
asked for none. `initial={{ x }}` is a value, not a transition, so the component that declares the
offset is the one that must zero it (`useReducedMotion()` in `RouteTransition` alone).

**And the route transition was dead on every path until it was measured.** No transform and no opacity
change in any frame. Two causes, both invisible to `tsc`: `Suspense` sat *above* `AnimatePresence`, so
the first navigation to a lazy route replaced the whole animated subtree with the fallback; and
`<Routes>` without an explicit `location` re-renders the **exiting** copy with the **entering** route,
so what slides out is the screen that is arriving. Direction now comes from `lib/nav-order.ts` — the
route's rank (tab index, then depth) — because `useNavigationType()` reads a programmatic
`navigate("/account")` after a save as *forward* when it is a return.

**«رجوع» means where you came from, and the written path is only a fallback** (`lib/back.ts`, both
apps). The bell in the map header opens `/account/notifications`, whose `back="/account"` was a fixed
destination — so anyone who entered from the map landed in «حسابي», a tab they never visited, with the
wrong tab lit. **The parent in the tree is not the parent in the journey**, and a screen with two doors
makes one of them a lie. `navigate(-1)` alone is not the fix either: a deep link has no in-app history,
so it would exit the app; `history.state.idx > 0` is what separates the two. Three rider screens have
two doors today (notifications, bookings, cards) and all three were wrong.

### Rider design-matching: five packages, all delivered

A screen-by-screen comparison of `customer-app` against the rider prototype (and the women's screens
against what 10-ج actually built) produced five packages. **The owner approved the order
هـ ← ج ← د ← ب ← أ, one package per session**, and all five are delivered. The rule applied throughout is
his: **in the design but not in the project → `FUTURE-FEATURES`, not built; in the project without a
design → derive from the design's idiom; a behavioural conflict → SPEC and the backend win except in
form, and the decision is recorded in `design/DESIGN-DECISIONS.md`.**

- **(هـ) — done** (`2131535`). Three passages that all describe **already-built** behaviour nobody was
  told about: the privacy note in the rider's profile (her gender is shown to no captain, and the
  nearby-cars map is anonymised already — `anonymous_ref` and its test), the **two-way** matching
  explanation in the female captain's settings (the direction every version of this feature drops, and
  the answer to "why did my offers dry up?"), and the «الطلبات» section heading.
- **(ج) — done** (`2131535`), and **measuring the prototype changed its scope**: `payShow` and
  `rateShow` are `inset:0` over a full scrim (z 60) — *screens*, not sheets — and only `topupShow` is a
  real bottom sheet. So one thing needed converting, not three: the topup sheet (three amounts and two
  channels, holding **no channel logic** — it hands off to `/wallet/topup`, which owns it), plus the
  `Stage` layer for rating. The package's real content was **the rider's notifications screen and its
  bell** — a functional gap, not a cosmetic one: the inbox has existed since 9-ب and the driver app
  reads it, while the rider could not see a dispute's outcome or any notice he missed.
- **(د) — done** (`07c2dd5`). The labels of decision 23 (all decision numbers here are
  `design/DESIGN-DECISIONS.md`); the theme toggle in the map header (**in addition to**
  the settings row, not instead of it); the pin address reverse-geocoded **while the map moves**, not at
  confirmation; the captain **card** in ride details instead of field/value rows; the cards row **inside**
  the wallet; and «الإعدادات» as a separate screen — where what groups it is **the owner, not the
  category**: everything in it belongs to the *device* (appearance, pink theme, offer notifications), and
  everything belonging to the *account* (name, gender, preference, privacy) stays in «حسابي».

- **(ب) — done.** The rest of the confirm sheet — the payment-method picker as a local preference
  (decision 3), the mixed-payment note, the price on the CTA, «رجوع» — plus the Payment screen's
  migration to the centred `payShow` layout, which belonged here rather than in (ج) because that layout
  presumes the channel was already chosen. **Without per-category pricing**, which the owner excluded
  explicitly; it stays deferred in `FUTURE-FEATURES`. Five things in it are worth carrying forward:

  - **`METHODS` moved out of `screens/Payment.tsx` into `lib/payment.ts`** because the list now has two
    readers. It is still *one* list — that is the whole point of decision 4 — but a component importing
    it from a screen is a second home waiting to happen. `PAYMENT_CHANNELS` and `usePaymentPreference`
    live there together, and the preference is **filtered by what the country allows**: a stored `card`
    in a market whose card flag is off would otherwise print «بطاقة» on the CTA and then not exist on
    the payment screen — the women's-service rule that a flag gating a screen must gate what it carries.
  - **There is no «مختلط» channel, and there must never be** (`DESIGN-DECISIONS.md` 51). The design
    lists one; in this backend mixing is not a choice but what *happens* —
    `payments._pay_from_wallet` debits `min(balance, outstanding)` and writes the remainder as a **cash
    row** itself. So the design's note survives verbatim (it describes real behaviour) and the channel
    dies: adding it would be a value the app invents and the backend never sends, which is
    `PaymentMethod.mixed` shipping a second time.
  - **The picker portals to `document.body`, and that is not tidiness.** `ConfirmRide` renders inside a
    `motion.div` carrying `y: 40` — and a non-zero `transform` **makes itself the containing block for
    every `fixed` descendant**, so `inset-0` would have been measured against the bottom sheet, not the
    viewport. The parent is also `pointer-events-none` and `max-w-lg`. Measured after the fix: scrim
    `y=0, height=844` of an 844 viewport. No build sees this class of bug.
  - **`.scr` was a class with no definition.** `Stage.tsx` has written `className="scr max-h-full"`
    since package (ج), copied from the prototype where `.scr` is `overflow-y:auto` — but it was never
    added to `index.css`, so `Stage` clipped anything taller than the viewport with no way to scroll.
    Spelled correctly, present in the markup, doing nothing: the sibling of the missing-scale-key bug
    `check:scale` exists for, and the build is green either way. Now defined, which repairs Rating too.
  - **The payment screen was telling riders a paid ride was paid when it wasn't** — found only by
    driving a real ride and paying it from a wallet that didn't cover the fare. `settled` was
    `outstanding <= 0`, and `pending` is inside `OWING_PAYMENT_STATUSES` — correct for the backend's
    question ("is a new payment row still needed?"), wrong for the rider's ("do I still owe something in
    hand?"). The screen said «اكتمل دفع هذه الرحلة — شكراً لك» in green with «كاش ٢٫٤٨١ بانتظار التأكيد»
    two lines below it. It is now **three states, not two**: pay CTA · nothing left to start but a
    `pending` row, which names the amount and its channel and offers no thanks · fully confirmed. This
    shipped in stage 9 and survived every pass since, because reaching it needs exactly the state (ب)
    built in order to test its own note.

- **(أ) — done, and it was last because it touches every route**: the four-tab bottom bar
  (`الرئيسية · رحلاتي · المحفظة · حسابي`), `/menu` deleted, «حسابي» as a container screen, and the six
  routes re-pathed under it — `/account/{profile,places,bookings,cards,notifications,settings}`. Four
  things in it are worth carrying forward:

  - **`BottomNav` is a copy of `driver-app`'s, not a re-derivation.** Both apps share one design system;
    two bars built twice diverge at the first value edited in one of them. Same 66px, same 19px square,
    same 9.5px label — only the labels differ.
  - **`nav` and `back` are two independent props, and collapsing them is what shipped first.** With a
    single `tab` prop the bar vanished on all six sub-pages while `BottomNav`'s own docstring promised
    «حسابي» stays active underneath — a written rule with no door, caught only by opening all six routes
    and measuring which tab was lit. A tab root is `nav` with `back={false}`; a sub-page is both.
  - **The prototype's measurement overrode decision 22's prose** (`DESIGN-DECISIONS.md` 53). It says
    "ride, payment, rating and provider screens cover the bar", but `pgRideDetail` measures
    `inset:0 0 66px` exactly like `pgPlaces`/`pgSettings`/`pgNotifs`/`pgCards` — bar **and** back arrow.
    Only `payShow`, `rateShow` and `pgCardPage` truly cover it, which they do for free here because both
    are `Stage` (`fixed inset-0 z-60`). "Ride screens" in decision 22 means the *running* ride on Home,
    not the history detail. Measure, then read the prose.
  - **Two doors closed rather than left as conveniences.** The map header's «القائمة» and wallet buttons
    are gone — the first *became* the bar, the second is a tab in it, and a shortcut above the map to a
    tab visible below it is two doors to one place. Same reasoning removed the «الإعدادات» row from
    `Profile.tsx`: package (د) put it there because the account container did not exist yet, and the
    prototype puts it in `accountRows`. The header now carries the account initial, the bell and the
    theme toggle, exactly as the prototype does.

**All five packages are delivered**, and sharing (12-ي) followed them and is done — so **stage 13 is
what remains**. `SPEC.md` §5.12 holds the eight owner decisions plus the six implementation ones the
build added.

**Four items are deferred by the owner's decision until after launch** and are marked ⏸️ in
`FUTURE-FEATURES.md` (dated 2026-08-13): report a problem, the help centre, the "N cars nearby" line,
and per-category pricing. Do not build them; he decides after launch.

### Open debt and decisions waiting on the owner

1. **`women_service_enabled` is off in both countries and stays off until the backlog of already-
   approved drivers has a verified gender** — that was the owner's call, and it is now the one
   business decision blocking a finished feature, with no code left under it. The panel's driver
   page carries the control: a gender column in the list, a filter toggle that opens
   `GET /admin/drivers?gender_verified=false` (kept as a **second axis, not a status pill** — "approved"
   and "no verified gender" are asked together, not instead of each other), and a card in the drawer
   that writes `PUT /admin/drivers/{id}/gender`. An unstamped driver reads «لم يُثبَّت», never a
   gender: matching reads only `gender_verified_at IS NOT NULL`, and showing an unstamped value
   makes it look like it counts. The flag itself is now in the settings screen too — the panel's
   `FeatureKey` union was missing `women_service_enabled`, so there was no switch to turn the
   service on with once the backlog cleared. Clearing the backlog is now data entry, not development.
2. **Three screens were never opened in a browser**: the driver's cancel-reason sheet, the
   «طلب نسائي» badge on the offer card, and the preference strip on the driver's home. All three
   need an approved driver (verified phone + three approved documents) and a live assigned ride to
   reach, so they are best checked during stage 13's manual run.
3. **Provider wire formats are best-reading, not contracts.** Three details in
   `services/card_gateway/telr.py` are flagged in its docstring as needing confirmation against
   real Telr docs/sandbox credentials (never delivered), and `services/sms/`, `services/cliq/`,
   `services/payout/` say the same in their module docstrings. They are arranged so being wrong
   cannot move money wrongly, but they cannot go to production unverified. **`services/whatsapp/`
   is the one provider written against real published documentation** (Meta's Cloud API), so it is
   not in this list — but its authentication template must be approved in the Meta console before
   the channel works anywhere.
4. **Six finished features are switched off waiting for the owner, and two of them also wait on a
   number.** `scripts/seed.py::FEATURE_DEFAULTS` is the intended state, and everything built since
   10-ج seeds **off in both countries**: `women_service_enabled`, `multi_stop_enabled`,
   `whatsapp_otp_enabled`, `tips_enabled`, `promo_codes_enabled`, `driver_referrals_enabled`,
   `scheduled_rides_enabled`. Each has a switch in the panel's settings screen — `scheduled_rides_enabled`'s
   was missing until 2026-08-13 and is now there. **Tipping does
   nothing until its three amounts are entered in the panel**: migration `0022` left both countries
   at zero, which correctly reads as "not configured" and hides the feature, and re-seeding will not
   fix it because `seed.py` is idempotent and skips existing rows. The referral reward is dormant
   the same way *by his explicit decision* — flag off **and** amount zero, so the mechanism records
   and measures while no screen promises money nobody has decided.
   **And do not read the dev database as the intended default**: visual checks toggle flags (JO's
   women's service is switched off and LY's on there right now, from this week's runs), so
   `FEATURE_DEFAULTS` is the answer to "what ships", never `SELECT * FROM feature_flags`.
5. **`FUTURE-FEATURES.md` items 45, 47 and 49** are what remains deferred from the women's service:
   the in-ride emergency button (deliberately *not* half-built — a button promising help nobody
   answers is worse than none), "wait for a female captain" (needs a queue that outlives
   `no_driver_found`), and in-app calling/messaging (needs number masking). Item 46 (referral
   incentives) shipped as 12-ح; item 48 (the "3 nearby" count) is now one of the four post-launch
   deferrals above.
6. **`GET /config` publishes no wallet limits**, so `customer-app/src/lib/wallet.ts` holds the three
   quick-topup amounts as a local constant. They are *suggestion chips*, not limits — the backend
   still validates every amount — but they are the one place the rider app carries a number the
   backend did not send, and the honest fix is to publish `wallet_settings` in the config payload.
   Small, and worth doing the next time a wallet screen is touched.
7. **This machine only**: host port 5173 is taken by an unrelated `taxo-web` stack, so
   `.env.local` sets `CUSTOMER_APP_PORT=5176`. 5176 is the one fallback allowed in
   `settings.cors_origins`; the card-return URL still points at 5173, so testing the card channel
   needs the canonical port.

**Two debts closed on 2026-08-13, recorded because each had already outlived its excuse.** The
rider's topup amount field showed the raw currency code (`JOD`) while every other money surface
showed «د.أ»; it was one line, and it stayed a "known cosmetic bug" long enough that I
**reproduced it in the new topup sheet** by passing the same raw code — the fix is a single exported
`currencyLabel` in `lib/utils.ts`. And quiet hours had been published by the backend since stage 8
while the rider app's `CountryConfig` **type never mirrored them**, so the data arrived and was
discarded: a new shape of this project's recurring failure — not a rule with no door, but **a field
with no mirror**.

## Project rules that override defaults

**`SPEC.md` is the single source of truth.** It is written in Arabic and defines every table, flow,
and constraint. If a requirement is ambiguous, ask before implementing. Do not add features it does
not describe.

**When you deviate from `SPEC.md` for a justified reason, update `SPEC.md` in the same session,
before the commit.** A deviation that outlives its session stops being a decision and becomes a
discrepancy nobody can tell from a bug.

**Section 16 of SPEC.md is a strict, ordered 13-stage plan — one stage per session.** Stages 1
(infrastructure, FastAPI skeleton, Alembic, `users`/`drivers`/`vehicles`, phone+password auth with
JWT), 2 (per-country settings tables, encrypted `provider_credentials` with admin CRUD, seed
script, `GET /config`), 3 (`rides`, Mapbox Directions pricing, request/status endpoints), 4
(Redis GEO presence, dispatch algorithm, WebSocket tracking and ride events), 5 (the
`wallet_transactions` ledger, rider topup/transfer, driver wallet and withdrawals), **6-أ**
(`payments` with cash/manual-CliQ/wallet/mixed and disputes, `ride_route_points` with `final_fare`
recalculation, `ratings`), **6-ب** (Telr card integration — `provider_orders`, hosted payment
page, signed webhook, instant card wallet topup, `saved_cards` tokenization and one-tap pay,
provider-side refunds), **7** (`driver_subscriptions`, purchase over all four channels, the
dispatch subscription check, and the Celery sweep), **8** (the full contracts page with test
connection, unified provider interfaces with mocks, and the OTP/Push/automatic-CliQ/payout
integrations), **9** (`customer-app/` — the rider PWA, plus the in-app CliQ payment page and the
backend fields it needed) and **9-ب** (backend only: driver-document upload/review on the
long-dormant `driver_documents` table, `core/storage.py`, and the `user_notifications` inbox
written from both send doors) are complete. **Stage 11 (the admin panel, `admin-panel/`) has begun** — shell, login, live map, drivers/documents,
finance (withdrawals and CliQ topups), disputes, campaigns, per-country settings and the provider
contracts page. The overview sits on `services/stats.py`, where three rules live: **aggregation happens in
the backend, full stop** — the same reasoning §14 applies to money, because a panel that sums rows
itself shows a number that disagrees with the database the moment a page is truncated; **"today" is
the country's day**, computed in the timezone stored on `notification_settings` (a UTC server
otherwise clips three hours off the start of an Amman day and adds three from yesterday); and
**"online now" counts live presence keys in Redis, not `drivers.is_online`** — the column says "the
switch is up", not "he is here", so an app killed mid-shift keeps its column raised until the key
expires.
**Stage 10's screens (the driver PWA, `driver-app/`) are
complete** — login/recovery, three-step registration, home with the offer card and active ride,
collect/rate/subscription, the ride log with details and dispute, the wallet with its withdrawal
sheet and request list, the account tab with settings/vehicle/cards, the notifications inbox and
the CliQ confirmation card. Do not implement
anything from a later stage unless the user asks for that stage. When a later-stage concern
appears in current code (e.g. no Celery job sweeps stale
`provider_orders` yet, no retention sweep trims `user_notifications`, and the campaigns page in the
admin panel lands in stage 11 while its endpoints already exist), leave a comment naming the stage
rather than building ahead.

**Any path that changes a row's status locks that row with `for_update` *before* it checks the
transition.** Reading the row, validating `current → target`, then writing is not atomic on its own:
under Postgres' READ COMMITTED default, concurrent requests all read the same pre-commit status,
all pass the check, and all report success. Load the row with `select(...).with_for_update()
.execution_options(populate_existing=True)` — see `topups.get_request` / `withdrawals.get_request`
(`for_update=True`) and `rides.cancel_ride` (`session.refresh(..., with_for_update=True)`).

**Lock order is always: the ride row, then the request/payment row, then the provider-order row,
then the driver row, then the wallet advisory lock.** Every mutating path takes them in that order,
which is why nothing deadlocks. **Two paths let the driver himself drop his own approval —
replacing a required document and editing a vehicle's identity fields — and both re-read
`drivers.status` under `drivers_service.lock` (a `refresh(..., with_for_update=True)`), never from
the object the router handed them.** What that lock owns is not duplicate work but a **cancelled
suspension**: an admin suspending a driver at the moment he changes his plate would otherwise have
`suspended` overwritten by a `pending` computed from an `approved` read before it, putting a
suspended driver back in the review queue — one approval away from working again.
`test_vehicle_update_concurrency.py` drives exactly that interleaving and fails when the lock is
deleted. In `documents.upload` the lock is taken **after** the document row's, not before, because
the driver row must not be held across an upload whose length the client dictates. Creating payments locks the ride (`payments._payable_ride`) so two
concurrent requests cannot both read the same outstanding amount; every status change locks its own
row (`topups`/`withdrawals.get_request`, `payments.get_payment` with `for_update=True`,
`rides.cancel_ride`); `card_payments._locked_order` locks the payment *before* the
`provider_orders` row, because the admin refund path starts from the payment and then needs its
provider order — reversing either side would deadlock the two against each other; buying a
subscription locks the driver row (`subscriptions._locked_driver`) before reading how far the
driver's coverage already extends, so two concurrent purchases produce consecutive periods rather
than two payments for one month — and the card path takes that lock *after* the provider-order row
because a webhook starts from the order; ledger writes take the wallet lock last. No path takes a
payment row lock and then a ride lock. When a single operation touches two wallets, their advisory
locks are taken in sorted UUID order (`wallet._lock_wallets`). Adding a new lock means fitting it
into this order, not inventing a second one.

Stage 8 added two mutating paths and both fit the same order. `cliq_topups.apply_state` locks the
provider-order row and then takes the wallet advisory lock (no ride and no payment row exist on a
wallet topup), and asks the acquirer *before* any lock in `reconcile`. `withdrawals.pay_via_provider`
is the deliberate exception to "never hold a row lock across a provider call": the call itself moves
the money, so it cannot run first — two concurrent clicks without the lock are two transfers, and the
lock's scope is one withdrawal row with a capped timeout.

Note which guard actually protects what: the driver row lock is redundant on the wallet purchase
path (the wallet advisory lock already serialises it) and is the *only* guard on the manual and
card paths, which write no ledger entry at all. That is why the concurrency test for it fires two
`POST /admin/subscriptions` at once rather than two wallet purchases — deleting the lock leaves the
wallet test green and turns the manual one's two consecutive periods into two identical ones.

**Never hold a row lock across a provider HTTP call when the call can happen first.**
`card_payments.reconcile` asks the provider *before* taking any lock, then applies the answer under
it: two concurrent settlements each spend one harmless extra `check` instead of one waiting out the
other's 20s network round-trip. Where the call genuinely must run inside the lock (opening an order
under the ride row lock in `card_payments._start`), the lock scope is a single ride and the timeout
is capped in `card_gateway/base.py`.

Do not let an idempotency key stand in for either lock. It bounds the financial damage, but a guard
that only works because the guard behind it also fired is a guard that has already failed — and
this exact defect shipped in stage 5 and was caught only by a concurrency test. Verify the tests
you write for a new lock by deleting the lock and watching them fail: dropping `with_for_update()`
from payment confirmation turns `Counter({200: 1, 409: 2})` into `Counter({200: 3})` while the
ledger still shows one entry, which is precisely the failure a passing sequential test would hide.

**A stage that touches money or state transitions is not done without a concurrency test.**
Sequential request-then-assert tests never enter the code path the locks exist for, so they prove
nothing about them. And write the test against the invariant the lock actually owns. Three concurrent `GET
/wallet/me/topups/cliq/{cart}` calls credit the wallet once *even with the row lock deleted* — the
ledger idempotency key and the wallet advisory lock already cover that — so that assertion proves
nothing about the lock. What the row lock alone owns is the order's **status**: `test_stage8_
concurrency.py::test_two_provider_answers_at_once_leave_a_coherent_order` drives a paid and a failed
settlement into a deliberately ordered interleaving (the first holds its transaction open while the
second starts) and asserts `paid ⇔ exactly one ledger entry`, `failed ⇔ none`. Delete the
`for_update` and it fails with a `failed` order whose money was credited.

Fire the requests together with `asyncio.gather` against the `client` fixture
(same event loop, separate session and transaction per request, so one really waits on the other's
lock in Postgres) and assert the invariant, not the timing: exactly N of M succeed, the losers carry
the *specific* error code, the ledger sum read straight from the database matches, and no
`balance_after` is negative. For deadlock, wrap the gather in `asyncio.wait_for` — a deadlock hangs
rather than raising, so only a timeout can fail the test. `tests/test_wallet_concurrency.py` is the
model to copy.

**User-facing strings, comments, and docs are in Arabic.** Identifiers stay English. Match this.

## Commands

Everything runs through Docker; there is no local venv. The compose project is named `taxo-app` and
the API is published on **8001** — an unrelated `taxo` stack and another service on 8000 exist on the
developer's machine. Never run `docker compose down --remove-orphans`; it would delete their containers.

```bash
docker compose up -d --build          # db + redis + backend + worker + beat (backend runs alembic upgrade head on boot)
docker compose logs -f backend
curl http://localhost:8001/health     # reports db + redis status; also the container healthcheck
```

**Two operational facts that bit this session.** A migration that adds an **ENUM value** needs the
running backend *recreated*, not just migrated — asyncpg caches the type per connection, so
`alembic upgrade head` alone leaves the live container answering `invalid input value for enum`. And a
migration that adds a **column with a default** leaves existing rows at that default while
`scripts/seed.py` (idempotent by design) skips them: after `0022` both countries' tip amounts are
zero, which reads as "not configured" and correctly hides the feature — so on an existing install the
amounts are set in the panel, not by re-seeding.

**A change to `requirements.txt` needs `docker compose build backend` *and then*
`docker compose up -d backend` — never `restart`.** The source tree is bind-mounted, so code edits are
picked up live and it is easy to assume dependencies are too; they are not. `restart` starts the same
container from the same image, so a newly declared package is simply absent. And **the test suite will
not catch it**: `docker compose run` builds a fresh container from the image each time, so tests pass
against the new dependency while the long-running service still crashes on it. This shipped once —
stage 9-ب added `python-multipart`, the suite went green, and the running backend answered every
request with `RuntimeError: Form data requires "python-multipart"` until the container was recreated.
Same rule for `worker` and `beat`: they run the same image.

**And `docker compose run` inherits `restart: unless-stopped` from the service, so a detached test run
restarts itself forever.** `docker compose run -d --rm ... backend pytest -q` looks like a background job
that ends with a verdict; what actually happens is that pytest exits, Docker restarts the container by
policy, **pytest starts over, and `docker logs` is truncated to the new run** — so the summary line
appears, vanishes, and the suite silently re-runs from zero. It cost two "the result disappeared" rounds
in one session, and the symptom reads exactly like a killed job. Two ways out: run it in the foreground,
or make the result outlive the container — `sh -c "pytest -q >> /app/.suite.out 2>&1"` writes into the
bind-mounted tree, so the verdict is on the host whatever the container does afterwards.

**These three are one family, and it is worth reading them together**: a `restart` that keeps the old
image (so a new dependency is missing), a bind mount that inotify cannot cross (so Vite serves the module
it read at startup), and a `run` that inherits a restart policy (so a finished test run starts again).
**Each one makes the container look like it did what you asked while it did something else**, and none of
them produces an error message — which is why every one of them was found by measuring the running
system, not by reading the compose file.

`driver-app` (stage 10) is the captain PWA on **5174**, same shape as `customer-app` — a
`node:22-alpine` container running Vite, `node_modules` in a named volume. Its
`tailwind.config.js` is copied verbatim from `design/DESIGN.md` §6, which is the source: scale keys
are pixel values (`text-14.5`, `p-16`, `rounded-13`) and Tailwind's own scales are **replaced, not
extended**, so `text-sm` or `p-4` is a build error rather than a silent drift to the nearest default.
Dark is the default and does not follow the system — a captain works for hours with the screen in the
car, and a theme that flips at sunset whitens his screen in a tunnel.

**`overflow-x-auto` on a bar that contains a hover menu is a clipping bug waiting to happen.** CSS
computes the *other* axis to `auto` when one axis is `auto` (`visible` becomes `auto`), so the panel's
nav strip silently became a vertical clipping-and-scrolling box and its 130px dropdown was cut
entirely — measured as `scrollHeight 172` inside `clientHeight 42`, which made the browser draw a
vertical scrollbar (on the **left** edge in RTL). There is no `overflow-x: auto` with
`overflow-y: visible` in CSS, so the fix is structural: `flex-wrap` instead of a scroll container.
Judge this class of bug by measuring in the browser (`getComputedStyle().overflowY`,
`offsetHeight - clientHeight`, `elementFromPoint` at the menu's edge), never from a screenshot — and
note that `scrollHeight` on a `visible` box reports content bounds without anything being clipped, so
it is the wrong probe for "is this cut off".

**`lib/utils.ts::cn` configures `tailwind-merge` with this project's font-size scale, and that is
not optional.** tailwind-merge knows Tailwind's default scales, not ours: our sizes are pixel-named
(`text-14.5`), not t-shirt-named, so it does not recognise them as font sizes and files them under
*colour* — and then `cn("text-14 text-accent-ink")` drops one of the two at runtime. It shipped
twice before it was caught: the bottom-nav label lost its 9.5px, and the wallet's "طلب سحب" button
came out with an **invisible label** (the size ate `text-accent-ink`, so light text landed on a
light fill). The build is green either way and `check:scale` cannot see it — the class is spelled
correctly and is present in the CSS; what deletes it is the merge at runtime. `check:scale` does
guard the list itself against drifting from `tailwind.config.js`.

The pixel scale stops you writing the *wrong* value; `npm run check:scale` (wired into
`npm run build`) stops you writing a *missing* one. A class whose key is absent from the scale —
`size-33` when 33 is not in `spacing` — is not an error to Tailwind: it emits nothing, the element
comes out with no size at all, and the build stays green. That shipped once in the first session that
built the home screen, four classes deep. The script reads the scales from `tailwind.config.js`
itself, so it cannot drift from them.

**`screens/Collect.tsx` is the screen where a wrong word costs a driver money**, and its whole job is
to keep two amounts apart: what he is taking *in his hand right now* and what *landed in his wallet*.
The distinction is a rule in the schema, not a presentation choice — cash and CliQ are
`DIRECTLY_COLLECTED_METHODS` and write **no** `ride_earning` at all (the money never passes through
the platform), while wallet and card credit the full fare; and commission is debited from his wallet
in *both* cases, so a cash ride can leave his balance lower than it started. So the big number always
carries a caption naming which of the two it is ("تقبض الآن من الراكب" / "أُضيف إلى محفظتك"), the
breakdown splits the two only when a ride actually has both parts, and the footnote states where the
money lives *before* it mentions disputes.

**The dispute button lives on a CliQ payment awaiting confirmation, and nowhere else.**
`payments.dispute_by_driver` refuses every other method, so `screens/RideDetails.tsx` gates the CTA
on exactly that pair (`method === "cliq" && status === "pending"`) and
`screens/Dispute.tsx` re-reads it rather than trusting the caller. The design draws the button on a
cash ride with cash-flavoured reasons; a driver who was never handed cash simply does not press
"استلمت المبلغ كاش", and the payment stays `pending` where the admin can see it. The
three reasons were rewritten for CliQ for the same reason — the backend takes free text, so a reason
that describes an impossible situation would land verbatim in the admin's queue.

**Arabic-Indic digits are for quantities, not identifiers.** `arabicDigits` converts fares,
distances, counts and dates; a plate number, a card's last4 and expiry, a CliQ reference and a
payout reference are printed on something the driver is holding, and he compares them character by
character — converting those makes him match a string against a differently-shaped one. The rule is
written into `screens/Cards.tsx` and `screens/Vehicle.tsx` where the two kinds sit next to each
other.

`admin-panel` (stage 11) is the operations panel on **5175**, the third origin in
`settings.cors_origins`. It shares the design system verbatim — the same `tailwind.config.js`,
the same `check:scale` and `check:enums` guards — and the same dark-first default the prototype
starts in, with a toggle in the header. Three things differ from the two PWAs and are deliberate:
no device registration (a desk panel receives no push), no WebSocket at all (see the live map
below), and a **country switch in the header** that narrows what every screen shows — display state
in `sessionStorage`, so two tabs on two markets do not fight.
One backend rule the panel made visible: **`/admin/drivers/{id}/activate` goes through
`drivers.approve`, not a bare status write** — otherwise suspending and reactivating a driver would
be a way around the verified-phone and approved-documents guards, and the shortest path to a driver
working with no licence on file. The drivers screen reads those two guards *before* enabling its
approve button and names what is missing, because a button that works and then bounces teaches the
admin to retry, while a disabled button that says why teaches them to fix.

**`support` sees less than `admin` in the UI, and that is comfort, not protection**: every admin
route enforces the role server-side (SPEC §13/8), and hiding a button never prevented a request.

**`GET /admin/live/map` is the only route in the project that pairs an identity with a location**,
and three rules follow from that. It is `AdminUser`, not `StaffUser` — the one read in the panel
that support cannot make, because nothing in handling a dispute needs to know where every driver is
standing right now. Opening it **writes an audit entry** (`AuditAction.READ` on `live_map`, the
only `read` the project records), throttled by a Redis key in `live_map.record_access` so a
monitoring session is one row rather than the two hundred an auto-refreshing screen would write in
an hour. And the rider-facing paths were not touched: `drivers.nearby_available` +
`anonymous_ref` and the `nearby_drivers` socket frame stay anonymised per SPEC §10, which is why
`live_map.drivers_now` is a **separate function with a separate schema** rather than the same one
with an `include_identity` flag —
`test_admin_live_map.py::test_rider_facing_paths_still_carry_no_identity` sees the same driver
named in the panel and pseudonymous to the rider, and any later "simplification" that merges the
two will fail it. The screen also has no "assign driver" button: dispatch offers a ride to one
driver at a time, so a panel button that jumps the offer is FUTURE-FEATURES item 27, not a
convenience.

`LiveCanvas.tsx` is the only file in the panel that imports `mapbox-gl`, and two traps in it both
produce a *silent* failure. A `Marker` must be given `setLngLat` **before** `addTo` — `addTo` draws
immediately and reads the marker's coordinates, so a marker added without one throws inside an
effect and React blanks the whole screen (the panel has no error boundary). And the element you
hand a `Marker` **belongs to mapbox**: it adds `mapboxgl-marker` (which carries
`position: absolute`) to that element's class list, so writing `element.className = …` on it drops
the marker out of the map into normal flow — no console error, just no marker. Both are why the
visual styling lives on an inner child and the outer shell is never touched. Neither shows up in
`npm run build`; both were caught by opening the screen.

**Vite in these containers does not see host edits.** The source tree is bind-mounted from Windows
into alpine and inotify does not cross that boundary, so HMR never fires and the dev server keeps
serving the module it read at startup — a fix can look like it did nothing for as long as you care
to test it. `docker compose restart <app>` before every browser check, and confirm with
`curl http://127.0.0.1:5175/src/<path>` that the served text contains your edit. (The earlier note
that `public/dev-login.html` only appears after a restart was this same fact, seen through one file.)

Its refresh is a **5s poll, not a socket** — `ws/` publishes per-user channels, and a
country-wide one would mean streaming everyone's position into an open connection to answer a
question that is only ever "where are they now".

**The panel reads; it does not invent a second place to decide.** Four screens deliberately have no
button where a design or a habit would put one, and each absence has a reason that outlives it:
`Rides.tsx` has no cancel/refund/assign — a refund is a decision **on a payment row** (one ride can
carry two, so a ride-level button would not know which), cancelling names its actor in the status
itself (`cancelled_by_rider` / `..._by_driver`, and an admin is neither), and manual assignment is
`FUTURE-FEATURES` 27 because dispatch offers to one driver at a time. `Pricing.tsx` has no
commission field — `commission_settings` is its single source and lives in `Settings.tsx`; two
screens writing one money rule is two states that can disagree. `Users.tsx` renders the permission
matrix **read-only**: `UserRole` has two staff roles, `core/deps` enforces them, and a clickable
cell would become a second source of truth that the guard ignores. `Audit.tsx` has no write path at
all — entries are written by the transaction that made the change.

**Aggregation stays in the backend even when it is only a count.** `services/stats.py::reports`
returns `avg_ride_fare` and `cancellation_rate` already divided, because numerator and denominator
are both summed over the whole table: dividing two capped page-loads in the browser yields the
average *of the page* under a label that says "of the month". Same reasoning as §14 for money.
`services/ride_log.py::payment_summaries` is the shape that rule takes for lists — a **second
query** over the same ride ids rather than a join, because joining payments multiplies a mixed-payment
ride into two rows and a page of fifty silently becomes a page of forty-nine rides.

Three shared pieces were added with these screens and are worth reusing rather than re-deriving:
`components/ui/Badge.tsx` (the one rule from `DESIGN.md` §2.6 that generates every panel badge,
taking a **tone** not a status — ride, payment, subscription and audit states all share five tones),
`Checkbox`/`Select` in `components/ui/Field.tsx`, and `lib/format.ts` (`money`, `moment`, `day`,
`currencyLabel`). The checkbox is a `role="checkbox"` button, not a styled `<input>`, because
`accent-ink` resolves to the palette's `accent-ink` colour (`--inv`) rather than to "accent-color:
var(--tx)" — a name collision that paints the box the background colour.

`customer-app` (stage 9) is the rider PWA on **5173** — a `node:22-alpine` container running Vite.
The **container** port is not interchangeable: it is in `settings.cors_origins` and
`settings.card_return_url` points at `/payments/card/return` on it. Only the host publish is
overridable, via `CUSTOMER_APP_PORT` (default 5173, and **5176** is the one documented fallback in
`cors_origins`) for machines where something else already holds 5173. Its `node_modules` lives in a
named volume because the host is Windows and the container is alpine. Frontend commands run on the
host (node 22+):

```bash
cd customer-app && npm install
npm run build     # check:scale + check:enums + check:config, then tsc -b, then a production build
npm run lint      # tsc --noEmit alone
npm run dev       # if you'd rather not use the container
```

**Stage 12-أ migrated it onto the design system**, so all three frontends now share one
`tailwind.config.js` (a verbatim copy of `DESIGN.md` §6), one palette, and both guards — and the
`cn` in each carries the pixel font-size scale, without which tailwind-merge silently drops classes.
Two consequences are worth knowing before touching a rider screen. **The yellow is gone**: §1.1 has
no brand colour, `--brand` defaults to `--tx`, and the app is charcoal/white unless the pink theme
is on — that is what the design system says, not a regression. And **colour tokens are hex in a CSS
variable, so `bg-brand/40` no longer works at all**; where the old palette used alpha, the system
has `--brand-soft` / `--sur2` / `--sa`, and reaching for opacity is a sign you want one of those.

There is no frontend test runner: stage 9 added no business logic to test — pricing, balances and
state transitions all stay in the backend, and the app displays what the API returns. `npm run
build` is the check that runs, and it type-checks every file.

`worker` and `beat` are the Celery pair from stage 7 (`app/tasks/`), running **eight** periodic jobs:
the subscription sweep and the CliQ-confirmation sweep every five minutes; the stage-8 campaign
dispatch, the multi-stop wait cap and **due bookings** (12-ط) every minute; the referral-bonus payout
(12-ح) every ten; and the two stage-12 maintenance jobs — the stale-provider-order sweep and the inbox
trim. **Run exactly one `beat`** — a
second scheduler fires every period twice. The worker process has no event loop of its own, so
`celery_app.run_async` keeps one loop per process: a fresh loop per task would strand the asyncpg
pool bound to the previous one. Tasks are thin wrappers over `services/`, and the tests call the
service directly — nothing in the suite needs a worker running.

Tests and Alembic run in one-off containers. `--no-deps` avoids restarting healthy services, and the
two env vars redirect the container from the `.env.local` localhost URLs to the compose hostnames:

```bash
DC_RUN='docker compose run --rm --no-deps
  -e DATABASE_URL=postgresql+asyncpg://taxo:taxo@db:5432/taxo
  -e REDIS_URL=redis://redis:6379/0 backend'

$DC_RUN pytest -q
$DC_RUN pytest tests/test_auth.py::test_refresh_rotates_and_invalidates_old_token   # single test
$DC_RUN alembic revision --autogenerate -m "message" --rev-id 0004                  # sequential rev ids
$DC_RUN alembic upgrade head
$DC_RUN alembic downgrade 0001
$DC_RUN python -m scripts.seed                                                     # dev settings + provider tokens
$DC_RUN python -m scripts.totp_reset --phone +962790000000 --release-enforcement   # 2FA escape hatch (12-د)
```

**`scripts/totp_reset.py` is not a convenience; it is the reason enforcement is allowed to exist.**
Once `admin_totp_required` is on, an admin who loses both the phone and the recovery sheet cannot
turn his own factor off from inside the panel (that refusal is what makes enforcement enforcement) —
so without a door outside the network this would be the one unrecoverable fault in the platform.
It writes an audit entry with **no actor** (the actor is a human on the server, and a row naming
someone who did not act is worse than a row naming nobody), revokes every session, and writes the
account's owner an inbox row. `--release-enforcement` also drops the global switch, for the case
where no admin holds a working factor any more.

### Five accounts exist on the dev stack, and the visual checks need them

These live in the local Postgres only, they are **never** to be created anywhere a browser other than
this machine's can reach, and the shared password `TaxoTest123` is written down here for exactly that
reason: it is worth nothing outside a container on one desk, and rebuilding four accounts by hand at
the start of every session costs an hour.

| phone | who | state |
| --- | --- | --- |
| `+962790000000` | مشرف التطوير | `admin` — the panel |
| `+962790000011` | زيد السائق | driver, `approved` (three documents), male |
| `+962790000012` | هناء السائقة | driver, `approved`, **female with `gender_verified_at` stamped** |
| `+962790000021` | عمر الراكب | rider, male |
| `+962790000022` | ليلى الراكبة | rider, **self-declared female** (the pink theme and privacy note) |

Two operational traps around them, both of which cost time this week. **Login is rate-limited per
phone, and polling it does not extend the window — it only keeps you locked out**; the limiter's Redis
key must be deleted **inside** the container (`docker compose exec redis redis-cli`), because a
Windows shell appends `\r` to the key name and deletes nothing. And **a 429 must never fall through to
a registration attempt**: that is how a session ends up creating a second account on a number that
already has one, with a password neither half remembers.

**The visual harness is worth rebuilding the same way each time**: Playwright driving the *installed*
Edge (`channel: "msedge"` — no browser download), with
`args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]` so `mapbox-gl`
renders headless. One helper that logs in and caches tokens into `localStorage`
(`taxo.access_token` / `taxo.refresh_token`, and `taxo.driver.*` for the captain app), one script per
package printing `✓/✗` per assertion, and screenshots in **both** themes. Keep it in the scratchpad,
not the repo: it asserts against a database state that only exists here.

**And read the API's actual shape before asserting on it.** Three of this week's "missing" features
were my probe's error, not the app's: `GET /rides/me` returns `{ride, has_open_dispute,
payment_methods, paid_amount}` with the ride **nested**, `RideOut` carries the captain as a nested
`driver` object rather than a `driver_id`, and `customer-app` has **no `arabicDigits` at all** (its
digits are Latin by convention). When a check reports "no data to test this", suspect the probe's
shape before believing the absence.

Postgres does not drop ENUM types with their tables, so every migration that creates one must
`DROP TYPE IF EXISTS` it in `downgrade()` (see `0002_users_drivers_vehicles.py`) or a re-upgrade fails.
Autogenerate also re-emits `CREATE TYPE` for enums an *earlier* migration already created; hand-edit
those references to `postgresql.ENUM(..., create_type=False)` as `0003` does, or `upgrade` fails with
"type already exists". Adding a *value* to an existing enum is `ALTER TYPE … ADD VALUE IF NOT EXISTS`
(`0009`), and Postgres forbids **using** that value later in the same transaction — so the check
constraint that pairs `provider_orders.plan_id` with `purpose = 'subscription'` compares
`purpose::text`, which never resolves the literal to the enum type and therefore ships in the same
migration as the column. Enum values cannot be removed on downgrade; the type itself is dropped by
whichever migration created it, so `IF NOT EXISTS` is what makes a partial downgrade re-upgradable. Because the downgrade/upgrade cycle gives the enums new OIDs,
`test_downgrade_then_upgrade_is_clean` ends with `engine.dispose()` — without it asyncpg's per-
connection type cache poisons every later test with "cache lookup failed for type".
`tests/test_migrations.py` enforces this: it runs the full `downgrade base → upgrade head` cycle, and
`test_migrations_match_models` fails whenever autogenerate finds a difference between the models and
the applied migrations — so a model change without a matching migration breaks the suite, and the
failure message names the drifting column.

Reflection in both `alembic/env.py` and that test goes through the shared
`app/core/migration_filters.py::include_object`; the postgis image puts `tiger` on the search_path, so
without it autogenerate proposes dropping the extension's own tables. Keep the two using one filter.

Tests create and drop a separate `taxo_test` database and use Redis db 15; `tests/conftest.py`
rewrites `DATABASE_URL`/`REDIS_URL` **before** importing the app, so any new import in conftest must
stay below that block. The test schema is built by `alembic upgrade head` (run via `asyncio.to_thread`
because `env.py` calls `asyncio.run`, which cannot nest inside the test event loop), never by
`create_all`.

## Architecture

`backend/app` is layered: `routers/` are thin HTTP wrappers, `services/` hold all business logic,
`models/` are SQLAlchemy 2 async, `schemas/` are Pydantic v2. `ws/` is the realtime layer (channels,
events, sockets); `tasks/` holds the Celery app and its periodic jobs, each one a thin wrapper over
a service.

**WhatsApp is the third verifier (12-هـ), and the priority chain changed with it.** It is now
`whatsapp_otp ← sms_otp ← firebase ← none` — the owner reversed the old Firebase-first order, and the
consequence is explicit: **an active Firebase contract goes unused while any contract ahead of it is
active**, so whoever wants Firebase turns off what precedes it. Four rules travel with the channel.
**Only the official Meta API** (WhatsApp Cloud API over Graph) — never `whatsapp-web.js`, `Baileys`,
or anything like them: those automate a personal account through the web interface, which violates
WhatsApp's terms and is punished by banning the number, i.e. new-user signup stops platform-wide,
without warning, from a number nobody can get back. **The contract is global while the flag is
per-country** — one business number serves both markets and the phone carries its own country, so the
contract says "we can" and `whatsapp_otp_enabled` says "we do here"; that is also why this provider
has no `feature_key` in the registry (the auto-sync would light up the *contract's* country, and this
contract has none). **Authentication templates take no free text** — the template is pre-approved at
Meta and we pass one parameter, the code — which is why `services/otp.py` now asks for an
`OtpSender.send_code` instead of composing the body itself: an interface that accepts text would lie
to its caller. And **a failed send never switches channel silently**: the code may in fact have
arrived, and a silent switch makes someone read a code from one channel and type a code from another,
burning both. The request bounces 502 carrying `fallback_channel`, and the app draws that button.
Verification itself is one door for every channel — the digest is stored **by phone, not by channel**
— because binding it to the channel would make the fallback itself invalid.

**A bug found while wiring that fallback, and fixed in all three frontends**: the backend's error
body is `{code, detail}` (see `core/exceptions.py`) and every client read `body.message`, so **every
Arabic error message the backend wrote was being replaced by the client's own generic fallback**. The
documented rule ("the app never writes its own Arabic for an error the backend already named") was
written and not running. `ApiError` now reads `detail` first and keeps the whole body in `extra`,
which is what lets `fallback_channel` reach the button.

**Login is always a password, and TOTP (12-د) does not change that — it adds a second step, never a
second method.** `POST /auth/login` still takes only a password; if the account has a *confirmed*
factor it answers `{totp_required: true, challenge_token}` **with no tokens at all**, and
`POST /auth/login/totp` is the only place a session is issued. The challenge is a random value in
Redis bound to the user for five minutes and single-use — deliberately **not** a real access token
with a reduced scope, because such a token becomes a full session the moment one guard is wrong. The
two-step shape mirrors password reset ("no token until the new password is actually written"), and
the second step accepts a **recovery code** as well as a code, because someone who lost the phone is
exactly who those codes exist for. `require_roles(..., enforce_two_factor=False)` is the one
exemption and it is an explicit argument, not a path match: without it "enroll a factor" would sit
behind a door that only opens for accounts that already have one.

**Login is always a password. OTP is verification, not a login method.** That distinction is the
whole shape of `services/auth/` and `services/verification.py`, and it replaced an earlier design
where the active contract chose *how you log in*. Two login methods meant two contradictory answers
to "how do I sign in": an account created under OTP has no password and stops working when the
contract is switched off, and one created under a password is never asked for it when the contract is
switched on. So login is fixed and the contracts govern **verification**, which is where differing
providers actually help.

Proving you own a phone happens exactly twice in an account's life — at signup (then you set your
password) and at password reset. `services/verification.py` is the single decision point: an active
`firebase_auth` contract wins, else an active `sms` contract, else nothing. Firebase first because it
is the strongest proof and the cheapest to run; the order is not configurable, because a switch
saying "which one first" is a second piece of state that can disagree with the contracts themselves.
`OtpAuthStrategy` was deleted as a login method but `services/otp.py` was not: the SMS provider became
the *second verifier*, so code generation, the HMAC digest, the attempt counter and the resend
cooldown all still earn their keep. `COOLDOWN_KEY` is public precisely so a test can fast-forward the
minute instead of sleeping it.

The proof travels in its own `verification_token` field, never in `password` — the password is set in
the same signup request, so one field cannot carry both. Password reset is a separate path that
**issues no token until the new password is actually written** (a proof that opened a session would
leave the attacker something if the request died right after it), revokes every refresh token for
that user, and is capped **daily** rather than hourly: taking over a specific account is not a race,
and an hourly window hands out 120 attempts a day.

`users.phone_verified_at` is the record of that proof. It is only ever NULL when an admin turned the
`otp_verification_enabled` guard off, and such accounts stay flagged and filterable in the panel
(`GET /admin/users?phone_verified=false`). **Driver approval requires it regardless of the flag** —
a driver's phone is where CliQ transfers land, so approving one we cannot prove owns it is sending
money to an unknown number. `services/drivers.approve` is the only door that sets `approved`.

**Every external provider follows one shape, and `card_gateway` is the template.** `services/sms/`,
`services/push/`, `services/cliq/` and `services/payout/` each carry `base.py` (the contract),
`mock.py` (enabled by `use_mock` on the contract, refused in production), exactly one file that knows
the real provider's wire format, and an `__init__` that is the single decision point reading the
encrypted contract. Because no contract was delivered for SMS/CliQ/payout, those wire details are
best-reading-of-the-common-shape and say so in their module docstrings, grouped into named constants
like `telr.py`'s. Two of the four expose `get_*_or_none` rather than raising: an absent FCM or CliQ
contract is the normal state, not an outage, and must never fail the request that triggered it.

`services/providers/health.py` is the one place that knows which call tests which provider, and each
provider answers from its own `test_connection`. A test must leave no trace — no order opened, no
payout sent, no paid SMS unless the admin typed a number — it runs on inactive contracts (you test
before you open the door, not after), it returns 200 with `ok=false` on failure because the admin
asked to know, and it stamps `last_tested_at` either way: the question is when it was last tested,
not when it last succeeded.

**Provider contracts are the only home for external keys.** `services/providers/registry.py` declares
each provider's fields (`secret` → encrypted + masked as `****` and never leaves the backend;
`expose_to_clients` → published by `GET /config`, e.g. the Mapbox pk). `services/providers/credentials.py`
is the only module that touches the table: the `credentials` column is a Fernet envelope
`{"v": 1, "ciphertext": …}` over the whole value dict, and re-submitting `****` for a secret keeps the
stored value instead of wiping it. Activating a per-country contract auto-syncs its `feature_key`
flag. Read secrets with `credentials.get_values(session, ProviderKey.X, country)` — never from `.env`.

**Every admin write records an audit entry** via `services/audit.py` in the *same* transaction, and
`details` carries changed field names only, never values. The deliberate exception is a **written
reason** — driver suspension, blocking a user, switching off a guard flag: that string is the whole
point of the entry, and it is a supervisor's decision, not a stored secret.

**`is_blocked` has exactly one door** (`admin_users._set_blocked`, admin-only, reason required,
row locked before the write). No session revocation runs with it and none is needed:
`core/deps.get_current_user` and `auth.refresh` both read the column on every request, so a block
lands on the live token — adding a revoke here would suggest the protection comes from it. Staff
accounts are refused by that door on purpose; SPEC §13/3 is about riders, and it must not become
the way one admin closes another out.

**Phone number is the login identity and is always stored as E.164.** `core/phone.py` normalizes on
every write and read path (`normalize_phone` with an explicit country, `resolve_phone` when the
client omits one). Never query `users.phone` with raw client input.

**Sessions do not auto-commit.** `get_session` only rolls back on exception; routers/services commit
explicitly. This is deliberate — stage 5's ledger requires multi-write atomic transactions.

**Errors** are domain exceptions from `core/exceptions.py` (`AppError` subclasses carrying
`status_code`/`code`/`message`), translated to a uniform JSON body by a handler registered in
`main.py`. Raise those, not `HTTPException`.

**JWT**: short-lived access token plus a refresh token whose `jti` lives in Redis. Refresh is
single-use rotation — `rotate_refresh_token` deletes the key and rejects replay. Access tokens cannot
be revoked before expiry; account-level revocation goes through `revoke_all_for_user`.

Enums are Postgres native types created via `models/base.py::pg_enum`, which stores the lowercase
`.value` rather than the member name. Reuse it for every new enum column. `feature_flags.feature_key`
is the deliberate exception: a plain `String(64)` guarded by the `FeatureKey` enum in the schema layer,
so stage 12's flags need code only, no migration.

**"Absence means disabled" has exactly one exception, and it is not a feature.**
`settings_service.DEFAULT_ENABLED_FLAGS` lists *guard* flags — today only `otp_verification_enabled`
— whose absent row reads as **enabled**. The original rule exists so a money feature is never switched
on by silence; a guard is the mirror image, where silence would switch a protection *off*. Turning
that flag off is admin-only and requires a written reason that lands in the audit log, it exempts
**signup only**, and it never touches password reset: if it did, disabling it would become a way to
take over any account by knowing its number. Do not add feature flags to that set.

Money columns use `models/base.py::MONEY` (`NUMERIC(12,3)`); currency is derived from the country via
`core/currency.py::currency_for_country` and is never accepted from a client.

**Multi-stop (12-ب) lives inside that same door, and four details are worth knowing before
touching it.** `at_stop` sits between `in_progress` and itself, with a third exit to `completed`
for the wait cap; it is in **both** `ACTIVE_*_STATUSES` (a rider waiting at his stop is not free to
order another ride), which is why migration `0018` rebuilds the two partial unique indexes.
That migration is also where two Postgres traps met: `ALTER TYPE … ADD VALUE` cannot be used in the
same transaction, and the `::text` cast that `0009` used to dodge that in a CHECK is rejected in an
**index predicate** (`functions in index predicate must be marked IMMUTABLE`). Since `env.py` wraps
the whole chain in one transaction, splitting into two files would not help either — so `0018`
issues an explicit `COMMIT` after the `ALTER TYPE`, and everything after it is written
`IF NOT EXISTS` because that commit means a later failure no longer rolls back.

**`current_leg` has exactly one writer** (`rides.resume_from_stop`, under the ride row lock) and
`route.capture` copies it onto each point. Deriving the leg by counting resumed stops would put a
COUNT on a path that runs every 20s per active ride; letting the capture guess would put a second
writer on a value that must not disagree with itself.

**Waiting is measured from `ride_stops.arrived_at`/`resumed_at` and nothing else** — no
`waited_minutes` column, because two columns for one duration diverge. The amount is always
computed in the backend (`pricing.waiting_charge`, at the rates frozen on the ride); the app renders
the running clock from `arrived_at` locally. Showing elapsed time is a time calculation and showing
money is a money calculation — §14 only forbids the second. Free minutes are **per stop**: someone
who waited two minutes at each of two stops kept nobody waiting four minutes.

**A new `RideStatus` value has to be added to four lists, not one**, and the two the compiler
cannot see are what the visual pass caught. `models/ride.py` has `ACTIVE_RIDER_STATUSES` and
`ACTIVE_DRIVER_STATUSES`; the rider app has `ACTIVE_RIDE_STATUSES` in `lib/labels.ts` and the driver
app has `ACTIVE` in `lib/ride.tsx`. Both frontends are `RideStatus[]`/`Set<string>` — not string
unions — so `check:enums` and `tsc` are both blind to a missing member. With `at_stop` absent, the
rider saw the *ride-ended* sheet and the driver was returned to «ابدأ الاستقبال», both while the car
was standing at the stop with the passenger in it. Nothing failed; the screens simply lied.

**The cap notifies and never ends the ride.** `tasks/stops.py` runs every minute, stamps
`notified_at` under the row lock so two workers cannot double-notify, and sends *different* text to
each party (the rider learns the meter is now charging, the driver learns he has an exit) — which is
why it has its own notifier like the CliQ expiry rather than a `RIDE_EVENT_TEXT` entry. Ending is
the driver's act; a periodic task that completes a ride on a human's behalf does something nobody
reviewed.

**Ride state changes go through `services/rides.py`, never a router.** Every transition is checked
against `ALLOWED_TRANSITIONS` before it is applied; routers only resolve who is allowed to ask.
`models/ride.py` owns the status groupings (`ACTIVE_RIDER_STATUSES`, `ACTIVE_DRIVER_STATUSES`) and
builds the partial unique indexes `uq_rides_active_rider`/`uq_rides_active_driver` from those same
tuples, so the database enforces "one active ride" even under a race and the service just turns the
`IntegrityError` into a readable Arabic error.

`rides.pickup_point`/`dropoff_point` are GeoAlchemy2 `geography(POINT,4326)` columns. Latitude and
longitude are exposed as `column_property` expressions (`ST_Y`/`ST_X` over a cast to `geometry`), so
they are computed by Postgres and arrive with any `select(Ride)` — but **an UPDATE expires them**.
That is why the mutating helpers end with `_flush_and_reload`: without it, serializing the ride
triggers a lazy load outside the async context and raises `MissingGreenlet`. Newly inserted rides
need the same reload before serialization.

Pricing lives in `services/pricing.py` and the Mapbox call in `services/directions.py`, which reads
the `sk` token from `provider_credentials` — never `.env`. Tests monkeypatch the single
`directions.fetch_route` seam so token resolution stays real while the network call does not happen.

**A ride is offered to one driver at a time; nobody else can accept it.** `POST /rides` commits,
then `dispatch.start(ride_id)` launches an asyncio task (not Celery — the rider is waiting on
screen) that flips the ride to `searching` and offers it to the nearest eligible driver for 20s,
then the next, until 5 attempts or 2 minutes produce `no_driver_found`. Those three numbers are
SPEC rules, so they are module constants in `services/dispatch.py`, not settings; the test suite
monkeypatches them. Offer state lives in Redis (`dispatch:offer:{ride_id}`,
`dispatch:driver_offer:{driver_id}` written with `NX`), so `accept_ride` validates the offer no
matter which worker serves the request, and `dispatch:signal:{ride_id}` is a list the dispatcher
`BLPOP`s so an accept or decline wakes it instead of burning the rest of the timeout. Every state
change the dispatcher makes reloads the row `with_for_update()` first — otherwise it would write
`searching` over a cancel that landed in between. `ALLOWED_TRANSITIONS` no longer contains
`requested → accepted`: acceptance is only reachable through an offer.

**A driver's subscription is a question about the clock, not a column.**
`services/subscriptions.py::coverage_condition` is `status = 'active' AND starts_at <= now() AND
expires_at > now()`, and `dispatch.eligible_driver_ids` (which the rider's map also calls) embeds it
as an EXISTS. The Celery sweep marks expired rows every five minutes, but eligibility never waits
for it — reading the status column alone would hand a ride to a driver whose period lapsed four
minutes ago. Renewal is a new row (SPEC section 4), and an early renewal *stacks*: `_create` starts
the new period at `coverage_until` — the **max** `expires_at`, not the newest row — so nobody loses
the days they already paid for, and "when does my subscription end" is that same max everywhere
(counter, 24h notice, sweep). Only the wallet channel writes a ledger entry
(`subscription_payment`); cash, CliQ and card money never passes through the driver's wallet, which
is the same asymmetry `WALLET_FUNDED_METHODS` draws for ride payments. The sweep leaves a driver
who is mid-ride online — dropping his presence would cut his rider's map and fire the section 5
"driver disconnected" alert at someone who never disconnected — and the 24h notice is deduplicated
by a Redis key rather than a column, because a notification is an event, not a record.

**Live driver locations are Redis-only, never a column.** `services/geo.py` keeps a per-country GEO
zset plus a `geo:presence:{driver_id}` hash carrying heading and vehicle category. The hash has a
60s TTL and the zset cannot (Redis has no per-member TTL), so a member whose presence hash is gone
counts as silent and is pruned lazily by the next `nearby()` call. A driver is dispatchable only
after `is_online` **and** a first location broadcast.

**`ws/` publishes nothing directly to sockets — it publishes to Redis pub/sub.** `ws/events.py`
owns the channel names and the `RideEvent` enum; routers call `publish_ride_event` **after**
`session.commit()` (before it, an announced state could still roll back), and each socket in
`ws/routes.py` subscribes to its own `ws:user:{user_id}`. That is what lets more than one uvicorn
worker run with no shared in-memory registry. Rider sockets additionally subscribe to
`ws:driver_location:{driver_id}` only for the driver the database assigned them. WebSocket auth is
`?token=` rather than a header because browsers cannot set headers on a WebSocket handshake.

**Uploaded documents are the only user-supplied bytes the backend stores, and `core/storage.py` is
the only module that touches the filesystem.** Three rules live there and nowhere else: the filename
is server-generated (`uuid4` + an extension derived from the content, so the client's name never
reaches a path), the type is decided by the magic bytes rather than the `Content-Type` header the
client writes, and the size cap is enforced by reading in chunks rather than by trusting
`Content-Length`. Stored paths are relative to the storage root, and every read goes through
`resolve()`, which refuses anything that escapes it. Files are never served by a static mount:
`routers/drivers.document_response` checks ownership first and answers with `nosniff` +
`private, no-store`. Order matters in both directions — the file is written *before* its row, and a
superseded file is deleted *after* the commit: an orphan file is litter, a row pointing at nothing
is a visible fault.

`services/documents.py` owns document state. Re-uploading a `doc_type` replaces its row (unique on
`(driver_id, doc_type)`) and resets it to `pending`; `review` takes the row lock **inside the
service, not in the router** — a guard each new caller has to remember is a guard that will be
forgotten, and no test can own it. `tests/test_driver_documents_concurrency.py` calls the service
with two sessions in a deliberately ordered interleaving (the first holds its transaction open while
the second starts), exactly like the stage-8 test. Verified by deletion: dropping `for_update=True`
turns `["first", "refused"]` into `["first", "second"]` with two audit rows for one document. An
earlier HTTP-level version of that test passed *without* the lock — two `client.post` calls in
`asyncio.gather` interleave only if the loop happens to schedule them that way, which is precisely
the false confidence this project's rules exist to prevent.

**The women's service (stage 10-ج) puts its matching inside `dispatch.eligible_driver_ids`, and
that placement is the design.** That function is the single answer to "who can take this ride" —
the dispatcher and the rider's map both call it — so a filter layered above it is a filter one of
the two paths will forget. It takes a `GenderMatch | None`, and `None` is deliberately *not*
`preference=any`: `None` means the country's `women_service_enabled` is off so there is **no gender
matching at all**, while `any` means the rider does not care and the *driver's* preference still
applies. Collapsing the two would leave a stale `female` preference on a driver's row quietly
starving them of rides in a market where the service does not exist.

The two directions are independent, and the second is the one an implementation drops: a rider who
picked "any" is still **not** offered to a driver who restricted herself to women.
`test_women_service.py` asserts that against `eligible_driver_ids` directly rather than against the
ride reaching `no_driver_found` — the first version of that test asserted the terminal state and
**passed with the rule deleted**, because a ride whose only candidate declines also ends
`no_driver_found`. Every rule in that file was then verified by deletion.

Two asymmetries carry real reasoning. A rider's `gender` is self-declared and unstamped, a driver's
is written **only** by `PUT /admin/drivers/{id}/gender` and matching reads `gender_verified_at IS
NOT NULL` — her declaration constrains her own ride, his constrains someone else's safety, so
without the stamp "female driver" is a word someone types about himself. And that admin write is a
**direct field, not a re-approval cycle**: the ID is already uploaded and reviewed, and sending
approved drivers back through the queue for one field makes clearing the backlog impossible — which
is the backlog the flag stays off for.

`cancel_reason_code = gender_mismatch` is the only reason that **waives the cancellation fee after
acceptance**, and it is refused where it has no place (a rider who asked for nobody, a driver who
restricted no one) — otherwise it is a free way out of every fee and a way to flag an innocent
account. The report lands on the *other* party's `gender_mismatch_reports`, and "flagged" is a
comparison against a threshold in the service, never a written column, so changing the threshold
re-evaluates everyone instead of leaving rows flagged by an old rule.

The women's service also adds the one **brand colour** this design system has: `--brand` /
`--brand-ink`, defined in `DESIGN.md` §1.1-ب and present in all three `tailwind.config.js` files
(the panel never activates it, but the file has to stay a verbatim copy of §6 — "identical except
two lines" is not identical). Its default value is `--tx`/`--inv`, so `text-brand` is a no-op until
a `.pink` class lands on `<html>`; that is what lets components be written once for both themes.
`lib/brand.tsx` in each PWA owns that class.

**A flag that gates a feature must also gate what the app *sends*, not just what it draws.**
`useWomenService().defaultPreference` used to return the stored `ride_gender_preference` regardless
of whether the service was on — so with the flag off the app hid the selector and still sent
`female`, and every ride request bounced with `women_service_unavailable` while she had no control
anywhere to change it. The backend was right to refuse (silently downgrading a gendered request is
worse), so the fix belongs in the app: it now sends `any` whenever the service is not offered to
this account, and the stored value is left alone — it is her choice and returns when the service
does; what stops is the *sending*, not the saving. A refusal with no way out is not a refusal. Two rules live there: the choice is stored **per
device, not on the account** (turning it off because someone is watching should not turn it off on
her phone at home), and `customer-app`'s `Brand.tsx` is the single component allowed to branch on it,
because the wordmark's normal colour is `--tx` and an unconditional `text-brand` would paint it the
app's default yellow. **What the theme is conditioned on changed on 2026-08-13 — the declaration
alone, no country flag — see the decision below; do not re-gate it on `women_service_enabled`.**

On the screens, one rule is a **UI narrowing, not a backend constraint**, and it is written into
`customer-app/src/lib/women.ts` — the single place either app answers "is this service offered to
whoever is holding this phone". The `GenderPreference` enum is three-way everywhere, and a driver
of any gender may restrict who he carries; but the *rider's* control is shown only to an account
that declared itself female, because offering "request a female captain" to a male rider opens the
exact door the service exists to close. Both PWAs hide every trace that **promises matching** —
control, default preference, badge — where `women_service_enabled` is off. **The pink theme is not in
that list any more**: it promises nothing, so it follows the declaration alone (the decision below).

The rider is told the cost of a gendered request **before** she commits (fewer captains, wider
search, longer wait), again while searching, and `no_driver_found` on such a ride carries its own
reason and a way out instead of the generic "nobody accepted", which reads as a personal rejection.
The driver's badge sits **above** the fare on the offer card for the same reason: a captain who
accepts and then discovers the ride is not his cancels, and that cancellation was preventable by a
pill. `test_ws.py` asserts `gender_preference` is present in the `ride_offer` frame — a field the
app reads and nobody sends is a badge that never appears, which is the `awaiting_confirmation`
failure shape.

**The pink theme activates on the self-declaration alone, and that line is the whole rule**
(owner's decision 2026-08-13, `DESIGN-DECISIONS.md` 50). A woman who declares herself female sees it
from her first open in either app — **no admin stamp and no country flag** — because the theme
*promises nothing*: it opens no door, enters no matching, and makes no account "a female driver".
What stays gated on `gender_verified_at` is matching and receiving gendered offers. Conflating the two
breaks it in both directions: a colour waiting on an admin queue makes the design wait on data entry,
and a stamp inferred from a colour buys safety with a self-declaration.

Its practical shape in the code is **two names, not one**: `useBrand().available` is the declaration
alone (the theme), and `useWomenService().available` is the flag *with* the declaration (everything
that promises matching). Merging them showed «من يقودني افتراضياً» in a market with no women's service
— the same no-way-out refusal 10-ج already fixed once.

Three more rules travel with it. **The one-time notice stays until she closes it**, unlike the 2800ms
toast in `DESIGN.md` §2.7: that lifetime is right for an *event* toast ("paid ✓") where nothing remains
to be done, and wrong for **introducing a switch** — someone who looks away for three seconds loses it
forever and is left with a mode she cannot turn off. Its "seen" flag is a **separate** storage key from
the choice, because a device with no choice set that has already seen the notice is a real state, and
merging them replays the notice on every open. And **`fixed left-1/2 -translate-x-1/2` caps a
shrink-to-fit box at half the viewport** — measured 201px of 402 — because the translate re-centres
*after* the width is computed; `inset-x-0 mx-auto` is what `Toasts.tsx` already does.

**Revocation reuses the existing gender door rather than adding a column.** When the documents
contradict the declaration, the admin stamps the real gender with a **mandatory written reason** (422
without it), `gender` stops being `female`, and the theme and its switch disappear together — because
both were built on the declaration alone. No `revoked` column: the stamped gender *is* the truth, and a
second column saying the same thing diverges the first time one is written without the other. She gets
an explicit notice (`women_mode_revoked`) carrying the general reason only — the admin's written reason
is for the audit log a month later, and forwarding it would turn a clerk's judgement into a letter.

The women's-service design arrived **after** the feature was built, and reconciling the two turned
up the failure mode neither the build nor the backend suite can see: **a rule with no door**. The
matching, the fee waiver and the report counter were implemented and tested, while the rider had no
field anywhere to declare her gender (so every gate downstream was permanently closed) and neither
app could send `reason_code` at all. `useWomenService` therefore returns **two** flags — `enabled`
opens the gender declaration itself, `available` opens everything that depends on it — because
gating the declaration on `available` is a closed loop. When a backend rule ships, check that some
screen can actually reach it; a green suite proves the rule works, not that anyone can use it.

**`services/drivers.approve` now has two guards, not one**: a verified phone (stage 8-ب) and every
required document approved (`REQUIRED_DOCUMENT_TYPES` in `models/driver.py` — licence, national ID,
vehicle registration; the vehicle photo is deliberately optional). Without the second, review is a
habit rather than a condition.

**The CliQ confirmation deadline is frozen on the payment, never read live.**
`payment_settings.cliq_confirmation_hours` is the per-country policy an admin edits; the moment the
rider submits a transfer reference, `payments.cliq_confirmation_expires_at` is stamped from it and
never recomputed — same reasoning as `commission_percent_at_ride`. Editing the setting governs what
comes after, not what a driver is already looking at a countdown for.
`tasks/payments.py::sweep_cliq_confirmations` runs every five minutes, takes the payment row lock
*before* re-checking the status, flips what expired to `disputed`, and notifies **both** parties —
the driver that his payment left his hands, the rider that his transfer was never confirmed; silence
here produces two support tickets, not one. And `confirm_by_driver` refuses a `disputed` payment
outright: `disputed → confirmed` exists for the admin's resolution (§13.4), and letting the app walk
through it would credit the money while leaving the dispute with no `resolution` and no record of who
decided — the row would simply vanish from the admin queue.

**`PaymentStatus` has five values and `awaiting_confirmation` is not one of them.** A cash or CliQ
payment waiting for the driver's word sits in `pending`; what separates "waiting for the provider"
from "waiting for me" is the **method**, not a sixth status. The driver app invented that status in
its TypeScript union and three screens gated on it — `Collect` could never find the payment to
confirm, so **no driver could confirm a cash ride**, and the dispute CTA never appeared. The build
was green (the string was a valid member of the union the app itself declared) and the visual review
passed because the preview fixtures were hand-written with the same invented value. Two rules follow:
mirror `app/models/enums.py` literally in `api/types.ts`, and derive review fixtures from a real API
response rather than from memory — a fixture that agrees with the bug proves nothing.
`npm run check:enums` (wired into `npm run build`) now enforces the first rule: it reads every
`StrEnum` member in `backend/app`, and fails any TypeScript string union that mixes real enum values
with invented ones — which is exactly the shape of a union that was copied and then added to. A
genuinely UI-derived union (the subscription's four display states) is exempted by name in
`UI_UNIONS`, with its reason. The audit that introduced it also found a second instance already
shipped: `PaymentMethod` carried `mixed`, a channel the provider never sends — mixed payment is
**two payment rows on one ride**, which is why there is no unique index on `payments.ride_id`.

**Nothing calls `ws/events.publish_*` directly any more; `services/notifications.py` does.** It
publishes to Redis and then sends the same event as a push notification, so a channel cannot be added
for one event and forgotten for another. Push goes only to devices whose socket is *not* open —
`services/presence.py` keeps a per-user hash of open `device_id`s (lazily pruned on read, since Redis
has no per-field TTL), and the socket writes into it only when the client sends `?device_id=`. That
one rule also means the actor never gets pushed his own action: whoever pressed the button has the app
open by definition. Ride offers are the only high-priority send — a twenty-second window does not
survive Doze mode. Delivery failures are swallowed and logged; a ride must not fail because a remote
service did.

**A notification's `data` carries raw values; its `title`/`body` exist for the OS tray alone.**
Every transactional sender puts `type`, `ride_id`, `amount`, `currency` and whatever else the event
needs into `data` — never a composed sentence and never formatted numbers. A backend-built
`f"{amount} {currency}"` renders "4.100 JOD" in Latin digits inside an app whose every numeral is
Arabic-Indic, and the fix is not to convert digits in the backend: that puts a language decision in
a layer that does not know who is reading, and runs money through a formatter for display reasons.
`title`/`body` stay because the OS draws them while the app is closed and no UI is running to
compose anything; every surface the app itself draws (the inbox, the sheets) composes from `data`
and falls back to the stored strings for a `kind` it does not know — so a new backend event degrades
to plain text instead of breaking the screen. Campaigns are the exception: their body *is* the
content an admin wrote.

Since stage 9-ب that same door also writes the durable record: `_safe_notify` writes a
`user_notifications` row through `services/inbox.py` **before** attempting push, and in its own
try/except — the row is the trace of the event, not of the provider, so it exists with no FCM
contract at all and when the socket was open so no push was sent. `kind` is `data["type"]` itself,
so tapping the notification and tapping its inbox row cannot open different screens. Two exclusions
carry real reasoning: `EPHEMERAL_KINDS` keeps the twenty-second ride offer out (once it expires,
`driver_assigned` is the correct trace and a stale "new ride request" row opens nothing), and
campaigns write a row only for `DeliveryStatus.SENT` — putting a marketing message in the inbox of
someone who switched marketing push off is a way around an explicit opt-out. There is no retention
sweep yet; the table grows, reads are capped, and the job belongs with stage 12's maintenance tasks.

Transactional notifications are not a user preference and never read `users.marketing_push_enabled`;
that column belongs to `services/campaigns.py` alone, along with per-country quiet hours. Campaigns
partition by country because quiet hours are per-country: a campaign spanning both markets sends in
Jordan now and Libya later and stays `scheduled` until every country in scope is done. Progress lives
in `notification_deliveries` (unique on `(campaign_id, user_id)`), never in the task's memory, so a
task that dies mid-campaign is resumed rather than restarted — and a `skipped` row for an opted-out
user is what makes honouring the opt-out provable instead of merely claimed.

`services/tracking.py` implements SPEC section 5's "driver offline > 60s during `in_progress` alerts
both parties and does **not** end the ride" — it starts on `POST /rides/{id}/start` and stops on
complete/cancel. It has no code path that mutates a ride; the 60s threshold is not a second timer
but the disappearance of the presence key, whose TTL already is 60s, so the two cannot disagree.

Nearby drivers shown on the rider's map are anonymised per SPEC section 10: coordinates, heading
and category only. `drivers.anonymous_ref` derives a per-connection pseudonym (blake2s keyed by a
random salt) so the frontend can interpolate a car's movement between frames without the same
driver being trackable across sessions.

**`ride_route_points` is the one exception to "live location lives in Redis only."** SPEC section
5.7 needs the broadcast to leave a durable trace for two things a 60s key cannot serve: the actual
distance that `final_fare` is recomputed on, and dispute evidence in the admin panel.
`services/route.py` hangs off the single `drivers.report_location` seam, so both the WebSocket and
the REST fallback feed it. It samples one point per 20s (SPEC says 15–30) and **the sampling window
is the Redis key's own TTL** (`SET NX EX`) rather than a separate timer — so nothing can disagree
with it and two uvicorn workers cannot both write the same instant. Capture failures are logged and
swallowed: a driver dropping out of dispatch because a route write failed is the worse loss.
`route.begin`/`route.end` bracket `in_progress` from the router, and `complete` ends capture
*before* computing the distance so a broadcast landing mid-calculation cannot extend a path already
priced. Fewer than two points yields `None`, never zero — zero would read as "drove 0 km" and drop
the fare to the minimum because an app went silent.

**A ride is settled by `services/payments.py`, and one ride can have several payment rows.** Mixed
payment (SPEC section 6) is wallet + cash on the same ride, so there is deliberately no unique
index on `payments.ride_id`; "don't charge twice" is the sum of `OWING_PAYMENT_STATUSES` against
`final_fare`, evaluated under the ride row lock. Money moves only at `confirmed`, exactly as it
does for topups. Cash and CliQ get no `ride_earning` — the driver already holds that money (section
9) — but commission is still owed on them under `all_rides` scope, which is the one path where a
driver's empty wallet blocks confirmation rather than overdrawing. Earnings are recorded as a full
`ride_earning` plus a separate `commission` debit rather than one net entry, so section 9's
"earnings − commissions" reads literally and cash-ride commission is not the only commission line
in the ledger; the reasoning is written into SPEC section 6. The frozen
`commission_percent_at_ride` is never re-read from settings, but `applies_to` is read at payment
time because it keys off the payment channel, which is unknowable at ride creation.

**The hosted card page returns to the app that opened it, and the app is derived from the payer's
role.** `settings.card_return_url` / `card_return_url_driver` are two publish addresses, and
`card_gateway.return_url_for(cart_id, payer_role=…)` picks between them — not a header the client
sends. In this system each role has exactly one app (`RiderUser` and `CurrentDriver` enforce it on
every route), so the role states which app opened the page with certainty, and a client-supplied
claim would be trust bought for nothing. The day one role uses two apps, the client has to declare
it; until then this is the narrowest thing that works. Before it, one address pointed at the rider
app, so a driver paying by card landed in an app that was not his — which disabled the whole card
channel for drivers, not just the saved-cards screen.

**The card channel trusts exactly one source for money: the provider's answer to a backend-initiated
call.** `services/card_gateway/` is a swappable strategy like `services/auth/`: `base.py` is the
contract, `telr.py` is **the only module in the project that knows Telr's wire format** (field names,
SHA-1 signature layout, order status codes), `mock.py` is the provider SPEC section 15 calls for, and
`__init__.get_gateway()` is the single decision point — reading the Telr contract from
`provider_credentials`, never `.env`, and refusing mock mode in production. A signed webhook is a
wake-up call, not a source of truth: `card_payments.handle_webhook` verifies the signature, reads
*only* the cart id from the payload, then calls `check_order` for the status and amount.
`WebhookNotice` deliberately carries no amount so a network-supplied number cannot reach the ledger.
All three entry points (webhook, client return lookup, one-tap charge) funnel into
`card_payments.apply_state`, which is the only function in the channel that writes money.

Because the Telr docs link SPEC section 6.4 promises was never delivered and no Sandbox credentials
exist, three wire details in `telr.py` are best-reading-of-the-public-API and are flagged in its
docstring as needing confirmation. They are deliberately arranged so that being wrong cannot move
money wrongly: a bad signature layout rejects webhooks with a visible 400 while the client-return
path still settles, and a bad stored-card charge returns 502 before any ledger write.

**Card money never touches the rider's wallet.** `models/payment.py` has three method categories,
not two: `DIRECTLY_COLLECTED_METHODS` (cash, CliQ — no `ride_earning` at all),
`WALLET_FUNDED_METHODS` (wallet — the only channel that writes `ride_payment` against the rider),
and card, which is in neither: the driver is credited but the rider is not debited, because his
money left his card, not his balance. Refunds follow the same asymmetry — a card refund goes back
through the provider (`provider_orders.refund_ref`) with no rider `refund` entry, while the driver's
counter-`adjustment` is written either way.

`services/ratings.py` recomputes `drivers.rating_avg` from the whole table after each rider rating
instead of rolling an average forward, for the same reason wallet balance is summed from its ledger.
`rater_type_for` decides who may rate from the ride itself, not from the account role — another
driver whose role is `driver` is not a party to this ride.

**`wallet_transactions.owner_id` always references `users.id` — for riders *and* drivers.**
`owner_type` is what distinguishes the two wallets. So a driver's balance is queried with
`driver.user_id`, never `driver.id`; passing the latter silently returns zero because it matches no
row. `withdrawal_requests.driver_id` deliberately points at `drivers` instead, as SPEC section 4
specifies — the two identifiers sit next to each other in `admin_wallets.mark_withdrawal_paid`,
which resolves one to the other before writing the ledger entry.

**There is no balance column and no balance cache.** `services/wallet.py::balance` sums the ledger.
Every write goes through `record()`, which first takes a transaction-scoped Postgres advisory lock
on the owner (`pg_advisory_xact_lock`, key derived from the UUID in Python so no dependency on
`hashtextextended`) — `SELECT SUM` followed by an INSERT is not atomic on its own, and two
concurrent debits would otherwise both read the same balance. The lock is re-entrant, so `transfer`
pre-locks both wallets in sorted UUID order (deadlock avoidance) and the nested `record` calls just
re-acquire. Migration `0006` installs a trigger that rejects UPDATE and DELETE on the table, so a
correction is an opposing `adjustment` entry, never an edit; `TRUNCATE` does not fire row triggers,
so the test cleanup still works. The amount's sign is dictated by its type via a CHECK built from
the same `CREDIT_TYPES`/`DEBIT_TYPES` tuples the service validates against, and `balance_after >= 0`
is enforced in the database too.

Idempotency (SPEC section 14) is a `UNIQUE (owner_id, idempotency_key)` on the ledger: the client
sends the key on a transfer, and `topups`/`withdrawals` derive one from the request id
(`topup:{id}`, `withdrawal:{id}`) so a double-click cannot pay twice. The key is checked *after*
the lock is taken, so concurrent retries serialise into a lookup hit rather than a constraint
violation. Money enters a wallet only at `confirm` (topups) and leaves only at `paid`
(withdrawals) — a `pending`/`approved` withdrawal reserves its amount against the available
balance instead, because no entry exists yet to represent it.

`wallet_enabled` gates topping up and paying, never reading: a balance from before the flag was
switched off stays visible to its owner. A zero in `wallet_settings.transfer_*_limit` means
"not configured yet" and blocks transfers with a message that says so, rather than being read as a
generous default.

WebSocket tests use `httpx-ws`, whose `ASGIWebSocketTransport` runs the app in the *same* event
loop; Starlette's `TestClient` would open its own loop in another thread and break the asyncpg
pool. Its transport opens an anyio task group, and anyio refuses to exit one from a different task
than entered it, so `ws_client()` in `conftest.py` is an `asynccontextmanager` used inside the test
body — making it a fixture fails at teardown.

**`customer-app/` decides nothing.** Every branch it takes is read from `GET /config`: which
verification flow to draw (**`countries[].verification`** since 12-هـ — `auth.verification` is the
*default country's* answer and stays only as a fallback, because reading it while the user has picked
the other market announces one channel and sends in another), which payment channels exist in this
country (`countries[].features`), which map token to use. A flag switched off in the contracts page
disappears from the app with no deploy — that is the whole point of publishing the config, and it
is why no feature name is hardcoded outside `lib/payment.ts::PAYMENT_CHANNELS` and `lib/config.tsx`.
Money is never computed there: amounts arrive as strings (`NUMERIC(12,3)` serialises to a string)
and `lib/utils.ts::formatMoney` formats them **textually**, because passing money through
`Intl.NumberFormat` means passing it through a float. Error text is whatever the backend's
`{code, message}` says — the app never writes its own Arabic for an error the backend already
named. `components/map/MapView.tsx` is the only file that imports `mapbox-gl`, and
`services/cliq_qr.py` on the backend is the only thing that builds a CliQ payload — the app
receives `qr_payload` and draws it.

Three rules in the app exist because the backend cannot enforce them: the socket opens with the
same `device_id` that registered the FCM token (otherwise the same event arrives twice — once on
screen, once from the OS), logout deletes the device row *before* revoking the session, and the
service worker never caches `/api/`.

## Invariants from SPEC.md that constrain future stages

- Money columns are `NUMERIC(12,3)`. Never float.
- Provider API keys (Mapbox, Telr, SMS, FCM, payout) belong in the encrypted `provider_credentials`
  table managed from the admin "contracts" page — never in `.env` or code. `.env.local` holds only
  infrastructure secrets (DB, Redis, JWT, the Fernet key); its Mapbox/Telr tokens exist solely as
  input for `scripts/seed.py`, which writes them encrypted and is idempotent.
- Wallet balance is derived from the immutable `wallet_transactions` ledger. There is no balance column.
- Riders top up and transfer but **never** withdraw (SPEC section 7); only drivers have a withdrawal path.
- Pricing and all financial math happen in the backend only; the frontends display.
- `rides.commission_percent_at_ride` is frozen at creation and never recomputed retroactively.
- `saved_cards` never stores a PAN or CVV — only the provider's token plus brand/last4/expiry. The
  table exists from stage 6-أ but is written by stage 6-ب.
- Commission is enabled **only** through `commission_settings`; there is deliberately no
  `commission_enabled` feature flag, so the switch, the percent, and the scope cannot disagree.
- A `driver_subscriptions` row exists only once its money has arrived — there is no `pending`
  status. Cash and CliQ are recorded from the admin panel *after* collection; wallet and card write
  the row only after the ledger or the provider says so.
- Every endpoint touching a ride or wallet must verify ownership (no IDOR).
- `device_tokens.token` never leaves the backend, for the same reason `saved_cards.provider_token`
  doesn't: it is what lets someone send a notification in TAXO's name to a user's phone.
- CliQ ride payments are never confirmed automatically, whatever contracts are active: that money goes
  from the rider to the *driver's* alias and never touches the company account, so no acquirer can
  witness it. The acquirer contract covers wallet topups only and does not move `cliq` out of
  `DIRECTLY_COLLECTED_METHODS`.

Python is pinned to 3.12 in the Dockerfile even though the host has 3.14, because Celery does not
support 3.14 yet.
