"""بابُ الكبتن إلى كراجه ومتجره (2026-08-22).

**والمِلكيّةُ لا تُكتب إلا من `services/vehicle_skins.py`** — لا من راوتر
ولا من مهمّةٍ دورية: بابان يكتبان مِلكيّةً يختلفان في شرطٍ واحدٍ يوماً ما،
وهو الشكلُ الثامن.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/vehicle-skins", tags=["vehicle-skins"])
