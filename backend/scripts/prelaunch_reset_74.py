"""تصفيرُ ما قبل الإطلاق (SPEC §٧٤-أ/١، §٧٤-ح) — **كلُّ رصيدٍ ودَينٍ ومعلَّقٍ إلى الصفر، بقيدٍ موسومٍ لا بحذف**.

**لا يُشغَّل إلا بنعم المالك** على ما وُجد من مالٍ حقيقيّ (الجزء ١/١: «إن وُجد مالٌ حقيقيٌّ يُوقَف التصفيرُ ويُنتظر»)، **وبعد نسخةٍ
محقَّقةٍ خارج الخادم**. وفي حاوية الخلفية، والأمرُ يذكر ملفاتِه كلَّها:

    docker compose --env-file .env -f docker-compose.yml -f docker-compose.prod-tunnel.yml \\
      run --rm --no-deps --user "$(id -u):$(id -g)" -v /home/taxo/backups:/out \\
      backend python -m scripts.prelaunch_reset_74 --export /out/prelaunch-<وقت>.json           # التصديرُ والمعاينة
    … backend python -m scripts.prelaunch_reset_74 --export /out/… --apply [--keep <معرّف>]    # الكتابة

## ما يفعله — في معاملةٍ واحدة، وبأبوابه

١. **التصدير أوّلاً** (`--export`، لازم): كلُّ محفظةٍ برصيدها، وكلُّ مستحقٍّ وسلفةٍ قائمَين، وعددُ كلِّ معلَّق — **بمعرّفاتٍ لا أسماءَ ولا
   أرقام** — في ملفٍّ جديدٍ بإذن 600 لا يُكتب فوقه، **يُحفظ مع النسخة**.
٢. **المستحقّاتُ القائمة** (عمولةُ رحلاتٍ قُبضت نقداً) **تُشطب** بـ`debts.write_off` — **والسلفُ القائمة** بـ`advances.write_off`. **ولا قيدَ
   في الدفتر لأيٍّ منهما**: لم يتحرّك مال — وهو نصُّ البابين.
٣. **كلُّ محفظةٍ رصيدُها غيرُ صفرٍ تُصفَّر بقيد تصحيحٍ واحد** مرجعُه **«تصفير ما قبل الإطلاق»** — بعكس رصيدها، **ولا يُحذف قيدٌ ولا يُعدَّل**.
٤. **والاشتراكاتُ لا تُمسّ** (الجزء ١/٤) — ولا جدولٌ غيرُ ما فوق.

## ما يقف عنده ولا يُصلحه

**معلَّقٌ لم يكن حين قِيس** — سحبٌ أو شحنٌ ينتظر، أو رسمُ إلغاءٍ معلَّق، أو دفعةٌ لم تُؤكَّد: **قِيس في ٢٠٢٦-١٠-١٣ أنها صفر**، فظهورُها
خبرٌ جديدٌ يُعرض على المالك ولا يُلغى من هنا. **والحالةُ نفسُها في المعاينة والكتابة.**

## و`--keep`

**مالٌ يقرّر المالكُ إبقاءه** (مالٌ حقيقيٌّ لكبتن مثلاً) يُستثنى بمعرّف صاحبه — **رصيدُه ومستحقّاتُه وسلفتُه معاً**، فلا تُشطب سلفةٌ
من تحت رصيدٍ أُبقي. **فلا يُقرّر السكربتُ عن المالك أيُّ مالٍ يُمحى**.

## وبعده — يُقاس لا يُفترض

يُعاد حسابُ كلِّ رصيدٍ ومستحقٍّ وسلفةٍ **من القاعدة** داخل المعاملة نفسِها قبل الالتزام: **غيرُ صفرٍ خارج `--keep` ⇒ تراجعٌ ولا شيءَ يُلتزم**.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.models.advance import DriverAdvance  # noqa: E402
from app.models.cancellation import RideCancellationCharge  # noqa: E402
from app.models.debt import DriverDebt  # noqa: E402
from app.models.driver import Driver  # noqa: E402
from app.models.enums import (  # noqa: E402
    AdvanceStatus,
    AuditAction,
    CancellationChargeStatus,
    DriverDebtStatus,
    PaymentStatus,
    TopupRequestStatus,
    WalletOwnerType,
    WalletTransactionType,
    WithdrawalStatus,
)
from app.models.payment import Payment  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.wallet import WalletTopupRequest, WalletTransaction, WithdrawalRequest  # noqa: E402
from app.services import advances, audit, debts, wallet  # noqa: E402

#: **علامةُ التصفير** بنصّ المالك — مرجعُ كلِّ قيدٍ وسببُ كلِّ شطب
RESET_MARK = "تصفير ما قبل الإطلاق"


class ResetRefused(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(slots=True)
class Snapshot:
    wallets: list[dict] = field(default_factory=list)
    debts: list[dict] = field(default_factory=list)
    advances: list[dict] = field(default_factory=list)
    pending: dict[str, int] = field(default_factory=dict)


async def _wallets(session: AsyncSession) -> list[tuple[uuid.UUID, WalletOwnerType, Decimal]]:
    rows = await session.execute(
        select(WalletTransaction.owner_id, WalletTransaction.owner_type, func.sum(WalletTransaction.amount))
        .group_by(WalletTransaction.owner_id, WalletTransaction.owner_type)
        .having(func.sum(WalletTransaction.amount) != 0)
        .order_by(WalletTransaction.owner_id)
    )
    return [(owner_id, WalletOwnerType(owner_type), Decimal(total)) for owner_id, owner_type, total in rows.all()]


async def snapshot(session: AsyncSession) -> Snapshot:
    snap = Snapshot()
    for owner_id, owner_type, balance in await _wallets(session):
        user = await session.get(User, owner_id)
        snap.wallets.append(
            {
                "owner_id": str(owner_id),
                "owner_type": owner_type.value,
                "country_code": user.country_code.value if user else None,
                "is_test": bool(user and user.is_test),
                "balance": str(balance),
            }
        )
    async def owner_of(driver_id: uuid.UUID) -> str:
        return str(await session.scalar(select(Driver.user_id).where(Driver.id == driver_id)))

    for debt in await session.scalars(select(DriverDebt).where(DriverDebt.status == DriverDebtStatus.OUTSTANDING)):
        snap.debts.append(
            {
                "id": str(debt.id),
                "driver_id": str(debt.driver_id),
                "user_id": await owner_of(debt.driver_id),
                "amount": str(debt.amount),
                "collected": str(debt.collected),
            }
        )
    for advance in await session.scalars(select(DriverAdvance).where(DriverAdvance.status == AdvanceStatus.OUTSTANDING)):
        repaid = await advances.repaid_amount(session, advance.id)
        snap.advances.append(
            {
                "id": str(advance.id),
                "driver_id": str(advance.driver_id),
                "user_id": await owner_of(advance.driver_id),
                "amount": str(advance.amount),
                "remaining": str(advance.amount - repaid),
            }
        )
    counts = {
        "withdrawal_requests": select(func.count()).select_from(WithdrawalRequest).where(
            WithdrawalRequest.status.in_([WithdrawalStatus.PENDING, WithdrawalStatus.APPROVED])
        ),
        "wallet_topup_requests": select(func.count()).select_from(WalletTopupRequest).where(
            WalletTopupRequest.status == TopupRequestStatus.PENDING
        ),
        "ride_cancellation_charges": select(func.count()).select_from(RideCancellationCharge).where(
            RideCancellationCharge.status == CancellationChargeStatus.PENDING
        ),
        "payments": select(func.count()).select_from(Payment).where(
            Payment.status.in_([PaymentStatus.PENDING, PaymentStatus.DISPUTED])
        ),
    }
    for name, query in counts.items():
        snap.pending[name] = int(await session.scalar(query) or 0)
    return snap


def _export(path: Path, snap: Snapshot, taken_at: str) -> None:
    """**ملفٌّ جديدٌ بإذن 600 ولا يُكتب فوق قائم** — قاعدةُ ملفّ الأسرار نفسُها: تصديرٌ خاطئُ المسار لا يمحو نسخة."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump({"taken_at": taken_at, "mark": RESET_MARK, **asdict(snap)}, handle, ensure_ascii=False, indent=1)
        handle.flush()
        os.fsync(handle.fileno())


async def reset(
    session: AsyncSession, *, keep: set[uuid.UUID], out: Callable[[str], None] = print
) -> Snapshot:
    """**يكتب ولا يلتزم** — الالتزامُ للمستدعي بعد أن يقيس."""
    before = await snapshot(session)
    surprises = {name: count for name, count in before.pending.items() if count}
    if surprises:
        raise ResetRefused(
            f"معلَّقٌ لم يكن حين قِيس: {surprises} — يُعرض على المالك ولا يُلغى من هنا"
        )

    def kept(row: dict) -> bool:
        if uuid.UUID(row["user_id"]) in keep:
            out(f"  = {row['id']}: مُبقًى بقرار المالك")
            return True
        return False

    for row in before.debts:
        if kept(row):
            continue
        debt = await session.get(DriverDebt, uuid.UUID(row["id"]), with_for_update=True, populate_existing=True)
        await debts.write_off(session, debt=debt, actor=None, reason=RESET_MARK)
        await audit.record(
            session, actor=None, action=AuditAction.UPDATE, entity_type="driver_debt", entity_id=debt.id,
            details={"status": debt.status.value, "reason": RESET_MARK},
        )
        out(f"  ✎ مستحقٌّ {row['id']}: {row['amount']} (حُصّل {row['collected']}) ← شُطب")
    for row in before.advances:
        if kept(row):
            continue
        await advances.write_off(session, advance_id=uuid.UUID(row["id"]), admin=None, reason=RESET_MARK)
        out(f"  ✎ سلفةٌ {row['id']}: بقي {row['remaining']} ← شُطبت")

    # **المحافظُ آخراً** — بعد أن يعود كلُّ مالٍ إلى موضعه
    for owner_id, owner_type, balance in await _wallets(session):
        if owner_id in keep:
            out(f"  = محفظة {owner_id} ({owner_type.value}): {balance} — مُبقاةٌ بقرار المالك")
            continue
        user = await session.get(User, owner_id)
        if user is None:
            raise ResetRefused(f"محفظةٌ بلا صاحب ({owner_id}) — يُوقَف")
        await wallet.record(
            session,
            owner=user,
            owner_type=owner_type,
            tx_type=WalletTransactionType.ADJUSTMENT,
            amount=-balance,
            reference=RESET_MARK,
        )
        await audit.record(
            session, actor=None, action=AuditAction.CREATE, entity_type="prelaunch_reset", entity_id=owner_id,
            details={"owner_type": owner_type.value, "type": WalletTransactionType.ADJUSTMENT.value},
        )
        out(f"  ✎ محفظة {owner_id} ({owner_type.value}{' · تجربة' if user.is_test else ''}): {balance} ← 0")
    await session.flush()

    # ── يُقاس لا يُفترض ──
    after = await snapshot(session)
    left = [row for row in after.wallets if uuid.UUID(row["owner_id"]) not in keep]
    debts_left = [row for row in after.debts if uuid.UUID(row["user_id"]) not in keep]
    advances_left = [row for row in after.advances if uuid.UUID(row["user_id"]) not in keep]
    if left or debts_left or advances_left or any(after.pending.values()):
        raise ResetRefused(f"بعد التصفير بقي ما ليس صفراً: {left[:3]} {debts_left[:3]} {advances_left[:3]} — تراجعٌ")
    return before


@dataclass(frozen=True, slots=True)
class Totals:
    wallets: int
    debts: int
    advances: int


async def main_async(
    *, export: Path, write: bool, keep: set[uuid.UUID], session_factory: Callable[[], AsyncSession] = SessionLocal
) -> Totals:
    taken_at = datetime.now(UTC).isoformat(timespec="seconds")
    async with session_factory() as session:
        before = await snapshot(session)
        _export(export, before, taken_at)
        print(f"صُدِّر: {len(before.wallets)} محفظة · {len(before.debts)} مستحقّ · {len(before.advances)} سلفة · المعلَّقات {before.pending}")
        await reset(session, keep=keep)
        if write:
            await session.commit()
            print(f"✓ صُفِّر والتُزم — «{RESET_MARK}»")
        else:
            await session.rollback()
            print("معاينةٌ — لم يُكتب شيء (أعد بـ--apply)")
        return Totals(len(before.wallets), len(before.debts), len(before.advances))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="تصفيرُ ما قبل الإطلاق (SPEC §74-ح)")
    parser.add_argument("--export", required=True, type=Path, help="ملفٌّ جديدٌ يُصدَّر إليه كلُّ رصيدٍ ودَينٍ ومعلَّقٍ قبل أيِّ كتابة")
    parser.add_argument("--apply", action="store_true", help="اكتب والتزم — وبدونه معاينةٌ لا تكتب")
    parser.add_argument("--keep", action="append", default=[], help="معرّفُ مستخدمٍ تُبقى محفظتُه بقرار المالك (يتكرّر)")
    args = parser.parse_args(argv)
    try:
        asyncio.run(main_async(export=args.export, write=args.apply, keep={uuid.UUID(value) for value in args.keep}))
    except (ResetRefused, FileExistsError) as refused:
        print(f"✗ {getattr(refused, 'message', refused)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
