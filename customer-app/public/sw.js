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
 */

const CACHE = "taxo-shell-v1";
const SHELL = ["/", "/index.html", "/manifest.webmanifest", "/icons/taxo.svg"];

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
      fetch(request).catch(() => caches.match("/index.html").then((r) => r ?? Response.error())),
    );
    return;
  }

  event.respondWith(
    caches.match(request).then(
      (cached) =>
        cached ??
        fetch(request).then((response) => {
          if (response.ok && url.pathname.startsWith("/assets/")) {
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put(request, copy));
          }
          return response;
        }),
    ),
  );
});
