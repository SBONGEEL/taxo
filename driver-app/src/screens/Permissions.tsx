/** **شاشةُ أذوناتٍ حالٌ لا معالج** (قرارُ المالك 2026-08-30).
 *
 * وثلاثةُ ما حسمه، مبنيّةً كما قالها:
 *
 * 1. **حالُ المنصّة حيّة**: تُقرأ من النظام في كلِّ فتحةٍ ولا تُحفظ إجابةٌ
 *    قديمة — **لأن المستخدمَ يسحب الإذنَ من إعدادات الهاتف ولا يمرّ بنا**،
 *    فذاكرةٌ عن إذنٍ مُنح أمسِ تكذب اليوم. **ومعالجُ خطواتٍ يُعرض مرّةً عند
 *    التسجيل يجعل من سحب إذناً بعد شهرٍ بلا شاشةٍ تخبره.**
 * 2. **والطلبُ في سياقه**: كلُّ سطرٍ يقول ما ينكسر بغيابه بعينه، لا «التطبيق
 *    يحتاج أذونات».
 * 3. **ومانعٌ يفترق عن ناصح**: ما بلا يقف العملُ يُعرض أحمرَ في الأعلى، وما
 *    يُضعفه دونه يُعرض تنبيهاً — **ورتبةٌ واحدةٌ للكلِّ تجعل الحرجَ يُقرأ
 *    اقتراحاً**.
 *
 * **ولا يُدَّعى أنّ إعدادات المصنّع ضُبطت**: لا API يقرأ «التشغيل التلقائيّ»
 * ولا قوائمَ سامسونغ البيضاء — والجسرُ يعلن ذلك (`manufacturerSettingsKnown`
 * دائماً `false`)، **والادّعاءُ أسوأُ من السكوت** لأنه يوقف صاحبَه عن البحث
 * حين ينقطع عمله.
 */

import { useCallback, useEffect, useState } from "react";

import {
  alertsAvailable,
  permissionStatus,
  type PermissionStatus,
} from "@/lib/offer-alert";
import { ROWS } from "@/lib/permission-rows";
import { useGoBack } from "@/lib/back";


export function PermissionsScreen() {
  const goBack = useGoBack("/account");
  const [state, setState] = useState<PermissionStatus | null>(null);
  const [checked, setChecked] = useState(false);

  const read = useCallback(async () => {
    setState(await permissionStatus());
    setChecked(true);
  }, []);

  useEffect(() => {
    void read();
    // **تُقرأ ثانيةً عند العودة من إعدادات النظام**: المستخدم يمنح الإذن
    // هناك ولا يمرّ بنا — وشاشةٌ تعرض ما قرأته قبل خروجه تكذب عليه.
    const onShow = () => {
      if (!document.hidden) void read();
    };
    document.addEventListener("visibilitychange", onShow);
    return () => document.removeEventListener("visibilitychange", onShow);
  }, [read]);

  const missing = state
    ? ROWS.filter((row) => !row.read(state) && row.severity === "blocking")
    : [];

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
        <h1 className="text-20 font-bold text-ink">أذونات الجهاز</h1>
      </div>

      {!alertsAvailable() ? (
        <p className="rounded-16 border border-line bg-surface p-16 text-12.5 leading-note text-muted">
          هذه الشاشة تقرأ أذونات الهاتف، وأنت تفتح التطبيق من المتصفّح — فلا
          شيء هنا يُقرأ. افتحها من تطبيق الكبتن المثبَّت.
        </p>
      ) : null}

      {alertsAvailable() && checked && state === null ? (
        <p className="rounded-16 border border-warn bg-surface p-16 text-12.5 leading-note text-warn">
          تعذّرت قراءة حال الأذونات من النظام. لا يعني ذلك أنّها ممنوحة ولا
          أنّها ممنوعة — أعد فتح الشاشة، وإن تكرّر فافتح إعدادات التطبيق.
        </p>
      ) : null}

      {state ? (
        <>
          {/* **المانعُ في الأعلى ومنفصلٌ** — ورتبةٌ واحدةٌ للكلِّ تجعل الحرجَ
              يُقرأ اقتراحاً */}
          {missing.length > 0 ? (
            <section
              className="mb-14 rounded-20 border border-danger bg-surface p-18"
              role="alert"
            >
              <h2 className="text-14 font-bold text-danger">
                لا تصلك طلبات الآن
              </h2>
              <p className="mt-6 text-11.5 leading-note text-ink">
                {missing.map((row) => row.label).join(" · ")} — امنح ما ينقص
                أدناه ثم عد.
              </p>
            </section>
          ) : (
            <section className="mb-14 rounded-20 border border-line bg-surface p-18">
              <h2 className="text-14 font-bold text-ok">كل ما يلزم ممنوح</h2>
              <p className="mt-6 text-11.5 leading-note text-muted">
                لا شيء يمنع وصول الطلبات إليك من جهة الأذونات.
              </p>
            </section>
          )}

          <div className="rounded-20 border border-line bg-surface p-4">
            {ROWS.map((row) => {
              const on = row.read(state);
              return (
                <div
                  key={row.key}
                  className="border-b border-line p-14 last:border-0"
                >
                  <div className="flex items-baseline justify-between gap-10">
                    <span className="text-13.5 font-bold text-ink">
                      {row.label}
                    </span>
                    <span
                      className={
                        on
                          ? "text-11.5 font-bold text-ok"
                          : row.severity === "blocking"
                            ? "text-11.5 font-bold text-danger"
                            : "text-11.5 font-bold text-warn"
                      }
                    >
                      {on
                        ? "ممنوح"
                        : row.severity === "blocking"
                          ? "مطلوب"
                          : "مستحسن"}
                    </span>
                  </div>
                  <p className="mt-4 text-11 leading-note text-muted">
                    {row.why}
                  </p>
                  {!on && row.open ? (
                    <button
                      type="button"
                      onClick={() => void row.open?.()}
                      className="pressable mt-8 rounded-12 border border-line px-12 py-8 text-11.5 font-bold text-ink"
                    >
                      افتح موضع المنح
                    </button>
                  ) : null}
                </div>
              );
            })}
          </div>

          {/* **ما لا نعرفه يُقال «لا نعرف»** — ولا يُدَّعى ضبطُه.
              **والسطرُ مشروطٌ بالحقل لا مكتوبٌ دائماً**: يومَ يفتح أندرويد
              باباً يقرأ إعداداتِ المصنّع يصير الحقلُ `true` **فيختفي السطرُ
              من نفسه** — ونصٌّ ثابتٌ كان سيبقى يعتذر عن شيءٍ صار معروفاً. */}
          {!state.manufacturerSettingsKnown ? (
          <p className="mt-14 rounded-16 border border-line bg-surface-2 p-14 text-11 leading-note text-muted">
            وإعدادات المصنّع لا يقرؤها التطبيق ولا يعرف حالها: «التشغيل
            التلقائيّ» و«توفير الطاقة الخاص» في هواتف سامسونغ وشاومي وهواوي
            تُوقف الخدمة بلا أن يظهر لنا شيء. فإن انقطع عملك ولا شيء هنا أحمر،
            فابحث عنها في إعدادات هاتفك.
          </p>
          ) : null}
        </>
      ) : null}
    </div>
  );
}
