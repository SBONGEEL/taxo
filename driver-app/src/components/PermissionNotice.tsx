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
import { Icon } from "@/taxo2";
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

  // **بلغة TAXO 2.0** (§٦٢/١ و/٦): كان بطاقتين بطرازٍ قديمٍ فوق C04 — صار `t2-callout` (`taxo2/primitives.css`) كبلاغ الراكب
  return (
    <div className="t2-callouts">
      {blocking.length > 0 ? (
        <section className="t2-callout danger" role="alert">
          <Icon name="error" fill />
          <div className="t2-callout-main">
            <p className="t2-callout-title">لا تصلك طلبات الآن</p>
            <ul className="t2-callout-list">
              {blocking.map((row) => (
                <NoticeRow key={row.key} row={row} />
              ))}
            </ul>
          </div>
        </section>
      ) : null}

      {advisory.length > 0 ? (
        <section className="t2-callout warn">
          <Icon name="info" fill />
          <div className="t2-callout-main">
            <p className="t2-callout-title">ينقص ما يقوّي وصولَ الطلب</p>
            <ul className="t2-callout-list">
              {advisory.map((row) => (
                <NoticeRow key={row.key} row={row} />
              ))}
            </ul>
          </div>
        </section>
      ) : null}
    </div>
  );
}

/** سطرٌ واحد — **يسمّي الإذنَ وأثرَ غيابه**، لا «فعّل الأذونات». */
function NoticeRow({ row }: { row: Row }) {
  return (
    <li>
      <p className="t2-callout-item">{row.label}</p>
      <p className="t2-callout-body">{row.why}</p>
      {row.open ? (
        <button type="button" onClick={() => void row.open?.()} className="t2-callout-open">
          افتح الإعداد
        </button>
      ) : null}
    </li>
  );
}
