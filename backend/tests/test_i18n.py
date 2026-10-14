"""الفرنسيّة في الخلفية (SPEC §٧٣-هـ المرحلة ٥) — **والعربيّةُ لا تتغيّر حرفاً**.

**ما يُقاس هنا**: القاموسُ لا يحمل مفتاحاً لا تكتبه الخلفية · العربيّةُ تعود كما هي لكلِّ مفتاح · الخطأُ يخرج بلغة الطلب (`Accept-Language`)
**وبلا رأسٍ عربيّاً حرفاً** · القالبُ يُطابَق وتُنقل قيمُه وتُترجم · لغةُ الحساب تُكتب عند التسجيل والدخول وتُغيَّر من الإعدادات · الإشعارُ بلغة
صاحبه · قالبُ رسالة الرمز بالفرنسيّة لمن يطلبه بها.

**والشاهدُ الأكبرُ على العربيّة ليس هنا**: كلُّ اختبارٍ قائمٍ في المجموعة يقرأ رسالةً عربيّةً بلا رأس لغة — فإن تغيّرت واحدةٌ سقط.
"""

from __future__ import annotations

import importlib.util
import json
import uuid
from pathlib import Path

from httpx import AsyncClient
from sqlalchemy import select

from app.core import i18n
from app.core.i18n import translate
from app.models.user import User
from app.services import notifications, otp_templates
from app.services.push import PushMessage
from tests.helpers import RIDER, auth, register

BACKEND = Path(__file__).resolve().parents[1]
FR = json.loads((BACKEND / "app/i18n/fr.json").read_text(encoding="utf-8"))
FRENCH = {"Accept-Language": "fr-DZ,fr;q=0.9,ar;q=0.8"}


def _extracted() -> set[str]:
    spec = importlib.util.spec_from_file_location("i18n_extract", BACKEND / "scripts/i18n_extract.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return set(module.keys())


def test_every_french_key_is_a_text_the_backend_writes() -> None:
    orphans = sorted(set(FR) - _extracted())
    assert orphans == [], orphans[:10]


def test_arabic_comes_back_verbatim_for_every_key() -> None:
    for key in FR:
        assert translate(key, "ar") == key
        assert translate(key) == key  # **بلا طلب** — السياقُ عربيٌّ افتراضاً


def test_the_header_decides_and_only_french_is_french() -> None:
    assert i18n.language_of_header("fr") == "fr"
    assert i18n.language_of_header("fr-FR,ar;q=0.5") == "fr"
    for header in (None, "", "ar", "en-US,en;q=0.9", "ar-JO,fr;q=0.8", "*"):
        assert i18n.language_of_header(header) == "ar"


def test_a_template_is_matched_its_values_carried_and_translated() -> None:
    assert translate("الحد الأدنى للسحب 150", "fr") == "Retrait minimum : 150"
    # **قيمُ المواضع تُترجم هي أيضاً** — اسمُ الحقل والفعلُ مفتاحان في القاموس
    assert translate("المبلغ يجب ألّا يقلّ عن 5", "fr") == "Montant ne doit pas être inférieur à 5"
    # **ونصٌّ لا مفتاحَ له يخرج عربيّاً** ولا يخرج فارغاً
    assert translate("نصٌّ لم يُكتب في أيِّ مكان", "fr") == "نصٌّ لم يُكتب في أيِّ مكان"


async def test_an_error_follows_the_request_language_and_arabic_is_unchanged(client: AsyncClient) -> None:
    body = {"phone": "0790000999", "password": "WrongPassword1", "country_code": "JO"}
    arabic = await client.post("/auth/login", json=body)
    french = await client.post("/auth/login", json=body, headers=FRENCH)
    assert arabic.status_code == french.status_code
    assert arabic.json()["code"] == french.json()["code"]
    assert arabic.json()["message"] == "بيانات الدخول غير صحيحة"
    assert french.json()["message"] == FR["بيانات الدخول غير صحيحة"]


async def test_a_validation_error_follows_the_request_language(client: AsyncClient) -> None:
    arabic = await client.post("/auth/login", json={})
    french = await client.post("/auth/login", json={}, headers=FRENCH)
    assert arabic.status_code == french.status_code == 422
    assert arabic.json()["message"] != french.json()["message"]
    assert translate(arabic.json()["message"], "fr") == french.json()["message"]


async def test_the_account_language_is_written_at_signup_login_and_from_settings(
    client: AsyncClient, session_factory
) -> None:
    from app.core.phone import normalize_phone
    from app.services.firebase_auth import mock_token

    payload = dict(RIDER) | {"verification_token": mock_token(normalize_phone(RIDER["phone"], RIDER["country_code"]))}
    made = await client.post("/auth/register", json=payload, headers=FRENCH)
    assert made.status_code == 201, made.text
    assert made.json()["user"]["language"] == "fr"
    headers = auth(made.json())

    switched = await client.patch("/auth/me", json={"language": "ar"}, headers=headers)
    assert switched.status_code == 200 and switched.json()["language"] == "ar"
    refused = await client.patch("/auth/me", json={"language": "en"}, headers=headers)
    assert refused.status_code == 422

    login = {"phone": RIDER["phone"], "password": RIDER["password"], "country_code": RIDER["country_code"]}
    assert (await client.post("/auth/login", json=login, headers=FRENCH)).status_code == 200
    async with session_factory() as session:
        language = await session.scalar(select(User.language).where(User.phone == normalize_phone(RIDER["phone"], "JO")))
    assert language == "fr"


async def test_a_notification_is_written_in_its_owner_language(client: AsyncClient, session_factory) -> None:
    rider = await register(client, RIDER)
    user_id = uuid.UUID(rider["user"]["id"])
    message = PushMessage(title="اكتمل دفع رحلتك", body="أكّد الكبتنُ استلام المبلغ — شكراً لك.")
    async with session_factory() as session:
        arabic = await notifications.in_language_of(session, user_id, message)
        assert arabic is message
        user = await session.get(User, user_id)
        user.language = "fr"
        await session.commit()
    async with session_factory() as session:
        french = await notifications.in_language_of(session, user_id, message)
    assert french.title == FR["اكتمل دفع رحلتك"]
    assert french.body == FR["أكّد الكبتنُ استلام المبلغ — شكراً لك."]


async def test_the_code_message_template_is_french_for_a_french_request(session_factory) -> None:
    async with session_factory() as session:
        arabic = await otp_templates.body_for(session, "registration")
        previous = i18n._current.set("fr")
        try:
            french = await otp_templates.body_for(session, "registration")
        finally:
            i18n._current.reset(previous)
    assert arabic == otp_templates.DEFAULTS["registration"]
    assert french.startswith("Votre code de confirmation") and "{code}" in french and "{minutes}" in french


async def test_the_published_rules_follow_the_request_language(client: AsyncClient) -> None:
    """**قواعدُ التحقّق في `/config` بلغة الطلب** — وكانت عربيّةً للفرنسيّة («8 محارف على الأقل» تحت حقلٍ فرنسيّ)."""
    from app.core import validation_rules

    arabic = (await client.get("/config")).json()["validation"]
    french = (await client.get("/config", headers=FRENCH)).json()["validation"]
    assert arabic == validation_rules.published_rules()  # **العربيّةُ حرفاً**

    def texts(node: object) -> list[str]:
        if isinstance(node, dict):
            return [text for item in node.values() for text in texts(item)]
        if isinstance(node, list):
            return [text for item in node for text in texts(item)]
        return [node] if isinstance(node, str) else []

    left = [text for text in texts(french) if any("؀" <= ch <= "ۿ" for ch in text)]
    assert left == [], left[:5]
    assert french["register"]["password"]["conditions"][0]["label"] == translate(
        arabic["register"]["password"]["conditions"][0]["label"], "fr"
    )
