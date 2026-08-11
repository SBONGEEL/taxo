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
dispatch subscription check, and the Celery sweep), **8** (the full contracts page with test
connection, unified provider interfaces with mocks, and the OTP/Push/automatic-CliQ/payout
integrations), **9** (`customer-app/` — the rider PWA, plus the in-app CliQ payment page and the
backend fields it needed) and **9-ب** (backend only: driver-document upload/review on the
long-dormant `driver_documents` table, `core/storage.py`, and the `user_notifications` inbox
written from both send doors) are complete. **Stage 11 (the admin panel, `admin-panel/`) has begun** — shell, login, drivers/documents,
finance (withdrawals and CliQ topups), disputes, and campaigns.
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

**A change to `requirements.txt` needs `docker compose build backend` *and then*
`docker compose up -d backend` — never `restart`.** The source tree is bind-mounted, so code edits are
picked up live and it is easy to assume dependencies are too; they are not. `restart` starts the same
container from the same image, so a newly declared package is simply absent. And **the test suite will
not catch it**: `docker compose run` builds a fresh container from the image each time, so tests pass
against the new dependency while the long-running service still crashes on it. This shipped once —
stage 9-ب added `python-multipart`, the suite went green, and the running backend answered every
request with `RuntimeError: Form data requires "python-multipart"` until the container was recreated.
Same rule for `worker` and `beat`: they run the same image.

`driver-app` (stage 10) is the captain PWA on **5174**, same shape as `customer-app` — a
`node:22-alpine` container running Vite, `node_modules` in a named volume. Its
`tailwind.config.js` is copied verbatim from `design/DESIGN.md` §6, which is the source: scale keys
are pixel values (`text-14.5`, `p-16`, `rounded-13`) and Tailwind's own scales are **replaced, not
extended**, so `text-sm` or `p-4` is a build error rather than a silent drift to the nearest default.
Dark is the default and does not follow the system — a captain works for hours with the screen in the
car, and a theme that flips at sunset whitens his screen in a tunnel.

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
no device registration (a desk panel receives no push), no WebSocket yet (the live map arrives with
its own screen, not with the shell), and a **country switch in the header** that narrows what every
screen shows — display state in `sessionStorage`, so two tabs on two markets do not fight.
One backend rule the panel made visible: **`/admin/drivers/{id}/activate` goes through
`drivers.approve`, not a bare status write** — otherwise suspending and reactivating a driver would
be a way around the verified-phone and approved-documents guards, and the shortest path to a driver
working with no licence on file. The drivers screen reads those two guards *before* enabling its
approve button and names what is missing, because a button that works and then bounces teaches the
admin to retry, while a disabled button that says why teaches them to fix.

**`support` sees less than `admin` in the UI, and that is comfort, not protection**: every admin
route enforces the role server-side (SPEC §13/8), and hiding a button never prevented a request.

`customer-app` (stage 9) is the rider PWA on **5173** — a `node:22-alpine` container running Vite.
That port is not interchangeable: it is in `settings.cors_origins` and `settings.card_return_url`
points at `/payments/card/return` on it. Its `node_modules` lives in a named volume because the
host is Windows and the container is alpine. Frontend commands run on the host (node 22+):

```bash
cd customer-app && npm install
npm run build     # full type-check (tsc -b) then a production build — the gate before committing
npm run lint      # tsc --noEmit alone
npm run dev       # if you'd rather not use the container
```

There is no frontend test runner: stage 9 added no business logic to test — pricing, balances and
state transitions all stay in the backend, and the app displays what the API returns. `npm run
build` is the check that runs, and it type-checks every file.

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
verification flow to draw (`auth.verification`), which payment channels exist in this country
(`countries[].features`), which map token to use. A flag switched off in the contracts page
disappears from the app with no deploy — that is the whole point of publishing the config, and it
is why no feature name is hardcoded outside `screens/Payment.tsx::METHODS` and `lib/config.tsx`.
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
