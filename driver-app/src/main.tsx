import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "@/App";
import "@/index.css";

// **يوقف نبضَ الخريطة حين يغيب التطبيق** (`index.css`: `html.is-hidden`).
// `requestAnimationFrame` تتوقف وحدها في الخلفية، أمّا حركاتُ CSS فتستمر في
// بعض المتصفحات — وتطبيقُ الكبتن يبقى مفتوحاً ساعاتٍ في السيارة.
// وهنا لا في مكوّن: المستمعُ واحدٌ لعمر الصفحة، ولا يُركَّب ويُفكَّك مع رسمة
document.addEventListener("visibilitychange", () => {
  document.documentElement.classList.toggle("is-hidden", document.hidden);
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

// عاملُ الخدمة: قشرةُ التطبيق تعمل بلا شبكة (SPEC القسم 2). يُسجَّل بعد
// التحميل كي لا ينافس أول رسمةٍ على الشبكة، ولا يلمس `/api/` إطلاقاً.
if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => undefined);
  });
}
