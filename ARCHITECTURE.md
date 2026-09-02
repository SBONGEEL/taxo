<!--جديد-->
# ARCHITECTURE.md — كيف بُني هذا النظام

**مُلزِمٌ بشرطه في `CLAUDE.md`**: *قبل أن تمسّ الخلفيةَ أو تضيف باباً أو تكتب في شاشة — يُفتح هذا الملفّ.*

**نقلٌ لا تحرير.** كلُّ ما تحت هذا السطر منقولٌ من `CLAUDE.md` بحرفه — لا حرفَ تغيّر ولا سطرَ أُعيدت صياغتُه.
وفهرسُه في `CLAUDE.md` تحت «الفهرس — كلُّ ما نُقل».
<!--/جديد-->

### Country visibility — one flag per market, and Libya is its first use (2026-08-19)

**`country_visible` is a per-country flag, and no app writes a country list any more** (`SPEC.md` §24).
The point is not Libya; it is that a market can be built in full — pricing, contracts, settings — and
**not appear**: not in the country picker, not in registration, nowhere.

**Silence means visible, and it is the second member of `DEFAULT_ENABLED_FLAGS`.** The general rule is
that an absent row disables, so a money feature is never switched on by silence. Here absence would
switch off **the whole app**: an unseeded install would publish no country at all, so no login screen
could be drawn. Hiding is therefore an explicit row a human writes.

**And that forced a split that had been latent since stage 8**: the "write a reason before switching it
off" condition was read from `DEFAULT_ENABLED_FLAGS` itself, so the new flag would have inherited a
refusal whose message says «مفتاح التحقق» to whoever hid a market. The two sets are now named
separately — `DEFAULT_ENABLED_FLAGS` says **how absence reads**, `GUARDED_FLAGS` says **what switching
off costs** — and the second still holds `otp_verification_enabled` alone. **Hiding a market is a launch
decision, not an emergency action.**

**The filter is in the backend because that is the only place that satisfies the condition.** Everything
the apps display about markets already derives from `GET /config`, and a list compiled into a bundle
changes only with a new bundle on every device. Two consequences: `default_country_code` becomes the
first visible country when the configured one is hidden (a name outside `countries` is a field with no
mirror — it arrives and reads `undefined`), and **the panel cannot read `/config`**, because whoever
prepares a market before opening it needs to see it while it is off.

So the panel has `GET /admin/countries` (`StaffUser`), carrying every market with `visible`, its name,
and its **full description** — currency, quiet hours, verification channels, all of which the pricing
and campaign screens read while the market is still dark. **Both doors call one builder**
(`services/country_config.build`): two doors publishing the same thing, each honest alone, is the eighth
shape — and `test_the_two_doors_publish_the_same_description` is what compares them.

**What was swept out of the apps**, with what was deliberately left:

| where | was | now |
|---|---|---|
| `admin-panel/components/Shell.tsx` | `["JO","LY"]` + a `COUNTRY_LABEL` map | from `/admin/countries`; the name comes from the backend |
| `admin-panel/lib/config.tsx::useCountryConfig` | `/config` only | the panel door first, `/config` as the pre-login exit |
| `customer-app/lib/config.tsx::useAuthCountry` | `?? ["JO"]`, `?? "JO"` | `?? []`, default taken from the list |
| `driver-app/lib/config.tsx::useAuthCountry` | same | same |
| `customer-app/screens/WalletTransfer.tsx` | `?? ["JO"]` for the recipient dial codes | `?? []` — transferring into a hidden market is a door the flag opens |

**Left on purpose**: `CountryCode = "JO" | "LY"` in all three `api/types.ts` — an **enum mirror, not a
display list**, guarded by `check:enums`, and nothing rendered is derived from it; and
`user?.country_code ?? "JO"` fallbacks, which are the **account holder's own** country rather than a
market list, and show a hidden market to nobody.

**The condition was "it must appear immediately with no rebuild and no redeploy", so it was measured on
a bundle that predates the work** (`index---ktOf25.js`, Note 20, over the live tunnel): toggling from
the panel door made `/config` drop `LY` in **206 ms**, the transfer screen's `select` measured
`["JO=الأردن"]`, enabling it and reloading **the same bundle** measured `["LY=ليبيا","JO=الأردن"]`, and
switching it back returned one option. The panel saw both markets throughout. Read from the DOM, never
from a screenshot.

**Enabling Libya is a launch item, not a toggle** — §24.5 lists the five things verified before it
(pricing rows, a verification contract reaching `+218`, payment contracts behind every flag switched on
there, a supervisor account, and quiet hours with its timezone).

### The error contract — one body shape, and the 422 that had no handler at all (2026-08-18)

**`SPEC.md` §17 is the contract; this is what building it found.** Every backend error now returns
`{code, message, field?}` — `code` for the log, `message` Arabic and display-ready, `field` only when
the error is about one. Three handlers cover the three sources, and covering only the first — which is
what existed — is what caused the reported bug.

**The 422 on `POST /drivers/me/vehicles` had two separate defects, and neither was in the vehicle code.**

1. **There was no `RequestValidationError` handler in the project at all.** Only `AppError` was
   registered, so a 422 fell through to FastAPI's default: body `{"detail": [ {loc, msg, type}, … ]}`
   and **nothing written to the log**. That is exactly "the log shows the status with no detail".
2. **`detail` was the project's own name for the Arabic message**, so the client read `body.detail`,
   received an **array**, and passed an object to `Error` — `[object Object]` on screen. **One name for
   two meanings is the defect; renaming it is not cosmetic.** It is now `message` everywhere, with no
   fallback read of `detail`: a fallback keeps the old shape working, so a missed path is never found.

**The 422 itself is the app's guard being weaker than the schema, and nothing bridging them.**
Measured through the real route with a real driver session:

| sent | backend answer |
|---|---|
| `year: 5` | 422 `سنة الصنع يجب ألّا تقلّ عن 1990`, field `year` |
| `plate_number: "7"` | 422 `رقم اللوحة قصيرٌ جداً — 2 محارف على الأقل`, field `plate_number` |
| `year: null` | 422 `سنة الصنع يجب أن تكون رقماً`, field `year` |
| the correct body | 201 |

The screen's check was `value.trim()` non-empty on all five fields, while the schema enforces
`year ∈ [1990, 2100]` and `plate_number` 2–32. So `"5"` and `"7"` pass the button and bounce off the
server. **`category` was never the cause** — `GET /config` publishes exactly `['economy','comfort']`
for both markets, matching the enum.

**And a second, quieter defect in the same field: the year input stripped Arabic-Indic digits.**
`replace(/\D/g, "")` — `\D` is "not `[0-9]`", and `٢٠٢٠` is not `[0-9]`, so an Arabic keyboard emptied
the field, `vehicleReady` stayed false, and **the submit button sat disabled with nothing saying why**,
in an app whose every numeral is Arabic. `toLatinDigits` now accepts both (and Persian digits) and
converts. This is the mirror image of `arabicDigits`, which the project has had since stage 10 —
**output was converted and input never was.**

**Three rules from building it that are worth keeping.**

- **Register on `starlette.exceptions.HTTPException`, not FastAPI's subclass.** Route-not-found is
  raised by Starlette's router with the parent class, so a handler on the FastAPI one never fires — it
  shipped that way for one iteration and returned `{"detail": "Not Found"}` in English until measured.
- **Arabic error text needs grammatical gender, and it must be written down per label.** «كلمة المرور
  مطلوب» is broken Arabic, and broken grammar in an error message reads as a broken app, which costs
  trust in everything after it. `FEMININE_LABELS` is explicit because gender is a property of the word
  and is not derivable from its shape — «سنة» is feminine and «اسم» is not, and the tāʾ is not a rule.
- **The log takes the whole request body, so redaction is not optional.** `redact` keeps the key and
  masks the value, because "sent it empty" and "did not send it" are different bugs on a signup screen
  and dropping the key makes them identical.

**§17.3 was the one open question, and the owner settled it: publish the rules in `GET /config`**, no
app-side copy and no build guard. `core/validation_rules.py` derives them from `model_fields` and their
`annotated_types` constraints — **nothing is hand-written beside a schema**, because a limit living in
two places diverges at the first edit, which this project has already done once (the WhatsApp per-phone
cap went 3 → 20 in the service and stayed 3 in a test that copied it, leaving the suite red on master
unnoticed). The Arabic text is generated by **the same function that answers a 422**, so the published
string and the served string cannot differ.

**Timeouts are three measured classes, not one number** (the first cut used 60 s everywhere, taken from
the slowest path — which leaves "accept this ride" spinning for a minute against a 20-second offer).
Every number is derived from **the server's own ceiling for that path**, because a client timeout below
it aborts a request the server will still answer, and the user then retries something that already
happened:

| class | measured locally | server ceiling | client timeout |
|---|---|---|---|
| interactive (DB only) | 6–51 ms | no external call | **15 s** |
| provider call inside the request (estimate, reroute) | 199–849 ms | 10 s (`directions`) | **20 s** |
| OTP send (`/auth/challenge`) | 0.74–3.5 s | 45 s (`15 + 30`) | **50 s** |
| document upload | size- and link-dependent | none | **no timeout** |

**And measuring caught a measurement error first**: `POST /rides/estimate` timed at 7–23 ms, which is
impossible for a Mapbox round trip — it was returning **403** to a driver token on a rider-only route.
The number was of a permission denial, not of the path. Re-measured with a rider token it is 199–849 ms.

**The upload needs three things in place of a timeout, and the third is the one that is easy to miss.**
A progress percentage, a cancel button, and a **stall detector** — because cancel handles *someone who
decided to stop*, while a socket that dies mid-upload emits **no `onerror` at all**: TCP retransmits
silently for minutes, so the bar stops at some percent with no event and no message, which is exactly
the no-way-out screen this contract exists to remove. **Its 20 s is measured, not chosen**: driving a
real upload in Edge over CDP, the largest gap between two progress events was 122 ms on localhost,
433 ms at 50 KB/s, and **1440 ms at 12 KB/s** — a link barely usable at all (506 KB in 43 s). Twenty
seconds is ~14× the worst measured gap, so it cannot fire on a live-but-slow upload, and it beats TCP's
own surrender by minutes. The two aborts are **told apart**: a stall is an error carrying a retry button
that holds the same file, a user cancel shows nothing at all, and both arrive through `onabort`.

**Progress forces `XMLHttpRequest`**: `fetch` reports upload progress in no way whatsoever — no event,
no stream. That is the whole reason the upload path does not share `request()`.

Three things in it are worth keeping. **The test guards two failures, not one**: a published limit that
differs from the schema, and a **field silently dropped** from the derivation — an app that validates
five of six fields is worse than one that validates none, because the sixth surprises the user after a
round trip. **The security exception extends to the published rules**: `LoginRequest.password` allows
any length on purpose, so login publishes `min_length: 1` and never the registration policy — publishing
8 would hand a guesser the search space, and a test now guards the two schemas staying different rather
than being "tidied" into one. And **the cache write fails silently by design**: a full or blocked
`localStorage` must not break a screen, since the rules are an optimisation over a check the backend
performs anyway.

### The app switch — a handoff token, and the busy check that could not ask its own question (2026-08-19)

**`SPEC.md` §23 holds it.** `POST /auth/handoff` issues a random value in Redis — **30 s, single-use,
bound to the user *and* the target app** — and `/handoff/exchange` spends it for a session in the
receiving app, with no password and no OTP. **The pattern is the TOTP challenge verbatim**, not a new
mechanism, and its argument was already written there. The refresh token is deliberately *not* moved:
its rotation is single-use, so two holders invalidate each other and log their owner out at random.

**The exchange re-runs every check** — account from the database, block flag, `app_scope` again — so a
role withdrawn between issue and exchange kills the token. It is a session transfer, never a frozen
permission.

**And the busy guard hit a circularity worth remembering.** "No switching mid-ride" naturally reaches
for `active_ride_for_user` — which calls `_side_of`, which **refuses dual-role accounts by design**. So
the check that exists for switchers was the one thing switchers could not run. `has_any_active_ride`
asks **both sides at once** and never asks which side you are, which is also the more correct rule: you
cannot switch away from an active ride on *either* side.

**Opening the other app is `intent://`, not a bare scheme, and all three reasons are about determinism**:
`package=` pins the receiver so no app that registered the same scheme can catch the token;
`S.browser_fallback_url` makes "not installed" **an answer from the OS** instead of a timeout after
which we guess — and the guess is wrong on a slow phone; and the token rides a custom scheme that
reaches no server at all.

**And the listener is a condition, not a nicety**: the shell opens the scheme URL and it does not become
a web route by itself, so without `appUrlOpen` the intent arrives and *nothing happens* — this project's
"a door with no button", wearing a platform's clothes.

### The rule that dissolves the ambiguities: context of the act, not role of the actor (2026-08-19)

**`SPEC.md` §22 is the rule; the owner set it as general so a fourth site finds its answer written.**
Where a role decides **meaning** rather than **permission**, the reference is the *act's* context — the
app that started it, the declaration carried with it, or the fact stamped at its moment — **never the
roles its actor holds today**. A role became a set and stopped naming one thing; a context is always
singular, because an operation is begun from one app and happens once.

Three consequences follow, and they are what makes it implementable: **declare or stamp at creation,
never derive at use**; **a declaration grants nothing** (it is checked against what the account holds,
exactly like `app_scope`); and **whoever does not declare gets the named error** — except where a
decisive safe value exists, which is written as a declared precedence instead (§21.3).

**Two wallets, not one, and the reason is the sharpest thing here**: the captain's wallet carries
earnings and is subject to advances, deductions and the subscription; the rider's carries what he tops
up for rides. **Merging them means deducting an advance from money he loaded himself.**

**And a rule fell out of the migration that is worth more than the three sites**: two columns were
backfilled and one was not. `wallet_topup_requests.owner_type` and `provider_orders.opened_from_app`
were — because at migration time every account holds exactly one role, so each old row's wallet and app
are **known with certainty**, and filling them moves a fact. `referrals.referral_type` was not — because
its question is *which app the referral came from*, and that was never recorded, so filling it writes an
**inference** into a column of facts. **Backfill what is recorded elsewhere; never backfill what needs
inferring.**

**The two homes of truth are a bridge, not a destination.** `users.role` and the table agree because the
migration made them agree and every creation writes both. A write to the column alone would break that
**with nothing failing** — authorisation reads the set, filters union the column — so an account would be
one thing at one door and another at the next. A test now fails if any path assigns `users.role`
(verified by adding one). Its drop condition is written down: after the switch-button stage settles and
no downgrade is needed, and once no read still unions the column.

### The roles model became a set — and the dangerous half was never authorisation (2026-08-19)

**`SPEC.md` §21 holds the design.** `users.role` was one scalar column, never written after signup, so
"one account, two apps" was impossible **structurally, not cosmetically**. It is now a set
(`user_roles`), and every guard asks "does he hold the role?" instead of "is that his role?".

**The count that mattered: `require_roles` has six call sites and all six are in `core/deps.py`** —
every route reaches them through four aliases. The "sweep across the project" was one function. What
actually needed care was the **41 direct reads of `.role`**, and splitting them was the whole job:
**15 decide permission** (mechanical) and **9 decide meaning** — *what a thing is*, not *who may*.

**Four of the nine are money and one is safety**, and three were invisible until the sweep:

- `by_role=user.role` at cancellation → `cancelled_by_rider|driver` → **the cancellation fee and the
  supervisor's count**. Guessing loads the fee onto the wrong party.
- `active_ride_for_user` / `rides_for_user` → `if driver: … else: rider`. A dual-role account falls in
  one branch **with no trace**: its other active ride vanishes from its own screen and half its history
  never renders. No exception, no log line, no complaint.
- self-declaring gender → whether the admin's stamp can be bypassed.

Each of the six money/meaning sites now raises **its own named code** (`wallet_owner_undecided`,
`cancelling_side_undecided`, `card_return_app_undecided`, `referral_programme_undecided`,
`ride_side_undecided`) — *a code per place, not one generic error*, because whoever reads the log needs
to know **which decision is missing**, not that an account had two roles.

**The gender site is the one deliberate exception, and it is a declared precedence, not a default**
(the owner's call): the admin's stamp wins whenever it exists. Shouting there would stop a woman using
the women's service, while silence opens the worse hole — a captain declaring against his stamp to
reach what is not his. **The safe value exists and is decisive, so there is nothing to guess.** And the
first cut of it *weakened an existing rule*: reading only the stamp let an unstamped driver
self-declare, which 10-ج forbids. It is two conditions now — holds the driver role, **or** carries a
stamp — so the set opened no door that was closed.

**Two things the build taught, both about the same seam:**

- **`User.roles` must never do IO.** `role_grants` is `selectin`, so any account from a query has it —
  but an account *constructed in Python* and committed does not, and the first read then lazy-loads
  outside the greenlet. It reads `inspect(self).unloaded` and falls back to the column. The same trap
  hit `create_account`, fixed by building the grant **in the constructor** rather than adding it after
  the flush.
- **The SQL clause and the Python property must union the column identically.** Accounts created
  outside `create_account` (the seed, test fixtures) carry the column and no grant row — so a filter
  reading only the table **hides them**, and an account becomes present in authorisation and absent
  from every list. `has_role_clause` is the one place that rule lives, and it is the same rule as
  `User.roles`. Found by `/admin/users?role=support` returning an empty list.

**The migration is measured, not asserted**: 37 accounts → 37 rows, `{user_id: role}` identical before
and after, **zero accounts with two roles** — and the down/up cycle was *run*, with the `users`
fingerprint (`md5` over id+role) identical on both sides. The column stays; dropping it would make the
downgrade a loss.

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

<!--جديد-->
### وصار بابان يقرنان هويةً بموقع لا باب — **وسطران فوق هذا بليا** (2026-09-03)

**ما فوق هذا السطر منقولٌ ولا يُحرَّر، وفيه جملتان لم تعودا صحيحتين** — فتُقرأان
معه لا بدلَه:

١. **«`GET /admin/live/map` is the only route in the project that pairs an
identity with a location»** — **صار معه `GET /admin/live/drivers/{driver_id}/ride`**
(البند ٦، `SPEC.md` §42): الرحلةُ الجارية لكبتنٍ بعينه، ومسارُها من
`ride_route_points`، وموضعُه من مفتاح الحضور. **وقيودُ الأول كلُّها تسري عليه**:
`AdminUser` لا `StaffUser`، وخارجَ مصفوفة الصلاحيات، وقيدُ تدقيقٍ مخنوقٌ
بالنافذة نفسِها — **لكن على `driver_live` بمعرّف الكبتن لا على `live_map`**،
لأن قيداً يقول «قرأ خريطةَ الأردن» عمّن فتح ملفَّ كبتنٍ واحدٍ يصف فعلاً أوسعَ
ممّا وقع. **ويُكتب حين يخرج موضعٌ فعلاً**: قراءةٌ لم تكشف موضعاً لا تُسجَّل.

**والعلّةُ في أنه ليس للدعم ليست حجمَ الحمولة بل أثرَها**: من ملك تتبّعَ كبتنٍ
واحدٍ بمعرِّفه ملك تتبّعَهم واحداً واحداً — **فبابٌ أضيقُ في الشكل ليس أضيقَ في
الأثر**. **وبيتُهما واحد** (`routers/admin_live_map.py`)، ومن أضاف ثالثاً
يضيفه هناك لا في موجّهِ الشاشة التي تعرضه.

٢. **«`LiveCanvas.tsx` is the only file in the panel that imports `mapbox-gl`»**
— **وقد بلي قبل البند ٦ لا به**: `SkinMapPreview.tsx` يستورده منذ دفعة المتجر،
و`RouteCanvas.tsx` منذ اليوم، **فثلاثة**. **والفخّان المذكوران فوق يسريان على
الثلاثة** ولذلك أُعيد ذكرُهما في رأس الجديد.

**والذي يجب أن يبقى واحداً هو `lib/map-rtl.ts` وحدَه**: `setRTLTextPlugin`
عامٌّ على الوحدة **ويرمي إن نُودي مرّتين**. **وفخٌّ ثالثٌ يخصّ الخطّ لا
العلامة**: `Marker` ينجو من `setStyle` **والمصدرُ والطبقةُ لا ينجوان** —
تبديلُ السمة يمسحهما **بلا خطأٍ يظهر**، فيختفي خطُّ المسار وتبقى الدبابيس.
فيُعاد رسمُه على `style.load`.
<!--/جديد-->

**Vite in these containers does not see host edits.** The source tree is bind-mounted from Windows
into alpine and inotify does not cross that boundary, so HMR never fires and the dev server keeps
serving the module it read at startup — a fix can look like it did nothing for as long as you care
to test it. `docker compose restart <app>` before every browser check, and confirm with
`curl http://127.0.0.1:5175/src/<path>` that the served text contains your edit. (The earlier note
that `public/dev-login.html` only appears after a restart was this same fact, seen through one file.)

**And on this machine right now the panel is not running Vite dev at all — it is `vite preview`
serving `dist`** (the tunnel stack overrides the compose command). So a panel source edit is invisible
until `npm run build`, and no number of container restarts will help. **Measure which one you are
talking to before debugging a "stale module"**: the request list is the answer — `/src/main.tsx` and
per-file module URLs mean dev, `/assets/index-<hash>.js` means a build. That question cost this session
four restarts, a cleared `node_modules/.vite`, and two wrong theories (browser cache, then Vite's
transform cache) before the request list settled it in one look.

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

`worker` and `beat` are the Celery pair from stage 7 (`app/tasks/`), running **fifteen** periodic jobs
(counted from `beat_schedule` on 2026-08-20; this line said "fourteen" while the schedule held fifteen):
the subscription sweep and the CliQ-confirmation sweep every five minutes; the stage-8 campaign
dispatch, the multi-stop wait cap and **due bookings** (12-ط) every minute; the referral-bonus payout
(12-ح), the advance sweep (item 15) and the **cancellation-charge sweep** every ten;
**the driver-level re-evaluation hourly** (item 53), **the pause-cap notice every minute**
(§5.10-ب), **the WhatsApp session watch every minute** and **the backup schedule check every quarter
hour**; and the three maintenance jobs — the stale-provider-order sweep, the inbox trim, and the
**orphan-document-file sweep**, which is the one job on a `crontab` rather than an interval (Friday
04:20, weekly): there is no driver-facing delete path, an orphan arises only from a replacement that
broke between the file and its row, and sweeping a directory of thousands of files is not work to
repeat daily. **Run exactly one `beat`** — a
second scheduler fires every period twice. The worker process has no event loop of its own, so
`celery_app.run_async` keeps one loop per process: a fresh loop per task would strand the asyncpg
pool bound to the previous one. Tasks are thin wrappers over `services/`, and the tests call the
service directly — nothing in the suite needs a worker running.

## Architecture

`backend/app` is layered: `routers/` are thin HTTP wrappers, `services/` hold all business logic,
`models/` are SQLAlchemy 2 async, `schemas/` are Pydantic v2. `ws/` is the realtime layer (channels,
events, sockets); `tasks/` holds the Celery app and its periodic jobs, each one a thin wrapper over
a service.

**WhatsApp is the third verifier (12-هـ), and the priority chain changed with it.** It is now
`whatsapp_otp ← sms_otp ← firebase ← none` — the owner reversed the old Firebase-first order, and the
consequence is explicit: **an active Firebase contract goes unused while any contract ahead of it is
active**, so whoever wants Firebase turns off what precedes it.

**And since 2026-08-16 the channel has two wires behind one contract**, chosen by its `transport` field:
`cloud` (Meta's official Cloud API over Graph) and `baileys` (a self-hosted gateway on a dedicated
number). **This reverses a rule that used to be written here** — "only the official Meta API, never
`Baileys` or anything like it" — and the reversal is the owner's, made with the cost in view. The old
rule's reasoning still stands and is worth keeping in front of you: automating an account through an
unofficial library violates WhatsApp's terms and is punished by **banning the number**, and a ban arrives
without warning. What changed is the alternative: the official route needed a business contract and an
approved template that had not arrived, and **until one of them did, nobody could register at all** —
the platform's single hardest launch blocker. A channel that might be banned beat a channel that did not
exist.

So the decision came with guards, and they are the reason it is defensible: a **dedicated number** never
used for ordinary WhatsApp, **per-number and per-hour caps** measured in Redis before anything reaches
the wire, **randomised spacing** and **one fixed link-free text** inside the gateway, an **immediate alert**
to every admin when the session drops, and **an emergency plan with measured recovery times** (above in
"what stands between here and launch"). And the official path was **kept alive in the same interface** —
going back is editing one field, not writing code. **The contract is global while the flag is
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

**Requesting a code is capped on the phone, in the backend, for every channel** (owner's decision,
2026-08-16 — `otp_settings` per-country, `services/otp_limits.py`). Before this there was only a flat 60s
cooldown and a *verify*-attempt limit: nothing stopped someone asking for a hundred codes an hour, which
on a self-hosted WhatsApp number is how the number gets burned. **Three caps, because each stops what the
others cannot** — a short window (a burst), a daily total (someone who waits the window out and returns),
and **a lifetime-per-registration cap**, which is the one that cannot be bought with patience: whoever
asked for ten codes on a number and never completed a signup is not a struggling user, and waiting a day
does not make him one. That third counter is cleared by `create_account` — the single creation door —
because once the signup happened its subject is gone; the window and daily counters are deliberately
*not* cleared, so a fresh account gets no free allowance in the same minute.

Four placement rules travel with it. **The guard sits in `otp.issue`**, the one door every channel we
generate and send a code through passes — so the cap is account policy, not a channel property, and
switching channel does not buy a new allowance (Firebase is outside it by its shape, not by oversight:
its code is sent from the user's device and never passes through us). **Counting is on the phone, never
on IP** — dozens of users behind one café's network must not throttle each other, and the abuser is
followed alone; the same reasoning as the location-broadcast cap. **Counting happens after a successful
send**, so a bounced gateway does not consume anyone's allowance — a cap is a penalty for insistence, not
for our own outage. And **every refusal carries `retry_after`**, which both apps already render as a
countdown, so the resend button is never live-but-inert. Verified on the live stack: three real requests
returned `resend_after` 5 → 10 → `429` with the wait named, and the third arrived over **SMS**, which is
the account-not-channel rule showing itself.

**The self-hosted wire (`baileys`) is a sidecar container, and four placement decisions carry it.**
`whatsapp-gateway/` runs Baileys with **no published port** — the backend alone reaches it, over the
compose network, with a shared key from `.env.local`; two guards, because "no port" is a deploy condition
that one line in another file can undo while a key check is in the code. **The caps live in the backend
and the spacing lives in the gateway**, which is not an arbitrary split: a cap is *policy* — measured,
tested, and surviving a restart on Redis — while spacing is *wire rhythm*, and a cap held in a process's
memory is erased by the first crash loop. **The gateway will not accept a message body**: `/send` takes a
number and a code, and the one fixed link-free text is composed there — so "no links" is guaranteed by
whoever owns the wire rather than by whoever calls it, which is the difference between a rule and a rule
that survives the next caller. And **the auth state is a named volume**, because otherwise every rebuild
needs a human with a phone.

**Its failure modes are announced, not discovered.** `tasks/whatsapp.py` reads the session every minute
and pushes every admin **on a transition** — never on the state, because an alert that repeats every
minute is ignored within the hour, which is the hour it matters. `disconnected` waits two cycles first
(a transient blip returns by itself and waking someone for it teaches them to ignore the next one), while
`awaiting_qr` and `unreachable` are said immediately: neither returns without a human. And recovery is
announced too — whoever was woken deserves to know it ended.

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

**«Is this ride settled?» has exactly one answer, and it lives in `services/settlement.py`.**
`SettlementState` is five values, not two, because "not settled" hides three different situations that
call for three different actions: pay now (`due`), the money is handed over and awaits the other party's
word (`awaiting`), and a dispute is open (`disputed`) — plus `not_due` and `settled`. It is published on
`RidePaymentsOut`, `RideListItem` and `AdminRideRow`, and **no screen computes it any more**; that is the
§14 rule applied to a decision rather than to an amount. Two properties keep it honest. It reads **what
the ride owes** (`chargeable_of`: the final fare, else the cancellation fee, else `None`) and never the
ride's *status*, which is why the cancellation fee needed no new line in it. And `_STATUS_ROLE` is a
**total map over `PaymentStatus`** whose `role_of` raises on an unclassified member, with
`tests/test_settlement.py` iterating the enum and cross-checking `RELEASES ⇔ not in
OWING_PAYMENT_STATUSES` — one concept, two homes, and the test is what stops them drifting.

**`core/app_scope.py` is the door guard, not a permission system.** Each client declares `app` on login,
TOTP login and register; `_ROLES` maps rider/driver/panel to the roles allowed in each, and a mismatch is
**403 with a message naming the right app** — someone who typed correct credentials in the wrong app
otherwise concludes the account is broken and registers a second one on the same number, which has already
happened on this project. Three properties: the guard runs **after** the password (so it tells nothing to
whoever cannot log in) and **before** the TOTP challenge (so no challenge is opened for a door that will
close); `app=None` **passes**, because this prevents role confusion in our three apps and is not a second
authentication factor — without that, adding it would log out every existing client; and it does **not**
replace `RiderUser`/`CurrentDriver`/`require_roles`, which guard *what may be done* rather than *where one
may enter*.

**The cancellation fee is the first debt between two users** (`services/cancellation.py`,
`models/cancellation.py`). An advance (item 15) is the platform lending to a captain; this is **a captain's
money held by a rider**, and the platform only carries it — which is where every rule in the file comes
from: both parties are named columns, the ledger takes **two** entries rather than one net one, and a
`pending` charge is shown to the captain **outside** his balance, because an entry means money that
*arrived*. Four more worth knowing before touching it. The proximity exemption is measured from
`geo.last_position` — the GEO index for the coordinates and the **presence key for liveness**, since Redis
cannot expire a zset member, so a member with no presence hash is a stale position; **no position at all
means the rider is exempt** (the owner's branch أ: no evidence of effort, and the doubt belongs to whoever
would be charged). Collection is attempted inside the cancel transaction and **failure is not an error** —
an insufficient balance is the *answer* (a debt), never a refusal to cancel. `try_collect` takes the wallet
locks **before** reading the balance, and the reverse order is what the concurrency test now catches. And
`blocks_new_ride` sits in `rides.request_ride`, not in the router, because scheduled bookings create rides
through that same door and a guard in the router is a guard the second door forgets.

**Collection has exactly two doors and they answer different questions.** `collect_with_ride` runs at the
end of `payments.settle` and asks "who is holding this money now" — cash/CliQ put it in the current
captain's hand (he becomes the **carrier**), the wallet takes it from the rider, and card takes nothing
(reason in the function's docstring). `on_wallet_funded` runs after every completed topup — all three
topup paths call it — and asks the same question of whoever's wallet just grew. Both end in `try_collect`,
which reads the debtor from `carrier_driver_id` **first** and only then from `payer_user_id`: after a cash
handoff the rider has paid and the captain owes. Notifications are published from the routers **after the
commit** (`announce_ride_collection` / `announce_settled_for_debtor`), deduplicated by a Redis key rather
than a column — a notice is an event, not a record.

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

