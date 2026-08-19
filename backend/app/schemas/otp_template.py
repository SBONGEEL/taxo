"""مخططاتُ قوالب رسالة الرمز."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TemplateViolationOut(BaseModel):
    code: str
    message: str


class OtpTemplateOut(BaseModel):
    """قالبٌ واحدٌ بحاله — **ومعه معاينتُه ومخالفاتُه**.

    والمعاينةُ تُصاغ في الخلفية بنفس دالّة الإرسال (`otp_templates.render`)، لا
    في اللوحة: معاينةٌ تحسب لنفسها تعرض ما تظنّه لا ما يخرج على السلك — وهو
    بعينه ما يجعل المشرفَ يوافق على نصٍّ لم يره أحد.
    """

    purpose: str
    label: str
    body: str
    is_default: bool = Field(
        description="لم يُحرَّر بعد — والنصُّ المعروض هو المدمج",
    )
    preview: str
    preview_sample_code: str = Field(
        description=(
            "الرمزُ المعروض في المعاينة — **عيّنةٌ وحدَها**، وكلُّ ما عداها في"
            " المعاينة قيمةٌ حقيقيةٌ لحظتَها"
        ),
    )
    violations: list[TemplateViolationOut]
    rejected_at_send: bool = Field(
        description="مخالفٌ فيُستعمل النصُّ الافتراضيُّ عند الإرسال",
    )
    updated_at: datetime | None = None


class OtpTemplatesOut(BaseModel):
    templates: list[OtpTemplateOut]
    max_body_bytes: int
    required_variables: list[str]
    optional_variables: list[str]
    applies_to_transport: str = Field(
        default="baileys",
        description=(
            "قوالبُ المصادقة عند ميتا لا تقبل نصّاً حرّاً — فهذا القالبُ يحكم"
            " الناقلَ الذاتيَّ وحدَه"
        ),
    )


class OtpTemplateUpdate(BaseModel):
    body: str
