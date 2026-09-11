/** تحذيرُ الأذونات في الرئيسية — **يُرى بلا أن يُبحث عنه** (قرارُ المالك ٢٠٢٦-٠٩-١١).
 *
 * **العلّةُ التي أنشأته مقيسة**: شاشةُ `/account/permissions` تعرض الحالَ
 * كاملاً — **ولا يفتحها إلا من يشكّ أن شيئاً معطوب**. وكان في الرئيسية سطرٌ
 * واحدٌ لرفض الإشعارات وحدَه، **فانطفاءُ قناة «طلبات الرحلات» لا يظهر في
 * الرئيسية البتّة** — والكبتنُ يفوت رحلةً ولا سببَ ظاهر. وهو أخطرُ الأحوال
 * لأن كلَّ ما يراه صمتٌ يُقرأ «لا طلبات اليوم».
 *
 * **وثلاثةُ حدودٍ تُقال قبل أن يُصدَّق:**
 *
 * 1. **المانعُ يفترق عن الناصح** — ما بلا يقف العملُ أحمرُ في الأعلى، وما
 *    يُضعفه دونه تنبيهٌ تحته. **ورتبةٌ واحدةٌ للكلِّ تجعل الحرجَ يُقرأ
 *    اقتراحاً** (وهو نصُّ قرار المالك في شاشة الأذونات، مطبَّقٌ هنا).
 * 2. **ولا تُفتح شاشةُ نظامٍ من تلقائها أبداً** — الزرُّ يفتحها بالضغط وحدَه.
 *    **من رفض إذناً يرى التحذيرَ ولا يُلاحَق**، وملاحقتُه تجعله يطفئ
 *    التطبيق لا الإذن.
 * 3. **والحالُ تُقرأ في كلِّ فتحةٍ ولا تُخزَّن** — المستخدمُ يسحب الإذنَ من
 *    إعدادات الهاتف ولا يمرّ بنا، **فذاكرةٌ عن إذنٍ مُنح أمسِ تكذب اليوم**.
 *
 * **والسجلُّ واحدٌ**: النصوصُ والتصنيفُ من `lib/permission-rows` — لا يُعاد
 * صوغُ جملةٍ هنا، ولا يُصنَّف إذنٌ مرّةً ثانية.
 */

import { useCallback, useEffect, useState } from "react";

import { alertsAvailable, permissionStatus, type PermissionStatus } from "@/lib/offer-alert";
import { ROWS, type Row } from "@/lib/permission-rows";

export function PermissionNotice() {
  const [state, setState] = useState<PermissionStatus | null>(null);

  const read = useCallback(async () => {
    setState(await permissionStatus());
  }, []);

  useEffect(() => {
    void read();
    // **وتُقرأ ثانيةً عند كلِّ عودةٍ إلى الشاشة** — هي نفسُها آليةُ شاشة
    // الأذونات: العودةُ من إعدادات النظام لا تمرّ بنا، **وتحذيرٌ باقٍ بعد
    // منح الإذن يُقرأ عطباً في التطبيق**.
    const onShow = () => {
      if (!document.hidden) void read();
    };
    document.addEventListener("visibilitychange", onShow);
    return () => document.removeEventListener("visibilitychange", onShow);
  }, [read]);

  // **وصمتٌ في المتصفّح لا ادّعاء**: لا أذونَ تُقرأ هناك، **ولا يُرسم تحذيرٌ
  // عن حالٍ لم تُقس** — وهو حدُّ `alertsAvailable` نفسُه في بقية الأسطح.
  if (!alertsAvailable() || state === null) return null;

  const missing = ROWS.filter((row) => !row.read(state));
  if (missing.length === 0) return null;

  const blocking = missing.filter((row) => row.severity === "blocking");
  const advisory = missing.filter((row) => row.severity === "advisory");

  return (
    <div className="mb-10 space-y-8">
      {blocking.length > 0 ? (
        <section className="rounded-14 border border-danger bg-surface-2 px-14 py-12" role="alert">
          <p className="text-12.5 font-semibold text-danger">لا تصلك طلبات الآن</p>
          <ul className="mt-6 space-y-8">
            {blocking.map((row) => (
              <NoticeRow key={row.key} row={row} />
            ))}
          </ul>
        </section>
      ) : null}

      {advisory.length > 0 ? (
        <section className="rounded-14 border border-line bg-surface-2 px-14 py-12">
          <p className="text-12.5 font-semibold text-warn">ينقص ما يقوّي وصولَ الطلب</p>
          <ul className="mt-6 space-y-8">
            {advisory.map((row) => (
              <NoticeRow key={row.key} row={row} />
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

/** سطرٌ واحد — **يسمّي الإذنَ وأثرَ غيابه**، لا «فعّل الأذونات». */
function NoticeRow({ row }: { row: Row }) {
  return (
    <li>
      <p className="text-11.5 font-semibold text-ink">{row.label}</p>
      <p className="mt-2 text-11.5 leading-6 text-muted">{row.why}</p>
      {row.open ? (
        <button
          type="button"
          onClick={() => void row.open?.()}
          className="pressable mt-4 text-11.5 font-semibold text-accent"
        >
          افتح الإعداد
        </button>
      ) : null}
    </li>
  );
}
