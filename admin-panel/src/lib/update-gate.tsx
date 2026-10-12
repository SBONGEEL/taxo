/** بوّابةُ التحديث عند الإقلاع — **البند ٨ (§39٫٨، §43)**.
 *
 * **ونسخةٌ واحدةٌ في ثلاثة تطبيقات، متطابقةٌ بايتاً ببايت** — يحرسها
 * `check:update-gate` (ومعها `update-gate.css`). **ولا تُستورد من مكانٍ ثالث**:
 * التطبيقاتُ ثلاثُ شجراتٍ مستقلّةٍ في هذا المستودع (لكلٍّ `package.json`
 * و`vite.config` وحزمتُه)، **واستيرادُ مكوّنٍ من خارج الشجرة يجرّ بناءً ثانياً
 * إلى داخل الأول**. فالنسخُ قرارٌ، **وحارسُه هو ما يمنعه أن يفترق** — كبطاقةِ
 * المتجر بحرفها.
 *
 * ## ما تفعله، وما لا تفعله
 *
 * **تسأل عند الإقلاع وعند كلِّ عودةٍ إلى التطبيق**: أيُّ تطبيقٍ أنا، وعلى أيِّ
 * نظام، وما رقمُ حزمتي — **والحكمُ يأتي محسوباً من الخلفية**
 * (`GET /public/app-version`). **ولا تقارن هنا رقمين**: ثلاثةُ تطبيقاتٍ تقارن
 * بأنفسها ثلاثُ نسخٍ من قاعدةٍ واحدة، تفترق أوّلَ ما تتغيّر **ولا شيءَ يفشل**.
 * **والعودةُ سؤالٌ ثانٍ** (2026-10-12): هاتفٌ يُبقي التطبيقَ في ذاكرته أيّاماً
 * لا يُقلعه من جديد، **وحدٌّ يُكتب في اللوحة يجب أن يبلغه حين يفتحه**.
 *
 * **والنظامُ يُرسل** (`android` · `ios`، قرارُ المالك 2026-10-12): رقمُ iOS
 * يُرقَّم وحدَه، **ولكلِّ نظامٍ صفُّه الحاكمُ ورابطُه** — فزرُّ «تحديث» يفتح ما
 * كُتب في اللوحة لهذا التطبيق على هذا النظام: صفحةَ التحميل اليوم، **والمتجرَ
 * يومَ يُنشر فيه** — بلا كودٍ ولا رفع.
 *
 * **ولا تعمل في متصفّح**: `Capacitor.isNativePlatform()` تحرسها — **ولا حزمةَ
 * في متصفّحٍ لتُحدَّث**، وشاشةُ «حدّث تطبيقك» أمام من يفتح موقعاً بابٌ مسدودٌ
 * بلا مخرج.
 *
 * **وشبكةٌ ساقطةٌ لا تقفل أحداً**: أيُّ خطأٍ في السؤال يُقرأ «لا تدخّل».
 * **والقفلُ عقوبةٌ على قِدَمٍ مثبَت**، لا على انقطاعٍ لحظة الإقلاع — ولو
 * قُفل عند الشكّ لَحُبس كلُّ من أقلع تطبيقَه في نفق. **وسقوطُ سؤال العودة لا
 * يرفع حكماً قائماً**: من حُجب لا يُفتح له البابُ لأن شبكتَه انقطعت.
 *
 * **ولا تعرف رقمَ حزمتها؟ لا تُقفل كذلك**: غلافٌ لا يجيب ملحقُه يُرسل بلا
 * رقم، **والخلفيةُ تجيب `ok`**.
 *
 * ## والإلزاميُّ نافذةٌ لا تُغلق، **ولا يعمل التطبيقُ تحتها**
 *
 * **نافذةٌ عائمةٌ بهوية TAXO 2.0** (قرارُ المالك 2026-10-12): رسالةٌ **نصُّها
 * من اللوحة** (`release_notes`)، وزرُّ «تحديث» — **بلا زرِّ إغلاقٍ وبلا خلفيةٍ
 * تُنقر**، ومخرجُها الزرُّ وحدَه. ولذلك لا يُكتب حدٌّ في اللوحة بلا رابطٍ
 * مطروقٍ قبله.
 *
 * **والتطبيقُ لا يُرسم تحتها أصلاً** — لا يُخفى: شاشةٌ مرسومةٌ تحت النافذة
 * تفتح مقابسَها وتسجّل جهازَها وتطلب ما تطلب، **وذاك هو «التطبيقُ القديمُ
 * يعمل»** وإن لم يُرَ. **ولا يُرسم قبل الحكم على الهاتف** حتى `WAIT_MS`:
 * أصحابُ النسخة القديمة لا يرون تطبيقَهم يعمل لحظةً ثمّ يُحجب — **ومن بطؤت
 * شبكتُه يُرسم له التطبيقُ بعد المهلة** ويُحجب إن وصل الحكمُ بعدها.
 *
 * **والاختياريُّ يُغلق ويسكت `reminder_hours`** — رقمٌ من الخلفية لا من هنا.
 * **والكتمُ في `localStorage` لا في الحالة**: من أغلق تنبيهاً ثم أقلع من جديد
 * بعد دقيقةٍ يراه ثانيةً، **وتنبيهٌ يعود في كلِّ إقلاعٍ يُقرأ عطباً**.
 */

import { App } from "@capacitor/app";
import { Capacitor } from "@capacitor/core";
import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import type { ReactNode } from "react";

import { getAppVersion } from "@/api/endpoints";
import type { AppVersion } from "@/api/types";
import { tr } from "@/lib/i18n";
import { Icon } from "@/taxo2";
import "./update-gate.css";

/** التطبيقاتُ الثلاثة — **مرآةُ `ClientApp` في الخلفية**، ويحرسها `check:enums`. */
export type UpdateApp = "rider" | "driver" | "panel";

/** نظامُ الحزمة — **مرآةُ `ReleasePlatform` في الخلفية**. ولا `web`: لا حزمةَ في متصفّح. */
export type ReleasePlatform = "android" | "ios";

/** **متى يعود التنبيهُ الاختياريُّ** — لحظةٌ لا راية، فالمدّةُ تُضبط من اللوحة. */
const SNOOZE_KEY = "taxo.update.snoozed_until";

/** **كم يُنتظر الحكمُ قبل رسم التطبيق على الهاتف** — سؤالٌ عامٌّ بلا جلسةٍ يجيب
 *  في أعشار الثانية، **وشبكةٌ أبطأُ من هذا لا تحبس أحداً**. */
const WAIT_MS = 2000;

function snoozedUntil(): number {
  try {
    return Number(localStorage.getItem(SNOOZE_KEY) ?? "0") || 0;
  } catch {
    return 0;
  }
}

/** **النظامُ كما يقوله الغلاف** — وما ليس أندرويد ولا iOS لا يسأل. */
function platformOf(): ReleasePlatform | null {
  const name = Capacitor.getPlatform();
  return name === "android" || name === "ios" ? name : null;
}

/** يسأل الخلفيةَ مرّةً — **وكلُّ سقوطٍ يُقرأ «لا جواب»**.
 *
 * **ويمرّ بطبقة الأبواب** (`api/endpoints.ts`) لا بـ`fetch` عارٍ: عنوانُ
 * الخادم والمهلةُ وشكلُ الخطأ في بيتٍ واحد، **و`check:contract` يقابل كلَّ
 * نداءٍ بفعلٍ ومسارٍ في الخلفية** — ونداءٌ يبني عنوانَه بيده يقفز فوقه.
 */
async function ask(app: UpdateApp): Promise<AppVersion | null> {
  if (!Capacitor.isNativePlatform()) return null;
  const platform = platformOf();
  if (platform === null) return null;

  let build: number | null = null;
  try {
    const info = await App.getInfo();
    const parsed = Number(info.build);
    build = Number.isFinite(parsed) ? parsed : null;
  } catch {
    build = null;
  }

  try {
    return await getAppVersion(app, build, platform);
  } catch {
    return null;
  }
}

export function UpdateGate({
  app,
  children,
}: {
  app: UpdateApp;
  children: ReactNode;
}) {
  const [verdict, setVerdict] = useState<AppVersion | null>(null);
  // **في المتصفّح لا سؤالَ فلا انتظار**؛ وعلى الهاتف يُنتظر الحكمُ أو المهلة
  const [settled, setSettled] = useState(() => !Capacitor.isNativePlatform());
  const [muted, setMuted] = useState(() => Date.now() < snoozedUntil());

  useEffect(() => {
    let alive = true;
    const check = () => {
      void ask(app).then((answer) => {
        if (!alive) return;
        // **سؤالٌ ساقطٌ لا يمحو حكماً قائماً** — ومن حُجب يبقى محجوباً
        if (answer !== null) setVerdict(answer);
        setSettled(true);
      });
    };
    check();
    const timer = window.setTimeout(() => {
      if (alive) setSettled(true);
    }, WAIT_MS);
    // **العودةُ إلى التطبيق سؤالٌ ثانٍ** — بحدث الصفحة لا بإضافةٍ أصليّة،
    // فيعمل على كلِّ غلافٍ مهما قدُم
    const onVisible = () => {
      if (document.visibilityState === "visible") check();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      alive = false;
      window.clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [app]);

  const mute = useCallback(() => {
    const hours = verdict?.reminder_hours ?? 24;
    try {
      localStorage.setItem(
        SNOOZE_KEY,
        String(Date.now() + hours * 60 * 60 * 1000),
      );
    } catch {
      // تخزينٌ ممتلئٌ أو محجوب — يعود التنبيهُ في الإقلاع القادم، ولا تسقط شاشة
    }
    setMuted(true);
  }, [verdict]);

  if (verdict?.state === "forced" && verdict.download_url) {
    return <Blocking verdict={verdict} />;
  }
  if (!settled) return null;

  return (
    <>
      {children}
      {verdict?.state === "optional" && verdict.download_url && !muted ? (
        <Notice verdict={verdict} onMute={mute} />
      ) : null}
    </>
  );
}

/** **نافذةٌ عائمةٌ بلا مخرجٍ إلا «تحديث»** — ولا زرَّ إغلاقٍ فيها بقصد.
 *
 * **والرسالةُ نصُّ اللوحة كما كُتب** (`release_notes`)، والعنوانُ والزرُّ ثابتان.
 * **والزرُّ رابطٌ لا نداءُ إضافة**: الغلافُ يفتح كلَّ عنوانٍ خارج نطاقه في
 * متصفّح الهاتف أو في المتجر، **فيعمل على غلافٍ بلا `AppLauncher`** — وهذه
 * شاشةٌ لا مخرجَ منها إلا هو، فلا تعلّق مخرجَها بإضافةٍ قد تغيب.
 */
function Blocking({ verdict }: { verdict: AppVersion }) {
  // **إطارُ الإقلاع يُرفع هنا** (قِيس 2026-10-12): `#boot` في `index.html` عقدةٌ `fixed` بطبقة 100 **يرفعها الترحيبُ
  // حين يُركَّب** (`lib/splash.ts` → `removeBootFrame`) — **والترحيبُ لا يُركَّب تحت هذه النافذة**. فبقي الإطارُ فوقها:
  // النافذةُ في DOM ولا يراها أحد، وصاحبُ النسخة القديمة يرى شعارَ الإقلاع إلى الأبد. **والنداءُ هنا لا الاستيراد**:
  // اللوحةُ بلا `splash.ts` وبلا إطار — فهو لا شيءَ هناك، والملفُّ واحدٌ في الثلاثة.
  useLayoutEffect(() => {
    document.getElementById("boot")?.remove();
  }, []);
  return (
    <div
      className="t2 t2-update"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="t2-update-title"
      aria-describedby="t2-update-text"
    >
      <div className="t2-update-card">
        <div className="t2-update-scroll">
          <span className="t2-update-mark" aria-hidden="true">
            <Icon name="system_update" />
          </span>
          <h1 id="t2-update-title" className="t2-update-title">
            {tr("تحديثٌ مطلوبٌ للمتابعة")}
          </h1>
          <p id="t2-update-text" className="t2-update-text">
            {verdict.release_notes ||
              tr("هذه النسخةُ لم تعد مدعومة، ولا يمكن استعمالُ التطبيق قبل تحديثها.")}
          </p>
        </div>
        <a
          href={verdict.download_url ?? "#"}
          target="_blank"
          rel="noreferrer"
          className="t2-button action t2-update-go"
        >
          {tr("تحديث")}
        </a>
        {/* **الرقمُ مُعرِّفٌ لا كمّية** فيبقى لاتينياً: يُقارَن بما تعرضه شاشةُ
            «حول التطبيق» وبما يقوله المشرف على الهاتف */}
        <p className="t2-update-build t2-num" dir="ltr">
          build {verdict.min_supported_build} +
        </p>
      </div>
    </div>
  );
}

/** **تنبيهٌ يُغلق** — ويسكت المدّةَ التي تقولها اللوحة. */
function Notice({
  verdict,
  onMute,
}: {
  verdict: AppVersion;
  onMute: () => void;
}) {
  return (
    <div className="fixed inset-x-0 bottom-0 z-40 mx-auto max-w-modal p-14">
      <div className="rounded-18 border border-line bg-surface p-16 shadow-toast">
        <h2 className="text-13.5 font-bold text-ink">{tr("تحديثٌ جديدٌ متاح")}</h2>
        {verdict.release_notes ? (
          <p className="mt-7 whitespace-pre-line text-11.5 leading-note text-muted">
            {verdict.release_notes}
          </p>
        ) : null}
        <div className="mt-12 flex gap-9">
          <a
            href={verdict.download_url ?? "#"}
            target="_blank"
            rel="noreferrer"
            className="flex-1 rounded-14 bg-accent px-14 py-11 text-center text-12.5 font-bold text-accent-ink"
          >
            {tr("حمّل الآن")}
          </a>
          <button
            type="button"
            onClick={onMute}
            className="rounded-14 border border-line px-14 py-11 text-12.5 text-muted"
          >
            {tr("لاحقاً")}
          </button>
        </div>
      </div>
    </div>
  );
}
