<!--جديد-->
# STATE.md — ما بُني وما لم يُبنَ

> **كلُّ خبرٍ في هذا الملفّ يحمل تاريخَه. وما لا تاريخَ له يُقرأ «غيرُ مقيسٍ اليوم» — لا حالاً قائمة.**
>
> **وهذا ملفُّ الأخبار، وأخطرُ ما فيه أن يُقرأ حالاً قائمة.** وقد وقع مرّتين في أسبوعٍ واحد: **حالُ الخادم**، و**خبرُ المفاتيح الثلاثةَ عشرَ بلا زرّ** — كان صحيحاً يومَ كُتب، ثمّ أُصلح ولم يُحدَّث السطر، فنُقل تقريراً وبُني عليه ترتيبُ عملٍ كامل.
>
> **فقبل نقل أيِّ رقمٍ من هذا الملفّ إلى تقرير**: إن كان له حارسٌ يقيسه **فشغِّله ولا تنقل**، وإن لم يكن **فقُل «مكتوبٌ بتاريخ كذا، ولم يُقَس اليوم»**. **ونقلُ رقمٍ بلا أحدهما هو الخطأُ بعينه** — لأن التقريرَ يُقرأ قياساً.

**مُلزِمٌ بشرطه في `CLAUDE.md`**: *قبل أن تقول إن شيئاً مبنيٌّ أو ليس مبنيّاً، أو تنقل رقماً عن حال المشروع — يُفتح هذا الملفّ.*

**نقلٌ لا تحرير.** كلُّ ما تحت هذا السطر منقولٌ من `CLAUDE.md` بحرفه. وفهرسُه في `CLAUDE.md`.
<!--/جديد-->

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

**1028 backend tests pass** across 92 test files — measured, not estimated, on 2026-08-19. **Zero failures** — including the two that used to be flaky under full-suite load
(`test_card_money_never_passes_through_the_riders_wallet` and `test_wallet_ride_credits_earnings`).
The second one reappeared while building item 53 and was **not** flakiness: the level ordering read the
per-country discount on every offer attempt, an extra query inside the dispatch window. Removing it
where there is nothing to reorder fixed both the rule and the test — which is the reminder that
"flaky under load" is a hypothesis, not a diagnosis. All three
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

> **Session boundary, 2026-08-19.** Since stage 13 the following shipped and are committed: the
> **cancellation fee** in full, the **self-hosted WhatsApp channel** with OTP request caps, the **driver
> profile photo**, **generalised referrals**, **missions/levels/badges**, **backups end to end**, the
> **Google-Maps hand-off**, **map items 1–4**, the **unplanned stop point**, the **unified error
> contract** (§17, with the money-format sweep and the password blocklist), and **subscription offers**
> (item 54 — all six branches answered, built, and pressed on two phones; **its flag ships off**).
>
> **The OTP blocker is closed, and it was ours.** The gateway judged "sent" on an event Baileys never
> emits for a server ack, so a healthy channel reported failure and `otp.issue` deleted the digest of a
> code WhatsApp had already delivered — the **sixth shape** below. Nothing was wrong with the number.

**Stage 13 is complete** (2026-08-15) — `tests/test_stage13_scenario.py` **and six manual scenarios driven
on two real phones** (rider on an S21, captain on a Note 20, both Capacitor shells over the live tunnel):

1. **The whole journey** — a captain created from the app's own screens, three-step signup, vehicle and
   nine documents, admin review and approval in the panel, wallet topup, subscription bought from his
   screen, online, a real ride requested from the second phone, payment, rating, withdrawal request, and
   the admin's transfer.
2. **The cash round trip** — both sides at every step, with force-stop-and-reopen before *and* after the
   captain confirms.
3. **A CliQ dispute** — reference submitted by the rider, «لم تصلني» by the captain, resolved in the panel.
4. **Cancellation after acceptance.**
5. **Multi-stop** with a paid wait.
6. **The women's service, both directions.**

**Thirteen defects came out of it, and all thirteen are now fixed and committed** — eleven during the
scenarios, and the last two plus the two found in the multi-stop run in the batch of six below (which also
carried two defects the owner reported afterwards: the gender buttons and the cross-app login).
**The ledger held in every scenario**: sum of entries = last `balance_after`
for both parties, never negative, cash and CliQ writing commission with no earning, waiting charged to the
second (3.411 min ⇒ 0.141) on parameters frozen on the ride.

**The three screens that had never been opened are now opened** on a real device: the «طلب نسائي» badge
(measured **above** the fare — `٢٠ / طلب نسائي / ٩٫٨٢٦ د.أ`), the captain's preference strip («أستقبل
ركاباً: النساء فقط»), and the cancel-reason sheet.

### The batch of six is built and committed (`eac926e`, 2026-08-15) — and four things remain

**All twelve owner decisions were recorded first** (`SPEC.md` §5.10-ب for the stop point,
`design/CANCELLATION-FEE.md` §11 for the fee), three of them carrying his reasoning verbatim so it cannot
be undone later, plus his addition on branch (ب): **a captain who cancels pays nothing but is counted for
the supervisor** — and that count is a **live comparison** over `cancelled_by_driver`, never a stored
column, the same rule as "flagged" in the gender-mismatch reports.

Then the six were built in his order. What each settled:

1. **The cancellation fee is collected** — `services/cancellation.py`, `models/cancellation.py`, migration
   `0034`. See below; this was the project's last open **money** defect.
2. **One `settled` cure, not three** — `services/settlement.py`. Four screens were answering one question
   with four private comparisons, and three of them lied: `pending` read as "payment complete", a
   **cancelled** ride read as settled, and an open dispute not seen at all. The backend now answers once
   and publishes `settlement` (`not_due` · `due` · `awaiting` · `disputed` · `settled`); every screen reads
   it. **And the test iterates `PaymentStatus` itself** — the owner's condition — so a sixth value added
   tomorrow fails three tests in three places until it is classified in `_STATUS_ROLE`; proven by adding
   one temporarily and watching them fall.
3. **The role guard is at the door** — `core/app_scope.py`. Driver credentials opened the rider app. Each
   client declares its app on every session-issuing route, and login refuses a role that does not belong to
   it, with a message that says **where to go** rather than "forbidden". **The client's claim is accepted
   here because it only narrows**: whoever claims an app that is not his role merely locks himself out —
   which is why this does not contradict `card_gateway.return_url_for`, where such a claim would *direct
   money*. The test sweeps every (app × role) pair from the table itself: both directions and the panel.
4. **The gender buttons are gone from «حسابي»**, and the declared value stays visible with «لتعديله راجع
   الدعم». Three things flip on a tap otherwise — the pink theme, the women's-service control, and
   matching — and none of them is announced to whoever tapped.
5. **The stop badge is on the offer card**, above the fare like the women's and booking badges: a captain
   accepting a detour he cannot see cancels when he discovers it. **The count, not the addresses** — the
   card is read in seconds before the offer expires.
6. **The captain's waiting counter ticks locally** (`useElapsedMinutes`, every 10s — minutes are displayed,
   so a per-second timer wakes the screen sixty times to write the same number). It printed the backend's
   `waited_minutes` and froze at «٠ دقيقة» until a frame arrived, so a captain standing at a stop read a
   dead counter and **assumed his arrival was never recorded**. The project's own rule — the app renders
   the clock, the backend sends the money — was followed by one app and broken by the other.

**804 backend tests passed** at that point (up from 766); all three frontends built with their five guards green.

#### The cancellation fee: what is built, and the four things left

**The defect it closed**: `rides.cancellation_fee` was frozen (0.750 measured), displayed to the rider —
and **never collected**. No payment row, no ledger entry on either side, nothing for the captain who drove
toward the pickup. A number telling a rider he owes something **with no door to pay it**.

Built: `ride_cancellation_charges` with **both parties named** (the money passes between two users; the
platform carries it and does not own it), `cancellation_settings` per country, two ledger types
(`cancellation_fee` debit, `cancellation_compensation` credit — **two entries, never one net one**), the
proximity exemption measured from the **last broadcast location**, the **exemption on silence** (branch أ),
immediate collection when the wallet covers it, a debt when it does not — **and a cancellation is never
refused for an empty wallet** — plus the repeat-offence block on the request path (a live comparison; zero
means "no block"). The rider's wallet shows the debt *beside* the balance, the captain's shows pending dues
*outside* it, and the captain is told **which of the two happened**: "it reached you" and "it is waiting on
the rider" are different facts about his own money.

#### The four that remained are built (2026-08-15, second session) — and one item is deferred by a decision

**All four landed**: collection with a later ride (§5), the cash carrier path (§6-أ), the unpaid outcome
(§10), and both panel surfaces. Migration `0035`, `services/cancellation.py`,
`tasks/cancellation.py`, `routers/admin_cancellations.py`, and `tests/test_cancellation_collection.py`.
Six rules in them are worth carrying forward:

1. **Collection sits at the end of `payments.settle`, and its position *is* branch (و).** «العمولةُ
   أولاً — حقُّ المنصّة على رحلةٍ وقعت، والدَّينُ يبقى مطلوباً»; by the same reasoning today's captain's
   fare comes before yesterday's debt. That meant splitting `settle`'s second half into `_distribute`,
   because the old early `return` on "no commission" would have skipped everything after it — the shape
   that makes a rule work in half the cases with nothing failing.
2. **Assigning a carrier *moves* the debt, it does not add one.** The moment the rider hands the cash
   over, his liability is discharged **even if the carrier's wallet is empty** — so
   `carrier_driver_id IS NULL` is a condition in *every* question about what the rider owes
   (`_rider_debt_predicate`). Without it he is blocked from ordering over a debt he paid by hand, which
   is the worst thing a block threshold can do.
3. **The card channel deliberately does not carry the debt, and the reason is written down.**
   `ride_earning` and `commission` are both computed from `payment.amount`, so raising the charge by the
   debt charges commission on money that is not a fare — exactly what §5 forbids; and a second payment row
   would credit `ride_earning` to the **current** captain, not the injured one. Its exit is the topup
   (§7, wired into all three topup doors through one `on_wallet_funded`), and its guard is the block
   threshold. **A written decision, not a hole.**
4. **One wallet on both sides of a transfer is a real case** — a captain collecting, in cash, a fee owed
   **to him**. Both entries are still written (net zero); what changes is that they need **two different
   idempotency keys** and the credit goes first. With one key `wallet.record` finds the existing entry
   and returns it *silently*, writing half the event — the 12-ح referral lesson exactly.
5. **What he carries leaves `available_for_withdrawal`**, as the reserve does: a condition on withdrawal,
   never a ledger entry — an entry means money that *arrived*, and this is money in his pocket that is not
   his. And the grace expiry blocks him **from dispatch** through a prepared column
   (`drivers.cancellation_carry_blocked`), which is deliberately **not** `advance_blocked`: two debts to
   two different creditors in one column means repaying one lifts the other's block. Freezing the wallet
   would have been the wrong door — it would block the topup, i.e. the very repayment the block exists to
   force.
6. **`admin_decides` is not an action for the periodic job.** The three outcomes are «stays pending» ·
   «the admin writes it off» · «the company bears it», and a job that writes off in both of the last two
   collapses them into one and deletes the decision the setting exists to carry. So the job applies
   `company_bears` only — a credit with no matching debit, like `referral_bonus`, with an **actorless**
   audit entry naming the setting that decided (the `totp_reset` rule).

**And opening the panel found a second shipped defect — a money amount with no currency.**
`lib/format.ts::money(value, currency)` resolves the label itself, so `money(row.amount,
currencyLabel(row.currency))` hands it an already-resolved label, `CURRENCY_LABEL["د.أ"]` is
`undefined`, and the `?? ""` prints the number bare. `components/Advances.tsx` has done exactly that on
**both** its columns since item 15 — the same shape as the coupon table's bare `JOD`, arriving through
the opposite door. It was copied into the new charges table and caught by reading the DOM
(`٠.٧٥٠ ` with a trailing space), which is the rule: **measure the text, never the screenshot** — at
that size «د.أ» and «-.» are indistinguishable in pixels. Both call sites now pass `row.currency`.

**And the build found a shipped defect of this project's signature shape: a field with no sender.** The
driver's wallet screen has drawn «مستحقاتٌ معلّقة» from `pending_compensation` since the first batch — but
it reads `GET /wallet/me/driver`, and only `GET /wallet/me` (which the driver app never calls) was filling
that field. `DriverWalletOut` inherits it with a `0.000` default, so the line was silently never drawn and
nothing failed: not `tsc`, not `check:config` (which watches `GET /config` and the auth responses, not this
pair). An injured captain had no way to see what he was owed. Fixed in `get_my_driver_wallet`, which now
fills both that and the new `carrier_dues`.

**One item is deferred by a decision, and deliberately not half-built: the carrier's reward** (§6-أ — a
rating boost and a subscription coupon). The rating boost needs either a second column added to a value
`services/ratings.py` recomputes from the whole ratings table, or a synthetic rating row with no rider
behind it; and 12-ز's `promo_codes` is a **ride** payment channel — `driver_subscriptions` has no discount
concept at all, so this is a new money path, not "reuse 12-ز's machinery". Everything else in §6-أ works
without it. Recorded in `design/CANCELLATION-FEE.md` §6-أ with both reasons.

#### Three things the build itself taught, all worth keeping

- **`check:enums` caught a real collision.** Naming a `SettlementState` member `"none"` made `"none"` a
  *known backend value*, which flipped `VerificationMethod` from a pure UI union into a **mixed** one — the
  exact shape the guard exists for. The fix was the more accurate name (`not_due`), which solved both.
- **The concurrency test passed first with the lock order reversed**, so it did not own its invariant. The
  cure was an explicit interleave (the first holds its transaction 400ms while the second starts), and what
  deletion then produces is **not a wrong number**: `wallet.record` raises `InsufficientBalance` *inside
  the cancel path*, so the rider who pressed «ألغِ» ends up **in a ride that was not cancelled**. Read the
  order in `cancellation.try_collect` as the rule — **lock, then read the balance**; the reverse lets two
  concurrent debits read the same number.
- **`MissingGreenlet` on the exemption path.** Zeroing `cancellation_fee` on the ride expires
  `pickup_lat`/`dropoff_lat` (they are `column_property` expressions), and the serializer then lazy-loads
  outside the greenlet — a 500 on an *exempt* cancellation, found by the first test run. **Any update to a
  ride after it was read needs a second read**, always. And one more from the same file: a CHECK constraint
  whose full name exceeds Postgres' 63 characters is **truncated and hashed**, so its name in the database
  stops matching the model and `test_migrations_match_models` reports drift on every run.

### What stands between here and launch — the whole list, in order (2026-08-18)

**Nothing here is guesswork: every line has a written spec or an owner decision behind it.**

> **✅ RESOLVED 2026-08-18 — registration is unlocked, and the cause was ours, not WhatsApp's.**
>
> **This box used to say the sending number was restricted. That was wrong, and how it got written is
> the lesson** — see "The sixth shape" below. The self-hosted number (`218930385734`) was never
> restricted: WhatsApp acknowledged every message, measured at **122 ms** and again at **481 ms** after
> the fix. What failed was our verdict — the gateway judged success on an event Baileys does not emit
> for a server ack, so it was really waiting on the recipient's handset, and a phone that took longer
> than ten seconds to confirm produced a 503 **and made `otp.issue` delete the code WhatsApp had already
> delivered**.
>
> **Fixed in `whatsapp-gateway/src/session.js`** (three points): the verdict is the raw
> `<ack class="message">` node, `attrs.error` bounces immediately with the code WhatsApp wrote, and the
> delivery receipt is logged but never awaited. Verified live to `218916166400`: **HTTP 200 in 0.89 s**,
> ack at 481 ms, receipt at 2362 ms marked `awaited: false`. The owner confirmed the code on the S21.
>
> **Two things that were hidden are now visible**: Baileys' logger is no longer `silent` (it was
> swallowing `'received error in ack'` — the one line that would have said "WhatsApp refused this"), and
> the 60 s init-query timeout is gone (`fireInitQueries: false`; `<props protocol='2'>` is never answered
> while blocklist, privacy and the pings all are, so the socket was healthy and one unread query hung).
>
> **What still stands**: the SMS contract is off by the owner's choice, so `fallback_channel` is `null`
> and WhatsApp has no second channel behind it. That is now a resilience question, not a blocker — but a
> single-channel registration path with no fallback is worth a decision.

#### 0. The cancellation fee is finished — one sub-item waits on an owner decision

The last open **money** defect is closed and the feature is complete end to end: the fee is collected, the
ledger carries it between the two parties, a later ride settles it, the cash carrier path works, the unpaid
outcome is a per-country setting applied by a job, and the panel has both surfaces. **The only thing left
is the carrier's reward** (rating boost + subscription coupon), which is not buildable on existing
machinery without a decision — see above and `design/CANCELLATION-FEE.md` §6-أ.

#### 1. Blocking, and not code

- ✅ **The WhatsApp channel delivers, and the blocker was our verdict** (closed 2026-08-18). The table
  below is kept **because it is the record of a wrong diagnosis**, not because it is current. Read the
  right-hand column as "what our instrumentation reported", never as "what WhatsApp did":

  | Checked | What was reported | What it actually was |
  |---|---|---|
  | Session state | `linked`, `last_error: null`, `queue_depth: 0` | true, and still true |
  | Recipient numbers | all correct `+218…` | true |
  | Priority chain | picks `whatsapp_otp` | true |
  | The three per-user caps | never the blocker | true |
  | `onWhatsApp` | answers **exists** | true |
  | `sendMessage` | returns a message id | true, and it proves **only a websocket write** |
  | **«WhatsApp server ack never arrives»** | 10 s timeout on every number | **the server ack arrived in 122 ms.** The wait was on the *recipient's handset*, an event Baileys reports and our filter mistook for the server's |
  | Owner's phone: nothing in Chats | read as "restricted number" | not reproducible; the code arrives and was confirmed on the S21 |

  **Two real defects were found on the way and both were genuine fixes**: the gateway container's DNS
  resolver failing intermittently on `web.whatsapp.com` (now pinned to `1.1.1.1`/`8.8.8.8` — this is what
  actually swallowed messages, and it is closed), and `usePhoneCountry` falling back to dial code `"962"`.

  **What the ack work bought, corrected**: the three outcomes are still distinct and still right — `422`
  "not on WhatsApp", `503` "WhatsApp did not answer about the number", `503` "the channel is not carrying".
  What was wrong was only **which event decides the third**, and it now decides on the server's own ack.

- **The dedicated number's guards must not be relaxed while this channel is live**: it is never used for
  ordinary WhatsApp, and the message is **one fixed link-free text composed inside the gateway** — the
  backend physically cannot inject text.

- **The per-recipient hourly cap is 20** (raised from 3 by the owner, 2026-08-17, "raise it gradually with
  volume"). **It caps the recipient, not our sending number** — ours is guarded by the global 100/hour.
  Three was strangling because with SMS off there is no second channel, so it was a **cap with no exit**.

- **There is a fourth OTP cap nobody planned**, and it is what actually bit the owner twice:
  `routers/auth.py` has `OTP_PHONE_LIMIT = 5` and `OTP_IP_LIMIT = 20` per hour, **duplicating**
  `otp_limits`' own window cap (also 5/hour, per-country, admin-editable). Two caps for one concept, with
  **different messages**, so whoever is refused cannot tell which one refused them. Worth collapsing.

- **Provider wire formats** (Telr, SMS, CliQ, payout) are best-reading, never verified against real
  credentials — debt item 3 below.

#### 2. ✅ Backups — **built end to end** (2026-08-16)

All four steps in the plan's own order: the server (`backend/scripts/backup.sh` + `restore.sh`, a beat job
every 15 min, `backup_settings`/`backup_runs`, retention and alerts), the pull (`scripts/pull-backup.ps1`
over SSH+rsync, documented in `README`), the panel (button, table, schedule, guarded download under
«الأمان»), **and a real restore test that actually ran** — an encrypted backup decrypted, fingerprints
verified, restored into `taxo_restore_test`, ledger reconciling.

**The owner's seven decisions are implemented literally**, including the one that loses money if wrong:
**nothing unpulled is ever deleted, however many pile up** — the cap applies to pulled backups only, and
the rest raise an alert. `test_backups.py` fails when the `is_pulled` condition is deleted.

**Four defects came out of running it, not out of review**, and each is worth carrying:

1. **Two backups in the same minute nested inside each other** — the name was minute-stamped and `mv` over
   an existing directory **moves into it** rather than failing. The result reads as a valid backup until
   restore day. Now second-stamped **plus an explicit guard**.
2. **`pg_dump` newer than the server breaks every restore** — Debian's package is 17, the server is 16, and
   `pg_restore` emits `SET transaction_timeout` which 16 rejects: a **successful restore that reads as
   failed**, which teaches the reader to ignore the error. Pinned to client 16 from PGDG, **with the
   codename read from the image** (the first attempt installed `bookworm` on a `trixie` image).
3. **A shell script with Windows line endings does not run in the container**, and the breakage lands the
   day the backup runs. `.gitattributes` pins `*.sh` to LF — and it came back twice, the second time
   because `pathlib.write_text` itself translates newlines on Windows.
4. **The ledger check reported a healthy wallet as broken.** Two entries written in one transaction share
   `created_at` exactly (a topup that collects a cancellation debt), and tie-breaking by `id` is random.
   **A false alarm here is worse than none** — it teaches its reader that "1" is normal. The check now
   measures what does not depend on order: **the sum equals one of the recorded balances**.

**And "last success" reads the disk before the table**: `backup_runs` records attempts that went through
the app; the disk records what exists — and the owner also runs `backup.sh` over SSH.

#### 3. The three registered specs, in the owner's order

| # | Item | Spec |
|---|---|---|
| 1 | ✅ **The driver's profile photo** — built 2026-08-16, see below | `FUTURE-FEATURES` 52 |
| 2 | ✅ **Generalising referrals** — built 2026-08-16, backend + all three surfaces | `design/REFERRALS-GENERALIZATION.md`, `FUTURE-FEATURES` 51 |
| 3 | ✅ **Missions, levels and badges** — built 2026-08-16 | `design/MISSIONS-LEVELS.md`, `FUTURE-FEATURES` 53 |

**All three are done, so what remains before launch is backups, then «افتح في خرائط قوقل», then the
map work** — plus two small tails recorded below (the `active_hours` metric and the badge-grant
button), and the WhatsApp/provider items in §1.

##### Generalising referrals (item 2) — four owner decisions, and the two defects only a browser found

`referrals` replaced `driver_referrals` with **both sides pointing at `users`** (migration `0038`), and
`referral_code` moved from `drivers` to `users` with it. **The alternative — a `referral_type` column on
the old table — makes a table with a column that lies**: a rider has no `drivers` row at all, so the
type would say "rider" while the FK pointed at a captain. **And there is no `referral_type` on the
referral row either**: the type is derived from `users.role`, which is fixed for the life of an account;
where it *is* written is the **settings** table, because a row there **is** the programme.

The owner's four answers, each with the condition he attached:

1. **The female bonus is a bonus, not a third programme** — added to `reward_amount` in **one ledger
   entry** when the referred driver is *stamped* female. Had it been its own programme with its own
   amount, an unset amount (zero) would pay **nothing** for referring a woman and the full amount for
   referring a man — the incentive inverted in silence. His guard: never stored negative (service *and*
   CHECK), and never displayed apart from the base — the panel and both apps state the **total**.
2. **The programme is chosen by the referred user's role**, not the referrer's. So a rider signing up
   with a code is now **accepted where it used to be refused** — and the refusal itself had become the
   lie ("wrong code" about a correct one).
3. **The monthly cap blocks payment, not attachment**, measured by the **month the referral was created**
   (by payment month it would be a disbursement schedule, not a cap). The referral is still recorded and
   attributed, and the referrer is told: `over_monthly_cap` is published and both apps render it.
4. **"Subscription" means bought at least once**, not "active at payment time" — his words: a right
   earned is not erased by the passage of time, and reading it live makes entitlement dance with the
   captain's calendar. `driver_subscriptions` has no `pending` status, so the row's existence *is* the
   purchase.

**The lock that guards the cap is the referrer's wallet lock, not the referral row's.** The row lock
stops one referral being paid twice; it does nothing about **two different rows for one referrer** paid
at once, each reading the same count. And the first version of that test **passed with the lock
deleted** — `asyncio.gather` finished the first before the second began. Rewritten with an explicit
interleave (400ms hold, 100ms stagger) it now fails on deletion: two payments of 5.000 against a cap of
one, with no exception and no log line.

**The welcome coupon sits in an `else`, not beside it.** Whoever typed a code chose that offer;
substituting another — even a larger one — shows them what they did not ask for. And **it never fails
the ride**: the rider did not ask for this gift, so an error on "request a ride" because of it is the
worst thing a welcome offer can do. Only the expected refusal is swallowed (`AppError`), so a
programming error stays visible — the 12-ط lesson. `promo.find()` now hides `is_public=false` from the
request path: a private code passed between people makes money earmarked for one person available to
everyone who learns it, and its budget is consumed by people nobody referred.

**Two defects the browser found, and neither had any other detector:**

- **The referral code box was empty.** `0038` moved the captains' codes — all that existed — so every
  account that is not a captain had `NULL` (20 of 35 here), and "copy"/"share" worked and copied
  nothing. The backfill is migration `0039`, **not lazy generation on first read**: that needs a lock,
  and without one two taps generate two codes and one overwrites the other — possibly after the first
  was copied and sent. And its `downgrade` deliberately **does not erase them**: a code in a friend's
  hand must not be invalidated by a reverse migration.
- **«٨ د.أ» beside «٥٫٠٠٠ د.أ»** — I was summing the total in the app with `Number(a) + Number(b)`,
  which is money through a float, forbidden by §14. `female_total_amount` is now computed in the backend
  and read by all three surfaces. The same pass found `rewarded_total` serialising as `"0"` while a
  `MONEY` column serialises as `"5.000"`; it is quantized now.

##### Missions and levels (item 3) — the constraint is the whole feature

**The nearest driver stays first. The level separates the close ones and never outranks distance.** The
built formula is the owner's choice (b): **effective distance = distance − the level's discount in
metres, capped at 100 m**, guarded in the request model, the service **and** a CHECK. The rejected
slab formula is kept in the design file as the reason it was rejected: its edge is hard — 499 m and
501 m fall in different slabs, so two metres flip the rule — and its worst displacement is the whole
slab, not the stated number.

Three rules are worth carrying forward:

- **The level is a computed value with exactly one writer**, and that resolves an apparent conflict
  between two project rules: "never store a judgement" (referrals) versus "no extra query on the
  dispatch path". Its precedent already exists — `drivers.rating_avg`, rebuilt in full from its source
  and read in dispatch without a query. The difference from the rejected `qualified_at` is not storage
  but **who writes and when**. `tasks/levels.py` is the only writer; the ride-completion and rating
  paths do not touch it, and `level_computed_at` gives "when was it computed?" one answer.
- **Progress is measured live and never accumulated in a column** — so lowering a target in the panel
  raises whoever was waiting on it in the next cycle, touching no row. And editing a mission triggers an
  **immediate** re-evaluation for that country, or the level would outlive the definition it was
  computed from.
- **Badges never enter the dispatch order, and that is why they are a separate table.** The level is
  measured from work done; a badge is human recognition. Letting recognition raise ride volume makes the
  supervisor **hand out money**. There is deliberately no "raise this captain's level" button anywhere.

**And the driver's screen states the effect in metres because a measured sentence can be checked.**
"Brings you 50 m closer to nearby requests — and the nearest to you is always still first" is true and
verifiable; "priority on requests" is read as a promise of more rides, which the captain then counts and
does not find.

**One thing the suite caught that was mine, not flakiness**: the ordering read the per-country discount
on *every* offer attempt — an extra query inside the 20-second window, which is exactly what §5-ج
forbids. It now reads it only when there is more than one candidate to reorder; a single candidate is
first whatever its level.

**What is not built, and is written down rather than half-done**: the `active_hours` metric (presence is
a 60-second Redis key and `is_online` says "the switch is up", so it needs a new daily capture table —
its own item), and **the badge-grant button in the panel's driver drawer**: the catalogue, the grant and
revoke endpoints and their tests exist, but no button reaches them yet — a door with no button, which is
this project's own recurring shape and is why it is named here.

##### The profile photo (item 1) is built — and its two hard edges are the interesting part

`profile_photo` is a fifth document type on 9-ب's machinery, and everything about it follows from one
fact: **it is a reviewed document and a published image at once**, and no existing path is both.
`document_response` checks ownership and answers `private, no-store`, which is right for an identity
paper and wrong for a face the rider must see. So there is a **second, narrower** door —
`GET /rides/{ride_id}/driver/photo` — whose key is **the ride, not the driver**: the rejected shape is a
route taking `driver_id`, which shows every captain's face to whoever counts identifiers.

**The requirement is per-driver, not a table.** `REQUIRED_DOCUMENT_TYPES` became
`required_document_types(gender_verified_female=…)`, because a single list would block the approval of
the very person the exemption exists for. And the exemption reads **the stamp, never the declaration**
(`gender_verified_at IS NOT NULL`) — reading `users.gender` would drop an identification requirement on
**a word anyone can type about themselves**. Same reading as 10-ج's matching and 12-ح's referral, same
reason: what constrains only you may be written; what lifts a rule needs a stamp.

**It does not apply retroactively** (owner's decision, 2026-08-16): it binds whoever is approved *after*
it, and everyone approved before becomes a backlog chased one by one from the drivers screen, where
`missing_required` now lists it. That falls out for free because `approve` only runs on a new approval —
**but it exposed a rule that had been silently safe until now**. "Replacing a required document sends an
approved driver back to review" was written when every approved driver necessarily held every required
document; with a requirement added later that stops being true, and the rule would have unapproved a
backlog captain **for doing exactly what we asked**. It now also requires that a row already existed —
i.e. that it is genuinely a replacement — which is what the rule always meant.

**And the rider sees a face or a letter, with nothing distinguishing the two reasons.** An exempt woman
and a captain whose photo is still under review both render the first letter of the name, and no text
separates them — because a label that did would make the *absence of a photo announce that she is a
woman*, which is the thing the exemption exists to prevent. There is deliberately **no `has_photo`
field**: the image request is its own answer (bytes or 404), and a second field claiming "she has one"
is a second home for a truth the file already holds.

#### 4. ✅ «افتح في خرائط قوقل» — **built** (2026-08-16)

`driver-app/src/lib/external-maps.ts` + a button on the active-ride card. **One correct destination at a
time, never a list**: pickup → next unvisited stop → dropoff, and **hidden at `arrived`** because he is
standing there. `geo:` on Android so any installed maps app opens, with a web fallback so the button is
never dead. **Not claimed to work until tried on the device inside the Capacitor shell** — the item's own
warning, still outstanding.

#### 5. The map work — **1–4 built, 5–6 remain** (2026-08-16)

**The item is halved: the captain's half is what gets built.** The owner's six, with what happened:

| # | What | State |
|---|---|---|
| 1 | **Full gestures** | ✅ written explicitly (`dragRotate`, `pitchWithRotate`, `touchZoomRotate`, `touchPitch`, `doubleClickZoom`, `maxPitch: 60`) in both PWAs |
| 2 | **Three-state locate button** | ✅ `driver-app/src/lib/follow.ts` — `free · follow · heading` |
| 3 | **Live ETA, computed locally** | ✅ `driver-app/src/lib/eta.ts` — no polling |
| 4 | **Capped reroute** | ✅ 3 per ride, **counted in a column**, `POST /rides/{id}/reroute` |
| 5 | **Next instruction** (store `steps`) | ❌ needs a schema change |
| 6 | **Navigation camera** | ❌ **and must not be built until frames are measured on a real device** — the item's own condition |

**On item 1, the plan's premise was wrong and it was measured, not assumed.** The plan called gestures
"absent in all three apps — a defect". They were not: `mapbox-gl 3.9` enables them by default, nothing in
the project disabled them, and `touch-action: none` on the canvas is Mapbox's own. **Then it was proved on
the owner's Note 20** inside the Capacitor shell — a real two-finger rotate dispatched over CDP flipped
the camera mode, i.e. `rotatestart` fired. So what was actually built is **writing the values down**: a
library upgrade that changes a default would otherwise drop a gesture with no line changing here and no
test failing.

**Item 2's rule worth keeping**: the exit to `free` happens **by his hand, not by a button** — dragging is
the command. A camera that drags him back after a second makes looking ahead impossible, which is the
commonest complaint about navigation apps. And **from `free` the button returns to `follow`, not
`heading`**: someone who panned away wants to find himself, not to have the map spin under him.

**Item 3's number is the owner's**: at 1,000 rides/day a polled ETA takes Directions from 120k to **870k**
calls a month for a figure that changes by the minute. So distance comes from the line already frozen on
the ride and speed from the captain's own movement over an 18-second window. **And no figure is shown
before a real speed is measured** — a number built on an assumed speed reads as a promise and is then
broken.

**Item 4's rule is the money one**: the reroute is **the only thing that calls Directions again**, so the
cap is a **column** (`rides.reroute_count`), not a counter in memory that the first deploy resets, and it
is enforced **in the backend** — a client that counts for itself is a client that directs spending, the
same reasoning as `card_gateway.return_url_for`. Failure keeps the old line and **consumes no quota**: a
call that never landed cost nothing, and charging it makes the outage a punishment. In the app, **three
consecutive readings over 80 m** before declaring drift — one GPS jump would otherwise buy a paid call.

**One thing the suite caught that was real**: the ordering read the per-country discount on *every* offer
attempt — an extra query inside the dispatch window, exactly what §5-ج forbids. It now reads it only when
there is more than one candidate to reorder, and that removed a long-standing "flaky under load" failure
in `test_driver_earnings`. **"Flaky under load" is a hypothesis, not a diagnosis.**

**Deferred by decision**: traffic overlays (a day+ for an uncertain return) and the tap-a-point info card.

**The cost arithmetic that produced this order** (at 1,000 rides/day): today ≈ 4 Directions calls per ride
→ 120k/month; navigation with a capped reroute → 270k; **a polled live ETA → 870k**. Navigation is not what
raises the bill — polling is.

#### 6. The unplanned stop point — built, all six branches (2026-08-16, SPEC §5.10-ب)

Backend + both apps + panel. `ride_pauses` (migration `0043`), `services/pauses.py`,
`tasks/pauses.py` every minute.

> **Branch (و) is two halves and both are built** — *"inside `final_fare`"* and *"a separate
> line in the breakdown"*, the second landing 2026-08-21 and measured from the DOM on all four
> screens (the rider's ride details, the rider's payment screen, the captain's «تفصيل السعر»,
> and the panel). `RideOut` publishes `stop_fee` and `stops_charge` — **multiplied in the
> backend, because a screen does not multiply money** (§14) — and `AdminRideDetail` publishes
> all five from **the same service door that computed `final_fare`**, so there is no second
> number resembling the first (the eighth shape). Its guard is
> `test_the_panel_reads_the_same_numbers_the_two_apps_read`, which compares the two responses
> field by field and `assert`s the measured value is non-zero first, so it cannot guard an
> empty ledger — verified in both directions.
>
> **The line it corrects used to say the second half was built nowhere, and that line outlived
> the defect by a day** (deleted 2026-08-22 along with SPEC's stale subsection): the fix landed
> the same day the measurement did, and the description stayed. **The lesson is kept below
> under "the thirteenth shape", where it belongs** — a money amount rendered while it accrues
> and silent when it is charged, which no guard could see: `check:config` asks whether a
> published field has a *mirror*, never whether it has a *reader*, and `check:readers` sweeps
> `lib/` only.

**A table of its own, not a column on `ride_stops`**: a planned stop is decided by **the rider before the
request** so it enters the estimate, the distance and the fee; a pause is pressed by **the captain during
the ride**, after the fare was quoted. A pause slipped in among stop rows would change `stops_count`, the
stop cap, the offer card and pricing — four things nobody asked for.

**The branch that guards money is (هـ)**: the arrival counter **does not start outside the pickup radius**,
in the owner's words — «وإلا صار «وصلت» الكاذبُ باباً للكسب». And **silence means no counter**: the doubt
belongs to whoever would be charged. The distance function is **borrowed from the cancellation-fee
exemption, not written again** — two formulas for one distance drift, and one of them decides money.

**And its money guard is a partial index** (`uq_ride_pauses_open`): two simultaneous presses would open two
pauses and **bill one wait twice**. Verified by deletion — and deleting it from the *model* is not enough,
because the migration is what creates it.

**Parameters are frozen twice, not once**: on the ride at creation (what was shown to both parties) and
onto each pause row at press time (what **that pause** was billed at). Without the second, one edit to the
ride row would re-price a pause that already happened.

**And opening it in a browser found what fourteen tests did not.** `POST /rides/{id}/pause` returned `200`
with **`open_pause: null`** — the row was written and the response denied it, so the strip never drew and
the whole feature was invisible. Cause: `Ride.pauses` is loaded with the row, and the ride object has been
in the session's identity map since the top of the function, so re-reading returns **the same object with
its stale collection**. `session.expire_all()` before the re-read is the fix. **The tests missed it because
they read rows from a fresh session — they see what the app cannot.**

**Both strips were then opened and measured**: captain «وقفة · ٢ دقيقة · ٠٫٦٠٥ د.أ» with a resume button,
rider «رسم الانتظار حتى الآن · ٣٫٤٥٠ د.أ» with a live seconds counter — and the cap notice appeared in the
rider's screen on its own («تجاوز الانتظارُ الحدَّ المسموح») while the ride stayed `in_progress`, which is
branch (أ) proving itself in the UI.

**A reading the owner should confirm**: the per-minute rate is **one number for both cases** (mid-ride
pause and arrival wait). His text said "likewise set by admin", read here as one concept — a captain's
waiting minute is worth the same either way, and two numbers for one concept drift. The free grace applies
to **arrival only**.

#### 7. ✅ Subscription offers — **built end to end** (2026-08-19, `design/SUBSCRIPTION-OFFERS.md`, `FUTURE-FEATURES` 54)

**All six branches answered by the owner, then built in §9's order** (tables → service → panel → captain
screen → two phones). Migration `0044`, `models/subscription_offer.py`, `services/offers.py`, the panel's
offers screen, and the captain's struck price. **The flag ships off**, per his instruction.

The first branch decided the tables and is worth keeping in front of anyone extending it: **the discount is
money, not time.** «10% off» lowers `amount_paid`; «a free week» would extend `expires_at` and touch no
money — and combining both in one cut makes "how much did we give away?" a question with two units. His
condition on top: **the row carries an explicit type column**, so adding time later is a new value rather
than a reinterpretation of the money columns.

Six rules from the build, each of which cost something to learn:

- **The discount is computed in `subscriptions._create` and nowhere else.** Every channel — wallet, cash,
  CliQ, card, the admin's manual record — passes through it, so a second computation is a rule that two
  channels can disagree about. `record_manual` stamps the offer and **keeps the admin's typed amount**,
  flagging the row «تسويةٌ يدوية» when the two differ: a human collecting cash is the authority on what he
  collected, and silently overwriting him would hide a real shortfall.
- **`promo_codes` is not reused, and the reason is not naming.** That is a **ride** payment channel the
  company bears on the rider's behalf, measured by summing `promo` rows. A subscription discount is
  **revenue not collected** — no ride, no payment row, nothing to sum. An expense and an uncollected
  revenue do not belong in one report. This is also what had been blocking the cancellation carrier's
  reward (`CANCELLATION-FEE.md` §6-أ); item 54 gives it a home.
- **The use cap is guarded by the offer row's own lock, and the wallet's advisory lock does not help.**
  Measured, not assumed: the first concurrency test passed with the offer lock deleted, because `gather`
  over HTTP did not interleave. Rewritten with two sessions and an explicit hold (400 ms / 100 ms
  stagger), deleting `with_for_update` gives **two subscriptions on a one-use offer**. Three tests own
  this and are named in `SPEC.md` §8.1.
- **Four columns, not one**: `offer_id` (`RESTRICT` — an offer with purchases behind it may not be
  deleted), `discount_amount`, `offer_discount_amount` and `list_price`. Frozen at purchase, like
  `commission_percent_at_ride`, so editing an offer never moves a sale that already happened.
- **The exhausted offer is named and never applied** — «استفدتَ من هذا العرض من قبل». Someone who saw a
  discount and then finds it gone reads the app as broken. And the distinction is the point: whoever
  **used** it is told, whoever never qualified is told **nothing** (branch و), and the line never shows
  beside a live discount.
- **`services/offers.py::exhausted_for` is read through `_plans_with_offers`, shared by `/plans` *and*
  `/me`** — the eighth shape below, found on the phone because the desktop probe called the API directly.

### The Jordan channel is the launch blocker, not Libya (2026-08-19)

**A read-only audit inverted the assumption this project had carried for weeks.** `+218` is the market
whose verification channel is proven — on the wire, in the database, and in the tests. **Jordan, the
launch market, had no working channel at all.**

Measured from the code that decides, not from a table: `method_for_phone('+962…')` returned
`firebase` alone, and Firebase answers `auth/billing-not-enabled` (stage 13, owner declined Blaze). The
SMS contract is inactive and mock-only. `otp_verification_enabled` is on — so verification was
**required and impossible**. The 31 "verified" Jordanian accounts prove nothing: seeded directly, or
verified through the mock SMS contract activated to get past Firebase.

**The owner then authorised enabling `whatsapp_otp_enabled` for Jordan and exactly one message.** It
needed no code and no new contract — the WhatsApp contract is **global** and the flag is **per-country**,
so one row changed the market's channel. Measured end to end: backend handed the gateway
`purpose=registration, deliver=True`, 88 bytes; the wire carried the same text; WhatsApp acked at
**1026 ms** with `error: null`; the delivery receipt landed at **2350 ms**. `SPEC.md` §24.7.

**Three things are now measured rather than assumed** (§24.8): the sending number is a **bare Libyan
number with no display name and no verification** (`me.name = null`, `registered = false`) — a
verification message from an unknown international number is shaped like fraud, and reports are what
get unofficial numbers banned; the only emergency exit is switching verification off entirely, which
means **accepting every number unproven** in a system with wallets and transfers; and "a session per
market" **does not exist in the code** — one global contract, one socket, one auth directory, with the
seven layers it would take written down and not built.

**And the hole stopped being hypothetical one second after that message was delivered.** `Stream
Errored (conflict)` — the account was opened elsewhere and evicted our session, so registration
stopped **in both markets at once** and stayed stopped until a human scanned a QR. Detection worked
(an inbox row and a push to every admin at **53 s**, since `awaiting_qr` is in `URGENT`); the repair is
what is human.

**One more thing the audit closed**: `OTP_PHONE_LIMIT` in the router duplicated
`otp_settings.max_per_window` — two homes for one concept, with different messages and *different
counts* (2 against 1 on one phone, because the router counted before sending and the settings after
success). The router's per-phone cap is gone; the IP cap stays because it answers a different question
(`otp_limits` counts the phone by design, so dozens behind one café network never throttle each other).
And `CODE_TTL_SECONDS = 300` — the one number in this project with no reason written above it — now
carries its measurement: delivery consumes **0.78%** of it, so what actually spends the window is a
human round-trip, and it once expired 22 seconds short.

### The dev stack has been mutated by the scenarios — do not read it as the intended state

The scenarios needed real values, so the local database now has: **JO commission 10% `all_rides`**,
**multi-stop enabled for JO** with stop fees (0.500 + 0.100/min, 2 free, 15 cap), **min withdrawal 5.000
and reserve 5.000**, an **active mock SMS contract**, **advances enabled for JO**, and a fresh captain
`سالمُ المرحلة` (+962791300013) alongside the five documented accounts. `FEATURE_DEFAULTS` — not
`SELECT * FROM feature_flags` — is still the answer to "what ships".

**1028 backend tests pass** across 92 test files, measured on 2026-08-19; all three frontends build with
their guards green (`check:scale`, `check:enums`, `check:slot`, `check:config`, `check:target`,
`check:dist`, and `check:flags` in the panel).

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

Its two comparisons and their reasons are in `admin-panel/scripts/check-flags.mjs` — read them there,
not here.

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

### Subscription offers (item 54) — built end to end (2026-08-19)

**All six branches of `design/SUBSCRIPTION-OFFERS.md` §8 were answered by the owner before the first
migration**, as that file required. The discount is **money, and a percentage** — `discount_type` is an
explicit column from day one (`money_percent`), and it is `VARCHAR(16)` **not** a Postgres enum, so a
time-based type later is code with no migration: the `feature_flags.feature_key` exception, for the
same reason.

**Four columns on `driver_subscriptions`, not three, and the fourth is the interesting one.**
`list_price` (frozen), `discount_amount` (**what we actually gave up** = `list_price − amount_paid`),
`offer_id`, and `offer_discount_amount` (**what the offer decided**). The last exists because the owner's
"manual adjustment" mark is only truthful with it: recomputing from the offer's percentage drifts the
first time the offer is edited, so the mark is a **live comparison of two frozen numbers** — and no
`manual_adjustment` column is stored, per the "flagged is measured, never stamped" rule.

**One rule for the discount across all four channels**: `discount_amount = list_price − amount_paid`.
Wallet and card make them equal by construction; cash and CliQ diverge when the admin collects something
else — and "how much did we give up?" keeps one answer with no branch. The panel **pre-fills and does
not force**, because `record_manual` already accepted a different amount ("خصمٌ أو تسويةُ فرقٍ يقرّرها
المشرف") and removing that would change existing behaviour.

**The design's §4 said to compute inside `_create`; that would have created money from nothing.**
`purchase_with_wallet` debits the wallet **before** the row is written, so a calculation inside the
writer debits 30 and records 27. The offer is now resolved *before* the money moves, and `_create`
stays the only writer of the four columns. The card path applies it to the **order amount at open**, for
the same reason: an order opened at full price with a discounted row after it collects what was never
deducted.

**Two locks own the per-driver cap, and either suffices** — see `SPEC.md` §8.1 for the measured detail,
including the fact that **the wallet advisory lock does not guard it** (resolve runs before record, and a
lock taken after the read serialises nothing). Both concurrency tests passed at first *with the lock
deleted*, because `asyncio.gather` over HTTP let the first commit before the second began; rewritten with
an explicit interleave, deleting both locks yields `['3.000', '3.000']` — an offer capped at one use
granted twice.

**And opening it in a browser found what 16 passing tests did not** — the discount was computed on
`/subscriptions/plans` and not on `/subscriptions/me`, which is the door the captain's screen actually
reads. Both now go through `_plans_with_offers`. That is **the eighth shape**, written up on its own
below, because it is not about offers.

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
twelve jobs).
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

**What waits on the owner as of 2026-08-18 — the first one blocks launch outright:**

0. ✅ **Closed 2026-08-18 — WhatsApp delivers.** The channel was never the blocker; our success criterion
   was. What remains is a smaller question the owner should still answer: **whether registration ships with
   one channel and no fallback.** SMS is off by his choice, so `fallback_channel` is `null` — the day the
   number is genuinely banned or the session drops, registration stops with no automatic exit. Re-activating
   the SMS contract is a field in the contracts page and no deploy.
1. ✅ **Closed 2026-08-19**: the six branches of subscription offers were answered and item 54 is built.
   **What it leaves behind is a «باب بلا زرّ» entry, not a decision** (`SPEC.md` §18.2): `ends_at` has no
   field in the panel and the `manual` audience has no grant button, so both are built and unreachable.
2. **Whether the per-minute pause rate should be two numbers, not one** — built as one; see item 6 above
   for the reading and its reason.
3. **Whether to collapse the duplicated OTP cap** — `routers/auth.py` keeps its own per-phone 5/hour beside
   `otp_limits`' window cap, with a different message. It is what actually refused the owner twice.

**And these two were already waiting**, both raised by finishing the cancellation fee rather than by
anyone guessing:

1. ✅ **The carrier's reward is closed, not open** — the owner **dropped it on 2026-08-16**
   (`design/CANCELLATION-FEE.md` §6-أ) for the reason recorded there: a rating boost needs either a
   second column beside a recomputed value or a synthetic rating row with no rider behind it, and a
   subscription coupon is a **new money path** wearing 12-ز's name (`promo_codes` is a *ride* channel).
   **What replaced it is built and running**: an explicit thank-you by name at the head of
   `publish_cancellation_carried` — the carrier loses nothing (net zero), so what falls on him is
   thanks, not a price. This entry survived here as "open" after the decision; corrected 2026-08-20.
2. **Whether the company bears the remaining rider's difference *before* departure** in ride sharing —
   his own earlier deferral (`SPEC.md` §5.12).

Everything else — the twelve branches (six for the cancellation fee, six for the stop point), the backup
plan's seven, the map plan's four, the nine advance decisions, the eight sharing decisions — is answered
and recorded in its own file.

**And the stop point (`SPEC.md` §5.10-ب) is now decided and not yet built**: a per-country cap that
notifies and never ends the ride, the counter stopped by the captain's tap, no cap on the number of stops,
the arrival counter starting on that tap, **no counter outside the pickup radius** (or a false «وصلت»
becomes a way to earn), and the amount inside `final_fare` with its own line in the breakdown.

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
2. ✅ **Closed on 2026-08-15**: the three screens that had never been opened — the cancel-reason sheet,
   the «طلب نسائي» badge, and the captain's preference strip — were all opened on a real phone during
   stage 13's scenarios.
3. **`drivers.is_online` stays `true` for captains with no presence in Redis** — measured on 2026-08-15:
   two rows said online while `geo:*` was empty, left behind by apps force-stopped without their sockets
   closing cleanly. It harms no money and draws no phantom cars (every map path reads Redis), but **a column
   that says what is not the case will mislead a report one day**, and the owner asked for it on the list.
   The honest fix is to stop treating it as an answer to "is he here": either derive "online" from presence
   wherever it is read outside dispatch, or have a periodic sweep clear the column when the key is gone.
4. **Provider wire formats are best-reading, not contracts.** Three details in
   `services/card_gateway/telr.py` are flagged in its docstring as needing confirmation against
   real Telr docs/sandbox credentials (never delivered), and `services/sms/`, `services/cliq/`,
   `services/payout/` say the same in their module docstrings. They are arranged so being wrong
   cannot move money wrongly, but they cannot go to production unverified. **`services/whatsapp/`
   is the one provider written against real published documentation** (Meta's Cloud API), so it is
   not in this list — but its authentication template must be approved in the Meta console before
   the channel works anywhere.
5. **Six finished features are switched off waiting for the owner, and two of them also wait on a
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
6. **`FUTURE-FEATURES.md` items 45, 47 and 49** are what remains deferred from the women's service:
   the in-ride emergency button (deliberately *not* half-built — a button promising help nobody
   answers is worse than none), "wait for a female captain" (needs a queue that outlives
   `no_driver_found`), and in-app calling/messaging (needs number masking). Item 46 (referral
   incentives) shipped as 12-ح; item 48 (the "3 nearby" count) is now one of the four post-launch
   deferrals above.
7. **`GET /config` publishes no wallet limits**, so `customer-app/src/lib/wallet.ts` holds the three
   quick-topup amounts as a local constant. They are *suggestion chips*, not limits — the backend
   still validates every amount — but they are the one place the rider app carries a number the
   backend did not send, and the honest fix is to publish `wallet_settings` in the config payload.
   Small, and worth doing the next time a wallet screen is touched.
8. **This machine only**: host port 5173 is taken by an unrelated `taxo-web` stack, so
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


<!--جديد-->

## بنودٌ مفتوحة — 2026-08-25

**بندان، ولا شغلَ فيهما اليوم بقرار.**

### ١ — `check:money-visible` يسطّح ثلاثة أسطحٍ في مجموعةٍ واحدة (2026-08-25)

**الحارسُ يجمع قُرّاءَ التطبيقات الثلاثة في `Set` واحدة**، ثمّ يسأل «أيقرأ هذا
الاسمَ **أحد**؟» — فقارئٌ في سطحٍ **يُسكت مرآةً بلا قارئ في سطحٍ آخر**.

**والقياسُ بعد إصلاح ثغرة التعليق (اليوم)**: **٣٧ حقلَ مالٍ** في المخططات ·
**٦ أزواجٍ** (اسم × تطبيق) فيها مرآةٌ بلا قارئ · **٤ أسماء** — وذلك خارج
استثناءَي `DELIBERATE` (`max_amount` و`list_price`).

**وهو الشكلُ الخامسَ عشر بعينه**: *حارسٌ صادقٌ تُوسَّع دعواه فوق نطاقه*
(`PATTERNS.md`). دعواه الصادقة «لا يقرؤه **أحد**»، وتُقرأ «يقرؤه **كلُّ** من
يعلنه» — وبينهما ستّةُ أزواج.

**ولا تُفصَل المجموعاتُ اليوم** (قرارُ المالك 2026-08-25): فصلُها قرارُ نطاقٍ
لا إصلاحُ عطب، ويحتاج جواباً عن «أكلُّ مرآةٍ في كلِّ تطبيقٍ تستوجب قارئاً؟» —
وهو سؤالٌ يخصّ ما تعرضه كلُّ شاشة، لا ما يمسكه حارس.

### ٢ — أربعةُ حقولِ مالٍ لها مرآةٌ بلا قارئ في سطحها (2026-08-25)

`outstanding` · `paid_amount` · `stop_fee` · `carried_cancellation_fee`

| الحقل | مُعلَنٌ بلا قارئ في | يقرؤه فعلاً |
|---|---|---|
| `stop_fee` | `customer-app` · `driver-app` | اللوحة (`Pricing.tsx`، `Rides.tsx`) |
| `paid_amount` | `customer-app` · `driver-app` | اللوحة (`Rides.tsx`) |
| `outstanding` | `driver-app` | تطبيق الراكب (`Payment.tsx`، `RideDetails.tsx`) |
| `carried_cancellation_fee` | `customer-app` | تطبيق الكبتن (`OfferSheet.tsx`) |

**واثنان منها كان أثرُهما الوحيدَ في سطحهما تعليقاً**: `stop_fee` في
`customer-app/src/components/home/ConfirmRide.tsx` رأسَ الملفّ،
و`outstanding` في `driver-app/src/screens/Collect.tsx` رأسَ الملفّ — **فكان
الحارسُ يعدّهما مقروءَين**، وهو ما أُصلح اليوم.

**وهذه أخبارٌ لا أحكام**: أنّ لحقلٍ مرآةً بلا قارئٍ في سطحٍ **ليس عطباً بذاته**
— قد يكون الحقلُ لا محلَّ له في تلك الشاشة أصلاً. **وتقريرُ أيِّها عطبٌ وأيِّها
مرآةٌ زائدةٌ يُطلب معه فتحُ الشاشات**، ولم يُفعل اليوم.
<!--/جديد-->
<!--جديد-->

## القياسُ الحيُّ لمفاتيح الميزات — 2026-08-25

**العددُ ٢٤ لا ٢٢** (`HANDOFF.md` §أ يقول اثنين وعشرين، وهو الرقمُ الشاردُ
الذي خلّفه `--reload`): الخادمُ الحيُّ ينشر **٢٤** لـJO، وبابُ اللوحة
`GET /admin/settings/feature-flags` يعطي ٢٤ للسوقين.

### الضابط — **٢٤ من ٢٤، مقيسةً بالنقر**

فُتحت شاشةُ الإعدادات في متصفحٍ حقيقيّ، ونُقر كلُّ زرٍّ وقُرئ أثرُه من
الخلفية: **٢١ مفتاحاً انقلبت بالنقر وعادت**، و**ثلاثةُ حرّاسٍ**
(`otp_verification_enabled` · `pricing_writes_enabled` ·
`withdrawal_payout_enabled`) فتحت نافذةَ «أطفئ الحارس» وطلبت سبباً مكتوباً،
**ثمّ أطفأت فعلاً حين أُعطي السبب وعادت**. ولا مفتاحَ بلا ضابط.

### الباب — **١٧ من ٢٤ مقيسةً حيّة**

بإطفاء المفتاح ومناداة المسار الحيّ ومقارنة الجواب كلِّه:

| المفتاح | المسار | مُشعَلاً ← مُطفأً |
|---|---|---|
| `country_visible` | `GET /config` | `JO` موجود ← غائب |
| `whatsapp_otp_enabled` | `GET /config` | `["whatsapp_otp","firebase"]` ← `["firebase"]` |
| `otp_verification_enabled` | `POST /auth/register` بلا إثبات | 422 ← **201 حسابٌ أُنشئ** |
| `driver_map_nearby_enabled` | `GET /drivers/me/nearby` | 200 ← 403 |
| `vehicle_skins_enabled` | `GET /vehicle-skins/store` | 200 ← 403 `feature_disabled` |
| `driver_levels_enabled` | `GET /drivers/me/progress` | `enabled: true ← false` |
| `driver_advances_enabled` | `GET /drivers/me/advances` | `offered: true ← false` |
| `subscription_offers_enabled` | `GET /public/landing` | عرضٌ ← `null` |
| `promo_codes_enabled` | `POST /rides/promo/validate` | 404 ← 403 |
| `cliq_enabled` | `POST /wallet/me/topups/cliq` | 409 ← 403 |
| `card_enabled` | `POST /wallet/me/topups/card` | 409 ← 403 |
| `wallet_enabled` | `POST /wallet/me/topups/cliq` | 409 ← 403 `المحفظة غير مفعّلة` |
| `wallet_transfer_enabled` | `POST /wallet/me/transfers` | 409 ← 403 |
| `driver_referrals_enabled` | `GET /me/referrals` (كبتن) | `programs[1].enabled: true ← false` |
| `rider_referrals_enabled` | `GET /me/referrals` (راكب) | `programs[0].enabled: true ← false` |
| `scheduled_rides_enabled` | `POST /me/bookings` | 422 ← 403 |
| `pricing_writes_enabled` | `PATCH /admin/settings/pricing/{id}` | 200 ← 403 |

**وسبعةٌ — «لم تُقَس»، لا «بلا باب»** (تصحيحُ المالك 2026-08-25). والفرقُ
ليس لفظاً: «بلا باب» حكمٌ، و«لم يُقَس» حال. ولكلٍّ ما يلزمه:

| المفتاح | ما يلزم لقياسه |
|---|---|
| `multi_stop_enabled` | **رحلةٌ حيّة** — طلبٌ بمحطّات |
| `women_service_enabled` | **رحلةٌ حيّة** تمرّ بالتوزيع |
| `next_instruction_enabled` | **رحلةٌ حيّة** جاريةٌ بخطِّ مسار |
| `ride_sharing_enabled` | **رحلةٌ حيّة** قابلةٌ للمشاركة |
| `tips_enabled` | **رحلةٌ حيّة** مكتملةٌ ومدفوعة |
| `referred_reward_enabled` | **سلسلةُ إحالةٍ تكتمل** — مُحالٌ يسجّل ويستحقّ |
| `withdrawal_payout_enabled` | **طلبُ سحبٍ `approved`** يُصرف |

> **والرقمُ ١٧ لا يعني أن السبعةَ بلا أبواب.** وهذا مقيسٌ في اليوم نفسِه لا
> محتاط: `wallet_enabled` أعطى «لا فرق» على `POST /wallet/me/transfers`
> **وهو كاذب** — لأن `wallet_transfer_enabled` مطفأٌ فيرفض قبله بالرمز نفسِه؛
> ثمّ ظهر بابُه حالاً من مسارٍ آخر. **فالقياسُ الواحدُ السالبُ ليس نفياً**،
> ومن قرأ «١٧ من ٢٤» حكماً على السبعة فقد قرأ ما لم يُقَس.

**وحالُ الحال بعد القياس: لا انحراف** — كلُّ مفتاحٍ أُعيد، والحسابُ الذي أنشأه
قياسُ `otp_verification_enabled` حُذف.

### وثلاثةُ بنودٍ من هذا القياس — 2026-08-25

1. **أزرارُ المفاتيح في اللوحة `<button>` عارية** — بلا `role="switch"` وبلا
   `aria-checked`. الحالُ مرسومٌ **باللون وحدَه** (`bg-ok` / `bg-line`)، فقارئُ
   الشاشة لا يعرف أمفتوحٌ هو أم مغلق، وأداةُ قياسٍ لا تجد الحالَ إلا بالنقر
   ومراقبةِ الخلفية — وهو ما اضطُرّ إليه هذا القياس.
2. **`wallet_enabled` يستره `wallet_transfer_enabled`** على
   `POST /wallet/me/transfers`: الثاني مطفأٌ في الحال القائمة فيرفض أولاً
   **بالرمز نفسِه** (`feature_disabled`)، فيقرأ القائسُ «لا باب» للأول وهو
   كاذب. وهي «عطبان يستر أحدهما الآخر» في ثوب مفاتيح.
3. **وسؤالٌ مفتوحٌ لم يُقَس اليوم بقرار**: **كم زوجاً آخرَ من المفاتيح يشترك
   في مسارٍ واحد؟** فما وقع مع المحفظة ليس خاصّةَ المحفظة — وأيُّ مسارٍ يمرّ
   بفحصَي مفتاحٍ يحمل الاحتمالَ نفسَه.

**وقاعدةُ المسح النصّيّ صارت قاعدةً لا بنداً** — موضعُها `PATTERNS.md`
(«اسمُ مفتاحٍ يُبحث عنه نصّاً لا يجد نداءً بمفتاحٍ متغيّر»)، وقد قِيس أنها
تكذب على **ستّةِ مفاتيحَ من ٢٤** في هذا المشروع.

<!--/جديد-->
<!--جديد-->

## بنيةُ النشر — ما قِيس وما ينتظر قراراً (2026-08-25)

### ١ — الشكلُ العاشر قائمٌ على الإنتاج الآن (2026-08-25)

**الخادمُ ينشر ٢٢ مفتاحاً والشجرةُ ٢٤.** مقيسٌ حيّاً:
`https://stg-api.tajora.ly/api/v1/config` يعطي **٢٢** لـJO، والشجرةُ وجهازُ
التطوير يعطيان **٢٤**.

**وهو حزمةٌ مخدومةٌ أقدمُ من مصدرها** — الشكلُ العاشر بحرفه. **ويُحلّ بالنشر
لا بإصلاح**: لا عطبَ في الكود، والفرقُ هو ما لم يُرفع بعد.

### ٢ — النطاقاتُ والأنفاقُ والحزمُ المنشورة — مقيسةً من الشبكة (2026-08-25)

**والتسميةُ مقلوبة**: الاسمُ العاري يشير إلى جهاز المطوّر، والبادئةُ `stg-`
إلى الإنتاج.

| النطاق | يخدمه | الدليلُ المقيس |
|---|---|---|
| `api.tajora.ly` | **جهازُ المطوّر** | `environment: development`، وبصمةُ `/config` **مطابقةٌ حرفياً** لـ`localhost:8001` |
| `app` · `driver` · `admin` | **جهازُ المطوّر** — Vite dev | الصفحةُ تطلب `/src/main.tsx` |
| `stg-api` | **الخادم** | `environment: production`، وينشر ٢٢ مفتاحاً |
| `stg-app` · `stg-driver` · `stg-admin` | **الخادم** — dist مبنيّ | تطلب `/assets/index-<hash>.js` |
| `taxo.tajora.ly` | **الخادم** — صفحةُ التنزيل | 200، و`manifest.json` يجيب |
| `dev-*` | **لا وجودَ لها** | لا سجلَّ DNS |

**ونفقان لا واحد، وكلاهما مُعرَّفٌ في `cloudflared/`**: نفقُ التطوير
(`config.docker.yml`) **يعمل حاويةً على جهاز المطوّر** ويوجّه الأربعةَ العارية
إلى `localhost` 8001/5176/5174/5175؛ ونفقُ الإنتاج (`config.prod.yml`) على
الخادم يوجّه `stg-*` و`taxo` إلى خدمات compose. **فقلبُ الأسماء يمسّ ملفَّي
التوجيه معاً وسجلّاتِ DNS في Cloudflare** — ولا يكفي أحدُهما.

**والحزمُ المنشورةُ الآن على `taxo.tajora.ly/downloads` تشير إلى جهاز
المطوّر** — قُرئ من **داخل** الحزمتين لا من الشجرة:

| الحزمة | `appId` | `server.url` داخلها | العنوانُ المخبوز في أصولها |
|---|---|---|---|
| `taxo-rider.apk` | `ly.tajora.rider` | `https://app.tajora.ly` | `https://api.tajora.ly` |
| `taxo-driver.apk` | `ly.tajora.driver` | `https://driver.tajora.ly` | `https://api.tajora.ly` |

وبصمتاهما تطابقان `manifest.json` (وسم `v0.1.4`، إيداع `de61235`).

**وما لم يُقَس**: ما هو **مثبَّتٌ فعلاً على هاتفَي المالك** — لا جهازَ موصولٌ
بـ`adb`، والقياسُ دقيقتان متى وُصل.

### ٣ — مفتاحُ توقيع النشر — بندٌ لم يُنفَّذ، ولا نشرَ عامٌّ قبله

**الحالُ اليوم**: الحزمُ **بتوقيع تصحيح** (`assembleDebug`)، ومفتاحُ الإصدار
لم يُنشأ. **وأثرُه أن أوّلَ حزمةٍ بمفتاح إصدارٍ لا تُحدِّث المثبَّت** — يُنزع
ويُثبَّت من جديد، فتضيع الجلسةُ والتخزين.

**وخطرُه الأكبرُ بعد النشر**: مفتاحٌ يضيع يعني أن **التطبيق العامَّ لا يُحدَّث
أبداً** — لا إصلاحَ أمنيّ، ولا تغييرَ عنوان. والوحيدُ المخرج نشرُ حزمةٍ
بمعرِّفٍ جديد، أي فقدُ كلِّ من ثبّت القديمة.

**وهو ملفٌّ ثنائيٌّ لا نصّ** (`.jks`)، **فلا يدخل git ولا يمسكه مسحُ نصّ**.
موضعُه الصحيح: **سرٌّ في GitHub مُرمَّزاً بـbase64** يفكّه CI إلى ملفٍّ مؤقّتٍ
في مجرى العمل، **ونسختان خارج الجهاز** (مدير كلمات مرور، ووسيطٌ بارد).
وكلماتُ مروره أسرارٌ منفصلةٌ عنه.

**ولا يُنشئه الوكيل** (قرارُ المالك 2026-08-25): إنشاؤه يعني وجودَ السرّ في
جلسةٍ تنتهي.

### ٤ — جدولُ الأسرار للنسخ الأربع وللنشر

| السرّ | ما هو | مَن يُنشئه | موضعُه الصحيح | إن ضاع |
|---|---|---|---|---|
| `taxo-release.jks` | مفتاحُ توقيع أندرويد (**ثنائيّ**) | المالك بـ`keytool` | سرُّ GitHub بـbase64 + نسختان خارج الجهاز | **التطبيقُ العامُّ لا يُحدَّث أبداً** |
| `ANDROID_KEYSTORE_PASSWORD` · `ANDROID_KEY_PASSWORD` · `ANDROID_KEY_ALIAS` | كلماتُ مرور المفتاح واسمُه | المالك عند الإنشاء | أسرارُ GitHub | المفتاحُ سليمٌ ولا يُستعمل — يُعاد ضبطُه بها وحدَها إن حُفظت |
| بيانُ اعتماد نفق الإنتاج | ملفُّ `<tunnel-id>.json` | Cloudflare | **على الخادم في `/home/taxo/secrets`** — وفي النسخة الاحتياطية | **نفقٌ لا يُعاد بناؤه** بلا وصولٍ إلى الحساب |
| بيانُ اعتماد نفق التطوير | `~/.cloudflared/<id>.json` | Cloudflare | **جهازُ المطوّر وحدَه** | يُنشأ نفقٌ جديدٌ ويُعاد توجيه DNS |
| `google-services.json` ×4 | معرِّفاتُ Firebase + مفتاحُ عميلٍ مقيَّد | المالك من وحدة تحكّم Firebase | **يُتعقَّب في git** (انظر الحكم أدناه) | يُعاد تنزيلُه من الحساب |
| `CREDENTIALS_ENCRYPTION_KEY` (Fernet) | يفكّ `provider_credentials` | قائمٌ | `.env` على الخادم + النسخة الاحتياطية | **لا تُفكّ عقودُ المزوّدين** |
| `POSTGRES_PASSWORD` · `JWT_SECRET` · `WA_GATEWAY_KEY` | أسرارُ بنية | قائمة | `.env` على الخادم + النسخة | فقدُ القاعدة/الجلسات/البوّابة |
| رموزُ Mapbox و Telr و…‏ | عقودُ مزوّدين | المالك | **`provider_credentials` مشفَّراً** لا ملفّاً | تُعاد من حسابات المزوّدين |

**وما يبقى في `.env.local` على جهاز المطوّر وحدَه**: أسرارُ البنية المحلّية
(قاعدةٌ وRedis وJWT وFernet المحلّيّة) ورموزُ البذر — **ولا شيءَ من مادّة
التوقيع ولا من أسرار الإنتاج**.

**وحكمُ `google-services.json` — مقيسٌ لا مُفترَض**: فُحص محتواه فعلياً، فليس
فيه إلا `project_id` و`project_number` و`storage_bucket` و`mobilesdk_app_id`
واسمُ الحزمة و**مفتاحُ عميلٍ واحد** (`AIza…`, 39 حرفاً)، و`oauth_client`
**فارغة**. **ولا سرَّ فيه**: المفتاحُ نفسُه **موجودٌ داخل الحزمة المنشورة علناً
الآن** — قِيس بالبحث عنه في `taxo-rider.apk` المنزَّلة من الصفحة. **فيُتعقَّب
في git**، بشرطِ تقييده في وحدة تحكّم Google باسم الحزمة وبصمة التوقيع.

### ٥ — مسحُ الأسرار قبل الدفع **لا يمسك مادّةَ التوقيع** (مقيسٌ 2026-08-25)

النمطُ المستعمَلُ يدوياً قبل كلِّ دفعٍ جُرِّب على خمسة ملفّاتٍ صوريّة:

| الملفّ | الحكم |
|---|---|
| `release-key.pem` (بادئةُ مفتاحٍ خاصٍّ بصيغة PEM) | ✓ يمسك |
| `keystore.properties` (`storePassword=…`) | **✗ يفوت** |
| `taxo-release.jks` (ثنائيّ) | **✗ يفوت** |
| `.env` بأسماءٍ كبيرة (`TAXO_KEYSTORE_PASSWORD=…`) | **✗ يفوت** |

**والعلّةُ أن النمطَ يشترط علامةَ اقتباسٍ بعد `=`**، وملفّاتُ gradle وproperties
و`.env` تكتب القيمةَ عاريةً. **فهو لا يحرس ما سيُتعامل معه هذا الأسبوع.**

**ونمطٌ مصحَّحٌ قِيس في الاتجاهين** (ولم يُثبَّت بعد): يمسك الثلاثةَ الفائتة
ومعها الـPEM، **ويصمت** على `build.gradle` يقرأ من البيئة وعلى `.env` بلا
سرّ. **والملفُّ الثنائيُّ لا يمسكه نمطُ نصٍّ إطلاقاً** — يُمنع بالامتداد لا
بالمحتوى.
<!--/جديد-->
<!--جديد-->

## خُضرةُ CI على الواجهتين لا تقول شيئاً عن بناءٍ بشكل الإنتاج (2026-08-25)

**بندٌ لا شغل — ولا يُرقَّع CI.**

مصفوفةُ `.github/workflows/ci.yml` تبني `customer-app` و`driver-app` على
`VITE_API_BASE_URL=https://api.tajora.ly`، و`admin-panel` وحدَه على
`https://stg-api.tajora.ly`.

**وقِيس أن `api.tajora.ly` نفقُ جهاز المطوّر لا الخادم** (2026-08-25): يجيب
`environment: development`، وبصمةُ `/config` منه **مطابقةٌ حرفياً** لجواب
`localhost:8001`.

**فخُضرةُ العملين تقول «بُنيا على النفق ونجحا»، وتُقرأ «بُنيا كما يُبنى
الإنتاج»** — والفرقُ ليس لفظاً: `check:target` و`check:dist` يقيسان الحزمةَ
**مقابل الهدف المُعلَن**، فهدفٌ مختلفٌ يعني حراسةً لشيءٍ آخر.

**وهو الشكلُ الخامسَ عشر**: *حارسٌ صادقٌ تُوسَّع دعواه فوق نطاقه*
(`PATTERNS.md`) — صادقٌ في نطاقه، ونطاقُه أضيقُ ممّا يُقرأ منه.

**وقِيس أثرُه العمليُّ اليوم**: الحزمُ المخدومةُ على الإنتاج تحمل
`https://stg-api.tajora.ly` في الثلاثة — قُرئ من الحزمة المخدومة نفسِها. فلو
أُخذ هدفُ البناء من مصفوفة CI لصار **إنتاجُ الناس يخاطب حاسوباً في بيت**.
ولذلك **صُرِّح الهدفُ في البوّابة الرابعة** (`TAXO_FRONT_API_BASE`) ولم يُؤخذ
منها.

**ويُحلّ بقلب الأسماء لا بترقيع CI** (قرارُ المالك 2026-08-25): يومَ يصير
`api.tajora.ly` الخادمَ و`dev-api` جهازَ المطوّر، تصير مصفوفةُ CI صادقةً بلا
تعديلِ سطرٍ فيها. **وترقيعُها اليومَ يُخفي العلّةَ ويُبقيها.**
<!--/جديد-->
<!--جديد-->

## الرقعُ الأربعُ المحفوظةُ على الخادم — قِيست وحُذفت (2026-08-25)

`~/taxo-aside-*` من رفعات 2026-08-22: اثنتان بـ٤٢ و٤٣ ملفّاً (١٨ م.ب لكلٍّ)،
واثنتان فارغتان.

**قِيست قبل الحذف**: لا اسمَ بلاحقةِ سرّ، **وصفرُ سطرٍ يطابق نمطَ البوّابة
الثانية**؛ و`tracked.patch` (١٢٣١ سطراً مضافاً في ٤٩ ملفّاً، فيها `enums.py`)
قُيس ضدّ **اتحادِ كلِّ نسخةٍ من كلِّ ملفٍّ عبر التاريخ** فكان **صفرَ سطرٍ لا
أثرَ له**.

**ولم تكن الأسطرُ كلَّ ما فيها**: حزمتان ثنائيّتان لا نسخةَ لهما في أيِّ
إصدار — `taxo-rider.apk` **11,573,391** بايت (ضِعفُ كلِّ ما نُشر) و
`taxo-driver.apk` **6,233,118**. **فسُحبتا أوّلاً** إلى
`D:	axo-backupsside-apks-20260822\` ببصمتين مطابقتين، **ثمّ حُذفت
الأربع**.

**والعنوانُ فيهما كالمنشورتين**: `server.url` = `app`/`driver.tajora.ly`،
والأصولُ تحمل `https://api.tajora.ly` — **فتسميةُ النطاقات لم تتغيّر منذ
08-22 على الأقلّ**.

**والدرسُ صار قاعدةً** في `PATTERNS.md`: «القياسُ الصادقُ لا يأذن بفعلٍ خارج
نطاقه».
<!--/جديد-->
<!--جديد-->

## ثلاثةُ بنودٍ من جولة النشر — 2026-08-25

**بنودٌ لا شغل، ولم يُفتح أيٌّ منها.**

### ١ — الحزمتان على S21 هما المنشورتان، وتخاطبان جهازَ المطوّر

قُرئ **من داخل الحزمتين المثبَّتتين على الجهاز** (`adb pull` لـ`base.apk`)، لا
من الشجرة ولا من صفحة التنزيل:

| | `ly.tajora.rider` | `ly.tajora.driver` |
|---|---|---|
| النسخة | `1.0` · code **288** | `1.1` · code **288** |
| `server.url` | `https://app.tajora.ly` | `https://driver.tajora.ly` |
| عناوينُ الأصول | `api.tajora.ly` · `taxo.tajora.ly` | مثلُها |
| البصمة | `8255abec…` **= المنشورة ✓** | `13ca2092…` **= المنشورة ✓** |

**فما على الهاتف هو المنشورُ بعينه** (`v0.1.4` · `de61235`)، **وثلاثةُ
النطاقات التي يخاطبها اليومَ هي جهازُ المطوّر**. ⇒ **قلبُ الأسماء ينقل هاتين
الحزمتين إلى الخادم بلا إعادة تثبيت** — مقيسٌ من داخل الجهاز لا مُرجَّح.

### ٢ — البوّابةُ الرابعةُ كانت تبتلع مخرَجَ البناء

أوّلُ تشغيلٍ لخطوة البناء سقط فقال `FAIL` للثلاثة **بلا سببٍ واحد**، لأن الأمرَ
كان `>/dev/null 2>&1`. **فاضطُرّ القياسُ إلى إعادة تشغيلٍ يدويٍّ على الخادم**
ليعرف أن السببَ `Cannot find module '/tools/check-money-math.mjs'`.

**وبابٌ يسقط بلا أثرٍ يُقرأ ليس باباً** — وهو الدرسُ المكتوبُ في CI نفسِه
(«الأثرُ يصل كاملاً») ولم يكن مطبَّقاً هنا. **أُصلح في اليوم نفسِه**: المخرَجُ
يُحفظ لكلِّ تطبيق ويُشحن ذيلُه عند السقوط.

### ٣ — رقعةٌ جديدةٌ محفوظةٌ على الخادم

`~/taxo-aside-20260825T065414Z` — `moved=0 patch=0`. **لم تُفتح ولم تُحذف.**
<!--/جديد-->
<!--جديد-->

## ثلاثةُ بنودٍ من جولة النشر الثانية — 2026-08-25

**لم يُفتح أيٌّ منها.**

1. **`check:client-doors` لا يفرّق بين «لا قارئ» و«لا أداة»**: يقيس الاستعمالَ
   بـ`git grep`، وشرطُه `catch { return false }` — **فغيابُ `git` وغيابُ
   القارئ جوابٌ واحد**. وقِيس أثرُه: في حاوية `node:22-alpine` بلا git أعلن
   **٥٨ باباً بلا زرّ** في تطبيقين، **والشجرةُ سليمةٌ والحارسُ أخضرُ على جهاز
   المطوّر** (٦١ مساراً كلُّها موصولة). وهو مقلوبُ «غيابُ أداةِ القياس يوقف
   ولا يُقرأ سلامة»: هنا **يوقف بدعوى كاذبة**، وكلاهما أن الحارسَ لا يعرف أنه
   لم يقِس. (أُغلق أثرُه في البوّابة بتثبيت `git`، **والحارسُ نفسُه لم يُمسّ**.)

2. **`dist` الراكب والكبتن فيه ملفّا `index-*.js` لا واحد** — بقيّةُ بناءٍ
   سابقٍ لم تُكنس. **والمخدومُ صحيحٌ مقيس**: `index.html` يشير إلى بناء اليوم،
   والمتصفّحُ حمّله. لكن **قراءةَ القرص بـ`ls | head -1` تعطي الملفَّ الخطأ** —
   وقد أوقعت هذا القياسَ في بلاغٍ كاذبٍ قبل أن يُصحَّح: **يُقرأ ما يشير إليه
   `index.html`، لا أوّلُ ما يسرده `ls`.**

3. **رقعةٌ محفوظةٌ جديدة**: `~/taxo-aside-20260825T080201Z` (`moved=0
   patch=0`). لم تُفتح ولم تُحذف.
<!--/جديد-->
<!--جديد-->

## بندان من قلب النطاقات — 2026-08-26

### ١ — شاشةُ «الشبكة ضعيفة» تكذب على من يقرؤها

`lib/splash.ts` يعرض حالين: **«لا يوجد اتصال»** حين `navigator.onLine` كاذب،
و**«الشبكة ضعيفة — جارٍ المحاولة»** فيما عدا ذلك. والتمييزُ بينهما مقصودٌ
ومكتوبٌ بعلّته (§7.8): أحدُهما يقول «افتح الشبكة» والآخرُ «لا تفعل شيئاً».

**لكنّ الثانيةَ تُعرض على كلِّ فشلٍ في `GET /config` مهما كان سببُه** — وقِيس
اليومَ ثلاث مرّات: **رفضُ CORS** (أصلٌ غيرُ مسموحٍ به) على `stg-app` ثمّ على
`dev-app`، وقبلهما نداءٌ إلى `127.0.0.1` من هاتف. **وشبكةُ القارئ سليمةٌ
تماماً في الثلاثة.**

**فالجملةُ تسمّي سبباً لا تعرفه** — وتوجّه من يقرؤها إلى الاتّجاه الخطأ: يبدّل
الواي-فاي ويعيد الإقلاع، والعلّةُ في خادمٍ أو ترويسة. **وهي «رسالةٌ تصف ما لم
يُقَس»** — أخفُّ من صمتٍ، وأثقلُ من «تعذّر الوصول إلى الخدمة».

**ولا تُصلَح اليوم بقرار** (قرارُ المالك 2026-08-26). **وحدُّ البند**: لا يُقاس
هنا كم مرّةً ظهرت لمستخدمٍ حقيقيّ — الثلاثةُ المقيسةُ كلُّها من قياسٍ متعمَّد.

### ٢ — حاجزُ الرخصة أمام متجر السيارات: **رُفع** (2026-08-26)

**أقرّ المالكُ في 2026-08-26** أن عقده مع Canva يجيز **الاستعمالَ التجاريَّ
وإعادةَ التوزيع داخل منتجٍ يُباع**. وكان هذا **شرطَ إطلاقِ ميزةِ المتجر**
وحدَها (§28.10) لا شرطَ إطلاق التطبيق.

**والإقرارُ موثَّقٌ في `LICENSE` بجذر المستودع** بتاريخه، **ومنسوبٌ إلى المالك
لا إلى قراءةِ أحد** — فالعقدُ لم يُقرأ في هذه الجلسة، والملفُّ يقول ذلك صراحةً.

**وما يزال موقوفاً بأمر المالك، ويُوقظ بترتيبه**: الاستخراج · الانتقاء ·
الصفوف · المتجر. **ورفعُ حاجزِ الرخصة لا يوقظ منها شيئاً.**
<!--/جديد-->
<!--جديد-->

## قرارٌ: Firebase تخرج من كلِّ مسار حساب — بندٌ لا شغل (2026-08-26)

**قرارُ المالك 2026-08-26**: Firebase **لا تمسّ حساباً بعد اليوم** — لا
التسجيلَ ولا إنشاءَ الحسابات الجديدة ولا الدخولَ ولا تأكيدَ الرقم ولا استعادةَ
كلمة المرور. **ويبقى لها FCM للإشعارات وحدَها.** **ولا ترقيةَ إلى Blaze.**

### العلّةُ مقيسةٌ لا مقدَّرة

الهاتفُ فشل في التطبيقين معاً بـ`Firebase: Error (auth/billing-not-enabled)`.
**وثلاثةٌ قِيست يومَها:**

1. **النداءُ لا يمرّ بخلفيتنا أصلاً**: `signInWithPhoneNumber` يعمل **في
   متصفّح الهاتف** (`lib/firebase.ts`)، فيذهب من الجهاز إلى Google مباشرةً.
   **وصفرُ نداءٍ** إلى `auth/challenge` أو `auth/method` أو `auth/verify` بلغ
   الخادمَ في عشرين دقيقة — وكلُّ ما وصله ثلاثةُ `GET /config`.
2. **والخطأُ جوابُ Google لا جوابُنا**: تحقّقُ الهاتف يشترط خطّة **Blaze**،
   والمشروعُ على المجّانية. **فهو حاجزُ فوترةٍ لا عطبُ كود.**
3. **ولم يكن بديلاً عن واتساب**: `whatsapp_otp_enabled` كان **مطفأً** لـJO
   على الإنتاج، فلم تدخل القناةُ القائمةَ أصلاً — **لا سقوطَ ولا سترَ**.

**فالنزعُ تعديلٌ في التطبيقات لا في الخادم** — وهذا ما يجعله فعلاً مستقلاً.

### ما سيُمسّ بالضبط — ولم يُمسّ اليوم

| الموضع | ما يقع |
|---|---|
| `*/lib/firebase.ts` | **يُقسم لا يُحذف**: `startPhoneVerification` يخرج، و`requestPushToken`/`onForegroundMessage` **يبقيان** — الملفُّ يجمع الدخولَ والإشعارَ اليوم |
| `*/components/PhoneVerification.tsx` | فرعُ `firebase` يخرج، ويبقى فرعُ الرمز |
| `*/lib/config.tsx` · `api/types.ts` | مرآةُ `firebase` في اتحاد قنوات التحقّق |
| `backend/services/verification.py` | `FIREBASE` يخرج من `available_methods` |
| `backend/services/auth/firebase_identity.py` | مسارُ تبادل رمز Firebase بجلسة |
| `backend/schemas/auth.py` · `routers/config.py` | حقولُ الرمز والنشر |
| `providers/registry.py` · `health.py` | عقدُ `firebase_auth` — **يبقى `fcm` منفصلاً** |

**وثلاثةُ حدودٍ تُقرأ قبل التنفيذ:**

· **FCM يبقى ويعمل على Spark** — الإشعاراتُ مربوطةٌ بمعرّف الحزمة لا بالنطاق
  ولا بالفوترة. **وخلطُه بالنزع يُطفئ الإشعارات وهو ما لم يُطلب.**
· **ولا يُنزع قبل أن يثبت واتساب** (قرارُ المالك): نزعُه أوّلاً يترك JO **بلا
  قناةٍ إطلاقاً** — فلا دخولَ ولا تسجيل.
· **و`services/totp.py` يذكر Firebase ولا علاقةَ له** بمسار الحساب — يُقرأ قبل
  أن يُمسّ.
<!--/جديد-->

<!--جديد-->
## متجرُ المركبات — أيقظت السلسلةُ الخمس (2026-08-27)

**أَذِن المالكُ بإيقاظ الأربع ومعها شاشةُ المشتريات، وبقي الحدُّ اللونيُّ
موقوفاً** — يحتاج قياسَ إطاراتٍ في رحلةٍ حقيقيةٍ بالسيارة، وذاك بيده.

### ١ — الاستخراج: ٤١٨، وخريطةُ الحروف استُرجعت بالقياس

**أُعيد لا لعطبٍ بل لأن المخرَجَ السابق كُتب في مجلَّدٍ مؤقّتٍ فذهب معه** —
ومعه **خريطةُ اللوح إلى حرفه**، فصارت وسومُ `B-40` و`D-40` و٣٦ زوجِ المكرَّر
تشير إلى ما لا يُعرف. **والخريطةُ ليست مكتوبةً في أيِّ ملفّ**، و`SPEC §28.11`
يسجّل أن إسنادَها أخطأ مرّةً («الاسمُ لا يقول اللوحة»).

**فصودق عليها بثلاثةِ شواهدَ مستقلّةٍ مكتوبةٍ من قبل**: التسعُ العلويّةُ أعطت
**٤١٨ بالضبط**؛ واللوحتان المكرَّرتان وقعتا على **B وD** كما ينصّ §28.14؛
والشاذّان **عند الفهرس ٤٠ في كلٍّ منهما** — `B-40` و`D-40` بالحرف، وهما
قصاصتان رماديتان لا مركبتان.

**و«١٢٨ أفقيّة · ٢٩٠ رأسيّة» تصالحت**: المقيسُ ١٣٠ و٢٨٨، والفرقُ اثنان في
اتجاهين متعاكسين وهما القصاصتان — فمن عدّهما مع الرأسيّ خرج بأرقام §28.13.

**والمخرَجُ في `car-stock/`** بجانب `car/`، يرث حكمَها في `.gitignore`، ومعه
`sheets.json` يثبّت الخريطةَ و`extract.py` يعيد إنتاج كلِّ شيء.

### ٢ — الانتقاء: **٤٧ زوجاً لا ٣٧**، والفارقُ مسمّى

اشتُقّ المكرَّرُ بالمعيار الثلاثيِّ في §28.14 (جارٌ أقربُ متبادَل · وفارقٌ عن
الثاني بمرّتين) على البصمة ١٦×١٦ بعد توحيد الاتجاه — **صفرُ إخفاقٍ في شرط حفظ
البكسلات**.

**والحصادُ ٤٧ زوجاً، كلُّها عبرَ لوحتين وصفرٌ داخل لوحة** — والقائمةُ القديمةُ
٣٧. وتوزيعُها: **B↔D تسعةٌ وثلاثون** (وهما لوحتان مكرَّرتان بكاملهما)،
**وF↔G ثمانية**. **وفُحصت الثمانيةُ كلُّها بالعين، وثلاثةٌ من B↔D: كلُّها
مكرَّرٌ حقيقيّ.**

> **وفيها `F-09≡G-11` التي رفضتها الجولةُ السابقة** — وهي بالعين **مكرَّرةٌ
> بحقّ**. فالرفضُ السابقُ كان خطأً، أو كان على وسومٍ تعني غيرَ ما تعنيه اليوم
> (والخريطةُ كانت ضائعة، فالثاني أرجح). **والقائمةُ القديمةُ لا تُنقل.**

**فالفريدُ ٣٦٩** بعد إسقاط أحد كلِّ زوج — **إسقاطٌ وسمٌ لا محو**: لم يُحذف
أصلٌ من `car/` ولا من `car-stock/`.

### ٣ — التمايزُ عند ٣٠ بكسلاً: **الجوابُ يتراوح ٢٤–٣٦٩، وهذا هو الجواب**

قِيس على الفريدة بعد توحيد الاتجاه، باللون الغالب (بلا الزجاج الأسود) والظلِّ
الخارجيِّ ٨×٨ — **والعتبةُ عُويرت بالمكرَّر المؤكَّد** لا اختيرت: أقلُّ عتبةٍ
تدمج كلَّ ما أكّدته العينُ مكرَّراً.

| العتبة | هويّاتٌ متمايزة |
|---|---|
| ثلثُ مسافة المكرَّر الوسطى | ٣٦٩ (لا اندماجَ أصلاً) |
| **مسافةُ المكرَّر الوسطى** | **٣٣٦** · وسيطُ الجيران **صفر**، و٣١٧ من ٣٦٩ بلا جارٍ البتّة |
| قصوى مسافة المكرَّر | **٢٤** |

**وهذا ليس رقماً واحداً يُقتبس، وهو بعينه ما يجب أن يُقال**: مدى «هذان
سيارتان مختلفتان» ومدى «هذان صورتان لسيارةٍ واحدة» **يتداخلان** عند ٣٠ بكسلاً.
فبعتبةٍ ضيّقةٍ تكاد كلُّها تتمايز، وبعتبةٍ تسع كلَّ ما تراه العينُ مكرَّراً
تنهار إلى **٢٤**.

> **وحكمُ §28.15 يقف**: من يبني ندرةً على «مئاتِ مركباتٍ مختلفة» يبني على رقمٍ
> لا وجودَ له على الخريطة. **والتمايزُ يشتريه الحدُّ اللونيُّ لا المادّة** —
> وهو موقوفٌ بأمر المالك حتى تُقاس الإطاراتُ في سيارة. **والمتجرُ لا يتوقّف
> عليه**: عند ١٠٤ بكسل تتمايز المركباتُ بيقين، وهناك تُشترى.
>
> **والرقمُ المكتوبُ سابقاً (٧١) لم يُعَد إنتاجُه** — لأن معاملاتِ قياسه غيرُ
> مكتوبةٍ في المواصفة. **ولا يُقرأ أحدُهما تكذيباً للآخر**: قياسان بمعيارين،
> وكلاهما يقول الشيءَ نفسَه — العشراتُ لا المئات.

### ٤ — الصفوف والمتجر: **٣٦٩ مركبةً مسعَّرة**

| | |
|---|---|
| عادية | ١٨٤ · بلا حدِّ كمية |
| مميّزة | ١١١ · بلا حدّ |
| نادرة | ٥٦ · **٥٠ نسخةً لكلٍّ** |
| أسطورية | ١٨ · **١٠ نسخٍ لكلٍّ** |

**والندرةُ تُشتقّ من خاصّيةٍ مقيسةٍ لا تُوزَّع بالهوى**: «طاقةُ النقش» —
انحرافُ اللون داخل الجسم بعد استبعاد الزجاج — **بالرُّتبة لا بعتبة**. سيارةٌ
بلونٍ صافٍ عاديّة، وذاتُ التمويه واللهب أندر. **وتُقاس عند ١٠٤ بكسل حيث تُرى**
لا عند ٣٠ حيث لا يفرّق النقشُ شيئاً (§28.12).

**والاسمُ يُركَّب ولا يُرقَّم**: عائلةُ اللون الغالب + صفة — «البرتقالية
الأبيّة» — **٣٦٩ اسماً فريداً بلا رقمٍ في شاشة**.

**والنادرةُ والأسطوريةُ `visible_before_accept=false`** كما يقضي §28.3/١.

**والاستيرادُ بابُه `scripts/import_garage.py` ولا يدخل `seed.py`** — بعلّةِ
البذر المكتوبة: مركبةٌ **مسعَّرة** تُبذَر تظهر في الإنتاج بلا أن يقرّرها أحد.
والرسمةُ تمرّ بـ`skin_artwork.ingest` لا بكتابةٍ مباشرة.

**والأسعارُ مقترَحةٌ لا مُقرَّة**: ١٫٥ · ٣ · ٧ · ١٥ د.أ (و٥ · ١٠ · ٢٥ · ٥٠
د.ل) — **كُتبت على قاعدة التطوير وحدَها، وتنتظر إقرارَ المالك قبل أيِّ إنتاج.**

### ٥ — شاشةُ المشتريات، ووحدةُ الرقم

`GET /admin/vehicle-skins/purchases` وشاشةُ «مشتريات المركبات» — **مستقلّةٌ لا
بطاقةٌ في الكتالوج** (قرارُ المالك: «مالٌ يخرج من محافظ الكباتن له شاشتُه»).
تعرض من اشترى ومتى وبكم وأيَّها يقود، ومجاميعَ **على الجدول كلِّه لا على
الصفحة**، والإيرادَ **بعملته** لا مجموعاً.

**ووُحِّد `owners_count`** — البندُ المفتوحُ الوحيدُ في §28.7: كان يُحسب مرّتين
(الخدمةُ للمتجر، والموجّهُ للوحة)، **وهما يتّفقان اليوم** وذلك بعينه الشكلُ
الثامن. فصار `vehicle_skins.aggregates` بيتاً واحداً يقرأ منه البابان.

### ما قِيس بالعين

المتجرُ يفتح بـ٣٧٣ بطاقةً بأسمائها وأسعارها وندراتها · والكراج يعرض المملوكةَ
ويسمّي المفعَّلة ويقول «متبقٍّ ٤٨» · وشاشةُ المشتريات ترسم الجدولَ والمجاميع ·
**وشراءٌ حقيقيٌّ تمّ**: `-1.500` في الدفتر نوعُه `skin_purchase`، والرصيد
`11.483 → 9.983`، وصفُّ مِلكيّةٍ بسعرٍ مجمَّد.

### الأسعارُ أُقرّت — **وشرطُها أنها تُعدَّل لا تُنشر** (قرارُ المالك 2026-08-27)

**وهي كذلك بالبناء**: الأسعارُ صفوفٌ في `vehicle_skin_prices`، لكلِّ سوقٍ حقلٌ
في شاشة «مركبات المتجر» يكتبه `PATCH /admin/vehicle-skins/{id}`، **ولا رقمَ
مخبوزٌ في حزمة**. وسكربتُ الاستيراد يكتب القيمَ الأولى وحدَها.

**والمرجعُ الذي وُزنت به** (المالك): اشتراكُه اليوميُّ ٣ والأسبوعيُّ ١٥،
**فالأسطوريةُ بـ١٥ تساوي أسبوعَ اشتراك**. وأُقرّت لأنها محدودةٌ — **١٨٠ نسخةً
كلُّها** (١٨ مركبةً × ١٠).

> **وشرطُ إقرارها مراقبةٌ لا سكوت**: **إن لم تُبَع أسطوريةٌ واحدةٌ في أوّل شهر
> فالسعرُ لا السلعة.** والقياسُ من شاشة المشتريات: `source='purchase'` على
> `rarity='legendary'`. **وهذا بندٌ مؤقّتٌ بتاريخه** — يُقرأ في أوّل جلسةٍ بعد
> شهرٍ من أوّل بيع، ويُحذف حين يُحكم عليه.

### واثنان من الثلاثة أُصلحا وقِيسا على هاتف (2026-08-27)

**١. ٣٧٣ بطاقةً في صفحةٍ واحدة — كان عطباً وصار صفحات.** `GET
/vehicle-skins/store` صار يأخذ `limit`/`offset` (افتراضُه ٤٨، وسقفُه ١٢٠)
**وينشر `total`** فيعرف التطبيقُ متى يقف بلا صفحةٍ فارغةٍ يكتشف بها النهاية.
والشاشةُ تُراكم الصفحاتِ بمراقبِ قاعٍ (`IntersectionObserver` بهامش ٦٠٠ بكسل)،
والصورةُ `loading="lazy"`.

**والقياسُ على هاتفٍ لا حاسوب** (Pixel 5 — ٣٩٣×٨٥١):

| | قبل | بعد |
|---|---|---|
| بطاقاتٌ عند الفتح | ٣٧٣ | **٤٨** |
| صورٌ تُطلب عند الفتح | ٣٧٣ | **٢٠** |
| حمولةُ JSON | ١٩٩ ك.ب | **٢٥ ك.ب** |

وبعد تمريرتين: ١٤٦ بطاقةً و٨٤ صورةً وثلاثةُ نداءات — **أي أن ما لا يُرى لا
يُحمَّل**. **وأوّلُ رسمٍ ٤٫٩ث على هاتفٍ محاكى** وهو يشمل إقلاعَ التطبيق كلَّه،
**ولم يُقَس على جهازٍ حقيقيّ** — فيبقى شرطاً بشرياً في جولة الهاتف.

**٢. الجدارُ البرتقاليُّ زال.** الترتيبُ كان `rarity, name`، وأسماءُ الكتالوج
تبدأ بعائلة اللون — **فالأبجديّةُ كانت تكدّس لوناً واحداً في صدر الصفحة**.
فصار المفتاحُ الثاني `blake2s(skin_id)`: **يخلط بالبناء ويبقى ثابتاً**، فشرطُ
«الترتيبُ عقدٌ لا ذوق» قائمٌ — قِيس: نداءان يعطيان الترتيبَ نفسَه بالحرف،
**وأوّلُ اثنتي عشرةَ بطاقةً فيها تسعُ عائلاتِ ألوان**.

> **ولمَ لم يُخلط عشوائياً**: ترتيبان مختلفان لنداءين يجعلان «الثالثةَ من
> اليسار» تعني مركبتين — وهو ما يحرسه الشرطُ أصلاً.

### والباقي واحدٌ من الثلاثة

**رسماتُ النادر والأسطوريّ من المادّة العلويّة نفسِها**، ولم يُرفع شكلٌ
مجسّمٌ للمتجر. والزاويةُ واحدةٌ في الخانتين فهو **صحيحٌ بحقّ لا اختصاراً**،
لكنّه ليس ما وصفه §28.3 حين كُتب.

### وثلاثةٌ ناقصةٌ تُقيَّد ولا تُوقِف

1. **المتجرُ يرسم ٣٧٣ بطاقةً في صفحةٍ واحدةٍ بلا ترقيم** — ٣٧٣ صورةً ١٢٨–٥١٢
   بكسل و١٩٩ ك.ب من JSON. **يفتح على الحاسوب ويحتاج قياساً على هاتف**، وموضعُه
   ترقيمُ صفحاتٍ أو تحميلٌ كسول.
2. **الترتيبُ `rarity, name` مع أسماءٍ بعائلة اللون يجعل أوّلَ الصفحة جداراً من
   البرتقاليّ** — العقدُ يقول «الترتيبُ عقدٌ لا ذوق»، فالتغييرُ في الخلفية
   وبقرار.
3. **رسماتُ النادر والأسطوريّ من المادّة نفسِها** (علويّة)، **ولم يُرفع شكلٌ
   مجسّمٌ للمتجر** — و§28.3 يذكر «مجسّمٌ للمتجر وعلويّةٌ للخريطة». والمادّةُ
   كلُّها علويّة، فالزاويةُ واحدةٌ في الخانتين — **وهذا صحيحٌ بحقّ لا اختصاراً**،
   لكنّه ليس ما وصفه البندُ حين كُتب.
<!--/جديد-->

<!--جديد-->
## عطبان على `dev-driver` — والثاني كمينٌ في تسعةَ عشرَ موضعاً (2026-08-27)

### ١ — معاينةُ المركبة قبل الشراء: **عطبان لا واحد**

**الأولُ هو العلّة**: `SkinMapPreview.tsx` **لا يستورد `mapbox-gl.css`** — وكان
**الملفَّ الوحيدَ من خمسةِ مكوّناتِ خرائطَ بلا هذا الاستيراد**. فبلا
`.mapboxgl-marker { position: absolute }` سقطت العلامةُ في التدفّق الطبيعيِّ
**تحت** اللوحة: قِيست عند `y 649` والخريطةُ `y 357–505`، وحاويتُها
`overflow:hidden` فاختفت.

> **وما جعله يبدو عطبَ صورة**: الخريطةُ **تُرسم** (لوحةُ WebGL لا تحتاج CSS)،
> **والصورةُ تصل `200`** بمقاس `128×128` من البابِ نفسِه. فكلُّ ما يُسأل عنه
> عادةً كان سليماً — **والعطبُ في `position`**.

**والثاني وجدتُه وأنا أقيس الأول، وأُثبت بالتجربة لا بالدعوى**: الدورانُ كان
يُكتب على **العنصر الذي تملكه mapbox**. وترتيبُ CSS `translate → rotate →
scale → transform` يعني أن `transform` يُطبَّق أوّلاً **ثم يُدار ناتجُه** —
فدورانُ الرأس يُدير **إزاحةَ mapbox نفسَها**.

| الحال | مركزُ العلامة | مركزُ اللوحة |
|---|---|---|
| الدورانُ على الابن الداخليّ | `197,431` | `197,431` |
| الدورانُ على القشرة | `118,525` | **١٢٣ بكسلاً بعيداً** |

**وهذا الثاني يمسّ الخرائطَ الحيّةَ لا المعاينةَ وحدَها**: خمسةُ مواضعَ في
تطبيق الكبتن وموضعان في تطبيق الراكب — **سيارةُ الكبتن نفسِه وزملاؤه حوله
يُزاحون كلَّما اختلف الرأسُ عن صفر**. وقد كُتب في `ARCHITECTURE.md` أن
«العنصرَ الذي تُسلِّمه لعلامةٍ يملكه mapbox، فالتنسيقُ على ابنٍ داخليّ» —
**والقاعدةُ كانت مكتوبةً ومطبَّقةً على `className` وحدَه**.

**وفخٌّ ثالثٌ في الإصلاح نفسِه**: أوّلُ غلافٍ داخليٍّ كان `display:block` بلا
عرض، فامتدّ إلى عرض الخريطة (٣٥٥ بكسلاً) — و`translate(-50%)` من مقاس العنصر
جعل النصفَ ١٧٧ بكسلاً بدل ١٧، **فقُذفت العلامةُ من جديد**. `max-content` هو
ما ثبّتها.

### ٢ — الاشتراك: **الحارسُ صادق، والمسارُ لم يُعلن**

`subscriptions.buy_with_wallet` كان ينادي `wallet.record` **بلا `owner_type`**،
فحاملُ الدورين يرتدّ بـ`wallet_owner_undecided` — **وهو محقّ**: البابُ لم يقل
من أيِّ محفظةٍ يُخصم.

**والتوقيتُ مقيسٌ من التاريخ**: `wallet.record` وُلد **2026-08-10**، ونموذجُ
الأدوار صار مجموعةً **2026-08-19** ومعه هذا الحارس. **فهو مسارٌ قديمٌ لم يمرّ
به حسابٌ مزدوجٌ قطُّ** — لا شيءَ تغيّر فيه، بل صار في القاعدة حسابٌ يحمل
الدورين (`+962790000021`، وهو الوحيد).

**وأُعلن بسياق الفعل**: `owner_type=DRIVER` — اشتراكُ الكبتن من محفظة الكبتن
مهما حمل الحسابُ من أدوار.

**والدليلُ على أنها المحفظةُ الصحيحة هو أيُّ رصيدٍ اشتكى منه**: بعد الإصلاح
ارتدّ الشراءُ بـ`insufficient_balance` **ومحفظةُ الراكب فيها ٦٫٢٢٣ تكفي
الـ١٫٢٠٠** — فلو أخذ منها لَمرّ. والدفترُ كلُّه: **٢١ قيدَ `subscription_payment`
جميعُها على `owner_type='driver'`، وصفرٌ على الراكب.**

### ⚠ وثمانيةَ عشرَ مساراً آخرَ بلا إعلان — تنتظر أوّلَ حسابٍ مزدوج

**عُدّت**: `wallet.record` يُنادى في **٢١ موضعاً، اثنان فقط يُعلنان**
(`topups.py` و`vehicle_skins.py`). والباقي — **١٩ قبل الإصلاح، ١٨ بعده**:

`admin_wallets` · `advances` (٣) · `cancellation` (٣) · `card_payments` ·
`cliq_topups` · `payments` (٥) · `referrals` · `tips` (٢) · `withdrawals`.

> **وواحدةٌ منها وقعت حيّةً في القياس**: تسويةُ اللوحة الإدارية
> (`admin_wallets.py:159`) ارتدّت بنفس الخطأ على نفس الحساب. **فهي ليست
> نظريّة.**
>
> **ولم تُصلَح بقرار**: كلٌّ منها يحتاج **سياقَ فعلٍ يُقرَّر لا يُخمَّن** —
> وتسويةُ المشرف خاصّةً: أيَّ محفظةٍ يعدّل؟ **ذلك حقلٌ في شاشة، لا استنتاج.**
> فتُعرض على المالك ككنسةٍ واحدة.

### ٣ — أسعارُ شاشة الاشتراك: **بذرةٌ وعرضٌ معاً، ولا واحدةَ منها المُقرّة**

| | |
|---|---|
| الأساسُ في قاعدة التطوير | `1.500 · 9.000 · 30.000` |
| «عرض الافتتاح» فعّالٌ لكلِّ الكباتن | **٢٠٪** |
| **فالمعروض** | `1.200 · 7.200 · 24.000` — ٨٠٪ منها بالحرف |
| **والمُقرُّ من المالك للأردن** | `3 · 15 · 45` — **ليس في القاعدة أصلاً** |

**فالجوابُ «كلاهما»**: الأساسُ بذرةُ تطويرٍ تخالف ما أقرَّه، **وفوقه عرضُ
افتتاحٍ ٢٠٪**. وثلاثةُ عروضٍ أخرى فعّالةٌ في القاعدة (٢٥٪ للكباتن الجدد،
و١٠٠٪ «شهرك الأول علينا»). **ولم يُصلَح شيء** — قِيس ولم يُمسّ.
<!--/جديد-->

<!--جديد-->
## كنسةُ إعلان المحفظة — ١٩ من ٢١، والباقيان بعلّتهما (2026-08-28)

**سياقُ الفعل يقرّر، ولا يُخمَّن** (قرارُ المالك، وهو `SPEC §22` بحرفه).
فأُعلن **ستةَ عشرَ موضعاً** وبقي اثنان **لا يقرّرهما السياق**.

### ما أُعلن — وأربعةَ عشرَ منها سياقُها قاطع

| الموضع | المحفظة | من أين قُرئ السياق |
|---|---|---|
| `withdrawals` | الكبتن | الراكبُ لا يسحب أصلاً (SPEC §7) |
| `advances` ×٣ | الكبتن | السلفةُ قرضٌ لكبتن، والسدادُ يعود من حيث خرجت |
| `payments` دفعُ الرحلة · الردّ | الراكب | `owner=rider`، والردُّ يعود من حيث دُفع |
| `payments` الأجر · العمولة · عكسُ الأجر | الكبتن | `owner=driver_user` |
| `tips` ×٢ | الراكب ثمّ الكبتن | قيدان لطرفين، كلٌّ في محفظته |
| `cancellation` التعويض ×٢ | الكبتن | `beneficiary_driver_id` عمودُ كبتنٍ يُقرأ عبر `Driver` |

### وثلاثةٌ محفظتُها **متغيّرة** — والصفُّ يختمها لا الدور

1. **رسمُ الإلغاء** (`cancellation`): المدينُ **يتبدّل**. بعد تسليمٍ نقديٍّ
   يصير المطلوبُ من **الحامل** (كبتن)، وقبله من الراكب — وهو ما يقرأه
   `_debtor_user` من `carrier_driver_id`. **فالمحفظةُ تُشتقّ من الختم نفسِه**،
   فلا تفترق قراءتان لصفٍّ واحد.
2. **مكافأةُ الإحالة**: البرنامجُ مختومٌ على الصفّ (`referral_type`) — إحالةُ
   كبتنٍ تُكافَأ في محفظة الكبتن وإحالةُ راكبٍ في محفظة الراكب. **ولا يُشتقّ
   من أدوار المُحيل**: حاملُ الدورين يُحيل في البرنامجين.
3. **شحنُ البطاقة**: `opened_from_app` كُتب لحظةَ فتح الشحن — **سياقُ الفعل
   مجمَّداً**. والصفوفُ الأقدمُ التي سبقت العمودَ تُترك **بلا إعلان**: لا ختمَ
   فيها يُقرأ، **والتخمينُ يكتب مالاً في غير موضعه**.

### وواحدٌ بُني حقلاً في الشاشة — تسويةُ المشرف

**لا سياقَ يقرّرها**: لا رحلةَ ولا تطبيقَ فتحه ولا ختمَ على صفّ. **فهي قرارٌ
ماليٌّ يكتبه المشرفُ بيده** (قرارُ المالك). `AdjustmentCreate.wallet` حقلٌ
اختياريّ، **ويُسأل عنه في «مكتب المحافظ» فقط لحاملِ الدورين** — وصاحبُ دورٍ
واحدٍ لا محفظةَ ثانيةَ له فالسؤالُ احتكاكٌ بلا قرار. والزرُّ **معطَّلٌ حتى
يُختار**.

> **ولزمه نشرُ الأدوار في مرآة اللوحة**: `UserOut.roles` منشورةٌ منذ نموذج
> الأدوار، **واللوحةُ لم تكن تعكسها** — و`role` وحدَه يقول دوراً واحداً حتى
> لمن يحمل اثنين.

### ~~وواحدٌ يُسمّى ولا يُبنى — **شحنُ كليك**~~ — **بُني 2026-08-28**

`cliq_topups` **لا يختم `opened_from_app` أصلاً** حين يفتح الطلب، ونقطةُ
`POST /wallet/me/topups/cliq` **لا تقبل `?wallet`** — بينما البطاقةُ تفعل
الاثنين. **فالسياقُ غيرُ مسجَّلٍ لا مجهولُ القراءة**، وإعلانُه يحتاج:
ختمَ التطبيق عند الفتح · ومَعْلَماً في نقطة النهاية · وإرسالَه من التطبيقين.

**وأثرُه اليومَ**: حاملُ الدورين **لا يستطيع فتحَ شحن كليك أصلاً** —
`start_topup` يرتدّ قبل أن يصل الدفتر. **بندٌ ينتظر قرارَ المالك.**

### المقيسُ في الاتجاهين

| | |
|---|---|
| تسويةٌ لحسابٍ مزدوجٍ بلا إعلان | `409 wallet_owner_undecided` |
| معلَنةً «كبتن» | محفظتُه `0.000 → 5.000` |
| معلَنةً «راكب» | محفظتُه `6.223 → 7.223` — **مستقلّةٌ تماماً** |
| حسابُ كبتنٍ وحدَه يُعلَن له «راكب» | `403` «لا محفظة لهذا الحساب من هذا النوع» |
| **الحسابُ المزدوجُ يشتري اشتراكاً** | كبتن `5.000 → 3.800` (−١٫٢٠٠)، **والراكبُ `7.223` لم يتحرّك** |

**و١٥٥ اختبارَ مالٍ خضراء** (المحفظة · التزامنُ · الدفعات · الإكرامية ·
السلَف · رسمُ الإلغاء · الإحالات · الاشتراكات).

### وأسعارُ الإنتاج — **لا تُقرأ بلا اعتمادٍ يملكه المالك**

`GET /config` على `api.tajora.ly` يردّ `200` **ولا يحمل أسعارَ الباقات** —
مفاتيحُه `app · auth · countries · providers · validation`. وقراءةُ الأسعار
تمرّ بـ`GET /subscriptions/plans` **وهي خلف جلسةِ كبتنٍ أو مشرف**.

**والمقروءُ فعلاً**: `subscription_offers_enabled = true` **على الإنتاج** —
أي أن العروضَ مشتعلةٌ هناك، **فالمعروضُ للكبتن ليس سعرَ الباقة الخام**.
**والأرقامُ نفسُها لم تُقرأ**، ولا تُقرأ إلا باعتمادٍ لا أملكه.
<!--/جديد-->

<!--جديد-->
## شحنُ كليك يختم كما تختم البطاقة — والبابان صارا واحداً (2026-08-28)

**الحجّةُ حجّةُ الشكل الثامن** (قرارُ المالك): بابان لغرضٍ واحدٍ بسلوكين —
البطاقةُ تختم `opened_from_app` وتقبل `?wallet`، **وكليك لا تفعل واحداً منهما**.
**وأثرُه مالٌ لا يدخل**: حاملُ الدورين كان يرتدّ عند `start_topup` **فلا يفتح
شحنَ كليك أصلاً**.

**واتُّبع ختمُ البطاقة بحرفه لا صيغةٌ جديدة** — وإلا صار البابان ثلاثة:
نفسُ `WalletChoice` في الموجّه، ونفسُ `owner_type_for(owner, declared=…)` في
الخدمة، ونفسُ `opened_from_app=owner_type.value` عند الفتح، ونفسُ القراءة منه
عند التسوية، ونفسُ `_WALLET_SIDES` مشتقّاً من التعداد لا مكتوباً بيد.

### وثالثةٌ لم تكن في العدّ — **التطبيقُ لم يكن يُعلن أصلاً**

الخلفيةُ تختم لكنّ **تطبيق الراكب لم يكن يرسل `?wallet` في أيِّ باب شحن** —
لا البطاقةِ ولا كليك ولا اليدويّ. **فالبطاقةُ كانت مقطوعةً لحاملِ الدورين
كذلك**، والفرقُ الذي بدا بين البابين كان في الخلفية وحدَها.

**والتطبيقُ يقرأ رصيدَه بـ`?wallet=rider` منذ زمن** — فالسياقُ كان معلوماً
عنده يقيناً **ولم يُقَل في الشحن**. فصارت الأبوابُ الثلاثةُ تعلنه.

### المقيسُ في الاتجاهين — بالدفتر لا بالردّ

| | |
|---|---|
| مزدوجٌ يفتح كليك بلا إعلان | `409 wallet_owner_undecided` |
| معلَنٌ «راكب» ثمّ وصلت الحوالة | راكب `7.223 → 9.223` · **والكبتنُ لم يتحرّك** |
| معلَنٌ «كبتن» من التطبيق نفسِه | كبتن `3.800 → 6.800` · **والراكبُ لم يتحرّك** |
| كبتنٌ وحدَه يُعلن «راكب» | `403` «لا محفظة لهذا الحساب من هذا النوع» |

**والقيدان في الدفتر بـ`owner_type` الصحيح**: `rider 2.000 → 9.223` و
`driver 3.000 → 6.800`.

> **ولزم القياسَ عقدُ كليك وهميّ** على قاعدة التطوير (`use_mock`، وهو **مرفوضٌ
> في الإنتاج** بالبناء). **وأُطفئ بعد القياس** — إشعالُ قناةِ دفعٍ لا يُترك
> أثراً جانبياً لقياس، **وإعادتُه نداءٌ واحدٌ من شاشة العقود** متى لزم.

**فصار العدُّ ٢١ من ٢١ تُعلن، وصفرٌ بلا إعلان.**
<!--/جديد-->

<!--جديد-->
## خمسةُ بنودٍ في جولةٍ واحدة (2026-08-28)

### ١ — النسخُ الاحتياطي: **ثلاثةُ أشياءَ لا اثنان**

**لم تكن الجدولةُ مطفأةً ولا المهمّةُ صامتة** — كانت تعمل كلَّ ربع ساعة
**وتفشل وتسجّل**: نجاحٌ يتيمٌ 08-22 و**٣٤٠ فشلاً متتالياً** حتى 08-28،
سببُها `pg_dump: command not found`.

**والعلّةُ صورةٌ أقدمُ من الميزة**: `worker`/`beat` على بناء **08-10**،
و`postgresql-client-16` أُضيف إلى `Dockerfile` في **08-16** مع ميزة النسخ
نفسِها. و`backend` أُعيد بناؤه 08-22 **وفيه `pg_dump`** — وهو تفسيرُ النجاح
اليتيم. **وهي عائلةُ «الحاويةُ تبدو كأنها فعلت ما طلبتَ»**: الكودُ مربوطٌ
حيّاً فالصفوفُ تُكتب، **والبرامجُ من الصورة فلا تُحدَّث**.

**والصمتُ عطبٌ ثانٍ منفصلٌ ومسجَّلٌ في `PATTERNS.md`** — إنذارٌ ينادي من لا
يسمع.

**والاتجاهان مقيسان**: نسخةٌ أُخذت (٢١٫٢ م.ب) **واستُعيدت في قاعدةٍ جانبيةٍ
وطابقت الحيَّ**: نفسُ الأعداد، ومجموعُ الدفتر `133.738`، **وبصمةُ md5 على
الدفتر كلِّه متطابقة**. وفشلٌ عمديٌّ (جذرٌ لا يُكتب فيه) **صاح** وسجّل خطأه.
والإنذارُ صار يصل **٣ صناديق** بعد `0`.

> **وثغرةٌ صغيرةٌ في `restore.sh`**: `--into DBNAME` **لا يُنشئ القاعدة**
> فيسقط بـ«database does not exist». تُنشأ بيدٍ قبله.

### ٢ — `check:money-visible`: **الجدولُ كبر، وما ظهر كان مستوراً**

كانت `seen` مجموعةً واحدةً للأسطح الثلاثة، **فقارئٌ في سطحٍ يُسكت مرآةً في
آخر**. فُصلت سطحاً سطحاً — **والمرآةُ هي الدعوى فتُحاسَب في سطحها**.

| | قبل | بعد |
|---|---|---|
| أسماءٌ مكشوفة | ٤ | **٥** — ومنها `fare` الذي لم يظهر قطُّ |
| مواضعُ مكشوفة | ٦ | **٧**، كلٌّ باسم سطحه |

**والاتجاهان مقيسان بحقلٍ مصنوع**: مرآةٌ بلا قارئٍ في سطحها **تُكشف**، وقارئٌ
حقيقيٌّ **يمرّ صامتاً**. **وأُصلح فحصُ «الاستثناءُ زالت علّتُه» بدوره**: كان
يقلّم استثناءً ما تزال مخالفتُه قائمةً لأن له قارئاً في سطحٍ آخر.

**والخمسةُ مقيَّدةٌ بحالها لا بعلّةٍ مخترَعة** — عرضُها أو حذفُ مرآتها قرارُ
منتَجٍ ينتظر المالك، **والحارسُ يصيح يومَ يصير لأحدها قارئ**.

### ٣ — شاشةُ الإقلاع تقول ما تعرف

كان أيُّ فشلٍ في `GET /config` يُرسم «الشبكة ضعيفة» — **فتُسمّى علّةٌ لا
تُعرف**، وقد كذبت على المالك ثلاثَ مرّاتٍ في أسبوعٍ وشبكتُه سليمة.

صارت ثلاثةَ نصوصٍ لثلاثةِ أشياءَ تُعرف، و**رمزٌ فنّيٌّ قصيرٌ** تحت «تعذّر
الوصول». مقيسٌ بالعين على ثلاثة أسباب: `HTTP 500` · `HTTP 503` ·
`ERR network_unreachable`.

### ٤ — المفاتيح: **صفرٌ عارٍ**

ثلاثةُ `<button>` بلا `role` صارت مكوّناً واحداً `Switch` بـ`role="switch"`
و`aria-checked`. **ورابعٌ من العائلة نفسِها**: منتقي الدولة في الترويسة —
حالُه لونٌ أيضاً، ووُسم `radiogroup`/`radio` لأنه **اختيارٌ من متعدّد لا حالُ
تشغيل**. والقياس: الحالُ يُقرأ من السمة **بلا نقر**.

### ٥ — دليلُ جولة الهاتفين في `HANDOFF.md`

**رحلةٌ واحدةٌ تقيس أربعاً**، **وإحالةُ الراكب تكافئ بعد رحلةٍ واحدةٍ لا
ثلاث** (٢٫٠٠٠ · `required_rides=1`) فتُختار على برنامج الكبتن.

**وصُحِّح ختمُ `+962790000011`** من أنثى إلى ذكر من باب اللوحة بسببٍ مكتوب —
ضابطٌ مختومٌ خطأً يفسد قياسَ الخدمة النسائية في الاتجاهين.

### ⚠ بندٌ عُدَّ ولم يُصلَح — **بابا دفعٍ آخران بلا صندوق**

`notify_user` (دفعٌ بلا كتابةِ صندوق) يُنادى من **موضعين** خارج
`_safe_notify`، كلاهما في `tasks/pauses.py`: تنبيهُ تجاوز الانتظار **للراكب
وللكبتن**.

**وخطرُهما أخفُّ من إنذار النسخ وأخبثُ في وجهٍ آخر**: هذان مستخدمان **لهما
أجهزةٌ فعلاً** فالدفعُ يصل — **لكن لا صفَّ صندوقٍ يُكتب**. وقاعدةُ المشروع أن
الدفعَ **لا يُرسل لجهازٍ مقبسُه مفتوح**، أي أن **من كان التطبيقُ مفتوحاً عنده
لا يرى الإشعارَ أصلاً ولا يجده في صندوقه**. **عُدّا ولم يُصلَحا بقرار المالك.**
<!--/جديد-->

<!--جديد-->
## رُفع إلى الإنتاج — `9481186` (2026-08-28)

**البوّاباتُ الستُّ خضراءُ مقيسةً**، بعد رفعةٍ أولى قُتلت عمليتُها من خارجها
فتركت **نصفَ رفعة** (الدرسُ في `PATTERNS.md`).

| البوّابة | المقيس |
|---|---|
| ١ الإعلان | ١٨ التزاماً · **ترحيلةٌ معلَّقة صفر** · لا ملفَّ مال |
| ٢ الدفعُ وCI | أخضر — تشغيل `33140105549` |
| ٣ النسخة | `/d/taxo-backups/20260828T134014Z` · 56K |
| ٤ التحقّق | **الأربعةُ فُتحت وقيس محتواها** |
| ٥ الرفع | `moved=0 patch=0` · الثلاثُ بُنيت على الخادم |
| ٦ التحقّق | إيداعُ الخادم = CI · الترحيلة `0057` = رأسُ الشجرة · `environment: production` · صفرُ أخطاءٍ في السجلّ |

**والصفوفُ بعده = قبله حرفاً**، **وصفوفُ المتجر صفرٌ على الإنتاج** —
`vehicle_skins` · `vehicle_skin_prices` · `driver_vehicle_skins`. **فالمتجرُ لم
ينزل**، وهو المقصود: لا `seed` يكتبه ولا ترحيلةَ تُدرجه.

**وأسعارُ الإنتاج قُرئت ولم تُمسّ**: الأردن ١٫٥٠٠ · ٩٫٠٠٠ · ٣٠٫٠٠٠ · وليبيا
٥ · ٣٠ · ١٠٠. **وأعلى عرضٍ فعّال «الشهر الأول مجاناً» ١٠٠٪ بلا نهاية.**
**وثلاثةُ أرقامٍ تفترق**: الإنتاجُ، وجهازُ التطوير (١٫٢ · ٧٫٢ · ٢٤)، ومرجعُ
المالك (٣ · ١٥ · ٤٥) — **قِيست ولم تُصلَح**.
<!--/جديد-->

<!--جديد-->
## التوقيعُ مقيسٌ من الحزمة نفسِها — وأين يسكن المفتاحُ وكلمتُه (2026-08-28)

**البصمتان متطابقتان حرفاً**، مقروءتين من موضعين مستقلَّين: من **المفتاح**
بـ`keytool -list -v`، ومن **الحزمة المبنيّة** بـ`apksigner verify --print-certs`.

| | SHA-256 | SHA-1 |
|---|---|---|
| المفتاح | `3B:DC:73:91:8E:2D:…:E1:9E` | `64:D9:26:6F:0D:B7:…:1F:CA` |
| الحزمة | **نفسُها** | **نفسُها** |

`CN=mohammed aldeeb, OU=TAXO, O=sbonge, L=Tripoli, ST=Tripoli, C=ly` ·
**RSA 4096** · `SHA384withRSA` · صالحٌ حتى **2054-01-11** · والاسمُ المستعار
**`taxo`**.

**وقِيس التطبيقان لا واحد** — `driver-app` و`customer-app` **ملفّا
`build.gradle` منفصلان**، وتطابقُ أحدهما لا يشهد للآخر (وهو الشكلُ الثامن).
**والحزمُ الستُّ مُسحت بعد القياس**، والشجرةُ نظيفة.

> **وملحوظةٌ تُقال ولا تُصلَح**: التوقيعُ `v1`+`v2` **و`v3` غيرُ مفعَّل** —
> يكفي المتجرَ اليوم، **ويلزم يومَ تُدوَّر المفاتيح**.

### وأين يسكنان — **بالمسار لا بالمحتوى**

| | المسار |
|---|---|
| كلمةُ المفتاح | `C:\Users\loly3\.taxo-secrets\taxo-keystore.password` |
| المفتاحُ (الأصل) | `D:\taxo-keys\taxo-release.jks` |
| المفتاحُ (نسخةٌ ثانية) | `C:\Users\loly3\.taxo-secrets\keystore-backup\taxo-release.jks` |

**كلاهما خارج المستودع تماماً**، بصلاحيات `loly3:(F)` وحدَها بلا وراثة —
**مع مفتاح SSH في المجلَّد نفسِه**. والنسخةُ الثانيةُ **مطابقةٌ بـSHA-256**.

**وتُقرأ من هناك عند الحاجة ولا تُنسخ**: لا إلى الشجرة، ولا إلى `.env`، ولا
إلى رسالة إيداع. **والبناءُ يقرؤها في أربعة متغيّرات بيئة**:
`ANDROID_KEYSTORE_PATH` · `ANDROID_KEYSTORE_PASSWORD` · `ANDROID_KEY_ALIAS`
(`taxo`) · `ANDROID_KEY_PASSWORD`.

> **وفخّان وقعا مقيسَين في هذا البناء**: `assembleRelease` يشترط **JDK 21**
> ولا يكفيه ١٧ الذي على المسار — وهو في `Android Studio/jbr`. **و`cap sync`
> يرفض بلا `TAXO_CHANNEL`** (`public` أو `test`) **ولا افتراضَ له بقصد**.
<!--/جديد-->

<!--جديد-->
## المتجرُ نزل إلى الإنتاج، والمجرى صار يعرف الأربع (2026-08-29)

### المتجر — **٣٦٩ مركبةً حيّةً**

| | قبل | بعد |
|---|---:|---:|
| `vehicle_skins` | 0 | **369** |
| `vehicle_skin_prices` | 0 | **738** (سوقان لكلٍّ) |
| `driver_vehicle_skins` | 0 | **0** — لم يشترِ أحدٌ بعد |

كلُّها فعّالة، ولكلٍّ **رسمتا متجرٍ وخريطة**. والندرةُ أربعُ طبقات: عاديّ 184
· مميّز 111 · نادر 56 · **أسطوريّ 18**.

**ومقيسٌ حيّاً لا في القاعدة وحدَها**: `GET /vehicle-skins/{id}/art/store`
يجيب **200 · 36 ك.ب · `image/jpeg`** من `api.tajora.ly`.

> **والرسومُ تسكن مخزنَ الوثائق** (`/app/var/documents`) **وهو حجمٌ مسمّى لا
> شجرةُ المشروع** — فلا يعيدها سحبُ git، **وتدخل النسخةَ في `files.tar.gz`**.
>
> **وطريقُ الإيصال مرّ بالحاوية لا بالمضيف**: `~/taxo/backend/var` مملوكٌ
> للجذر (أنشأه دوكر)، فمستخدمُ `taxo` لا يكتب فيه — والمادّةُ وُضعت
> بـ`compose cp` ثمّ فُكّت من داخل الحاوية التي تملك المسار.

**ونسخةٌ سبقته وحُقّقت**: أُخذت من الخادم (`taxo-20260828-214303`)، وسُحبت،
**وفُتحت وقيس محتواها** — `PGDMP` صحيح 229,653 بايت، والترحيلة `0057`، ومعها
`files.tar.gz` وبصمتاهما في البيان.

### والمجرى: **أربعُ حزمٍ لا حزمتان**

**كان الوسمُ سيبني موقَّعاً ولا يجد ما ينشره** — والعلّةُ ثلاثةُ مواضعَ
افترقت عن `channels.json` منذ صارت القنواتُ نكهتين (2026-08-26):

1. `cap sync` **بلا `TAXO_CHANNEL` يقف باسمه** — والمجرى لم يكن يضبطه.
2. ونكهتان تعنيان أن `apk/release/app-release.apk` **لم يعد موجوداً أصلاً**.
3. و`apk-manifest.mjs` يقرأ من ذلك المسار الميت.

فصار المجرى يبني **قناتين × تطبيقين**، **والنكهةُ تُقرأ من الجدول لا تُكتب**
(`test` محجوزٌ في AGP فنكهتُها `trial`)، **ويقيس التوقيعَ في الأربع ويعدّها**
— فثلاثةٌ من أربعٍ كانت تمرّ صامتة. **والعامّتان وحدَهما تنزلان صفحةَ
التحميل**، والتجريبيّتان تُرفَقان بالإصدار: نسخةٌ تخاطب جهازَ مطوّرٍ في صفحةٍ
عامّةٍ تتوقّف حين يُطفأ حاسوب.

### والبابان أُغلقا — **وصفرُ نداءٍ بقي**

`tasks/pauses.py` كان ينادي `notify_user` مرّتين — **دفعٌ بلا صندوق**. صارا
`publish_pause_limit_exceeded` على `_safe_notify`، **وصفرُ مناداةٍ لـ
`notify_user` خارج `_safe_notify` في المشروع كلِّه**.

**والاختبارُ القائم كان يدّعي ما لا يقيس**: اسمُه «يُنبَّه الطرفان» وهو يعدّ
ما تعيده الكنسةُ **ولا يسأل أوصل شيءٌ إلى أحد**. أُضيفت القياساتُ: صفٌّ لكلِّ
طرف، وحمولةٌ خام، **وجملتان تفترقان**.

### والأسعارُ والعرض — **مقيسةٌ ولم تُمسّ**

- **أسعارُ المركبات تُعدَّل من اللوحة لا مخبوزة** — حقلُ سعرٍ لكلِّ سوقٍ في
  `VehicleSkins.tsx` وبابُ `PATCH` قائم. **فشرطُ المالك محقَّق.**
- **وأسعارُ الاشتراك على الإنتاج = بذرةُ `PLAN_DEFAULTS` حرفاً**: الأردن
  ١٫٥ · ٩ · ٣٠، وليبيا ٥ · ٣٠ · ١٠٠.
- **والعرضُ الفعّالُ محدودٌ لا مفتوح**: «الشهر الأول مجاناً» ١٠٠٪ — لكن
  `audience=new_driver` · `max_uses_per_driver=1` · `total_budget=300` ·
  وخطّةٌ واحدةٌ بعينها. **فبلا نهايةٍ في التاريخ، لا بلا سقفٍ في المال.**
- **وأرقامُ التطوير ٠٫٨ من الإنتاج في الثلاثة** (١٫٢/١٫٥ · ٧٫٢/٩ · ٢٤/٣٠) —
  **خصمٌ منتظمٌ ٢٠٪ لا بذرةٌ عشوائية**. والصفُّ نفسُه **لم يُقَس** لأن دوكر
  متوقّفٌ على الجهاز، ويُقال كذلك.

### بنودٌ كُتبت ولم تُشغَل

- **مرجعُ المالك ٣ · ١٥ · ٤٥ يخالف الإنتاجَ في السوقين** — رقمٌ ينتظر قراره.
- **`scripts/pull-backup.ps1` يعتمد `rsync`** وهو غيرُ مثبَّتٍ على الجهاز:
  **النسخةُ تُؤخذ على الخادم وتنجح، والنقلُ وحدَه يسقط**. سُحبت بـ`ssh+tar`.
- **`v3` غيرُ مفعَّلٍ في التوقيع** — يكفي اليومَ، ويلزم يومَ تُدوَّر المفاتيح.
<!--/جديد-->

<!--جديد-->
## بندٌ: ما الذي ينزل من `CLAUDE.md` حين يبلغ السقف (قرارٌ مؤجَّل 2026-08-29)

**لا يُفعَل اليوم** — 55,595 من 60,000، والفسحةُ 4,405 حرفاً. **وهذا مكتوبٌ
الآن كي لا يُقرَّر تحت ضغط السقف**: من يقرّر وهو مضطرٌّ يحذف ما يجده لا ما
يجب.

**والقياسُ أوّلاً — ثلاثةُ أقسامٍ تحمل ٧٠٪ من الملفّ:**

| القسم | حروف | نسبة |
|---|---:|---:|
| **الفهرس** — كلُّ ما نُقل بسطرٍ وموضع | 15,136 | ٢٧٪ |
| **Commands** | 12,390 | ٢٢٪ |
| **Project rules that override defaults** | 10,849 | ٢٠٪ |
| الوقوفُ للضرورة | 4,754 | ٩٪ |
| الباقي (٥ أقسام) | 12,352 | ٢٢٪ |

**والترتيبُ حين يحين — من الأرخص إلى الأغلى:**

1. **`Commands` ← ملفٌّ خامس (`COMMANDS.md`) بشرطٍ في الجدول**: «قبل أن تشغّل
   أمراً على الحزمة أو الحاويات أو الترحيلات». **وهو أرخصُ ما يُنقل**: نصُّه
   إجرائيٌّ يُفتح عند الحاجة الفعلية، **لا قاعدةً تحكم قراراً**. ويوفّر ٢٢٪.
2. **`Project rules` ← `ARCHITECTURE.md`** — أكثرُه أقفالٌ وترتيبُ قفلٍ ومراحلُ
   `SPEC §16`، **وهي معمارٌ لا حكم**. ويبقى في `CLAUDE.md` سطرٌ واحدٌ بشرطه:
   «قبل أن تكتب مساراً يغيّر حالَ صفّ». يوفّر ٢٠٪.
3. **والفهرسُ لا يُنقل ولا يُقصّ** — **هو الطريقُ إلى المنقول**، ونقلُه يجعل
   «من لا يعرف أن الشيءَ مكتوبٌ لن يفتح ملفّاً ليقرأه» تنطبق على الفهرس نفسِه.
   **وقصُّه يجعله قائمةً ناقصةً تُقرأ كاملة** — وذاك أسوأُ من طولِه.

**وما لا يُنقل أبداً**: المطلقاتُ الثلاث · بوّاباتُ الرفع الخمس · القاعدتان
اللتان تعلوان · «الوقوفُ للضرورة» · وشروطُ الملفّات الأربعة. **هذه تحكم متى
تقف وماذا لا تفعل، ومن لم يقرأها لا يعرف أنه يحتاجها** — وهو الفرقُ بينها وبين
الإجراء.

> **وعلامةُ البدء**: **58,000** لا 60,000 — النقلُ نفسُه يضيف أسطرَ شرطٍ
> وفهرس، **فمن ينتظر البلوغَ يجد أن ما ينقل به قد نفد**. وهي قاعدةُ «التسليمُ
> قبل الحدِّ لا عنده» بعينها.
<!--/جديد-->

<!--جديد-->
## توقيعان لمعرّفٍ واحد — **الإزالةُ لازمةٌ لا محتملة** (قِيس 2026-08-29)

**السؤال**: أيستطيع من ثبّت المنشورَ اليومَ أن يحدِّث فوقه بحزمة الإصدار؟
**الجواب: لا.**

**والقياسُ من الملفَّين المنشورَين نفسِهما** (سُحبا من `taxo.tajora.ly`،
5,992,798 و6,246,815 بايت، والبيانُ يقول `v0.1.4` · `de612356`):

| | الشهادة | SHA-256 |
|---|---|---|
| المنشورُ الآن | `C=US, O=Android, CN=Android Debug` | `5686172807c0…` |
| مفتاحُ الإصدار | `CN=mohammed aldeeb, OU=TAXO…` | `3bdc73918e2d…` |

**والمعرّفان واحدان** — قُرئا من الحزمتين بـ`aapt2 dump packagename`:
`ly.tajora.rider` · `ly.tajora.driver`، **وهما ما ستحمله نكهةُ `public`**
(`applicationId` بلا لاحقة).

**فمعرّفٌ واحدٌ وتوقيعان** ⇒ أندرويد يردّ التحديثَ بـ
`INSTALL_FAILED_UPDATE_INCOMPATIBLE`.

> **وما قِيس وما لم يُقَس، بحدِّه**: قِيست **الشهادتان والمعرّفان** — وهما ما
> يقرّر. **ولم يُقَس الرفضُ على جهازٍ حقيقيّ** (لا هاتفَ ولا محاكيَ في هذه
> الجلسة)، وهو سلوكُ منصّةٍ موثَّقٌ لا اجتهاد. **ويُقال كذلك.**

### والصفحةُ كانت تقول ذلك — **وبتاريخٍ خاطئ**

صندوقُ `presign-note` موجودٌ منذ 2026-08-21 ويقول إن الإزالةَ ستلزم — **لكنه
يعلّقها على «نزول المتجر»**. **والكسرُ يقع في أوّل حزمةٍ تالية من الصفحة
نفسِها**، أي في هذا الوسم. فمن قرأه اطمأنّ إلى أن التحديث القادم عاديّ.

**فصُحّح النصُّ قبل الوسم لا بعده**: «من يحمّلها الآن سيحتاج إزالتَها **قبل
تثبيت النسخة التالية** — وهذا يبدأ من التحديث القادم لا من نزول المتجر»، ومعه
**ما سيراه بعينه** («لم يكتمل التثبيت» ليس عطباً)، **والخطوتان** (احذف ثمّ
ثبّت)، **وأن الدخولَ يُعاد مرّةً** لأن الإزالةَ تمحو بياناتِ الجهاز —
والحسابُ والمحفظةُ عندنا لا عليه.
<!--/جديد-->

<!--جديد-->
## الدخولُ بالبصمة — بُني في التطبيقين (2026-08-29)

### القياسُ الذي قرّر الشكل

**رمزُ التجديد يُستهلك مرّةً ويُدوَّر** — `token_service.rotate_refresh_token`
يحذف مفتاحَ Redis القديم ويُصدر زوجاً جديداً، وإعادةُ المستهلَك تُرفض.
**فنسختان منه ليستا نسختين: واحدةٌ حيّةٌ وأخرى ميتةٌ بعد أوّل تجديد** — وهو
الشكلُ الثامن بحرفه. **فالبيتُ واحد**: يعيش في المخزن الآمن وحدَه ويُنزع من
`localStorage`، **ويُعاد كتابتُه بعد كلِّ تدوير** عبر حاقنٍ في `tokens.save`.

**وأعمارُ الرموز**: وصولٌ ٣٠ دقيقة · تجديدٌ ٣٠ يوماً. **فمن فتح التطبيق خلال
الثلاثين لا يُسأل بصمةً أصلاً** — وهو المقصود لا نقص.

**والإضافتان بخطِّ Capacitor 7 لا 8**: `@aparajita/capacitor-biometric-auth@9.1.2`
و`@aparajita/capacitor-secure-storage@7.1.6` — كلتاهما `@capacitor/core ^7.4.4`
(و`10.0.0` تشترط Capacitor 8، والمشروعُ على 7). و`minSdk 23` يكفي BiometricPrompt.

**وعزلُ النكهتين**: `…​.test` **حزمةٌ أخرى بمجلَّد بياناتٍ ومدخلِ Keystore
آخرَين** — حكمُ المنصّة لا إعدادٌ نضبطه. **ولم يُقَس على جهاز.**

### والأربعُ التي تمحو — كلٌّ في موضعها

| | الموضع |
|---|---|
| خروج | `session.signOut` |
| تبديلُ كلمة المرور | `ForgotPassword` — **قبل** أن تقوم الجلسةُ الجديدة |
| الخادمُ يقول «لم تعد صالحة» | `setSessionLostHandler` |
| إطفاءُ الميزة | `setBiometric(false)` |

**والتفضيلُ يبقى في الثلاثة الأُوَل**، والإطفاءُ وحدَه يطفئه — فمن خرج ثمّ دخل
بكلمته عاد زرُّه بلا أن يُشعلها. **و`armed` غيرُ `enabled`**: الزرُّ لا يُرسم
إلا بوجود رمزٍ فعليّ، **وزرٌّ يُرسم على التفضيل وحدَه زرٌّ يفشل عند الضغط**.

**وأثرُ تبديل كلمة المرور على الأجهزة الأخرى مقيس**: `set_password` في الخلفية
**يُبطل كلَّ الجلسات** — فتموت نسخُها وتُمحى بالثالثة.

### ما قِيس وما لم يُقَس — **بحدِّه**

**قِيس بالعين من متصفّح حقيقيّ (DOM لا كود):**

- **زرُّ البصمة غائبٌ في شاشتَي الدخول** — والشاشةُ مرسومةٌ فعلاً (أزرارُ
  الكبتن الثلاثة، وزرُّ دخول الراكب).
- **ومفتاحُ البصمة غائبٌ في شاشتَي الإعدادات** بعد دخولٍ حقيقيّ.

**ولم يُقَس — لا جهازَ موصولاً (`adb devices` فارغة)، ويلزمه S21:**

- دخولٌ ببصمةٍ صحيحةٍ ينجح · وبصمةٌ خاطئةٌ تُرفض · وخروجٌ ثمّ فتحٌ يُخفي الزرّ
  · وجلسةٌ أبطلها الخادمُ تمحو وتطلب دخولاً كاملاً · وعزلُ النكهتين في Keystore.

### ⚠ بندٌ كُتب ولم يُشغَل — **`DEV_BUILD=1` يبني بلا عنوانٍ أصلاً**

`check-dist-target --intent` يقبل `DEV_BUILD=1` **ولو كان `VITE_API_BASE_URL`
فارغاً**، و`client.ts` حينها **يرمي عند تحميل الوحدة** — فالتطبيقُ لا يقلع
ويظهر «تعذّر الوصول».

**ووقع مقيساً اليوم**: بُنيت الثلاثةُ بـ`DEV_BUILD=1` وحدَها، **فخدمت حاوياتُ
التطوير حزماً لا تقلع**، وأولُ قياسٍ للمتصفّح أعطى «الزرُّ غائب» — **وهو خضرةٌ
كاذبة**: الشاشةُ كلُّها كانت غائبة. أُعيد البناءُ بـ`VITE_API_BASE_URL=http://localhost:8001`
فرُسمت الشاشاتُ وصحّ القياس.

**والإصلاحُ سطر**: يشترط الحارسُ هدفاً غيرَ فارغٍ في الفرع المحلّيِّ أيضاً —
`DEV_BUILD=1` يأذن بعنوانٍ محلّيّ، **لا بغياب العنوان**.
<!--/جديد-->

<!--جديد-->
## `DEV_BUILD=1` صار يشترط عنواناً — **الإذنُ ليس عنواناً** (2026-08-29)

**البندُ المكتوبُ أمسِ شُغِّل.** كان `DEV_BUILD=1` وحدَه يقطع البوّابةَ الأولى
**ولو كان `VITE_API_BASE_URL` فارغاً** — و`client.ts` حينها **يرمي عند تحميل
الوحدة**، فتُبنى حزمةٌ لا تقلع.

**وهي عائلةُ الاحتياط الصامت التي نُزعت من الثلاثة**: `POSTGRES_PASSWORD:?`
و`ANDROID_KEYSTORE_PATH` و`TAXO_CHANNEL` — **قيمةٌ تقرّر إلى أين تذهب البيانات
لا تُترك للسكوت**. وهذه رابعتُها، وقد أفلتت لأن `DEV_BUILD=1` **بدا إعلانَ
قصدٍ وهو إعلانُ نيّةٍ بلا وجهة**.

**وكذبت مقيساً**: بُنيت الثلاثةُ بها وحدَها، فخدمت حاوياتُ التطوير حزماً لا
تقلع، **وأولُ قياسٍ بالمتصفّح أعطى «الزرُّ غائب ✓» والشاشةُ كلُّها غائبة**.

**والرفضُ يسمّي علّتَه هو لا الرسالةَ العامّة**: من كتب `DEV_BUILD=1` بيده ثمّ
قرأ «بناءٌ بلا هدف» يظنّ الحارسَ لم يرَ إذنَه — **فيُطارد ما ليس هناك**.

### مقيسٌ في الاتجاهين، في الثلاثة

| الحال | الرمز | ما يُطبع |
|---|:--:|---|
| `DEV_BUILD=1` بلا عنوان | **1** | «**إذنٌ بلا عنوان**» ومعه الأمرُ الصحيح |
| `DEV_BUILD=1` + `localhost:8001` | **0** | «بناءٌ محليٌّ مُصرَّحٌ به: `http://localhost:8001`» |
| هدفٌ بعيدٌ بلا `DEV_BUILD` | **0** | «الهدف مُصرَّحٌ به: `https://api.tajora.ly`» |
| لا إذنَ ولا عنوان | **1** | الرسالةُ العامّةُ كما كانت — **لم تُمسّ** |

**والعنوانُ صار يُطبع مع الإذن** لا «مُصرَّحٌ به» مجرَّدة: **حارسٌ يقول ما
قَبِله يُقرأ، وحارسٌ يقول «تمّ» يُصدَّق ولا يُراجَع.**

> **وفخٌّ وقع في الإصلاح نفسِه ويستحقّ الذكر**: أوّلُ ترقيعٍ كتب **سطراً
> حقيقياً** داخل `join("\n")` بدل الشرطة المائلة، **فسقط الحارسُ بخطأ نحوٍ
> ورمزُ خروجه `1`** — وهو الرمزُ المنتظَر من الاتجاه الأول بعينه. **فلولا
> قراءةُ النصّ لَقُرئ السقوطُ نجاحاً.** والرمزُ وحدَه لا يكفي: **يُقرأ ما
> طُبع لا ما خرج.**
<!--/جديد-->

<!--جديد-->
## خطوةُ الصفر أوقفت جولةَ قياسٍ كاملةً (2026-08-29)

**الحزمتان على S21 صحيحتان تماماً** — قُرئتا **من الجهاز** لا من الصفحة
(`adb pull` ثمّ `aapt2` و`apksigner`):

| | المعرّف | code | البصمة | الشهادة |
|---|---|---:|---|---|
| الراكب | `ly.tajora.rider` | **392** | `7ecf178d1b…` | `3bdc7391…` |
| الكبتن | `ly.tajora.driver` | **392** | `591b2a0ced…` | `3bdc7391…` |

**والبصمتان تطابقان أثرَ الإصدار** الذي طبعه `check:apk` يومَ النشر. **فهي
`v0.2.0` موقَّعةً بمفتاح الإصدار فعلاً.**

### **ثمّ سقطت الجولةُ كلُّها على شيءٍ واحد**

**ولا بصمةَ فيهما أصلاً.** قِيس **من داخل الحزمتين** — لا استنتاجاً من
التواريخ: صفرُ أثرٍ لـ`الدخول بـ` و`بصمة الإصبع` و`BiometricAuth`
و`SecureStorage` و`aparajita` في 58 و44 ملفَّ JS.

**والعلّةُ ترتيبٌ لا عطب**: `v0.2.0` وُسم عند `41656f2`، **وإيداعُ البصمة
`69737d4` بعده بإيداعين**. فالمثبَّتُ يسبق الميزة.

> **ولولا خطوةُ الصفر لَقِيست الأربعُ على حزمةٍ لا تحوي ما يُقاس** — ولَكان
> الجوابُ «الزرُّ غائب» في كلِّ حال، **وهو الجوابُ الصحيحُ للسؤال الخطأ**.
> وهذا ثالثُ موضعٍ تمسك فيه خطوةُ الصفر خُضرةً كاذبةً هذا الأسبوع.

### وبنيتُ ما يحمل الميزةَ ولم أثبّته

`versionCode 394` · موقَّعةٌ بمفتاح الإصدار (`3bdc7391…`) · **والبصمةُ
والملحقان فيها مقيسان من داخلها** · وهدفُها `api.tajora.ly` **بلا عنوانٍ
محلّيّ**. **ولم تُثبَّت** — التثبيتُ بإذن المالك وحدَه.

### وشرطٌ ثانٍ على الجهاز — **يُقال بحدِّه**

`cmd lock_settings get-disabled` أجاب **`true`**، و`dumpsys fingerprint`
لم يُظهر قالباً مسجَّلاً (`Max Template : 4` بلا تعداد). **وهذا يقرأ «لا قفلَ
شاشةٍ ولا بصمةَ مسجَّلة»** — وحينها `checkBiometry().isAvailable` كاذبةٌ
**فلا يُرسم الزرُّ ولو كانت الميزةُ في الحزمة**.

**وقراءتان غيرُ مباشرتين ليستا يقيناً**: لم أفتح شاشةَ الإعدادات على الجهاز،
**فيبقى شرطاً بشرياً** — نظرةٌ واحدةٌ من المالك تحسمه.

### ⚠ الخامسةُ مؤجَّلةٌ بقرار المالك — عزلُ النكهتين

**لا تُبنى النكهةُ التجريبيةُ حتى يُسجَّل `ly.tajora.rider.test` و
`ly.tajora.driver.test` في Firebase** (قرارُ المالك 2026-08-29). فيبقى عزلُ
المخزن الآمن بين النسختين **غيرَ مقيس**، ويُقال كذلك.
<!--/جديد-->

<!--جديد-->
## الغلافُ يحمّل شاشاتِه من الشبكة — **فما في الحزمة زينة** (قِيس 2026-08-29)

**قُرئ من داخل الحزمة المثبَّتة على S21:**

```
server: {"url": "https://driver.tajora.ly", "androidScheme": "https"}
```

**فالحزمةُ غلافٌ يفتح الموقع، لا تطبيقٌ يشغّل ما فيه.** وحزمةُ الـJS المرفقةُ
في `assets/public/` **لا تُنفَّذ ألبتّة** ما دام `server.url` مضبوطاً.

**وهذا يُبطل دعوىً قلتُها مرّتين**: «الميزةُ في المثبَّت — مقيسةٌ من داخله».
**كانت القراءةُ صحيحةً والاستنتاجُ خاطئاً**: قِستُ ما في الحقيبة، **والذي
يعمل هو ما على الشبكة**. والذي يعمل اليومَ هو ما نُشر عند `9481186` — **قبل
إيداع البصمة `69737d4`**.

> **وخطوةُ الصفر أمسكت الأولى وأخطأت الثانية**: سألت «أهذه الحزمةُ هي التي
> وُقّعت؟» فأجابت بصدق، **ولم تسأل «وأين تسكن الشاشةُ التي تعمل؟»**. فصار
> السؤالُ الرابعُ في خطوة الصفر: **من أين يقرأ الغلافُ شاشاتِه؟**

**والأثرُ العمليّ**: **لا تُقاس ميزةُ واجهةٍ على الهاتف قبل أن تُنشر إلى
`driver.tajora.ly`/`app.tajora.ly`** — والتثبيتُ وحدَه لا يكفي. وثلاثُ جولاتِ
قياسٍ اليومَ ذهبت في هذا: «لا مفتاح · لا سطر · لا زرّ» — **وكلُّها الجوابُ
الصحيحُ لسؤالٍ لم يُسأل**.

### والمستوى المطلوب — مقيسٌ ومُجاب

| | القيمة | المصدر |
|---|---|---|
| ما تطلبه الشيفرة | **لا شيء** — فالافتراضُ `weak` | `androidBiometryStrength` غيرُ ممرَّر · افتراضُ الملحق `AndroidBiometryStrength.weak` · وفي جافا `authenticator = BIOMETRIC_WEAK` |
| ما يقيسه الملحقُ للإتاحة | `canAuthenticate(BIOMETRIC_WEAK) == SUCCESS` | `BiometricAuthNative.checkBiometry()` |
| وجهُ S21 | `modality 8` · **`oemStrength 255`** = **Class 2 / WEAK** | `dumpsys biometric` من الجهاز |
| إصبعُ S21 | `modality 2` · `oemStrength 15` = Class 3 / STRONG | نفسُه |

**فالوجهُ يُقبل بما تطلبه الشيفرةُ اليوم، ولا تخفيضَ مطلوباً أصلاً** — لأن
المطلوبَ `weak` منذ البداية.

### ⚠ وما يخصّ الأمنَ حقّاً — **غيرُ ما ظنناه**

**مفتاحُ Keystore غيرُ مربوطٍ بالتصديق**: `KeyGenParameterSpec` في
`@aparajita/capacitor-secure-storage` يضبط `BLOCK_MODE_GCM` و
`ENCRYPTION_PADDING_NONE` **ولا يضبط `setUserAuthenticationRequired`** (قِيس
في مصدره).

**فالبصمةُ بوّابةُ تطبيقٍ لا بوّابةَ مفتاح**: المفتاحُ في Keystore العتاديّ
ومحصورٌ بالحزمة (فلا يُستخرج بنسخِ ملفّ ولا بنسخةٍ احتياطية)، **لكنّ أيَّ
شيفرةٍ داخل التطبيق تفكّ التعميةَ بلا بصمة**.

**وأثرُ ذلك على سؤال «ما ثمنُ التخفيض؟»**: **لا ثمنَ لأنه لا تخفيض** — الوجهُ
Class 2 ومطلوبُنا `weak` أصلاً، **والمفتاحُ لم يكن محميّاً بالبصمة في الحالين**.
**والطريقُ الوحيدُ الذي يجعل البصمةَ تحرس المفتاحَ حقاً** هو
`setUserAuthenticationRequired(true)` — **ويشترط Class 3 (إصبعاً)**، والمستشعرُ
الإصبعيُّ في S21 معطوب. **فهو قرارُ أمنٍ للمالك، ولم يُتَّخذ.**
<!--/جديد-->

<!--جديد-->
## قراءةٌ قبل بناء: كيف يُدفع الاشتراك اليوم (قِيس 2026-08-29)

**والمقروءُ يخالف الظنَّ في موضعٍ ويؤكّده في آخر.**

### ١) بابان لا باب — **والبطاقةُ مبنيّةٌ من طرفَيها**

| الباب | الخلفية | تطبيقُ الكبتن |
|---|---|---|
| المحفظة | `POST /subscriptions` → `purchase_with_wallet` | مرسوم |
| **البطاقة** | `POST /subscriptions/card` → `card_payments.start_subscription` | **مرسومٌ أيضاً** (`buyWithCard`) |

**فليست المحفظةُ وحدَها**، والبطاقاتُ المحفوظة موصولةٌ كذلك.

### ٢) والكبتنُ **يستطيع** الشحن في الخلفية — والمانعُ زرٌّ لا قاعدة

`POST /wallet/me/topups/cliq` يأخذ **`CurrentUser`** لا راكباً، ويقرّر المحفظةَ
بـ`owner_type_for(user, declared=…)`. **ولا شرطَ دورٍ في المسار.**

**و`RIDER_METHODS` اسمٌ يُوهم**: شرطُه `method not in RIDER_METHODS` — **قناةٌ
لا دور**.

**والمنعُ في التطبيق**: `driver-app/src/api/endpoints.ts` فيه **صفرُ نداءِ
شحن**، بينما الراكبُ ينادي `‎/wallet/me/topups/cliq?wallet=rider` **بمحفظةٍ
مكتوبةٍ في المسار**. **فمحفظةُ الكبتن مصرفٌ لا صندوق — بابٌ بلا زرّ، لا قرارٌ
مكتوب.**

### ٣) والعقود على الإنتاج — **وهنا العلّةُ الحقيقية**

صفوفُ `provider_credentials` على الإنتاج **أربعة**: `mapbox` · `fcm` ·
`firebase_auth` (مطفأ) · `whatsapp`.

**ولا `telr` ولا `cliq_acquirer` — لا مطفأً ولا مفعّلاً.**

**فالبابان الإلكترونيان ميّتان على الإنتاج**: البطاقةُ ترتدّ
`card_gateway_unavailable` (503، «الميزة مبنية والعقد غائب»)، وشحنُ كليك الآليّ
يرتدّ 503 بالتصميم نفسِه. **فالكودُ قائمٌ والقابضُ غائب.**

> **فعلّةُ المالك صحيحةٌ في أثرها، وسببُها غيرُ ما ظُنّ**: ليس أن المسارَ غيرُ
> مبنيّ — **بل أن لا عقدَ يقبض**. وبناءُ بابٍ ثالثٍ لا يغيّر ذلك بحرف.
<!--/جديد-->

<!--جديد-->
## الحزمُ المنشورةُ بُنيت بلا Firebase — والحارسُ صار يوقف (2026-08-29)

**خامسةُ عائلة «قيمةٌ تقرّر إلى أين تذهب البيانات لا تُترك للسكوت»** — بعد
`POSTGRES_PASSWORD:?` و`ANDROID_KEYSTORE_PATH` و`TAXO_CHANNEL` و`DEV_BUILD`.

**وما كان هناك أسوأُ من سطرِ سجلّ**: `try { servicesJSON.text } catch` **يبتلع
كلَّ استثناء** — غيابَ الملفّ وتلفَه وتعذّرَ قراءته — ثمّ يسجّل بمستوى `info`
(لا يُطبع افتراضاً) **ويُكمل البناءَ ناجحاً**.

**والأثرُ مقيسٌ في الحزم المنشورة نفسِها** — سُحبت من S21 وقُرئت من داخلها:

| | `google_app_id` · `project_id` | `879288557931` |
|---|---|---|
| **`v0.2.0` — بناءُ CI (على صفحة التحميل)** | **غائبةٌ كلُّها** | **غائب** |
| بناءٌ محلّيٌّ والملفُّ موجود | موجودة | موجود |

**فالحزمتان على الصفحة بلا إشعاراتٍ أصلاً، وبناؤهما أخضرُ صامت.** والعلّةُ أن
`google-services.json` **مُتجاهَلٌ في git ولا سرَّ له في CI** — فلا بيتان
يفترقان، **بل بيتٌ واحدٌ وآخرُ فارغٌ يبني ولا يشكو**.

### والإصلاح — ومقيسٌ في ثلاثة اتجاهات

`app/build.gradle` في التطبيقين: **يُطبَّق الملحقُ إن وُجد الملفُّ وله حجم**،
**وإلا يسقط البناءُ باسمه** — **والإذنُ يُعلَن ولا يُفترض**
(`TAXO_ALLOW_NO_FIREBASE=1`، كما `DEV_BUILD=1`).

| الحال | الرمز | ما وقع |
|---|:--:|---|
| بلا الملفّ | **1** | يسمّي الناقصَ ويقول: من السرّ في CI · ومن Firebase محلياً · وكيف يُؤذن بلا إشعارات |
| بإذنٍ صريح | **0** | سطرٌ **بمستوى `lifecycle`** يُطبع فعلاً: «لا إشعارات في هذه الحزمة» |
| **وبالملفّ** | **0** | والحزمةُ تحمل `google_app_id` · `project_id` · `gcm_defaultSenderId` · **ورقمَ المشروع و`taxo-84a5f` مقروءَين من `.arsc`** |

**وخطوةٌ في CI تفكّ السرَّ إلى التطبيقين وتقيس ما فكَّته**: JSON بعملاءَ لا
نصٌّ فارغ، **وتشترط الأربعة بأسمائها** — فسرٌّ بعميلين يوقف البناءَ ولا يمرّ.

> **وفخُّ الهروب وقع مرّتين في يومٍ واحد**: كتابةُ `\n` داخل نصٍّ مُقتبَسٍ عبر
> heredoc تُنتج **سطراً حقيقياً** يكسر الملفّ — في `check-dist-target.mjs`
> أوّلاً، ثمّ في `build.gradle`. **وفي الثانية سقط البناءُ بخطأ نحوٍ ورمزُه
> `1`** — وهو الرمزُ المنتظَر من اتجاه الرفض بعينه. **فلولا قراءةُ النصّ
> لَقُرئ السقوطُ نجاحاً مرّةً ثانية.** والعلاجُ نصٌّ ثلاثيُّ الاقتباس بلا
> هروبٍ أصلاً.
<!--/جديد-->

<!--جديد-->
## القناةُ اليدويةُ صارت تخدم الكبتن — ومبلغُ المشرف هو المال (2026-08-29)

**ولا بابَ ثانياً**: `POST /wallet/me/topups` هو البيت — كان يأخذ `CurrentUser`
لا راكباً منذ نشأته، **والمانعُ كان زرّاً غائباً في تطبيق الكبتن**.

### الأربعةُ التي بُنيت في الخلفية

1. **الـalias يُقرأ من الإعداد لا من نصّ** — `require_cliq_alias` بيتٌ واحد،
   **ويُقاس في المسار لا في الشاشة وحدَها**: الشاشةُ تُخفي، والمسارُ يمنع من
   التفَّ عليها.
2. **`CliqAliasNotConfigured` — 503 برمزٍ خاصّ** لا رسالةٌ عامّة، ولا يلوم
   المستخدمَ على إعدادٍ ليس له.
3. **مبلغُ المشرف هو ما يدخل الدفتر**، ودعوى المستخدم تبقى في `amount`
   **تُقرأ ولا تُصرف**.
4. **صفُّ تدقيقٍ لكلِّ تأكيد** — بالمشرف والمبلغين والمحفظة وقيد الدفتر.

### والخمسةُ مقيسةٌ على قاعدة التطوير — لا موصوفة

| السؤال | الجواب المقيس |
|---|---|
| سوقٌ بلا alias | **503** `cliq_alias_not_configured` · «الشحن بكليك غير متاح في هذا السوق الآن» |
| كبتنٌ يشحن — أتصل محفظتُه؟ | الصفُّ في القاعدة `owner_type = driver` ✓ |
| مبلغُ المشرف ٧٫٥٠٠ ودعوى المستخدم ١٠٫٠٠٠ | **الدفترُ `7.500` · `topup` · `driver`** — والدعوى باقيةٌ في الطلب |
| تأكيدٌ مرّتين | **409** `invalid_status_transition` — **فلا يدخل المالُ مرّتين** |
| **مؤكَّدٌ ثمّ مُلغى** | **409، والإلغاءُ مرفوض** — `reject` يشترط `PENDING`. **فلا يُعكَس قيدٌ من هذا الباب**، والتصحيحُ قيدٌ مقابلٌ من مسار التسوية |
| صفُّ التدقيق | `{"action":"confirm","credited":"7.500","claimed":"10.000","wallet":"driver","transaction_id":…}` بـ`actor_id` |

> **و«مؤكَّدٌ ثمّ مُلغى» كُتب ولم يُخترع**: لا مسارَ يعكس شحناً مؤكَّداً — وهو
> موافقٌ لقاعدة المشروع «**الدفترُ لا يُعدَّل، والتصحيحُ قيدٌ مقابلٌ لا محو**».

### ولمَ `/config` ينشره

ليقرأه التطبيقان **فلا يكتب أحدُهما رقماً من عنده**، ومقيسٌ أنه ينشر
`JO → TAXOJO` **وليبيا ليست في القائمة أصلاً** (سوقٌ غيرُ مرئيّ).

**والباقي: الشاشات** — زرُّ الشحن في تطبيق الكبتن، وورقةُ الـalias والمرجع
والحال، وحقلُ المبلغ في شاشة اللوحة.
<!--/جديد-->

<!--جديد-->
## دفعُ الاشتراك بكليك — **البيتُ كان قائماً، ولم يُبنَ ثالث** (2026-08-29)

**والقراءةُ غيّرت التصميم**: كنتُ ماضياً إلى `wallet_topup_requests` — **وهو
بيتُ محفظةٍ يكتب قيداً بالضرورة**، أي الخلطُ الذي نهى عنه المالك.
**و`provider_orders` هو «بيتٌ واحدٌ بغرضٍ معلَن» الذي وصفه**: غرضُه مُصرَّح،
والتسويةُ تُوجَّه به، **وغرضُ الاشتراك يكتب صفَّه ولا يمسّ الدفتر** — بنصِّ
الكود منذ المرحلة السادسة: «لا قيد في الدفتر: مال الكبتن خرج من بطاقته لا من
محفظته».

**فالمطالبةُ اليدويةُ طلبُ مزوّدٍ بمصدرٍ يدويّ**: `provider = cliq_acquirer`
**والقضيبُ واحد**، `source = manual` **والمختلفُ مَن يحصّل**.

### وشرطٌ لم يلزم قبله

**المزوّدُ كان يحكم بالمبلغ**: `activate_paid_order` **لا يقارن بالسعر أصلاً**
(قِيس) — لأن الطلبَ يُفتح بالمبلغ المخصوم وما يعود من تِلر هو ما خُصم.
**فلمّا صار المصدرُ بشرياً لزم الشرط**: المشرفُ يكتب رقماً بيده، **ورقمٌ ناقصٌ
يفعّل اشتراكاً بأقلَّ من ثمنه**.

### مقيسٌ في الاتجاهين — من القاعدة لا من الشاشة

| | الجواب |
|---|---|
| المبلغُ المفتوحُ به | **7.200 = سعرُ العرض**، لا 9.000 الخام |
| **ناقصٌ (5.000 من 7.200)** | **لا تفعيل** — الاشتراكاتُ 9 قبلَه و9 بعده · الحالُ `created` · و`failure_reason` = «وصل 5.000 من 7.200 — ينقص 2.200 JOD» |
| **مساوٍ (7.200)** | **فُعِّل** — 9 ← 10 · `amount_paid=7.200` · `list_price=9.000` · `active` |
| **حركةُ محفظة الكبتن** | **صفرٌ في الحالين** — الدفترُ لم يُمسّ |
| صفُّ التدقيق | `{source: manual, credited, due, activated, purpose}` |

### وختمٌ كان يكذب — أُصلح في الطريق

`activate_paid_order` كان يختم `payment_method = card` **ثابتاً**، لأنه كان
مسارَ البطاقة وحدَه. **فلمّا شاركه كليكُ اليدويّ صار اشتراكٌ دُفع بكليك يُقرأ
«بطاقة» في كلِّ تقريرٍ بعده.** صارت الطريقةُ تُمرَّر — ومقيسٌ بعده:
`amount_paid=1.200 · payment_method=cliq · active`.

### والباركود: **لا يُولَّد، بل يُرفع**

`cliq/acquirer.py` يأخذ `qr_payload` **من جواب القابض** ويرمي «مزود كليك لم
يعد برمز الدفع» إن غاب، **والمحاكي يصنع `CLIQ|alias|amount|ref` وهي صيغةٌ
مخترعةٌ للفحص**. **فالرمزُ لا يُشتقّ من alias**، والحقلُ `cliq_qr_path` صورةٌ
يرفعها المالك. **ومولّدُ QR موجودٌ في المشروع** — يرسم حمولةً تأتيه ولا
يخترعها.

### ويومَ يصل العقد

**يتغيّر**: `source` يصير `acquirer`، وخطوةُ «تأكيد الدفع» يملؤها إشعارُه بدل
المشرف، والرمزُ يأتي منه. **ولا يتغيّر**: `provider_orders` وغرضُه،
و`_activate_subscription` وأنه لا يمسّ الدفتر، وشاشةُ الدفع وسعرُها المشتقّ.
<!--/جديد-->

<!--جديد-->
## شاشاتُ الدفع بكليك — مقيسةٌ بالعين (2026-08-29)

| ما قِيس | النتيجة |
|---|---|
| اختيارُ عرضٍ ← طرقُ الدفع | **الثلاثةُ ظاهرة**: خصمٌ من المحفظة · بطاقة · **كليك** |
| **المبلغ** | **1.200 = سعرُ العرض** لا سعرَ الخطّة الخام |
| الحساب | `TAXOJO` كما ضُبط في اللوحة — **لا مكتوبٌ في الشيفرة** |
| بلا صورةِ رمز | **«لم يُرفع رمز الاستجابة بعد»** والشاشةُ قائمةٌ بحسابها ومبلغها ومرجعها |
| المرجع | «اكتب هذا المرجع في التحويل» — `cart_id` قابلاً للنسخ |
| حالُ الطلب | **«بانتظار التأكيد»** |
| جملةُ المدّة | **«ستتم المراجعة خلال ٣ إلى ٥ دقائق»** — والعددان من اللوحة |
| ولا يُدَّعى أنها آلية | **«التحصيل يدويّ: يراجع مشرفٌ… ولا يُخصم شيءٌ تلقائياً»** |
| **سوقٌ بلا alias** | زرُّ كليك **يظهر معطَّلاً** وعلّتُه مكتوبة: «لم يُضبط حساب الاستقبال» |

**والبطاقةُ لم تُقَس معطَّلةً** — `card_enabled` **مشتعلٌ على جهاز التطوير**،
فالمسارُ الظاهرُ هو الصحيحُ لحاله. **ويبقى المعطَّلُ غيرَ مقيسٍ ويُقال كذلك.**

### وأين يرى الكبتنُ حالَ مطالبته بعد أن يغلق الشاشة

**ثلاثةُ مواضع**: `GET /subscriptions/cliq` يعيد مطالباتِه وحالَها؛ وشاشةُ
`‎/subscription/cliq/:id` **تُستعلَم كلَّ ١٥ ثانيةً ما دامت معلّقة وتتوقف عند
أيِّ حالٍ نهائية**؛ **وشاشةُ الاشتراك هي المدخل** — ومن أغلق التطبيقَ يعود
إليها ويجد طلبَه، **فلا يعيد التحويل**. والنصُّ يقول ذلك صراحةً: «ولا تعِد
التحويل — يكفي واحد، وتجد حال طلبك هنا وفي شاشة الاشتراك».

### واللوحة

حقلُ الحساب وحقلا المدّة ورفعُ صورة الرمز — **في بطاقة سياسات الدفع مع مهلة
كليك**، فبيتُها واحد. وتبويبُ **«مطالبات كليك»** بزرِّ «تأكيد الدفع»، ولوحتُه
تقول قبل النقر: **«التأكيد يفعّل الاشتراك ولا يُلغى»**، وتنبّه حين يكون
المبلغُ أقلَّ من المطلوب.

> **وحارسٌ صاح في الطريق بحقّ**: استثناءُ `check:money-math` كان مربوطاً بـ
> `Settings.tsx:949` **فأزاحه إدراجي سطراً واحداً** — فصاح «فجوةٌ لم تعد تقع».
> **ومِرساةٌ بالسطر تتقادم بأوّل إدراج**، وهي كلفةٌ مقبولةٌ لأنها تصيح ولا تسكت.
<!--/جديد-->

<!--جديد-->
## `v0.2.1` منشورةٌ وتحمل Firebase — وبندان (2026-08-29)

### ١) الحزمُ المنشورةُ صارت تحمل المشروع

**قُرئ من داخل الملفَّين المسحوبَين من `taxo.tajora.ly`** — لا من سجلّ بناء:

| | `google_app_id` · `project_id` · `gcm_defaultSenderId` | `879288557931` · `taxo-84a5f` | الشهادة |
|---|---|---|---|
| `v0.2.0` (قبل) | **غائبةٌ كلُّها** | **غائب** | `3bdc7391…` |
| **`v0.2.1` (الآن)** | **موجودةٌ كلُّها** | **موجودان** | `3bdc7391…` |

`code 399` · إيداع `f4cc2faf`. **فالإشعاراتُ صار لها إعدادٌ في الحزمة**، وهو
ما كان غائباً عن كلِّ من نزّل `v0.2.0`.

> **وخطوةٌ لا تقع بالوسم وحدَه**: بناءُ الوسم يرفع الأثرَ إلى إصدار GitHub،
> **والصفحةُ لا تتغيّر حتى يسحبه الخادمُ** بـ`pull-release.sh`. وقِيس أن
> الصفحةَ بقيت تنشر `v0.2.0` بعد نجاح الوسم — **والنشرُ خطوتان لا واحدة.**

### ٢) بندٌ: **البطاقةُ لم تُقَس معطَّلة**

`card_enabled` **مشتعلٌ على جهاز التطوير**، فالذي ظهر (زرٌّ فعّالٌ بلا سطرِ
علّة) **صحيحٌ لحاله ولا يبرهن على المعطَّل**. **ولا يُقاس اليوم** بقرار المالك.

### ٣) بندٌ: **مراسي الأسطر — عُدَّت ولم تُصلَح**

**كلُّ مِرساةٍ بالسطر تتقادم بأوّل إدراج** — ووقع مقيساً: إدراجُ كتلةٍ في
`Settings.tsx` أزاح استثناءً سطراً واحداً فصاح الحارسُ «فجوةٌ لم تعد تقع».

| الموضع | العدد |
|---|---:|
| `tools/check-money-math.mjs` (`ملف:سطر`) | **3** |
| مفاتيحُ `ملف:سطر` في `backend/tests/` | **11** |
| **المجموع** | **14** |

**والثلاثةُ في الحارس هي الأخطر**: تصيح على الشجرة كلَّ بناء. **والأحدَ عشرَ في
الاختبارات** مفاتيحُ استثناءٍ في `test_no_shortcut_fixtures` وأخواته — تتقادم
كذلك، **لكنها تظهر عند تشغيل المجموعة لا عند كلِّ بناء**.

**ولم يُصلَح شيءٌ منها بقرار المالك** — والكلفةُ مقبولةٌ لأنها **تصيح ولا
تسكت**: مِرساةٌ متقادمةٌ تُوقف البناءَ وتُصحَّح في دقيقة، **وبديلُها (مطابقةٌ
بالنصّ) يسكت حين يتغيّر النصُّ نفسُه**.
<!--/جديد-->

<!--جديد-->
## الدخولُ بالبصمة — **الفيصلُ حُسم، وعطبٌ في تصميمي كُشف** (2026-08-29)

### ١) المانعُ كان الوجهَ لا القفل — بجهازين لا بمنطق

| الجهاز | القفل | المسجَّل | النتيجة في الإعدادات |
|---|---|---|---|
| **S21** (SM-G991N) | مضبوط | **وجهٌ فقط** (الإصبعُ معطوب) | **لا مفتاح** · سطرُ الإرشاد |
| **Note 20** (SM-N980F · أندرويد 13) | مضبوط | **إصبع** (وصفرُ وجه) | **المفتاحُ ظاهرٌ**: «الدخول ببصمة الإصبع» |

**ونفسُ الشيفرة ونفسُ الطلب (`weak`) في الحالين.** وتصنيفُ الحسّاسات متطابقٌ
في الجهازين: إصبعٌ `15` STRONG · وجهٌ `255` WEAK.

**فوجهُ سامسونج غيرُ متاحٍ لتطبيقات الطرف الثالث** — يفتح الشاشةَ **ولا يصادق
تطبيقاً**، رغم أن `dumpsys biometric` يعلنه Class 2.

**والنصُّ صُحّح بإقرار المالك**: «فعّل قفل الشاشة **وبصمة إصبع** في إعدادات
جهازك. **وبصمة الوجه في أجهزة سامسونج لا تفتح هذه الميزة**.» — لأن الأولَ
**كان يرسل القارئَ إلى ما فعله**.

### ٢) ⚠ وعطبٌ في تصميمي يجعل الميزةَ لا تعمل أصلاً

**قِيس من مسار الشيفرة لا من الشاشة**: في `client.ts` كلُّ ردٍّ `401` يفشل
تجديدُه يستدعي `onSessionLost()` — **وحاقني يستدعي `forgetToken()`**.

**وعند إقلاعٍ باردٍ والميزةُ مشتعلة**: رمزُ التجديد يعيش في المخزن الآمن
**وحدَه** (وهو الصواب — بيتٌ واحدٌ لرمزٍ يُدوَّر)، والذاكرةُ فارغةٌ بعد
الإقلاع، **فـ`tokens.refresh()` تعود `null`** ⇒ `refreshSession` تردّ `false`
فوراً ⇒ `onSessionLost` ⇒ **يُمحى الرمزُ الذي تقوم عليه الميزةُ كلُّها**.

**فالنتيجةُ أن الزرَّ لا يظهر أبداً**: أوّلُ نداءٍ بعد فتح التطبيق يهدم
المخزَّن قبل أن يُستعمل.

> **وهو الشكلُ الذي يمسك نفسَه بنفسه**: «انتهت الجلسة» **حالٌ حقيقيةٌ في
> المسار القديم** (لا رمزَ ⇒ اخرج)، **وصارت كاذبةً في المسار الجديد** (لا
> رمزَ **في الذاكرة** ⇒ اسأل المخزنَ الآمن أولاً). **شرطٌ صادقٌ بحالةٍ واحدة
> يكذب حين تصير الحالتان** — وهو الدرسُ المسجَّل قبل ساعاتٍ في `PATTERNS.md`
> بعينه، **وقعتُ فيه ثانيةً في اليوم نفسِه**.

**ولم يُصلَح** — بقرار المالك: يُقال أيُّهما وقع قبل أن يُلمس شيء.
<!--/جديد-->

<!--جديد-->
## ⚠ بندٌ يصيح: **عمرُ رمز الوصول مخفوضٌ إلى دقيقةٍ على جهاز المطوّر** (2026-08-29)

`ACCESS_TOKEN_EXPIRE_MINUTES=1` في `.env.local` — **خُفض من ٣٠ لقياس الإقلاع
البارد** (بلا خفضٍ ينتظر القياسُ ثلاثين دقيقة).

**ويُعاد إلى ٣٠.** ورقمٌ خُفض لقياسٍ ونُسي **عطبٌ يولد بلا صياح**: كلُّ جلسةٍ
على جهاز التطوير تنتهي كلَّ دقيقة، **فيُقرأ ذلك عطباً في الجلسة لا أثراً
لقياس**.

**والإنتاجُ لم يُمسّ** — التغييرُ في `.env.local` على جهاز المالك وحدَه.

## وبريدُ النطاق — تمّ إلا قياساً واحداً

| | |
|---|---|
| Email Routing | **مفعَّل** · ٥ سجلّاتٍ أُضيفت · و١٥ CNAME لم تُمسّ |
| العنوانُ المستقبِل | `aldeeb7767@gmail.com` · **مُحقَّق** |
| `privacy@` · `support@` | **أُنشئتا ومفعّلتان** |
| **وصولُ رسالةٍ فعليّة** | **لم يُقَس** — منفذُ 25 محجوبٌ صادراً من الجهاز (`TimeoutError` إلى `162.159.205.11`)، **فلا إرسالَ مباشراً** ولا مُرحِّلَ معتمَداً في المشروع |

## وبندُ حارسٍ لم يُبنَ

**فحصٌ يمنع كتابةَ `REFRESH_KEY` في `localStorage` خارج فرعٍ يشترط أن البصمةَ
مطفأة** — وهو ما كان يمسك «بيتين» الثلاثةَ قبل أن تقع. **لم يُبنَ**، ويُكتب
بنداً لأن الميزةَ ما تزال تُقاس.
<!--/جديد-->

<!--جديد-->
## الرحلةُ والأذونات — الثمانيةُ بعد قراءتها وبناءِ أربعةٍ منها (2026-08-30)

**والترتيبُ ترتيبُ المالك**: بدأ البناءُ بالطريق المسدود لأنه **حيٌّ اليومَ لا
مستقبَل**، ثم البقيّةُ ببنودها.

### ما كان مبنيّاً ووجدَه القياسُ خلافَ الظنّ

- **سقفُ السلسلة مبنيٌّ منذ البداية**: `MAX_ATTEMPTS = 5` و`TOTAL_TIMEOUT_SECONDS
  = 120` — واقتراحُ المالك كان قائماً قبل أن يُقترح.
- **وبيتُ الدَّين مبنيٌّ مرّتين لا صفراً**: `driver_advances` (بنسبة اقتطاعٍ
  وحدٍّ أدنى يُبقى للكبتن) و`ride_cancellation_charges` (بمهلةِ حملٍ وعَلَمِ
  منع). **والعَلَمان يُقرآن في شرط أهلية التوزيع فعلاً** — فالتجميدُ كشرط عملٍ
  كان يعمل، والناقصُ نوعُ دَينٍ ثالثٌ لا آلةٌ ثالثة.
- **ومن هو في رحلةٍ لا يُعرض عليه**: `Driver.current_ride_id.is_(None)` في
  الأهلية. **وضغطتان على الطلب**: `RideAlreadyActive`.

### وعطبٌ كان حيّاً — عمولةُ الكاش بلا رصيد

عمولةُ رحلةِ الكاش كانت **قيداً سالباً** على محفظة الكبتن، و`wallet.record`
يرفض السالب، **وبابُ شحن محفظة الكبتن أُلغي أمسِ** — فكانت الجملةُ «اشحن
المحفظة ثم أكّد» تدلّ على ما ليس هناك، **وكبتنٌ رصيدُه دون العمولة لا يُنهي
رحلةَ كاشٍ أصلاً**.

**والحارسُ لم يُرخَ**: المستحقُّ خرج إلى `driver_debts` (الترحيلة `0061`)،
ويُحصَّل من أوّل أجرةٍ تدخل المحفظة **قبل اقتطاع السلفة**، ويُسدَّد جزئيّاً
بكليك، **ويُرفع منعُه عند الصفر لا قبله**.

### وما بقي بندَ انتظارٍ لا بناءً

| البند | حالُه |
|---|---|
| **سقفُ الدَّين** | **مبنيٌّ وفارغٌ عمداً** (`payment_settings.driver_debt_ceiling` = `NULL`) — **ولا يُحجب أحدٌ حتى يكتب المالكُ الرقم**. والحقلُ في اللوحة بجانب استقبال كليك |
| **الفقاعةُ على الجهاز** | بُنيت (`OfferBubble` + `SYSTEM_ALERT_WINDOW`)، **ولم تُقَس بعد بطلبٍ حقيقيّ** |
| **مسبارُ القياس** | `src/trial/OfferProbe.java` — **معزولٌ بالبناء**، ويُنزع بعد أن يُقرأ السبب |
| **الورقةُ السفلية للعرض** | لم تُبنَ — البطاقةُ اليومَ في `Home`، والناقصُ شكلُ العرض لا وصولُه |
| **إعداداتُ المصنّع** | **لا API يقرؤها** — والشاشةُ تقول ذلك ولا تدّعي ضبطَها |
<!--/جديد-->

<!--جديد-->
## سقفُ دَينِ الكبتن فارغٌ بقرار، لا بنقصٍ في البناء (قرارُ المالك 2026-08-30)

**`payment_settings.driver_debt_ceiling = NULL` في كلِّ سوق، وهذا هو المقصود.**
والمسارُ **كاملٌ ويعمل**: الدَّينُ يُسجَّل، ويُحصَّل من أوّل أجرةٍ تدخل المحفظة،
ويُسدَّد جزئيّاً بكليك، ويُقرأ العَلَمُ في شرط أهلية التوزيع. **والناقصُ رقمٌ
واحدٌ لا شيفرة.**

**ونصُّ قراره**: «اتركه فارغاً كما هو… وأكتبه حين أرى دَيناً حقيقياً في يوم
عمل، **لا اليوم بالتخمين**».

**فمن قرأ الفراغَ بعد شهرٍ فليقرأه قراراً**: لا يُحجب أحدٌ مهما بلغ دَينُه حتى
يُكتب الرقمُ في اللوحة (شاشةُ الإعدادات ← استقبال كليك ← «سقف دَين الكبتن»).
**وصفرٌ ليس فراغاً**: صفرٌ يحجب كلَّ كبتنٍ عليه فلسٌ واحد، ولذلك تفرق القاعدةُ
بين `NULL` و`0` بقيدٍ صريح.
<!--/جديد-->

<!--جديد-->
## الشاشاتُ الأربعُ من ملفّ التصميم — ما قِيس بالعين وما لم يُقَس (2026-08-30)

**بُنيت الأربعُ كما رُسمت** في `mobile-app-design-request`، **وثلاثٌ منها قِيست
بالعين على S21** بلقطاتٍ محفوظة، **والرابعةُ لم تُقَس ويُقال ذلك**.

| الشاشة | موضعُها | قياسُها |
|---|---|---|
| ٠١ داخل التطبيق | `OfferSheet.tsx` | **لم تُقَس بالعين** — انظر أدناه |
| ٠٢ ورقةٌ سفليّة | `OfferSheetWindow.java` | **قِيست** |
| ٠٣ شاشةٌ مقفلة | `OfferActivity.java` | **قِيست بالمسار الحقيقيِّ لا بإجبار** |
| ٠٤ فقاعة + موسَّعة | `OfferBubble.java` | **قِيستا** |

### ولمَ لم تُقَس الأولى

**الغلافُ التجريبيُّ يحمّل شاشاتِه من `dev-driver.tajora.ly`، والهاتفُ يجيب**
`ERR network_unreachable` — **مع أنّ `ping` إلى المضيف نفسِه ينجح من الهاتف
(٥٧ms) و`curl` من الجهاز يجيب ٢٠٠**. وعلى الهاتف شبكةٌ خاصّةٌ فعّالة
(`VpnNetworkProvider`)، **وهي حالُ جهازٍ لا عطبُ شيفرة**.

**فالشاشةُ ٠١ مبنيّةٌ وحرّاسُها خضر** (`tsc` · `check:scale` · `check:digits`)،
**ولم تُرَ بعين** — ولا يُقال إنها رُئيت.

### وما بقي بلا قياسٍ معها

**«يقبل والشاشةُ مقفلةٌ ⇒ الرحلةُ له ⇒ ثم يفتح»** — يحتاج رحلةً حقيقيّةً على
جهازٍ داخلٍ إلى حسابه، **وهو متعذّرٌ بالسبب نفسِه**. والمسارُ مبنيٌّ
(`OfferApi.accept`)، **ولم يُقَس**.
<!--/جديد-->

<!--جديد-->
## بندٌ: حارسٌ يسأل «أيتحدّث السطح؟» لا «أهي الحزمةُ نفسُها؟» (قرارُ المالك 2026-08-30)

**لم يُبنَ اليومَ بقرارِ المالك، ويُكتب بنداً كي لا يضيع.**

### ما كشفه، وكم كلّف

**قِيس 2026-08-30**: `cors_origins` على خلفية التطوير يحوي `localhost`
و`127.0.0.1` وحدَهما — **ولا وجودَ لأصلَي النفق** `https://dev-driver.tajora.ly`
و`https://dev-app.tajora.ly`. **فكلُّ متصفّحٍ يحمّل التطبيقَ من النفق يُمنع في
كلِّ نداء**، والغلافُ التجريبيُّ لم يعمل من هاتفٍ قطّ.

**وثلاثةُ أشياءَ صادقةٍ سترته:**

1. **`curl` لا يمرّ بـCORS أصلاً** — فقياسُ «`dev-api` يجيب ٢٠٠» صادقٌ **ولا
   يقيس هذا**. وهو «قياسٌ صادقٌ تُوسَّع دعواه فوق نطاقه» بعينه.
2. **`check:served` يقارن الحزمَ في ثلاثة أعمدة** — المبنيُّ والمحلّيُّ
   والنفق — **ولا يفتح نداءً واحداً**. وهو **الشكلُ الرابعَ عشر** بحرفه:
   «سطحٌ تُفحص أطرافُه ولا يُسأل: أيتحدّث؟».
3. **والخطأُ يظهر في التطبيق `network_unreachable`** — نصٌّ يقول «الشبكة»
   وعلّتُه إعدادُ خادم، **فيُبحث عنه في المكان الخطأ**. وقد بُحث: أُطفئت
   شبكةٌ خاصّةٌ ولا شأنَ لها.

### وما يُبنى حين يُبنى

**نداءٌ حقيقيٌّ من أصل السطح إلى الخلفية، تُقرأ ترويسةُ**
`Access-Control-Allow-Origin` **في جوابه** — لا `curl` يتجاوز CORS، ولا مقارنةُ
تجزئةِ حزمة. **والسؤالُ: أيقبل الخادمُ نداءَ هذا الأصل؟**

**وموضعُه بجانب `check:served` لا بدلاً منه**: ذاك يقيس «أيَّ حزمةٍ تُخدم»،
وهذا يقيس «أتتكلّم». **وسؤالان لحارسٍ واحدٍ يجعل أحدَهما يستر الآخر.**
<!--/جديد-->

<!--جديد-->
## بندٌ: كيف دُفع إيداعٌ بلا مجموعة — **البابُ لم يقل «لا»، لم يُسأل** (2026-08-30)

**لم يُصلَح اليومَ بقرارِ المالك. وهذه الفجوةُ مسمّاةً بقياسها.**

### ما وقع، بالأرقام

| | |
|---|---|
| آخرُ تشغيلِ CI **أخضر** | `f4cc2fa` · 2026-08-29 **02:08** |
| ثم أُودعت ودُفعت خمسةُ إيداعات | `76827fc` · `3045914` · `5bcd20c` · `c5c9ebd` · `e2ffd1a` |
| تشغيلُ CI على آخرها | `e2ffd1a` · **`failure`** |
| تشغيلُ CI على `76827fc` نفسِه | **لا وجودَ له** — لم يُشغَّل قطّ |
| والأربعةُ الحمرُ التي خلّفها | `test_wallet` ×٣ · `test_wallet_concurrency` · `test_user_roles` |

### وثلاثةُ أسبابٍ يجتمع منها الثقب — كلٌّ منها سليمٌ وحدَه

1. **CI يحرس الدفعةَ لا الإيداع.** GitHub Actions يُشغَّل على **رأس ما دُفع**،
   **فإيداعٌ داخل دفعةٍ لا يُختبر أبداً** — و`76827fc` كان رابعَ خمسةٍ في دفعة.
   **والقاعدةُ تقول «لا يُودَع على مجموعةٍ حمراء»، والمجموعةُ عليه لم تُشغَّل**:
   لم يقل البابُ «لا»، **لم يُسأل**.
2. **وأحمرُ CI تقريرٌ لا بوّابة.** حين سقط `e2ffd1a` كانت الشيفرةُ **على
   `origin/master` بالفعل** — والسقوطُ يُقرأ بعد الدفع لا قبله. **ولا حمايةَ
   فرعٍ تمنعه**: الحسابُ خاصٌّ والميزةُ تحتاج Pro (مقيسٌ: `403` من
   `branches/master/protection`).
3. **ولا خطّافَ محلّيّاً واحداً.** `.git/hooks` **خالٍ إلا من العيّنات** —
   فلا `pre-commit` ولا `pre-push` يسأل عن المجموعة.

### ولمَ لم يُرَ يوماً كاملاً

**لأن السقوطَ في الخلفيةِ لا يظهر في الواجهة**: الحرّاسُ الأماميّةُ خضرٌ،
والحزمُ تُبنى، والشاشاتُ تعمل. **وأربعةُ اختباراتٍ حمراءَ لا تصيح إلا حين
تُشغَّل المجموعة** — وهي خمسون دقيقة، فلا تُشغَّل إلا بقصد.

**وثلاثةُ حرّاسٍ أخرى وُجدت حمراءَ من الإيداعات نفسِها** في اليوم نفسِه: `tsc`
في تطبيقَي الكبتن والراكب، و`tsc` في اللوحة، وترحيلتان بلا `test_migrations`.
**فالنمطُ واحد، والعلّةُ واحدة.**

### وما يُبنى حين يُبنى — ثلاثةُ خياراتٍ لا واحد

- **خطّافُ `pre-push` يشغّل المجموعة** — يمسك كلَّ دفعة، **ويكلّف خمسين دقيقةً**
  في كلِّ مرّة. **ومن يكلّفه ذلك يتجاوزه بـ`--no-verify`.**
- **أو CI على كلِّ إيداعٍ في الدفعة** (`on: push` بمصفوفةٍ من `git rev-list`)
  — يمسك «الإيداعَ داخل الدفعة»، **ولا يمنع الدفعَ** لأنه بعده.
- **أو حمايةُ فرعٍ تمنع الدفعَ حتى يخضرّ** — **وهي وحدَها بوّابةٌ حقيقيّة**،
  وتحتاج حساباً يدعمها.

**والقرارُ للمالك، ولا يُبنى بظنٍّ**: لكلٍّ ثمنٌ مختلف، والأول يُتجاوَز بحرف.
<!--/جديد-->

<!--جديد-->
## بندٌ: أحمرُ CI **تقريرٌ لا بوّابة** — والشجرةُ تقبل ما يقول إنه أحمر (2026-08-30)

**لم يُبنَ بقرارِ المالك: يُكتب بعلّته وبثمنه، ويقرّر متى يدفع.**

### الحال، مقيسةً

| | |
|---|---|
| **حمايةُ الفرع** | **لا وجودَ لها** — `403` من `branches/master/protection`: «Upgrade to GitHub Pro or make this repository public». والمستودعُ **خاصّ** |
| **خطّافٌ محلّيّ** | **لا واحد** — `.git/hooks` خالٍ إلا من العيّنات |
| **أثرُ ذلك** | حين سقط `e2ffd1a` كانت الشيفرةُ **على `origin/master` بالفعل** |

**فالمعنى بحرفه**: CI يقول «أحمر» **بعد** أن تصير الشيفرةُ في الفرع. **ولا
شيءَ في الطريق يمنع الدفع** — لا قبله ولا بعده.

### وثمنُه، بالخيارين

- **GitHub Pro** — يفتح حمايةَ الفرع على مستودعٍ خاصّ. **ثمنٌ شهريٌّ يدفعه
  المالك**، ولم يُقَس هنا لأنه سعرُ خدمةٍ لا رقمُ قياس.
- **أو فتحُ المستودع للعموم** — مجّانيٌّ ويفتحها، **وثمنُه أن تصير الشيفرةُ
  ومعها `SPEC.md` و`STATE.md` مقروءةً للكافّة**. ومشروعٌ يحمل مالَ الناس
  وتفاصيلَ مسارات الدفع **لا يُفتح لتوفير اشتراك**.

**والقرارُ للمالك، ولا يُبنى بظنّ.**

## وسُدَّ نصفُ الثقب: CI على كلِّ إيداعٍ في الدفعة (قرارُ المالك 2026-08-30)

**بُني**: وظيفتا `batch` و`batch-suite` في `.github/workflows/ci.yml` —
تُعدّان إيداعاتِ الدفعة **عدا الرأس** وتشغّلان **المجموعةَ** على كلٍّ منها.

**وما تملكه بحدّه**: المجموعةَ وحدَها على الوسط — **لا حرّاسَ ولا بناءَ
الثلاثة**، فتلك تُقاس على الرأس وثمنُها أربعةُ أضعافٍ لا يشتري قدرَه.
**وسقفُها اثنا عشرَ إيداعاً**، وما سقط **يُقال عدداً** في ملخّص التشغيل —
**ولا سقفَ صامت**.

**وثمنُها مقيسٌ من تشغيلاتٍ حقيقيّة**: وظيفةُ المجموعة **١٦ دقيقة**، والتشغيلُ
الكاملُ ١٦–٢٧. **والوظائفُ تتوازى**، فدفعةٌ من خمسةٍ تزيد الجدارَ **دقائقَ
معدودةً لا أضعافاً** — **وتزيد الدقائقَ المحسوبة ٤ × ١٦ ≈ ٦٤**.

**وحصّةُ الحساب الشهريّةُ لم تُقَس**: بابُ الفوترة يحتاج صلاحيةَ `user` في
الرمز، **ولم أطلبها بلا إذن** — فيبقى «كم يبقى من الحصّة» غيرَ معروف.
<!--/جديد-->

<!--جديد-->
## قرارٌ: التحدّياتُ توسيعٌ للمهامّ لا بيتٌ ثانٍ (قرارُ المالك 2026-08-30)

**لم يُبنَ بعد — يُبنى بعد إيداع الخمسين.** ويُكتب الآن لأن قراراً في الرأس
يذهب مع الجلسة.

### ولمَ توسيعٌ لا بيت

**نسختان من «قِس تقدّماً واعرِض شريطاً» تفترقان أوّلَ تعديل** — وهو الشكلُ
الثامنُ قبل أن يُبنى. والمقياسُ نفسُه (`completed_rides`) والتقدّمُ يُقاس حيّاً
في الحالين، **والمختلفُ ثلاثةٌ لا تُرسم**:

### والثلاثةُ كما حسمها المالك

1. **النافذةُ مضبوطةٌ لا مسمّاة**: **بدايةٌ ونهايةٌ بتاريخين من اللوحة** —
   فتصلح لأسبوعٍ وشهرٍ وموسم. **ولا عمودَ اسمُه «أسبوعيّ»** فيُحتاج ثالثٌ بعد
   شهر. **وقيدُ `EXTRACT(DAY FROM month) = 1` يسقط معها.**
2. **والفريدُ بالنافذة لا بالشهر**: **لا تتداخل نافذتان لمقياسٍ واحدٍ في سوقٍ
   واحد**. فأربعُ نوافذَ متتاليةٍ تمرّ، ومتداخلتان تُمنعان بعلّتهما.
3. **والجائزةُ نوعان معلَنان**: **مستوى** (كما اليوم) **أو سِمةُ مركبة**.

### وأربعةُ حرّاسٍ على الجائزة الثانية — **لأنها بابٌ في مخزونِ بيع**

- **تُملَّك بمسار المتجر نفسِه لا بإدراجٍ ثانٍ** — بيتٌ واحدٌ للملكيّة.
- **وتُخصم من الكمّية المحدودة** إن كانت نادرةً أو أسطورية — **وإلا صار الفوزُ
  يطبع نسخاً بلا حساب**.
- **وقيدُها في الدفتر بصفرِ ثمنٍ وسببٍ معلَن «جائزة تحدٍّ»** — لا شراءٌ بلا مالٍ
  **يُقرأ بيعاً بعد شهر**.
- **ولا تُقبل جائزةُ سِمةٍ غيرِ موجودةٍ أو نفدت كمّيتُها** — **يمنعها البابُ عند
  إنشاء التحدّي لا عند الفوز**، فلا يُوعَد بما لا يُسلَّم.

**ويُقاس**: نافذتان متتاليتان تمرّان · ومتداخلتان تُمنعان · وفوزٌ بسِمةٍ نادرةٍ
**ينقص كمّيتَها** · وسِمةٌ نفدت **لا تُقبل جائزةً**.
<!--/جديد-->

<!--جديد-->
## بندٌ: البوّابةُ الجديدةُ تستهلك حصّة، والحدُّ لم يُقَس (قرارُ المالك 2026-08-30)

**`batch-suite` تشغّل المجموعةَ على كلِّ إيداعٍ في الدفعة** — **‎+١٦ دقيقةً
محسوبةً لكلِّ إيداعٍ زائدٍ عن الرأس**. ودفعةٌ من خمسةٍ ⇒ **‎+٦٤ دقيقة**.

**والحصّةُ الشهريّةُ للحساب لم تُقَس، ولن تُقاس**: بابُ الفوترة يطلب صلاحيةَ
`user` في الرمز، **ولم يأذن المالكُ بها لأجل رقم** — قرارُه 2026-08-30.

**والمراقبةُ عليه**: «سأراقب الفاتورة بنفسي، فإن قربت الحصّةُ أخبرتُك
وخفّضنا». **فالسقفُ بشريٌّ مكتوبٌ لا حارسٌ مبنيّ** — ويُقال ذلك بحدّه.

**وخفضُها حين يُطلب**: سقفُ الاثني عشر يُنزَل، أو تُشغَّل على الإيداعات التي
تمسّ `backend/` وحدَها. **ولا يُبنى أيٌّ منهما اليوم.**

## وما يبقى مكشوفاً بعد اليوم — **بعلمِ المالك** (قرارُه 2026-08-30)

**أحمرُ CI يبقى تقريراً لا بوّابة، والمالكُ يقبله اليوم.** ولا `Pro` ولا فتحٌ
للعموم: **مشروعٌ يحمل مالَ الناس ومسارات دفعه لا يُفتح للعموم توفيراً
لاشتراك**.

**والذي تغيّر**: كان الأحمرُ يُرى على **رأس الدفعة وحدَه**، فيمرّ إيداعٌ في
وسطها بلا أن يُسأل — **وذاك أكثرُ ما كنّا نفتقده، وقد سُدّ**.

**والذي يبقى مكشوفاً بحرفه**: **أنّ أحداً يستطيع الدفعَ على أحمرَ عمداً.**
لا شيءَ في الطريق يمنعه — لا حمايةُ فرعٍ ولا خطّاف. **والمالكُ يعرفه ولا
يفعله**، وهو نصُّ قراره. **ومن يقرأ هذا بعدنا يقرأ حدّاً معروفاً لا فجوةً
منسيّة.**
<!--/جديد-->

<!--جديد-->
## بندٌ: ماذا تعني خُضرةُ CI عن الواجهات بعد قلب الأسماء؟ (قرارُ المالك 2026-08-30)

**قُرئ ولم يُصلَح.** والجوابُ: **ليست علّةً واحدةً ممتدّة، بل ثلاثُ حالاتٍ
مختلفةٍ يجمعها سؤالٌ واحد** — *أيَّ هدفٍ بنى CI، وهل هو الهدفُ الذي يُشحن؟*

### ما يبنيه CI اليوم، مقروءاً من `ci.yml`

| التطبيق | هدفُ CI | هدفُ الشحن الحقيقيّ |
|---|---|---|
| `customer-app` | `https://api.tajora.ly` | `channels.json` عامّ: `api.tajora.ly` · و`deploy.sh`: `FRONT_API` = `api.tajora.ly` |
| `driver-app` | `https://api.tajora.ly` | **مطابق** |
| `admin-panel` | **`https://stg-api.tajora.ly`** | **`deploy.sh` يبني الثلاثة بـ`FRONT_API` واحد** = `api.tajora.ly` |

### فالحالاتُ ثلاث، لا واحدة

**١ — تطبيقا الراكب والكبتن: الهدفُ مطابقٌ لِما يُشحن.**
**فخُضرةُ CI هنا تعني ما تقوله**: الحزمةُ تُبنى بلا سقوطٍ وهدفُها هدفُ
الإنتاج. **ولا تعني أنّ ما على هاتفٍ هو هذا** — تلك مسألةُ الشكل العاشر
وحارسُ `check:served` يقول إنه **لا يقيس الهاتف**.

**٢ — اللوحةُ: هدفُ CI ليس هدفَ الشحن.** `stg-api` في CI و`api` في
`deploy.sh`. **وخُضرتُها تقول «تُبنى على هدفٍ ما»، لا «تُبنى على هدفها».**
**وحارسُ `check:target` يقيس التطابقَ بين المعلَن والمبنيّ** — فهو أخضرُ
صادقٌ لأن المعلَنَ هنا `stg-api` فعلاً؛ **والفجوةُ بين المُعلَن في CI
والمُعلَن في النشر، لا بين معلَنٍ ومبنيّ**.

**٣ — والنفقُ شيءٌ ثالثٌ لم يقع هنا**: بناءُ الواجهات على `dev-*` يقع في
**بناءِ قناة الاختبار** (`TAXO_CHANNEL=test`)، **ولا يقع في CI أصلاً** —
مقروءاً من مصفوفة `frontends`: لا ذكرَ لـ`dev-` فيها.

### وما تعنيه الخُضرةُ بالضبط — بحدّها

**تعني**: الحرّاسُ مرّوا · و`tsc` مرّ · والحزمةُ بُنيت · **وهدفُها المخبوزُ
هو ما صرّحت به المصفوفة**.

**ولا تعني**: أنّ الهدفَ المصرَّحَ في CI هو الذي سيُشحن (**اللوحةُ مثالُه**)
· ولا أنّ ما على جهازِ أحدٍ هو هذه الحزمة (الشكلُ العاشر) · ولا أنّ السطحَ
**يتحدّث** بعد نشره (الرابعَ عشر — وقد وقع اليومَ في `cors_origins`).

### والسؤالُ الذي يبقى للمالك

**أمقصودٌ أن تُبنى اللوحةُ في CI على `stg-api`؟** إن كان مقصوداً فالأمرُ
سليمٌ ويُكتب سببُه؛ **وإن لم يكن، فحارسٌ يبني هدفاً لا يُشحن يمرّ أخضرَ على
ما لا يُقاس**. **ولا أصلحه بظنّي** — لا أعرف أثمّة لوحةُ تجربةٍ منشورةٌ على
`stg-api` أم لا، **ولم يُقَس**.
<!--/جديد-->

<!--جديد-->
## بندٌ: ما يسدّ الفجوةَ بين مُعلَنِ CI ومُعلَنِ النشر (قرارُ المالك 2026-08-30)

**اقتراحٌ لم يُبنَ.** والمشكلةُ بحرفها: **`check:target` صادقٌ في نطاقه** —
يقيس **المُعلَنَ مقابل المبنيّ** داخل بناءٍ واحد. **والفجوةُ خارجه**: أن
المُعلَنَ في CI ليس المُعلَنَ في النشر. **فحارسٌ يبني هدفاً لا يُشحن يمرّ
أخضرَ على ما لا يُقاس.**

### والعلّةُ البنيويّة: ثلاثةُ مواضعَ تعلن الهدف

| الموضع | من يقرؤه |
|---|---|
| `channels.json` | بناءُ الحزم (`build-channel.mjs`) و`check-apk.mjs` |
| `scripts/deploy.sh` (`FRONT_API`) | بناءُ الواجهات على الخادم |
| `.github/workflows/ci.yml` (مصفوفة `frontends`) | بناءُ CI |

**وثلاثةُ مواضعَ لقيمةٍ واحدةٍ تفترق** — وهو الشكلُ المسجَّل نفسُه.
**و`channels.json` كُتب ليكون «مصدراً واحداً لأربع نسخ»**، ثمّ لم يقرأه
`deploy.sh` ولا `ci.yml`.

### والاقتراح — ثلاثُ درجاتٍ بأثمانها

**١ — الأرخص: يقرأ CI من `channels.json`.** تُشتقّ مصفوفةُ `frontends` من
القناة العامّة بدل جدولٍ مكتوبٍ بيد. **يسدّ فرقَ CI عن الحزم، ولا يسدّ
فرقَه عن `deploy.sh`** ما دام `FRONT_API` مستقلاًّ.

**٢ — الأتمّ: `deploy.sh` يقرأ `channels.json` أيضاً.** فيصير المصدرُ واحداً
للثلاثة، **ويسقط `FRONT_API` كمتغيّرٍ مستقلّ** أو يصير تجاوزاً مصرَّحاً
يُطبع في التقرير.

**٣ — والحارسُ الذي يمنع الرجوع**: فحصٌ يقرأ الثلاثةَ ويقارنها، **يسقط إن
أعلن أحدُها هدفاً لا يعلنه الآخر**. وهو الوحيدُ الذي يمنع أن يفترقوا ثانيةً
— **والاثنان قبله يوحّدان اليومَ ولا يمنعان الغد**.

**والترتيبُ المقترح: ٢ ثمّ ٣.** والأول وحدَه يترك نصفَ الفجوة.
<!--/جديد-->

<!--جديد-->
## بندٌ: وظيفةٌ عَلِقت مرّةً — **بشرطِ قراءتها حين تعود** (2026-08-30)

**التشغيلُ ‎#84**: خمسُ مجموعاتٍ متوازية، أربعٌ منها **بين ١٦:١٨ و١٦:٣٣**،
**والخامسة (`540236a`) قُطعت عند ٣٠:١٦ — مهلتُها بالضبط**. `conclusion:
cancelled` **لا `failure`**.

**ولا أثرَ لها**: خطوةُ الأثر كانت `if: failure()` وحدَها، **والإلغاءُ ليس
سقوطاً** — فسُكت عنها. **وقد أُصلح** (`failure() || cancelled()` ومعه طبعُ
`.suite.out` كاملاً في السجلّ)، **فالمرّةُ القادمةُ تكتب أثرَها**.

**ولمَ عَلِقت؟ لم يُقَس، ولا يُخمَّن.** وأربعٌ بجانبها مرّت في ١٦ دقيقة.

### وكيف يُقرأ حين يعود — **شرطٌ مكتوبٌ قبل وقوعه**

| ما يقع | ما يُقرأ |
|---|---|
| **تكرّر على الإيداع نفسِه** | **العلّةُ فيه** — شيءٌ في شيفرة ذلك الإيداع يعلّق |
| **وقع على غيره** | **العلّةُ في البيئة أو في التوازي** — لا في إيداعٍ بعينه |
| **لم يعد** | **عارضٌ**، ولا يُبنى عليه شيء |

**وحالُ المهلة أخطرُ من الحمرة** (قرارُ المالك): **حمرةٌ تُقرأ، ومهلةٌ تُقرأ
علامةً صفراءَ فتمرّ عليها العين**. **فانتهاءُ المهلة يُقال باسمه** —
وخطوةُ الأثر تكتب الآن عند الإلغاء كما تكتب عند السقوط.
<!--/جديد-->

<!--جديد-->
## قرارٌ: بلاطاتُ الخدمات واللافتاتُ جدولان، والحملاتُ ليست بيتاً لأيّهما (2026-08-30)

**لم يُبنَ بعد.** ويُكتب لأن حجّتَه هي ما يمنع دمجَهما بعد شهر.

### أوّلاً — لمَ ليست `notification_campaigns` بيتاً للّافتة

**خمسةُ فروقٍ بنيويّة، مقروءةً من الجدول:**

1. **الحملةُ إرسالٌ واللافتةُ سطح**: آلتُها كلُّها تسليم — `notification_
   deliveries` **صفٌّ لكلِّ متلقٍّ** و`sent_count` و`status: sent`. **واللافتةُ
   لا تُرسل إلى أحد**، فلا متلقٍّ يُسجَّل.
2. **وعمرُها لحظةٌ لا نافذة**: `scheduled_at` و`sent_at` نقطتان، **ولا عمودَ
   انتهاءٍ أصلاً** — واللافتةُ **مدّتُها إلزاميّة** بقرار المالك.
3. **وحالُها نهائيّة**: `sent` نهايةٌ لا رجعةَ فيها.
4. **ولا مقصدَ ولا صورةَ ولا ترتيبَ فيها** — وثلاثتُها شرطٌ في اللافتة.
5. **وساعاتُ الهدوء** (`notification_settings.quiet_hours_*`) تحكم الحملات،
   **والقاعدةُ الثالثةُ في التصميم تقصرها عليها** — فلافتةٌ تسكن بيتَها ترث
   دلالةً لا معنى لها: **لافتةٌ لا «تصل الثالثةَ فجراً»**.

### وثانياً — لمَ البلاطةُ واللافتةُ جدولان لا جدولٌ بنوعٍ مصرَّح

**والحجّةُ للمالك، وهي أقوى ممّا قلتُه:**

- **الفروقُ الخمسةُ نفسُها تفصلهما**: **البلاطةُ دائمةٌ بلا نافذة، واللافتةُ
  مؤقّتةٌ بنافذةٍ إلزاميّة**.
- **وجدولٌ واحدٌ بنوعٍ مصرَّح يعني عموداً إلزاميّاً لصنفٍ واختياريّاً لآخر** —
  **وذاك يُقرأ «إلزاميٌّ أحياناً»، ولا يحرسه شيء**. ولا قيدَ في القاعدة يقول
  «مطلوبٌ إن كان النوعُ كذا» إلا بشرطٍ مركَّبٍ يُنسى.
- **ومقصداهما مختلفان في النوع لا في القيمة**: البلاطةُ **تفتح خدمةً في
  التطبيق**، واللافتةُ قد تفتح **رابطاً خارجيّاً أو لا شيء**.

### وثالثاً — ما يُشترك فيه، يُشترك

**`CampaignAudience` للجمهور في الاثنين** (`all_riders` · `all_drivers`) —
**ولا مفرداتٌ ثانيةٌ تُخترع**. **وبيتُ السوق نفسُه** (`country_code`).

**والفرقُ بين القاعدتين مكتوبٌ كي لا يُخلطا**: «لا تبنِ بيتاً ثانياً لما له
بيت» **تخصّ المفهوم**، و«لا تحشُر شيئاً في بيتٍ ليس له» **تخصّ الصفّ**.
<!--/جديد-->

<!--جديد-->
## ثمانِ نغماتٍ كانت مبنيّةً بلا سلكٍ إليها (قِيس 2026-08-30)

**قِيس أنّ `play(` لا تُنادى في التطبيق كلِّه إلا في ثلاثة مواضع**: توقيعُ
الفتح في `App.tsx`، ومعايناتُ المفاتيح الثلاث في `Settings.tsx`. **ولا نغمةَ
واحدةٌ تُعزف على أيِّ حدثِ رحلة** — ولا `offer` نفسُها، و`startOfferLoop`
**لم تكن تُستدعى من أيِّ شاشة**.

**فالجدولُ مبنيٌّ منذ المرحلة ١٠ والأسلاكُ لم تُوصل** — وهو الشكلُ الذي
يجعل قارئَ الشيفرة يقول «مبنيّة» وهو يقرأ **جدولاً لا سلوكاً**. **وقد وقعتُ
فيه في هذه الجلسة نفسِها**: قلتُ «`offer` و`collected` و`credited` مبنيّة ✅»
من قراءة الجدول.

### وقد وُصلت اليوم

| الحدث | النغمة |
|---|---|
| `ride_offer` | `startOfferLoop()` — تتكرّر حتى ينتهي العدّاد |
| `offer_expired` | `offerExpired` ومعها `stopOfferLoop()` |
| `driver_arrived` | `driverArrived` — **هادئةٌ عمداً**، تقع والكبتنُ يقود |
| `ride_started` | `rideStarted` |
| `ride_completed` | `rideCompleted` — **غيرُ `collected`** |
| `ride_cancelled` | `notify` — **خبرٌ محايدٌ بلا نغمةِ فرح** |
| تأكيدُ التحصيل | `collected` عند وقوعه لا عند فتح الشاشة |

### والبقشيشُ وجد سلكَه — **ولا حدثَ اختُرع** (قرارُ المالك 2026-08-30)

**`credited` تُعزف على إشعار `tip_received`.** والبقشيشُ **الوحيدُ الذي يصل
الكبتنَ دفعاً بلا مقبس**: أحداثُ المقبس أحدَ عشرَ وليس فيها بقشيش، و
`notifications.publish_tip_received` ترسله إشعاراً بمبلغه وعملته ورحلته.

**وبابُ الاستقبال في المقدّمة كان مسدوداً بقرارٍ سليم**: `received: () =>
undefined` وعلّتُه «ما يصل هنا يصله المقبسُ أصلاً». **وهي صحيحةٌ لكلِّ ما له
مقبس، ولا تنطبق على البقشيش** — فاستُثني وحدَه.

### ولا حدثَ لدخول الأجرة، ولا يُبنى (قرارُ المالك)

**والحجّةُ حجّتُه**: الأجرةُ تدخل عند إتمام الرحلة، و`ride_completed` تعزف في
اللحظة نفسِها — **فنغمةٌ ثانيةٌ معها ضجيجٌ لا خبر**.

### وما بقي بلا إشارةٍ من مسارات المال

**`credited` — «دخولُ مال» — لا حدثَ لها.** مقروءاً من `socket.ts`: أحداثُ
الكبتن أحدَ عشرَ، **وليس فيها دخولُ مالٍ إلى المحفظة**. ومسارات دخوله
(`ride_earning` عند التسوية · شحنُ المشرف · تحصيلُ الدَّين) **لا تبثّ شيئاً**.

**وشحنُ المشرف وتحصيلُ الدَّين يبقيان صامتين** — لا حدثَ لهما ولا إشعار.
**ولم يُبنَ لهما شيء**: الأوّلُ نادرٌ ويقع والكبتنُ لا ينتظره، والثاني خصمٌ
لا دخل. **ويُكتب هنا كي لا يُقرأ صمتُهما عطباً.**
<!--/جديد-->


<!--جديد-->
## الشاشتان الرئيسيتان بُنيتا — وأربعُ زياداتٍ على الرسم بعللها (2026-08-30)

**الرئيسيتان صفحتان تُمرَّران، والخريطةُ بطاقةُ ١٧٠ في أعلى كلٍّ منهما** —
وكانتا خريطةً ملءَ الشاشة بأوراقٍ فوقها. **وطورا الطلبِ والتتبّعِ لم يتغيّرا**:
من ضغط «إلى أين؟» أو قَبِل طلباً رأى الخريطةَ ملءَ الشاشة كما كانت.

**والخريطةُ عقدةٌ واحدةٌ تُوضع حيث تنتمي** (`mapNode`) لا نسختان بخصائصَ
متوازية — **ونسختان تفترقان بحرفٍ يوماً**، وهو الشكلُ الثامن على شاشةٍ واحدة.

### وعلّةُ كلِّ زيادةٍ مكتوبةٌ في مجلّد التصميم نفسِه

**كُتبت في `home Captain/README.md` و`home Rider/README.md`** لا هنا وحدَه:
من يفتح الرسمَ غداً يجد الفرقَ حيث يبحث عنه، **ولا يقرأ الزيادةَ انحرافاً عن
تصميمٍ قيل فيه «بلا تغييرٍ ولا استثناء»**.

### ونسبةُ الكبتن نُشرت على بابٍ واحدٍ لا على كلِّ `DriverOut`

الرسمُ يخبز «عمولة TAXO ‎0%». **والمعروضُ نسبتُه هو**:
`settings_service.commission_percent_of_driver` — **وهي حرفاً ما يفعله
`rides.accept`**: عمودُ الوعد إن كان، وإلا نسبةُ السوق. **فلا يفترق ما يُعرض
عمّا يُقتطع**، ومن اشترى اشتراكاً بوعدِ صفرٍ يرى صفراً ولو رفع السوقُ إلى خمسة.

**وموضعُها `DriverProfileOut` لا `DriverOut`**: بابُ «ملفّي» يعرف صاحبَه،
**وصفُّ كبتنٍ في جدول اللوحة لا يحمل هذا السؤال**. ونشرُها على كلِّ `DriverOut`
كان يفرض استعلاماً في **خمسةِ مساراتٍ إداريّةٍ لا تقرؤه** — **وحقلٌ لا يقرؤه
أحدٌ هو ما يمسكه `check:readers`**.

### وثلاثةُ أرقامٍ في الرسم لم تُرسم لأنها لا تُقاس

1. **«5 كباتن قريبون · دقيقتان»** → العددُ وحدَه. **والمهلةُ لا تُحسب قبل أن
   تُعرف نقطةُ الالتقاط**، **ورقمٌ يُرسم ولا يُقاس وعدٌ يعدّه صاحبُه ولا يجده**.
2. **«طرابلس»** → عنوانُ موقعه حين يُعرف وإلا فلا سطر. **لا حقلَ مدينةٍ في أيِّ
   حمولة**، ومدينةٌ تُخمَّن من إحداثيّةٍ حسابٌ في الجهاز.
3. **«المستوى 3»** → من `GET /drivers/me/progress`، **و`enabled: false` تُسقط
   السطرَ كلَّه**: «المستوى ٠» رقمٌ لا وجودَ له في سوقٍ لا يشغّل المهامّ.

### و«أعِد الرحلة» تنسخ الوجهةَ وحدَها

**ثلاثةٌ لا تُنسخ**: نقطةُ الانطلاق (أين هو **الآن** لا أين كان)، والأجرةُ
(تُحسب لحظتَها، والقديمةُ تعريفةُ يومها)، والمحطاتُ الوسيطة (مسارٌ يُعاد
بمحطاتٍ لم يطلبها **أغلى بلا إذنه**). **ومنها إلى ورقة التأكيد لا إلى طلبٍ
يُرسل بلمسة.**

---

## حارسٌ صاح على مرآةٍ صادقةٍ لأنها لم تكن في بيتها (قِيس 2026-08-30)

**`check:enums` قال إن `VerificationMethod` فيها ثلاثُ قيمٍ مخترعة** —
`firebase` و`sms_otp` و`whatsapp_otp`. **وهي مرآةٌ صادقةٌ حرفاً**: القيمُ
الأربعُ عقدٌ منشورٌ في `/config` يقرؤه التطبيقان.

**والعلّةُ أنها كانت ثوابتَ وحدةٍ في `services/verification.py` لا تعداداً في
`models/enums.py`** — **والحارسُ لا يقرأ إلا هذا الملفّ**، فما لا يراه يقرؤه
اختراعاً.

**والعلاجُ لم يكن إعلانَها في `UI_UNIONS`** — **وذلك كان سيكون كذباً**:
الإعلانُ هناك **تصريحٌ بأنها واجهةٌ لا مرآةُ عقد**، وهي مرآةُ عقدٍ بحقّ.
**فصارت `StrEnum` في بيتها، ويشتقّ `verification.py` ثوابتَه منها** — القيمُ
هي هي حرفاً، فلا مقارنةَ تتبدّل ولا سلكَ يتغيّر، **والتعدادُ يجعلها مرئيّةً لا
يبدّلها**.

> **والدرسُ أعمُّ من الحادثة**: **حارسٌ يصيح على سليمٍ يُطفأ، فيسقط معه ما
> يمسكه حقاً.** وحين يصيح، **السؤالُ الأولُ «أهو مخطئٌ أم أعمى؟»** — والأعمى
> يُعالَج بأن يُوضع ما يقيسه حيث يراه، **لا بأن يُستثنى منه**.

---

## وموضعُ بناء العنوان بيتٌ واحد: `endpoints.ts` (2026-08-30)

`PromoBanners` كانت تبني `${API_URL}${banner.image_url}` بيدها — **فقفزت فوق
`check:contract`** الذي يسأل «أثمّة بابٌ يخدم هذا المسار؟». **والحارسُ أمسكها**.

**فنزلت `mediaUrl(path)` في `endpoints.ts` في التطبيقين**، حيث تسكن
`locationBroadcastUrl` أصلاً. **وحين ينتقل الوسيطُ إلى مضيفٍ آخر يُبدَّل سطرٌ
واحد** — لا كلُّ مكوّنٍ يعرض صورة.
<!--/جديد-->

<!--جديد-->

## وجهٌ سادسٌ لعائلة الحاوية: `restart` يحفظ **الأمر** لا الصورةَ وحدَها (قِيس 2026-08-30)

**قِيس بالعين على جهاز التطوير، وكلّف جولةَ قياسٍ كاملة.** الشاشتان بُنيتا،
والملفُّ في الحاوية صحيحٌ حرفاً (`grep -c CaptainHome` أجاب ٢)، **والمتصفّحُ
يرسم الشاشةَ القديمة**.

**والسببُ ليس المِرآةَ ولا inotify**: `docker compose ps` قال إن الخدمةَ
تعمل، **و`ps` داخل الحاوية قال ما لا يقوله أيُّ ملفّ**:

```
1  npm exec vite preview --host 0.0.0.0 --port 5174
```

**`vite preview` يخدم `dist`** — لا `vite dev` الذي يكتبه `docker-compose.yml`.
حاويةٌ أُقلعت في جولةِ هاتفٍ سابقةٍ بأمرٍ آخر، **و`restart` يعيد تشغيل الأمرِ
الذي أُنشئت به**، فبقيت تخدم بناءَ ذلك اليوم شهراً.

> **وهو أخو «`restart` يبقي الصورةَ القديمة»** المكتوب في `CLAUDE.md` — **وهذا
> أخفى**: هناك تنقص حزمةٌ فتنفجر بخطأ، **وهنا تُخدَم صفحةٌ كاملةٌ صحيحةُ
> الشكل**، **وكلُّ شيءٍ أخضر**. **والعلاجُ `up -d --force-recreate` لا
> `restart`.**
>
> **والسؤالُ الذي يكشفه**: لا «أهي تعمل؟» بل **«أيَّ أمرٍ تشغّل؟»** — و`ps`
> داخلَها هو الجواب، **لا ملفُّ compose**.
>
> **⚠ وتصحيحٌ في اليوم نفسِه قبل أن يُقرأ خطأً**: `preview` **ليس عطباً في
> ذاته**. `docker-compose.tunnel.yml` **يستبدل `command:` قصداً** — حارسا
> الواجهة يقرآن `backend/app` والحاويةُ لا تحمله، **فتبني أنت على المضيف
> وتخدم هي `dist`**. فالحاوياتُ الثلاثُ كانت في **وضع النفق** لا في عطب.
>
> **والعطبُ الحقيقيُّ أدقُّ**: أُقلعت بطبقةٍ ثمّ نُوديت بلا ملفّها، **فبقيت في
> وضعٍ لا يصفه الأمرُ الذي يُنادى به**. وهو حرفاً «كلُّ أمرِ compose يذكر
> ملفاتِه كلَّها صراحةً» — **في الاتجاهين**: من نسيه عند الإقلاع أقلع غيرَ ما
> ظنّ، ومن نسيه عند الإصلاح **كسر وضعاً سليماً**.

### ومعه فخُّ `localhost` على ويندوز: اسمان لخادمين

**نفس الجولة**: مِنفذُ 5174 كان محجوزاً مرّتين — Docker على `0.0.0.0` (IPv4)،
**وعمليةٌ على المضيف على `[::1]`** (IPv6). **وويندوز يحلّ `localhost` إلى
`::1` أوّلاً**، فكان كلُّ قياسٍ يذهب إلى **الخادم الخطأ** — وهو يخدم حزمةً
تخاطب `dev-api.tajora.ly` لا `127.0.0.1:8001`.

**فالقياسُ يُوجَّه إلى `127.0.0.1` صراحةً**، **و`netstat -ano | grep :المنفذ`
يُقرأ قبل أن يُتَّهم الكود**: **سطران لمنفذٍ واحدٍ يعنيان خادمين لا خادماً**.

---

## وثلاثةُ مقاصدَ كُتبت عن ظهر قلبٍ في يوم بنائها (قِيس 2026-08-30)

`SERVICE_DESTINATIONS` كُتب من الذاكرة لا من جدولَي المسارات، **فحمل
`/missions` و`/withdrawals` و`/bookings`** — والمبنيُّ `/account/missions`
و`/wallet/withdrawals` و`/account/bookings`. **وبُذرت بلاطةُ كبتنٍ تشير إلى
مسار الراكب**، فيقع على `path="*"`.

**وأدوارُ القاموس كانت مكتوبةً لا يقرؤها أحد**: `require_destination` سأل
«أهذا في القائمة؟» ولم يسأل «أعند من يراه؟». **وصُحّح الاثنان**، وبُني
`check:destinations` — **وتفصيلُه في `GUARDS.md`**.
<!--/جديد-->

<!--جديد-->

## قرار: المهامُّ تُوسَّع في بيتها — نافذةٌ وفرادةٌ وجائزتان (قرارُ المالك 2026-08-30)

**كُتب متأخّراً، والتأخيرُ نفسُه هو البند**: قيل في محادثةٍ ولم يُكتب لحظتَه،
**فطُويت الجلسةُ وكاد يضيع**. وهو حرفاً ما تحذّر منه قاعدةُ «ما لم يُكتب في
ملفٍّ لم يحدث» — **والتأجيلُ هو بعينه ما يُضيّع القرار**.

### أوّلاً — بيتٌ واحدٌ وترحيلةٌ واحدة، لا بيتٌ ثانٍ

**تُوسَّع `missions` نفسُها.** جدولُ «تحدّياتٍ» ثانٍ بجانبها **بابان لشيءٍ
واحد** (الشكلُ الثامن): كلاهما يعدّ رحلاتٍ في مدّة، **ويفترقان أوّلَ يومٍ
يُضاف معيارٌ لأحدهما**.

### ثانياً — النافذةُ تاريخان من اللوحة، لا شهرُ تقويم

`month: Date` **يفترض أن كلَّ تحدٍّ شهرٌ كامل**، **وتحدّي أسبوعٍ لا يُكتب فيه
أصلاً**. فيصير `starts_at` و`ends_at` **يضبطهما المشرف**.

**والنافذةُ تبقى بتوقيت الدولة** — قاعدةُ «يومِ الدولة» في `stats.py`: كبتنٌ
أنهى رحلتَه في الحادية عشرة ليلاً في آخر يومٍ **يُحرم منها بلا سبب** لو قِيست
بـUTC.

### ثالثاً — الفرادةُ بالتداخل لا بالشهر

`UNIQUE(country, month, metric)` كان يمنع هدفين لمعيارٍ واحدٍ في شهر. **وبتاريخين
حرّين تسقط الحيلة**: نافذتان تتداخلان بيومٍ واحدٍ تعيدان السؤالَ بجوابين.

**فالقيدُ صار منعَ تداخل**: `EXCLUDE USING gist` على
`(country_code =, metric =, daterange(starts_at, ends_at) &&)`.
**وهو قيدُ قاعدةٍ لا شرطٌ في الخدمة** — والشرطُ في الخدمة يمرّ عليه كاتبان
متزامنان.

### رابعاً — الجائزةُ **نوعان مُصرَّحان**: مستوىً أو سِمةُ مركبة

`reward_kind ∈ {level, vehicle_skin}` — **ولا نوعَ ثالثٌ ضمنيّ**.

- **`level`**: ما هو مبنيٌّ اليوم — الإنجازُ يرفع المستوى.
- **`vehicle_skin`**: يمنح سِمةً من `vehicle_skins`، **وهي مالٌ عيني** —
  تُشترى بمالٍ في المتجر، **فمنحُها مجاناً يمسّ ما يبيعه المتجر**.

### والأربعةُ على مسار السِمة — **وهي اقتراحي لا قولُه، وتُعرض عليه**

1. **لا سِمةَ إلا موجودةً ومشتعلة**: `reward_skin_id` مفتاحٌ أجنبيٌّ على
   `vehicle_skins`، **ويُرفض المطفأُ عند الكتابة لا عند المنح** — ومهمّةٌ
   جائزتُها سِمةٌ مسحوبةٌ **تَعِد بما لا يُسلَّم**.
2. **ومهمّةٌ بجائزةِ سِمةٍ لا تُنشر بلا سِمة**: قيدُ قاعدةٍ
   `reward_kind <> 'vehicle_skin' OR reward_skin_id IS NOT NULL` — **من عائلة
   «بلاطةٌ فعّالةٌ بلا مقصد»** نفسِها.
3. **والمنحُ مرّةً واحدةً لكلِّ كبتن**: يُكتب في `driver_vehicle_skins` بمفتاح
   تفرّدٍ `(driver_id, skin_id)`، **وإعادةُ حساب الإنجاز لا تمنح ثانيةً**.
   **والقفلُ على صفِّ الكبتن قبل الكتابة** — لا مفتاحُ تعطيلٍ وحدَه، فهو
   «حارسٌ يعمل لأن الذي خلفه عمل».
4. **ولا تُفعَّل تلقائياً**: تُمنَح مملوكةً **ويختار صاحبُها متى يلبسها** —
   **وتبديلُ مظهرِ مركبته دونه تمييزٌ مرئيٌّ لم يطلبه**، وهو الشكلُ الثالثَ عشر.

**وخامسةٌ تُقال ولا تُبنى حارساً**: منحُ سِمةٍ **لا يكتب قيداً في الدفتر** —
لا مالَ تحرّك، **والسِمةُ ليست رصيداً**. ولو صارت تُشترى وتُباع بين الكباتن
يوماً فذاك دفترٌ آخرُ يُفتح بقراره.

### وما لم يُبنَ بعد

**البند مكتوبٌ والبناءُ لم يبدأ** — ويبدأ من الترحيلة. **ولا يُقرأ هذا البندُ
حالاً قائمة**: هو قرارٌ مسجَّل، **و`missions` اليوم ما زالت بـ`month` وقيدِ
الشهر**.
<!--/جديد-->

<!--جديد-->

## بنودٌ من جولة النفق 2026-08-30 — رُئيت ولم يُوقَف لها

1. **`JAVA_HOME` يشير إلى JDK 17 و`assembleTrialDebug` يطلب 21.** فسقط البناءُ
   برسالةٍ تسمّي ما نقص — **وهي رسالةٌ صادقة**. والجاهزُ على الجهاز هو JBR
   المرفقُ بـAndroid Studio (`21.0.8`)، فبُني به صراحةً:
   `JAVA_HOME="C:\Program Files\Android\Android Studio\jbr" ./gradlew …`.
   **ولم يُغيَّر `JAVA_HOME` في النظام** — تغييرُ متغيّرِ بيئةٍ عامٍّ لأجل بناءٍ
   واحدٍ يمسّ كلَّ أداةٍ أخرى على الجهاز بلا أن يعرف أحد.

2. **حزمتا التجربة موقَّعتان بمفتاح `Android Debug`** — بصمةٌ واحدةٌ للاثنتين
   (`5686172807c0…`). **وهو المقصود في `assembleTrialDebug`**، ولا يُقرأ توقيعَ
   نشر. **والقياسُ من داخل الحزمة لا من مخرَج التثبيت**: `apksigner verify
   --print-certs` و`aapt2 dump badging` و`capacitor.config.json` **المقروءُ من
   داخل ملفّ الـAPK نفسِه**.

3. **وحسابُ «زيد» على جهاز التطوير كان `pending`** — ستُّ صورِ مركبةٍ منتظرةُ
   مراجعة. اعتُمد على قاعدة **التطوير** ليُبلَغ إلى الرئيسية، **ولم يُمسّ
   إنتاج**.
<!--/جديد-->

<!--جديد-->

## حزمةٌ على هاتفٍ لم تُبنَ على هذا الجهاز — كشفها التوقيعُ لا الرقم (قِيس 2026-08-30)

`adb install -r` سقط على Note 20 بـ`INSTALL_FAILED_UPDATE_INCOMPATIBLE`:
**توقيعُ المثبَّت لا يطابق توقيعَ الجديد.**

**والسببُ ليس مفتاحاً تبدّل**: `~/.android/debug.keystore` على هذا الجهاز
**بتاريخ ٢٠٢٥-١٢-١٩ لم يُمسّ**. **فالمثبَّتُ هو الغريب** — `versionCode=405`
موقَّعٌ بـ`3bdc7391…`، وبناءُ اليوم بـ`56861728…`.

> **⚠ وتصحيحٌ في اليوم نفسِه — الاستنتاجُ الأوّلُ كان خطأً.** كُتب هنا أوّلاً
> «أي أن حزمةَ أمسٍ بُنيت على جهازٍ آخر»، **وهو تخمينٌ لا قياس**.
>
> **والقياسُ جاء من حيث لا يُنتظر**: عند قراءة حزمة `v0.2.2` المنشورة على
> صفحة التحميل، **كانت بصمةُ موقِّعها `3bdc7391…` نفسَها** — واسمُ الشهادة
> `CN=mohammed aldeeb, OU=TAXO, O=sbonge`. **فهي مفتاحُ الإصدار**، لا مفتاحُ
> تصحيحٍ على جهازٍ غريب.
>
> **فما كان على Note 20 حزمةٌ تجريبيةٌ موقَّعةٌ بمفتاح الإصدار** — من إصدارِ
> CI، لا من `assembleTrialDebug` محلّيّ. **والتعارضُ كان بين مفتاح الإصدار
> ومفتاح التصحيح**، وهو متوقَّعٌ تماماً ولا غرابةَ فيه.
>
> **والدرسُ الباقي على حاله**: `versionCode` لا يقول من بنى، **والتوقيعُ
> يقول**. **والدرسُ المضاف**: توقيعٌ لا أعرفه ليس «جهازاً غريباً» حتى أقرأ
> الشهادةَ نفسَها — **واسمُ الشهادة كان يجيب في سطرٍ واحد، ولم أقرأه**.

> **وهو أنفعُ مما يبدو**: `versionCode` وحدَه **لا يقول من بنى**. رقمان
> متتاليان يُقرآن «تحديثٌ طبيعيّ»، **والتوقيعُ وحدَه يقول إن المصدرَ تبدّل**
> — وهو أخو «تساوي الأعداد ليس تساوي الأسباب».
>
> **ولذلك يُقرأ من داخل المثبَّت لا من مخرَج التثبيت**: `Success` سطرٌ لا
> يحمل معرّفاً ولا رقماً ولا توقيعاً. **والقياسُ الصادق**: `pm path` ثمّ
> `adb pull` ثمّ قراءةُ الحزمة المسحوبة — **وبصمتُها تُقارَن بالمبنيّ**.
> وقد طابقت اليومَ إلى الحرف: `9f657064…` و`88efbe5a…`.

**وما ضاع بالإزالة**: جلسةُ دخولٍ ومفاتيحُ صوتٍ في تطبيق **تجريبيّ** — تُستعاد
بتسجيل دخولٍ واحد، **ولا فريدَ فيها**. وقِيس ما كان قبل الإزالة وكُتب هنا.
<!--/جديد-->

<!--جديد-->

## توسيعُ بطاقة الخريطة — زيادةٌ على التصميم، وصنفٌ لا وجودَ له أمسكته نقرة (2026-08-30)

**قُرئ التصميمان قبل البناء والجوابُ صريح**: **لا توسيعَ في أيٍّ منهما** —
بطاقةُ ١٧٠ فيها شارةٌ وزرٌّ في القاع، لا أكثر. **فهي زيادةُ المالك**، وكُتبت
في README المجلَّدين بعلّتها كما كُتبت الأربعُ قبلها.

**وتنطبق على الشاشتين**: البطاقتان **الشكلُ نفسُه**، فحدُّ التوسيع واحدٌ
ومكوّنٌ واحدٌ يخدمهما. **والفرقُ الوحيد** أن للكبتن سطرَ حالٍ يظهر موسَّعةً،
**وللراكب لا حالَ عملٍ تُقرأ** — وسطرٌ يُخترع له ليُشبه شاشةَ الكبتن يقول ما
لا معنى له.

### والمقاسُ يخصّ من يملك اللوحة

`mapbox-gl` يقيس مقاسَه **مرّةً عند البناء**، فبلا مراقبِ مقاسٍ تبقى اللوحةُ
١٧٠ بكسلاً داخل حاويةٍ ملءَ الشاشة. **فنزل `ResizeObserver` في `MapView`
نفسِه** لا في البطاقة: **من يملك اللوحةَ هو من يعيد قياسَها** — وأيُّ حاويةٍ
تتبدّل غداً تجد الجوابَ مبنيّاً، **ولا يُكتب الإصلاحُ مرّتين**.

### وصنفٌ لا وجودَ له صُرِّف بلا أثرٍ ولا خطأ

أوّلُ نسخةٍ وضعت زرَّ الإغلاق على **`top-safe`** — **وهو ليس في هذا المشروع**:
الموجودُ `pt-safe` و`pb-safe` **حشوةً لا إزاحة**. فلم يحمل الزرُّ `top` أصلاً،
وسقط إلى موضعه الساكن **خارج الشاشة**.

> **ولم يمسكه حارس**: `check:scale` يقرأ السلالمَ الرقمية لا هذه، **وقد مرّ
> أخضرَ عليه** — وهو الفخُّ نفسُه المكتوب عند `warn-soft` في `Home.tsx`.
> **ولم يُكتشف إلا بنقرةٍ حقيقيةٍ فشلت**: «فحصُ الشكل ليس قياسَ السلوك».
>
> **والقياسُ الذي كشفه لم يكن لقطةً**: `boundingBox()` للوحة قبل النقرة وبعدها.
> **ولقطةٌ كانت ستُظهر خريطةً ملءَ الشاشة وتُقرأ نجاحاً** — والزرُّ خارجها.

### وقِيس بالعين على dev عبر `dev-*` — الدورةُ كاملةً

| | مطويّة | موسَّعة | بعد الإغلاق |
|---|---|---|---|
| الكبتن | 356×168 | **390×844** | 356×168 |
| الراكب | 356×168 | **390×844** | 356×168 |

**وشارةُ التوسيع ظهرت وعادت، وزرُّ الإغلاق ظهر وأغلق، وحالُ الاستقبال قُرئت في
الحالين.**

### وشارةٌ في التصميم لم تُبنَ، بعلّتها

تصميمُ الكبتن يرسم في أعلى البطاقة **«الطلب مرتفع في منطقتك»**. **ولم تُبنَ**:
**لا شيءَ في النظام يقيس ارتفاعَ الطلب** — لا عدّادَ طلباتٍ في نطاق، ولا نسبةَ
كباتنَ إلى طلبات. **وشارةٌ تقول ذلك بلا قياسٍ وعدٌ يعدّه الكبتنُ ولا يجده**،
ويخرج ليعمل على كلامٍ لا سند له. **فتُترك حتى يُبنى ما يقيسها.**
<!--/جديد-->

<!--جديد-->
## جولةُ اللوحة — تمّت الخلفيةُ واللوحة (٢٠٢٦-٠٨-٣١، الجلسة الثانية)

**الترحيلةُ `0064` شُغِّلت على قاعدة التطوير** — والأعمدةُ الثلاثةُ قائمةٌ
مقيسةً (`\d service_tiles` و`\d promo_banners`): `first_shown_at` على الجدولين
و`image_path` على اللافتة. **و`test_migrations` خضراء** (٣ اختبارات، ٣٥ ثانية)
— **وفيها دورةُ `downgrade base → upgrade head`**، فنزولُ `0064` مقيسٌ لا مقروء.

### البنودُ الثلاثةَ عشر — حالُها الآن

| # | البند | الحال |
|---|---|---|
| 1 | `0064` | ✅ **شُغِّلت ومقيسة** |
| 2 | العمودان في النموذجين | ✅ |
| 3 | `SERVICE_ICONS` و`require_icon` | ✅ **موصولان بالأبواب الأربعة** |
| 4 | `stamp_if_shown` · `require_draft` | ✅ **موصولان** |
| 5 | ربطُ الثلاثة بالراوتر | ✅ |
| 6 | بابا الحذف — للمسوّدة وحدَها | ✅ |
| 7 | `GET /admin/settings/service-icons` | ✅ |
| 8 | رفعُ صورة اللافتة وخدمتُها وعرضُها | ✅ **بالأربعة معاً** |
| 9 | تحريرُ الصفّين (٧ حقولٍ و٩) | ✅ |
| 10 | `audience` في الإنشاء | ✅ **ومعه حارسُه** |
| 11 | منتقي الأيقونات | ✅ |
| 12 | المعاينةُ بالبطاقة نفسِها + حارسُ بصمة | ✅ |
| 13 | حارس «حقلٌ بلا زرّ» | ✅ `check:fields` |

**وزِيد على الثلاثةَ عشر بندٌ لم يكن فيها**: `GET /admin/settings/service-destinations`
ومنتقي المقصد. **وعلّتُه علّةُ الأيقونة نفسُها**: الحقلُ كان نصّاً حرّاً،
**فمسارٌ يُكتب بيدٍ يُرفض في الباب** والمشرفُ كتب شيئاً معقولاً ولا يعرف لمَ
مُنع. **والأدوارُ تُنشر معه** فلا يُعرض للكبتن مقصدُ راكب.

### وثلاثةُ عطبٍ قِيست على الطريق — اثنان كانا يستران بعضهما

**١) `PUT /admin/settings/payments/{country}/cliq-qr` لم يعمل قطّ.**
`setting.cliq_qr_path = stored.path` — **و`StoredFile` لا تحمل `path` أصلاً**
(كلُّ مستدعٍ آخرَ في المشروع يكتب `relative_path`). فكان البابُ يرمي
`AttributeError` **بعد كتابة الملفّ على القرص**: ٥٠٠ للمشرف، **وملفٌّ يتيمٌ لا
صفَّ يشير إليه**. **ولا اختبارَ كان يطرق هذا الباب.**

**٢) وتحته عطبٌ ثانٍ كان الأولُ يستره**: بعد إصلاح السطر سقط الباب بـ
`MissingGreenlet` على `updated_at` — يُحسب في SQL بـ`onupdate` **فيبقى منتهياً
بعد الإيداع**، والمخطَّطُ يقرؤه خارج السياق. **ولم يظهر يوماً لأن السطرَ قبله
كان يرمي قبل أن يبلغه.** العلاجُ `_commit(session, setting)` — وهو الشكلُ
المسجَّل: **عطبان يستر أحدهما الآخر يعيشان أطولَ من عطبٍ مفرد.**

**٣) و`stamp_if_shown` كانت تترك ثقباً في اللافتة**: كانت تختم على `is_active`
وحدَها. **والسؤالُ لحظةَ الإشعال ليس «أتُعرض الآن؟» بل «أستُعرض بعدُ؟»** —
لافتةٌ تُشعَل قبل نافذتها **تُعرض حتماً حين تفتح** ولو لم يُلمس صفُّها ثانيةً،
**فتبقى تُقرأ مسوّدةً تُحذف وهي على شاشات الناس**. صار الشرطُ: مشتعلةٌ
**ونافذتُها لم تنتهِ** — **وميلُ الخطأ مقصود**: ختمٌ زائدٌ يمنع حذفاً
والإخفاءُ بديلٌ قائم، **وختمٌ ناقصٌ يأذن بمحو صفٍّ رآه الناس**.

### وأوّلُ اختبارٍ لهذين الجدولين

`backend/tests/test_storefront.py` — **٢١ اختباراً، ولم يكن لهما اختبارٌ واحدٌ
قبل اليوم**: بُنيا في جولتين وشُحنا، **والخضرةُ كانت خضرةَ ما لم يُقَس**.
ويقيس: قائمةَ الأيقونات ورفضَ ما خارجها في الأربعة، والختمَ في حالاته الستّ
(بما فيها اللافتةُ قبل نافذتها وبعدها)، والحذفَ للمسوّدة ورفضَه لما عُرض،
ودورةَ الصورة كاملةً **مع شرط السوق** (راكبٌ أردنيٌّ يُمنع من لافتة ليبيا،
وبابُ اللوحة لا يسأل)، وكنسَ الملفِّ القديم عند الاستبدال وعند حذف الصفّ،
والمصفاةَ العامّة، وانحدارَ `cliq-qr`.

### ⚠ وما لم يُقَس — ولا يُقرأ سلامة

**لم تُفتح شاشةُ اللوحة في متصفّح.** حسابُ مشرف التطوير يطلب TOTP، **والرمزُ
بيد المالك** — فما قِيس هو المجموعةُ والحرّاسُ و`tsc`، **لا DOM ولا نقرة**.
**وجولةُ اللوحة تحتاج فتحةً واحدةً من المالك**: منتقي الأيقونات، والمعاينة،
وزرّا الحذف، ورفعُ صورةٍ ونزعُها.
<!--/جديد-->

<!--جديد-->
## FastSpring — قراءةُ شروطها للثلاثة (٢٠٢٦-٠٨-٣١) — **ولا حكمَ واحدٌ عليها**

**النصُّ الحاكم**: `https://fastspring.com/terms-use/` — قسمُ **«Restricted
Business Types»**، ومطلعُه: *«Due to restrictions from credit card processors
and our own internal standards, certain business types are not allowed to sell
their products, goods or services via FastSpring.»* وفيه **٢٦ بنداً**.
ومعه `https://fastspring.com/terms-use/seller-terms-service/` §4.5 (قائمةٌ
أقصر: بالغون، تبغ، أدوية، ميسر، كراهية، **third-party processing**).

### ١) اشتراكُ الكبتن — **مقبول**

**ليس في البنود الستّةِ والعشرين ما يمسّه**: خدمةٌ رقميّةٌ متكرّرةٌ يبيعها
صاحبُها لمستخدمه، وهي صلبُ ما تبيعه FastSpring. **وتعريفُ «Product» في §2 من
عقد البائع يسعها**: *«(i) a product and/or (ii) any access to content,
software-as-a-service or other service»*.

> **⚠ والبندُ الوحيدُ الذي قد يُشهر عليه بندُ ٢٥**: *«Aggregators, including
> but not limited to marketplaces, platforms, Staged Digital Wallet Operators
> or Payment service companies, including but not limited to peer-to-peer,
> bill payments, commissary accounts»*. **وقراءتي أنه في تجميع المدفوعات
> لحساب الغير لا في بيع المرء اشتراكَه لمستخدمه** — **لكنّها قراءةٌ لا نصّ**،
> وTAXO منصّةٌ باسمها. **ومن يحسمها مراجعةُ FastSpring عند التسجيل لا أنا.**

### ٢) شحنُ المحفظة — **تمنعه، ببندين لا بند**

**البند ٢٠**: *«Provider or seller prepaid access/stored value»*.
**والبند ١٦**: *«E-wallet or e-money that can be monetized, re-sold or
converted to physical and digital goods and services or otherwise exit the
virtual world»*.

**ومحفظةُ TAXO هي هذا بحرفه**: قيمةٌ مخزَّنة (`wallet_transactions`) يشحنها
الراكبُ ثمّ **تُصرف لاحقاً في خدمة نقل** — أي تخرج من العالم الرقميّ إلى خدمةٍ
واقعية. **فلا يُبنى.**

### ٣) سدادُ الدَّين — **لا يُبنى، ولسببين**

**الأول نصّيّ**: **البند ١٥** *«Debt repayment and collection agency»*،
و**البند ٢٥** يذكر **`bill payments`** صراحةً — وسدادُ الكبتن ما عليه هو
«bill payment» بعينه في عين شبكة البطاقات.

> **وحدُّ ما وجدتُه مكتوب**: نصُّ البند ١٥ يقول **«agency»** — **ولم أجد في
> الوثيقة بنداً يسمّي «منصّةً تحصّل مستحقّها على مستخدمها»**. فقراءتي أنها
> داخلةٌ في ١٥+٢٥، **وهي قراءةٌ لا نصّ**، وأقولها كذلك.

**والثاني بنيويٌّ لا يحتاج نصّاً**: **أيُّ منتجٍ يُسجَّل مقابله؟** لا شيء
يُسلَّم — الدَّينُ التزامٌ قائمٌ يُطفأ. **وبائعُ السجلّ يبيع منتجاً باسمه
ويصدر فاتورةً به**، فتسجيلُ «سداد دَين» منتجاً رقميّاً **يصف المعاملةَ بغير
ما هي** أمام الضريبة والمصدِّر معاً.

### وأربعةٌ سألتَ عنها

| السؤال | الجواب المقروء | مصدرُه |
|---|---|---|
| **الدينار الأردنيّ** | **غيرُ مدعوم** — لا في عملات العرض (٣٨) ولا في عملات الصرف (٦: USD·EUR·GBP·AUD·CAD·JPY). فالكبتنُ يُحاسَب بعملةٍ أخرى **وفرقُ الصرف على كلِّ عملية** | `developer.fastspring.com/docs/currencies-and-conversions` |
| **هامشُ الصرف** | **٣٫٥٪** فوق سعر السوق للعملات الكبرى، **٥٫٥٪** لما عداها حين تُحوَّل الأسعارُ آلياً · **و٢٫٥٪** حين تختلف عملةُ المتجر عن عملة الصرف | نفسُه، و`docs/receive-payouts` |
| **متى يصل المال** | **الـ١٥ ونهايةَ الشهر** افتراضاً · **تأخيرُ تسويةٍ ١٤ يوماً على كلِّ معاملة** · **وحجزُ مراقبةٍ ٤٥ يوماً على الحساب الجديد** · وحدٌّ أدنى **١٠٠ دولار** يُرحَّل ما دونه · والطرق: PayPal · Venmo · حسابٌ بنكيّ · شيك · **حوالةُ SWIFT** · MoneyGram — **وPayoneer غيرُ مدعوم** | `docs/receive-payouts` · `docs/set-up-your-payout-account` |
| **الاسترداد** | بابُها هي: من لوحتها أو من واجهتها البرمجية · جزئيٌّ مدعوم · والمهل: **٦ أشهر** بطاقة · **٣ أشهر** PayPal · **٦٠ يوماً** UPI · **وتحتفظ برسم المعاملة في الاسترداد الكامل** | `docs/refund-an-order` |
| **النسبة** | **لم أجد رقماً منشوراً**. صفحةُ التسعير تقول: *«FastSpring's team will work with you to determine simple, flat-rate pricing based on transaction type and your volume»* — **فالرقمُ لا يُعرف إلا منهم** | `fastspring.com/pricing` |
| **الردُّ العكسيّ** | FastSpring هي بائعُ السجلّ ومسؤولةُ المراقبة، **لكنّ المبلغَ المتنازَعَ عليه يُسحب من صرفك فوراً** ويُحتجز حتى يفصل البنك | `docs/chargebacks-and-disputes` |

**ولم أجد**: قائمةَ الدول المدعومة لاستلام الصرف — **فلا أقول إن الأردن
مدعوم**؛ يُسأل عنه FastSpring.

### ⚠ وملفُّ اعتمادٍ في جذر المستودع

`fastspring.txt` **غيرُ متعقَّبٍ وغيرُ مستثنى في `.gitignore`** — فـ`git add -A`
يودعه. **ولم يُحذف ولم يُنظَّف** (تنظيفُه يخفي أنه كان هناك)، **ولم يُودَع**.
**ومكانُ بيانات الاعتماد `provider_credentials` مشفَّرةً من صفحة العقود**، لا
ملفٌّ في الشجرة (SPEC §14 والثابتُ المسجَّل).
<!--/جديد-->

<!--جديد-->
## FastSpring — **قُرئت ورُفضت** (قرارُ المالك 2026-08-31)

**لا تُبنى: لا الاشتراكُ ولا غيرُه.** ولا يُعاد فتحُها بـ«لعلّها تصلح» — هذا
البندُ هو الدراسة، **فمن قرأه فقد قرأها**.

**والاثنان ممنوعان بنصِّهم** في قسم **«Restricted Business Types»** من
`https://fastspring.com/terms-use/` (٢٦ بنداً، ومطلعُه: *«Due to restrictions
from credit card processors and our own internal standards, certain business
types are not allowed to sell their products, goods or services via
FastSpring.»*):

- **شحنُ المحفظة** — البند ٢٠: *«Provider or seller prepaid access/stored
  value»*؛ والبند ١٦: *«E-wallet or e-money that can be monetized, re-sold or
  converted to physical and digital goods and services or otherwise exit the
  virtual world»*. **ومحفظةُ TAXO هي هذا بحرفه**.
- **سدادُ الدَّين** — البند ١٥: *«Debt repayment and collection agency»*،
  والبند ٢٥ يذكر **`bill payments`**. **ومعه سببٌ بنيويٌّ لا يحتاج نصّاً**:
  لا منتجَ يُسجَّل مقابله — الدَّينُ التزامٌ يُطفأ لا شيءٌ يُسلَّم، **وبائعُ
  السجلّ يُصدر فاتورةً باسمه بمنتج**.

**والاشتراكُ كان مقبولاً في نصِّها** (ليس في البنود ما يمسّه، و§2 من عقد
البائع يسع «any access to content, software-as-a-service or other service»)
— **ورُفض بالأرقام لا بالنصّ** (قرارُ المالك):

| ما وُجد | الرقم | مصدرُه |
|---|---|---|
| الدينارُ الأردنيّ | **غيرُ مدعومٍ في العرض ولا في الصرف** — الصرفُ بستٍّ فقط: USD·EUR·GBP·AUD·CAD·JPY | `docs/currencies-and-conversions` |
| هامشُ الصرف | **٣٫٥٪** للكبرى · **٥٫٥٪** لما عداها · **٢٫٥٪** عند اختلاف عملة المتجر عن الصرف | نفسُه · `docs/receive-payouts` |
| النسبة | **غيرُ منشورة** — *«FastSpring's team will work with you to determine simple, flat-rate pricing»* | `fastspring.com/pricing` |
| وصولُ المال | **١٤ يوماً تأخيرَ تسويةٍ على كلِّ معاملة** · دفعتان شهرياً (١٥ ونهايةَ الشهر) · **٤٥ يوماً حجزَ مراقبةٍ على الحساب الجديد** · حدٌّ أدنى ١٠٠ دولار | `docs/receive-payouts` |
| الردُّ العكسيّ | المبلغُ يُسحب من صرفك فوراً ويُحتجز | `docs/chargebacks-and-disputes` |
| الاسترداد | بابُها هي (لوحةً أو API)، جزئيٌّ مدعوم، **وتحتفظ برسم المعاملة** | `docs/refund-an-order` |

> **وحجّةُ الرفض بلفظ المالك**: «كبتنٌ يشترك بـ٤٥ يدفع بعملةٍ أخرى ويأكل
> الصرفُ منها **قبل عمولةٍ لا أعرفها** — **وسعرٌ لا أعرف كلفته لا أبني
> عليه**.»

**فيبقى Telr كما هو، وكليك اليدويُّ هو الطريقُ العاملُ اليوم.**

### والأربعةُ التي تُقاس بها أيُّ بوّابةٍ قادمة — **قبل سطرِ كود**

**تُسأل عن هذه الأربعة قبل أيِّ شيءٍ آخر، ورفضُ واحدةٍ يُسقط البوّابة**:

1. **أتقبل الدينارَ الأردنيَّ عرضاً وصرفاً؟** — لا عرضاً وحدَه: عرضٌ بلا صرفٍ
   يعني فرقَ صرفٍ على **كلِّ** عملية.
2. **أتسمح بالقيمة المخزَّنة؟** — شحنُ المحفظة هو الاستعمالُ الأكبر، **وبائعُ
   السجلّ يمنعه عادةً**. ويُقرأ نصُّها لا يُرجَّح.
3. **أنسبتُها منشورةٌ برقم؟** — «تُناقَش مع مندوب» تعني **سعراً لا تُعرف
   كلفتُه**، ولا يُبنى عليه سعرُ اشتراك.
4. **متى يصل المال؟** — تأخيرُ التسوية، ودورةُ الصرف، وحجزُ الحساب الجديد،
   والحدُّ الأدنى. **وبوّابةٌ فوريّةٌ ليست بائعَ سجلٍّ عادةً — والفرقُ في هذا
   السطر.**

> **والفرقُ الذي أنتج هذه الأربعة**: **بائعُ السجلّ ليس بوّابة.** هو يشتري
> منك ويبيع باسمه — **فيقرّر ما يُباع** (البنود)، **ويحمل المالَ قبلك**
> (التسوية)، **ويأخذ فرقَ العملة** (الهامش). والبوّابةُ تمرّر. فمن قارن
> نسبتَيهما وحدَهما قارن رقمين من جدولين.

## أبوابٌ لا يطرقها اختبار — **عدٌّ لا إصلاح** (قرارُ المالك 2026-08-31)

**العلّةُ**: `PUT /admin/settings/payments/{country}/cliq-qr` **لم يعمل قطّ**
منذ كُتب — وسطرٌ واحدٌ خاطئٌ بقي شهراً **لأن لا اختبارَ يطرقه**. فالسؤالُ:
كم بابٍ آخرَ كذلك؟

**قِيس 2026-08-31** (المِقياسُ في `scratchpad/count-untouched.mjs`):

| | الأبواب | لا يطرقها اختبار |
|---|---:|---:|
| **كلُّها** | 288 | **46** |
| **أبوابُ اللوحة** | 160 | **37** |

**وأثقلُها عائلاتٍ كاملة**: **النسخُ الاحتياطية بأبوابها الثمانية** — وهي
البوّابةُ الثالثةُ في الرفع، **فبابٌ لا يُطرق في ما لا رفعَ بدونه** ·
والمهمّاتُ والمستويات (٥) · ورموزُ الخصم (٤) · وإعداداتُ السلَف والإلغاء
والخريطة وOTP والتوزيع (١١) · و`POST /admin/providers/{id}/activate` ·
وجلسةُ واتساب وخروجُها · و`GET /subscriptions/cliq/qr` — **وهو شقيقُ الباب
الذي انكسر**.

> **وحدُّ العدد مكتوب**: **الطرقُ ليس القياس.** ظهورُ المسار في نصِّ اختبارٍ
> يثبت أنه **طُرق** لا أنه **قِيس** — **فـ٢٤٢ باباً «مطروقاً» ليست ٢٤٢ باباً
> مقيساً**. **والغيابُ وحدَه يقينيّ**: ما لا يظهر لم يُطرق قطعاً. فالرقمُ
> **حدٌّ أدنى للعطب لا جردٌ له**.

**ولم يُصلَح منها شيء** (قرارُ المالك): العدُّ أوّلاً.

**ومنها بابٌ كُتب اليومَ**: `GET /admin/settings/service-destinations` —
يُقرأ في اللوحة ولا يطرقه اختبار.
<!--/جديد-->

<!--جديد-->
## البريدُ قناةً بديلة — **الخلفيةُ والتطبيقان** (٢٠٢٦-٠٨-٣١)

**والبريدُ يُثبت البريدَ لا الهاتف** — وهذا هو التصميمُ كلُّه. **فلا يدخل
`available_methods` ولا `challenge` ولا `verify`**: ثلاثتُها تجيب سؤالاً
واحداً، «ما الذي يُثبت **ملكيةَ هذا الرقم**؟» — **ورمزٌ يصل صندوقَ بريدٍ لا
يثبت أن صاحبَه يملك الرقم**.

> **وإدخالُه هناك كان سيكون العطبَ بعينه**: بابٌ يُسمّى «إثباتَ رقم» ويقبل
> إثباتاً من قناةٍ أخرى — **فيُنشأ حسابٌ كاملُ الصلاحية برقمٍ لم يملكه أحد**،
> وهو ما بُني `otp_verification_enabled` ليمنعه. **ولا يُلتفّ عليه بقناةٍ
> ثالثة.** ويقيسه `test_email_is_never_a_phone_verifier`.

**فماذا يفعل إذاً**: **يفتح حساباً محدوداً** — بريدٌ مُثبَتٌ · ورقمٌ **محجوزٌ
لا مملوك** · **ولا رحلةَ ولا محفظة**. **وهو مخرجٌ لا التفاف**: حين تسقط
واتساب، من لا قناةَ له **لا يستطيع حتى أن يبدأ**.

### ما بُني

| | |
|---|---|
| **`0065`** | `email` · `email_verified_at` · `phone_pending` · و`ALTER TYPE provider_key ADD VALUE 'email'` بـ`COMMIT` صريحٍ كـ`0018`، **وكلُّ ما بعده يُعاد بلا ضرر** |
| **الفهرس** | `uq_users_email_verified` على `lower(email)` **حيث `email_verified_at IS NOT NULL`** — بلا حساسيةِ حالة، **وللمُثبَت وحدَه** |
| **العقد** | `ProviderKey.EMAIL` عامٌّ **بلا `feature_key`** كواتساب · و`services/email/` بعقدٍ مجرَّدٍ ومُرسِلٍ وهميّ |
| **المفتاح** | `email_otp_enabled` per-country **مطفأٌ بالسكوت** — **ولا يُشعَل بلا عقدٍ فعّال**، يرفضه `upsert_feature_flag` بنصّه |
| **الرمز** | يمرّ بـ`otp.issue` نفسِها — **فسقوفُه سقوفُ القنوات الأخرى**، ولا يشتري أحدٌ محاولاتٍ بتبديل القناة |
| **القالب** | من `otp_templates` بمدّةٍ **محقونةٍ** من `CODE_TTL_SECONDS` · **والموضوعُ وحدَه يُصاغ في `EmailCodeSender`** لأنه حقلٌ لا وجودَ له في القناتين الأخريين |
| **البابان** | `POST /auth/email/challenge` · `POST /auth/register/email` — **ولا بابَ دخولٍ بالبريد** |
| **الحدّ** | `require_owned_phone` في `rides.request_ride` (لا في الراوتر — **الحجزُ المجدول يمرّ من الباب نفسِه**) · و`topups.create_request` · و`wallet.transfer` **من طرفيه** |
| **الرفع** | `POST /auth/me/verify-phone` **نفسُه** يمسح `phone_pending` — **ولا بابَ ثالثٌ يُكتب له** |
| **التطبيقان** | `PhonePendingNotice` **في كلِّ فتحةٍ فوق البلاطات**، بلا زرِّ إغلاق: **حالٌ قائمةٌ لا خبر**، ومن أغلقه يبقى محدوداً ولا يرى لمَ |

### وعطبٌ قِيس أثناء البناء

**بريدٌ مُثبَتٌ مكرَّرٌ كان يعطي ٥٠٠**: الفهرسُ الفريدُ يمنع الازدواجَ **ولا
يقول شيئاً** — من اصطدم به قرأ خطأَ خادمٍ بلا سطرٍ يفهمه. **فصار الفحصُ في
`create_account` يعطي الرسالة (`EmailAlreadyRegistered`) والفهرسُ يبقى حارساً
للسباق** — طبقتان لا واحدة، **ومن اكتفى بالفحص فتح ثغرةَ تزامن**.

### ⚠ وما لم يُبنَ من البريد — بعلّته

**لا مُرسِلَ حقيقيَّ** (قرارُ المالك: لا يُلمس عقدُ Resend ولا يُرسل بريدٌ
حقيقيٌّ حتى إذنِه). **و`build_provider` يرفض بنصّه** أيَّ عقدٍ ليس وهميّاً —
**فمن أدخل عقداً حقيقيّاً اليومَ يقف ويُقال له لمَ**، ولا يمضي إلى مُرسِلٍ لا
وجودَ له. **وإضافتُه غداً ملفٌّ واحدٌ وفرعٌ في `build_provider`.**

**ولا شاشةَ تسجيلٍ بالبريد في التطبيقين**: البابان مبنيّان ومقيسان، **والشاشةُ
التي تناديهما لم تُرسم** — فالقناةُ تعمل من الخلفية ولا يبلغها إصبع. **وهي
أوّلُ ما يُبنى حين تُشعَل**، ولا تُشعَل بلا مُرسِل.

**ولم يُعَد تسميةُ `phone` في `otp.py` إلى `subject`** وهو يحمل عنواناً
بريديّاً الآن: المُعامِلُ نفسُه في `otp_limits`، **ومفاتيحُه في ٣٨ موضعاً**.
**وتبديلُ اسمٍ في ٣٨ موضعاً في الجولة التي تُضاف فيها قناةٌ فعلان يمسّان سطحاً
واحداً** — **فالدَّينُ مكتوبٌ بتاريخه في رأس `otp.issue`**، ويُقضى في جولةٍ لا
شيءَ فيها غيرُه.
<!--/جديد-->

<!--جديد-->
## حملةُ تأكيد الأرقام — **بُنيت ولم تُطلق** (٢٠٢٦-٠٨-٣١)

**وقُرئ الإنتاجُ أوّلاً كما أمر المالك** (قراءةٌ خالصةٌ بـ`SELECT` لا غير):

| الدور | الحسابات | رقمُه غير مؤكَّد |
|---|---:|---:|
| راكب | 3 | **0** |
| كبتن | 4 | **0** |
| مشرف | 2 | **2** |

**فالجوابُ صفر** — كما توقّع المالك، لأن التسجيل بالبريد لم يعمل بعد.
**والاثنان المشرفان لا رقمَ لهما أصلاً** ويدخلان باسمِ مستخدم.

> **وهذا القياسُ غيَّر التصميم، ولم يكن ليُعرف بلا قراءة**: حملةٌ لا تستثني
> الموظّفين **توقف اللوحةَ عن نفسها** في أوّل تشغيل — **من يفكّ الإيقافَ
> يحتاج لوحةً، واللوحةُ موقوفة**. فصار النطاقُ ثلاثةَ شروطٍ لا شرطاً:
> رقمٌ غير مؤكَّد · **وله رقمٌ أصلاً** · **ودورُه راكبٌ أو كبتن**.

### ما بُني

| | |
|---|---|
| **`0066`** | `verification_campaigns` (حيّةٌ واحدةٌ لكلِّ سوقٍ بفهرسٍ جزئيّ) · `verification_enforcements` · `users.verification_suspended_at` |
| **حالٌ مستقلّةٌ عن `is_blocked`** | ذاك قرارُ مشرفٍ بسببٍ مكتوب، **وهذه آليّةٌ تشفي نفسَها**. **وخلطُهما عطبٌ في اتجاهين**: ضغطةُ تأكيدٍ **تفكّ حظراً قرّره مشرفٌ لسببٍ آخر**، ومشرفٌ يرفع الحظرَ **يُلغي إيقافاً لم يُشفَ سببُه** |
| **النصوصُ الثلاثة** | بلفظ المالك، **والمدّةُ محقونةٌ من الحقل لا مكتوبةٌ في النصّ** |
| **سببُ الإيقاف** | منشورٌ على `UserOut.suspension` — **ومن بيتٍ واحدٍ** يقرؤه الإشعارُ والخطأُ والحقل |
| **التجمّدُ والاستئناف** | **آليّان بلا مشرف**، **والمهلُ تُمدَّد بمقدار ما تجمّدت** — «تستأنف بما بقي» لا بما مضى من التقويم |
| **الفكّ** | **بتأكيد الرقم وحدَه** من `POST /auth/me/verify-phone` نفسِه — ولا بابَ ثالث |
| **الاشتراك** | يُمدَّد بأيام الإيقاف، **والصفُّ الأبعدُ انتهاءً** لا الأحدثُ إنشاءً · **ولا يُخترع اشتراكٌ لمن لم يكن مشتركاً** |
| **المحفظة** | **لا تُمسّ** — الإيقافُ منع العملَ ولم يأخذ مالاً |
| **الأبواب** | أربعةٌ: قراءةٌ · مسوّدة · إطلاق · إلغاء. **ولا بابَ تجميدٍ ولا فكّ** — وزرٌّ يفكّ بلا تأكيدٍ يُفرِّغ الحملةَ من معناها |
| **اللوحة** | قسمٌ في الإعدادات، **و`scope_size` معروضٌ على الزرّ**: من ضغط لا يستردّ رسالةً أُرسلت. **والإطلاقُ يستأذن مرّتين** |
| **الاختبارات** | **١٦** — ومنها التجمّدُ والاستئنافُ بمدِّ المهل، ومن أكّد بين دورتين، والمحفظةُ لا تُمسّ |

### ⚠ وما لم يُبنَ — بعلّته

**لا شاشةَ جديدةً في التطبيقين** (قرارُ المالك): **سطرُ «أكّد رقمك» هو نفسُه**،
وزِيدت له حالُ الإيقاف بنصِّها من الخلفية. **ولا مسارَ تأكيدٍ جديد**.

**ولم تُطلق على أحد** — ولا تُطلق: **الزرُّ بيد المالك**، والنطاقُ اليومَ صفر.
<!--/جديد-->

<!--جديد-->
### وثلاثةُ حرّاسٍ أمسكوا الحملةَ وهي تُبنى — ويُقرأ هذا قبل الحارس القادم

**١) `test_locks_have_tests` أمسك قفلاً بلا شاهد.** `_locked` تأخذ قفلَ صفٍّ
ولا اختبارَ تزامنٍ يسمّيها — **فأحمرَّت المجموعة**.

**٢) و`test_two_doors` أمسك حمولةً من أربعة أبواب** بحقولٍ محسوبة، فصُنّفت
`SHARED_BUILDER`: الأبوابُ الأربعةُ كلُّها تمرّ بـ`_out` وحدَه.

**٣) والثالثُ هو الدرس**: أوّلُ اختبارِ تزامنٍ كُتب بـ`asyncio.gather` على
نداءَي HTTP — **ومرّ والقفلُ محذوف**.

> **ونداءان في `gather` يتشابكان فقط إن شاءت حلقةُ الأحداث** — وغالباً ينتهي
> الأولُ قبل أن يبدأ الثاني. **فالاختبارُ يمرّ لأن التزامنَ لم يقع، لا لأن
> القفلَ عمل** — وهو «الثقةُ الكاذبة» التي كُتبت في `CLAUDE.md` عن اختبارٍ
> مثله في `documents`، **ووقعت ثانيةً في اليوم نفسِه لمن كتبها**.

**فأُعيد بجلستين وتشابكٍ مرتَّب**: الأولى تأخذ القفلَ وتُبقي معاملتَها
مفتوحة، والثانيةُ تقف عليه — **ومهلةٌ قصيرةٌ تُثبت أنها واقفة**. **وقِيس
بالحذف**: أخضرُ بالقفل، **وأحمرُ بلا القفل**.

> **وحدُّ ذلك مكتوب**: لولا `test_locks_have_tests` **لَما عُرف أن القفلَ بلا
> شاهد**، ولولا **حذفُ القفل** لَما عُرف أن الشاهدَ لا يشهد. **حارسان لا
> واحد** — وكلاهما لازم.

**ورابعٌ اسمُه ملف**: `test_locks_have_tests` **لا يقرأ إلا
`test_*concurrency*.py`** — فاختبارٌ صحيحٌ في ملفٍّ آخر **يمرّ ولا يُحسب**،
والحارسُ يبقى أحمرَ وصاحبُه يظنّه عطباً في الحارس.
<!--/جديد-->

<!--جديد-->
### ⚠ و`test_missions_levels` سقط مرّةً ونجح مرّةً — **على الشجرة نفسِها**

**قِيس 2026-08-31/09-01**: في تشغيلٍ كاملٍ سقط اثنان
(`test_progress_counts_completed_rides_only` بـ`1 == 2`،
و`test_lowering_a_target_raises_whoever_was_waiting_on_it` بـ`0 == 3`)،
**ثم نجح التشغيلُ التالي على الشجرة نفسِها بلا تغييرِ حرف** — ١٢٤٦ خضراء.

**وقِيس أيضاً** أن الملفَّ يمرّ **منفرداً**، ويمرّ **مع الملفّات الجديدة
كلِّها** (٦٤ خضراء) — **فليس من الحملة ولا من البريد**.

> **وهذا يُكتب ولا يُصلَح اليوم** (بحكم «ما عدا ذلك يُكتب بنداً ويُمضى»):
> **اختبارٌ يسقط مرّةً من مرّتين أخطرُ من اختبارٍ ساقطٍ دائماً** — الساقطُ
> دائماً يُصلَح، **والمتقطّعُ يُعاد تشغيلُه حتى يخضرّ**، فيصير الحارسُ
> إجراءً يُمرّ عليه. **ومن أعاد التشغيلَ مرّةً سيعيده على سقوطٍ حقيقيّ.**

**وما لم يُقَس**: سببُه. **ولا يُرجَّح هنا** — يحتاج تشغيلاً بترتيبٍ مثبَّت
(`-p no:randomly` أو بذرةٍ مسجَّلة) وقياساً لما يشترك فيه مع ما قبله.
<!--/جديد-->
