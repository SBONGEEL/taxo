/** زرُّ الرجوع الأصليّ في أندرويد — يُربط بتاريخ الملاح لا بالخروج.
 *
 * **العطبُ الذي أنشأ هذا الملف** (رآه المالك على هاتفه): الرجوعُ من شاشة
 * الإشعارات كان **يخرج من التطبيق كلِّه**. والسببُ أن Capacitor بلا مستمعٍ
 * لهذا الزر يُسلّمه إلى سلوكه الافتراضي: إنهاءُ النشاط. فالتطبيقُ يُغلق من
 * أوّل رجوعٍ في أيِّ شاشةٍ داخلية — وهو أسوأُ من ألّا يعمل الزرُّ أصلاً،
 * لأن المستخدمَ يفقد مكانَه بلا إنذار.
 *
 * **والقاعدةُ واحدةٌ لكلِّ الشاشات لا استثناءَ لشاشة**: إن كان في تاريخ
 * التطبيق ما يُرجَع إليه فارجع إليه، وإلا فاخرج. وهي نفسُ قاعدةِ سهم الرجوع
 * في الرأس (`lib/back.ts`) — فلا يفترق زرُّ الجهاز عن زرِّ الشاشة، والاثنان
 * يقرآن `history.state.idx` نفسَه.
 *
 * **ولا يُستدعى على الويب**: `Capacitor.isNativePlatform()` تحرسه، فالمتصفحُ
 * له زرُّ رجوعه ولا يحتاج من يفسّره له.
 */

import { App } from "@capacitor/app";
import { Capacitor } from "@capacitor/core";

import { AUTH_ROOTS, isWelcomeOpen, reopenWelcome } from "@/components/welcome/gate";
import { closeTopLayer } from "@/lib/back-layers";
import { tr } from "@/lib/i18n";

/** مهلةُ الضغطة الثانية — ما يراه أندرويد نفسُه في تطبيقاته. */
const EXIT_WINDOW_MS = 2000;
let lastRootBack = 0;

/** **«اضغط مرّةً أخرى للخروج»** — سطرٌ عائمٌ يختفي وحدَه، ولا يأخذ لمسة. عقدةٌ لا مكوّن: يُنادى من خارج شجرة React. */
function showExitHint(): void {
  const hint = document.createElement("div");
  hint.className = "t2-exit-hint";
  hint.setAttribute("role", "status");
  hint.textContent = tr("اضغط مرّةً أخرى للخروج");
  Object.assign(hint.style, {
    position: "fixed",
    insetInline: "16px",
    bottom: "calc(92px + env(safe-area-inset-bottom))",
    margin: "0 auto",
    width: "fit-content",
    zIndex: "2147483647",
    padding: "10px 18px",
    borderRadius: "999px",
    background: "var(--t2-inverse, #14181d)",
    color: "var(--t2-on-inverse, #ffffff)",
    fontSize: "13.5px",
    fontWeight: "600",
    pointerEvents: "none",
  });
  document.body.appendChild(hint);
  window.setTimeout(() => hint.remove(), EXIT_WINDOW_MS);
}

/** يبدأ الاستماع، ويُعيد دالةَ إيقافٍ للتنظيف. */
/** **شاشةٌ تأخذ زرَّ الرجوع** (SPEC §٧٦-س): بعد الدفع، الرجوعُ إلى الرئيسية بتاريخٍ نظيف لا إلى شاشة الدفع — والشاشةُ تسجّله وتنزعه */
let override: (() => void) | null = null;
export function setBackOverride(handler: (() => void) | null): void {
  override = handler;
}

export function bindHardwareBack(): () => void {
  if (!Capacitor.isNativePlatform()) return () => undefined;

  // **والرفضُ يُمسك عند التعليق لا عند الفكّ** (الشكلُ الذي أنتج بلاغَ 496): وعدٌ يبقى بلا ماسكٍ حتى التنظيف يطفو
  const handle = App.addListener("backButton", () => {
    // **الطبقةُ العليا قبل كلِّ شيء** (SPEC §٩٣-ب): ورقةٌ أو خريطةٌ موسَّعةٌ أو جولةٌ تُغلق، ولا يُمسّ التاريخ
    if (closeTopLayer()) return;
    if (override) {
      override();
      return;
    }
    const state = window.history.state as { idx?: number } | null;
    const depth = typeof state?.idx === "number" ? state.idx : 0;
    if (depth > 0) {
      window.history.back();
      return;
    }
    // **وشاشتا الدخول ليستا الجذر** (§٦٢/١١): الترحيبُ قبلهما فوق المسارات لا في التاريخ — فالرجوعُ منهما يعيده كسهم الشاشة،
    // **والخروجُ من الترحيب نفسِه**
    if (!isWelcomeOpen() && AUTH_ROOTS.includes(window.location.pathname)) {
      reopenWelcome();
      return;
    }
    // **الخروجُ من جذر التطبيق وحدَه، وبضغطتين** (أمرُ المالك ٢٠٢٦-١١-٠٢، SPEC §٩٣-ب): ضغطةٌ واحدةٌ على الرئيسية كانت تُغلق التطبيقَ
    // بلا إنذار — والأولى الآن تقول «اضغط مرّةً أخرى للخروج»، والثانيةُ في مهلتها تُغلق
    const now = Date.now();
    if (now - lastRootBack < EXIT_WINDOW_MS) {
      void App.exitApp().catch(() => undefined);
      return;
    }
    lastRootBack = now;
    showExitHint();
  }).catch(() => null);

  return () => {
    void handle.then((listener) => listener?.remove());
  };
}
