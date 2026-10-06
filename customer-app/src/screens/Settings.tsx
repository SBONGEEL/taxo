/** الإعدادات — TAXO 2.0 «R23» (`design/t2-new/rider/R23-settings.dc.html`)، **في المظهرين والنسائيّ** — لوحةٌ جديدةٌ من عائلة R15
 *  ومن صفوف C15 (مجموعاتٌ بعناوينها، وصفٌّ بأيقونةٍ ومفتاحٍ بشكل الهوية).
 *
 * **وما يجمعها ليس التصنيف بل المالك**: كلُّ ما فيها يخصّ **الجهاز الذي بيدك**
 * — مظهرٌ، وسِمةٌ نسائية، وإشعاراتُ عروض — لا الحساب. أما الاسمُ والرقمُ والجنسُ
 * والتفضيلُ الافتراضي فتخصّ الحساب، ومكانُها «بياناتي». وشاشةٌ تجمعهما تجعل من
 * جاء يبدّل لوناً يقرأ بياناته الشخصية، ومن جاء يصحّح بياناته يبدّل لوناً.
 *
 * **وساعاتُ الهدوء تُقرأ من `GET /config` لا تُكتب هنا** (قرار 44): رقمٌ في
 * الواجهة يخالف الجدولَ أولَ مرةٍ يُعدَّل، والمنطقةُ الزمنيةُ معه — وإلا قُرئت
 * الساعةُ بتوقيت الجهاز لا بتوقيت الدولة.
 *
 * **والمنطقُ هو هو حرفاً** (الطلباتُ والمفاتيحُ وقواعدُها): `GET`/`PUT` تفضيلات الإشعارات، والبصمةُ والأصواتُ والتقاريرُ والمظهرُ
 * والسِمةُ على الجهاز. **وما تغيّر طبقةُ العرض**: المجموعاتُ الثلاث، و**الصفُّ كلُّه زرُّ مفتاحه** (هدفُ لمسٍ أعرض)، **وسببُ
 * فشل الحفظ تحت صفّه** لا أعلى الشاشة.
 */

import { useEffect, useState, type ReactNode } from "react";

import { ApiError } from "@/api/client";
import { getNotificationPreferences, setNotificationPreferences } from "@/api/endpoints";
import { useGoBack } from "@/lib/back";
import { useBrand } from "@/lib/brand";
import { useConfig } from "@/lib/config";
import { biometryLabel } from "@/lib/biometric";
import { useSession } from "@/lib/session";
import { useTheme } from "@/lib/theme";
import {
  notificationSoundEnabled,
  play,
  setNotificationSoundEnabled,
  setSoundsEnabled,
  soundsEnabled,
} from "@/lib/sound";
import { crashReportsEnabled, setCrashReportsEnabled } from "@/lib/crash-reports";
import { AuthChoice, Icon, Switch } from "@/taxo2";
import { SubHeadT2 } from "@/screens/t2/KitT2";

import "@/screens/t2/t2.css";
import "@/screens/t2/account.css";

/** المظاهرُ الثلاثة بترتيبها — **النظامُ أوّلاً** كما كانت. */
const THEMES = [
  { value: "system" as const, label: "النظام" },
  { value: "light" as const, label: "نهاري" },
  { value: "dark" as const, label: "ليلي" },
];

export function SettingsScreen() {
  const goBack = useGoBack("/account");
  const { user, biometry, setBiometric } = useSession();
  const [bioError, setBioError] = useState<string | null>(null);
  const { config } = useConfig();
  const { choice, setChoice } = useTheme();
  // **إقرارُها وحده يكفي للسِمة** (البند 6): عرضٌ بصريٌّ لا يَعِد بخدمة
  const { pink, available: themeAvailable, setPink } = useBrand();
  const [marketing, setMarketing] = useState<boolean | null>(null);
  const [sounds, setSounds] = useState(soundsEnabled);
  const [crashReports, setCrashReports] = useState(crashReportsEnabled);
  const [notifySound, setNotifySound] = useState(notificationSoundEnabled);
  const [error, setError] = useState<string | null>(null);

  const country = config?.countries.find(
    (entry) => entry.country_code === user?.country_code,
  );

  useEffect(() => {
    getNotificationPreferences()
      .then((preferences) => setMarketing(preferences.marketing_push_enabled))
      .catch(() => setMarketing(null));
  }, []);

  async function toggleMarketing(value: boolean) {
    setMarketing(value);
    setError(null);
    try {
      await setNotificationPreferences(value);
    } catch (caught) {
      setMarketing(!value);
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر حفظ الإعداد",
      );
    }
  }

  return (
    <div className="t2 t2-page pb-nav">
      <SubHeadT2 title="الإعدادات" onBack={goBack} />

      <Group label="الإشعارات">
        <Toggle
          icon="campaign"
          title="إشعارات العروض والكوبونات"
          hint="عروضٌ وتخفيضات. إشعارات رحلتك تصلك دائماً."
          on={marketing === true}
          disabled={marketing === null}
          onToggle={() => void toggleMarketing(!marketing)}
        />
        {/* **سببُ فشل الحفظ تحت صفّه** (§٦٢/٢٠) — والمفتاحُ عاد إلى حاله */}
        {error ? (
          <p className="t2-srow-error" role="alert">
            {error}
          </p>
        ) : null}
        <Toggle
          icon="notifications"
          title="صوت الإشعارات"
          hint="نغمةُ الإشعارات وحدها — مستقلّةٌ عن بقية الأصوات."
          on={notifySound}
          onToggle={() => {
            const next = !notifySound;
            setNotificationSoundEnabled(next);
            setNotifySound(next);
            if (next) play("notify");
          }}
        />
        {/* ساعاتُ الهدوء — **تُعرض ولا تُحرَّر**: قاعدةٌ للحملات يضبطها المشرف
            per-country، ومكانُها هنا كي يعرف من ينتظر عرضاً متى لا يصله.
            و«إشعارات رحلتك تصلك في أي وقت» تُقال صريحةً: الهدوءُ للتسويق وحده.
            **وبلا سهمٍ يَعِد بتحرير** */}
        {country?.quiet_hours_start && country?.quiet_hours_end ? (
          <div className="t2-srow">
            <Icon name="bedtime" className="t2-srow-icon" />
            <span className="t2-srow-main">
              <span className="t2-srow-title">ساعات الهدوء</span>
              <span className="t2-srow-hint">تخصّ الحملات التسويقية وحدها — إشعارات رحلتك تصلك في أي وقت.</span>
            </span>
            <span dir="ltr" className="t2-srow-value">
              {country.quiet_hours_start} – {country.quiet_hours_end}
            </span>
          </div>
        ) : null}
      </Group>

      <Group label="التطبيق">
        <div className="t2-srow tall">
          <Icon name="dark_mode" className="t2-srow-icon" />
          <span className="t2-srow-main">
            <span className="t2-srow-title">مظهر التطبيق</span>
            <AuthChoice label="مظهر التطبيق" value={choice} options={THEMES} onChange={setChoice} />
          </span>
        </div>
        {/* السِمة الوردية — **إقرارُها وحده يكفي** (البند 6): عرضٌ بصريٌّ لا
            يَعِد بخدمة، فلا يُعلَّق على مفتاحٍ قُطريٍّ ولا على ختمِ الإدارة.
            ومن ليست كذلك لا ترى مفتاحاً معطّلاً ولا رسالةَ اعتذار.
            **والسببُ مكتوبٌ لأنه ليس ذوقاً**: القرارُ عن المكان الذي أنتِ فيه لا عن جمال اللون */}
        {themeAvailable ? (
          <Toggle
            icon="woman"
            women
            title="السِمة الوردية"
            hint="هوية خدمة التوصيل النسائي. أطفئيها متى شئتِ — الشاشة يراها من حولك."
            on={pink}
            onToggle={() => setPink(!pink)}
          />
        ) : null}
        {/* **أصواتُ التطبيق** (`DESIGN.md` §9) — **على الجهاز لا الحساب** كالسِمة: من يُسكت تطبيقه في اجتماعٍ لا يريد
            إسكاته على هاتفه في البيت. ومفعَّلةٌ افتراضياً، فالصوتُ ميزةٌ يُطفئها صاحبُها لا ميزةٌ تنتظر إشعالاً */}
        <Toggle
          icon="volume_up"
          title="أصوات التطبيق"
          hint="نغماتٌ قصيرة عند قبول الكبتن ووصوله واكتمال الدفع."
          on={sounds}
          onToggle={() => {
            const next = !sounds;
            setSoundsEnabled(next);
            setSounds(next);
            // تُسمع النغمةُ عند الإشعال — فيعرف صاحبُها ما أشعل
            if (next) play("notify");
          }}
        />
        <Toggle
          icon="bug_report"
          title="إرسال تقارير الأعطال"
          hint="تقريرٌ تقنيٌّ بلا رقمك ولا موقعك ولا رصيدك — يساعدنا نعرف أين توقّفت الشاشة. وزرُّ «أرسل تقريراً» يعمل ولو أطفأته."
          on={crashReports}
          onToggle={() => {
            const next = !crashReports;
            setCrashReportsEnabled(next);
            setCrashReports(next);
          }}
        />
      </Group>

      {/* **الدخولُ السريع** (قرارُ المالك 2026-08-29) — **ولا يظهر إلا لمن يملكه**: `available` كاذبةٌ في المتصفّح وعلى جهازٍ
          بلا بصمةٍ مسجَّلة. **والغيابُ الصامتُ عائلةُ «الشبكة ضعيفة»** (تصحيحُ المالك 2026-08-29): سطرٌ يقول **ما يفعله
          القارئ** ولا يدّعي سبباً لا يعرفه. وفي المتصفّح لا مجموعةَ ولا سطرَ ولا مفتاح — `native` كاذبة. */}
      {biometry?.available || biometry?.native ? (
        <Group label="الدخول">
          {biometry.native && !biometry.available ? (
            <div className="t2-srow">
              <Icon name="fingerprint" className="t2-srow-icon" />
              <span className="t2-srow-main">
                <span className="t2-srow-title">الدخول السريع</span>
                <span className="t2-srow-hint">
                  فعّل قفل الشاشة وبصمة إصبع في إعدادات جهازك. وبصمة الوجه في أجهزة سامسونج لا تفتح هذه الميزة.
                </span>
              </span>
            </div>
          ) : null}
          {biometry.available ? (
            <Toggle
              icon="fingerprint"
              title={`الدخول بـ${biometryLabel(biometry.kind)}`}
              hint="يفتح جلستك المحفوظة على هذا الجهاز — ولا تُحفظ كلمةُ مرورك أبداً، ويُمحى المحفوظ عند الخروج أو تبديل كلمة المرور."
              on={biometry.enabled}
              onToggle={() => {
                setBioError(null);
                void setBiometric(!biometry.enabled).catch((caught: unknown) => {
                  // **الرفضُ يُقال ولا يُقلب مفتاحاً**
                  setBioError(caught instanceof Error ? caught.message : "تعذّر تفعيل الدخول بالبصمة");
                });
              }}
            />
          ) : null}
          {bioError ? (
            <p className="t2-srow-error" role="alert">
              {bioError}
            </p>
          ) : null}
        </Group>
      ) : null}
    </div>
  );
}

function Group({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section>
      <div className="t2-group">{label}</div>
      <div className="t2-list t2-sgroup">{children}</div>
    </section>
  );
}

/** **الصفُّ كلُّه زرُّ المفتاح** — `role="switch"` كمفاتيح الشاشة القائمة، والمفتاحُ المرئيُّ زينةٌ (`Switch` · `aria-hidden`). */
function Toggle({
  icon,
  title,
  hint,
  on,
  disabled,
  women = false,
  onToggle,
}: {
  icon: string;
  title: string;
  hint?: string;
  on: boolean;
  disabled?: boolean;
  /** أيقونةُ الخدمة النسائية بالبرقوق (الهوية) */
  women?: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={title}
      disabled={disabled}
      onClick={onToggle}
      className="t2-srow"
    >
      <Icon name={icon} className={women ? "t2-srow-icon women" : "t2-srow-icon"} />
      <span className="t2-srow-main">
        <span className="t2-srow-title">{title}</span>
        {hint ? <span className="t2-srow-hint">{hint}</span> : null}
      </span>
      <Switch on={on} />
    </button>
  );
}
