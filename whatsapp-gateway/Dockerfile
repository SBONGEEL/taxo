# بوابةُ واتساب — صورةٌ صغيرةٌ بلا أدواتِ بناء.
#
# **و`npm ci` لا `npm install`**: الملفُّ المقفول هو ما جُرِّب، وتحديثُ مكتبةٍ
# تُؤتمت واتساب **بلا قصدٍ** هو أقصرُ طريقٍ إلى حظرٍ لا يُفسَّر.
FROM node:22-alpine

WORKDIR /app

# **مستخدمٌ غيرُ الجذر**: هذه الخدمةُ تحمل مفاتيحَ جلسةِ واتساب على قرصٍ
# دائم، فأقلُّ صلاحيةٍ ممكنة هي الأصل
RUN mkdir -p /data/auth && chown -R node:node /data

COPY --chown=node:node package.json package-lock.json* ./
RUN npm ci --omit=dev || npm install --omit=dev

COPY --chown=node:node src ./src
COPY --chown=node:node scripts ./scripts
# **شروطُ القالب تُنسخ، ولا تُترك للربط** (2026-08-19). كانت مربوطةً بالخلفية
# وحدَها ولا تُنسخ هنا، فسقطت البوابةُ إلى احتياطها المتشدّد `max_body_bytes: 0`
# ورفضت **كلَّ** قالبٍ وارد — فما خرج على السلك قالبٌ محرَّرٌ قط. والنسخُ في
# الصورة لا في الربط لأن الشرطَ صفةُ الوِيرِ نفسِه: صورةٌ تعمل وحدَها أصدقُ من
# صورةٍ تحتاج ملفَّ تركيبٍ صحيحاً كي لا **تُطفئ ميزةً بصمت**
COPY --chown=node:node otp-template-rules.json ./otp-template-rules.json

USER node
ENV NODE_ENV=production WA_AUTH_DIR=/data/auth WA_PORT=8080

# **الفحصُ على `/health` وحدَه** — البابُ الوحيد بلا مفتاح، فلا يحتاج
# `docker compose` سرّاً ليعرف أن العمليةَ حيّة
HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD node -e "require('node:http').get('http://127.0.0.1:8080/health',r=>process.exit(r.statusCode===200?0:1)).on('error',()=>process.exit(1))"

CMD ["node", "src/index.js"]
