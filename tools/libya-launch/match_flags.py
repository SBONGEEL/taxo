# مطابقةُ مفاتيح ليبيا بالأردن والجزائر (أمرُ المالك ١٧/١١) — المشتعلُ في الدولتين معاً يُشعَل لليبيا، عبر set_flag (سطرُ تدقيقٍ لكلٍّ).
# country_visible مستثنى (بابُه صفحةُ «الدول»). APPLY=1 يكتب، وإلا خطّةٌ وحدَها.
import asyncio, os, json
from sqlalchemy import select, text
from app.core.db import SessionLocal
from app.models.enums import CountryCode, FeatureKey
from app.models.user import User
from app.services import settings_service, trip_chat
REASON = "مطابقةُ ليبيا بالأردن والجزائر قبل الافتتاح — أمرُ المالك ٢٠٢٦-١١-١٧"
async def main():
    apply = os.environ.get("APPLY") == "1"
    async with SessionLocal() as s:
        jo = await settings_service.get_flags(s, CountryCode.JO)
        dz = await settings_service.get_flags(s, CountryCode.DZ)
        ly = await settings_service.get_flags(s, CountryCode.LY)
        print("LY_BEFORE", json.dumps({k:v for k,v in sorted(ly.items())}))
        todo = [k for k in sorted(jo) if jo.get(k) and dz.get(k) and not ly.get(k) and k != "country_visible"]
        print("PLAN", todo)
        owner = (await s.execute(text("select u.id from users u join user_roles r on r.user_id=u.id where r.role='owner' limit 1"))).scalar()
        actor = await s.get(User, owner)
        done, skipped = [], []
        for k in todo:
            try:
                if k in (FeatureKey.TRIP_CHAT_ENABLED.value, FeatureKey.RIDE_CALLS_ENABLED.value):
                    await trip_chat.require_published_line(s, CountryCode.LY, trip_chat.CHAT_PRIVACY_MARKER)
                if k == FeatureKey.DELIVERY_ENABLED.value: raise ValueError("delivery not built")
                if apply:
                    async with s.begin_nested():
                        await settings_service.set_flag(s, country_code=CountryCode.LY, feature_key=k, enabled=True, actor=actor, reason=REASON)
                done.append(k)
            except Exception as e:
                skipped.append((k, type(e).__name__, str(e)[:120]))
        if apply: await s.commit()
        else: await s.rollback()
        print("DONE" if apply else "WOULD", done)
        print("SKIPPED", json.dumps(skipped, ensure_ascii=False))
        async with SessionLocal() as s2:
            ly2 = await settings_service.get_flags(s2, CountryCode.LY)
            print("LY_AFTER", json.dumps({k:v for k,v in sorted(ly2.items())}))
asyncio.run(main())
