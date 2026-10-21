/* عاملُ خدمة اللوحة — **إشعاراتُ المالك واللسانُ مغلق** (SPEC §٨١/٢)، **وعاملُ تثبيتها على الهاتف** (`manifest.webmanifest`).
 *
 * **ما يرسمه**: رسالةٌ بياناتٍ وحدَها (`type: admin_alert`) تصل حين لا تكون اللوحةُ أمامَ صاحبها — فيرسمها بأيقونة فئتها وشارة TAXO
 * وزرَّي «افتح» و«مقروء». **واللوحةُ مفتوحةً** يسلّمها Firebase للصفحة فيُسأل الجرسُ ويُعزف صوتُ الفئة هناك. **ومغلقةً يعزف المتصفّحُ
 * صوتَ النظام** — العاملُ لا يعزف ملفّاً (قيدُ المتصفّح، وتقوله صفحةُ الإعداد).
 *
 * **والإعدادُ وعنوانُ الخادم في رابط التسجيل** (`lib/alert-push.ts`) لا مكتوبان هنا — قيمٌ تعيش في عقد FCM وفي البناء.
 *
 * **والمسارُ يُشتقّ من نوع السجلّ ومعرّفه** كـ`recordPath` في `lib/alerts.tsx` حرفاً — **ولا مسارَ يُقرأ من الإشعار**. وهذه نسخةٌ ثانيةٌ
 * لا مفرَّ منها (العاملُ لا يستورد من الحزمة)، **فمن عدّل إحداهما عدّل الأخرى**.
 *
 * **ولا يخبّئ شيئاً**: لا `respondWith` — كلُّ طلبٍ يمضي إلى الشبكة كما كان، و`/api/` خاصّةً لا يُخبّأ أبداً.
 */

importScripts("https://www.gstatic.com/firebasejs/10.14.1/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/10.14.1/firebase-messaging-compat.js");

const params = new URL(self.location.href).searchParams;
const API = params.get("api") || "";

function recordPath(data) {
  const id = encodeURIComponent(data.record_id || "");
  switch (data.record_type) {
    case "ride":
      return `/rides?open=${id}`;
    case "driver":
      return `/drivers?open=${id}`;
    case "rider":
      return `/riders?open=${id}`;
    case "withdrawal":
      return "/finance";
    case "topup_request":
      return "/finance?tab=topups";
    case "feedback":
      return "/feedback";
    case "chat_report":
      return "/chat-reports";
    case "photo_report":
      return "/photo-reports";
    default:
      return `/alerts?kind=${encodeURIComponent(data.kind || "")}`;
  }
}

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));
// **وجودُه شرطُ التثبيت على بعض المتصفّحات** — ولا يجيب عن شيء، فكلُّ طلبٍ يمضي كما كان
self.addEventListener("fetch", () => undefined);

self.addEventListener("notificationclick", (event) => {
  const data = (event.notification && event.notification.data) || {};
  event.notification.close();

  if (event.action === "read") {
    if (!API || !data.read_token || !data.alert_id) return;
    event.waitUntil(
      fetch(`${API}/alerts/${encodeURIComponent(data.alert_id)}/read-by-token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: data.user_id, token: data.read_token }),
      }).catch(() => undefined),
    );
    return;
  }

  const target = recordPath(data);
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      for (const client of windows) {
        if ("focus" in client) {
          client.postMessage({ type: "taxo:admin-alert-open", target });
          return client.focus();
        }
      }
      return self.clients.openWindow(target);
    }),
  );
});

try {
  const config = JSON.parse(params.get("config") || "{}");
  if (config.projectId) {
    firebase.initializeApp(config);
    firebase.messaging().onBackgroundMessage((payload) => {
      const data = payload.data || {};
      if (data.type !== "admin_alert") return;
      const actions = [{ action: "open", title: "افتح" }];
      if (data.read_token) actions.push({ action: "read", title: "مقروء" });
      // **علامةُ «من اليمين» (U+200F) أوّلَ النصّ** (§٨١، 2026-10-21): `dir` يُهمله بعضُ أنظمة الحاسوب (إشعاراتُ ويندوز)، فيبدأ سطرٌ
      // أوّلُه رقمٌ («2 طلبات رحلة · الأردن») من اليسار ويتأخّر الرقمُ عن جملته. والعلامةُ لا تُرى، وتثبّت اتجاهَ السطر أيّاً كان الراسم
      const rtl = (text) => (text ? `\u200f${text}` : text);
      return self.registration.showNotification(rtl(data.title) || "TAXO", {
        body: rtl(data.body) || "",
        icon: `/icons/alerts/alert_${data.tone || "account"}.png`,
        badge: "/icons/alerts/alert_badge.png",
        dir: "rtl",
        lang: "ar",
        // **مفتاحُ الجمع**: صفٌّ يكبر يستبدل إشعارَه بلا صوتٍ ثانٍ — وما عداه يُسمع
        tag: data.tag || data.alert_id || "taxo-admin",
        renotify: data.bumped !== "1",
        data,
        actions,
      });
    });
  }
} catch (error) {
  console.warn("TAXO: إعداد FCM غير صالح", error);
}
