"""**قاعدةُ الولاء** في اللوحة (البند ١٤، §٩٧/١٤) — يضعها المالكُ لكلِّ دولة، **وكلُّ تغييرٍ مدقَّق**، والأرقامُ من الخلفية."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.core.deps import DbSession, SettingsWriter, StaffUser
from app.core.exceptions import NotFound
from app.models.enums import AuditAction, CountryCode, WalletTransactionType
from app.models.loyalty import LoyaltyEarning, LoyaltyRule
from app.models.user import User
from app.models.wallet import WalletTransaction
from app.schemas.loyalty import LoyaltyRuleIn, LoyaltyRuleOut
from app.services import audit, loyalty, pricing

router = APIRouter(prefix="/admin/loyalty", tags=["admin-loyalty"])


async def _out(session, rule: LoyaltyRule) -> LoyaltyRuleOut:
    now = datetime.now(UTC)
    live = (
        select(LoyaltyEarning.rider_id, LoyaltyEarning.remaining)
        .join(User, User.id == LoyaltyEarning.rider_id)
        .where(User.country_code == rule.country_code, LoyaltyEarning.expires_at > now, LoyaltyEarning.remaining > 0)
        .subquery()
    )
    holders = await session.scalar(select(func.count(func.distinct(live.c.rider_id))))
    open_points = await session.scalar(select(func.coalesce(func.sum(live.c.remaining), 0)))
    redeemed = await session.scalar(
        select(func.coalesce(func.sum(WalletTransaction.amount), 0))
        .join(User, User.id == WalletTransaction.owner_id)
        .where(User.country_code == rule.country_code, WalletTransaction.type == WalletTransactionType.LOYALTY_REWARD)
    )
    return LoyaltyRuleOut(
        country_code=CountryCode(rule.country_code).value, points_per_ride=rule.points_per_ride, expiry_days=rule.expiry_days,
        silver_threshold=rule.silver_threshold, gold_threshold=rule.gold_threshold,
        silver_bonus_percent=rule.silver_bonus_percent, gold_bonus_percent=rule.gold_bonus_percent,
        redeem_points=rule.redeem_points, redeem_value=rule.redeem_value, holders=holders or 0, open_points=int(open_points),
        redeemed_value=pricing.as_money(Decimal(redeemed)),
    )


@router.get("", response_model=LoyaltyRuleOut | None)
async def get_rule(_staff: StaffUser, session: DbSession, country_code: CountryCode = Query()) -> LoyaltyRuleOut | None:
    rule = await loyalty.rule_for(session, country_code)
    return await _out(session, rule) if rule is not None else None


@router.put("", response_model=LoyaltyRuleOut)
async def put_rule(payload: LoyaltyRuleIn, admin: SettingsWriter, session: DbSession, country_code: CountryCode = Query()) -> LoyaltyRuleOut:
    rule, changes = await loyalty.save_rule(session, country_code, payload.model_dump())
    if not changes and rule is None:  # pragma: no cover
        raise NotFound()
    await audit.record(
        session, actor=admin, action=AuditAction.UPDATE, entity_type="loyalty_rule", entity_id=rule.id,
        details={"country_code": country_code.value}, changes=changes,
    )
    await session.commit()
    return await _out(session, rule)
