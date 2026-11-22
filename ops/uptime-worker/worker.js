// **مراقبُ التوفّر الخارجيّ** (أمرُ المالك ٢٠٢٦-١١-٠٦، البند ٧) — Worker على Cloudflare بمُشغِّلٍ كلَّ دقيقة، خارج خادمنا:
// خادمٌ ساقطٌ لا يبلّغ عن سقوطه، فالمراقبُ في مكانٍ لا يسقط معه.
//
// - يفحص `api.tajora.ly/health` (جوابُ JSON بـ`status: ok`) و`app.tajora.ly/` (200).
// - **ينبّه عند الفحص الفاشل الثاني المتّصل** (دقيقةٌ بين أوّل فشلٍ وثانيه) **ومرّةً واحدة** — فأسوأُ ما بين السقوط والبريد
//   دقيقتان (أمرُ المالك ٢١/١١ السابع، البند ٢: «خلال دقيقتين»؛ كان الثالثَ فبلغ ثلاثاً) — ثمّ **ينبّه عند العودة** بمدّة السقوط.
//   **والبريدُ يصل هاتفَ المالك عبر تطبيق Gmail** (قِيس ٢١/١١: أربعُ رسائل سقوطٍ وعودةٍ في صندوقه).
// - **التنبيهُ بريدٌ** عبر Email Routing في نطاق tajora.ly إلى العنوان المُتحقَّق منه في الحساب (ربطُ `ALERT`، لا عنوانَ في الشيفرة).
// - **الحالُ في KV ولا يُكتب إلا حين تتغيّر** (أوّلُ سقوط، التنبيه، العودة) — حدُّ الكتابة المجانيّ ١٠٠٠ في اليوم، والفحصُ ١٤٤٠.
// - **مجّانيٌّ بالكامل** (Workers Free: ١٠٠ ألف طلبٍ في اليوم؛ المُشغِّلُ نفسُه لا يُحسب طلباً).
//
// النشرُ: `scripts/deploy-uptime-worker.py` (يقرأ رمزَ الحساب من الأسرار ولا يطبعه).

import { EmailMessage } from "cloudflare:email";

const TARGETS = [
  { key: "api", name: "الخادم (api.tajora.ly)", url: "https://api.tajora.ly/health", json: true },
  { key: "app", name: "تطبيق الراكب على الويب (app.tajora.ly)", url: "https://app.tajora.ly/", json: false },
];
const ALERT_AFTER_MS = 60 * 1000;
const TIMEOUT_MS = 10_000;
const FROM = "monitor@tajora.ly";

// **تذكيرُ تجديد وثائق الشركة** (أمرُ المالك ٢١/١١ السابع، البند ٣) — قبل كلِّ انتهاءٍ بـ٣٠ و١٤ و٣ أيّام.
// **هنا لا في جلسة**: مُشغِّلُ الجلسة يموت بعد أيّام، وهذا الـWorker يعمل كلَّ دقيقةٍ خارج خادمنا وبريدُه يصل المالكَ مقيساً.
// يُرسل **مرّةً واحدةً** يومَه بعد التاسعة صباحاً بتوقيت عمّان، ومفتاحُ «أُرسل» في KV — **ولا بياناتِ وثيقةٍ هنا** (تفاصيلُها في الأسرار).
const REMINDERS = [
  { date: "2026-12-14", doc: "شهادةُ الغرفة التجاريّة", expires: "13/01/2027", left: 30 },
  { date: "2026-12-30", doc: "شهادةُ الغرفة التجاريّة", expires: "13/01/2027", left: 14 },
  { date: "2027-01-10", doc: "شهادةُ الغرفة التجاريّة", expires: "13/01/2027", left: 3 },
  { date: "2026-12-21", doc: "الرخصةُ التجاريّة", expires: "20/01/2027", left: 30 },
  { date: "2027-01-06", doc: "الرخصةُ التجاريّة", expires: "20/01/2027", left: 14 },
  { date: "2027-01-17", doc: "الرخصةُ التجاريّة", expires: "20/01/2027", left: 3 },
];
const REMINDER_HOUR = 9;
// فاتورةُ Contabo شهريّة (طلبُ ٢٠/٠٨: «Cloud VPS 4»، عقدٌ لشهر، €5.50) — وتأخّرُها يوقف الخادمَ كلَّه.
// موعدُها الدقيقُ في لوحة Contabo (حسابُ المالك) لا نقرؤه، فالتذكيرُ يومَ ١٥ من كلِّ شهرٍ قبل ذكرى الطلب (٢٠) (أمرُ المالك ٢٢/١١، البند ١٢)
const MONTHLY_REMINDERS = [
  { day: "15", id: "contabo", subject: "💳 تذكير: فاتورةُ خادم TAXO (Contabo) هذا الشهر", lines: [
    "فاتورةُ الخادم الشهريّة عند Contabo تستحقّ قرابةَ يوم 20 (الطلبُ بدأ 20/08/2026، عقدٌ شهريّ).",
    "تأكّد من لوحة Contabo أنّها مدفوعة أو أنّ الدفعَ التلقائيّ يعمل — تأخّرُها يوقف التطبيقين واللوحة معاً.",
    "",
    "تذكيرٌ آليٌّ من TAXO — يصل يومَ 15 من كلِّ شهر.",
  ] },
];

async function probe(target) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(target.url, {
      signal: controller.signal,
      headers: { "user-agent": "taxo-uptime/1", "cache-control": "no-cache" },
      cf: { cacheTtl: 0 },
    });
    if (response.status !== 200) return { ok: false, why: `HTTP ${response.status}` };
    if (target.json) {
      const body = await response.json().catch(() => null);
      if (!body || body.status !== "ok") return { ok: false, why: `health: ${JSON.stringify(body?.checks ?? body).slice(0, 120)}` };
    }
    return { ok: true };
  } catch (error) {
    return { ok: false, why: error?.name === "AbortError" ? `لا جواب خلال ${TIMEOUT_MS / 1000} ث` : String(error).slice(0, 120) };
  } finally {
    clearTimeout(timer);
  }
}

/** فحصٌ ثانٍ قبل الحكم بالسقوط — نقطةٌ عابرةٌ في الشبكة لا تُحسب دقيقةَ سقوط. */
async function check(target) {
  const first = await probe(target);
  if (first.ok) return first;
  await new Promise((resolve) => setTimeout(resolve, 3000));
  return probe(target);
}

function amman(ms) {
  return new Date(ms).toLocaleString("ar-JO-u-nu-latn", { timeZone: "Asia/Amman", hour12: false });
}

function minutes(ms) {
  return Math.max(1, Math.round(ms / 60000));
}

async function send(env, subject, lines) {
  const body = lines.join("\r\n");
  const raw = [
    `From: TAXO Monitor <${FROM}>`,
    `To: ${env.ALERT_TO}`,
    `Subject: =?UTF-8?B?${btoa(String.fromCharCode(...new TextEncoder().encode(subject)))}?=`,
    `Message-ID: <${crypto.randomUUID()}@tajora.ly>`,
    `Date: ${new Date().toUTCString()}`,
    "MIME-Version: 1.0",
    'Content-Type: text/plain; charset="UTF-8"',
    "Content-Transfer-Encoding: 8bit",
    "",
    body,
  ].join("\r\n");
  await env.ALERT.send(new EmailMessage(FROM, env.ALERT_TO, raw));
}

async function run(env, now) {
  for (const target of TARGETS) {
    const result = await check(target);
    const stateKey = `state:${target.key}`;
    const state = (await env.STATE.get(stateKey, "json")) ?? null; // {since, why, alerted}

    if (result.ok) {
      if (state) {
        if (state.alerted) {
          await send(env, `✅ عاد ${target.name}`, [
            `عاد ${target.name} إلى العمل.`,
            `سقط منذ ${amman(state.since)} (بتوقيت عمّان) — مدّةُ السقوط نحو ${minutes(now - state.since)} دقيقة.`,
            `آخرُ سبب: ${state.why}`,
          ]);
        }
        await env.STATE.delete(stateKey);
      }
      continue;
    }

    if (!state) {
      await env.STATE.put(stateKey, JSON.stringify({ since: now, why: result.why, alerted: false }));
      continue;
    }
    if (!state.alerted && now - state.since >= ALERT_AFTER_MS) {
      await send(env, `🔴 ${target.name} متوقّف`, [
        `${target.name} لا يجيب منذ ${amman(state.since)} (بتوقيت عمّان) — فحصان متتاليان فشلا.`,
        `السبب: ${result.why}`,
        `الرابط: ${target.url}`,
        "",
        "سيصلك بريدٌ آخر حين يعود.",
      ]);
      await env.STATE.put(stateKey, JSON.stringify({ since: state.since, why: result.why, alerted: true }));
    }
  }
}

function ammanParts(ms) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Amman", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", hour12: false })
      .formatToParts(new Date(ms))
      .map((part) => [part.type, part.value]),
  );
  return { date: `${parts.year}-${parts.month}-${parts.day}`, hour: Number(parts.hour) % 24 };
}

async function remind(env, now) {
  const today = ammanParts(now);
  if (today.hour < REMINDER_HOUR) return;
  for (const item of REMINDERS) {
    if (item.date !== today.date) continue;
    const key = `reminder:${item.date}:${item.left}:${item.expires}`;
    if (await env.STATE.get(key)) continue;
    await send(env, `📄 تذكير: ${item.doc} تنتهي بعد ${item.left} يوماً`, [
      `${item.doc} تنتهي في ${item.expires} — بقي ${item.left} يوماً.`,
      "وهي من وثائق التحقّق من الشركة (D-U-N-S وGoogle Play)؛ التجديدُ قبل الانتهاء يمنع توقّفَ التحقّق.",
      "",
      "تذكيرٌ آليٌّ من TAXO — يصل قبل الانتهاء بـ30 و14 و3 أيّام.",
    ]);
    await env.STATE.put(key, String(now));
  }
  for (const item of MONTHLY_REMINDERS) {
    if (today.date.slice(8) !== item.day) continue;
    const key = `monthly:${item.id}:${today.date.slice(0, 7)}`;
    if (await env.STATE.get(key)) continue;
    await send(env, item.subject, item.lines);
    await env.STATE.put(key, String(now));
  }
}

// **رقيبُ النسخ خارج الموقع** (أمرُ المالك ٢٢/١١ الثاني، البند ٣: «نبّهني إن سقط رفع»).
// الحاسوبُ يرفع نسخةً مشفَّرةً يوميّاً إلى Google Drive (`scripts/offsite-backup.sh`) ويكتب نبضاً في KV بعد كلِّ رفعٍ مقيس
// (`backup:last`)، أو سببَ الفشل فوراً (`backup:fail`). **والرقيبُ هنا لا هناك**: حاسوبٌ مطفأٌ أو مهمّةٌ ماتت لا تبلّغ عن نفسها —
// فغيابُ النبض ٢٦ ساعةً إنذارٌ كالفشل نفسِه. **ولا عنوانَ عامٌّ لهذا**: النبضُ يُكتب في KV بواجهة Cloudflare برمز الحساب.
// **وقبل أوّل نبضٍ لا إنذار** — Drive لم يُربط بعد، وإنذارٌ يوميٌّ قبل الربط يعلّم تجاهلَ الإنذار.
const BACKUP_STALE_MS = 26 * 60 * 60 * 1000;

async function watchBackup(env, now) {
  const fail = await env.STATE.get("backup:fail", "json");
  if (fail?.at && (await env.STATE.get("backup:fail-alerted")) !== String(fail.at)) {
    await send(env, "⚠ النسخةُ الاحتياطيّةُ الخارجيّة لم تُرفع", [
      `فشل رفعُ النسخة المشفَّرة إلى Google Drive في ${amman(fail.at)} (بتوقيت عمّان).`,
      `السبب: ${fail.why ?? "غيرُ معروف"}`,
      "",
      "النسخُ على الحاسوب (D:\\taxo-backups) سليمة؛ المتأخّرُ هو النسخةُ خارج الموقع. السجلّ: taxo-deploy-logs\\offsite.",
    ]);
    await env.STATE.put("backup:fail-alerted", String(fail.at));
  }
  const last = Number(await env.STATE.get("backup:last")) || 0;
  if (!last) return;
  if (now - last > BACKUP_STALE_MS && (await env.STATE.get("backup:stale-alerted")) !== String(last)) {
    await send(env, "⚠ لا نسخةَ خارجيّةً منذ أكثر من يوم", [
      `آخرُ نسخةٍ مشفَّرةٍ رُفعت إلى Google Drive في ${amman(last)} (بتوقيت عمّان) — قبل نحو ${Math.round((now - last) / 3600000)} ساعة.`,
      "الأرجح أنّ الحاسوبَ كان مطفأً وقتَ المهمّة اليوميّة، أو أنّ إذنَ Drive انتهى (يُجدَّد بـ scripts/offsite-connect.sh).",
    ]);
    await env.STATE.put("backup:stale-alerted", String(last));
  }
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(Promise.all([run(env, event.scheduledTime), remind(env, event.scheduledTime), watchBackup(env, event.scheduledTime)]));
  },
  // لا مسارَ عامّاً لهذا الـWorker — لا workers.dev ولا Route؛ فهذا لا يُنادى إلا من «اختبار» في لوحة Cloudflare
  async fetch() {
    return new Response("taxo-uptime", { status: 200 });
  },
};
