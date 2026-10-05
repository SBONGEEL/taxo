/** شاشةُ جولة الأذونات — **واحدةٌ في كلِّ مرّة، وما مُنح لا يُسأل عنه**.
 *
 * **والحالُ تُقرأ من النظام بعد كلِّ طلبٍ ولا تُستنتج من جوابه**: مُلحقٌ يردّ
 * «ممنوح» وإذنُه مسحوبٌ من الإعدادات يكذب، **والمرجعُ واحدٌ هو `permissionStatus`**
 * — وهو نفسُه مرجعُ شاشة الأذونات وتحذير الرئيسية. **ثلاثةُ أسطحٍ ومرجعٌ واحد.**
 *
 * **ولا تُعرض لمن لا ينقصه شيء**: الجولةُ تُخطى كاملةً إن كانت السبعةُ ممنوحة،
 * **ولا تُعرض شاشةُ ترحيبٍ تقول «كلُّ شيءٍ تمام»** — وقتُ الكبتن أثمن.
 *
 * **بلغة TAXO 2.0** (§٦٢/١ و/٦): كانت أوّلَ ما يراه الكبتنُ بعد الدخول **بطرازٍ قديم** (قِيس على S21 ٢٠٢٦-١٠-٠٥). لا لوحةَ
 * لها، **فرُسمت من خطوات C02**: مسارُ «١ / ٤» وعنوانُ الخطوة وسطرُها (`taxo2/Auth`)، وأيقونةُ الإذن في مربّع الجمر الخافت،
 * والفعلُ جمرٌ والتأجيلُ رابطٌ هادئ. **والمنطقُ حرفاً.**
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
import { AuthPage, AuthTitle, AuthTop, Icon } from "@/taxo2";

import "@/components/t2/captain-auth.css";

/** أيقونةُ كلِّ إذن — بالمفتاح لا بالترتيب، ومن خطّ الأيقونات المقتطع (`index.html`). */
const STEP_ICON: Record<string, string> = {
  location: "location_on",
  notifications: "notifications",
  batteryUnrestricted: "battery_charging_full",
  overlay: "layers",
  backgroundLocation: "my_location",
};

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
    <div className="cap-auth cap-perm">
      <AuthPage>
        <AuthTop step={index + 1} total={steps.length} />
        <span className="cap-perm-icon" aria-hidden="true">
          <Icon name={STEP_ICON[step.key] ?? "verified_user"} />
        </span>
        <AuthTitle step title={step.title} sub={step.body} />

        {blockedStep || exhausted ? (
          <p className="cap-perm-warn" role="status">
            <Icon name="info" fill />
            رفضتَ هذا الإذن مرّتين، فلا يعرض النظام نافذته مرّةً أخرى. امنحه من إعدادات التطبيق متى شئت.
          </p>
        ) : null}

        <div className="t2-auth-push" />
        <div className="t2-auth-actions">
          <button type="button" className="t2-button primary" disabled={busy} onClick={() => void act()}>
            {exhausted || blockedStep ? "فتح الإعدادات" : step.cta}
          </button>
          <button type="button" className="cap-perm-later" onClick={skip}>
            {index + 1 >= steps.length ? "لاحقاً" : "ليس الآن"}
          </button>
        </div>
      </AuthPage>
    </div>
  );
}
