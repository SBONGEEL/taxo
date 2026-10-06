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
 *
 * **بلغة TAXO 2.0** «C27» (`design/t2-new/captain/C27*.dc.html`): المانعُ في الأعلى **بلاغُ الرئيسية نفسُه** (`t2-callout`،
 * `PermissionNotice`)، **وأيقوناتُ الأذونات أيقوناتُ جولة أوّل فتح** (`PermissionsIntro`) في صفِّ «C12» بنبرة حاله ووسمه،
 * **وزرُّ المنح زرُّ «ارفع الوثيقة»**. والنصوصُ والتصنيفُ من `lib/permission-rows` كما هي.
 */

import { useCallback, useEffect, useState } from "react";

import {
  alertsAvailable,
  permissionStatus,
  type PermissionStatus,
} from "@/lib/offer-alert";
import { ROWS } from "@/lib/permission-rows";
import { useGoBack } from "@/lib/back";
import { Icon } from "@/taxo2";

import "@/screens/t2/account.css";

/** أيقونةُ كلِّ إذن — **أيقوناتُ الجولة** (`PermissionsIntro::STEP_ICON`) وما ليس فيها بمعناه، بالمفتاح لا بالترتيب. */
const ROW_ICON: Record<string, string> = {
  location: "location_on",
  notifications: "notifications",
  offerChannel: "notifications_active",
  backgroundLocation: "my_location",
  batteryUnrestricted: "battery_charging_full",
  overlay: "layers",
  fullScreenIntent: "open_in_full",
};

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
    <div className="t2 t2-ax t2-perm">
      <div className="t2-ax-scroll">
        <div className="t2-head">
          <button type="button" className="t2-back" aria-label="رجوع" onClick={() => goBack()}>
            <Icon name="arrow_forward" />
          </button>
          <h1 className="t2-title">أذونات الجهاز</h1>
        </div>

        {!alertsAvailable() ? (
          <section className="t2-callout">
            <Icon name="info" fill className="muted" />
            <p className="t2-perm-msg">
              هذه الشاشة تقرأ أذونات الهاتف، وأنت تفتح التطبيق من المتصفّح — فلا
              شيء هنا يُقرأ. افتحها من تطبيق الكبتن المثبَّت.
            </p>
          </section>
        ) : null}

        {alertsAvailable() && checked && state === null ? (
          <section className="t2-callout warn">
            <Icon name="info" fill />
            <p className="t2-perm-msg warn">
              تعذّرت قراءة حال الأذونات من النظام. لا يعني ذلك أنّها ممنوحة ولا
              أنّها ممنوعة — أعد فتح الشاشة، وإن تكرّر فافتح إعدادات التطبيق.
            </p>
          </section>
        ) : null}

        {state ? (
          <>
            {/* **المانعُ في الأعلى ومنفصلٌ** — ورتبةٌ واحدةٌ للكلِّ تجعل الحرجَ
                يُقرأ اقتراحاً */}
            {missing.length > 0 ? (
              <section className="t2-callout danger" role="alert">
                <Icon name="error" fill />
                <div className="t2-callout-main">
                  <h2 className="t2-callout-title">لا تصلك طلبات الآن</h2>
                  <p className="t2-callout-body">
                    {missing.map((row) => row.label).join(" · ")} — امنح ما ينقص
                    أدناه ثم عد.
                  </p>
                </div>
              </section>
            ) : (
              <section className="t2-callout ok">
                <Icon name="check_circle" fill />
                <div className="t2-callout-main">
                  <h2 className="t2-callout-title t2-perm-ok-title">كل ما يلزم ممنوح</h2>
                  <p className="t2-callout-body">
                    لا شيء يمنع وصول الطلبات إليك من جهة الأذونات.
                  </p>
                </div>
              </section>
            )}

            <div className="t2-perm-list">
              {ROWS.map((row) => {
                const on = row.read(state);
                const tone = on ? "ok" : row.severity === "blocking" ? "danger" : "warn";
                return (
                  <div
                    key={row.key}
                    className={!on && row.severity === "blocking" ? "t2-perm-row blocking" : "t2-perm-row"}
                  >
                    <div className="t2-perm-top">
                      <span className={`t2-ax-tile ${tone}`} aria-hidden="true">
                        <Icon name={ROW_ICON[row.key] ?? "verified_user"} />
                      </span>
                      <span className="t2-perm-label">{row.label}</span>
                      <span className={`t2-chip ${tone}`}>
                        {on
                          ? "ممنوح"
                          : row.severity === "blocking"
                            ? "مطلوب"
                            : "مستحسن"}
                      </span>
                    </div>
                    <p className="t2-perm-why">{row.why}</p>
                    {!on && row.open ? (
                      <button
                        type="button"
                        onClick={() => void row.open?.()}
                        className="t2-perm-open"
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
              <p className="t2-ax-fine t2-perm-maker">
                <Icon name="info" />
                <span>
                  وإعدادات المصنّع لا يقرؤها التطبيق ولا يعرف حالها: «التشغيل
                  التلقائيّ» و«توفير الطاقة الخاص» في هواتف سامسونغ وشاومي وهواوي
                  تُوقف الخدمة بلا أن يظهر لنا شيء. فإن انقطع عملك ولا شيء هنا أحمر،
                  فابحث عنها في إعدادات هاتفك.
                </span>
              </p>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}
