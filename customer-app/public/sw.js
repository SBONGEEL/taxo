/* عامل خدمة صغير بيدٍ لا بمولّد (SPEC القسم 2: manifest + service worker).
 *
 * قاعدتان تحكمانه، والثانية أهم:
 *
 * 1. **قشرة التطبيق من الكاش**: الملفات المبنيّة (`/assets/*`) لا تتغير أبداً
 *    لأن اسمها يحمل بصمتها، فتُخدَم من الكاش فوراً.
 * 2. **لا يلمس `/api/` إطلاقاً.** رصيدٌ أو حالةُ رحلةٍ تُخدَم من كاش عمرُه
 *    دقيقة كذبةٌ على شاشةٍ مالية — والراكب يقرأ «الكبتن في الطريق» بعد أن
 *    وصل. كل نداءات الخلفية تمر إلى الشبكة كما هي، وانقطاعُها خطأٌ يُعرض لا
 *    بيانٌ قديم يُعرض.
 *
 * ## وثالثةٌ أُضيفت: **سقفٌ وكنسٌ لـ`/assets`** (قرارُ المالك ٢٠٢٦-٠٩-٢٢)
 *
 * **قِيس على الإنتاج أن المخزنَ بلا سقف**: ١٨ مدخلاً فيها **ثلاثةُ أجيالٍ من
 * الفهرس** ولا شيءَ يكنسها — كلُّ رفعةٍ تُضيف ولا تحذف. صغيرٌ اليومَ (٢٫٩٥
 * ميغا)، **وينمو بلا حدٍّ**.
 *
 * **والجيلُ = حزمةُ المدخل** (`index-*.js`) التي يشير إليها `index.html` حين
 * يُحمَّل. ويُبقى **أحدثُ ثلاثةِ أجيال** ويُكنس ما عداها.
 *
 * **ولمَ ثلاثة**: من فتح التطبيقَ ثمّ وقع رفعان وهو فيه **يحمل فهرساً عمرُه
 * جيلان**، وكلُّ حزمةٍ كسولةٍ يطلبها بعدهما باسمٍ من ذلك الجيل. فالحالي
 * واثنان قبله **هو أقلُّ ما يغطّي «رفعٌ أو رفعان أثناء الجلسة»**، وأكثرُ منه
 * لا يشتري إلا حجماً.
 *
 * ## والقاعدةُ التي لا يكسرها الكنس
 *
 * **لا يُحذف مدخلٌ يشير إليه الجيلُ الحالي** — ولو كان أقدمَ من السقف.
 * و`index.html` لا يسمّي إلا المدخلَ وأوراقَ أسلوبه؛ **والحزمُ الكسولةُ تُسمّى
 * داخل حزمة المدخل** (خريطةُ التحميل المسبق في Vite). فالمحميُّ اتّحادُ ثلاثة:
 * ما يسمّيه `index.html` · وما تسمّيه حزمةُ المدخل · **وما طُلب فعلاً والجيلُ
 * حالٍ** — والأخيرُ يمسك ما قد لا تسمّيه الخريطة.
 *
 * **وحزمةٌ مشتركةٌ بين جيلين** (بصمتُها لم تتغيّر، كـ`mapbox-*`) تبقى ما دام
 * أحدُ الأجيال الباقية يسمّيها — **فالحمايةُ بالاسم لا بعمر أوّل تخزين**.
 *
 * ## وما قبل هذا الملفّ — **لا يُكنس يومَ النشر**
 *
 * المخازنُ القائمةُ لا سجلَّ لأجيالها. **فيُعدّ كلُّ ما فيها جيلاً واحداً
 * «سابقاً»** يوضع أقدمَ الأجيال، **فلا يُحذف شيءٌ يومَ يصل هذا الملفّ** — ومن
 * كان في منتصف جلسةٍ لا يفقد حزمَه. ويسقط ذلك الجيلُ من السقف بعد رفعتين،
 * فيُكنس حينها كسائر الأجيال. **فالمخزنُ لا يُصفَّر ولا يبقى بلا حدّ.**
 */

const CACHE = "taxo-shell-v1";
const SHELL = ["/", "/index.html", "/manifest.webmanifest", "/icons/taxo.svg"];

/** **أحدثُ ثلاثةِ أجيال** — انظر علّتَها في رأس الملفّ. */
const KEEP_GENERATIONS = 3;

/** سجلُّ الأجيال — مفتاحٌ في المخزن نفسِه، **ولا يطلبه التطبيقُ أبداً**. */
const GENERATIONS_KEY = "/__taxo_sw_generations__";

/** اسمُ الجيل السابق لهذا الملفّ — ما كان في المخزن قبل أن يُسجَّل شيء. */
const LEGACY = "legacy";

/** أسماءُ الأصول في نصٍّ — `assets/index-BRR6X1M8.js` ونحوُها. */
const ASSET_NAME = /assets\/[A-Za-z0-9_.-]+\.(?:js|css|woff2?|png|svg|webp|jpg)/g;

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  // الخلفية والخرائط والخطوط: شبكةٌ دائماً، بلا وساطة
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;

  // التنقّل: الشبكة أولاً حتى يصل أحدثُ إصدار، والقشرة عند الانقطاع
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // **الجيلُ يُعرف من الفهرس الذي وصل** — ثمّ يُكنس ما تجاوز السقف
          if (response.ok) event.waitUntil(recordGeneration(response.clone()));
          return response;
        })
        .catch(() => caches.match("/index.html").then((r) => r ?? Response.error())),
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) {
        if (url.pathname.startsWith("/assets/")) {
          event.waitUntil(noteAsset(url.pathname, cached.clone()));
        }
        return cached;
      }
      return fetch(request).then((response) => {
        if (response.ok && url.pathname.startsWith("/assets/")) {
          const copy = response.clone();
          const note = response.clone();
          event.waitUntil(
            caches
              .open(CACHE)
              .then((cache) => cache.put(request, copy))
              .then(() => noteAsset(url.pathname, note)),
          );
        }
        return response;
      });
    }),
  );
});

// ------------------------------------------------------------- الأجيال
//
// **كلُّ كتابةٍ على السجلّ تمرّ بطابورٍ واحد**: طلبان متوازيان يقرآن السجلَّ
// نفسَه ويكتب أحدُهما فوق الآخر **فيضيع اسمٌ من الجيل الحالي** — وهو بعينه
// ما قد يُكنس بعدها. والطابورُ يجعل القراءةَ-ثمّ-الكتابة فعلاً واحداً.

let queue = Promise.resolve();

function serial(task) {
  const run = queue.then(task, task);
  // **ولا يُوقف خطأٌ في مهمّةٍ ما بعدها** — الطابورُ لا يموت بعطبٍ واحد
  queue = run.catch(() => undefined);
  return run;
}

async function readGenerations(cache) {
  const hit = await cache.match(GENERATIONS_KEY);
  if (!hit) return null;
  try {
    const list = await hit.json();
    return Array.isArray(list) ? list : null;
  } catch {
    return null;
  }
}

function writeGenerations(cache, list) {
  return cache.put(
    GENERATIONS_KEY,
    new Response(JSON.stringify(list), {
      headers: { "Content-Type": "application/json" },
    }),
  );
}

function namesIn(text) {
  return new Set((text.match(ASSET_NAME) ?? []).map((name) => `/${name}`));
}

/** **أوّلُ تشغيلٍ لهذا الملفّ** — كلُّ ما في المخزن جيلٌ واحدٌ «سابق». */
async function legacyGeneration(cache) {
  const keys = await cache.keys();
  const assets = keys
    .map((key) => new URL(key.url).pathname)
    .filter((path) => path.startsWith("/assets/"));
  return { entry: LEGACY, assets, parsed: true };
}

/** يُسجَّل الجيلُ الذي أعلنه `index.html` — **ويُكنس ما تجاوز السقف**. */
function recordGeneration(response) {
  return serial(async () => {
    const html = await response.text();
    const names = namesIn(html);
    const entry = [...names].find((name) => /^\/assets\/index-[^/]+\.js$/.test(name));
    // **لا مدخلَ يُعرف ⇒ لا جيلَ يُسجَّل ولا كنس** — لا يُحذف شيءٌ بتخمين
    if (!entry) return;

    const cache = await caches.open(CACHE);
    let list = await readGenerations(cache);
    if (!list) list = [await legacyGeneration(cache)];

    const existing = list.find((gen) => gen.entry === entry);
    const current = existing ?? { entry, assets: [], parsed: false };
    current.assets = [...new Set([...current.assets, ...names])];

    // **الأحدثُ أوّلاً** — والجيلُ العائدُ يعود إلى الرأس لا يُكرَّر
    list = [current, ...list.filter((gen) => gen.entry !== entry)].slice(
      0,
      KEEP_GENERATIONS,
    );

    // **حزمةُ المدخل إن كانت في المخزن تُقرأ الآن** — زائرٌ عائدٌ على الجيل نفسِه
    if (!current.parsed) {
      const cached = await cache.match(entry);
      if (cached) {
        current.assets = [...new Set([...current.assets, ...namesIn(await cached.text())])];
        current.parsed = true;
      }
    }
    await writeGenerations(cache, list);

    // **لا كنسَ قبل أن تُعرف خريطةُ الجيل الحالي** — وإلا حُذفت حزمةٌ يسمّيها
    // المدخلُ ولم تُقرأ بعد. **والقاعدةُ مضمونةٌ بالبناء لا بالاحتمال**: جيلٌ
    // جديدٌ لم يصل مدخلُه يُؤجِّل الكنسَ إلى `noteAsset` حين يصل.
    if (current.parsed) await sweep(cache, list);
  });
}

/** أصلٌ طُلب — **يُضاف إلى الجيل الحالي**، وحزمةُ المدخل تُقرأ مرّةً لخريطتها. */
function noteAsset(path, response) {
  return serial(async () => {
    const cache = await caches.open(CACHE);
    const list = await readGenerations(cache);
    // **لا سجلَّ بعد ⇒ لا شيء** — السجلُّ يُولد من تنقّلٍ لا من أصل
    if (!list || !list.length) return;

    const current = list[0];
    let changed = false;
    let mapped = false;
    if (!current.assets.includes(path)) {
      current.assets.push(path);
      changed = true;
    }
    // **خريطةُ الحزم الكسولة داخل المدخل** — تُقرأ مرّةً لكلِّ جيل
    if (path === current.entry && !current.parsed) {
      const text = await response.text();
      current.assets = [...new Set([...current.assets, ...namesIn(text)])];
      current.parsed = true;
      changed = true;
      mapped = true;
    }
    if (changed) await writeGenerations(cache, list);
    // **الكنسُ المؤجَّل** — الآن وقد عُرفت خريطةُ الجيل الحالي
    if (mapped) await sweep(cache, list);
  });
}

/** **يُحذف من `/assets` ما لا يسمّيه جيلٌ باقٍ** — ولا شيءَ خارجَها. */
async function sweep(cache, list) {
  const keep = new Set(list.flatMap((gen) => gen.assets));
  const keys = await cache.keys();
  await Promise.all(
    keys
      .filter((key) => {
        const path = new URL(key.url).pathname;
        // **القشرةُ والسجلُّ خارجَ الكنس** — وليسا تحت `/assets` أصلاً
        return path.startsWith("/assets/") && !keep.has(path);
      })
      .map((key) => cache.delete(key)),
  );
}
