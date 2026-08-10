from __future__ import annotations

import uuid

from fastapi import APIRouter, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto import get_cipher
from app.core.deps import AdminUser, DbSession
from app.core.exceptions import Conflict, NotFound
from app.models.enums import ProviderKey
from app.models.provider_credential import ProviderCredential
from app.models.user import User
from app.schemas.provider import (
    ProviderCatalogOut,
    ProviderCredentialOut,
    ProviderCredentialUpsert,
    ProviderFieldOut,
    ProviderSpecOut,
    ProviderTestRequest,
    ProviderTestResult,
)
from app.services.providers import credentials as credentials_service, health
from app.services.providers.registry import PROVIDERS, get_spec

# صفحة العقود لـ admin حصراً — support لا يراها إطلاقاً (SPEC القسم 13/8)
router = APIRouter(prefix="/admin/providers", tags=["admin"])


def _to_out(credential: ProviderCredential) -> ProviderCredentialOut:
    spec = get_spec(credential.provider_key)
    values = get_cipher().decrypt(credential.credentials)
    return ProviderCredentialOut(
        id=credential.id,
        provider_key=credential.provider_key,
        country_code=credential.country_code,
        is_active=credential.is_active,
        values=credentials_service.masked_values(spec, values),
        last_tested_at=credential.last_tested_at,
        updated_at=credential.updated_at,
    )


@router.get("", response_model=ProviderCatalogOut)
async def list_providers(_admin: AdminUser, session: DbSession) -> ProviderCatalogOut:
    """بطاقات المزودين وحقولها + العقود المحفوظة بقيم مقنّعة."""
    stored = await credentials_service.list_credentials(session)
    return ProviderCatalogOut(
        providers=[
            ProviderSpecOut(
                provider_key=spec.key,
                label=spec.label,
                per_country=spec.per_country,
                feature_key=spec.feature_key,
                fields=[
                    ProviderFieldOut(
                        key=field.key,
                        label=field.label,
                        secret=field.secret,
                        required=field.required,
                    )
                    for field in spec.fields
                ],
            )
            for spec in PROVIDERS.values()
        ],
        credentials=[_to_out(credential) for credential in stored],
    )


@router.put("/{provider_key}", response_model=ProviderCredentialOut)
async def upsert_provider_credential(
    provider_key: ProviderKey,
    payload: ProviderCredentialUpsert,
    admin: AdminUser,
    session: DbSession,
) -> ProviderCredentialOut:
    """حفظ عقد مزود — يشفَّر at rest وتُقنّع قيمه في الرد.

    تفعيل العقد يفعّل ميزته تلقائياً بلا نشر كود (SPEC القسم 15).
    """
    try:
        credential = await credentials_service.upsert(
            session,
            provider_key=provider_key,
            country_code=payload.country_code,
            values=payload.values,
            is_active=payload.is_active,
            actor=admin,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise Conflict("يوجد عقد محفوظ لهذا المزود بنفس النطاق") from exc

    await session.refresh(credential)
    return _to_out(credential)


async def _set_active(
    credential_id: uuid.UUID,
    is_active: bool,
    admin: User,
    session: AsyncSession,
) -> ProviderCredentialOut:
    credential = await session.get(ProviderCredential, credential_id)
    if credential is None:
        raise NotFound("العقد غير موجود")

    await credentials_service.set_active(
        session, credential, is_active=is_active, actor=admin
    )
    await session.commit()
    await session.refresh(credential)
    return _to_out(credential)


@router.post("/{credential_id}/test", response_model=ProviderTestResult)
async def test_provider_credential(
    credential_id: uuid.UUID,
    payload: ProviderTestRequest,
    admin: AdminUser,
    session: DbSession,
) -> ProviderTestResult:
    """زرّ «اختبار الاتصال» في بطاقة العقد (SPEC القسم 13/7).

    يعود 200 حتى حين يفشل الاختبار: المشرف سأل فعرف، والنصُّ هو الفائدة.
    ويعمل على عقدٍ **غير مفعّل** عمداً — يُختبر قبل أن يُفتح لا بعد.
    """
    credential = await session.get(ProviderCredential, credential_id)
    if credential is None:
        raise NotFound("العقد غير موجود")

    result = await health.test_credential(
        session, credential, actor=admin, test_phone=payload.test_phone
    )
    await session.commit()
    await session.refresh(credential)
    return ProviderTestResult(
        ok=result.ok, detail=result.detail, credential=_to_out(credential)
    )


@router.post("/{credential_id}/activate", response_model=ProviderCredentialOut)
async def activate_provider_credential(
    credential_id: uuid.UUID, admin: AdminUser, session: DbSession
) -> ProviderCredentialOut:
    return await _set_active(credential_id, True, admin, session)


@router.post("/{credential_id}/deactivate", response_model=ProviderCredentialOut)
async def deactivate_provider_credential(
    credential_id: uuid.UUID, admin: AdminUser, session: DbSession
) -> ProviderCredentialOut:
    return await _set_active(credential_id, False, admin, session)


@router.delete("/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider_credential(
    credential_id: uuid.UUID, admin: AdminUser, session: DbSession
) -> None:
    credential = await session.get(ProviderCredential, credential_id)
    if credential is None:
        raise NotFound("العقد غير موجود")

    await credentials_service.delete(session, credential, actor=admin)
    await session.commit()
