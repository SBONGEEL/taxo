"""**الشكلُ الثامن**: بابان ينشران الشيءَ نفسَه، وكلٌّ صادقٌ وحدَه.

**وقع مرتين مقيستين.** خصمُ الاشتراك حُسب في `GET /subscriptions/plans` ونُسي في
`GET /subscriptions/me` — **والشاشةُ تقرأ الثاني**، فلم تُرسم تخفيضاتٌ والـAPI
تجيب بها صحيحةً إن سُئلت مباشرة؛ و**ستةَ عشرَ اختباراً أخضر** لأن لكلِّ بابٍ
اختبارَه وكلٌّ صادقٌ عن نفسِه. ثم وقع ثانيةً في 2026-08-20 في
`WalletTransactionOut.commission_percent`: مُلئ في باب الكبتن ونُسي في باب
اللوحة، فيقرأ المشرفُ كشفَ الكبتن بلا نسبة.

**ولا حارسَ بناءٍ يراه**: الحمولةُ نموذجٌ **واحد**، فالأنواعُ متطابقةٌ بالتعريف
و`check:config` يرى مرآةً واحدةً سليمة. **الفرقُ ليس في الشكل بل في أيِّ الحقول
يُملأ** — ولا يظهر إلا بمقارنة الردّين.

**والعلاجُ الأولُ بانٍ واحد** (`commission_view.rows_with_percent`)، وهذا
الملفُّ هو العلاجُ الثاني: **حارسٌ يمنع بابين جديدين من الافتراق**، ويجبر كلَّ
حمولةٍ متعددةِ الأبواب تحمل حقولاً محسوبةً على أن تُصنَّف.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from httpx import AsyncClient

from tests.helpers import (
    RIDER,
    approved_driver,
    auth,
    bring_online,
    completed_ride,
    pay_ride,
    register,
    set_commission,
    topup_wallet,
)


async def test_both_wallet_doors_publish_the_same_transaction(
    client: AsyncClient,
    session_factory,
    admin_headers: dict,
    jordan_settings: None,
    jordan_wallet: None,
) -> None:
    """**كشفُ الكبتن كما يراه هو، وكما تراه اللوحة — حقلاً حقلاً.**

    ولا يكفي أن يجيب كلٌّ بمائتين: الافتراقُ يقع في **قيمةِ حقلٍ** لا في شكلِ
    الرد، وهو ما لا يراه اختبارٌ يسأل باباً واحداً.
    """
    # **العمولةُ قبل إنشاء الرحلة** — تُجمَّد لحظتَها، وهي القيدُ الذي يحمل
    # النسبةَ التي افترق فيها البابان
    await set_commission(session_factory, "10.00")
    driver = await approved_driver(client, session_factory)
    await bring_online(client, driver)
    rider = auth(await register(client, RIDER))
    # **الشحنُ قبل الدفع**: رحلةٌ نقديةٌ تكتب `commission` مديناً بلا
    # `ride_earning` (§9)، فتحتاج محفظتُه رصيداً يكفيها وإلا رُفضت التسوية
    await topup_wallet(client, admin_headers, driver["user_id"], "50.000")
    ride = await completed_ride(client, rider, driver)
    # **القيدُ يُكتب عند التسوية لا عند الإنهاء** — ورحلةٌ منتهيةٌ بلا دفعٍ لا
    # تترك في الدفتر شيئاً يُقارَن. والكاشُ يكتب `commission` بلا `ride_earning`
    # (§9)، وهو بالضبط القيدُ الذي يحمل النسبة
    paid = await pay_ride(client, rider, ride["id"], "cash")
    assert paid.status_code == 201, paid.text
    # الردُّ حمولةُ الرحلة لا صفَّ الدفعة — دفعتان على رحلةٍ ممكنتان (§6)
    payments = paid.json()["payments"]
    assert len(payments) == 1, payments
    payment = payments[0]
    confirmed = await client.post(
        f"/payments/{payment['id']}/confirm", headers=driver["headers"]
    )
    assert confirmed.status_code == 200, confirmed.text

    user_id = driver["user_id"]

    mine = (
        await client.get(
            "/wallet/me/transactions?wallet=driver", headers=driver["headers"]
        )
    ).json()
    theirs = (
        await client.get(f"/admin/wallets/{user_id}/transactions", headers=admin_headers)
    ).json()

    assert mine, "لا قيود — الاختبار لا يقيس شيئاً"
    by_id = {row["id"]: row for row in theirs}
    for row in mine:
        other = by_id.get(row["id"])
        assert other is not None, f"قيدٌ يراه صاحبُه ولا تراه اللوحة: {row['id']}"
        # **حقلاً حقلاً** — لا مقارنةَ مفاتيحَ وحدَها: الشكلُ الثامن يفترق في
        # القيمة لا في الاسم
        assert row == other, (
            "بابان ينشران القيدَ نفسَه ويفترقان: "
            f"{ {k: (row.get(k), other.get(k)) for k in row if row.get(k) != other.get(k)} }"
        )


def test_every_multi_door_computed_payload_is_classified() -> None:
    """**ما يُنشر من بابين ويحمل حقولاً محسوبةً — يُصنَّف أو يفشل البناء.**

    والتصنيفُ نصٌّ لا سكوت: `SHARED_BUILDER` لِما وُحّد بانِيه،
    و`COMPARED` لِما يقارنه اختبار، و`SINGLE_SOURCE` لِما يُقرأ من الصفِّ كلَّه
    فلا شيءَ فيه يُنسى. **وقائمةٌ يُضاف إليها بلا سبب تصير قائمةَ أعذار**، فكلُّ
    مدخلٍ يحمل علّتَه.
    """
    from app.main import app

    schema = app.openapi()

    def refs(node, out):
        if isinstance(node, dict):
            if "$ref" in node:
                out.add(node["$ref"].split("/")[-1])
            for value in node.values():
                refs(value, out)
        elif isinstance(node, list):
            for value in node:
                refs(value, out)

    doors: dict[str, set[str]] = {}
    for path, operations in schema["paths"].items():
        for verb, operation in operations.items():
            found: set[str] = set()
            refs(operation.get("responses", {}), found)
            for name in found:
                doors.setdefault(name, set()).add(f"{verb.upper()} {path}")

    components = schema["components"]["schemas"]
    unclassified = []
    for name, routes in doors.items():
        if len(routes) < 2 or name == "HTTPValidationError":
            continue
        model = components.get(name, {})
        # **حقلٌ محسوب**: يقبل `null` وليس مطلوباً — أي أن بانياً قد يتركه
        computed = [
            field
            for field, spec in model.get("properties", {}).items()
            if field not in model.get("required", [])
            and "anyOf" in spec
            and any(part.get("type") == "null" for part in spec["anyOf"])
        ]
        if computed and name not in CLASSIFIED:
            unclassified.append((name, len(routes), computed[:4]))

    assert not unclassified, (
        "حمولاتٌ تُنشر من أكثر من باب وتحمل حقولاً محسوبةً ولم تُصنَّف — "
        "وحّد بانِيها أو قارن الردّين، ثم صنّفها بعلّتها:\n"
        + "\n".join(f"  {n} (أبواب={d}) حقول={c}" for n, d, c in unclassified)
    )


#: التصنيفُ بعلّته — والعلّةُ نصٌّ يُقرأ لا مجرّد وجودٍ في قائمة.
CLASSIFIED: dict[str, str] = {
    # ✅ بانٍ واحد
    "SubscriptionPlanOut": "بانٍ واحد: `subscriptions._plans_with_offers` يخدم /plans و/me",
    "WalletTransactionOut": "بانٍ واحد: `commission_view.rows_with_percent` يخدم بابَي الكشف",
    "NearbyDriverOut": (
        "بانٍ واحد: `NearbyDriverOut.of` يخدم بابَي REST ومقبسَ `nearby_drivers` — "
        "و`skin` هو الحقلُ الذي أوجب التصنيف، وغيابُه ليس نسياناً بل حالةٌ واحدةٌ "
        "مسمّاة (لا بديلَ منشورٌ في الكتالوج) تقع على الجميع سواءً، فلا يُقاس فرق"
    ),
    # ✅ بانٍ واحد (تُبع 2026-08-30)
    "DebtClaimOut": (
        "بانٍ واحد: `cliq_debts.claim_out` يخدم أبوابَها الأربعة — بابَي الكبتن "
        "وبابَي اللوحة. **وكان بابا اللوحة يتركان `qr_url` و`alias` فارغَين** "
        "فيقرأ المشرفُ مطالبةً بلا حسابٍ ولا رمز، ولا شيءَ يفشل — فوُحِّد"
    ),
    "CliqSubscriptionOut": (
        "بانٍ واحد: `cliq_subscriptions.claim_out` يخدم بابَي الفتح والقائمة "
        "(وُحِّد 2026-08-30). **وكان بابُ القائمة يكتب `qr_url=None` نصّاً** — "
        "فيرى الكبتنُ الباركودَ لحظةَ الفتح ولا يراه إن عاد من قائمته، وشاشتُه "
        "تقول «لم يُرفع الرمزُ بعد» وهو مرفوع"
    ),
    "PaymentSettingOut": (
        "مصدرٌ واحد: أبوابُه الثلاثةُ كلُّها `PaymentSettingOut.model_validate(row)` "
        "— **الصفُّ كلُّه لا حقولٌ تُملأ بيد**، فلا شيءَ فيه يُنسى في بابٍ ويُذكر "
        "في آخر. و`cliq_alias` و`cliq_qr_path` و`driver_debt_ceiling` أعمدةٌ تُقرأ"
    ),
    "AdminServiceTileOut": (
        "مصدرٌ واحد: أبوابُه الثلاثةُ (القائمة والإنشاء والتعديل) كلُّها "
        "`AdminServiceTileOut.model_validate(row)` — **الصفُّ كلُّه لا حقولٌ "
        "تُملأ بيد**. و`subtitle` و`destination` و`new_until` أعمدةٌ تُقرأ، "
        "**و`null` فيها حالٌ مقصودةٌ لا نسيان**: «قريباً» بلا مقصدٍ عن قصد، "
        "وبلاطةٌ بلا مدّةِ «جديد» ليست جديدةً — والقيدُ في القاعدة يمنع "
        "الفعّالةَ بلا مقصد، فالفراغُ محروسٌ لا مُهمَل"
    ),
    "AdminPromoBannerOut": (
        "مصدرٌ واحد: أبوابُه الثلاثةُ كلُّها `model_validate(row)` من صفِّ "
        "`promo_banners`. و`body` و`icon` و`link` أعمدةٌ تُقرأ — **و`link` "
        "فراغُه محروسٌ بقيدٍ**: `link_kind='none'` أو عنوانٌ مبنيّ، فلا "
        "لافتةَ تفتح شاشةً لا وجودَ لها"
    ),
    "AdminDebtOut": (
        "مصدرٌ واحد: كلُّ حقوله من `driver_debts` وصاحبِه في ضمٍّ واحد، "
        "و`driver_phone` و`ride_id` عمودان يُقرآن لا يُحسبان. **وبابان لا "
        "يفترقان**: القائمةُ والشطبُ يبنيانه من الصفِّ نفسِه بعد التغيير"
    ),
    # ✅ يقارنه اختبار
    "RideOut": "تقارنه `test_ws.py` و`test_rides.py` عبر أبوابه، و`from_ride` بانيه الوحيد",
    # ✅ مصدرٌ واحد: كلُّ حقوله من الصفِّ نفسِه، فلا شيءَ «يُملأ» ليُنسى
    "UserOut": "من صفِّ `users` كلُّه — لا حقلَ يحسبه راوتر",
    "WhatsAppSessionOut": "من `/status` البوابة كلِّه عبر `session.describe`",
    "ChallengeResponse": "يبنيه `verification.challenge` وحدَه",
    "TotpStatusOut": "يبنيه `totp.status_for` وحدَه",
    "RidePaymentsOut": "يبنيه `payments.summary_for` وحدَه",
    "BadgeOut": "من صفِّ `driver_badges` كلِّه",
    "BookingOut": "من صفِّ `ride_bookings` كلِّه",
    "RouteLineOut": "من `rides.route_polyline` وحدَه",
    "GrantOut": "من صفِّ المنح كلِّه",
    "MissionOut": "يبنيه `levels.missions_for` وحدَه",
    "ReferralSettingsOut": "من صفِّ `referral_settings` كلِّه",
}
