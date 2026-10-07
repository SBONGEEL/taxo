"""الاسترداد الأسبوعي (SPEC §٦٣-ج/٨ — تعريفُ المالك) — **مطفأٌ لكلِّ سوقٍ حتى يُشعله المالك**.

ما يحرسه هذا الملف:

- **مطفأً أو بمبلغٍ صفر: لا سلسلة ولا نار.**
- **رحلةٌ كلَّ يومٍ تمدّ السلسلة، والجمعةُ لا تُطلب ولا تقطع، ورحلتان في يومٍ لا تزيدان.**
- **فواتُ يومٍ يُسقطها وتبدأ غيرُها.**
- **اليومُ الأخيرُ ينزل فيه المبلغُ مرّةً واحدة** — من TAXO.
- **والتذكيرُ عن الأيام** ويحين في ساعاته لمن لم يركب.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.cashback import CashbackStreak
from app.models.enums import CountryCode, FeatureKey, WalletTransactionType
from app.models.service_setting import ServiceSetting
from app.models.user import User
from app.models.wallet import WalletTransaction
from app.services import cashback
from tests.helpers import enable_features, rider_session

FLAG = FeatureKey.WEEKLY_CASHBACK_ENABLED.value
AMOUNT = Decimal("2.000")
#: سبتٌ معلوم — فالجمعةُ بعد ستة أيام
SATURDAY = date(2026, 10, 3)


@pytest.fixture(autouse=True)
async def _service_settings(_clean_state, session_factory) -> None:
    async with session_factory() as session:
        session.add_all([ServiceSetting(country_code="JO", cashback_amount=AMOUNT), ServiceSetting(country_code="LY")])
        await session.commit()


async def _day(session_factory, rider_id: str, day: date):
    async with session_factory() as session:
        rider = await session.get(User, rider_id)
        row = await cashback.settings_for(session, CountryCode.JO)
        streak = await cashback.record_day(session, rider=rider, day=day, row=row) if row is not None else None
        await session.commit()
        return streak


async def _credits(session_factory) -> Decimal:
    async with session_factory() as session:
        return await session.scalar(
            select(func.coalesce(func.sum(WalletTransaction.amount), 0)).where(
                WalletTransaction.type == WalletTransactionType.CASHBACK
            )
        )


async def test_switched_off_or_zero_amount_shows_no_fire(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    rider = await rider_session(client)
    assert (await client.get("/me/cashback", headers=rider["headers"])).json() == {
        "enabled": False, "days_required": None, "days_done": None, "days_left": None, "amount": None,
        "currency": None, "rode_today": False, "friday": False,
    }
    await enable_features(session_factory, FLAG)
    async with session_factory() as session:
        row = await session.get(ServiceSetting, CountryCode.JO)
        row.cashback_amount = Decimal("0")
        await session.commit()
    assert (await client.get("/me/cashback", headers=rider["headers"])).json()["enabled"] is False


async def test_six_days_without_friday_land_the_cashback_once(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    rider = await rider_session(client)
    rider_id = rider["user"]["id"]
    # السبتُ إلى الخميس، ورحلتان يومَ الإثنين، وجمعةٌ بينها لا تُحسب
    for offset in range(6):
        streak = await _day(session_factory, rider_id, SATURDAY + timedelta(days=offset))
        if offset == 2:
            await _day(session_factory, rider_id, SATURDAY + timedelta(days=offset))
    assert streak.status == "won" and streak.days_done == 6
    assert await _credits(session_factory) == AMOUNT
    # الجمعةُ التالية لا تبدأ شيئاً، والسبتُ بعدها يبدأ سلسلةً جديدة
    assert await _day(session_factory, rider_id, SATURDAY + timedelta(days=6)) is None
    fresh = await _day(session_factory, rider_id, SATURDAY + timedelta(days=7))
    assert fresh.status == "active" and fresh.days_done == 1
    assert await _credits(session_factory) == AMOUNT


async def test_friday_does_not_break_and_a_missed_day_cancels(
    client: AsyncClient, jordan_settings: None, session_factory
) -> None:
    await enable_features(session_factory, FLAG)
    rider = await rider_session(client)
    rider_id = rider["user"]["id"]
    thursday = SATURDAY + timedelta(days=5)
    await _day(session_factory, rider_id, thursday)
    # الخميسُ ثمّ السبت — الجمعةُ بينهما لا تُطلب
    after = await _day(session_factory, rider_id, thursday + timedelta(days=2))
    assert after.days_done == 2
    # ثمّ يفوت الأحد: الإثنينُ يبدأ سلسلةً جديدة والقديمةُ ساقطة
    restarted = await _day(session_factory, rider_id, thursday + timedelta(days=4))
    assert restarted.days_done == 1
    async with session_factory() as session:
        statuses = sorted((await session.scalars(select(CashbackStreak.status))).all())
    assert statuses == ["active", "lost"]
    assert await _credits(session_factory) == 0


def test_reminders_talk_on_their_hours_and_only_to_whoever_has_not_ridden() -> None:
    streak = CashbackStreak(last_day=SATURDAY, days_done=1, days_required=6)
    sunday = SATURDAY + timedelta(days=1)
    assert cashback.due_reminder(streak, sunday, 8) is None
    assert cashback.due_reminder(streak, sunday, 9) == "morning"
    assert cashback.due_reminder(streak, sunday, 19) == "evening"
    assert cashback.due_reminder(streak, sunday, 22) == "warning"
    streak.last_day = sunday
    assert cashback.due_reminder(streak, sunday, 22) is None
    friday = SATURDAY + timedelta(days=6)
    streak.last_day = friday - timedelta(days=1)
    assert cashback.due_reminder(streak, friday, 22) is None
