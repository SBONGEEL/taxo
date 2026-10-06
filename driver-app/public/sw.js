/* عاملُ خدمةٍ لقشرة التطبيق وحدها.
 *
 * **لا يلمس `/api/` إطلاقاً** (نفس قاعدة تطبيق الراكب): رصيدٌ أو حالةُ رحلةٍ
 * أو بطاقةُ طلبٍ من كاشٍ عمرُه دقيقة كذبةٌ على شاشةٍ يُتخذ عليها قرارٌ مالي.
 * الكاش هنا للأصول الساكنة فقط، فتظهر الشاشة الأولى بلا شبكة بدل بياض.
 */
const CACHE = "taxo-driver-shell-v1";
const SHELL = ["/", "/index.html", "/manifest.webmanifest", "/icons/taxo.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET") return;
  if (url.pathname.startsWith("/api/")) return;
  if (url.origin !== self.location.origin) return;

  // **التنقّلُ في مهلته** (§٦٢-د/٦) — والفهرسُ الذي وصل يُحفظ قشرةً ولو عُرضت المحفوظةُ قبله
  if (event.request.mode === "navigate") {
    const network = fetch(event.request);
    event.waitUntil(
      network
        .then((response) =>
          response.ok ? caches.open(CACHE).then((cache) => cache.put("/index.html", response.clone())) : undefined,
        )
        .catch(() => undefined),
    );
    event.respondWith(answerNavigation(network));
    return;
  }

  // **الحزمُ المبنيّةُ من المخزن أوّلاً** (§٦٢-د/٦): اسمُها يحمل بصمتَها فلا تتغيّر — **وبغيره لا تنفع القشرةُ المحفوظة**:
  // تُعرض في مهلتها ثمّ تنتظر حزمَها من الشبكة نفسِها التي لم تُجب. (كقاعدة تطبيق الراكب.)
  if (url.pathname.startsWith("/assets/")) {
    event.respondWith(
      caches.match(event.request).then(
        (hit) =>
          hit ??
          fetch(event.request).then((response) => {
            if (response.ok) {
              const copy = response.clone();
              caches.open(CACHE).then((cache) => cache.put(event.request, copy));
            }
            return response;
          }),
      ),
    );
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const copy = response.clone();
        caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        return response;
      })
      .catch(() => caches.match(event.request).then((hit) => hit ?? caches.match("/index.html"))),
  );
});

// ------------------------------------------------------------ مهلةُ التنقّل
//
// **قرارُ المالك ٢٠٢٦-١٠-٠٦ (SPEC §٦٢-د/٦)**: كان التنقّلُ «الشبكةُ أوّلاً» **بلا حدّ** — قِيس على S21 ٠٫٤–٠٫٩٣ ث في كلِّ فتح،
// **و٤٫٨ ث حين تعثّرت الشبكة** والقشرةُ في المخزن. **فبعد ١٫٥ ث بلا جوابٍ صالح تُعرض القشرةُ المحفوظة**، ويكمل الطلبُ في الخلفية
// فتُحفظ وتُعرض في الفتحة التالية. **وكلفتُه مكتوبةٌ في القرار**: إصدارٌ جديدٌ يصل صاحبَ الشبكة البطيئة في الفتحة التالية.

/** **مهلةُ التنقّل** — بعدها القشرةُ المحفوظة إن وُجدت. */
const NAV_TIMEOUT_MS = 1500;

/** **جوابُ التنقّل**: الشبكةُ إن أجابت صالحةً في مهلتها، وإلا المحفوظةُ **بعلامةٍ تقرؤها الصفحة** (`StaleShellNotice`).
 *  وجوابٌ غيرُ صالحٍ (خطأُ حافّةٍ ٥xx حين يسقط الأصل) **لا يُعرض بدل قشرةٍ صالحة** — صفحةُ خطأٍ غريبةٌ بدل التطبيق. */
async function answerNavigation(network) {
  const saved = await caches.match("/index.html");
  // **أوّلُ فتحٍ بلا قشرة** — كما كان: ما تقوله الشبكة
  if (!saved) return network.catch(() => Response.error());
  const valid = network.then((response) => (response.ok ? response : null), () => null);
  const timedOut = new Promise((resolve) => setTimeout(() => resolve(null), NAV_TIMEOUT_MS));
  const first = await Promise.race([valid, timedOut]);
  return first ?? markSaved(saved);
}

/** القشرةُ المحفوظةُ **بعلامة** — `<meta name="taxo-shell" content="saved">` في رأسها، فتقول الصفحةُ للمستخدم ما يرى. */
async function markSaved(saved) {
  const html = await saved.text();
  const marked = html.replace(/<head[^>]*>/i, (head) => `${head}<meta name="taxo-shell" content="saved">`);
  return new Response(marked, { headers: { "Content-Type": "text/html; charset=utf-8" } });
}

