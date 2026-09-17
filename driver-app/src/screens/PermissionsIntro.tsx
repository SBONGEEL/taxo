/** شاشةُ جولة الأذونات — **واحدةٌ في كلِّ مرّة، وما مُنح لا يُسأل عنه**.
 *
 * **والحالُ تُقرأ من النظام بعد كلِّ طلبٍ ولا تُستنتج من جوابه**: مُلحقٌ يردّ
 * «ممنوح» وإذنُه مسحوبٌ من الإعدادات يكذب، **والمرجعُ واحدٌ هو `permissionStatus`**
 * — وهو نفسُه مرجعُ شاشة الأذونات وتحذير الرئيسية. **ثلاثةُ أسطحٍ ومرجعٌ واحد.**
 *
 * **ولا تُعرض لمن لا ينقصه شيء**: الجولةُ تُخطى كاملةً إن كانت السبعةُ ممنوحة،
 * **ولا تُعرض شاشةُ ترحيبٍ تقول «كلُّ شيءٍ تمام»** — وقتُ الكبتن أثمن.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  alertsAvailable,
  openAppSettings,
  permissionStatus,
  type PermissionStatus,
} from "@/lib/offer-alert";
import {
  BACKGROUND_STEP,
  REFUSAL_LIMIT,
  WALK,
  markWalkDone,
  noteRefusal,
  refusalsOf,
  type WalkStep,
} from "@/lib/permission-walk";

export function PermissionsIntroScreen() {
  const navigate = useNavigate();
  const [status, setStatus] = useState<PermissionStatus | null>(null);
  const [index, setIndex] = useState(0);
  const [busy, setBusy] = useState(false);
  /** مفتاحُ الخطوة التي نفد حوارُها — **لا `boolean` للشاشة كلِّها**. */
  const [blocked, setBlocked] = useState<string | null>(null);

  const read = useCallback(async () => {
    const next = await permissionStatus();
    setStatus(next);
    return next;
  }, []);

  useEffect(() => {
    void read();
    // **تُقرأ عند كلِّ عودة**: الإعدادُ يُمنح خارج التطبيق ولا يمرّ بنا.
    const onShow = () => {
      if (!document.hidden) void read();
    };
    document.addEventListener("visibilitychange", onShow);
    return () => document.removeEventListener("visibilitychange", onShow);
  }, [read]);

  const finish = useCallback(() => {
    markWalkDone();
    navigate("/", { replace: true });
  }, [navigate]);

  // **الترتيبُ: الأربعُ ثمّ الإفصاحُ البارز** — ولا يُعرض الإفصاحُ قبل منح
  // الموقع العادي، وهو شرطُ أندرويد لا اختيارُ تصميم.
  const steps: WalkStep[] = status
    ? [
        ...WALK.filter((s) => !s.read(status)),
        ...(status.location && !BACKGROUND_STEP.read(status) ? [BACKGROUND_STEP] : []),
      ]
    : [];

  useEffect(() => {
    if (!alertsAvailable() || (status && steps.length === 0)) finish();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  if (!status || steps.length === 0) return null;

  const step = steps[Math.min(index, steps.length - 1)];

  // **وحالُ المنع تُنسب إلى خطوتها لا إلى الشاشة** (عطبٌ قِيس على الجهاز
  // 2026-09-12): كان `blocked` حالَ المكوّن، **فيبقى بعد أن تنصرف خطوتُه** —
  // ورُئي بالعين على Note 20: نصُّ «رفضتَ هذا الإذن مرّتين» وزرُّ «فتح
  // الإعدادات» **على خطوة «استثناء من توفير الطاقة»** وهي لم تُرفض قطّ.
  //
  // **وهو من عائلة «شرطٌ داخل الغلاف لا حوله»**: قائمةُ الخطوات تُعاد حسابتُها
  // من الحال، **فتنصرف الخطوةُ ويبقى ما عُلّق عليها**. ولا يمسكه `tsc` ولا
  // اختبارُ وحدة: الحالُ صحيحةُ النوع، **والعطبُ في عمرها لا في قيمتها**.
  const blockedStep = blocked === step.key;
  const refusals = refusalsOf(step.key);
  // **بعد رفضين لا حوارَ يفتحه النظام** — فالزرُّ يقول الحقيقةَ ويفتح الإعداد.
  const exhausted = step.kind === "dialog" && refusals >= REFUSAL_LIMIT;

  const act = async () => {
    setBusy(true);
    setBlocked(null);
    try {
      // **الزرُّ يفعل ما يقوله لا ما يجاوره** (عطبٌ قِيس قبل أن يُشحن
      // 2026-09-11): كان يستدعي `BACKGROUND_STEP.request` حين ينفد الحوار —
      // **ويعمل بالصدفة** لأن الاثنين يفتحان إعداداتِ التطبيق اليوم. ولو
      // تبدّل أحدهما غداً لَفتح زرُّ الإشعارات شاشةَ إذنٍ آخر، **ولا
      // اختبارَ وحدةٍ يمسكه**: التوقيعان متطابقان و`tsc` يقبله صامتاً.
      await (exhausted ? openAppSettings() : step.request());
      const after = await read();
      if (after && !step.read(after) && step.kind === "dialog") {
        const count = noteRefusal(step.key);
        if (count >= REFUSAL_LIMIT) setBlocked(step.key);
      }
    } catch {
      /* رفضٌ أو إغلاقٌ — يُعدّ رفضاً ولا يكسر الشاشة */
      noteRefusal(step.key);
    } finally {
      setBusy(false);
    }
  };

  const skip = () => {
    if (index + 1 >= steps.length) finish();
    else setIndex(index + 1);
  };

  return (
    <div className="scr flex h-full flex-col justify-between bg-bg px-16 pb-16 pt-safe">
      <div className="mt-24">
        <p className="text-11.5 text-muted">
          {index + 1} / {steps.length}
        </p>
        <h1 className="mt-10 text-20 font-bold text-ink">{step.title}</h1>
        <p className="mt-10 text-12.5 leading-note text-muted">{step.body}</p>

        {blockedStep || exhausted ? (
          <p className="mt-14 rounded-14 border border-line bg-surface-2 px-14 py-12 text-11.5 leading-6 text-warn">
            رفضتَ هذا الإذن مرّتين، فلا يعرض النظام نافذته مرّةً أخرى. امنحه من
            إعدادات التطبيق متى شئت.
          </p>
        ) : null}
      </div>

      <div className="space-y-10">
        <button
          type="button"
          disabled={busy}
          onClick={() => void act()}
          className="pressable w-full rounded-14 bg-accent py-14 text-13 font-semibold text-accent-ink disabled:opacity-60"
        >
          {exhausted || blockedStep ? "فتح الإعدادات" : step.cta}
        </button>
        <button
          type="button"
          onClick={skip}
          className="pressable w-full py-10 text-12 text-muted"
        >
          {index + 1 >= steps.length ? "لاحقاً" : "ليس الآن"}
        </button>
      </div>
    </div>
  );
}
