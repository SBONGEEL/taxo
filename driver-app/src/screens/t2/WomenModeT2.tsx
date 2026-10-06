/** الخدمةُ النسائيةُ عند الكبتنة — TAXO 2.0 «CW1 الوضع النسائي» (صفحتُها) وصفُّها في «الإعدادات» (C15)، **في الداكن المرسوم
 *  والفاتح والنسائيّ** (§٦٢-ج/٢٣).
 *
 * **بسلوك اليوم حرفاً — الوضعُ أ** (`design/APPROVALS-WOMEN-MODES.md` §١، §٦٢-ج/٩): التفضيلُ **ثلاثيٌّ لكلِّ كبتن** (الجميع · النساءُ
 * فقط · الرجالُ فقط) **ويُطابَق في الاتجاهين** (`dispatch._eligible_levels`)، **والحفظُ بلمسة الاختيار** كما في «الإعدادات» —
 * `useCaptainSettings().savePreference` نفسُه (`PATCH /drivers/me`)، **والمعروضُ من الملفّ لا من حالٍ محلّية**. فلا شيءَ هنا يغيّر مطابقة.
 *
 * **ومن ترى CW1**: الكبتنةُ (`gender = female` — ما تُتاح به السِمةُ الوردية، `lib/brand.tsx`) حيث الخدمةُ مشتعلةٌ في سوقها، **وصفُّها
 * في «الإعدادات» يفتحها**. **وغيرُها يرى التفضيلَ الثلاثيَّ في «الإعدادات» كما كان** (`SettingsT2`) — الوضعُ أ يعرضه لكلِّ كبتن.
 * **و«الشروط» حالٌ تُقرأ من الملفّ ولا تُكتب**: ختمُ المشرف لجنسها من هويتها (`gender_verified_at`) — **وبغيره لا تصلها طلباتُ من
 * طلبت كبتنة** — واعتمادُ حسابها (`driver.status`)، وهو شرطُ كلِّ طلب.
 *
 * **وما رسمته اللوحةُ ولم يُبنَ — بعلّته**:
 * - **«الكل، مع أولوية للراكبات»**: الوضعُ ب (§٦٢-ج/٩) بندٌ مستقلّ — ولا يتغيّر منطقُ مطابقةٍ هنا. **و«راكبات فقط» وحدَها خياراً
 *   آخر**: الخياراتُ اليومَ ثلاثة («الجميع» و«الرجال فقط» معها) — فرُسمت الثلاثةُ بطاقاتٍ كما رُسمت اثنتان.
 * - **زرُّ «تفعيل الوضع النسائي»**: الاختيارُ يُحفظ بلمسته كما في «الإعدادات» اليوم — **وزرٌّ بعده يترك اختياراً معروضاً لم يُحفظ**
 *   لمن غادرت قبل لمسه.
 * - **«حين يكون الوضع النسائي مفعّلاً، لا تصلك إلا طلبات الراكبات من الخدمة النسائية»**: في الوضع أ تصلها الراكباتُ كلُّهنّ — من
 *   طلبت كبتنةً ومن قبلت «أي كبتن» — فالسطرُ يقول ما يقع: «لا تصلك إلا طلبات الراكبات».
 * - **«وثائقك ومركبتك سارية»** ⇐ «حسابك ووثائقك معتمدة»: التوزيعُ يقرأ اعتمادَ الحساب (`status = approved`) لا تاريخَ سريانٍ لكلِّ وثيقة.
 * - **صفُّ C15 «الخدمة النسائية — للكبتنات، استقبال الراكبات فقط» مفتاحاً**: التفضيلُ ثلاثيّ — فالصفُّ يقول الاختيارَ الحاليَّ وسهمُه إلى CW1.
 */

import { Navigate, useNavigate } from "react-router-dom";

import type { GenderPreference } from "@/api/types";
import { ErrorNote, SuccessNote } from "@/components/ui/Feedback";
import { useBrand } from "@/lib/brand";
import { PREFERENCE_LABEL } from "@/lib/rideFormat";
import { useSession } from "@/lib/session";
import { useCaptainSettings } from "@/screens/Settings";
import { Icon } from "@/taxo2";

import "@/taxo2";
import "./t2.css";
import "./women.css";

/** **الخياراتُ الثلاثةُ القائمة** بترتيب اللوحة («راكبات فقط» أوّلاً) — **وكلُّ سطرٍ يصف المطابقةَ في الاتجاهين كما تقع** (الوضعُ أ). */
const OPTIONS: { value: GenderPreference; title: string; sub: string }[] = [
  { value: "female", title: "الراكبات فقط", sub: "لا تصلك إلا طلبات الراكبات." },
  { value: "any", title: "الجميع", sub: "يصلك كل راكبٍ يقبل تفضيلُه كبتنة." },
  { value: "male", title: "الرجال فقط", sub: "لا يصلك إلا الركّاب الرجال." },
];

/** **صفُّ «الخدمة النسائية» في «الإعدادات»** (C15) — للكبتنة وحدَها، يقول اختيارَها الآن وسهمُه إلى CW1. */
export function WomenModeRowT2({ preference }: { preference: GenderPreference }) {
  const navigate = useNavigate();
  return (
    <button type="button" className="t2-srow" onClick={() => navigate("/account/settings/women")}>
      <span className="t2-icon t2-srow-icon pink" aria-hidden="true">
        woman
      </span>
      <span className="t2-srow-main">
        <span className="t2-srow-title">الخدمة النسائية</span>
        <span className="t2-srow-hint">تستقبلين: {PREFERENCE_LABEL[preference]}</span>
      </span>
      <span className="t2-icon t2-wrow-go" aria-hidden="true">
        chevron_left
      </span>
    </button>
  );
}

/** شرطٌ بحاله — **مستوفىً بعلامة النجاح، أو منتظَرٌ بعلامة التنبيه وسطرٍ يقول ما ينتظره**. */
function Condition({ ok, title, wait }: { ok: boolean; title: string; wait: string }) {
  return (
    <div className="t2-wcond">
      <Icon name={ok ? "check_circle" : "hourglass_top"} className={ok ? "t2-wcond-icon ok" : "t2-wcond-icon wait"} />
      <span className="t2-wcond-main">
        <span className="t2-wcond-title">{title}</span>
        {ok ? null : <span className="t2-wcond-hint">{wait}</span>}
      </span>
    </div>
  );
}

/** **CW1 — صفحةُ الوضع النسائيّ**: ما هو، وشروطُه بحالها، **واختيارُ ما يصلها بلمسته**. */
export function WomenModeT2Screen() {
  const { goBack, profile, womenService, preference, savingPreference, savePreference, done, error } = useCaptainSettings();
  const { available } = useBrand();
  const { user } = useSession();

  // **لا يُرى منها شيءٌ حيث الخدمةُ مطفأة، ولا لغير الكبتنة** — والتفضيلُ الثلاثيُّ في «الإعدادات» كما كان
  if (!womenService || !available) return <Navigate to="/account/settings" replace />;

  const stamped = user?.gender === "female" && user.gender_verified_at !== null;

  return (
    <div className="t2 t2-settings t2-wmode scr">
      <div className="t2-head">
        <button type="button" className="t2-back" aria-label="رجوع" onClick={() => goBack()}>
          <Icon name="arrow_forward" />
        </button>
        <h1 className="t2-title">الخدمة النسائية</h1>
      </div>

      <section className="t2-whero">
        <span className="t2-whero-icon">
          <Icon name="woman" fill />
        </span>
        <h2 className="t2-whero-title">استقبلي راكبات فقط.</h2>
        <p className="t2-whero-body">حين تختارين «الراكبات فقط» لا تصلك إلا طلبات الراكبات.</p>
      </section>

      <div className="t2-wlabel">الشروط</div>
      <div className="t2-wconds">
        <Condition
          ok={stamped}
          title="هويتك موثّقة"
          wait="يثبّته المشرف من هويتك — وقبله لا تصلك طلبات من طلبت كبتنة."
        />
        {profile ? (
          <Condition
            ok={profile.driver.status === "approved"}
            title="حسابك ووثائقك معتمدة"
            wait="تصلك الطلبات بعد اعتماد حسابك."
          />
        ) : null}
      </div>

      <div className="t2-wlabel">ما الطلبات التي تصلك؟</div>
      {/* **الحفظُ بلمسة الاختيار** (`savePreference`) — ولا حفظان معاً: الخياراتُ معطّلةٌ ما دام الحفظُ جارياً */}
      <div className="t2-wopts" role="radiogroup" aria-label="ما الطلبات التي تصلك؟">
        {OPTIONS.map((option) => {
          const on = preference === option.value;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={on}
              disabled={savingPreference}
              className={on ? "t2-wopt on" : "t2-wopt"}
              onClick={() => {
                if (!on) void savePreference(option.value);
              }}
            >
              <Icon name={on ? "radio_button_checked" : "radio_button_unchecked"} className="t2-wopt-radio" />
              <span className="t2-wopt-main">
                <span className="t2-wopt-title">{option.title}</span>
                <span className="t2-wopt-sub">{option.sub}</span>
              </span>
            </button>
          );
        })}
      </div>

      {/* **شرحُ المطابقة** — يجيب «لماذا قلّت طلباتي؟»، والشرطُ ثنائيُّ الاتجاه في الخلفية (نصُّ «الإعدادات» حرفاً) */}
      <p className="t2-explain">
        <span className="t2-explain-title">كيف تعمل المطابقة</span>
        تصلك الرحلة فقط إذا قبِل تفضيلُ الراكب جنسَك، وقبِل تفضيلُك جنسَه — الاتجاهان معاً. فراكبٌ اختار «الجميع» لن تصله
        رحلتُك إن كان تفضيلُك «النساء فقط».
      </p>

      <div className="t2-settings-notes">
        <ErrorNote message={error} />
        <SuccessNote message={done} />
      </div>
    </div>
  );
}
