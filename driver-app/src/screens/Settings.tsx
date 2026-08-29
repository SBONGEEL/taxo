/** الإعدادات — SPEC القسم 11/8 و12، وشكلُها من `DESIGN.md` §5.3.
 *
 * **مفتاحٌ واحد لا مفاتيح**: `marketing_push_enabled` وحده يملكه المستخدم.
 * إشعاراتُ الرحلة ليست خياراً — من يطفئ «طلبٌ جديد» ينتظر طلباتٍ لا تصله
 * ويظن المنطقة فارغة. ولذلك تقول الشاشة ذلك صراحةً تحت المفتاح.
 *
 * **وساعاتُ الهدوء تُقرأ من `/config` لا تُكتب هنا**: صارت تُنشر لكل دولة
 * ومعها مِنطقتُها الزمنية، فالمعروضُ ما في الجدول لا رقمٌ في الواجهة يخالفه
 * يوم يغيّره المشرف. وغيابُها `null` يعني «لم تُضبط» فتبقى القاعدةُ وحدها —
 * ولا يخترع الرقمَ أحد.
 *
 * **والسِمة الوردية مفتاحٌ ثالث** (المرحلة 10-ج) لا يظهر إلا لمن لها أن
 * تختارها. وهو مفتاحُ **عرضٍ على هذا الجهاز** لا تفضيلٌ على الحساب: من
 * أطفأتها لأن حولها من ينظر لا تريد إطفاءها على هاتفها في بيتها.
 *
 * ولا صفَّ لغة: التطبيق عربيٌّ وحده (`DESIGN-DECISIONS` بند 18).
 */

import { useEffect, useState } from "react";

import { ApiError } from "@/api/client";
import type { GenderPreference } from "@/api/types";
import {
  getNotificationPreferences,
  setNotificationPreferences,
  updateDriver,
} from "@/api/endpoints";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { useBrand } from "@/lib/brand";
import { useCountryConfig, useFeature } from "@/lib/config";
import { useDriver } from "@/lib/driver";
import { biometryLabel } from "@/lib/biometric";
import { useSession } from "@/lib/session";
import { useTheme } from "@/lib/theme";
import {
  notificationSoundEnabled,
  offerSoundEnabled,
  play,
  setNotificationSoundEnabled,
  setOfferSoundEnabled,
  setSoundsEnabled,
  soundsEnabled,
} from "@/lib/sound";
import { digits, cn } from "@/lib/utils";
import { useGoBack } from "@/lib/back";

export function SettingsScreen() {
  const goBack = useGoBack();
  const { profile, refresh } = useDriver();
  const { choice, toggle } = useTheme();
  const { pink, available, setPink } = useBrand();
  const { user, biometry, setBiometric } = useSession();
  const [bioError, setBioError] = useState<string | null>(null);
  const country = useCountryConfig(user?.country_code);
  const womenService = useFeature(user?.country_code, "women_service_enabled");
  const preference = profile?.driver.gender_preference ?? "any";
  const [savingPreference, setSavingPreference] = useState(false);
  // «٢٢:٠٠ – ٠٨:٠٠» بخاناتٍ عربية، و`null` تبقى فراغاً لا صفراً
  const quietHours =
    country?.quiet_hours_start && country.quiet_hours_end
      ? `${digits(country.quiet_hours_start)} – ${digits(country.quiet_hours_end)}`
      : null;

  const [marketing, setMarketing] = useState<boolean | null>(null);
  const [sounds, setSounds] = useState(soundsEnabled);
  const [notifySound, setNotifySound] = useState(notificationSoundEnabled);
  const [offerSound, setOfferSound] = useState(offerSoundEnabled);
  const [alias, setAlias] = useState("");
  const [savingAlias, setSavingAlias] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getNotificationPreferences()
      .then((preferences) => setMarketing(preferences.marketing_push_enabled))
      .catch(() => setMarketing(null));
  }, []);

  useEffect(() => {
    setAlias(profile?.driver.cliq_alias ?? "");
  }, [profile?.driver.cliq_alias]);

  async function flipMarketing() {
    if (marketing === null) return;
    const next = !marketing;
    setMarketing(next); // تفاؤليٌّ: المفتاح يجب أن يتحرك تحت الإصبع
    setError(null);
    try {
      await setNotificationPreferences(next);
    } catch (caught) {
      setMarketing(!next);
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر حفظ التفضيل",
      );
    }
  }

  async function saveAlias() {
    setSavingAlias(true);
    setError(null);
    setDone(null);
    try {
      await updateDriver({ cliq_alias: alias.trim() });
      await refresh();
      setDone("حُفظ ✓");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
    } finally {
      setSavingAlias(false);
    }
  }

  /** الحفظُ فوريّ بلا زرِّ «حفظ»: خيارٌ من ثلاثة لا نصٌّ يُكتب. وعند الفشل
   *  يعود المعروضُ إلى ما في الملف — `refresh` هو مصدر القيمة لا حالةٌ محلية. */
  async function savePreference(next: GenderPreference) {
    setSavingPreference(true);
    setError(null);
    setDone(null);
    try {
      await updateDriver({ gender_preference: next });
      await refresh();
      setDone("حُفظ ✓");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
    } finally {
      setSavingPreference(false);
    }
  }

  return (
    <div className="scr h-full bg-bg px-16 pb-12 pt-safe">
      <div className="mb-16 mt-6 flex items-center gap-10">
        <button
          type="button"
          onClick={() => goBack()}
          aria-label="رجوع"
          className="pressable text-18 text-muted"
        >
          →
        </button>
        <h1 className="text-20 font-bold text-ink">الإعدادات</h1>
      </div>

      {/* **الدخولُ السريع** (قرارُ المالك 2026-08-29) — **ولا يظهر إلا لمن
          يملكه**: `available` كاذبةٌ في المتصفّح وعلى جهازٍ بلا بصمةٍ مسجَّلة،
          **فلا مفتاحَ ولا سطرَ يشرح ما لا يستطيعه القارئ**. ولا بديلَ برقمٍ
          سرّيّ — بابٌ ثانٍ يضعف الأول. */}
      {/* **الغيابُ الصامتُ عائلةُ «الشبكة ضعيفة»** (تصحيحُ المالك 2026-08-29):
          «لا مفتاحَ ولا سطر» صوابُه نصفُه — من لا بصمةَ عنده يفتح الإعدادات
          **فلا يجد شيئاً ولا يعرف لماذا**. فيُكتب سطرٌ يقول **ما يفعله**،
          ولا يدّعي سبباً لا يعرفه: لا «جهازك لا يدعمها» ولا «عطبٌ في
          المستشعر» — كلاهما دعوى. **والرمزُ الذي ردَّته المنصّةُ يُسجَّل في
          السجلّ لا يُعرض.**
          **وفي المتصفّح لا سطرَ ولا مفتاح**: `native` كاذبةٌ هناك، والميزةُ
          ليست غائبةً بل غيرُ موجودةٍ أصلاً. */}
      {biometry?.native && !biometry.available ? (
        <section className="mb-12 card p-15">
          <p className="text-13.5 font-semibold text-ink">الدخول السريع</p>
          <p className="mt-4 text-11 leading-snug text-muted">فعّل قفل الشاشة وبصمةً في إعدادات جهازك لاستعمال الدخول السريع.</p>
        </section>
      ) : null}

      {biometry?.available ? (
        <section className="mb-12 card p-15">
          <SoundToggle
            title={`الدخول بـ${biometryLabel(biometry.kind)}`}
            hint="يفتح جلستك المحفوظة على هذا الجهاز — ولا تُحفظ كلمةُ مرورك أبداً، ويُمحى المحفوظ عند الخروج أو تبديل كلمة المرور."
            on={biometry.enabled}
            onToggle={() => {
              setBioError(null);
              void setBiometric(!biometry.enabled).catch((caught: unknown) => {
                // **الرفضُ يُقال ولا يُقلب مفتاحاً**: مفتاحٌ يبدو مشتعلاً وهو
                // مطفأٌ يجعل المستخدمَ يظنّ أن له باباً لا يُفتح
                setBioError(
                  caught instanceof Error
                    ? caught.message
                    : "تعذّر تفعيل الدخول بالبصمة",
                );
              });
            }}
          />
          {bioError ? (
            <p className="mt-10 text-11 leading-snug text-danger">{bioError}</p>
          ) : null}
        </section>
      ) : null}

      {/* **أصواتُ التطبيق** (`DESIGN.md` §9): ثلاثةُ مفاتيحَ لا اثنان — انظر
          الثالثَ أدناه. وكلُّها **على الجهاز لا الحساب** كالسِمة */}
      <section className="mb-12 card p-15">
        <SoundToggle
          title="أصوات التطبيق"
          hint="نغماتٌ قصيرة عند التحصيل ودخول المال وتنبيهات الاشتراك."
          on={sounds}
          onToggle={() => {
            const next = !sounds;
            setSoundsEnabled(next);
            setSounds(next);
            if (next) play("notify");
          }}
        />
        <div className="mt-13 border-t border-line pt-13">
          <SoundToggle
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
        </div>
        <div className="mt-13 border-t border-line pt-13">
          {/* **مفتاحٌ ثالثٌ مستقلّ، وهو الاستثناء الوحيد** (قرارُ المالك §9.2):
              نغمةُ الطلب الوارد **لا يُسكتها المفتاحُ العام**. كبتنٌ يُطفئ
              الأصواتَ في اجتماعٍ ثم يفوّت طلباتٍ لا يعرف أنها وصلت يخسر دخلاً
              ويلوم التطبيق — والعلاقةُ بين ما أطفأه وما خسره لا تظهر له. فلا
              يُسكتها إلا من قصدها بعينها، وهذا النصُّ يقول ذلك صراحةً */}
          <SoundToggle
            title="نغمة الطلب الوارد"
            hint="تعمل حتى لو أطفأت الأصوات العامة — إطفاؤها من هنا وحده، وقد تفوتك طلبات."
            on={offerSound}
            onToggle={() => {
              const next = !offerSound;
              setOfferSoundEnabled(next);
              setOfferSound(next);
              if (next) play("offer");
            }}
          />
        </div>
      </section>

      <section className="mb-12 card p-15">
        <button
          type="button"
          onClick={() => void flipMarketing()}
          disabled={marketing === null}
          className="pressable flex w-full items-center gap-12 text-start"
        >
          <span className="flex-1">
            <span className="block text-13.5 font-semibold text-ink">
              إشعارات العروض والحملات
            </span>
            <span className="block text-11 leading-snug text-muted">
              إطفاؤها لا يمنع إشعارات الطلبات والرحلات إطلاقاً
            </span>
          </span>
          <span
            className={cn(
              "relative block h-27 w-46 flex-none rounded-full transition-colors",
              marketing ? "bg-ok" : "bg-line",
            )}
          >
            <span
              className={cn(
                "absolute top-3 block size-21 rounded-full bg-surface transition-all",
                marketing ? "start-22" : "start-3",
              )}
            />
          </span>
        </button>

        <div className="mt-13 border-t border-line pt-13">
          <div className="flex items-center justify-between">
            <div className="text-13 font-semibold text-ink">ساعات الهدوء</div>
            {quietHours ? (
              <span dir="ltr" className="text-12.5 font-bold text-ink">
                {quietHours}
              </span>
            ) : null}
          </div>
          <div className="mt-4 text-11 leading-snug text-muted">
            {country?.quiet_hours_timezone
              ? `بتوقيت ${country.quiet_hours_timezone}. `
              : ""}
            تخص الحملات التسويقية وحدها — بطاقة الطلب تصلك في أي وقت.
          </div>
        </div>
      </section>

      <div className="mb-12 overflow-hidden card">
        <button
          type="button"
          onClick={toggle}
          className="pressable flex w-full items-center justify-between px-15 py-14"
        >
          <span className="text-13.5 font-semibold text-ink">المظهر</span>
          <span className="text-12.5 text-muted">
            {choice === "dark" ? "ليلي" : "نهاري"}
          </span>
        </button>

        {/* السِمة الوردية — **إقرارُها وحده يكفي** (البند 6 من قرار المالك
            2026-08-13): عرضٌ بصريٌّ لا يَعِد بخدمة، فلا يُعلَّق على مفتاحٍ
            قُطريٍّ ولا على `gender_verified_at`. أما **استقبالُ الطلبات
            النسائية** فيبقى على الختم في الخلفية — ولا يُخلط بينهما.
            ومن ليست كذلك لا ترى مفتاحاً معطّلاً ولا تفسيراً */}
        {available ? (
          <button
            type="button"
            onClick={() => setPink(!pink)}
            className="pressable flex w-full items-center justify-between gap-12 border-t border-line px-15 py-14 text-start"
          >
            <span>
              <span className="block text-13.5 font-semibold text-ink">
                السِمة الوردية
              </span>
              {/* السببُ مكتوبٌ لأنه ليس ذوقاً: الشاشة تُرى، وإطفاؤها قرارٌ
                  عن المكان الذي أنت فيه لا عن جمال اللون */}
              <span className="mt-3 block text-11 leading-snug text-muted">
                هوية خدمة التوصيل النسائي. أطفئيها متى شئتِ — الشاشة يراها من
                حولك.
              </span>
            </span>
            <span
              className={cn(
                "relative block h-27 w-46 flex-none rounded-full transition-colors",
                pink ? "bg-brand" : "bg-line",
              )}
            >
              <span
                className={cn(
                  "absolute top-3 block size-21 rounded-full bg-surface transition-all",
                  pink ? "start-22" : "start-3",
                )}
              />
            </span>
          </button>
        ) : null}
      </div>

      {/* تفضيلُ جنس الركاب — **دائمٌ لا لكل رحلة**، ومعروضٌ لكل كبتنٍ لا
          للكبتنات وحدهنّ: أن يقصر كبتنٌ عمله على الرجال قرارٌ مثلُ نظيره.
          ولا يظهر والخدمةُ مطفأة في دولته: مفتاحٌ لا أثر له اليوم يجعله يظن
          أن طلباتِه تُصفّى وهي لا تُصفّى (المرحلة 10-ج) */}
      {womenService ? (
        <section className="mb-12 card p-15">
          {/* **«الطلبات» عنوانُ القسم كما في التصميم النسائي (شاشة ٩)**، و«من
              أُقلّ» عنوانُ الحقل داخله: التصميمُ يجمع تحت «الطلبات» ما يحكم ما
              يصل الكبتنَ من عمل، وعنوانٌ واحدٌ للقسم والحقل يجعل القسمَ حقلاً */}
          <h2 className="mb-8 text-11 font-bold tracking-map text-muted">
            الطلبات
          </h2>
          <h3 className="mb-4 text-13.5 font-bold text-ink">من أُقلّ</h3>
          <p className="mb-10 text-11 leading-snug text-muted">
            يسري على كل الطلبات حتى تغيّره. وتضييقُه يقلّل ما يصلك منها.
          </p>
          <div className="grid grid-cols-3 gap-8">
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
                className={cn(
                  "pressable rounded-11 border px-8 py-11 text-12 font-semibold transition-colors",
                  preference === option.value
                    ? "border-ink bg-stripe-a text-ink"
                    : "border-line text-muted",
                )}
              >
                {option.label}
              </button>
            ))}
          </div>
          {/* **شرحُ المطابقة — التصميمُ النسائيُّ (شاشة ٩) يضعه هنا**، وهو
              يجيب السؤالَ الذي يُفتح به أولُ تذكرة دعم: «لماذا قلّت طلباتي؟».
              والشرطُ **ثنائيُّ الاتجاه** في الخلفية منذ 10-ج
              (`dispatch.eligible_driver_ids`)، وهو الاتجاهُ الذي تُسقطه كلُّ
              نسخةٍ من هذه الميزة: راكبٌ اختار «الجميع» لا تصله رحلةُ كبتنةٍ
              قصرت عملَها على النساء. فبلا هذا النصّ يُقرأ التضييقُ عطباً */}
          <div className="mt-14 rounded-12 border border-line bg-surface-2 p-12">
            <p className="text-12 font-semibold text-ink">كيف تعمل المطابقة</p>
            <p className="mt-4 text-11.5 leading-relaxed text-muted">
              تصلك الرحلة فقط إذا قبِل تفضيلُ الراكب جنسَك، وقبِل تفضيلُك جنسَه
              — الاتجاهان معاً. فراكبٌ اختار «الجميع» لن تصله رحلتُك إن كان
              تفضيلُك «النساء فقط».
            </p>
          </div>
        </section>
      ) : null}

      <section className="card p-15">
        <h2 className="mb-4 text-13.5 font-bold text-ink">alias كليك</h2>
        <p className="mb-10 text-11 leading-snug text-muted">
          عليه تستلم تحويلات السحب — تأكد من مطابقته لبنكك.
        </p>
        <Field
          dir="ltr"
          placeholder="ABUMOHD"
          value={alias}
          onChange={(event) => setAlias(event.target.value)}
        />
        <Button
          className="mt-11"
          size="sm"
          loading={savingAlias}
          disabled={alias.trim() === (profile?.driver.cliq_alias ?? "")}
          onClick={() => void saveAlias()}
        >
          حفظ
        </Button>
      </section>

      <div className="mt-12">
        <ErrorNote message={error} />
        <SuccessNote message={done} />
      </div>
    </div>
  );
}


/** صفُّ مفتاحٍ صوتيٍّ بشكل مفاتيح هذه الشاشة — ثلاثةٌ تستعمله. */
function SoundToggle({
  title,
  hint,
  on,
  onToggle,
}: {
  title: string;
  hint: string;
  on: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={title}
      onClick={onToggle}
      className="pressable flex w-full items-center gap-12 text-start"
    >
      <span className="flex-1">
        <span className="block text-13.5 font-semibold text-ink">{title}</span>
        <span className="block text-11 leading-snug text-muted">{hint}</span>
      </span>
      <span
        className={cn(
          "relative block h-27 w-46 flex-none rounded-full transition-colors",
          // **`--brand` لا `--ok`** (§2.3، مُحدَّثة 2026-08-13): كان الأخضرَ هنا
          // والورديَّ في تطبيق الراكب — مفتاحان لفعلٍ واحد بلونين. والأخضرُ
          // يبقى لونَ **الحالة** (متصل، مدفوع) لا لونَ ما يختاره المستخدم
          on ? "bg-brand" : "bg-line",
        )}
      >
        <span
          className={cn(
            "absolute top-3 block size-21 rounded-full bg-surface transition-all",
            on ? "start-22" : "start-3",
          )}
        />
      </span>
    </button>
  );
}
