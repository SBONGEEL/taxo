/** بوّابةُ التحديث عند الإقلاع — **البند ٨ (§39٫٨، §43)**.
 *
 * **ونسخةٌ واحدةٌ في ثلاثة تطبيقات، متطابقةٌ بايتاً ببايت** — يحرسها
 * `check:update-gate`. **ولا تُستورد من مكانٍ ثالث**: التطبيقاتُ ثلاثُ شجراتٍ
 * مستقلّةٍ في هذا المستودع (لكلٍّ `package.json` و`vite.config` وحزمتُه)،
 * **واستيرادُ مكوّنٍ من خارج الشجرة يجرّ بناءً ثانياً إلى داخل الأول**. فالنسخُ
 * قرارٌ، **وحارسُه هو ما يمنعه أن يفترق** — كبطاقةِ المتجر بحرفها.
 *
 * ## ما تفعله، وما لا تفعله
 *
 * **تسأل مرّةً عند الإقلاع**: أيُّ تطبيقٍ أنا، وما رقمُ حزمتي — **والحكمُ
 * يأتي محسوباً من الخلفية** (`GET /public/app-version`). **ولا تقارن هنا
 * رقمين**: ثلاثةُ تطبيقاتٍ تقارن بأنفسها ثلاثُ نسخٍ من قاعدةٍ واحدة، تفترق
 * أوّلَ ما تتغيّر **ولا شيءَ يفشل**.
 *
 * **ولا تعمل في متصفّح**: `Capacitor.isNativePlatform()` تحرسها — **ولا حزمةَ
 * في متصفّحٍ لتُحدَّث**، وشاشةُ «حدّث تطبيقك» أمام من يفتح موقعاً بابٌ مسدودٌ
 * بلا مخرج.
 *
 * **وشبكةٌ ساقطةٌ لا تقفل أحداً**: أيُّ خطأٍ في السؤال يُقرأ «لا تدخّل».
 * **والقفلُ عقوبةٌ على قِدَمٍ مثبَت**، لا على انقطاعٍ لحظة الإقلاع — ولو
 * قُفل عند الشكّ لَحُبس كلُّ من أقلع تطبيقَه في نفق.
 *
 * **ولا تعرف رقمَ حزمتها؟ لا تُقفل كذلك**: غلافٌ لا يجيب ملحقُه يُرسل بلا
 * رقم، **والخلفيةُ تجيب `ok`**.
 *
 * ## والإلزاميُّ لا يُغلق، والاختياريُّ يسكت مدّةً تُضبط من اللوحة
 *
 * **شاشةُ الإلزاميِّ بلا زرِّ إغلاقٍ وبلا خلفيةٍ تُنقر** — وهي الحالُ الوحيدةُ
 * في هذه التطبيقات التي تحجب الشاشةَ كلَّها بلا مخرج، **ومخرجُها زرُّ التحميل
 * وحدَه**. ولذلك لا يُكتب حدٌّ في اللوحة بلا رابطٍ مطروقٍ قبله.
 *
 * **والاختياريُّ يُغلق ويسكت `reminder_hours`** — رقمٌ من الخلفية لا من هنا.
 * **والكتمُ في `localStorage` لا في الحالة**: من أغلق تنبيهاً ثم أقلع من جديد
 * بعد دقيقةٍ يراه ثانيةً، **وتنبيهٌ يعود في كلِّ إقلاعٍ يُقرأ عطباً**.
 */

import { App } from "@capacitor/app";
import { Capacitor } from "@capacitor/core";
import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";

import { getAppVersion } from "@/api/endpoints";
import type { AppVersion } from "@/api/types";

/** التطبيقاتُ الثلاثة — **مرآةُ `ClientApp` في الخلفية**، ويحرسها `check:enums`. */
export type UpdateApp = "rider" | "driver" | "panel";

/** **متى يعود التنبيهُ الاختياريُّ** — لحظةٌ لا راية، فالمدّةُ تُضبط من اللوحة. */
const SNOOZE_KEY = "taxo.update.snoozed_until";

function snoozedUntil(): number {
  try {
    return Number(localStorage.getItem(SNOOZE_KEY) ?? "0") || 0;
  } catch {
    return 0;
  }
}

/** يسأل الخلفيةَ مرّةً — **وكلُّ سقوطٍ يُقرأ «لا تدخّل»**.
 *
 * **ويمرّ بطبقة الأبواب** (`api/endpoints.ts`) لا بـ`fetch` عارٍ: عنوانُ
 * الخادم والمهلةُ وشكلُ الخطأ في بيتٍ واحد، **و`check:contract` يقابل كلَّ
 * نداءٍ بفعلٍ ومسارٍ في الخلفية** — ونداءٌ يبني عنوانَه بيده يقفز فوقه.
 */
async function ask(app: UpdateApp): Promise<AppVersion | null> {
  if (!Capacitor.isNativePlatform()) return null;

  let build: number | null = null;
  try {
    const info = await App.getInfo();
    const parsed = Number(info.build);
    build = Number.isFinite(parsed) ? parsed : null;
  } catch {
    build = null;
  }

  try {
    return await getAppVersion(app, build);
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
  const [muted, setMuted] = useState(() => Date.now() < snoozedUntil());

  useEffect(() => {
    let alive = true;
    void ask(app).then((answer) => {
      if (alive) setVerdict(answer);
    });
    return () => {
      alive = false;
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

  return (
    <>
      {children}
      {verdict?.state === "optional" && verdict.download_url && !muted ? (
        <Notice verdict={verdict} onMute={mute} />
      ) : null}
    </>
  );
}

/** **شاشةٌ بلا مخرجٍ إلا التحميل** — ولا زرَّ إغلاقٍ فيها بقصد. */
function Blocking({ verdict }: { verdict: AppVersion }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-bg p-24">
      <div className="w-full max-w-modal rounded-22 border border-line bg-surface p-24 text-center">
        <h1 className="text-20 font-bold text-ink">تحديثٌ مطلوبٌ للمتابعة</h1>
        <p className="mt-10 text-12.5 leading-note text-muted">
          هذه النسخةُ لم تعد مدعومة، ولا يمكن استعمالُ التطبيق قبل تحديثها.
        </p>
        {verdict.release_notes ? (
          <p className="mt-14 whitespace-pre-line rounded-14 border border-line bg-surface-2 px-14 py-12 text-start text-12 leading-note text-ink">
            {verdict.release_notes}
          </p>
        ) : null}
        <a
          href={verdict.download_url ?? "#"}
          target="_blank"
          rel="noreferrer"
          className="mt-18 block rounded-16 bg-accent px-16 py-13 text-13 font-bold text-accent-ink"
        >
          تحميل النسخة الجديدة
        </a>
        {/* **الرقمُ مُعرِّفٌ لا كمّية** فيبقى لاتينياً: يُقارَن بما تعرضه شاشةُ
            «حول التطبيق» وبما يقوله المشرف على الهاتف */}
        <p className="mt-10 text-10.5 text-muted" dir="ltr">
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
        <h2 className="text-13.5 font-bold text-ink">تحديثٌ جديدٌ متاح</h2>
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
            حمّل الآن
          </a>
          <button
            type="button"
            onClick={onMute}
            className="rounded-14 border border-line px-14 py-11 text-12.5 text-muted"
          >
            لاحقاً
          </button>
        </div>
      </div>
    </div>
  );
}
