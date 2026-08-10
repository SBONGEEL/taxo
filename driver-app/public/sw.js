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
