"""حساباتُ اختبار الحمل على الإنتاج (SPEC §٧٥) — **هويّةٌ محجوزةٌ موسومة، وجلساتٌ تُصدَر على الخادم بلا رسالة تحقّق**.

    docker compose … run --rm --no-deps --user "$(id -u):$(id -g)" -v /home/taxo/secrets:/out backend \\
      python -m scripts.stress_provision --captains 100 --riders 200 --tokens-file /out/stress-tokens-1.json --apply

* **الهويّة**: موسومٌ بالتجربة (`is_test`) **ورقمُه في النطاق المحجوز** «+962 719…» (`services/stress.STRESS_PHONE_PREFIX`): الكباتنُ
  `+9627190nnnnn` والركّابُ `+9627195nnnnn` — **فيُعثر على كلِّ صفٍّ لهم ويُحذف** (`stress_cleanup`). **وعالمُ التجربة معزول**: لا يُعرض
  كبتنُ تجربةٍ على راكبٍ حقيقيٍّ ولا العكس (`dispatch`، SPEC §٦٥-ج).
* **لا رسالةَ تحقّق ولا طريقَ دخولٍ مختصر**: الرقمُ مؤكَّدٌ عند الإنشاء (لا يملكه أحد)، **وكلمةُ المرور مجهولةٌ لكلِّ أحد** (بصمةُ سرٍّ
  عشوائيٍّ يُرمى)، **والجلسةُ تُصدَر بباب الجلسات نفسِه** (`issue_token_pair`) وتُجدَّد ببابها المعتاد (`/auth/refresh`).
* **الكبتن**: مركبةٌ اقتصاديّة ووثائقُه معتمَدة واعتمادُه ببابه، **واشتراكُ تجربةٍ بلا مال** (`record_manual`، صفر) — **فلا قيدَ في الدفتر**.
* **تزايديّ**: يُكمل العددَ المطلوب ولا يُنشئ ما وُجد، **ويُصدر جلساتٍ لكلِّ المطلوبين** إلى ملفٍّ جديدٍ بإذن 600 (لا يُطبع رمز).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, update  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.driver import Driver, DriverDocument, required_document_types  # noqa: E402
from app.models.enums import (  # noqa: E402
    CountryCode,
    DocumentReviewStatus,
    PaymentMethod,
    UserRole,
    VehicleCategory,
)
from app.models.subscription import SubscriptionPlan  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.vehicle import Vehicle  # noqa: E402
from app.schemas.auth import RegisterRequest  # noqa: E402
from app.services import drivers as drivers_service  # noqa: E402
from app.services import stress  # noqa: E402
from app.services import subscriptions as subscriptions_service  # noqa: E402
from app.services import token_service  # noqa: E402
from app.services.auth.base import create_account  # noqa: E402
from scripts.provision_test_accounts import ProvisionRefused, _check_secrets_path  # noqa: E402

COUNTRY = CountryCode.JO
CAPTAIN_BASE = "0"
RIDER_BASE = "5"
REFERENCE = "اختبارُ حمل — لا مال (SPEC §٧٥)"
REVIEW_NOTE = "اختبارُ حمل — حسابٌ موسومٌ يُحذف بعده (SPEC §٧٥)"
BATCH = 50


def phone_of(role: UserRole, index: int) -> str:
    base = CAPTAIN_BASE if role is UserRole.DRIVER else RIDER_BASE
    return f"{stress.STRESS_PHONE_PREFIX}{base}{index:05d}"


async def _plan(session: AsyncSession) -> SubscriptionPlan:
    plan = await session.scalar(
        select(SubscriptionPlan)
        .where(SubscriptionPlan.country_code == COUNTRY, SubscriptionPlan.is_active.is_(True))
        .order_by(SubscriptionPlan.price.desc())
        .limit(1)
    )
    if plan is None:
        raise ProvisionRefused("لا خطةَ اشتراكٍ فعّالةٌ في الأردن — وكبتنٌ بلا اشتراكٍ لا يصله عرض")
    return plan


async def _create(session: AsyncSession, role: UserRole, index: int, password_hash: str) -> User:
    phone = phone_of(role, index)
    label = "كبتن" if role is UserRole.DRIVER else "راكب"
    user = await create_account(
        session,
        phone=phone,
        data=RegisterRequest(
            phone=phone, password=secrets.token_urlsafe(18) + "aA1!", name=f"حمل {label} {index}",
            country_code=COUNTRY, role=role,
        ),
        password_hash=password_hash,
        phone_verified_at=datetime.now(UTC),
    )
    await session.execute(update(User).where(User.id == user.id).values(is_test=True))
    await session.flush()
    await session.refresh(user)
    return user


async def _make_captain(session: AsyncSession, user: User, index: int, plan: SubscriptionPlan) -> Driver:
    driver = await session.scalar(select(Driver).where(Driver.user_id == user.id))
    if driver is None:
        raise ProvisionRefused("حسابُ كبتنٍ بلا صفِّ كبتن — يُوقَف")
    session.add(
        Vehicle(driver_id=driver.id, make="Toyota", model="Corolla", year=2020, color="أبيض",
                plate_number=f"STR-{index:05d}", category=VehicleCategory.ECONOMY)
    )
    stamped = datetime.now(UTC)
    for doc_type in required_document_types(gender_verified_female=False):
        session.add(
            DriverDocument(driver_id=driver.id, doc_type=doc_type, review_status=DocumentReviewStatus.APPROVED,
                           file_path="", content_type="", size_bytes=0, reviewed_by=None, reviewed_at=stamped,
                           review_note=REVIEW_NOTE)
        )
    await session.flush()
    await drivers_service.approve(session, driver=driver, actor=None)  # type: ignore[arg-type]
    await subscriptions_service.record_manual(
        session, driver=driver, user=user, plan_id=plan.id, method=PaymentMethod.CASH, amount_paid=Decimal(0),
        reference=REFERENCE, actor=None,  # type: ignore[arg-type]
    )
    await session.flush()
    return driver


def _write_tokens(path: Path, rows: list[dict]) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(rows, handle)


async def provision(*, captains: int, riders: int, tokens_file: Path | None, write: bool, session_factory=SessionLocal) -> dict:
    if tokens_file is not None:
        _check_secrets_path(tokens_file)
    # **كلمةٌ لا يعرفها أحد** — بصمةُ سرٍّ يُرمى، واحدةٌ للجميع (بصمةٌ لكلِّ حسابٍ آلافُ الثواني بلا فائدة)
    password_hash = hash_password(secrets.token_urlsafe(32))
    created = {"captains": 0, "riders": 0}
    rows: list[dict] = []
    async with session_factory() as session:
        plan = await _plan(session)
        for role, count in ((UserRole.DRIVER, captains), (UserRole.RIDER, riders)):
            for index in range(1, count + 1):
                phone = phone_of(role, index)
                user = await session.scalar(select(User).where(User.phone == phone))
                if user is None:
                    user = await _create(session, role, index, password_hash)
                    if role is UserRole.DRIVER:
                        await _make_captain(session, user, index, plan)
                    created["captains" if role is UserRole.DRIVER else "riders"] += 1
                elif not stress.is_stress_account(user):
                    raise ProvisionRefused(f"رقمٌ في النطاق المحجوز لحسابٍ غيرِ موسوم (…{phone[-4:]}) — يُوقَف ولا يُمسّ")
                driver_id = None
                if role is UserRole.DRIVER:
                    driver_id = await session.scalar(select(Driver.id).where(Driver.user_id == user.id))
                rows.append({"role": role.value, "i": index, "user_id": str(user.id),
                             "driver_id": str(driver_id) if driver_id else None, "user": user})
                if index % BATCH == 0 and write:
                    await session.commit()
        if not write:
            await session.rollback()
            return {**created, "tokens": 0}
        await session.commit()
        if tokens_file is not None:
            out = []
            for row in rows:
                user = await session.get(User, row["user"].id)
                pair = await token_service.issue_token_pair(session, user)
                out.append({k: v for k, v in row.items() if k != "user"} | {"access": pair.access_token, "refresh": pair.refresh_token})
            _write_tokens(tokens_file, out)
    return {**created, "tokens": len(rows)}


def main() -> int:
    parser = argparse.ArgumentParser(description="حساباتُ اختبار الحمل (SPEC §٧٥)")
    parser.add_argument("--captains", type=int, required=True)
    parser.add_argument("--riders", type=int, required=True)
    parser.add_argument("--tokens-file", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        result = asyncio.run(provision(captains=args.captains, riders=args.riders, tokens_file=args.tokens_file, write=args.apply))
    except ProvisionRefused as exc:
        print(f"✗ {exc}")
        return 1
    print(f"✓ أُنشئ {result['captains']} كبتناً و{result['riders']} راكباً · جلساتٌ: {result['tokens']}"
          + ("" if args.apply else " (معاينة — لم يُكتب شيء)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
