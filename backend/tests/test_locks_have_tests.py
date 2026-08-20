"""**البند ٢**: قفلُ صفٍّ بلا اختبارِ تزامنٍ يحرسه.

**والقاعدةُ مكتوبةٌ في `CLAUDE.md` منذ المرحلة ٥**: «مرحلةٌ تمسّ المالَ أو
انتقالَ حالٍ ليست منتهيةً بلا اختبارِ تزامن»، و«قفلٌ لا يُثبَت بحذفه لا
يُصدَّق». **ولم يكن لها حارس** — والقاعدةُ بلا حارسٍ تُطبَّق حتى تُنسى.

**وما يفحصه وما لا يفحصه — يُقال صراحةً**: يفحص أن لكلِّ خدمةٍ تأخذ قفلَ صفٍّ
**ملفَّ تزامنٍ يسمّيها**. **ولا يستطيع أن يفحص أن الاختبارَ يسقط بحذف القفل** —
ذلك يبقى شرطاً بشرياً مكتوباً في القاعدة. **وحارسٌ يوحي بتغطيةٍ لا يملكها أسوأُ
من غيابه**، فيُقال هنا ما يملكه بحدّه.

**والاستثناءُ يحمل علّتَه**: قفلٌ يحرسه اختبارُ **خدمةٍ أخرى** (المسارُ يمرّ
بها) يُسمّى بعلّته، لا يُسكت عنه.
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICES = ROOT / "app" / "services"
TESTS = pathlib.Path(__file__).resolve().parent

#: خدماتٌ تأخذ قفلاً ويحرسها اختبارُ تزامنٍ **باسمٍ آخر** — بعلّته.
COVERED_ELSEWHERE: dict[str, str] = {
    "campaigns": "تُقاد من `tasks/notifications`، ويحرس تقدّمَها"
    " `notification_deliveries` بفريدٍ على (campaign_id, user_id) لا بقفل",
    "cliq_topups": "يحرسه `test_stage8_concurrency.py` — جوابان متزامنان"
    " من المزوّد على طلبٍ واحد",
    "deactivation": "طلبُ إلغاءِ تفعيلٍ لا يمسّ مالاً، وفريدُ الطلب القائم"
    " يمنع الثاني في القاعدة",
    "dispatch": "العرضُ يحرسه Redis بـ`NX` لا قفلُ صفّ — و"
    "`test_ride_sharing_join_concurrency.py` يقيس المقعدَ الثاني",
    "documents": "يحرسه `test_driver_documents_concurrency.py`",
    "drivers": "يحرسه `test_vehicle_update_concurrency.py` — تعليقٌ يُلغى"
    " بتعديلِ مركبة",
    "offers": "يحرسه `test_subscriptions_concurrency.py` — عرضٌ بحدِّ استعمالٍ"
    " واحدٍ لا يُمنح مرتين",
    "promo": "يحرسه `test_promo_concurrency.py`",
    "rides": "يحرسه `test_multi_stop_concurrency.py` و"
    "`test_ride_sharing_join_concurrency.py`",
    "subscriptions": "يحرسه `test_subscriptions_concurrency.py`",
    "topups": "يحرسه `test_wallet_concurrency.py` — تأكيدان على طلبٍ واحد",
    "withdrawals": "يحرسه `test_wallet_concurrency.py`",
}


def _locking_services() -> set[str]:
    return {
        path.stem
        for path in SERVICES.rglob("*.py")
        if "with_for_update" in path.read_text(encoding="utf-8")
    }


def _concurrency_text() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in TESTS.glob("test_*concurrency*.py")
    )


def test_every_locking_service_has_a_concurrency_test() -> None:
    locking = _locking_services()
    # **إثباتُ الصمت** (قاعدةُ المِسبار ٥): مسحٌ لا يجد قفلاً واحداً يمرّ أخضرَ أبداً
    assert len(locking) >= 15, f"لم يُعثر إلا على {len(locking)} خدمةً تقفل — المسحُ أعمى"

    body = _concurrency_text()
    assert body, "لا ملفَّ تزامنٍ واحد — المسحُ أعمى"

    missing = sorted(
        name
        for name in locking
        if name not in COVERED_ELSEWHERE
        and not re.search(rf"\b{re.escape(name)}\b", body)
    )
    assert not missing, (
        "خدماتٌ تأخذ قفلَ صفٍّ ولا يسمّيها اختبارُ تزامن:\n  "
        + "\n  ".join(missing)
        + "\n\n  اكتب له اختبارَ تزامنٍ **يفشل بحذف القفل**، أو صنّفه في"
        "\n  `COVERED_ELSEWHERE` بعلّته إن كان يحرسه اختبارُ خدمةٍ أخرى."
    )


def test_no_stale_exemptions() -> None:
    """**استثناءٌ لخدمةٍ لم تعد تقفل يصير عذراً لا أحدَ يقلّمه.**"""
    locking = _locking_services()
    stale = sorted(name for name in COVERED_ELSEWHERE if name not in locking)
    assert not stale, (
        "استثناءاتٌ لخدماتٍ لم تعد تأخذ قفلاً — تُحذف:\n  " + "\n  ".join(stale)
    )
