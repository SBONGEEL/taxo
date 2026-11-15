#!/usr/bin/env bash
# **بيئةُ تشغيل CI** — كانت منسوخةً في وظيفتين من `ci.yml` سطراً سطراً، فصارت هنا مرّةً (2026-11-15).
#
# **قيمٌ للتشغيل وحدَه ويُرمى بها** — مولَّدةٌ في كلِّ تشغيل، فليست أسراراً ولا تُقرأ كذلك. **ولا احتياطَ صامتٌ لسرّ**: الملفُّ
# يُكتب كاملاً فيقف الإقلاعُ إن نقص مفتاحٌ بدل أن يقع على افتراض. **ولا يُطبع منه شيء** («لا سرَّ في سجلّ CI»).
set -euo pipefail
python3 - <<'PY' > .env
import secrets, base64
fernet = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
print(f"""POSTGRES_USER=taxo
POSTGRES_PASSWORD={secrets.token_urlsafe(24)}
POSTGRES_DB=taxo
DATABASE_URL=postgresql+asyncpg://taxo:x@db:5432/taxo
REDIS_PASSWORD={secrets.token_urlsafe(24)}
REDIS_URL=redis://redis:6379/0
JWT_SECRET={secrets.token_urlsafe(48)}
CREDENTIALS_ENCRYPTION_KEY={fernet}
ENVIRONMENT=test
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30
CUSTOMER_APP_PORT=5176
TELR_USE_MOCK=1
WA_GATEWAY_KEY={secrets.token_urlsafe(24)}""")
PY
# القيمةُ الحقيقيةُ لكلمة القاعدة تدخل عنوانَ الاتصال أيضاً
pw=$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2-)
sed -i "s|postgresql+asyncpg://taxo:x@|postgresql+asyncpg://taxo:$pw@|" .env
# **وكلمةُ Redis تدخل عنوانَها أيضاً** — redis يشترط المصادقة منذ 2026-09-20
rpw=$(grep '^REDIS_PASSWORD=' .env | cut -d= -f2-)
sed -i "s|redis://redis:6379/0|redis://:$rpw@redis:6379/0|" .env
echo "✓ بيئةُ التشغيل كُتبت ($(wc -l < .env) مفتاحاً)"
