"""مهام Celery الخلفية (انتهاء الاشتراكات، وما يليها من إشعارات وتقارير).

`celery_app.py` يحمل الإعداد وجدول الدورية، وكل ملفٍ بعده مهمةٌ واحدة غلافاً
رقيقاً على خدمةٍ في `services/`.
"""

from app.tasks.celery_app import celery_app

__all__ = ["celery_app"]
