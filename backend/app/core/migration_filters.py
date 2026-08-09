from __future__ import annotations

from typing import Any

from app.models import Base

# صورة postgis تضيف search_path يشمل tiger، فتظهر جداول الامتداد في الانعكاس.
# نتجاهل كل ما ليس من جداولنا حتى لا يقترح autogenerate إسقاطها.
EXCLUDED_SCHEMAS = {"tiger", "tiger_data", "topology"}
ALEMBIC_OWNED = {"alembic_version"}


def include_object(
    object_: Any, name: str | None, type_: str, reflected: bool, compare_to: Any
) -> bool:
    """يحصر مقارنة alembic في الجداول التي يملكها التطبيق.

    مشترك بين `alembic/env.py` واختبار تطابق الموديلات مع الترحيلات، حتى
    يقارن الاثنان بالمعايير نفسها.
    """
    metadata = Base.metadata

    if getattr(object_, "schema", None) in EXCLUDED_SCHEMAS:
        return False

    if type_ == "table":
        if reflected and name not in metadata.tables and name not in ALEMBIC_OWNED:
            return False
    elif type_ == "index" and reflected:
        if getattr(object_.table, "name", None) not in metadata.tables:
            return False

    return True
