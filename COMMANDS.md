<!--جديد-->
# COMMANDS.md — الأوامرُ، وما يكسرها في هذه الحاويات

**مُلزِمٌ بشرطه في `CLAUDE.md`**: *قبل أن تشغّل أمراً أو تبنيَ حاويةً أو تفتح المجموعة — يُفتح هذا الملفّ.*

**نقلٌ لا تحرير.** كلُّ ما تحت هذا السطر منقولٌ من `CLAUDE.md` بحرفه — لا حرفَ تغيّر ولا سطرَ أُعيدت صياغتُه.
وفهرسُه في `CLAUDE.md` تحت «الفهرس — كلُّ ما نُقل».
<!--/جديد-->

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

**Run the suite through `scripts/suite.sh` and nowhere else** — it is the guard for this class, and it
exists because the written rule did not prevent the fault. It refuses to start while a previous run is
still alive (naming the container), refuses while anything still holds `taxo_test`, names its own
container so an interrupt can remove it, and writes the verdict into the bind-mounted tree so it
outlives the container.

**And one long-standing claim here was measured and is false**: a killed run does *not* restart itself
by policy — `RestartPolicy=no` on the run container, measured 2026-08-20. What actually happens is
simpler and worse: **killing the compose client does not kill the container it started**, so it keeps
running and keeps holding the test database, and every later run dies at setup with one error repeated
once per test (1076 of them), which reads as catastrophe and is dirt. The `-d` variant was never
re-measured; do not assert it either way.

<!--جديد-->
**ووجهٌ سادسٌ قِيس 2026-08-30، وهو أخفاها كلِّها**: **`restart` يعيد تشغيل
الأمرِ الذي أُنشئت به الحاويةُ لا الأمرَ المكتوبَ في `docker-compose.yml`.**
حاويةُ تطويرٍ أُقلعت مرّةً بـ`vite preview` ظلّت **تخدم `dist` شهراً** والملفُّ
يقول `vite dev` — **وكلُّ شيءٍ أخضر**: الخدمةُ «تعمل»، والملفُّ في الحاوية
صحيحٌ حرفاً، والصفحةُ تُرسم كاملةً — **صفحةَ ذلك اليوم**. **والسؤالُ ليس «أهي
تعمل؟» بل «أيَّ أمرٍ تشغّل؟»**، وجوابُه `ps` **داخلها**، لا ملفُّ compose.
**والعلاجُ `up -d --force-recreate`.**

> **⚠ وقبل أن «تُصلِح» حاويةً تخدم `dist`: اسأل بأيِّ طبقةٍ أُقلعت.**
> `docker-compose.tunnel.yml` **يستبدل `command:` قصداً** بـ`vite preview`،
> لأن حارسَي الواجهة يقرآن `backend/app` والحاويةُ لا تحمله — **فتبني أنت على
> المضيف وتخدم هي `dist`**. فـ`preview` في وضع النفق **هو الصحيح**، وإعادتُه
> إلى `dev` تكسر جولةَ الهاتف.
>
> **فالخللُ ليس في `preview` بل في أن تُقلَع الطبقةُ ثم تُنسى**: أمرُ compose
> **يذكر ملفاتِه كلَّها صراحةً** في الاتجاهين — من نسي `-f docker-compose.tunnel.yml`
> عند الإقلاع أقلع وضعَ التطوير، ومن نسيه عند الإصلاح ظنّ وضعَ النفق عطباً.

**ومعه على ويندوز**: `localhost` يُحلّ إلى `::1` أوّلاً. **فمنفذٌ يحمله Docker
على IPv4 وعمليةُ مضيفٍ على IPv6 خادمان لا خادم** — وقياسٌ على `localhost`
يذهب إلى الخطأ منهما صامتاً. **يُقاس على `127.0.0.1` صراحةً**، و`netstat -ano
| grep :المنفذ` يُقرأ **قبل** أن يُتَّهم الكود.

---

**وبناءُ أيِّ حزمةٍ أندرويد يحتاج JDK 21 لا 17** (قِيس 2026-09-01):
`capacitor-android` يعلن `sourceCompatibility JavaVersion.VERSION_21`،
و`JAVA_HOME` على جهاز التطوير 17 — **فالسقوطُ `error: invalid source
release: 21` عند `:capacitor-android:compileDebugJavaWithJavac`**، ولا يقول
اسمَ المتغيّر الذي يُصلحه.

    JAVA_HOME="/c/Program Files/Android/Android Studio/jbr"       TAXO_CHANNEL=public sh gradlew assemblePublicRelease --no-daemon -q

**و`sh gradlew` لا `./gradlew`** — صلاحيةُ التنفيذ لا يحفظها ويندوز.
**و`local.properties` غيرُ متعقَّبٍ بحقّ** (فيه مسارُ SDK لهذا الجهاز)،
فمشروعٌ أندرويد جديدٌ يحتاج نسخَه من مشروعٍ قائم قبل أوّل بناء.

**والقناةُ تُصرَّح ولا تُفترض** في الطرفين معاً — `build-channel.mjs` ثمّ
`cap sync` ثمّ `gradlew`؛ ومن نسيها في الأخير بنى نكهةً بغلافِ غيرها.
<!--/جديد-->

**These three are one family, and it is worth reading them together**: a `restart` that keeps the old
image (so a new dependency is missing), a bind mount that inotify cannot cross (so Vite serves the module
it read at startup), and a `run` that inherits a restart policy (so a finished test run starts again).
**Each one makes the container look like it did what you asked while it did something else**, and none of
them produces an error message — which is why every one of them was found by measuring the running
system, not by reading the compose file.

**وللعائلة وجهٌ رابعٌ قِيس 2026-08-24، وهو أخبثُها لأن الحاويةَ فيه سليمةٌ
تماماً**: `uvicorn --reload` **لا يعبر تجسيرَ ويندوز** — كما لا يعبره Vite.
فالعمليةُ الحيّةُ تبقى حاملةً وحدةً قُرئت يومَ إقلاعِها، **والشجرةُ تحتها
جديدة**. ووقع أن الخلفيةَ كانت تنشر **٢٢ مفتاحاً والتعدادُ ٢٤** — فبدا في
اللوحة أن مفتاحَي المال «غيرُ موجودَين»، وهما في الشجرة منذ يوم.

**وما يجعله فخّاً بعينه**: `docker exec … python -c` **عمليةٌ جديدةٌ تقرأ
القرصَ فتُجيب ٢٤** — فتشهد الحاويةُ لنفسها بالسلامة، **والخادمُ يجيب ٢٢**.
فيُسأل **الخادمُ** لا عمليةٌ تُولد بجانبه، وهي «اقرأ من الشيء الذي يحكم»
نفسُها. **والعلاجُ إعادةُ تشغيل، لا انتظارُ `--reload`.**

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

**⚠️ And a trap that is new since the self-hosted WhatsApp channel went live: these numbers are
fabricated for the dev database, but they are *shaped* like real Jordanian numbers — and some of them
are registered on WhatsApp by their real owners.** Passing one as `test_phone` to the WhatsApp contract's
test button **sends a real message to a real stranger**. It happened on 2026-08-16: `+962790000021`
(«عمر الراكب» in the table below) was assumed not to be on WhatsApp, `onWhatsApp` reported that it *was*,
and a code message went out with a real `wamid` returned. The guard worked exactly as designed — it just
found the number genuinely exists. **So `test_phone` on the WhatsApp contract takes a number you own and
nothing else**; to prove the wire without sending anything, leave it blank — the test then reports the
linked number and its link time, which is what the question usually is.

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

