"""**البند ١٢**: تأنيثُ الوصف في رسائل الخطأ — تصنيفٌ لا افتراض.

**والعربيةُ لا تحتمل «كلمة المرور مطلوب»**: جملةٌ مكسورةٌ نحوياً في شاشةِ خطأٍ
تُقرأ **عطباً في التطبيق** لا خطأً في الإدخال، فتُضعف ثقةَ قارئها بكلِّ ما
بعدها. والجنسُ **خاصّةُ الكلمة لا صيغتِها**: «سنة» مؤنثةٌ و«اسم» مذكَّر،
والتاءُ ليست قاعدة.

**وما يحرسه ليس النحوَ بل الصمت.** المذكَّرُ كان **افتراضاً** — فحقلٌ جديدٌ
مؤنَّثٌ يُنسى، ولا شيءَ يفشل، ويخرج «سنة الصنع مطلوب» إلى شاشةٍ حقيقية.
فبكتابة القائمتين معاً تصير كلُّ تسميةٍ **مصنَّفةً أو ساقطةً هنا**.
"""

from __future__ import annotations

from app.core.validation_errors import (
    FEMININE_LABELS,
    FIELD_LABELS,
    MASCULINE_LABELS,
)


def test_every_label_declares_its_gender() -> None:
    """**كلُّ تسميةٍ مصنَّفة** — ولا تُترك للافتراض الصامت."""
    # إثباتُ الصمت (قاعدةُ المِسبار ٥)
    assert len(FIELD_LABELS) >= 20, f"لم يُقرأ إلا {len(FIELD_LABELS)} تسمية — المسحُ أعمى"

    classified = FEMININE_LABELS | MASCULINE_LABELS
    missing = sorted(set(FIELD_LABELS.values()) - classified)
    assert not missing, (
        "تسمياتٌ بلا تصنيفِ جنس — والمذكَّرُ ليس افتراضاً:\n  "
        + "\n  ".join(missing)
        + "\n\n  ضعها في `FEMININE_LABELS` أو `MASCULINE_LABELS` في"
        "\n  `core/validation_errors.py`."
    )


def test_no_label_is_both() -> None:
    """**ولا تسميةَ في القائمتين** — تصنيفان لواحدةٍ يجعل السلوكَ يتبع الترتيب."""
    both = sorted(FEMININE_LABELS & MASCULINE_LABELS)
    assert not both, "تسمياتٌ مصنَّفةٌ مرتين:\n  " + "\n  ".join(both)


def test_the_agreement_actually_reaches_the_sentence() -> None:
    """**والتصنيفُ يصل الجملةَ فعلاً** — لا يكفي أن يكون مكتوباً في قائمة.

    وهذا ما يفرّق حارساً يقيس **الأثر** عن حارسٍ يقيس **الإعلان**: قائمتان
    صحيحتان ودالّةٌ لا تقرؤهما تمرّان خضراوين.
    """
    from app.core.validation_errors import _fem

    assert _fem("كلمة المرور") is True
    assert _fem("سنة الصنع") is True
    assert _fem("الاسم") is False
    assert _fem("رقم اللوحة") is False
