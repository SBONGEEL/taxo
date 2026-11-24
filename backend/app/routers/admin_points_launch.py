"""**اللوحة: نقاطُ الالتزام وحملةُ الإطلاق وعروضُ الركاب** (§١١٤، أمرُ المالك ٢٠٢٦-١١-٢٤ السادس).

**كلُّ مفتاحٍ مطفأٌ حتى يضع المالكُ القيم**، وكلُّ تعديلٍ بقيد تدقيقٍ يحمل القديمَ والجديد. والقراءةُ للطاقم، والكتابةُ لصلاحيّة الإعدادات.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Query, status

from app.core.deps import DbSession, RedisDep, SettingsWriter, StaffUser
from app.models.enums import CountryCode
from app.schemas.points_launch import (
    CaptainDiscountsOut,
    CommitmentReportRow,
    CommitmentRuleOut,
    CommitmentRulePatch,
    DutyDayAdminOut,
    LaunchCampaignOut,
    LaunchCampaignPatch,
    LaunchGrantRow,
    PartnerCouponIn,
    PartnerCouponOut,
    RiderPerksOut,
    RiderPerksPatch,
)
from app.services import commitment, launch_campaign, rider_offers

router = APIRouter(prefix="/admin", tags=["admin-points-launch"])

#: **ما يجوز تفريغُه صراحةً** — القيمُ الاختياريّة وحدَها
_RULE_CLEARABLE = {
    "points_per_day",
    "points_per_credit_unit",
    "credit_unit_value",
    "daily_points_cap",
    "monthly_points_cap",
    "points_expiry_days",
    "credit_expiry_days",
}
_PERKS_CLEARABLE = {"free_cancel_seconds", "premium_after_rides"}


def _changes(payload, clearable: set[str]) -> dict:
    data = payload.model_dump(exclude={"clear"}, exclude_none=True)
    for key in getattr(payload, "clear", []):
        if key in clearable:
            data[key] = None
    return data


# ===================================================================== نقاطُ الالتزام


@router.get("/commitment/rule", response_model=CommitmentRuleOut)
async def get_commitment_rule(_staff: StaffUser, session: DbSession, country_code: CountryCode = Query()) -> CommitmentRuleOut:
    rule = await commitment.get_rule(session, country_code)
    await session.commit()
    return CommitmentRuleOut.model_validate(rule)


@router.patch("/commitment/rule", response_model=CommitmentRuleOut)
async def update_commitment_rule(
    payload: CommitmentRulePatch, admin: SettingsWriter, session: DbSession, redis: RedisDep, country_code: CountryCode = Query()
) -> CommitmentRuleOut:
    rule = await commitment.update_rule(
        session, redis, country=country_code, changes=_changes(payload, _RULE_CLEARABLE), actor=admin
    )
    await session.commit()
    return CommitmentRuleOut.model_validate(rule)


@router.get("/commitment/report", response_model=list[CommitmentReportRow])
async def commitment_report(
    _staff: StaffUser, session: DbSession, country_code: CountryCode = Query(), month: date | None = Query(default=None)
) -> list[CommitmentReportRow]:
    rows = await commitment.report(session, country=country_code, month=month or datetime.now(UTC).date())
    return [CommitmentReportRow.model_validate(row) for row in rows]


@router.get("/commitment/flags", response_model=list[DutyDayAdminOut])
async def commitment_flags(_staff: StaffUser, session: DbSession, country_code: CountryCode = Query()) -> list[DutyDayAdminOut]:
    return [DutyDayAdminOut.model_validate(row) for row in await commitment.flagged_days(session, country=country_code)]


@router.get("/commitment/drivers/{driver_id}/days", response_model=list[DutyDayAdminOut])
async def commitment_driver_days(driver_id: uuid.UUID, _staff: StaffUser, session: DbSession) -> list[DutyDayAdminOut]:
    return [DutyDayAdminOut.model_validate(row) for row in await commitment.driver_days(session, driver_id=driver_id)]


# ===================================================================== حملةُ الإطلاق


@router.get("/launch-campaign", response_model=LaunchCampaignOut)
async def get_launch_campaign(_staff: StaffUser, session: DbSession, country_code: CountryCode = Query()) -> LaunchCampaignOut:
    view = await launch_campaign.view(session, country_code)
    await session.commit()
    return LaunchCampaignOut.model_validate(view, from_attributes=True)


@router.patch("/launch-campaign", response_model=LaunchCampaignOut)
async def update_launch_campaign(
    payload: LaunchCampaignPatch, admin: SettingsWriter, session: DbSession, country_code: CountryCode = Query()
) -> LaunchCampaignOut:
    await launch_campaign.update(session, country=country_code, changes=payload.model_dump(exclude_none=True), actor=admin)
    view = await launch_campaign.view(session, country_code)
    await session.commit()
    return LaunchCampaignOut.model_validate(view, from_attributes=True)


@router.get("/launch-campaign/grants", response_model=list[LaunchGrantRow])
async def launch_campaign_grants(_staff: StaffUser, session: DbSession, country_code: CountryCode = Query()) -> list[LaunchGrantRow]:
    return [LaunchGrantRow.model_validate(row) for row in await launch_campaign.grants(session, country_code)]


# ===================================================================== عروضُ الركاب


@router.get("/rider-offers/perks", response_model=RiderPerksOut)
async def get_rider_perks(_staff: StaffUser, session: DbSession, country_code: CountryCode = Query()) -> RiderPerksOut:
    row = await rider_offers.perks(session, country_code)
    await session.commit()
    return RiderPerksOut.model_validate(row)


@router.patch("/rider-offers/perks", response_model=RiderPerksOut)
async def update_rider_perks(
    payload: RiderPerksPatch, admin: SettingsWriter, session: DbSession, country_code: CountryCode = Query()
) -> RiderPerksOut:
    row = await rider_offers.update_perks(
        session, country=country_code, changes=_changes(payload, _PERKS_CLEARABLE), actor=admin
    )
    await session.commit()
    return RiderPerksOut.model_validate(row)


@router.get("/rider-offers/coupons", response_model=list[PartnerCouponOut])
async def list_partner_coupons(_staff: StaffUser, session: DbSession, country_code: CountryCode = Query()) -> list[PartnerCouponOut]:
    return [PartnerCouponOut.model_validate(row) for row in await rider_offers.list_coupons(session, country_code, live_only=False)]


@router.post("/rider-offers/coupons", response_model=PartnerCouponOut, status_code=status.HTTP_201_CREATED)
async def create_partner_coupon(
    payload: PartnerCouponIn, admin: SettingsWriter, session: DbSession, country_code: CountryCode = Query()
) -> PartnerCouponOut:
    row = await rider_offers.save_coupon(session, country=country_code, data=payload.model_dump(exclude_none=True), actor=admin)
    await session.commit()
    return PartnerCouponOut.model_validate(row)


@router.patch("/rider-offers/coupons/{coupon_id}", response_model=PartnerCouponOut)
async def update_partner_coupon(
    coupon_id: uuid.UUID, payload: PartnerCouponIn, admin: SettingsWriter, session: DbSession, country_code: CountryCode = Query()
) -> PartnerCouponOut:
    row = await rider_offers.save_coupon(
        session, country=country_code, data=payload.model_dump(exclude_none=True), actor=admin, coupon_id=coupon_id
    )
    await session.commit()
    return PartnerCouponOut.model_validate(row)


@router.get("/rider-offers/captain-discounts", response_model=CaptainDiscountsOut)
async def captain_discounts(
    _staff: StaffUser, session: DbSession, driver_id: uuid.UUID = Query(), month: date | None = Query(default=None)
) -> CaptainDiscountsOut:
    return CaptainDiscountsOut.model_validate(
        await rider_offers.captain_discounts(session, driver_id=driver_id, month=month or datetime.now(UTC).date())
    )
