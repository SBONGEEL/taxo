/** «رجوع» يعني **من حيث جئت**، والمسارُ المكتوب مخرجٌ احتياطي لا وجهة.
 *
 * العطبُ الذي أنشأ هذا الملف قِيس في المتصفح: الجرسُ في رأس الخريطة يفتح
 * `/account/notifications`، وسهمُ الرجوع كان `back="/account"` — **وجهةٌ ثابتة**
 * — فيهبط الضاغطُ في «حسابي» وهو لم يزره قط، ويُضاء تبويبٌ غيرُ الذي انطلق منه.
 * والشاشةُ لم تخطئ: هي لا تعرف من أين دخلها أحد، فكتبت أباً في الشجرة. **والأبُ
 * في الشجرة ليس الأبَ في الرحلة** — وشاشةٌ لها بابان يجعل أحدَ البابين كذباً.
 *
 * **والحلُّ ليس `navigate(-1)` وحدَه**: من فتح رابطاً مباشراً (إشعارٌ من النظام،
 * أو تبويبةٌ جديدة) لا تاريخَ له داخل التطبيق، فـ`-1` تُخرجه من التطبيق كلِّه —
 * فتُقرأ ضغطةُ «رجوع» إغلاقاً. فيُقاس **تاريخُ الملاح نفسِه**: `history.state.idx`
 * الذي يكتبه react-router لكلِّ إدخال؛ صفرُه يعني «هذا أوّلُ ما فُتح هنا»،
 * وعندها وحدَها يُستعمل المسارُ المكتوب.
 *
 * فالخاصيةُ `back` صارت **مخرجاً احتياطياً**: لا تتغيّر في أيِّ شاشة، ويتغيّر
 * معناها في مكانٍ واحد.
 */

import { clearReturnPoint, stepsBackToHome } from "@/lib/outcome";
import { useCallback } from "react";
import { useNavigate } from "react-router-dom";

/** هل للتطبيق تاريخٌ داخليٌّ يمكن الرجوعُ فيه؟ */
function hasHistory(): boolean {
  const state = window.history.state as { idx?: number } | null;
  return typeof state?.idx === "number" && state.idx > 0;
}

/** **إلى الرئيسية بعد الدفع — بتاريخٍ نظيف** (SPEC §٧٦-س): رجوعٌ إلى موضعها الذي حُفظ عند الذهاب إلى الدفع (`lib/outcome`)، فلا تبقى شاشةُ
 *  الدفع ولا التقييم وراءها يعود إليها زرُّ الرجوع؛ **وبلا موضعٍ محفوظ** (رابطٌ مباشر، عودةٌ من صفحة البطاقة) تُفتح الرئيسيةُ بـ`replace`. */
export function useReturnHome() {
  const navigate = useNavigate();
  return useCallback(() => {
    const state = window.history.state as { idx?: number } | null;
    const steps = stepsBackToHome(typeof state?.idx === "number" ? state.idx : null);
    clearReturnPoint();
    if (steps !== null) navigate(steps);
    else navigate("/", { replace: true });
  }, [navigate]);
}

/** يعيدك من حيث جئت، أو إلى `fallback` إن دخلت من الخارج مباشرةً. */
export function useGoBack(fallback = "/") {
  const navigate = useNavigate();
  return useCallback(() => {
    if (hasHistory()) navigate(-1);
    else navigate(fallback, { replace: true });
  }, [navigate, fallback]);
}
