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
script, `GET /config`), 3 (`rides`, Mapbox Directions pricing, request/status endpoints) and 4
(Redis GEO presence, dispatch algorithm, WebSocket tracking and ride events) are complete. Do not
implement anything from a later stage unless the user asks for that stage. When a later-stage
concern appears in current code (e.g. `dispatch.eligible_driver_ids` does not check for a valid
subscription because `driver_subscriptions` arrives in stage 7), leave a comment naming the stage
rather than building ahead.

**User-facing strings, comments, and docs are in Arabic.** Identifiers stay English. Match this.

## Commands

Everything runs through Docker; there is no local venv. The compose project is named `taxo-app` and
the API is published on **8001** — an unrelated `taxo` stack and another service on 8000 exist on the
developer's machine. Never run `docker compose down --remove-orphans`; it would delete their containers.

```bash
docker compose up -d --build          # start db + redis + backend (runs alembic upgrade head on boot)
docker compose logs -f backend
curl http://localhost:8001/health     # reports db + redis status; also the container healthcheck
```

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
"type already exists". Because the downgrade/upgrade cycle gives the enums new OIDs,
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
events, sockets); `tasks/` is still a placeholder for stage 7's Celery jobs.

**Authentication is a swappable strategy, not a fixed flow.** `services/auth/` defines `AuthStrategy`
with `PasswordAuthStrategy` (active) and `OtpAuthStrategy` (stage 8, currently raises 501).
`get_auth_strategy()` picks between them and `sms_provider_enabled()` is the single decision point; it
reads the `sms` row of `provider_credentials`, so saving and activating that contract from the admin
panel flips every route to OTP. Routers depend only on the interface — activating a provider must
never require touching an endpoint.

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

`services/tracking.py` implements SPEC section 5's "driver offline > 60s during `in_progress` alerts
both parties and does **not** end the ride" — it starts on `POST /rides/{id}/start` and stops on
complete/cancel. It has no code path that mutates a ride; the 60s threshold is not a second timer
but the disappearance of the presence key, whose TTL already is 60s, so the two cannot disagree.

Nearby drivers shown on the rider's map are anonymised per SPEC section 10: coordinates, heading
and category only. `drivers.anonymous_ref` derives a per-connection pseudonym (blake2s keyed by a
random salt) so the frontend can interpolate a car's movement between frames without the same
driver being trackable across sessions.

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
- Pricing and all financial math happen in the backend only; the frontends display.
- `rides.commission_percent_at_ride` is frozen at creation and never recomputed retroactively.
- Commission is enabled **only** through `commission_settings`; there is deliberately no
  `commission_enabled` feature flag, so the switch, the percent, and the scope cannot disagree.
- Every endpoint touching a ride or wallet must verify ownership (no IDOR).

Python is pinned to 3.12 in the Dockerfile even though the host has 3.14, because Celery (stage 7)
does not support 3.14 yet.
