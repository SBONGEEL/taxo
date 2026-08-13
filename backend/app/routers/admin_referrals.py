"""إحالاتُ السائقات في اللوحة — `admin` حصراً (القسم 9.1/13، المرحلة 12-ح).

**ولا `StaffUser`**: مبلغُ الحافز قرارٌ ماليٌّ لا إجراءُ دعمٍ فني — كمفتاح
العمولة وسقف الكوبون بالضبط (القسم 13/8).

**ولا زرَّ «ادفع الآن»**: الدفعُ مهمةٌ دورية تقيس الشروطَ بنفسها، وزرٌّ يدفع
يدوياً هو بابٌ ثانٍ للمال يتجاوز الشروطَ التي يحرسها الأول. وإن أراد المشرفُ
تعويضاً استثنائياً فبابُه `adjustment` في محفظة الكبتن — حيث يُكتب سببُه ويدخل
سجلَّ التدقيق.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.core.deps import AdminUser, DbSession, StaffUser
from app.models.driver import Driver
from app.models.enums import AuditAction, CountryCode
from app.models.referral import DriverReferral
from app.models.user import User
from app.schemas.referral import (
    AdminReferralRow,
    ReferralSummaryOut,
    ReferralSettingsIn,
    ReferralSettingsOut,
)
from app.services import audit, referrals as referrals_service

router = APIRouter(prefix="/admin/referrals", tags=["admin"])


@router.get("", response_model=list[AdminReferralRow])
async def list_referrals(
    _staff: StaffUser,
    session: DbSession,
    country_code: CountryCode | None = None,
    rewarded: bool | None = Query(
        default=None, description="المدفوعُ وحده أو غيرُ المدفوع وحده"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AdminReferralRow]:
    """جدولُ الإحالات بحال كلِّ صفٍّ. **قراءةٌ يملكها الدعمُ أيضاً**: سؤالُ «لِمَ
    لم تصل مكافأتي؟» سؤالُ دعمٍ لا قرارٌ ماليّ — والكتابةُ وحدها `admin`.
    """
    referrer = User.__table__.alias("referrer_user")
    referred = User.__table__.alias("referred_user")
    referrer_driver = Driver.__table__.alias("referrer_driver")
    referred_driver = Driver.__table__.alias("referred_driver")

    stmt = (
        select(
            DriverReferral,
            referrer.c.name,
            referrer.c.phone,
            referrer.c.country_code,
            referred.c.name,
            referred.c.phone,
        )
        .join(
            referrer_driver,
            referrer_driver.c.id == DriverReferral.referrer_driver_id,
        )
        .join(referrer, referrer.c.id == referrer_driver.c.user_id)
        .join(
            referred_driver,
            referred_driver.c.id == DriverReferral.referred_driver_id,
        )
        .join(referred, referred.c.id == referred_driver.c.user_id)
        .order_by(DriverReferral.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if country_code is not None:
        # **دولةُ المُحيلة هي المقياس**: المكافأةُ تدخل محفظتَها وبعملةِ بلدها،
        # فالفرزُ بدولةِ المُحالة يعرض صفوفاً لا تُدفع من ميزانية هذا السوق
        stmt = stmt.where(referrer.c.country_code == country_code)
    if rewarded is True:
        stmt = stmt.where(DriverReferral.rewarded_at.is_not(None))
    elif rewarded is False:
        stmt = stmt.where(DriverReferral.rewarded_at.is_(None))

    rows = (await session.execute(stmt)).all()

    # **سياسةٌ واحدةٌ لكل دولةٍ لا لكل صف**: الدولتان اثنتان وصفحةُ الجدول
    # خمسون صفاً، فقراءةُ السياسة لكل صفٍّ خمسون استعلاماً لجوابين
    policies: dict[CountryCode, referrals_service.Policy] = {}
    for _referral, _n, _p, rer_country, _n2, _p2 in rows:
        if rer_country not in policies:
            policies[rer_country] = await referrals_service.policy_for(
                session, rer_country
            )

    # **وحالُ الصفحة باستعلامين** لا ثلاثةٍ لكل صف (نفسُ شكل `payment_summaries`).
    # والحدُّ يختلف بين سوقين، فتُقاس كلُّ مجموعةٍ بحدِّها
    progress_by_id: dict = {}
    for country, policy in policies.items():
        subset = [row[0] for row in rows if row[3] == country]
        progress_by_id |= await referrals_service.progress_many(
            session, subset, required_rides=policy.required_rides
        )

    out: list[AdminReferralRow] = []
    for referral, rer_name, rer_phone, rer_country, red_name, red_phone in rows:
        progress = progress_by_id[referral.id]
        out.append(
            AdminReferralRow(
                id=referral.id,
                created_at=referral.created_at,
                referrer_name=rer_name,
                referrer_phone=rer_phone,
                referred_name=red_name,
                referred_phone=red_phone,
                code_used=referral.code_used,
                driver_approved=progress.driver_approved,
                gender_ready=progress.gender_ready,
                rides_done=progress.rides_done,
                rides_required=progress.rides_required,
                qualifies=progress.qualifies,
                rewarded=progress.rewarded,
                reward_amount=referral.reward_amount,
                reward_currency=referral.reward_currency,
                rewarded_at=referral.rewarded_at,
            )
        )
    return out


@router.get("/summary", response_model=ReferralSummaryOut)
async def summary(
    _staff: StaffUser, session: DbSession, country_code: CountryCode
) -> ReferralSummaryOut:
    """مجموعُ ما دُفع وعددُ ما ينتظر — **مجموعٌ في القاعدة** (القسم 14).

    وجمعُ صفحةٍ مقصوصةٍ في المتصفح يعرض «مجموع الصفحة» تحت عنوانٍ يقول
    «المجموع» — نفسُ سببِ وجود `services/stats.py`.
    """
    referrer = User.__table__.alias("summary_referrer")
    referrer_driver = Driver.__table__.alias("summary_referrer_driver")
    scoped = (
        select(DriverReferral)
        .join(
            referrer_driver,
            referrer_driver.c.id == DriverReferral.referrer_driver_id,
        )
        .join(referrer, referrer.c.id == referrer_driver.c.user_id)
        .where(referrer.c.country_code == country_code)
        .subquery()
    )
    total = await session.scalar(
        select(func.coalesce(func.sum(scoped.c.reward_amount), 0))
    )
    rewarded_count = await session.scalar(
        select(func.count()).select_from(scoped).where(scoped.c.rewarded_at.is_not(None))
    )
    pending_count = await session.scalar(
        select(func.count()).select_from(scoped).where(scoped.c.rewarded_at.is_(None))
    )
    return ReferralSummaryOut(
        country_code=country_code,
        total_rewarded=Decimal(total or 0),
        rewarded_count=int(rewarded_count or 0),
        pending_count=int(pending_count or 0),
    )


@router.get("/settings", response_model=ReferralSettingsOut)
async def get_settings(
    _staff: StaffUser, session: DbSession, country_code: CountryCode
) -> ReferralSettingsOut:
    row = await referrals_service.ensure_settings(session, country_code)
    await session.commit()
    return ReferralSettingsOut(
        country_code=country_code,
        reward_amount=row.reward_amount,
        required_rides=row.required_rides,
    )


@router.put("/settings", response_model=ReferralSettingsOut)
async def update_settings(
    payload: ReferralSettingsIn,
    admin: AdminUser,
    session: DbSession,
    country_code: CountryCode,
) -> ReferralSettingsOut:
    """مبلغُ الحافز وحدُّ الرحلات. **والتغييرُ يحكم ما يأتي لا ما دُفع**: المدفوعُ
    مجمَّدٌ على صفِّه، وحدُّ الرحلاتِ الجديد يعيد تقييمَ غيرِ المدفوع كلِّه.
    """
    row = await referrals_service.update_settings(
        session,
        country=country_code,
        reward_amount=payload.reward_amount,
        required_rides=payload.required_rides,
    )
    await audit.record(
        session,
        actor=admin,
        action=AuditAction.UPDATE,
        entity_type="referral_settings",
        entity_id=row.id,
        details={
            "country": country_code.value,
            "fields": [
                name
                for name, value in (
                    ("reward_amount", payload.reward_amount),
                    ("required_rides", payload.required_rides),
                )
                if value is not None
            ],
        },
    )
    await session.commit()
    return ReferralSettingsOut(
        country_code=country_code,
        reward_amount=row.reward_amount,
        required_rides=row.required_rides,
    )
