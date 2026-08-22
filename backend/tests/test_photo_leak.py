"""**الإعفاءُ لا يجوز أن يُرى** — وإلا صار علامةً على من أُعفي (قرارُ المالك 2026-08-22).

**الشكلُ العام**: **امتيازٌ يُمنح لفئةٍ يصير علامةً عليها إن كان غيابُه
مرئياً.** والحمايةُ ليست في منح الإعفاء بل في **ألّا يُميَّز المُعفى** — فمن
أُعفيت من الصورة يجب أن تبدو **كمن لم تُراجَع صورتُه بعد وكمن لم يرفعها**،
في الشاشة **وفي الشبكة معاً**.

**ولا يكفي أن تتشابه الشاشتان**: من يقرأ الشبكةَ لا يرى الشاشة — يرى **رمزَ
الحالة وحجمَ الردّ وترويسته**. فأيُّ فرقٍ في أحدها **وشايةٌ** ولو رسم
التطبيقُ الحرفَ نفسَه.

**والتسربُ الذي وُجد لهذا الملف ليس في ردٍّ واحد** (مقيسٌ 2026-08-22): الردّان
كانا **متطابقين فعلاً** — ٤٠٤ بنفس الجسم والترويسة. **والوشايةُ في الحالة
المستقرّة لا في اللحظة**: كلُّ كبتنٍ غيرِ مُعفى **يجب أن يرفع صورةً ليُعتمد**،
فتُراجَع وتظهر. **فمن لا تظهر صورتُه أبداً مُعفاةٌ — أي امرأة.** والزمنُ وحدَه
يكشفها، ولا يُصلح ذلك توحيدُ ردٍّ واحد.

**فالعلاجُ أن يكون للجميع صورة**: البابُ يردّ **دائماً ٢٠٠ بصورة** — الحقيقيةَ
لمن رُوجعت، **وحرفاً مرسوماً في الخادم** لمن سواه. فلا غيابَ يُرى، ولا حالةَ
تُستدلّ. **وبطولٍ ثابتٍ ونوعٍ واحد** كي لا يبقى للطول قناةٌ يُعدّ منها.
"""

from __future__ import annotations

from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy import select

from app.models.user import User
from tests.helpers import (
    DRIVER,
    RIDER,
    JPEG_BYTES,
    accepted_ride,
    approved_driver,
    bring_online,
    rider_session,
    upload_document,
)

# **حرفان مختلفان عمداً**: الحرفُ يُرسم في الخادم، **فحرفان متشابهان يجعلان
# الطولين متساويين بالصدفة** — واختبارٌ يمرّ بالصدفة لا يحرس الحشو. وقِيس:
# بحذف الحشو بقي الاختبارُ أخضرَ حين كان الاسمان يبدآن بـ«ك».
SECOND_DRIVER = {**DRIVER, "phone": "0797770001", "name": "مروانُ المقارنة"}
SECOND_RIDER = {**RIDER, "phone": "0797770002", "name": "راكبُ المقارنة"}
THIRD_RIDER = {**RIDER, "phone": "0797770003", "name": "راكبٌ ثالث"}


async def _stamp_female(session_factory, phone: str) -> None:
    """**الختمُ بيدِ الإدارة** — وهو ما يقرؤه الإعفاء، لا إقرارُ صاحبِ الحساب.

    والرقمُ يُطبَّع إلى E.164 كما تخزّنه القاعدة: `0791…` في الاختبار،
    `+962791…` في الصفّ — ومقارنةُ الصيغتين تعيد `None` صامتةً.
    """
    normalised = "+962" + phone.lstrip("0")
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.phone == normalised))
        user.gender = "female"
        user.gender_verified_at = datetime.now(UTC)
        await session.commit()


def _fingerprint(response) -> dict:
    """ما يراه قارئُ الشبكة — لا ما ترسمه الشاشة."""
    return {
        "status": response.status_code,
        "type": response.headers.get("content-type"),
        "length": len(response.content),
        "cache": response.headers.get("cache-control"),
        "disposition": response.headers.get("content-disposition"),
    }


async def test_the_exempt_and_the_unreviewed_look_identical_to_the_rider(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**سائقةٌ مُعفاةٌ وكبتنٌ لم تُراجَع صورتُه — ردٌّ واحدٌ لا يُفرَّق بينهما.**

    وبحذف التوحيد يسقط هذا الاختبار: يعود أحدُهما ٤٠٤ والآخرُ ٢٠٠، **أو
    يتساويان في الرمز ويفترقان في الطول** — وكلاهما يكفي لمن يعدّ البايتات.
    """
    # (أ) سائقةٌ ختمت الإدارةُ جنسَها — مُعفاةٌ فلا صورةَ لها أصلاً
    exempt = await approved_driver(client, session_factory, DRIVER)
    await _stamp_female(session_factory, DRIVER["phone"])
    await bring_online(client, exempt)
    rider_a = await rider_session(client)
    ride_a = await accepted_ride(client, rider_a["headers"], exempt)
    seen_exempt = await client.get(
        f"/rides/{ride_a['id']}/driver/photo", headers=rider_a["headers"]
    )

    # (ب) كبتنٌ رفع صورتَه ولم تُراجَع بعد
    pending = await approved_driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-7001"
    )
    await upload_document(
        client, pending["headers"], doc_type="profile_photo",
        content=JPEG_BYTES, filename="face.jpg",
    )
    await bring_online(client, pending)
    rider_b = await rider_session(client, SECOND_RIDER)
    ride_b = await accepted_ride(client, rider_b["headers"], pending)
    seen_pending = await client.get(
        f"/rides/{ride_b['id']}/driver/photo", headers=rider_b["headers"]
    )

    a, b = _fingerprint(seen_exempt), _fingerprint(seen_pending)
    # **`assert` قبل المقارنة**: ردّان فارغان يتطابقان ولا يحرسان شيئاً
    assert a["length"] > 0, "ردٌّ بلا جسم — الاختبارُ يقيس فراغاً"
    assert a == b, f"الردّان يفترقان — وشايةٌ لقارئ الشبكة:\n  معفاة={a}\n  معلّقة={b}"


async def test_a_driver_with_no_photo_at_all_looks_the_same(
    client: AsyncClient, session_factory, jordan_settings: None
) -> None:
    """**والحالُ الثالثة كذلك**: من لم يرفع شيئاً — فالحالاتُ ثلاثٌ لا اثنتان."""
    none_yet = await approved_driver(client, session_factory, DRIVER)
    await bring_online(client, none_yet)
    rider = await rider_session(client)
    ride = await accepted_ride(client, rider["headers"], none_yet)
    seen = await client.get(
        f"/rides/{ride['id']}/driver/photo", headers=rider["headers"]
    )

    exempt = await approved_driver(
        client, session_factory, SECOND_DRIVER, plate_number="AMM-7002"
    )
    await _stamp_female(session_factory, SECOND_DRIVER["phone"])
    await bring_online(client, exempt)
    rider2 = await rider_session(client, THIRD_RIDER)
    ride2 = await accepted_ride(client, rider2["headers"], exempt)
    seen2 = await client.get(
        f"/rides/{ride2['id']}/driver/photo", headers=rider2["headers"]
    )

    assert len(seen.content) > 0, "ردٌّ بلا جسم — الاختبارُ يقيس فراغاً"
    assert seen.status_code == 200, f"الردُّ ليس صورة: {_fingerprint(seen)}"
    assert _fingerprint(seen) == _fingerprint(seen2)
