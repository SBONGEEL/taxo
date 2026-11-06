// **مراقبُ التوفّر الخارجيّ** (أمرُ المالك ٢٠٢٦-١١-٠٦، البند ٧) — Worker على Cloudflare بمُشغِّلٍ كلَّ دقيقة، خارج خادمنا:
// خادمٌ ساقطٌ لا يبلّغ عن سقوطه، فالمراقبُ في مكانٍ لا يسقط معه.
//
// - يفحص `api.tajora.ly/health` (جوابُ JSON بـ`status: ok`) و`app.tajora.ly/` (200).
// - **ينبّه بعد دقيقتين متّصلتين من السقوط** (الفحصُ الثالثُ الفاشل) **ومرّةً واحدة**، ثمّ **ينبّه عند العودة** بمدّة السقوط.
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
const ALERT_AFTER_MS = 2 * 60 * 1000;
const TIMEOUT_MS = 10_000;
const FROM = "monitor@tajora.ly";

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
        `${target.name} لا يجيب منذ ${amman(state.since)} (بتوقيت عمّان) — أكثرَ من دقيقتين.`,
        `السبب: ${result.why}`,
        `الرابط: ${target.url}`,
        "",
        "سيصلك بريدٌ آخر حين يعود.",
      ]);
      await env.STATE.put(stateKey, JSON.stringify({ since: state.since, why: result.why, alerted: true }));
    }
  }
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(run(env, event.scheduledTime));
  },
  // لا مسارَ عامّاً لهذا الـWorker — لا workers.dev ولا Route؛ فهذا لا يُنادى إلا من «اختبار» في لوحة Cloudflare
  async fetch() {
    return new Response("taxo-uptime", { status: 200 });
  },
};
