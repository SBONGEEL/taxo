"""**دورُ المالك يملك كلَّ صلاحيةٍ موجودة — وما يُضاف غداً** (SPEC §٧٦-ك/١، أمرُ المالك ٢٠٢٦-١٠-١٥).

صلاحيةٌ تُضاف إلى `AdminPermission` ولا يملكها دورُ المالك **تُسقط المجموعة** — والاختبارُ يقرأ التعدادَ نفسَه لا نسخةً منه.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models.admin_credential import AdminCredential
from app.models.admin_permission import AdminPermissionGrant
from app.models.audit import AdminAuditLog
from app.models.enums import AdminPermission, CountryCode, UserRole
from app.models.user import User
from app.models.user_role_grant import UserRoleGrant, has_role_clause
from app.services import permissions, security_settings
from scripts import provision_panel_owner as script
from scripts import provision_test_accounts


def test_the_owner_role_holds_every_permission_that_exists() -> None:
    owner = permissions.DEFAULTS[UserRole.OWNER]
    missing = sorted(p.value for p in AdminPermission if p not in owner)
    assert not missing, f"صلاحياتٌ لا يملكها دورُ المالك: {missing}"
    assert permissions.SENSITIVE <= owner
    assert owner == frozenset(AdminPermission)


def test_the_admin_default_is_unchanged() -> None:
    """**المشرفان القائمان كما هما** — دورُ المالك لا يوسّع `admin`، والحسّاسُ ما زال خارج افتراضه."""
    assert permissions.DEFAULTS[UserRole.ADMIN] == permissions.ALL - permissions.SENSITIVE
    assert not permissions.SENSITIVE & permissions.DEFAULTS[UserRole.ADMIN]


async def _owner(session_factory) -> User:
    async with session_factory() as session:
        user = User(
            phone=None,
            name="owner-under-test",
            role=UserRole.ADMIN,
            country_code=CountryCode.JO,
            role_grants=[UserRoleGrant(role=UserRole.ADMIN), UserRoleGrant(role=UserRole.OWNER)],
        )
        session.add(user)
        await session.commit()
        return user


@pytest.mark.asyncio
async def test_permission_rows_never_narrow_the_owner(session_factory) -> None:
    """**«أوّلُ صفٍّ يحكم» لا يسري على المالك** — منحٌ واحدٌ من المصفوفة كان سيضيّقه على تلك وحدَها."""
    user = await _owner(session_factory)
    async with session_factory() as session:
        session.add(AdminPermissionGrant(user_id=user.id, permission=AdminPermission.READ_ONLY, granted_by=None))
        await session.commit()
        fresh = await session.scalar(select(User).where(User.id == user.id))
        assert await permissions.for_user(session, fresh) == permissions.ALL
        assert await permissions.holds(session, fresh, AdminPermission.MARKETS_MANAGE)


@pytest.mark.asyncio
async def test_the_owner_must_enrol_a_second_factor_and_admins_are_untouched(session_factory) -> None:
    owner = await _owner(session_factory)
    async with session_factory() as session:
        admin = User(phone=None, name="plain-admin", role=UserRole.ADMIN, country_code=CountryCode.JO,
                     role_grants=[UserRoleGrant(role=UserRole.ADMIN)])
        session.add(admin)
        await session.commit()
        fresh_owner = await session.scalar(select(User).where(User.id == owner.id))
        # **المفتاحُ العامُّ مطفأ** (لا صفَّ إعداد) — والمالكُ مُلزَمٌ مع ذلك، والمشرفُ لا
        assert await security_settings.totp_required_for(session, fresh_owner) is True
        assert await security_settings.totp_required_for(session, admin) is False


@pytest.fixture
def secrets_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(provision_test_accounts, "_EPHEMERAL_ROOTS", ())
    return tmp_path


@pytest.mark.asyncio
async def test_provision_panel_owner(session_factory, secrets_dir: Path, capsys) -> None:
    async with session_factory() as session:
        admins_before = await session.scalar(select(func.count()).select_from(User).where(has_role_clause(UserRole.ADMIN)))

    preview, _ = await script.main_async(secrets_file=secrets_dir / "p.txt", write=False, session_factory=session_factory)
    assert preview and not (secrets_dir / "p.txt").exists()
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(User).where(has_role_clause(UserRole.OWNER))) == 0

    path = secrets_dir / "panel-owner.txt"
    _, user = await script.main_async(secrets_file=path, write=True, session_factory=session_factory)
    async with session_factory() as session:
        fresh = await session.scalar(select(User).where(User.id == user.id))
        assert fresh.name == "Mohammed Aldeeb" and fresh.phone is None and fresh.role is UserRole.ADMIN
        assert fresh.roles == frozenset({UserRole.ADMIN, UserRole.OWNER})
        assert await permissions.for_user(session, fresh) == permissions.ALL
        credential = await session.scalar(select(AdminCredential).where(AdminCredential.user_id == user.id))
        assert credential is not None and not credential.is_break_glass
        audits = list(await session.scalars(select(AdminAuditLog).where(AdminAuditLog.entity_id == user.id)))
        kinds = sorted(a.entity_type for a in audits if a.entity_type in ("user_role_grant", "panel_owner_account"))
        assert kinds == ["panel_owner_account", "user_role_grant", "user_role_grant"]
        assert all(a.details.get("granted_by") == script.GRANTED_BY for a in audits if a.entity_type in kinds)
        # **ولا يمسّ حساباً آخر** — المشرفون قبلَه كما هم، وزاد واحد
        assert await session.scalar(
            select(func.count()).select_from(User).where(has_role_clause(UserRole.ADMIN))
        ) == admins_before + 1

    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    content = path.read_text(encoding="utf-8").splitlines()
    password = next(line.split("=", 1)[1] for line in content if line.startswith("password="))
    username = next(line.split("=", 1)[1] for line in content if line.startswith("username="))
    out = capsys.readouterr().out
    assert len(password) >= 32 and password not in out and username not in out
    assert credential.username == username

    with pytest.raises(provision_test_accounts.ProvisionRefused):
        await script.main_async(secrets_file=secrets_dir / "again.txt", write=True, session_factory=session_factory)
