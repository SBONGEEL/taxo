from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.exceptions import AppError

# رقم صيغة المظروف — يتيح تدوير المفتاح لاحقاً بلا لبس في قراءة الصفوف القديمة
ENVELOPE_VERSION = 1


class CredentialsEncryptionUnavailable(AppError):
    status_code = 500
    code = "credentials_encryption_unavailable"
    message = "مفتاح تشفير بيانات المزودين غير مضبوط"


class CredentialsCipher:
    """تشفير مظروف JSONB لبيانات عقود المزودين (at rest).

    نشفّر المظروف كاملاً لا الحقول السرية وحدها: لا شيء في هذا الجدول
    يُستعلَم عنه داخلياً، والتقنيع في اللوحة يقوده سجل المزودين لا القاعدة.
    """

    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except (ValueError, TypeError) as exc:
            raise CredentialsEncryptionUnavailable(
                "مفتاح CREDENTIALS_ENCRYPTION_KEY غير صالح (مطلوب مفتاح Fernet)"
            ) from exc

    def encrypt(self, values: dict[str, Any]) -> dict[str, Any]:
        payload = json.dumps(values, ensure_ascii=False, sort_keys=True).encode()
        return {
            "v": ENVELOPE_VERSION,
            "ciphertext": self._fernet.encrypt(payload).decode(),
        }

    def decrypt(self, envelope: dict[str, Any]) -> dict[str, Any]:
        try:
            raw = self._fernet.decrypt(envelope["ciphertext"].encode())
        except (InvalidToken, KeyError, AttributeError) as exc:
            raise CredentialsEncryptionUnavailable(
                "تعذّر فك تشفير بيانات المزود — تحقق من مفتاح التشفير"
            ) from exc
        return json.loads(raw)


@lru_cache
def get_cipher() -> CredentialsCipher:
    key = settings.credentials_encryption_key
    if not key:
        raise CredentialsEncryptionUnavailable()
    return CredentialsCipher(key)
