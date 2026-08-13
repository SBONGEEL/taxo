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
import { useNavigate } from "react-router-dom";

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
import { useSession } from "@/lib/session";
import { useTheme } from "@/lib/theme";
import { arabicDigits, cn } from "@/lib/utils";

export function SettingsScreen() {
  const navigate = useNavigate();
  const { profile, refresh } = useDriver();
  const { choice, toggle } = useTheme();
  const { pink, available, setPink } = useBrand();
  const { user } = useSession();
  const country = useCountryConfig(user?.country_code);
  const womenService = useFeature(user?.country_code, "women_service_enabled");
  const preference = profile?.driver.gender_preference ?? "any";
  const [savingPreference, setSavingPreference] = useState(false);
  // «٢٢:٠٠ – ٠٨:٠٠» بخاناتٍ عربية، و`null` تبقى فراغاً لا صفراً
  const quietHours =
    country?.quiet_hours_start && country.quiet_hours_end
      ? `${arabicDigits(country.quiet_hours_start)} – ${arabicDigits(country.quiet_hours_end)}`
      : null;

  const [marketing, setMarketing] = useState<boolean | null>(null);
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
          onClick={() => navigate(-1)}
          aria-label="رجوع"
          className="text-18 text-muted"
        >
          →
        </button>
        <h1 className="text-20 font-bold text-ink">الإعدادات</h1>
      </div>

      <section className="mb-12 rounded-16 border border-line bg-surface p-15">
        <button
          type="button"
          onClick={() => void flipMarketing()}
          disabled={marketing === null}
          className="flex w-full items-center gap-12 text-start"
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

      <div className="mb-12 overflow-hidden rounded-16 border border-line bg-surface">
        <button
          type="button"
          onClick={toggle}
          className="flex w-full items-center justify-between px-15 py-14"
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
            className="flex w-full items-center justify-between gap-12 border-t border-line px-15 py-14 text-start"
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
        <section className="mb-12 rounded-16 border border-line bg-surface p-15">
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
                  "rounded-11 border px-8 py-11 text-12 font-semibold transition-colors",
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

      <section className="rounded-16 border border-line bg-surface p-15">
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
