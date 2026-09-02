"""قوالبُ رسالة الرمز — قراءةٌ وكتابةٌ لـ`admin` حصراً.

**لا `StaffUser`**: نصُّ ما يخرج من رقم الشركة على واتساب قرارٌ على القناة
كلِّها لا إجراءُ دعم — كصفحة العقود وسياسة الدخول.

**وحفظُ قالبٍ لا يمسّ الآخر**: بابٌ لكل غرض، وصفٌّ لكل غرض.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import ProvidersManager, DbSession
from app.core.exceptions import InvalidOtpTemplate, NotFound
from app.models.enums import AuditAction
from app.models.otp_template import OtpMessageTemplate, OtpTemplatePurpose
from app.schemas.otp_template import (
    OtpTemplateOut,
    OtpTemplatesOut,
    OtpTemplateUpdate,
    TemplateViolationOut,
)
from app.services import audit, otp, otp_templates

router = APIRouter(prefix="/admin/otp-templates", tags=["admin"])

# **المعاينةُ بالقيم الحقيقية لحظتَها** (قرارُ المالك 2026-08-19، SPEC §19.8):
# كانت تعرض «١٠ دقيقة» والمهلةُ الحقيقيةُ خمس، فيحرّر المشرفُ على أساسٍ كاذب —
# وهو صنفُ «شاشةٌ تقول ما لا يقع» بعينه. والمهلةُ تُقرأ من مصدرها لا تُكتب هنا.
#
# **والرمزُ وحدَه عيّنةٌ ظاهرة**، ولا مفرَّ: لا رمزَ حقيقياً قبل الإرسال، وتوليدُ
# واحدٍ للمعاينة يعني رمزاً حيّاً لم يطلبه أحد.
_PREVIEW_CODE = "123456"


def _to_out(purpose: str, row: OtpMessageTemplate | None) -> OtpTemplateOut:
    body = row.body if row is not None else otp_templates.DEFAULTS[purpose]
    bad = otp_templates.validate(body, purpose=purpose)
    return OtpTemplateOut(
        purpose=purpose,
        label=otp_templates.PURPOSE_LABEL[purpose],
        body=body,
        is_default=row is None,
        preview=otp_templates.render(
            body, code=_PREVIEW_CODE, minutes=otp.CODE_TTL_SECONDS // 60
        ),
        preview_sample_code=_PREVIEW_CODE,
        violations=[TemplateViolationOut(code=v.code, message=v.message) for v in bad],
        # **يُقال في الشاشة لا في السجل وحدَه**: من حرّر نصّاً مخالفاً يظنّه
        # يعمل، والسجلُّ لا يقرؤه إلا من يبحث عن عطبٍ يعرف بوجوده أصلاً
        rejected_at_send=bool(bad),
        updated_at=row.updated_at if row is not None else None,
    )


@router.get("", response_model=OtpTemplatesOut)
async def list_templates(session: DbSession, _: ProvidersManager) -> OtpTemplatesOut:
    rows = await otp_templates.all_templates(session)
    rules = otp_templates.rules()
    return OtpTemplatesOut(
        templates=[_to_out(p, rows[p]) for p in OtpTemplatePurpose.ALL],
        max_body_bytes=rules["max_body_bytes"],
        required_variables=list(rules["required_variables"]),
        optional_variables=list(rules["optional_variables"]),
    )


@router.put("/{purpose}", response_model=OtpTemplateOut)
async def update_template(
    purpose: str,
    payload: OtpTemplateUpdate,
    session: DbSession,
    user: ProvidersManager,
) -> OtpTemplateOut:
    if purpose not in OtpTemplatePurpose.ALL:
        raise NotFound("لا قالبَ بهذا الاسم")

    body = payload.body
    # **الرفضُ هنا لا عند الإرسال**: من يعرف رفضَه في اللوحة يصحّحه، ومن يكتشفه
    # من رسالةٍ لم تصل لا يعرف أنّ شيئاً وقع أصلاً. والشروطُ من ملفِّ البوابة
    # نفسِه، فلا يقبل هذا البابُ ما ترفضه هي.
    bad = otp_templates.validate(body, purpose=purpose)
    if bad:
        raise InvalidOtpTemplate("؛ ".join(v.message for v in bad), field="body")

    row = (await otp_templates.all_templates(session))[purpose]
    before = row.body if row is not None else otp_templates.DEFAULTS[purpose]
    if row is None:
        row = OtpMessageTemplate(purpose=purpose, body=body, updated_by_id=user.id)
        session.add(row)
    else:
        row.body = body
        row.updated_by_id = user.id

    await session.flush()
    # **النصُّ قبل وبعد في التدقيق** — وهو الاستثناءُ المعلن من «أسماءُ الحقول
    # لا قيمُها»: النصُّ نفسُه هو ما تغيّر، وقرارُ مشرفٍ لا سرٌّ مخزَّن، وسؤالُ
    # «من كتب هذا لصاحب الرقم؟» لا جوابَ له بغيره
    await audit.record(
        session,
        actor=user,
        action=AuditAction.UPDATE,
        entity_type="otp_message_template",
        entity_id=row.id,
        details={"purpose": purpose, "before": before, "after": body},
    )
    await session.commit()
    await session.refresh(row)
    return _to_out(purpose, row)
