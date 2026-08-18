/** التسجيل — الخطوة ١ من ٣ ثم إثباتُ الرقم (SPEC القسم 12/1).
 *
 * ترتيبُ التصميم مطابقٌ للمواصفات حرفياً وليس صدفة: **الرقم يُثبت قبل أن
 * ينتظر المراجعة** — رقمُ الكبتن هو ما تصل عليه حوالات كليك (القسم 6/9)،
 * فالإثبات شرطُ الاعتماد لا تفصيلٌ يُؤجَّل.
 *
 * والإثبات وكلمةُ المرور يُرسلان في **طلبٍ واحد** (`POST /auth/register`):
 * حسابٌ يُفتح بالإثبات وحده حسابٌ بلا كلمة مرور، وإثباتٌ يفتح جلسةً قبل أن
 * تُكتب الكلمة يترك للمهاجم شيئاً إن انقطع الطلب بعده (القسم 15/أ).
 *
 * الشكل من `design/DESIGN.md` §5.3: «الخطوة ١ من ٣» 12px، العنوان 22/700،
 * الحقول بفجوة 12، ثم زرٌّ أساسي وملاحظةٌ 11.5 بسطرٍ 1.7.
 */

import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { registerAccount, startSignupChallenge } from "@/api/endpoints";
import type { OtpChannel } from "@/api/types";
import { CountryPicker } from "@/components/CountryPicker";
import { PhoneField } from "@/components/PhoneField";
import { PhoneVerification } from "@/components/PhoneVerification";
import { AuthScreen } from "@/components/ui/AuthScreen";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { Field } from "@/components/ui/Field";
import { useAuthCountry, useConfig, usePhoneCountry } from "@/lib/config";
import { looksComplete, toE164 } from "@/lib/phone";
import { useSession } from "@/lib/session";
import { confirmError, passwordError, passwordRule, passwordsReady } from "@/lib/password";
import { FieldConditions } from "@/components/FieldConditions";

/** يوجّه خطأَ حقلٍ من الخلفية إلى حقله في الشاشة (SPEC ١٧.٧).
 *
 * **والخريطةُ لأن اسمَ الحقل في الشاشة ليس دائماً اسمَه في المخطط**: حقلُ
 * كلمة المرور هنا `new-password` (لدلالة الإكمال التلقائي)، والخلفيةُ تسمّيه
 * `password`. وبغير التوجيه يُعلَّم لا شيء وينتقل التركيزُ إلى لا مكان.
 */
const FIELD_INPUT: Record<string, string> = {
  password: "new-password",
  name: "name",
  phone: "phone",
};

function focusField(field: string): void {
  document
    .querySelector<HTMLInputElement>(`[name="${FIELD_INPUT[field] ?? field}"]`)
    ?.focus();
}

export function RegisterScreen() {
  const navigate = useNavigate();
  const { config } = useConfig();
  const { signIn } = useSession();

  // **الاختيارُ محفوظٌ على الجهاز** (البند ١٠): نسخةٌ محليةٌ هنا تعني اختياراً
  // يُنسى بين التسجيل والدخول، فيعيده صاحبُ الرقم الليبيّ في كل شاشة
  const { country, countries, setCountry } = useAuthCountry();
  const { dialCode, nationalLength } = usePhoneCountry(country);

  const [step, setStep] = useState<"details" | "verify">("details");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // المُحقِّقُ يتبع الدولةَ المختارة لا الافتراضية (12-هـ)
  const method =
    config?.countries.find((entry) => entry.country_code === country)
      ?.verification ??
    config?.auth.verification ??
    "none";
  // **ولا رقمَ بلا مفتاحٍ منشور** (`usePhoneCountry`): بمفتاحٍ فارغٍ يُبنى
  // رقمٌ بلا دولة، وبمفتاح سوقٍ آخرَ يُبنى رقمُ إنسانٍ آخر — فيُقال إن الرمز
  // أُرسل ولا يصل أحداً. والفراغُ هنا يُعطّل الإرسالَ ويُقال سببُه
  const e164 = dialCode === null ? "" : toE164(phone, dialCode);

  // **والقناةُ تُمرَّر لا تُهمَل**: زرُّ الارتداد يعطي القناةَ التالية، فمُغلَّفٌ
  // يتجاهلها يعيد الإرسال في القناة الفاشلة نفسها — زرٌّ يعمل ولا يفعل شيئاً
  const requestChallenge = useCallback(
    (channel?: OtpChannel) => startSignupChallenge(e164, country, channel),
    [e164, country],
  );

  const complete =
    name.trim().length >= 2 &&
    looksComplete(phone, nationalLength) &&
    passwordsReady(password, confirmation);

  function next() {
    setError(null);
    if (password !== confirmation) {
      setError("كلمتا المرور غير متطابقتين");
      return;
    }
    // مُحقِّقٌ مطفأ للطوارئ: الخلفية تقبل التسجيل بلا إثبات وتَسِم الحساب
    // (SPEC القسم 4)، فلا خطوةَ إثباتٍ تُعرض على أحد
    if (method === "none") {
      void create();
      return;
    }
    setStep("verify");
  }

  async function create(verificationToken?: string) {
    setBusy(true);
    setError(null);
    try {
      signIn(
        await registerAccount({
          phone: e164,
          name: name.trim(),
          password,
          country_code: country,
          verification_token: verificationToken,
        }),
      );
      navigate("/register/documents", { replace: true });
    } catch (caught) {
      if (caught instanceof ApiError) {
        const field = caught.field("field");
        setError(caught.message);
        // الحقلُ المرفوض يُعلَّم ويُنتقل إليه — لا شريطٌ وحدَه يترك صاحبَه يبحث
        if (field) focusField(field);
      } else {
        setError("تعذّر الاتصال بالخادم — أعد المحاولة");
      }
      // إثباتٌ استُهلك لا يُعاد استعماله
      if (caught instanceof ApiError && caught.status === 401)
        setStep("details");
    } finally {
      setBusy(false);
    }
  }

  if (step === "verify") {
    return (
      <AuthScreen onBack={() => setStep("details")}>
        <PhoneVerification
          phone={e164}
          method={method}
          otpLength={config?.auth.otp_length ?? null}
          title="تحقق من رقمك"
          subtitle={`أرسلنا رمز تحقق إلى ${e164} — التحقق من الرقم مرة واحدة عند التسجيل.`}
          requestChallenge={requestChallenge}
          onProven={(token) => void create(token)}
          submitting={busy}
        />
        <ErrorNote message={error} />
      </AuthScreen>
    );
  }

  return (
    <AuthScreen onBack={() => navigate("/login")} className="px-26">
      <div className="mt-20 text-12 text-muted">الخطوة ١ من ٣</div>
      <h1 className="mb-4 text-22 font-bold text-ink">إنشاء حساب كبتن</h1>
      <p className="mb-20 text-12.5 leading-snug text-muted">
        الرقم هو مُعرّف دخولك، ويُخزَّن بصيغة دولية.
      </p>

      <form
        className="flex flex-col gap-12"
        onSubmit={(event) => {
          event.preventDefault();
          next();
        }}
      >
        <Field
          label="الاسم الكامل"
          name="name"
          autoComplete="name"
          placeholder="مثال: أبو محمد الزعبي"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />

        <PhoneField value={phone} onChange={setPhone} country={country} />

        <CountryPicker
          country={country}
          countries={countries}
          onChange={setCountry}
        />

        <Field
          label="كلمة المرور"
          name="new-password"
          type="password"
          autoComplete="new-password"
          placeholder="••••••••"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          error={passwordError(password) ?? undefined}
        />
          <FieldConditions rule={passwordRule()} value={password} />
        <Field
          label="تأكيد كلمة المرور"
          name="confirm-password"
          type="password"
          autoComplete="new-password"
          placeholder="••••••••"
          value={confirmation}
          error={confirmError(password, confirmation) ?? undefined}
          onChange={(event) => setConfirmation(event.target.value)}
        />

        <ErrorNote message={error} />

        <Button
          type="submit"
          size="md"
          className="mt-20"
          loading={busy}
          disabled={!complete}
        >
          التالي
        </Button>
      </form>

      <p className="mt-14 text-center text-11.5 leading-note text-muted">
        بالمتابعة أنت توافق على شروط الاستخدام. الرقم يُثبت بالتحقق مرة واحدة.
      </p>
    </AuthScreen>
  );
}
