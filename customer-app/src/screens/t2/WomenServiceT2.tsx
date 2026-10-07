/** الخدمةُ النسائيةُ عند الراكبة — TAXO 2.0 «R15» (بطاقتُها في «حسابي») و«RW1» (صفحتُها)، **في المظهرين والنسائيّ** (§٦٢-ج/٢٣).
 *
 * **بقول المالك**: «كبتنةٌ فقط، والراكبةُ نفسُها تختار «أي كبتن»… ولا يبدّلها التطبيقُ بنفسه». **فالتفعيلُ هو التفضيلُ الافتراضيُّ
 * القائمُ نفسُه** — `ride_gender_preference = female` بـ`PATCH /auth/me`، كما يكتبه «من يقودني افتراضياً» في «بياناتي» (R22) — **لا
 * حقلٌ جديدٌ ولا بيانٌ جديد**: يُنسخ إلى كلِّ طلبٍ لا تختار فيه غيرَه، **وتغيّره لرحلةٍ واحدةٍ من ورقة الطلب**. والإيقافُ يكتب «أي كبتن»
 * بلمستها هي. **ولا شيءَ هنا يكتب إلا بلمسة** — ولا يُبدَّل التفضيلُ في غيابها.
 *
 * **ومن تُعرض عليه — قاعدةُ `lib/women.ts` بعينها**: حيث الخدمةُ مطفأةٌ في السوق لا يظهر شيءٌ منها (لا بطاقةَ ولا صفحة — ومن بلغها
 * برابطٍ يعود إلى «حسابي»). **ومن أعلنت أنها أنثى** ترى حالَ تفضيلها وتبدّله. **ومن أعلن أنه رجل** لا تُعرض عليه البطاقة (الخدمةُ لمن
 * أُنشئت لها). **ومن لم يُعلن جنسَه تُسأل حين تضغط الخدمة** (جوابُ المالك ٢٠٢٦-١٠-٠٧، §٦٤-ج/٤-٢): ورقةٌ بسؤال التسجيل نفسِه
 * (`DeclareGenderSheetT2`) **مرّةً** — تكتب `gender` بـ`PATCH /auth/me` ثمّ تمضي إلى الخدمة إن كانت أنثى. **و«بياناتي» تعرضه ولا
 * تكتبه** (قرارُ المالك ٢٠٢٦-٠٨-١٥، `Profile.tsx`)، **ولا زرَّ يبدّل جنساً أُعلن**: الخلفيةُ تردّ التغييرَ ٤٢٢، وتغييرُه عبر الدعم.
 *
 * **وما رسمته اللوحةُ ولم يُبنَ — بعلّته**:
 * - **R15 · «نطابقك مع كبتنة كلما توفرت»**: «كلما توفرت» تُقرأ وعداً بكبتنٍ حين لا تتوفّر كبتنة — **وهو ما نفاه قولُ المالك**. فالسطرُ
 *   يقول ما يقع: «نطابقك مع كبتنة فقط» (وما بعد «فقط» في RW1). **والمفتاحُ حالٌ لا زرّ**: البطاقةُ كلُّها تفتح RW1، وهناك يُفعَّل
 *   ويُوقف — مفتاحٌ يكتب تفضيلاً بلمسةٍ عابرةٍ في قائمة الحساب هو ما نزعه قرارُ المالك من «بياناتي» في الجنس.
 * - **RW1 · «تُشارَك رحلتك تلقائياً مع جهة تثقين بها»**: رابطُ التتبّع الحيّ بندٌ ينتظر إذنَ المالك (§٦٢-ج/١٩، بيانات) — **ولا يُوعَد
 *   بما لم يُبنَ**.
 * - **RW1 · «نتحقق من هويتك مرة واحدة»** — صورةُ الهوية والصورةُ الشخصية و«أعيدي التصوير» و«إرسال للتحقق» و«تُراجَع يدوياً، ونرسل لك
 *   إشعاراً بالنتيجة»: **بياناتٌ شخصيةٌ جديدة** تنتظر إذنَ المالك (§٦٢-د/١). **والزرُّ مكانَها التفعيلُ نفسُه** (التفضيلُ القائم) بالبرقوق كما رُسم.
 */

import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { updateMe } from "@/api/endpoints";
import type { GenderPreference, User } from "@/api/types";
import { useGoBack } from "@/lib/back";
import { useSession } from "@/lib/session";
import { useWomenService } from "@/lib/women";
import { AuthChoice, Icon, Switch } from "@/taxo2";

import { DrawerT2 } from "./DrawerT2";
import { NoteT2, SubHeadT2 } from "./KitT2";
import "@/taxo2";
import "./t2.css";
import "./women.css";

type Gender = NonNullable<User["gender"]>;

/** **إعلانُ الجنس حين تُضغط الخدمةُ النسائية** (§٦٤-ج/٤-٢) — لمن لم تُعلنه في التسجيل (`user.gender === null`).
 *
 *  **السؤالُ نفسُه الذي في التسجيل** (`Register.tsx`): «نخاطبك بصيغة» بخياريه «راكب» و«راكبة» (`AuthChoice` — البرقوقُ لـ«راكبة»)،
 *  **ولا يُكتب شيءٌ قبل «تأكيد»**: إقرارٌ لا يُبدَّل من الهاتف لا تكتبه لمسةٌ عابرةٌ على خيار. ثمّ `PATCH /auth/me {gender}` وتُحدَّث
 *  الجلسة — **فأنثى ⇒ `onFemale`** (المستدعي يمضي إلى الخدمة)، **ورجلٌ ⇒ «الخدمة النسائية للراكبات»** في الورقة نفسِها ولا شيءَ بعدها.
 *
 *  **ولا يُعرض لمن أعلن** — والخلفيةُ هي الحارس: تغييرُ جنسٍ أُعلن يُردّ ٤٢٢ بنصّه («تغييرُه عبر الدعم») ويُقال تحت الزرّ. */
export function DeclareGenderSheetT2({
  open,
  onOpenChange,
  onFemale,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** أعلنت أنها أنثى — والجلسةُ حُدِّثت قبله، فـ`useWomenService().available` صادقٌ حين يُنادى. */
  onFemale: () => void;
}) {
  const { refreshUser } = useSession();
  const [choice, setChoice] = useState<Gender | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [declaredMale, setDeclaredMale] = useState(false);

  function close(next: boolean) {
    if (next) return onOpenChange(true);
    onOpenChange(false);
    setChoice(null);
    setError(null);
    setDeclaredMale(false);
  }

  async function confirm() {
    if (!choice) return;
    setSaving(true);
    setError(null);
    try {
      await updateMe({ gender: choice });
      await refreshUser();
      if (choice === "female") {
        close(false);
        onFemale();
      } else {
        setDeclaredMale(true);
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الحفظ");
      // **أُعلن من جهازٍ آخر؟** — الجلسةُ تُقرأ من جديد فلا يبقى السؤالُ معروضاً على ما أُجيب
      await refreshUser().catch(() => undefined);
    } finally {
      setSaving(false);
    }
  }

  return (
    <DrawerT2 open={open} onOpenChange={close} title="الخدمة النسائية">
      {declaredMale ? (
        <>
          <p className="t2-drawer-text">الخدمة النسائية للراكبات.</p>
          <div className="t2-drawer-actions">
            <button type="button" className="t2-button t2-quiet" onClick={() => close(false)}>
              حسناً
            </button>
          </div>
        </>
      ) : (
        <>
          <p className="t2-drawer-text">تُعرض الخدمة على من أعلنت أنها أنثى — ولم يُعلَن جنسٌ في حسابك.</p>
          <p className="t2-wdecl-ask">نخاطبك بصيغة</p>
          <AuthChoice
            label="نخاطبك بصيغة"
            value={choice}
            options={[
              { value: "male", label: "راكب" },
              { value: "female", label: "راكبة", women: true },
            ]}
            onChange={setChoice}
          />
          <p className="t2-wdecl-fine">
            إقرارٌ ذاتيٌّ بلا وثيقة، ولا يظهر لأحد. <b>يُعلَن مرّةً، وتغييرُه بعدها عبر الدعم.</b>
          </p>
          {error ? <NoteT2 tone="danger">{error}</NoteT2> : null}
          <div className="t2-drawer-actions">
            {/* **البرقوقُ حين اختارت «راكبة»** — زرُّ الخدمة كما في RW1 · RW3؛ وما عداه أساسيُّ الهوية */}
            <button
              type="button"
              className={choice === "female" ? "t2-wbtn" : "t2-button primary"}
              disabled={choice === null || saving}
              aria-busy={saving}
              onClick={() => void confirm()}
            >
              {saving ? "نحفظ…" : "تأكيد"}
            </button>
            <button type="button" className="t2-button t2-quiet" onClick={() => close(false)}>
              ليس الآن
            </button>
          </div>
        </>
      )}
    </DrawerT2>
  );
}

/** **R15 — بطاقةُ الخدمة في «حسابي»** بين الأرقام والصفوف كما رُسمت. **تعكس التفضيلَ الافتراضيَّ ولا تكتبه**: المفتاحُ مشتعلٌ حين
 *  يكون «كبتنة»، ولمستُها تفتح RW1 — **ومن لم تُعلن جنسَها تُسأل أوّلاً** (`DeclareGenderSheetT2`، §٦٤-ج/٤-٢). */
export function WomenServiceCardT2() {
  const navigate = useNavigate();
  const { user } = useSession();
  const women = useWomenService();
  const [asking, setAsking] = useState(false);
  // **مطفأةٌ في السوق ⇒ لا شيء** · **ومن أعلن أنه رجل ⇒ لا بطاقة** (`lib/women.ts`: الخدمةُ تُعرض على من أُنشئت لها) — **والورقةُ
  // في الشجرة نفسِها ما دامت البطاقة**: من أعلن الآن أنه رجلٌ يقرأ «الخدمة النسائية للراكبات» فيها، ثمّ تختفي البطاقةُ تحتها
  if (!women.enabled) return null;
  const on = women.available && women.defaultPreference === "female";
  return (
    <>
      {user?.gender === "male" ? null : (
        <button
          type="button"
          className="t2-wsvc"
          onClick={() => (user?.gender ? navigate("/account/women") : setAsking(true))}
          aria-label={women.available ? `الخدمة النسائية — ${on ? "مفعّلة" : "غير مفعّلة"}` : "الخدمة النسائية"}
        >
          <span className="t2-wsvc-icon">
            <Icon name="woman" />
          </span>
          <span className="t2-wsvc-main">
            <span className="t2-wsvc-title">الخدمة النسائية</span>
            <span className="t2-wsvc-sub">
              {women.available ? "نطابقك مع كبتنة فقط" : "تُعرض على من أعلنت أنها أنثى"}
            </span>
          </span>
          {/* **حالٌ لا زرّ** (`Switch` بلا دور) — ومن لم تُعلن جنسَها لا حالَ لها: سهمٌ إلى الصفحة */}
          {women.available ? <Switch on={on} /> : <Icon name="chevron_left" className="t2-wsvc-go" />}
        </button>
      )}
      <DeclareGenderSheetT2 open={asking} onOpenChange={setAsking} onFemale={() => navigate("/account/women")} />
    </>
  );
}

/** **RW1 — صفحةُ الخدمة**: ما هي، وما يصدق فيها اليوم، **والتفعيلُ بلمستها** (أو الإيقاف). */
export function WomenServiceT2Screen() {
  const goBack = useGoBack("/account");
  const { user, refreshUser } = useSession();
  const women = useWomenService();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // **ورقةُ الإعلان** (§٦٤-ج/٤-٢) — لمن بلغت الصفحةَ برابطٍ ولم تُعلن جنسَها؛ والبطاقةُ في «حسابي» تسألها قبل أن تفتحها
  const [asking, setAsking] = useState(false);

  if (!user) return null;
  // **حيث الخدمةُ مطفأةٌ لا يظهر شيءٌ منها** — ولا صفحةٌ تُبلغ برابط
  if (!women.enabled) return <Navigate to="/account" replace />;

  const on = women.available && women.defaultPreference === "female";

  /** **البابُ نفسُه الذي يكتب به «من يقودني افتراضياً»** (`Profile.tsx`) — والمعروضُ بعده من الجلسة لا من حالٍ محلّية. */
  async function save(next: GenderPreference) {
    setSaving(true);
    setError(null);
    try {
      await updateMe({ ride_gender_preference: next });
      await refreshUser();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر حفظ التفضيل");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="t2 t2-page t2-account t2-wsp pb-nav">
      <SubHeadT2 title="الخدمة النسائية" onBack={goBack} />

      <section className="t2-whero">
        <span className="t2-whero-stripe" aria-hidden="true" />
        <span className="t2-whero-icon">
          <Icon name="woman" fill />
        </span>
        <h2 className="t2-whero-title">رحلات بين نساء فقط.</h2>
        <p className="t2-whero-body">كبتنة لراكبة، في كل رحلة تطلبينها من هذه الخدمة.</p>
      </section>

      {/* **ما يصدق اليوم وحدَه**: الكبتنةُ مختومةُ الجنس من هويتها بيد المشرف ووثائقُها معتمدة (`dispatch._eligible_levels`)، و«لا كبتنة»
          تُعرض عليها خياراتُها (RW3) ولا يُسنَد كبتنٌ في غيابها */}
      <ul className="t2-wpoints">
        <li>
          <Icon name="verified_user" fill />
          كل الكبتنات موثّقات الهوية والوثائق.
        </li>
        <li>
          <Icon name="front_hand" fill />
          إن لم تتوفر كبتنة نخبرك أولاً، ولا نرسل كبتناً دون موافقتك.
        </li>
      </ul>

      {women.available ? (
        <>
          {on ? (
            <p className="t2-wstate">
              <Icon name="check_circle" fill />
              الخدمة مفعّلة في حسابك
            </p>
          ) : null}
          {on ? (
            <button
              type="button"
              className="t2-button secondary"
              disabled={saving}
              aria-busy={saving}
              onClick={() => void save("any")}
            >
              {saving ? "نحفظ…" : "إيقاف الخدمة — أقبل أي كبتن"}
            </button>
          ) : (
            <button type="button" className="t2-wbtn" disabled={saving} aria-busy={saving} onClick={() => void save("female")}>
              {saving ? "نحفظ…" : "تفعيل الخدمة النسائية"}
            </button>
          )}
          <p className="t2-wfine">تسري على كل طلبٍ لا تختارين فيه غيرها، ولكِ تغييرها لرحلةٍ واحدة من شاشة الطلب.</p>
        </>
      ) : user.gender === "male" ? (
        <NoteT2 tone="plain">الخدمة النسائية للراكبات.</NoteT2>
      ) : (
        // **الإعلانُ من هنا مرّةً** (§٦٤-ج/٤-٢، رأسُ الملفّ) — كان «راسلي الدعم» يومَ لم يكن له باب؛ **والدعمُ لتغييره بعدها**
        <div className="t2-callout">
          <Icon name="person" />
          <div className="t2-callout-main">
            <p className="t2-callout-title">لم يُعلَن جنسٌ في حسابك</p>
            <p className="t2-callout-body">
              تُعرض الخدمة على من أعلنت أنها أنثى. يُعلَن مرّةً، وتغييرُه بعدها عبر الدعم.
            </p>
            <button type="button" className="t2-callout-open" onClick={() => setAsking(true)}>
              إعلان الجنس
            </button>
          </div>
        </div>
      )}
      {/* **أنثى ⇒ تبقى هنا** — الجلسةُ حُدِّثت فتصير الصفحةُ صفحةَ التفعيل نفسَها؛ ورجلٌ ⇒ «للراكبات» في الورقة ثمّ في الصفحة */}
      <DeclareGenderSheetT2 open={asking} onOpenChange={setAsking} onFemale={() => undefined} />

      {error ? <NoteT2 tone="danger">{error}</NoteT2> : null}
    </div>
  );
}
