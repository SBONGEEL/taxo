/** «الإحصاءات» — عدُّ الزيارة وضغطِ زرِّ التحميل (أمرُ المالك ٢٠٢٦-١١-٠٤، `design/SITE-STATS.md`).
 *
 * **لا كوكي ولا معرّف ولا طرفَ ثالث**: نداءٌ واحدٌ إلى خادمنا (`/api/site/hit`) بالمسار واسمِ نطاق المُحيل وحدَه، وثلاثةِ أعلامٍ
 * «أوّلُ زيارةٍ لي اليوم / هذا الأسبوع / هذا الشهر» يحسبها المتصفّحُ من **تاريخٍ** يحفظه عنده — لا هويّةَ فيه، ولا يُرسَل.
 * **والبلدُ يعرفه الخادمُ من Cloudflare**، ولا يُقرأ عنوان.
 *
 * وكلُّ خطأٍ هنا يُبتلع: العدُّ لا يُعطّل صفحةً أبداً.
 */

const KEY = "taxo.seen.v1";

function stamps(now) {
  const day = now.toISOString().slice(0, 10);
  const monday = new Date(now);
  monday.setUTCDate(now.getUTCDate() - ((now.getUTCDay() + 6) % 7));
  return { d: day, w: monday.toISOString().slice(0, 10), m: day.slice(0, 7) };
}

function firsts() {
  const now = stamps(new Date());
  let seen = {};
  try {
    seen = JSON.parse(localStorage.getItem(KEY) || "{}") || {};
  } catch {
    return { d: false, w: false, m: false };
  }
  const flags = { d: seen.d !== now.d, w: seen.w !== now.w, m: seen.m !== now.m };
  try {
    localStorage.setItem(KEY, JSON.stringify(now));
  } catch {
    /* تخزينٌ ممنوع: تُعدّ الزيارةُ ولا يُعدّ الفريد */
  }
  return flags;
}

function send(path, body) {
  try {
    const data = JSON.stringify(body);
    const blob = new Blob([data], { type: "application/json" });
    if (navigator.sendBeacon && navigator.sendBeacon(path, blob)) return;
    fetch(path, { method: "POST", body: data, headers: { "Content-Type": "application/json" }, keepalive: true }).catch(() => {});
  } catch {
    /* لا شيء */
  }
}

function referrerHost() {
  try {
    if (!document.referrer) return null;
    return new URL(document.referrer).hostname || null;
  } catch {
    return null;
  }
}

function appOf(link) {
  const href = link.getAttribute("href") || "";
  if (/taxo-rider|ly\.tajora\.rider/i.test(href)) return "rider";
  if (/taxo-driver|ly\.tajora\.driver/i.test(href)) return "driver";
  return null;
}

export function track() {
  try {
    send("/api/site/hit", { path: location.pathname, ref: referrerHost(), ...firsts() });
    document.addEventListener(
      "click",
      (event) => {
        const link = event.target instanceof Element ? event.target.closest("a[href]") : null;
        const app = link && appOf(link);
        if (app) send("/api/site/click", { app });
      },
      { capture: true },
    );
  } catch {
    /* لا شيء */
  }
}
