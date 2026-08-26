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
