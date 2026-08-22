"""إدارةُ كتالوج المركبات في اللوحة (2026-08-22).

**وكلُّ بابٍ هنا له زرّ** — `check:doors` يحرسه.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/admin/vehicle-skins", tags=["admin"])
