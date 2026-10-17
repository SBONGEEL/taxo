"""**عميلُ الدافع عند الوسيط — يُنشأ مرّةً ويُعاد** (SPEC §٧٦-ع/٢، أمرُ المالك ٢٠٢٦-١٠-١٧).

**ولا يوقف الدفعَ أبداً**: وسيطٌ بلا عملاء، أو مفتاحٌ مطفأ، أو إنشاءٌ تعذّر — يُدفع كما كان، وتسأل صفحةُ الوسيط بياناتِها. **فالعميلُ تسهيلٌ لا
شرط**، وفشلُه سطرٌ في السجلّ لا خطأٌ في وجه الدافع.

**ونداءُ الوسيط بلا قفلِ صفّ** — لا صفَّ مقفولاً هنا؛ **ودفعتان متزامنتان** قد تُنشئان عميلين عند الوسيط، فيُحفظ أوّلُهما (القيدُ الفريد)
ويُستعمل، والثاني يبقى عنده بلا ضرر.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gateway_customer import GatewayCustomer
from app.models.user import User
from app.services import payment_gateways

logger = logging.getLogger(__name__)


def _customer(owner: User) -> payment_gateways.CheckoutCustomer:
    return payment_gateways.CheckoutCustomer(
        full_name=owner.name or "", phone=owner.phone or "", email=getattr(owner, "email", None) or None
    )


async def _stored(session: AsyncSession, owner: User, integration: str, livemode: bool) -> GatewayCustomer | None:
    return await session.scalar(
        select(GatewayCustomer).where(
            GatewayCustomer.user_id == owner.id,
            GatewayCustomer.integration == integration,
            GatewayCustomer.livemode.is_(livemode),
        )
    )


async def customer_for(session: AsyncSession, gateway: payment_gateways.Gateway, owner: User) -> payment_gateways.CheckoutCustomer:
    """**بياناتُ الدافع ومعرّفُه عميلاً** — المحفوظُ إن كان، وإلا يُنشأ ويُحفظ؛ **وبلا معرّفٍ حين لا يُنشأ** (أعلاه)."""
    customer = _customer(owner)
    create = getattr(gateway, "create_customer", None)
    if create is None or not getattr(gateway, "send_customer", False):
        return customer
    livemode = not bool(getattr(gateway, "test_mode", False))
    row = await _stored(session, owner, gateway.name, livemode)
    if row is not None:
        return payment_gateways.CheckoutCustomer(customer.full_name, customer.phone, customer.email, row.external_id)
    try:
        external_id = await create(customer)
    except payment_gateways.GatewayError:
        logger.warning("gateway customer not created", extra={"integration": gateway.name, "user_id": str(owner.id)})
        return customer
    if not external_id:
        return customer
    try:
        async with session.begin_nested():
            session.add(
                GatewayCustomer(user_id=owner.id, integration=gateway.name, livemode=livemode, external_id=external_id)
            )
    except IntegrityError:
        # **دفعةٌ متزامنةٌ حفظت عميلَها قبلنا** — يُستعمل المحفوظ
        row = await _stored(session, owner, gateway.name, livemode)
        external_id = row.external_id if row is not None else external_id
    return payment_gateways.CheckoutCustomer(customer.full_name, customer.phone, customer.email, external_id)


async def forget(session: AsyncSession, gateway: payment_gateways.Gateway, owner: User) -> None:
    """**عميلٌ رفضه الوسيط** (حُذف عنده، أو مفتاحٌ تبدّل) — يُنسى معرّفُه فيُنشأ غيرُه في الدفعة التالية."""
    livemode = not bool(getattr(gateway, "test_mode", False))
    row = await _stored(session, owner, gateway.name, livemode)
    if row is not None:
        await session.delete(row)
        await session.flush()
