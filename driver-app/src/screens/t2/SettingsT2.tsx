/** الإعدادات — TAXO 2.0 «C15» (Claude Design «Captain»)، **في الداكن المرسوم وحدَه** (افتراضُ الكبتن).
 *
 * **الحالُ والأفعالُ من بيتٍ واحدٍ للشاشتين** (`screens/Settings.tsx::useCaptainSettings`): كلُّ مفتاحٍ هنا هو مفتاحُ
 * الشاشة القائمة بقاعدته وطلبه — `GET`/`PUT` تفضيلات الإشعارات، و`PATCH /drivers/me` للتفضيل والـalias، والبصمةُ
 * والأصواتُ والتقاريرُ والمظهرُ والسِمةُ على الجهاز. **وما تغيّر طبقةُ العرض**: مجموعاتُ اللوحة بعناوينها، وصفوفٌ
 * بأيقونةٍ ومفتاحٍ بشكلها.
 *
 * **وما رسمته اللوحةُ ولم يُبنَ — بعلّته** (`TAXO2-DESIGN-CORRECTIONS.md` §١٩):
 * - **«قبول تلقائي للطلبات القريبة» و«تطبيق الملاحة» بُنيا بقرار المالك** (§٦١-ط/٦–٧) تفضيلين على الجهاز (`lib/driving-prefs`).
 *   **و«طلبات المطار» و«صوت الإرشاد» «قريباً»** (§٦١-ط/٨–٩): لا رحلاتِ مطارٍ يحرّكها المفتاح، والإرشادُ ينتظر أصواتَ TAXO.
 * - **«الخدمة النسائية — للكبتنات، استقبال الراكبات فقط»** مفتاحاً: التفضيلُ في التطبيق **ثلاثيٌّ لكلِّ كبتن**
 *   (الجميع · النساء فقط · الرجال فقط) — فبقي ثلاثياً بشرحه. **وللكبتنة صفٌّ بالاسم المرسوم إلى صفحته «CW1»** (§٦٢-ج/٢٣،
 *   `WomenModeT2.tsx`) — بالاختيار الثلاثيّ نفسِه.
 * - **«اللغة»**: محذوفةٌ بقرار المالك (§61). **و«تسجيل الخروج»**: بابُه في «حسابي» — وبابان لفعلٍ واحدٍ يفترقان.
 * - **«ساعات الهدوء» بسهم**: تُقرأ من إعداد الدولة ولا تُحرَّر هنا — فبلا سهم.
 *
 * **وما فيها اليومَ ولم يُرسم يبقى** في مجموعاتها: البصمة، والأصواتُ الثلاثة (ونغمةُ الطلب مع «استقبال الطلبات»)،
 * وتقاريرُ الأعطال، وإشعاراتُ العروض، والسِمةُ الوردية.
 */

import { useState, type ReactNode } from "react";

import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { biometryLabel } from "@/lib/biometric";
import { NAV_APPS, autoAcceptEnabled, navApp, setAutoAccept, setNavApp, type NavApp } from "@/lib/driving-prefs";
import { useCaptainSettings } from "@/screens/Settings";

import { WomenModeRowT2 } from "./WomenModeT2";
import "@/taxo2";
import "./t2.css";

/** مفتاحٌ بشكل اللوحة — **`role="switch"`** كمفاتيح الشاشة القائمة. */
function Toggle({
  icon,
  title,
  hint,
  on,
  disabled,
  pinkIcon,
  onToggle,
}: {
  icon: string;
  title: string;
  hint?: string;
  on: boolean;
  disabled?: boolean;
  pinkIcon?: boolean;
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
      <span className={pinkIcon ? "t2-icon t2-srow-icon pink" : "t2-icon t2-srow-icon"} aria-hidden="true">
        {icon}
      </span>
      <span className="t2-srow-main">
        <span className="t2-srow-title">{title}</span>
        {hint ? <span className="t2-srow-hint">{hint}</span> : null}
      </span>
      <span className={on ? "t2-switch on" : "t2-switch"} aria-hidden="true">
        <span className="t2-switch-knob" />
      </span>
    </button>
  );
}

/** صفٌّ لما يُرسم ولا يعمل بعد — **«قريباً» في موضع المفتاح**، فلا مفتاحَ يُحفظ ولا يفعل شيئاً. */
function Soon({ icon, title }: { icon: string; title: string }) {
  return (
    <div className="t2-srow" aria-disabled="true">
      <span className="t2-icon t2-srow-icon" aria-hidden="true">{icon}</span>
      <span className="t2-srow-main">
        <span className="t2-srow-title">{title}</span>
      </span>
      <span className="t2-soon">قريباً</span>
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

export function SettingsT2Screen() {
  const {
    goBack,
    profile,
    choice,
    toggle,
    pink,
    available,
    setPink,
    biometry,
    bioError,
    toggleBiometric,
    country,
    womenService,
    preference,
    savingPreference,
    savePreference,
    quietHours,
    marketing,
    flipMarketing,
    sounds,
    toggleSounds,
    otherSounds,
    toggleOtherSounds,
    offerSound,
    toggleOfferSound,
    crashReports,
    toggleCrashReports,
    alias,
    setAlias,
    savingAlias,
    saveAlias,
    done,
    error,
  } = useCaptainSettings();
  // **تفضيلا القيادة على الجهاز** (§٦١-ط/٦–٧) — يُقرآن مرّةً ويُكتبان مع كلِّ تبديل
  const [autoAccept, setAutoAcceptState] = useState(autoAcceptEnabled);
  const [nav, setNavState] = useState<NavApp>(navApp);
  const [picking, setPicking] = useState(false);

  return (
    <div className="t2 t2-settings scr">
      <div className="t2-head">
        <button type="button" className="t2-back" aria-label="رجوع" onClick={() => goBack()}>
          <span className="t2-icon" aria-hidden="true">arrow_forward</span>
        </button>
        <h1 className="t2-title">الإعدادات</h1>
      </div>

      <Group label="استقبال الطلبات">
        <Toggle
          icon="bolt"
          title="قبول تلقائي للطلبات القريبة"
          hint="أقل من 1 كم فقط — والتطبيقُ مفتوح"
          on={autoAccept}
          onToggle={() => {
            setAutoAccept(!autoAccept);
            setAutoAcceptState(!autoAccept);
          }}
        />
        <Soon icon="flight_takeoff" title="طلبات المطار" />
        {/* **وللكبتنة صفُّ «الخدمة النسائية» إلى CW1** (§٦٢-ج/٢٣) — والاختيارُ الثلاثيُّ نفسُه هناك */}
        {womenService && available ? <WomenModeRowT2 preference={preference} /> : null}
        {/* تفضيلُ جنس الركاب — **دائمٌ لا لكل رحلة، ولكلِّ كبتن**، ولا يظهر والخدمةُ مطفأةٌ في دولته (10-ج) */}
        {womenService && !available ? (
          <div className="t2-srow tall">
            <span className="t2-icon t2-srow-icon" aria-hidden="true">person</span>
            <span className="t2-srow-main">
              <span className="t2-srow-title">من أُقلّ</span>
              <span className="t2-srow-hint">يسري على كل الطلبات حتى تغيّره. وتضييقُه يقلّل ما يصلك منها.</span>
              <span className="t2-seg">
                {(
                  [
                    { value: "any", label: "الجميع" },
                    { value: "female", label: "النساء فقط" },
                    { value: "male", label: "الرجال فقط" },
                  ] as const
                ).map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    disabled={savingPreference}
                    onClick={() => savePreference(option.value)}
                    className={preference === option.value ? "t2-seg-opt on" : "t2-seg-opt"}
                  >
                    {option.label}
                  </button>
                ))}
              </span>
              {/* **شرحُ المطابقة** — يجيب «لماذا قلّت طلباتي؟»، والشرطُ ثنائيُّ الاتجاه في الخلفية */}
              <span className="t2-explain">
                <span className="t2-explain-title">كيف تعمل المطابقة</span>
                تصلك الرحلة فقط إذا قبِل تفضيلُ الراكب جنسَك، وقبِل تفضيلُك جنسَه — الاتجاهان معاً. فراكبٌ اختار
                «الجميع» لن تصله رحلتُك إن كان تفضيلُك «النساء فقط».
              </span>
            </span>
          </div>
        ) : null}
        {/* **نغمةُ الطلب لا يُسكتها المفتاحُ العام** (قرارُ المالك §9.2) — ولذلك تسكن مع استقبال الطلبات */}
        <Toggle
          icon="notifications"
          title="نغمة الطلب الوارد"
          hint="تعمل حتى لو أطفأت الأصوات العامة — إطفاؤها من هنا وحده، وقد تفوتك طلبات."
          on={offerSound}
          onToggle={toggleOfferSound}
        />
      </Group>

      <Group label="الملاحة">
        <button
          type="button"
          className="t2-srow"
          aria-expanded={picking}
          onClick={() => setPicking(!picking)}
        >
          <span className="t2-icon t2-srow-icon" aria-hidden="true">navigation</span>
          <span className="t2-srow-main">
            <span className="t2-srow-title">تطبيق الملاحة</span>
          </span>
          <span className="t2-srow-value">{NAV_APPS.find((app) => app.value === nav)?.label}</span>
          <span className="t2-icon t2-chev" aria-hidden="true">{picking ? "expand_more" : "chevron_left"}</span>
        </button>
        {picking ? (
          <div className="t2-navpick" role="radiogroup" aria-label="تطبيق الملاحة">
            {NAV_APPS.map((app) => (
              <button
                key={app.value}
                type="button"
                role="radio"
                aria-checked={nav === app.value}
                className={nav === app.value ? "t2-navpick-opt on" : "t2-navpick-opt"}
                onClick={() => {
                  setNavApp(app.value);
                  setNavState(app.value);
                  setPicking(false);
                }}
              >
                <span className="t2-navpick-dot" aria-hidden="true" />
                {app.label}
                {app.value === "system" ? <span className="t2-navpick-sub">كما اليوم — يسألك الهاتف</span> : null}
              </button>
            ))}
          </div>
        ) : null}
        <Soon icon="record_voice_over" title="صوت الإرشاد" />
      </Group>

      <Group label="التطبيق">
        <button type="button" className="t2-srow" onClick={toggle}>
          <span className="t2-icon t2-srow-icon" aria-hidden="true">dark_mode</span>
          <span className="t2-srow-main">
            <span className="t2-srow-title">المظهر</span>
          </span>
          <span className="t2-srow-value">{choice === "dark" ? "ليلي" : "نهاري"}</span>
        </button>
        {/* السِمةُ الوردية — **إقرارُها وحده يكفي**، ومن ليست كذلك لا ترى مفتاحاً معطّلاً */}
        {available ? (
          <Toggle
            icon="woman"
            pinkIcon
            title="السِمة الوردية"
            hint="هوية خدمة التوصيل النسائي. أطفئيها متى شئتِ — الشاشة يراها من حولك."
            on={pink}
            onToggle={() => setPink(!pink)}
          />
        ) : null}
        <Toggle
          icon="volume_up"
          title="أصوات التطبيق"
          hint="المفتاحُ الأعلى — إطفاؤه يُسكت كلَّ شيءٍ عدا نغمة الطلب."
          on={sounds}
          onToggle={toggleSounds}
        />
        <Toggle
          icon="volume_up"
          title="أصوات الرحلة والإشعارات"
          hint="بدءُ الرحلة والوصولُ والإنهاءُ والتحصيلُ ودخولُ المال والإشعارات — دون نغمة الطلب."
          on={otherSounds}
          onToggle={toggleOtherSounds}
        />
        <Toggle
          icon="campaign"
          title="إشعارات العروض والحملات"
          hint="إطفاؤها لا يمنع إشعارات الطلبات والرحلات إطلاقاً"
          on={marketing === true}
          disabled={marketing === null}
          onToggle={() => void flipMarketing()}
        />
        {/* **ساعاتُ الهدوء تُقرأ من `/config` لا تُكتب هنا** — فبلا سهمٍ يَعِد بتحرير */}
        <div className="t2-srow">
          <span className="t2-icon t2-srow-icon" aria-hidden="true">bedtime</span>
          <span className="t2-srow-main">
            <span className="t2-srow-title">ساعات الهدوء للعروض</span>
            <span className="t2-srow-hint">
              {country?.quiet_hours_timezone ? `بتوقيت ${country.quiet_hours_timezone}. ` : ""}
              تخص الحملات التسويقية وحدها — بطاقة الطلب تصلك في أي وقت.
            </span>
          </span>
          {quietHours ? (
            <span dir="ltr" className="t2-srow-value">
              {quietHours}
            </span>
          ) : null}
        </div>
        <Toggle
          icon="bug_report"
          title="إرسال تقارير الأعطال"
          hint="تقريرٌ تقنيٌّ بلا رقمك ولا موقعك ولا رصيدك — يقول أين توقّفت الشاشة. وزرُّ «أرسل تقريراً» يعمل ولو أطفأته."
          on={crashReports}
          onToggle={toggleCrashReports}
        />
      </Group>

      <Group label="الحساب">
        {/* **الدخولُ السريع لمن يملكه**، وسطرٌ يقول ما يفعله من لا يملكه — **وفي المتصفّح لا سطرَ ولا مفتاح** */}
        {biometry?.native && !biometry.available ? (
          <div className="t2-srow">
            <span className="t2-icon t2-srow-icon" aria-hidden="true">verified_user</span>
            <span className="t2-srow-main">
              <span className="t2-srow-title">الدخول السريع</span>
              <span className="t2-srow-hint">
                فعّل قفل الشاشة وبصمة إصبع في إعدادات جهازك. وبصمة الوجه في أجهزة سامسونج لا تفتح هذه الميزة.
              </span>
            </span>
          </div>
        ) : null}
        {biometry?.available ? (
          <>
            <Toggle
              icon="verified_user"
              title={`الدخول بـ${biometryLabel(biometry.kind)}`}
              hint="يفتح جلستك المحفوظة على هذا الجهاز — ولا تُحفظ كلمةُ مرورك أبداً، ويُمحى المحفوظ عند الخروج أو تبديل كلمة المرور."
              on={biometry.enabled}
              onToggle={toggleBiometric}
            />
            {bioError ? <p className="t2-srow-error">{bioError}</p> : null}
          </>
        ) : null}
        <div className="t2-srow tall">
          <span className="t2-icon t2-srow-icon" aria-hidden="true">account_balance</span>
          <span className="t2-srow-main">
            <span className="t2-srow-title">حساب CliQ للسحب</span>
            <span className="t2-srow-hint">عليه تستلم تحويلات السحب — تأكد من مطابقته لبنكك.</span>
            <span className="t2-alias">
              <input
                dir="ltr"
                className="t2-input"
                placeholder="ABUMOHD"
                aria-label="alias كليك"
                value={alias}
                onChange={(event) => setAlias(event.target.value)}
              />
              <button
                type="button"
                className="t2-save"
                disabled={savingAlias || alias.trim() === (profile?.driver.cliq_alias ?? "")}
                onClick={() => void saveAlias()}
              >
                {savingAlias ? "…" : "حفظ"}
              </button>
            </span>
          </span>
        </div>
      </Group>

      <div className="t2-settings-notes">
        <ErrorNote message={error} />
        <SuccessNote message={done} />
      </div>
    </div>
  );
}
