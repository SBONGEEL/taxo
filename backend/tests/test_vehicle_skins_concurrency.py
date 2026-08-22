"""آخرُ نسخةٍ تحت التزامن — **وهذا ما يملكه القفلُ وحدَه** (2026-08-22).

**والكميّةُ محسوبةٌ لا مخزَّنة**، فلا فهرسَ فريدٌ يحرسها كما حرس مقعدَ
المشاركة: `UNIQUE(driver_id, skin_id)` يمنع أن يملك كبتنٌ واحدٌ نسختين،
**ولا يقول شيئاً عن كبتنين يشتريان آخرَ نسخةٍ معاً**. فالقفلُ هنا هو الحارسُ
الوحيد، وحذفُه يُسقط هذا الملفّ — قِيس ذلك، والنتيجةُ في ترويسة الاختبار.

**ولا `gather` وحدَه**: أُثبت في هذا المشروع مراراً أن `gather` قد يُنهي
الأولَ قبل أن يبدأ الثاني، فيمرّ الاختبارُ والقفلُ محذوف. فالتشابكُ صريح —
الأولُ يمسك معاملتَه ٤٠٠ مللي والثاني يبدأ بعد ١٠٠.
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.exceptions import AppError
from app.models.enums import CountryCode, WalletTransactionType
from app.models.user import User
from app.models.wallet import WalletTransaction
from app.models.vehicle_skin import (
    RARITY_LEGENDARY,
    DriverVehicleSkin,
    VehicleSkin,
    VehicleSkinPrice,
)
from app.models.driver import Driver
from app.services import vehicle_skins as skins_service
from tests.helpers import approved_driver, enable_features, topup_wallet

DEADLOCK_TIMEOUT = 20.0


def _payload(phone: str) -> dict:
    """كبتنٌ برقمٍ خاصّ به — رقمان متطابقان يجعلان الثاني يرتدّ عند التسجيل."""
    return {
        "phone": phone,
        "password": "Driver12345",
        "name": f"كبتن {phone[-4:]}",
        "country_code": "JO",
        "role": "driver",
    }


@pytest.fixture
async def last_copy(
    client: AsyncClient, admin_headers: dict, session_factory
) -> dict:
    """مركبةٌ بنسخةٍ واحدة، وكبتنان يملك كلٌّ منهما ثمنَها."""
    await enable_features(session_factory, "wallet_enabled", "vehicle_skins_enabled")
    first = await approved_driver(
        client, session_factory, _payload("+962791700001"), plate_number="AMM-1010"
    )
    second = await approved_driver(
        client, session_factory, _payload("+962791700002"), plate_number="AMM-2020"
    )
    for driver in (first, second):
        await topup_wallet(client, admin_headers, driver["user_id"], "20.000")

    async with session_factory() as session:
        skin = VehicleSkin(
            name="الوحيدة",
            rarity=RARITY_LEGENDARY,
            asset_key="the-only-one",
            max_supply=1,
        )
        session.add(skin)
        await session.flush()
        session.add(
            VehicleSkinPrice(
                skin_id=skin.id,
                country_code=CountryCode.JO,
                price=Decimal("5.000"),
            )
        )
        await session.commit()
        return {
            "skin_id": skin.id,
            "drivers": [first["driver_id"], second["driver_id"]],
            "users": [uuid.UUID(first["user_id"]), uuid.UUID(second["user_id"])],
        }


async def _buy(session_factory, *, driver_id, user_id, skin_id, hold=0.0) -> str:
    """شراءٌ في معاملةٍ مستقلة — `ok` أو رمزُ الرفض."""
    async with session_factory() as session:
        driver = await session.get(Driver, driver_id)
        user = await session.get(User, user_id)
        try:
            await skins_service.buy(
                session, driver=driver, user=user, skin_id=skin_id
            )
            if hold:
                # يُبقي المعاملةَ مفتوحةً فيدخل الثاني في انتظار القفل فعلاً
                await asyncio.sleep(hold)
            await session.commit()
            return "ok"
        except AppError as caught:
            await session.rollback()
            return caught.code


async def test_two_captains_buying_the_last_copy_leave_one_owner(
    session_factory, last_copy
):
    """**الثابت**: مالكٌ واحدٌ لآخر نسخة، والثاني يُردّ بـ`skin_sold_out`.

    **وقِيس بالحذف** (٢٠٢٦-٠٨-٢٢): بإسقاط `with_for_update` من
    `vehicle_skins._locked_skin` يمرّ الشراءان معاً — `['ok', 'ok']` ومالكان
    لمركبةٍ سقفُها واحد، **بلا استثناءٍ وبلا سطرٍ في سجلّ**. ولا فهرسَ يمسكها:
    `uq_driver_skin` يقارن كبتناً بنفسه لا كبتنين ببعضهما.

    **وأسوأُ من العدد ما بعده**: صفَّا مِلكيّةٍ لا يُحذفان، وقيدان في دفترين —
    فالتصحيحُ لاحقاً سحبُ مركبةٍ من كبتنٍ دفع ثمنها.
    """
    results = await asyncio.wait_for(
        asyncio.gather(
            _buy(
                session_factory,
                driver_id=last_copy["drivers"][0],
                user_id=last_copy["users"][0],
                skin_id=last_copy["skin_id"],
                hold=0.4,
            ),
            _second(session_factory, last_copy),
        ),
        timeout=DEADLOCK_TIMEOUT,
    )

    assert sorted(results) == ["ok", "skin_sold_out"], results

    async with session_factory() as session:
        owners = await session.scalar(
            select(func.count())
            .select_from(DriverVehicleSkin)
            .where(DriverVehicleSkin.skin_id == last_copy["skin_id"])
        )
        # **الدفترُ يوافق العدد**: قيدُ شراءٍ واحدٌ لا اثنان — فلو خُصم من
        # كبتنين لصار التصحيحُ ردَّ مالٍ لا حذفَ صفّ
        entries = await session.scalar(
            select(func.count())
            .select_from(WalletTransaction)
            .where(
                WalletTransaction.type == WalletTransactionType.SKIN_PURCHASE
            )
        )
    assert owners == 1, "مالكان لمركبةٍ سقفُها نسخةٌ واحدة"
    assert entries == 1, "قيدان في الدفتر لنسخةٍ واحدة"


async def _second(session_factory, last_copy) -> str:
    """يبدأ بعد ١٠٠ مللي — فيدخل بالفعل في انتظار قفلِ الأول."""
    await asyncio.sleep(0.1)
    return await _buy(
        session_factory,
        driver_id=last_copy["drivers"][1],
        user_id=last_copy["users"][1],
        skin_id=last_copy["skin_id"],
    )


async def test_the_same_captain_pressing_twice_pays_once(
    session_factory, last_copy
):
    """ضغطتان من كبتنٍ واحد — **صفٌّ واحدٌ وقيدٌ واحد**.

    وهذا يحرسه اثنان: القفلُ نفسُه، **ومفتاحُ التفرّد المشتقّ**
    (`skin:{skin}` تحت مالكه) الذي يجعل القيدَ الثاني يجد قيدَ الأول بدل أن
    يكتب ثانياً. وهو موثَّقٌ بما هو: **يمرّ بحذف القفل** لأن
    `uq_driver_skin` يمسك التكرار — فلا يُقرأ حارساً للقفل.
    """
    results = await asyncio.wait_for(
        asyncio.gather(
            _buy(
                session_factory,
                driver_id=last_copy["drivers"][0],
                user_id=last_copy["users"][0],
                skin_id=last_copy["skin_id"],
                hold=0.4,
            ),
            _same_again(session_factory, last_copy),
        ),
        timeout=DEADLOCK_TIMEOUT,
    )
    assert results.count("ok") == 1, results

    async with session_factory() as session:
        owned = await session.scalar(
            select(func.count())
            .select_from(DriverVehicleSkin)
            .where(DriverVehicleSkin.driver_id == last_copy["drivers"][0])
        )
    assert owned == 1


async def _same_again(session_factory, last_copy) -> str:
    await asyncio.sleep(0.1)
    return await _buy(
        session_factory,
        driver_id=last_copy["drivers"][0],
        user_id=last_copy["users"][0],
        skin_id=last_copy["skin_id"],
    )
