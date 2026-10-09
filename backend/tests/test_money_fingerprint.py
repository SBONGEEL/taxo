"""بصمةُ المال (SPEC §٦٥-أ) — **تُرى بها أدقُّ مخالفةٍ للشرط، ولا يُقرأ الجديدُ مخالفة**.

- لا شيءَ تغيّر ⇒ مطابقة.
- **قيدٌ جديدٌ بعد لحظة «قبل»** (حركةٌ حيّةٌ بعد الرفع) ⇒ مطابقةٌ بـ`as_of` — **وبغيرها يُرى**، فالأداةُ لا تعمى عن الجديد.
- **بصمةُ الدفتر أو رصيدُ محفظةٍ تغيّر** ⇒ مخالفةٌ مسمّاة (والدفترُ لا يُحرَّر أصلاً — مشغّلُ القاعدة).
"""

from __future__ import annotations

import copy

from scripts import money_fingerprint
from tests.helpers import OTHER_RIDER, auth, register, rider_session, topup_wallet


async def test_the_fingerprint_sees_changes_to_what_existed_and_ignores_what_came_after(
    client, admin_headers, jordan_settings, jordan_wallet, session_factory, monkeypatch
) -> None:
    monkeypatch.setattr(money_fingerprint, "SessionLocal", session_factory)
    first = await rider_session(client)
    await topup_wallet(client, admin_headers, first["user"]["id"], "10.000")
    await topup_wallet(client, admin_headers, first["user"]["id"], "5.000")

    before = await money_fingerprint.fingerprint()
    assert money_fingerprint.compare(before, await money_fingerprint.fingerprint()) == ([], [])

    # **حركةٌ حيّةٌ بعد «قبل»**: قيدٌ جديدٌ لمالكٍ قائمٍ ومحفظةٌ جديدة
    await topup_wallet(client, admin_headers, first["user"]["id"], "1.000")
    second = auth(await register(client, OTHER_RIDER))
    me = await client.get("/auth/me", headers=second)
    await topup_wallet(client, admin_headers, me.json()["id"], "3.000")

    as_of = await money_fingerprint.fingerprint(as_of=before["taken_at"])
    assert money_fingerprint.compare(before, as_of)[0] == [], "قيودُ ما بعد «قبل» قُرئت تغيّراً لما كان"
    live = await money_fingerprint.fingerprint()
    assert money_fingerprint.compare(before, live)[0], "الأداةُ عمياءُ عن رصيدٍ تغيّر"

    # **والدفترُ نفسُه لا يُحرَّر** (`wallet_transactions_append_only` — مشغّلُ القاعدة منذ `0006`)، فتُقاس المقارنةُ على نسخةٍ
    # بُدّلت فيها بصمةُ الدفتر ورصيدُ محفظة: **كلاهما يُسمّى، ولو بقي المجموعُ كما كان**
    tampered = copy.deepcopy(before)
    tampered["tables"]["wallet_transactions"]["sha256"] = "0" * 64
    wallet = next(iter(tampered["wallets"]))
    tampered["wallets"][wallet]["balance"] = "0.000"
    problems, _notes = money_fingerprint.compare(before, tampered)
    assert any(p.startswith("table wallet_transactions") for p in problems), problems
    assert any(p.startswith(f"wallet {wallet}") for p in problems), problems


async def test_the_rounding_journal_is_fingerprinted_like_the_ledger(
    client, admin_headers, jordan_settings, jordan_wallet, session_factory, monkeypatch
) -> None:
    """**سجلُّ التقريب في البصمة** (SPEC §٧٠-ج/٣) — **ويُقاس كالدفتر**: يُضاف إليه ولا يُحرَّر، فتغيّرُ ما كان فيه مخالفةٌ
    **ولو مع `as_of`** (حيث الجداولُ الأخرى ملاحظة). **وغيابُه في بصمة «قبل»** (نسخةٌ أقدمُ من `0104`) **لا يُقرأ تغيّراً**: جدولٌ
    جديدٌ لم يكن فيه ما يتغيّر — والشرطُ «الجداولُ والأعمدةُ الجديدةُ لا بأس بها».

    **وصفوفُه الحقيقيّةُ ومقارنتُها قبل الإشعال وبعده** في `test_rounding.py` (رحلةٌ تُقرَّب بالمسار الحقيقيّ).
    """
    monkeypatch.setattr(money_fingerprint, "SessionLocal", session_factory)
    first = await rider_session(client)
    await topup_wallet(client, admin_headers, first["user"]["id"], "10.000")

    before = await money_fingerprint.fingerprint()
    journal = before["tables"][money_fingerprint.ROUNDINGS]
    assert journal["rows"] == 0 and "absent" not in journal, journal

    # **نسخةٌ أقدمُ من الترحيلة**: الجدولُ غائبٌ في «قبل» — لا مخالفةَ ولا ملاحظة
    older = copy.deepcopy(before)
    older["tables"][money_fingerprint.ROUNDINGS] = {"absent": True}
    assert money_fingerprint.compare(older, await money_fingerprint.fingerprint()) == ([], [])

    # **وبصمتُه تغيّرت** ⇐ مخالفةٌ **حتى على الإنتاج الحيّ** (`as_of`) — لا ملاحظةُ حركة
    tampered = copy.deepcopy(before)
    tampered["tables"][money_fingerprint.ROUNDINGS]["sha256"] = "0" * 64
    live = await money_fingerprint.fingerprint(as_of=before["taken_at"])
    problems, notes = money_fingerprint.compare(tampered, live)
    assert any(p.startswith(f"table {money_fingerprint.ROUNDINGS}") for p in problems), (problems, notes)
