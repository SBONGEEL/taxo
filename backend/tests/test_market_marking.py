"""**كلُّ صفٍّ يُعرف سوقُه بلا تخمين** (SPEC §٧٦-ي/ج/١ — قرارُ المالك ٢٠٢٦-١٠-١٥).

الجزائرُ تُفتح على الخادم الحاليّ **وتنتقل إلى خادمها لاحقاً** (§٧٣-أ/٤ مؤجَّلٌ لا ملغًى) — والنقلُ يختار صفوفَ السوق **بانضمامٍ محدَّد**:
جدولٌ يحمل `country_code`، أو يبلغه **بمفاتيحَ أجنبيّةٍ غيرِ قابلةٍ للفراغ** (`design/DZ-SEPARATION-PLAN.md`). **وما ليس بياناتِ مستخدمٍ في سوق**
(إعدادٌ عامّ · فهرس · قياسٌ بلا هويّة) **يُصرَّح باسمه وعلّته** — فجدولٌ جديدٌ بلا طريقٍ إلى سوقه ولا تصريحٍ يُسقط المجموعة.
**وقِيس على الإنتاج ٢٠٢٦-١٠-١٥**: صفرُ رابطٍ يعبر الأسواق (الرحلةُ وراكبُها وكبتنُها · الاشتراكُ وباقتُه · طلبُ الدفع ومستخدمُه · الإحالة).
"""

from __future__ import annotations

import ast
from collections import deque
from pathlib import Path

import app.models  # noqa: F401 — يُحمِّل الجداولَ كلَّها في البيانات الوصفيّة
from app.models.base import Base

APP_DIR = Path(__file__).resolve().parents[1] / "app"

#: **ليست بياناتِ مستخدمٍ في سوق** — تُنسخ إلى الخادم الجديد أو تبدأ فيه من جديد، **ولا تُفرز بالسوق**
GLOBAL = {
    "admin_audit_logs": "سجلُّ أفعال المشرفين — صفُّه يُردّ إلى سوقه من الكيان الذي يشير إليه (entity_type/entity_id)؛ وخطّةُ الفصل تنسخ ما يخصّ الجزائر",
    "app_releases": "إصداراتُ التطبيقين — عامّةٌ لكلِّ الأسواق",
    "backup_runs": "سجلُّ النسخ الاحتياطيّ لهذا الخادم",
    "backup_settings": "إعدادُ النسخ الاحتياطيّ لهذا الخادم",
    "badges": "فهرسُ الشارات — لا يخصّ مستخدماً",
    "broadcast_changes": "سجلُّ إعداد البثّ المتكيّف لهذا الخادم",
    "broadcast_settings": "إعدادُ البثّ المتكيّف لهذا الخادم",
    "error_events": "تقاريرُ الأعطال — بلا هويّة مستخدم (بصمةُ جهازٍ مموّهة)، وتُكنس بعد ٣٠/٩٠ يوماً؛ لا تُنقل",
    "error_group_devices": "أجهزةُ مجموعة العطل — بصماتٌ مموّهة، وتُكنس مع مجموعتها",
    "error_groups": "مجموعاتُ الأعطال — عطلٌ واحدٌ يجمع الأسواق؛ لا تُنقل",
    "exchange_rates": "أسعارُ الصرف — عامّة",
    "market_borders": "حدودٌ بين سوقين — تخصّ اثنين معاً بطبيعتها",
    "org_profile": "ملفُّ الشركة — عامّ",
    "otp_message_templates": "قوالبُ رسائل التحقّق — عامّة",
    "security_settings": "إعدادُ الأمان لهذا الخادم",
    "site_settings": "إعدادُ الموقع العامّ",
    "vehicle_skins": "فهرسُ أشكال المركبات — لا يخصّ مستخدماً",
    # **وضعُ الضيف** (SPEC §٧٦-ن/أ) — بُني على `master` بعد هذا الحارس فلم يُصنَّف (أمسكه CI حين دُمج الفرعان، ٢٠٢٦-١٠-١٧)
    "guest_sessions": "جلسةُ عرضٍ لا حساب — بلا هويّةٍ ولا سوق (دولةُ الشبكة وحدَها)، وتُمحى بعد ٣٠ يوماً؛ لا تُنقل",
    "guest_mode_settings": "مفتاحُ وضع الضيف لكلِّ تطبيق — صفٌّ عالميٌّ واحد",
}

#: **طريقٌ إلى السوق بمفتاحٍ قابلٍ للفراغ — بقصدٍ مكتوب**: الصفُّ ذو الحساب يصل سوقَه به، **والفارغُ صفٌّ بلا حسابٍ أصلاً**
NULLABLE_PATH = {
    "app_feedback": "`user_id` يصل `users` وسوقَه؛ **وملاحظةُ الضيف بلا حساب** (`guest_session_id`) فلا سوقَ لها — وتُمحى مع جلستها",
}

#: **`country_code` قابلٌ للفراغ بقصد** — الصفُّ بلا سوقٍ صفٌّ عامّ (لكلِّ الأسواق)، لا صفٌّ ضاع سوقُه
NULLABLE_COUNTRY = {
    "notification_campaigns": "حملةٌ بلا دولة تُرسل للأسواق كلِّها",
    "provider_credentials": "عقدٌ عامّ (Mapbox · الرسائل · FCM…) لكلِّ الأسواق",
    # **إشعاراتُ المالك** (SPEC §٨١) — سوقُ الحدث من سجلّه؛ **وملاحظةُ ضيفٍ من خارج الأسواق بلا سوق**. ولا تُنقل: تُكنس بعد ٩٠ يوماً
    "admin_alerts": "إشعارُ نشاطٍ سوقُه مجهول (ضيفٌ من شبكةٍ خارج الأسواق) — يُعرض «بلا سوق» ولا يُنسب إلى سوقٍ بالتخمين",
}

#: **إسنادُ سوقٍ لصفٍّ قائم** — موضعٌ واحدٌ معروف، وليس مستخدماً
COUNTRY_ASSIGNMENTS = {
    ("services/campaigns.py", "campaign"): "المشرفُ يعدّل دولةَ حملةٍ قبل إرسالها — إعدادٌ لا بياناتُ مستخدم",
}


def _direct() -> set[str]:
    return {t.name for t in Base.metadata.sorted_tables if "country_code" in t.c}


def _strict_path(table_name: str, direct: set[str]) -> list[str] | None:
    """أقصرُ طريقٍ **بمفاتيحَ أجنبيّةٍ غيرِ قابلةٍ للفراغ** إلى جدولٍ يحمل `country_code` — **إلا ما صُرِّح به في `NULLABLE_PATH`
    بعلّته** فيُقبل مفتاحُه القابلُ للفراغ في خطوته الأولى."""
    allow_nullable_first = table_name in NULLABLE_PATH
    tables = Base.metadata.tables
    queue = deque([(table_name, [])])
    seen = {table_name}
    while queue:
        current, trail = queue.popleft()
        for fk in tables[current].foreign_keys:
            if fk.parent.nullable and not (allow_nullable_first and current == table_name):
                continue
            target = fk.column.table.name
            if target in seen:
                continue
            step = trail + [f"{current}.{fk.parent.name}→{target}"]
            if target in direct:
                return step
            seen.add(target)
            queue.append((target, step))
    return None


def test_every_table_reaches_its_market_or_is_declared_global() -> None:
    direct = _direct()
    # إثباتُ الصمت: المسحُ يرى ما نعرفه على الأقلّ
    assert {"users", "rides", "payment_requests"} <= direct, direct
    orphans = sorted(
        t.name
        for t in Base.metadata.sorted_tables
        if t.name not in direct and t.name not in GLOBAL and _strict_path(t.name, direct) is None
    )
    assert not orphans, (
        "جداولُ لا يُعرف سوقُ صفِّها — **نقلُ الجزائر إلى خادمها يصير تخميناً**:\n  "
        + "\n  ".join(orphans)
        + "\n  أضف `country_code`، أو مفتاحاً أجنبيّاً غيرَ قابلٍ للفراغ إلى جدولٍ يحمله،"
        " أو صرِّح به في `GLOBAL` بعلّته إن لم يكن بياناتِ مستخدم."
    )


def test_the_ledger_and_the_listed_data_reach_their_market() -> None:
    """**ما سمّاه المالكُ بالاسم** يُختار بسوقه — لا يكفي أن يُعفى بتصريح."""
    direct = _direct()
    named = [
        "users", "drivers", "rides", "wallet_transactions", "payments", "payment_requests", "ride_messages",
        "ride_calls", "driver_documents", "app_feedback", "driver_subscriptions", "withdrawal_requests",
    ]
    missing = [t for t in named if t not in direct and _strict_path(t, direct) is None]
    assert not missing, missing
    assert not set(named) & set(GLOBAL)


def test_declared_global_tables_have_no_market_path() -> None:
    """**التصريحُ لا يبلى صامتاً**: جدولٌ صار له طريقٌ إلى سوقه يخرج من `GLOBAL`."""
    direct = _direct()
    tables = Base.metadata.tables
    stale = sorted(t for t in GLOBAL if t in tables and (t in direct or _strict_path(t, direct) is not None))
    unknown = sorted(t for t in GLOBAL if t not in tables)
    assert not stale, f"صار لها طريقٌ إلى سوقها — أخرجها من GLOBAL: {stale}"
    assert not unknown, f"ليست جداولَ في النماذج — أخرجها من GLOBAL: {unknown}"


def test_country_code_is_mandatory_except_declared() -> None:
    nullable = sorted(
        t.name for t in Base.metadata.sorted_tables if "country_code" in t.c and t.c.country_code.nullable
    )
    assert nullable == sorted(NULLABLE_COUNTRY), (
        "`country_code` قابلٌ للفراغ — صفٌّ بلا سوقٍ لا يُنقل بلا تخمين: "
        + ", ".join(t for t in nullable if t not in NULLABLE_COUNTRY)
    )


def test_no_code_moves_a_row_to_another_market() -> None:
    """**سوقُ المستخدم لا يتغيّر بعد إنشائه** — والدفترُ يُختار بسوق صاحبه، فإسنادٌ جديدٌ لـ`country_code` على صفٍّ قائمٍ يُسقط المجموعة."""
    found = set()
    for path in APP_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, (ast.AugAssign, ast.AnnAssign)) else []
            for target in targets:
                if isinstance(target, ast.Attribute) and target.attr == "country_code" and isinstance(target.value, ast.Name):
                    found.add((path.relative_to(APP_DIR).as_posix(), target.value.id))
    unexpected = sorted(found - set(COUNTRY_ASSIGNMENTS))
    assert not unexpected, f"إسنادُ سوقٍ لصفٍّ قائم — يجعل نقلَ السوق تخميناً: {unexpected}"
    assert found >= set(COUNTRY_ASSIGNMENTS), "موضعٌ مصرَّحٌ به لم يعد موجوداً — أخرجه من COUNTRY_ASSIGNMENTS"
