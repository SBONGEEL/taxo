/** الإعدادات — شاشةٌ مستقلةٌ كما في تصميم الراكب (`pgSettings`).
 *
 * **وما يجمعها ليس التصنيف بل المالك**: كلُّ ما فيها يخصّ **الجهاز الذي بيدك**
 * — مظهرٌ، وسِمةٌ نسائية، وإشعاراتُ عروض — لا الحساب. أما الاسمُ والرقمُ والجنسُ
 * والتفضيلُ الافتراضي فتخصّ الحساب، ومكانُها «حسابي». وشاشةٌ تجمعهما تجعل من
 * جاء يبدّل لوناً يقرأ بياناته الشخصية، ومن جاء يصحّح بياناته يبدّل لوناً.
 *
 * **وساعاتُ الهدوء تُقرأ من `GET /config` لا تُكتب هنا** (قرار 44): رقمٌ في
 * الواجهة يخالف الجدولَ أولَ مرةٍ يُعدَّل، والمنطقةُ الزمنيةُ معه — وإلا قُرئت
 * الساعةُ بتوقيت الجهاز لا بتوقيت الدولة.
 */

import { useEffect, useState } from "react";
import { BellRing, Moon, Sun, SunMoon } from "lucide-react";

import { ApiError } from "@/api/client";
import {
  getNotificationPreferences,
  setNotificationPreferences,
} from "@/api/endpoints";
import { Screen } from "@/components/ui/Screen";
import { ErrorNote } from "@/components/ui/Feedback";
import { useBrand } from "@/lib/brand";
import { useConfig } from "@/lib/config";
import { useSession } from "@/lib/session";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

export function SettingsScreen() {
  const { user } = useSession();
  const { config } = useConfig();
  const { choice, setChoice } = useTheme();
  // **إقرارُها وحده يكفي للسِمة** (البند 6): عرضٌ بصريٌّ لا يَعِد بخدمة
  const { pink, available: themeAvailable, setPink } = useBrand();
  const [marketing, setMarketing] = useState<boolean | null>(null);
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
    <Screen title="الإعدادات" back="/profile">
      <ErrorNote message={error} />
      <div className="space-y-14">
        <section className="card space-y-12 p-16">
          <div className="flex items-start justify-between gap-12">
            <div>
              <p className="flex items-center gap-8 font-medium text-ink">
                <BellRing className="size-20" />
                إشعارات العروض والكوبونات
              </p>
              <p className="mt-2 text-14 text-muted">
                عروضٌ وتخفيضات. إشعارات رحلتك تصلك دائماً.
              </p>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={marketing === true}
              aria-label="إشعارات العروض والكوبونات"
              disabled={marketing === null}
              onClick={() => toggleMarketing(!marketing)}
              className={cn(
                "relative h-28 w-48 shrink-0 rounded-full transition",
                marketing ? "bg-brand" : "bg-line",
              )}
            >
              <span
                className={cn(
                  "absolute top-4 size-20 rounded-full bg-white transition-all",
                  marketing ? "start-24" : "start-4",
                )}
              />
            </button>
          </div>
        </section>

        {/* ساعاتُ الهدوء — **تُعرض ولا تُحرَّر**: قاعدةٌ للحملات يضبطها المشرف
            per-country، ومكانُها هنا كي يعرف من ينتظر عرضاً متى لا يصله.
            و«إشعارات رحلتك تصلك في أي وقت» تُقال صريحةً: الهدوءُ للتسويق وحده */}
        {country?.quiet_hours_start && country?.quiet_hours_end ? (
          <section className="card space-y-4 p-16">
            <div className="flex items-center justify-between gap-12">
              <p className="font-medium text-ink">ساعات الهدوء</p>
              <span dir="ltr" className="text-13 font-semibold text-ink">
                {country.quiet_hours_start} – {country.quiet_hours_end}
              </span>
            </div>
            <p className="text-12 leading-relaxed text-muted">
              تخصّ الحملات التسويقية وحدها — إشعارات رحلتك تصلك في أي وقت.
            </p>
          </section>
        ) : null}

        <section className="card space-y-12 p-16">
          <p className="font-medium text-ink">مظهر التطبيق</p>
          <div className="grid grid-cols-3 gap-8">
            {(
              [
                { value: "system", label: "النظام", icon: SunMoon },
                { value: "light", label: "نهاري", icon: Sun },
                { value: "dark", label: "ليلي", icon: Moon },
              ] as const
            ).map(({ value, label, icon: Icon }) => (
              <button
                key={value}
                type="button"
                onClick={() => setChoice(value)}
                className={cn(
                  "flex flex-col items-center gap-4 rounded-12 border px-8 py-12 text-14 transition",
                  choice === value
                    ? "border-brand bg-brand-soft text-ink"
                    : "border-line text-muted hover:bg-surface-2",
                )}
              >
                <Icon className="size-20" />
                {label}
              </button>
            ))}
          </div>
        </section>

        {/* السِمة الوردية — **إقرارُها وحده يكفي** (البند 6): عرضٌ بصريٌّ لا
            يَعِد بخدمة، فلا يُعلَّق على مفتاحٍ قُطريٍّ ولا على ختمِ الإدارة.
            ومن ليست كذلك لا ترى مفتاحاً معطّلاً ولا رسالةَ اعتذار */}
        {themeAvailable ? (
          <section className="card space-y-12 p-16">
            <div className="flex items-start justify-between gap-16">
              <div>
                <p className="font-medium text-ink">السِمة الوردية</p>
                {/* السببُ مكتوبٌ لأنه ليس ذوقاً: القرارُ عن المكان الذي أنتِ
                    فيه لا عن جمال اللون */}
                <p className="mt-4 text-12 leading-relaxed text-muted">
                  هوية خدمة التوصيل النسائي. أطفئيها متى شئتِ — الشاشة يراها
                  من حولك.
                </p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={pink}
                aria-label="السِمة الوردية"
                onClick={() => setPink(!pink)}
                className={cn(
                  "relative h-28 w-48 flex-none rounded-full transition",
                  pink ? "bg-brand" : "bg-line",
                )}
              >
                <span
                  className={cn(
                    "absolute top-4 size-20 rounded-full bg-surface transition-all",
                    pink ? "start-24" : "start-4",
                  )}
                />
              </button>
            </div>
          </section>
        ) : null}
      </div>
    </Screen>
  );
}
