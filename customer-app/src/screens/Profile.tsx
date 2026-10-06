/** بياناتي — TAXO 2.0 «R22» (`design/t2-new/rider/R22-profile.dc.html` · `R22b-profile-states.dc.html`)، **في المظهرين
 *  والنسائيّ** — لوحةٌ جديدةٌ من عائلة R15: بطاقةُ الهوية والصورة، والجنسُ والتفضيلُ صفّين بلغة C15، و«الخصوصية» ببرقوق R15.
 *
 * **والمنطقُ هو هو حرفاً**: الصورةُ (`PhotoCard`)، وإثباتُ الرقم عبر `POST /auth/me/verify-phone`، والتفضيلُ عبر
 * `PATCH /auth/me`، والخروج. **وما تغيّر طبقةُ العرض** — **وخطوةُ الرمز صارت صفحةَ R04 نفسَها** (`VerifyCode`، منطقُ
 * `PhoneVerification` حرفاً) بدل صندوقٍ داخل البطاقة، **ولا شريطَ تحتها** كالدخول والتسجيل.
 *
 * وحين يكون الرقم غير محقق (أُنشئ الحساب والمفتاح مطفأ للطوارئ — القسم 4)
 * تطالبه الشاشة بالتحقق عند أول فرصة.
 *
 * **ومفتاحُ إشعارات العروض انتقل إلى «الإعدادات»** مع ما يخصّ الجهاز — وإشعاراتُ الرحلة ليست خياراً (القسم 10/11.8).
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import type { GenderPreference } from "@/api/types";
import { startChallenge, updateMe, verifyMyPhone } from "@/api/endpoints";
import { PhotoCard } from "@/components/account/PhotoCard";
import { VerifyCode } from "@/components/t2/VerifyCode";
import { useGoBack } from "@/lib/back";
import { useConfig, usePhoneCountry } from "@/lib/config";
import { useCoverNav } from "@/lib/navCover";
import { useSession } from "@/lib/session";
import { useBrand } from "@/lib/brand";
import { useWomenService } from "@/lib/women";
import { NoteT2, SubHeadT2 } from "@/screens/t2/KitT2";
import { AuthChoice, Icon } from "@/taxo2";

import "@/screens/t2/t2.css";
import "@/screens/t2/account.css";

/** التفضيلُ بخياراته الثلاثة كما كان — **و«إناث» بالبرقوق**: اختيارُ الخدمة النسائية (الهوية، و«راكبة» في R03). */
const PREFERENCES = [
  { value: "female" as const, label: "إناث", women: true },
  { value: "male" as const, label: "ذكور" },
  { value: "any" as const, label: "الجميع" },
];

export function ProfileScreen() {
  const navigate = useNavigate();
  const goBack = useGoBack("/account");
  const { user, signOut, refreshUser } = useSession();
  const { config } = useConfig();
  // **اسمان لا اسمٌ واحد** (البند 6 من قرار المالك 2026-08-13): إتاحةُ السِمة
  // إقرارٌ وحده، وإتاحةُ **ما يَعِد بخدمة** مفتاحٌ قُطريٌّ مع الإقرار. ودمجُهما
  // في `available` واحدٍ يعرض «من يقودني افتراضياً» في سوقٍ لا خدمةَ فيه —
  // وهو بعينه الرفضُ بلا مخرجٍ الذي وقع في 10-ج
  // إتاحةُ السِمة (الإقرارُ وحده) — تحكم **ملاحظةَ الخصوصية** هنا، والمفتاحُ
  // نفسُه صار في «الإعدادات» مع ما يخصّ الجهاز
  const { available: themeAvailable } = useBrand();
  // `available` من الخدمة: مفتاحٌ قُطريٌّ **مع** الإقرار — شرطُ ما يَعِد بمطابقة
  const { enabled, available, defaultPreference } = useWomenService();
  const [savingPreference, setSavingPreference] = useState(false);
  const { dialCode } = usePhoneCountry(user?.country_code);

  const [verifying, setVerifying] = useState(false);
  /** **إثباتُ الرمز جارٍ** — يعطّل زرَّ «تحقق» حتى يصل الجواب (كما في التسجيل)، فلا يُرسل الرمزُ مرّتين */
  const [proving, setProving] = useState(false);
  // يضيّق النوعَ مرةً واحدة — والمشرفُ لا يدخل هذا التطبيق أصلاً
  const phone = user?.phone ?? null;
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  // **خطوةُ الرمز صفحةٌ كاملةٌ بلا شريط** (R04) — كالدخول والتسجيل؛ وتنزع الغطاءَ حين تعود
  useCoverNav(verifying && phone !== null);

  async function provePhone(token: string) {
    setError(null);
    setProving(true);
    try {
      await verifyMyPhone(token);
      await refreshUser();
      setVerifying(false);
      setDone("تم إثبات رقمك.");
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر إثبات الرقم",
      );
    } finally {
      setProving(false);
    }
  }

  if (!user) return null;

  async function savePreference(next: GenderPreference) {
    setSavingPreference(true);
    setError(null);
    try {
      await updateMe({ ride_gender_preference: next });
      await refreshUser();
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر حفظ التفضيل",
      );
    } finally {
      setSavingPreference(false);
    }
  }

  // **`user.phone` صار يقبل `null` نظرياً** (المشرف يدخل باسمِ مستخدم، SPEC §25.9) — ولا مشرفَ في هذا التطبيق بحكم
  // `app_scope`. فالشرطُ يُرضي المُصرِّفَ ويقول الحقيقة: لا تحققَ من رقمٍ لا وجودَ له
  if (verifying && phone) {
    return (
      <VerifyCode
        phone={phone}
        dialCode={dialCode}
        method={config?.auth.verification ?? "none"}
        otpLength={config?.auth.otp_length ?? null}
        requestChallenge={(channel) => startChallenge(phone, user.country_code, channel)}
        onProven={(token) => void provePhone(token)}
        // «تعديل الرقم» والسهمُ كلاهما يعيدان إلى «بياناتي» — كما كان «تعديل الرقم» في الخطوة القديمة
        onBack={() => setVerifying(false)}
        // **بلا عدّاد خطوات**: إثباتٌ واحدٌ لا تسجيلٌ من خطوتين
        step={0}
        total={0}
        outerError={error}
        busy={proving}
      />
    );
  }

  return (
    <div className="t2 t2-page pb-nav">
      <SubHeadT2 title="بياناتي" onBack={goBack} />

      {/* **الصورةُ بجوار بياناته** (قرارُ المالك 2026-08-22): اختياريةٌ،
          بلا مراجعة، ويراها كبتنُ رحلته بعد القبول وحدَه — **والدائرةُ نفسُها صورتُه** */}
      <PhotoCard />

      {!user.phone_verified ? (
        <div className="t2-callout warn">
          <Icon name="error" fill />
          <div className="t2-callout-main">
            <p className="t2-callout-title">رقمك غير مُثبَت</p>
            <p className="t2-callout-body">أثبت ملكية رقمك لتأمين حسابك — يُطلب مرةً واحدة.</p>
            {/* **خطأٌ سابقٌ لا يُرسم تحت الرمز** — صفحةُ الرمز تعرض خطأها هي (`outerError`) */}
            <button
              type="button"
              className="t2-cbtn ink full"
              onClick={() => {
                setError(null);
                setVerifying(true);
              }}
            >
              أثبت رقمي الآن
            </button>
          </div>
        </div>
      ) : null}

      {/* **الجنسُ يُعرض ولا يُبدَّل من هنا** (قرارُ المالك 2026-08-15).
          كان زرّان يكتبان `gender` بضغطة، وثلاثةُ أشياء تتعلّق به لا يجوز
          أن تنقلب بضغطةٍ في شاشةِ بيانات: سمةُ الوردي، وإتاحةُ «سائقة
          تقودني»، ومطابقةُ الطلبات المجنَّسة. وهو **إقرارٌ يُعطى مرةً عند
          التسجيل** — وتغييرُه واقعةٌ نادرةٌ يشهدها الدعم. والعرضُ باقٍ: من لا
          يرى ما أقرّه لا يعرف على أيِّ أساسٍ يُعامَل.
          **والتفضيلُ الافتراضي** يُنسخ إلى كل طلبٍ لا تختار فيه شيئاً، وتغييرُه
          يحكم ما يأتي لا رحلةً جاريةً الآن (المرحلة 10-ج) — **وشرطُه إتاحةُ الخدمة
          لا إتاحةُ السِمة**: هذا يَعِد بمطابقة */}
      {(enabled && user.gender) || available ? (
        <div className="t2-list t2-sgroup">
          {enabled && user.gender ? (
            <div className="t2-srow tall">
              <Icon name="person" className="t2-srow-icon" />
              <span className="t2-srow-main">
                <span className="t2-srow-title">الجنس</span>
                <span className="t2-srow-hint">
                  إقرارٌ ذاتيّ أعطيتَه عند التسجيل — لا نطلب وثيقة، ولا يظهر لأي مستخدمٍ آخر. عليه تُبنى مطابقةُ تفضيلات
                  الرحلات، ولتعديله راجع الدعم.
                </span>
              </span>
              <span className="t2-srow-value">{user.gender === "female" ? "أنثى" : "ذكر"}</span>
            </div>
          ) : null}
          {available ? (
            <div className="t2-srow tall">
              <Icon name="local_taxi" className="t2-srow-icon" />
              <span className="t2-srow-main">
                <span className="t2-srow-title">من يقودني افتراضياً</span>
                <span className="t2-srow-hint">
                  يسري على كل طلبٍ لا تختارين فيه غيره — ولك تغييره لرحلةٍ واحدة من شاشة الطلب.
                </span>
                {/* **لا حفظان معاً** — كان الزرُّ معطّلاً ما دام الحفظُ جارياً */}
                <AuthChoice
                  label="من يقودني افتراضياً"
                  value={defaultPreference}
                  options={PREFERENCES}
                  onChange={(next) => {
                    if (!savingPreference) void savePreference(next);
                  }}
                />
              </span>
            </div>
          ) : null}
        </div>
      ) : null}

      {/* **«الخصوصية» — التصميمُ النسائيُّ (شاشة ٧) يضعها هنا نصّاً**، وهي
          تخبرها **بأمانٍ تملكه ولا تعرفه**: أن جنسَها لا يُعرض لأحد، وأن
          خريطةَ السيارات القريبة مجهَّلةٌ أصلاً. وكلُّ حرفٍ فيها يصف سلوكاً
          **مبنيّاً ومختبَراً** لا وعداً: `drivers.anonymous_ref` يعطي كنيةً
          لكل اتصالٍ (إحداثياتٌ واتجاهٌ وفئةٌ فقط، SPEC §10)، و`RideDriverOut`
          وإطارُ `nearby_drivers` لا يحملان جنساً لأي طرف —
          و`test_admin_live_map.py::test_rider_facing_paths_still_carry_no_identity`
          يمنع انحرافَ ذلك.

          **وشرطُها الإقرارُ وحده** (كالسِمة): من لم تعلن جنسها ليس لديها ما
          تُطمأن عليه، والنصُّ لها لا عنها. ولا تذكر «سائقات» ولا خدمةً: هي
          حقيقةٌ عن **بياناتها** تسري والخدمةُ مطفأةٌ كما تسري وهي مشتعلة —
          فلا تُعلن عن غير موجود (قاعدةُ القرار 48). */}
      {themeAvailable ? (
        <section className="t2-privacy">
          <span className="t2-privacy-icon">
            <Icon name="lock" fill />
          </span>
          <div>
            <p className="t2-privacy-title">الخصوصية</p>
            <p className="t2-privacy-body">
              جنسُكِ لا يُعرض لأي كبتن — لا قبل القبول ولا بعده. وخريطةُ السيارات القريبة تعرض موقعاً واتجاهاً وفئةَ مركبةٍ
              فقط، بلا اسمٍ ولا لوحةٍ ولا أي معرّفٍ يُتابَع بين الجلسات.
            </p>
          </div>
        </section>
      ) : null}

      {error ? <NoteT2 tone="danger">{error}</NoteT2> : null}
      {done ? <NoteT2 tone="ok">{done}</NoteT2> : null}

      <button
        type="button"
        className="t2-logout"
        onClick={async () => {
          await signOut();
          navigate("/login", { replace: true });
        }}
      >
        تسجيل الخروج
      </button>
    </div>
  );
}
