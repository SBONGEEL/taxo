/** **بلاغُ النسخة المحفوظة** — قرارُ المالك ٢٠٢٦-١٠-٠٦ (SPEC §٦٢-د/٦).
 *
 * عاملُ الخدمة (`public/sw.js`) **ينتظر جوابَ الخادم ١٫٥ ثانية** ثمّ يعرض القشرةَ المحفوظة ويكمل التحديثَ في الخلفية، **ويضع في
 * رأسها علامة** (`<meta name="taxo-shell" content="saved">`). فإن وُجدت قيل للمستخدم ما يرى — **بما يُعرف لا بسببٍ مظنون** (صوتُ
 * `lib/splash.ts`): «لا يوجد اتصال» حين يقوله الجهاز، و«لم يصل الجواب بعد» حين لا يُعرف أهي شبكتُه أم خادمُنا.
 *
 * **في أعلى الشاشة بلغة بلاغات التطبيق** (`t2-notices`) **وفوق غطاء الترحيب** (٩٥ > ٩٠): من لم يدخل بعد **شاشتُه الترحيبُ نفسُه**،
 * وفي أسفله زرّاه — فبلاغٌ سفليٌّ كان يُرسم تحت الغطاء (قِيس: النصُّ في الصفحة ولا يُرى) أو فوق «حساب جديد».
 * **بعد الترحيب لا فوق حركته** — يُنتظر أن يستقرّ (صفحاتُ التعريف `.cw.page-*`، أو غاب)، **ومرّةً في كلِّ فتح** ولو أُعيد تركيبُ موضعه،
 * **ويُغلق باليد أو يزول بعد ثماني ثوانٍ**: حدثٌ وقع لا مفتاحٌ يُعرَّف به (عمرُ التوست في `DESIGN.md` §2.7 لغرضه).
 */

import { useEffect, useState } from "react";

import "@/taxo2";

/** **علامةُ العامل** — تُقرأ مرّةً عند تحميل الصفحة. */
const SAVED = document.querySelector('meta[name="taxo-shell"]')?.getAttribute("content") === "saved";
const LIFE_MS = 8000;
let shown = false;

/** **استقرّ الترحيبُ أو غاب** — فلا يُغطّى ما يتحرّك. */
function welcomeSettled(): boolean {
  return !document.querySelector(".cw") || !!document.querySelector(".cw[class*='page-']");
}

export function StaleShellNotice() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!SAVED || shown) return;
    const timer = window.setInterval(() => {
      if (!welcomeSettled()) return;
      window.clearInterval(timer);
      shown = true;
      setOpen(true);
    }, 300);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!open) return;
    const timer = window.setTimeout(() => setOpen(false), LIFE_MS);
    return () => window.clearTimeout(timer);
  }, [open]);

  if (!open) return null;
  const offline = navigator.onLine === false;
  return (
    <div className="t2 t2-notices" style={{ zIndex: 95 }}>
      <div className="t2-notice" role="status">
        <span className="t2-notice-icon" aria-hidden="true">
          <span className="t2-icon">schedule</span>
        </span>
        <div className="t2-notice-main">
          <p className="t2-notice-title">{offline ? "لا يوجد اتصال بالإنترنت" : "لم يصل الجواب بعد"}</p>
          <p className="t2-notice-body">
            {offline
              ? "هذه آخرُ نسخةٍ محفوظةٍ من التطبيق."
              : "هذه آخرُ نسخةٍ محفوظةٍ من التطبيق، والجديدُ يُجلب في الخلفية."}
          </p>
        </div>
        <button type="button" className="t2-notice-close" onClick={() => setOpen(false)} aria-label="إغلاق">
          <span className="t2-icon" aria-hidden="true">
            close
          </span>
        </button>
      </div>
    </div>
  );
}
