/** الإعدادات — SPEC القسم 11/8 و12، وشكلُها من `DESIGN.md` §5.3.
 *
 * **مفتاحٌ واحد لا مفاتيح**: `marketing_push_enabled` وحده يملكه المستخدم.
 * إشعاراتُ الرحلة ليست خياراً — من يطفئ «طلبٌ جديد» ينتظر طلباتٍ لا تصله
 * ويظن المنطقة فارغة. ولذلك تقول الشاشة ذلك صراحةً تحت المفتاح.
 *
 * **وساعاتُ الهدوء تُعرض بلا أرقام**: قيمُها في `notification_settings`
 * لكل دولة وتُدار من اللوحة، و`GET /config` لا ينشرها. وكتابةُ «٢٢:٠٠ –
 * ٠٨:٠٠» كما في النموذج تعني رقماً في الواجهة قد يخالف الجدول — والقاعدةُ
 * وحدها هي ما يفيد الكبتن: الهدوءُ يخصّ الحملات، وبطاقةُ الطلب تصله في أي
 * وقت (`FUTURE-FEATURES.md` بند 42).
 *
 * ولا صفَّ لغة: التطبيق عربيٌّ وحده (`DESIGN-DECISIONS` بند 18).
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import {
  getNotificationPreferences,
  setNotificationPreferences,
  updateDriver,
} from "@/api/endpoints";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { useDriver } from "@/lib/driver";
import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

export function SettingsScreen() {
  const navigate = useNavigate();
  const { profile, refresh } = useDriver();
  const { choice, toggle } = useTheme();

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
          <div className="text-13 font-semibold text-ink">ساعات الهدوء</div>
          <div className="mt-4 text-11 leading-snug text-muted">
            تحدّدها الإدارة لكل دولة، وتخص الحملات التسويقية وحدها — بطاقة الطلب
            تصلك في أي وقت.
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
      </div>

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
