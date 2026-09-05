"""مخطَّطاتُ شاشة «الموقع» — **والتحقّقُ هنا لا في الشاشة** (§52).

**ورابطٌ يُفحص في المتصفّح وحدَه ليس مفحوصاً**: من أرسل بـ`curl` تجاوزه.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, field_validator

#: **`https` وحدَها** — صفحةٌ عامّةٌ تفتح `http` تُنذر المتصفّحُ زائرَها.
_HTTPS = "https://"

#: **رابطُ المتجر يبدأ بهذا حرفاً** (شرطُ المالك): زرٌّ يقول «Google Play»
#: ويفتح غيرَه **يكذب على من ضغطه**، والشارةُ الرسمية لا تُوضع فوق رابطٍ آخر.
_PLAY = "https://play.google.com/"


def _https_or_empty(value: str, *, label: str) -> str:
    """رابطٌ آمنٌ أو فراغ — **والفراغُ قصدٌ لا نقص**.

    الفارغُ يعني «لا أيقونة» و«شارةٌ معطَّلة»، وهو ما تقرؤه الصفحة. **ولا زرَّ
    بلا رابطٍ أبداً** — وهذا هو الطرفُ الذي يضمنه.
    """
    value = (value or "").strip()
    if not value:
        return ""
    if not value.startswith(_HTTPS):
        raise ValueError(f"{label} يجب أن يبدأ بـhttps://")
    return value


class SiteUpdateIn(BaseModel):
    """ما تُرسله الشاشة — **وكلُّ حقلٍ اختياريّ**.

    **و«لم يُرسَل» ليست «أُرسل فارغاً»**: الموجّه يقرأ `exclude_unset`، فحفظُ
    قسمٍ واحدٍ لا يمحو أقساماً لم تُفتح.
    """

    hero_title: str | None = Field(default=None, max_length=120)
    hero_subtitle: str | None = Field(default=None, max_length=240)
    hero_note: str | None = Field(default=None, max_length=80)

    announce_enabled: bool | None = None
    announce_text: str | None = Field(default=None, max_length=200)
    announce_url: str | None = Field(default=None, max_length=300)

    support_email: str | None = Field(default=None, max_length=120)
    privacy_email: str | None = Field(default=None, max_length=120)
    social_facebook: str | None = Field(default=None, max_length=300)
    social_instagram: str | None = Field(default=None, max_length=300)
    social_tiktok: str | None = Field(default=None, max_length=300)
    social_x: str | None = Field(default=None, max_length=300)
    social_whatsapp: str | None = Field(default=None, max_length=300)

    hidden_sections: list[str] | None = None
    hidden_cards: list[str] | None = None
    faq: list[dict[str, Any]] | None = None

    distribution_mode: Literal["apk", "play"] | None = None
    play_url_rider: str | None = Field(default=None, max_length=300)
    play_url_driver: str | None = Field(default=None, max_length=300)
    ios_url: str | None = Field(default=None, max_length=300)
    apk_page_enabled: bool | None = None

    policies_public: bool | None = None
    seo_description: str | None = None

    @field_validator(
        "announce_url",
        "social_facebook",
        "social_instagram",
        "social_tiktok",
        "social_x",
        "social_whatsapp",
        "ios_url",
    )
    @classmethod
    def _check_https(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _https_or_empty(value, label="الرابط")

    @field_validator("play_url_rider", "play_url_driver")
    @classmethod
    def _check_play(cls, value: str | None) -> str | None:
        """**رابطُ المتجر يبدأ بـ`https://play.google.com/`** — أو يبقى فارغاً.

        **ويقبل رابطَ اختبارٍ مغلق** لأنه على النطاق نفسِه
        (`/apps/testing/<pkg>`)، **فالشرطُ على المضيف لا على شكل المسار**.
        """
        if value is None:
            return None
        value = (value or "").strip()
        if not value:
            return ""
        if not value.startswith(_PLAY):
            raise ValueError("رابط المتجر يجب أن يبدأ بـhttps://play.google.com/")
        return value


class SiteAdminOut(BaseModel):
    """ما تقرؤه الشاشة — **الحقولُ نفسُها التي ينشرها البابُ العام**.

    **ولا حقلَ إداريٌّ زائد**: كلُّ ما في هذا الجدول عامٌّ بحكم بنائه، **فشاشةٌ
    ترى أكثرَ ممّا يرى الزائرُ كانت ستوهم أن ثمّة سرّاً هنا** — وليس.
    """

    hero_title: str
    hero_subtitle: str
    hero_note: str
    announce_enabled: bool
    announce_text: str
    announce_url: str
    support_email: str
    privacy_email: str
    social_facebook: str
    social_instagram: str
    social_tiktok: str
    social_x: str
    social_whatsapp: str
    hidden_sections: list[str]
    hidden_cards: list[str]
    faq: list[dict[str, Any]]
    distribution_mode: str
    play_url_rider: str
    play_url_driver: str
    ios_url: str
    apk_page_enabled: bool
    policies_public: bool
    seo_description: str

    #: **يُعرض ولا يُكتب هنا** — بيتُه `commission_settings` في شاشة الإعدادات،
    #: **وشاشتان تكتبان قاعدةَ مالٍ واحدةً حالان يمكن أن تختلفا**.
    commission_percent: str
    updated_at: datetime


#: ما يُذكر في الشاشة بجانب مفتاح التوزيع — **الأثرُ يُقال لا يُستنتج**.
DISTRIBUTION_EFFECT: dict[str, str] = {
    "apk": "تجريبي: روابط APK",
    "play": "المتجر: شارات Google Play",
}

__all__ = [
    "SiteUpdateIn",
    "SiteAdminOut",
    "DISTRIBUTION_EFFECT",
    "Annotated",
]
