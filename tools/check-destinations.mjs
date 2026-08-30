#!/usr/bin/env node
/** `check:destinations` — **مقصدُ بلاطةٍ لا شاشةَ له عند من يراه** (2026-08-30).
 *
 * **ووقع مقيساً في اليوم الذي بُني فيه الجدول**: `SERVICE_DESTINATIONS` كُتب
 * **عن ظهر قلب** لا من جداول المسارات، **فحمل ثلاثةَ عناوينَ لا وجودَ لها**:
 * `/missions` (والمبنيُّ `/account/missions`)، و`/withdrawals` (والمبنيُّ
 * `/wallet/withdrawals`)، و`/bookings` (والمبنيُّ `/account/bookings` **في
 * تطبيق الراكب وحدَه**). **وبُذرت بلاطةُ كبتنٍ تشير إلى مسار الراكب** —
 * فيضغط الكبتنُ ويقع على `path="*"`.
 *
 * **والبابُ كان يحرس نفسَه بنفسه**: `require_destination` يسأل «أهذا في
 * القاموس؟» **والقاموسُ هو الكاذب**. فحارسٌ مرجعُه قائمةٌ تُكتب بيدٍ **يحرس
 * الكتابةَ لا الواقع** — وهو «الشرطُ الذي يُقرأ حراسةً وهو تعطيل» في ثوبٍ ثانٍ.
 *
 * ## فالمرجعُ هنا جدولا المسارات أنفسُهما
 *
 * يُقرأ `path="…"` من `App.tsx` في التطبيقين، **ويُقارَن الاتجاهان**:
 *
 * 1. **لا مقصدَ في القاموس بلا مسارٍ مبنيّ** — لكلِّ دورٍ يُعلنه.
 * 2. **ولا دورَ يُعلَن ولا يملكه**: `(RIDER, DRIVER)` على مسارٍ في أحدهما
 *    فقط **يُقرأ إذناً لبلاطةٍ مشتركةٍ تكسر عند نصف الناس**.
 *
 * **ولا يقيس العكس**: مسارٌ مبنيٌّ ليس في القاموس **ليس عطباً** — القاموسُ
 * قائمةُ ما **يجوز** أن تشير إليه بلاطة، لا فهرسُ الشاشات. وذلك مكتوبٌ هنا
 * كي لا يُقرأ سكوتُه شهادةً.
 */

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const APPS = { rider: "customer-app", driver: "driver-app" };

/** المساراتُ الساكنةُ وحدَها — **وما فيه `:` معلمةٌ لا عنوانٌ تشير إليه بلاطة**. */
function routesOf(app) {
  const src = readFileSync(join(ROOT, app, "src", "App.tsx"), "utf8");
  return new Set(
    [...src.matchAll(/path="([^"]+)"/g)]
      .map((m) => m[1])
      .filter((path) => !path.includes(":") && path !== "*"),
  );
}

/** القاموسُ من مصدره — **بقراءةِ نصٍّ لا باستيراد**: هذا ملفُّ عقدةٍ ولا
 *  مُفسِّرَ بايثون هنا، **والشكلُ ثابتٌ يُقرأ سطراً سطراً**. */
function declared() {
  const src = readFileSync(
    join(ROOT, "backend", "app", "services", "storefront.py"),
    "utf8",
  );
  const block = src.match(
    /SERVICE_DESTINATIONS: dict\[str, tuple\[UserRole, \.\.\.\]\] = \{([\s\S]*?)\n\}/,
  );
  if (!block) {
    console.error("✗ لم يُعثر على `SERVICE_DESTINATIONS` — أَبُدِّل شكلُه؟");
    process.exit(1);
  }
  const rows = new Map();
  for (const line of block[1].split("\n")) {
    const m = line.match(/^\s*"([^"]+)":\s*\(([^)]*)\)/);
    if (!m) continue;
    const roles = [...m[2].matchAll(/UserRole\.(\w+)/g)].map((r) =>
      r[1].toLowerCase(),
    );
    rows.set(m[1], roles);
  }
  return rows;
}

const routes = { rider: routesOf(APPS.rider), driver: routesOf(APPS.driver) };
const table = declared();
const faults = [];

for (const [destination, roles] of table) {
  if (roles.length === 0) {
    faults.push(`«${destination}» بلا دورٍ واحد — فلا أحدَ يراها`);
    continue;
  }
  for (const role of roles) {
    if (!routes[role]) {
      faults.push(`«${destination}» تُعلن دوراً لا أعرفه: ${role}`);
      continue;
    }
    if (!routes[role].has(destination)) {
      const who = role === "driver" ? "الكبتن" : "الراكب";
      faults.push(
        `«${destination}» مُعلَنٌ لـ${who} — **ولا مسارَ له في ${APPS[role]}/src/App.tsx**`,
      );
    }
  }
}

if (faults.length > 0) {
  console.error("\n✗ مقاصدُ تَعِد بشاشاتٍ لا وجودَ لها:\n");
  for (const fault of faults) console.error(`  ${fault}`);
  console.error(
    "\nالمرجعُ جدولُ المسارات لا الذاكرة — انسخ العنوانَ من `App.tsx` كما هو،",
  );
  console.error("أو اسحب الدورَ الذي لا يملكه من الصفّ.\n");
  process.exit(1);
}

const stamp = new Date().toISOString().slice(0, 16).replace("T", "T") + "Z";
console.log(
  `✓ check:destinations · ${table.size} مقصداً مُعلَناً لكلٍّ منها مسارٌ مبنيٌّ ` +
    `عند كلِّ من يراه (الراكب ${routes.rider.size} · الكبتن ${routes.driver.size}) · ${stamp}`,
);
