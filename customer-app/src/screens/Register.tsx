/** التسجيل — **R03 «أنشئ حسابك» ثمّ R04 «أدخل رمز التحقق»** بلغة TAXO 2.0، **وإثباتُ الرقم مرّةً ثمّ كلمةُ المرور في الطلب
 * نفسِه** (القسم 11.1).
 *
 * الترتيبُ في الشاشة يتبع الترتيبَ في الخلفية: تُجمع البياناتُ كلُّها أوّلاً، ثمّ يقع الإثبات، ثمّ يُرسل `POST /auth/register`
 * **مرّةً واحدة** حاملاً الإثباتَ وكلمةَ المرور معاً — فلا يبقى حسابٌ نصفُ مُنشأٍ لرمزٍ لم يُقبل.
 *
 * **وما صحّحه المالكُ في اللوحة** (§٦١-أ و§٦٢/١١) مرسومٌ بلغتها: **تأكيدُ كلمة المرور** · **اختيارُ السوق** · **الموافقةُ على
 * السياسات** · رمزٌ **بطول ما ينشره المُحقِّق** · وقاعدةُ الكلمة **كما تنشرها الخلفية** (٨–١٢٨ وقائمةُ المنع) — لا «بينها رقم».
 */
import { useCallback, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { register, startChallenge } from "@/api/endpoints";
import { PolicyConsentT2 } from "@/components/t2/PolicyConsentT2";
import { VerifyCode } from "@/components/t2/VerifyCode";
import { reopenWelcome } from "@/components/welcome/gate";
import { useAuthCountry, useConfig, useFeature, usePhoneCountry } from "@/lib/config";
import { confirmError, passwordConditions, passwordError, passwordsReady } from "@/lib/password";
import { COUNTRY_LABEL, looksComplete, toNational } from "@/lib/phone";
import { useSession } from "@/lib/session";
import {
  AuthBlock,
  AuthChoice,
  AuthConditions,
  AuthInput,
  AuthPage,
  AuthPhone,
  AuthSecret,
  AuthTitle,
  AuthTop,
  AuthWomenNote,
  Icon,
} from "@/taxo2";

type Field = "name" | "phone" | "password";
type Failure = { field: Field | null; message: string };

/** حقلُ الشاشة الذي يحمل اسمَ حقل الخلفية (SPEC ١٧.٧). */
const INPUT_ID: Record<Field, string> = { name: "name", phone: "phone", password: "new-password" };

export function RegisterScreen() {
  const { config } = useConfig();
  const { signIn } = useSession();
  const navigate = useNavigate();

  const [step, setStep] = useState<"details" | "verify">("details");
  // **الدولةُ من `useAuthCountry`** — بيتٌ واحدٌ لشاشات المصادقة الثلاث
  const { country, countries, setCountry } = useAuthCountry();
  // المُحقِّقُ **وطولُ رمزه** يتبعان الدولةَ المختارة لا الافتراضية (12-هـ)
  const entry = config?.countries.find((item) => item.country_code === country);
  const verification = entry?.verification ?? config?.auth.verification ?? "none";
  const { dialCode, nationalLength } = usePhoneCountry(country);
  // الدولةُ تُختار في هذه الشاشة، فالمفتاحُ يُقرأ منها لا من حسابٍ لا وجودَ له
  const womenService = useFeature(country, "women_service_enabled");

  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [gender, setGender] = useState<"male" | "female" | null>(null);
  const [touched, setTouched] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [busy, setBusy] = useState(false);

  // **الموافقةُ شرطٌ في الزرّ لا في الرسالة** (البند ١٠) — والخلفيةُ ترفض أيضاً: حارسان لا واحد
  const [policyIds, setPolicyIds] = useState<string[]>([]);
  const [agreed, setAgreed] = useState(false);
  const consentOk = policyIds.length === 0 || agreed;
  const onPolicies = useCallback((ids: string[]) => setPolicyIds(ids), []);

  const complete = looksComplete(phone, nationalLength);
  const ready = useMemo(
    () => complete && name.trim().length >= 2 && passwordsReady(password, confirm) && consentOk,
    [complete, name, password, confirm, consentOk],
  );

  const errorOf = (field: Field) => (failure?.field === field ? failure.message : null);
  const nameShort = touched && name.length > 0 && name.trim().length < 2 ? "الاسم قصير — حرفان على الأقل." : null;
  const phoneShort =
    touched && phone.length > 0 && !complete && dialCode !== null ? `الرقم ناقص — ${nationalLength} أرقام بعد +${dialCode}.` : null;

  async function create(verificationToken?: string) {
    setBusy(true);
    setFailure(null);
    try {
      signIn(
        await register({
          phone,
          name: name.trim(),
          password,
          country_code: country,
          verification_token: verificationToken,
          gender: gender ?? undefined,
          // **ما وافق عليه بعينه** — لا `true` تستنتج منها الخلفيةُ شيئاً
          accepted_policy_ids: agreed ? policyIds : [],
        }),
      );
      navigate("/", { replace: true });
    } catch (caught) {
      if (caught instanceof ApiError) {
        const field = caught.field("field");
        const at = field === "name" || field === "phone" || field === "password" ? field : null;
        setFailure({ field: at, message: caught.message });
        setStep("details");
        if (at) window.setTimeout(() => document.getElementById(INPUT_ID[at])?.focus(), 0);
      } else {
        setFailure({ field: null, message: "تعذّر الاتصال بالخادم — أعد المحاولة" });
        setStep("details");
      }
    } finally {
      setBusy(false);
    }
  }

  function next(event: React.FormEvent) {
    event.preventDefault();
    if (!ready) {
      setTouched(true);
      return;
    }
    // لا مُحقِّقَ مُهيّأ: الحسابُ يُنشأ غيرَ محقَّقٍ ويبقى موسوماً حتى يُثبت رقمه (SPEC القسم 4) — تقرّره الخلفيةُ لا الواجهة
    if (verification === "none") {
      void create();
      return;
    }
    setStep("verify");
  }

  const total = verification === "none" ? 0 : 2;

  if (step === "verify") {
    return (
      <VerifyCode
        phone={phone}
        dialCode={dialCode}
        method={verification}
        otpLength={entry?.otp_length ?? null}
        requestChallenge={(channel) => startChallenge(phone, country, channel)}
        onProven={(token) => void create(token)}
        onBack={() => setStep("details")}
        onLeave={() => setStep("details")}
        step={2}
        total={2}
        outerError={failure?.field === null ? failure.message : null}
        busy={busy}
      />
    );
  }

  return (
    <AuthPage>
      <AuthTop onBack={reopenWelcome} step={total ? 1 : undefined} total={total || undefined} />
      <AuthTitle step title="أنشئ حسابك" sub="رقمك هو هويتك في TAXO — نتحقق منه مرة واحدة." />

      <form onSubmit={next} className="t2-auth-form step" noValidate>
        <AuthBlock label="الاسم الكامل" htmlFor="name" error={nameShort ?? errorOf("name")}>
          <AuthInput
            id="name"
            name="name"
            autoComplete="name"
            value={name}
            placeholder="اسمك كما يظهر للكبتن"
            invalid={Boolean(nameShort ?? errorOf("name"))}
            onBlur={() => setTouched(true)}
            onChange={(event) => setName(event.target.value)}
          />
        </AuthBlock>

        {countries.length > 1 ? (
          <AuthBlock label="السوق">
            <AuthChoice
              label="السوق"
              value={country}
              options={countries.map((code) => ({ value: code, label: COUNTRY_LABEL[code] }))}
              onChange={setCountry}
            />
          </AuthBlock>
        ) : null}

        <AuthBlock
          label="رقم الهاتف"
          htmlFor="phone"
          error={
            dialCode === null
              ? "مفتاحُ هذه الدولة غير متاح الآن — اختر دولةً أخرى أو أعد المحاولة."
              : phoneShort ?? errorOf("phone")
          }
        >
          <AuthPhone
            id="phone"
            name="phone"
            dial={dialCode}
            value={phone}
            maxLength={nationalLength}
            valid={complete}
            disabled={dialCode === null}
            invalid={Boolean(phoneShort ?? errorOf("phone"))}
            onBlur={() => setTouched(true)}
            onChange={(event) => (dialCode === null ? undefined : setPhone(toNational(event.target.value, dialCode)))}
          />
        </AuthBlock>

        <AuthBlock label="كلمة المرور" htmlFor="new-password" error={passwordError(password) ?? errorOf("password")}>
          <AuthSecret
            id="new-password"
            name="new-password"
            autoComplete="new-password"
            value={password}
            invalid={Boolean(passwordError(password) ?? errorOf("password"))}
            onChange={(event) => setPassword(event.target.value)}
          />
          <AuthConditions items={passwordConditions(password)} />
        </AuthBlock>

        <AuthBlock label="تأكيد كلمة المرور" htmlFor="confirm" error={confirmError(password, confirm)}>
          <AuthSecret
            id="confirm"
            name="confirm"
            autoComplete="new-password"
            value={confirm}
            invalid={Boolean(confirmError(password, confirm))}
            onChange={(event) => setConfirm(event.target.value)}
          />
        </AuthBlock>

        {/* إقرارٌ ذاتيٌّ بلا وثيقة (المرحلة 10-ج) — **اختياريّ**: من تركه لا يُخمَّن عنه. ويظهر حيث الخدمةُ مفتوحةٌ في الدولة وحدها */}
        {womenService ? (
          <AuthBlock label="نخاطبك بصيغة" hint="اختياريّ — إقرارٌ ذاتيٌّ بلا وثيقة، لمطابقة تفضيلات الرحلات وحدها، ولا يظهر لأحد.">
            <AuthChoice
              label="نخاطبك بصيغة"
              value={gender}
              options={[
                { value: "male", label: "راكب" },
                { value: "female", label: "راكبة", women: true },
              ]}
              onChange={(value) => setGender(gender === value ? null : value)}
            />
            {gender === "female" ? (
              <AuthWomenNote>يتيح لكِ هذا طلب كبتنة عبر الخدمة النسائية، ويمكن تغييره من الحساب.</AuthWomenNote>
            ) : null}
          </AuthBlock>
        ) : null}

        {/* **مربّعٌ يُضغط لا جملةٌ تفترض** (البند ١٠، ٢٠٢٦-٠٩-٠٥) */}
        <PolicyConsentT2 country={country} checked={agreed} onChange={setAgreed} onLoaded={onPolicies} />

        {failure && failure.field === null ? (
          <div className="t2-auth-banner" role="alert">
            <Icon name="error" />
            <span>{failure.message}</span>
          </div>
        ) : null}

        <div className="t2-auth-push" />
        <div className="t2-auth-actions">
          <button type="submit" className="t2-button primary" disabled={busy || dialCode === null || !ready}>
            {busy ? "لحظة…" : verification === "none" ? "إنشاء الحساب" : "متابعة"}
          </button>
        </div>
      </form>

      <p className="t2-auth-foot">
        لديك حساب؟ <Link to="/login">ادخل</Link>
      </p>
    </AuthPage>
  );
}
