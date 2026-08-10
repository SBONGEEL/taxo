# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
dispatch subscription check, and the Celery sweep) and **8** (the full contracts page with test
connection, unified provider interfaces with mocks, and the OTP/Push/automatic-CliQ/payout
integrations) are complete. **The next stage is 9** (the rider PWA). Do not implement
anything from a later stage unless the user asks for that stage. When a later-stage concern appears
in current code (e.g. no Celery job sweeps stale `provider_orders` yet, and the campaigns page in
the admin panel lands in stage 11 while its endpoints already exist), leave a comment naming the
stage rather than building ahead.

**Any path that changes a row's status locks that row with `for_update` *before* it checks the
transition.** Reading the row, validating `current → target`, then writing is not atomic on its own:
under Postgres' READ COMMITTED default, concurrent requests all read the same pre-commit status,
all pass the check, and all report success. Load the row with `select(...).with_for_update()
.execution_options(populate_existing=True)` — see `topups.get_request` / `withdrawals.get_request`
(`for_update=True`) and `rides.cancel_ride` (`session.refresh(..., with_for_update=True)`).

**Lock order is always: the ride row, then the request/payment row, then the provider-order row,
then the driver row, then the wallet advisory lock.** Every mutating path takes them in that order,
which is why nothing deadlocks. Creating payments locks the ride (`payments._payable_ride`) so two
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

`worker` and `beat` are the Celery pair from stage 7 (`app/tasks/`), running the subscription sweep
every five minutes and the stage-8 campaign dispatch every minute. **Run exactly one `beat`** — a
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
```

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
`details` carries changed field names only, never values.

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

**Nothing calls `ws/events.publish_*` directly any more; `services/notifications.py` does.** It
publishes to Redis and then sends the same event as a push notification, so a channel cannot be added
for one event and forgotten for another. Push goes only to devices whose socket is *not* open —
`services/presence.py` keeps a per-user hash of open `device_id`s (lazily pruned on read, since Redis
has no per-field TTL), and the socket writes into it only when the client sends `?device_id=`. That
one rule also means the actor never gets pushed his own action: whoever pressed the button has the app
open by definition. Ride offers are the only high-priority send — a twenty-second window does not
survive Doze mode. Delivery failures are swallowed and logged; a ride must not fail because a remote
service did.

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
