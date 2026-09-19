"""كبتنُ جولةِ القياس على الإنتاج — **بإذنٍ صريحٍ من المالك 2026-08-22**.

**ولمَ سكربتٌ لا أوامرُ SQL متفرّقة**: الاعتمادُ يمرّ بـ`drivers.approve` —
**البابِ الوحيد** — فيكتب قيدَ التدقيق وينتقل بالحالة كما ينتقل بها أيُّ
اعتمادٍ حقيقيّ. **وما يُتجاوَز يُسمّى في الكود لا يُمرَّر صامتاً.**

**والتجاوزان اثنان لا أكثر، وكلاهما شرطٌ قبل الباب لا الباب نفسُه:**

١) **`phone_verified_at` يُكتب بلا رمز.** والسببُ مقيسٌ لا اختيار: الأردنُ على
   الإنتاج ينشر `verification: firebase`، وفايربيس يردّ
   `auth/billing-not-enabled`، و`whatsapp_otp_enabled/JO` **مطفأٌ بقرار
   المالك** (§27.5 — الرقمُ المرسِل بريطانيٌّ عارٍ). **فالتحققُ مشترطٌ
   ومستحيل**، ولا سبيلَ إلى رقمٍ مُثبتٍ من داخل النظام.

   **وأثرُه يُقال**: `drivers.approve` يشترط الإثباتَ لأن رقمَ الكبتن هو ما
   تصله حوالاتُ كليك — **فهذا الحسابُ لا يُرسَل إليه مالٌ حقيقيّ**، وهو
   حسابُ قياسٍ يُغلق بعد الجولة.

٢) **المستنداتُ الستُّ تُكتب معتمدةً بلا ملفّات.** والمراجعةُ الحقيقيةُ فعلُ
   إنسانٍ يقرأ صورة؛ ولا صورةَ هنا. **فتُكتب `file_path` فارغةً بقصد** كي
   يُقرأ الصفُّ على حقيقته: اعتمادٌ إداريٌّ لجولةِ قياس، لا وثيقةٌ رُوجعت.

**ولا تجاوزَ ثالث**: الحسابُ يُنشأ بـ`create_account`، والمركبةُ بخدمتها،
والاعتمادُ بـ`drivers.approve`، والشحنُ بـ`wallet.record` — فكلُّ ما يُكتب
يمرّ ببابه ويحمل قيدَه.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime
from decimal import Decimal

sys.path.insert(0, "/app")

from sqlalchemy import select  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models.driver import Driver, DriverDocument, required_document_types  # noqa: E402
from app.models.enums import (  # noqa: E402
    CountryCode,
    DocumentReviewStatus,
    UserRole,
    VehicleCategory,
    WalletOwnerType,
    WalletTransactionType,
)
from app.models.user import User  # noqa: E402
from app.models.enums import AccountKind  # noqa: E402
from app.models.vehicle import Vehicle  # noqa: E402
from app.schemas.auth import RegisterRequest  # noqa: E402
from app.services import wallet  # noqa: E402
from app.services import drivers as drivers_service  # noqa: E402
from app.services.auth.base import create_account  # noqa: E402

PHONE = "+962790001001"
PASSWORD = os.environ["ROUND_CAPTAIN_PASSWORD"]
NAME = "كبتنُ جولةِ القياس"
#: **٣٥٫٠٠٠ لا رقمٌ مستدير**: أغلى مركبةٍ في الكتالوج + هامشٌ لمركبةٍ ثانية.
#: يُعاد حسابُه من الكتالوج قبل الكتابة، ولا يُكتب رقماً في نصّ.
FALLBACK_TOPUP = Decimal("35.000")


async def main() -> None:
    async with SessionLocal() as session:
        existing = await session.scalar(select(User).where(User.phone == PHONE, User.account_kind == AccountKind.TAXO))
        if existing is not None:
            print(f"الحسابُ موجودٌ سلفاً: {PHONE} — لا يُنشأ ثانيةً")
            return

        admin = await session.scalar(
            select(User).where(User.role == UserRole.ADMIN).limit(1)
        )
        if admin is None:
            raise SystemExit("لا مشرفَ على الإنتاج — والاعتمادُ يحتاج فاعلاً يُسجَّل")

        # ── الحساب: البابُ الحقيقيّ ──────────────────────────────────────
        # **التجاوزُ الأول مسمّى**: `phone_verified_at` يُمرَّر بلا رمز.
        user = await create_account(
            session,
            phone=PHONE,
            data=RegisterRequest(
                phone=PHONE,
                password=PASSWORD,
                name=NAME,
                country_code=CountryCode.JO,
                role=UserRole.DRIVER,
            ),
            password_hash=hash_password(PASSWORD),
            phone_verified_at=datetime.now(UTC),
        )
        await session.flush()

        driver = await session.scalar(select(Driver).where(Driver.user_id == user.id))
        if driver is None:
            raise SystemExit("أُنشئ الحسابُ بلا صفِّ كبتن — يُوقَف")

        session.add(
            Vehicle(
                driver_id=driver.id,
                make="Toyota",
                model="Corolla",
                color="أبيض",
                plate_number="AMM-9001",
                year=2020,
                category=VehicleCategory.ECONOMY,
            )
        )

        # ── التجاوزُ الثاني مسمّى: مستنداتٌ معتمدةٌ بلا ملفّات ────────────
        # **والقائمةُ تُقرأ من الدالّة لا من الثابت** — أمسكه الحارسُ في أوّل
        # تشغيل: الصورةُ الشخصيةُ مطلوبةٌ لمن ليس مُعفى (البند ٥٢)، والثابتُ
        # `REQUIRED_DOCUMENT_TYPES` لا يحملها. **فالتفافٌ عليها كان سيُنتج
        # كبتناً لا يشبه أيَّ كبتنٍ حقيقيّ** — وهو ما تُقاس به الجولة.
        for doc_type in required_document_types(gender_verified_female=False):
            session.add(
                DriverDocument(
                    driver_id=driver.id,
                    doc_type=doc_type,
                    review_status=DocumentReviewStatus.APPROVED,
                    # **فارغةٌ بقصدٍ لا سهواً**: لا ملفَّ ولا حجمَ ولا نوع،
                    # فيُقرأ الصفُّ على حقيقته — اعتمادٌ إداريٌّ لا وثيقةٌ رُوجعت.
                    file_path="",
                    content_type="",
                    size_bytes=0,
                    reviewed_by=admin.id,
                    reviewed_at=datetime.now(UTC),
                    review_note="اعتمادٌ إداريٌّ لجولةِ قياسٍ — لا ملفَّ ولا مراجعة",
                )
            )
        await session.flush()

        # ── الاعتماد: البابُ الوحيد، بحارسيه اللذين استُوفيا أعلاه ───────
        await drivers_service.approve(session, driver=driver, actor=admin)

        # ── الشحن: قيدٌ في الدفتر بسببٍ مكتوب ───────────────────────────
        await wallet.record(
            session,
            owner=user,
            owner_type=WalletOwnerType.DRIVER,
            amount=FALLBACK_TOPUP,
            tx_type=WalletTransactionType.ADJUSTMENT,
            # **السببُ يُكتب في الصفِّ لا يُترك للذاكرة** — ومن يقرأ الدفترَ
            # بعد شهرٍ يجد لماذا دخل هذا المبلغُ ومن أذِن به.
            reference="شحنُ جولةِ قياسٍ بإذن المالك 2026-08-22 — لشراء مركبةٍ واحدةٍ على الأقل",
            created_by=admin.id,
            idempotency_key=f"round-topup:{user.id}",
        )

        await session.commit()
        balance = await wallet.balance(session, user.id, WalletOwnerType.DRIVER)
        print(f"✓ الحساب : {PHONE} · {NAME}")
        print(f"✓ الحالة : {driver.status.value}")
        print(f"✓ الرصيد : {balance}")


asyncio.run(main())
