# زرُّ إطلاق ليبيا ورجوعُه — فعلٌ واحدٌ عبر بابه الحقيقيّ (markets.set_status: فحصُ الجاهزيّة + سطرُ تدقيق + مفتاحُ country_visible).
# ACTION=open|close   FORCE=1 يُفتح رغم نقص الجاهزيّة (قرارُ المالك وحدَه، والسببُ إلزاميّ)   REASON="..."
# بلا ACTION: قراءةٌ وحدَها (الحالُ والجاهزيّة).
import asyncio, os, json
from sqlalchemy import text
from app.core.db import SessionLocal
from app.models.enums import CountryCode
from app.models.user import User
from app.services import markets

async def main():
    action = os.environ.get("ACTION")
    reason = os.environ.get("REASON") or None
    force = os.environ.get("FORCE") == "1"
    async with SessionLocal() as s:
        before = await markets.status_of(s, CountryCode.LY)
        ready = await markets.readiness(s, CountryCode.LY)
        print("BEFORE", before, "SIGNUP", await markets.signup_state(s, CountryCode.LY), "MISSING", json.dumps(ready, ensure_ascii=False))
        if action not in ("open", "close"):
            await s.rollback(); return
        owner = (await s.execute(text("select u.id from users u join user_roles r on r.user_id=u.id where r.role='owner' limit 1"))).scalar()
        actor = await s.get(User, owner)
        after = await markets.set_status(s, country=CountryCode.LY, open_=(action == "open"), actor=actor, reason=reason, force=force)
        await s.commit()
        print("AFTER", after)
    async with SessionLocal() as s:
        print("CHECK", await markets.status_of(s, CountryCode.LY), "SIGNUP", await markets.signup_state(s, CountryCode.LY))

asyncio.run(main())
