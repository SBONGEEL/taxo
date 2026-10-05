/** استعادةُ كلمة المرور — **بلغة R03 · R04** (لا لوحةَ لها في TAXO 2.0، فرُسمت من أختيها — §٦٢/٦)، **وقاعدتاها كما هما**
 * (SPEC القسم 11.1):
 *
 * - **لا جلسةَ تُفتح بمجرّد الإثبات**: تُكتب الكلمةُ الجديدة أوّلاً ثمّ يُرسل الإثباتُ معها في `POST /auth/password-reset`، فتصدر
 *   الجلسةُ بعد أن كُتبت الكلمةُ فعلاً (SPEC القسم 15/أ).
 * - **التحقّقُ مطلوبٌ هنا دائماً** ولا يعفيه `otp_verification_enabled`: عفوُه يجعل إطفاءَ المفتاح طريقاً للاستيلاء على أيِّ حسابٍ
 *   بمعرفة رقمه (القسم 4) — فإن كان المُحقِّقُ `none` قيل إن الاستعادةَ غيرُ متاحةٍ الآن.
 *
 * **وتأكيدُ الكلمة الجديدة أُضيف** (§٦٢-ب): خطأُ طباعةٍ في كلمةٍ **لا تُعرض** لا يُكتشف إلا عند العجز عن الدخول — وهي علّةُ التأكيد
 * في التسجيل نفسُها، **والطلبُ لا يتغيّر** (الخلفيةُ تأخذ كلمةً واحدة).
 */
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { resetPassword, startPasswordReset } from "@/api/endpoints";
import { VerifyCode } from "@/components/t2/VerifyCode";
import { forgetToken } from "@/lib/biometric";
import { useAuthCountry, useConfig, usePhoneCountry } from "@/lib/config";
import { confirmError, passwordConditions, passwordError, passwordsReady } from "@/lib/password";
import { COUNTRY_LABEL, looksComplete, toNational } from "@/lib/phone";
import { useSession } from "@/lib/session";
import {
  AuthBlock,
  AuthChoice,
  AuthConditions,
  AuthPage,
  AuthPhone,
  AuthSecret,
  AuthTitle,
  AuthTop,
  Icon,
} from "@/taxo2";

type Failure = { field: "phone" | "password" | null; message: string };

export function ForgotPasswordScreen() {
  const { config } = useConfig();
  const { signIn } = useSession();
  const navigate = useNavigate();
  const [step, setStep] = useState<"details" | "verify">("details");
  // **من `useAuthCountry` لا من `countries[0]`**: الترتيبُ في `/config` تعدادٌ لا أفضلية
  const { country, countries, setCountry } = useAuthCountry();
  const entry = config?.countries.find((item) => item.country_code === country);
  const verification = entry?.verification ?? config?.auth.verification ?? "none";
  const { dialCode, nationalLength } = usePhoneCountry(country);
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [touched, setTouched] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [busy, setBusy] = useState(false);

  const complete = looksComplete(phone, nationalLength);
  const ready = useMemo(() => complete && passwordsReady(password, confirm), [complete, password, confirm]);
  const phoneShort =
    touched && phone.length > 0 && !complete && dialCode !== null ? `الرقم ناقص — ${nationalLength} أرقام بعد +${dialCode}.` : null;

  async function apply(verificationToken: string) {
    setBusy(true);
    setFailure(null);
    try {
      const response = await resetPassword({
        phone,
        country_code: country,
        verification_token: verificationToken,
        new_password: password,
      });
      // **تبديلُ كلمة المرور يمحو المخزَّن قبل أن تقوم الجلسةُ الجديدة** — و`set_password` في الخلفية يُبطل كلَّ الجلسات
      await forgetToken();
      signIn(response);
      navigate("/", { replace: true });
    } catch (caught) {
      if (caught instanceof ApiError) {
        const field = caught.field("field");
        setFailure({ field: field === "phone" || field === "password" ? field : null, message: caught.message });
      } else {
        setFailure({ field: null, message: "تعذّر تغيير كلمة المرور — أعد المحاولة" });
      }
      setStep("details");
    } finally {
      setBusy(false);
    }
  }

  if (step === "verify") {
    return (
      <VerifyCode
        phone={phone}
        dialCode={dialCode}
        method={verification}
        otpLength={entry?.otp_length ?? null}
        requestChallenge={(channel) => startPasswordReset(phone, country, channel)}
        onProven={(token) => void apply(token)}
        onBack={() => setStep("details")}
        onLeave={() => setStep("details")}
        step={2}
        total={2}
        submitLabel="تغيير كلمة المرور"
        busy={busy}
      />
    );
  }

  return (
    <AuthPage>
      <AuthTop onBack={() => navigate("/login")} step={verification === "none" ? undefined : 1} total={verification === "none" ? undefined : 2} />
      <AuthTitle step title="نسيت كلمة المرور؟" sub="اكتب رقمك وكلمة مرورٍ جديدة، ثم نرسل لك رمزاً نتأكد به أنه رقمك." />

      {verification === "none" ? (
        <div className="t2-auth-banner" role="alert">
          <Icon name="error" />
          <span>استعادة كلمة المرور غير متاحة حالياً — لا مُحقِّق مُهيّأ. راجع الدعم.</span>
        </div>
      ) : (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            if (ready) setStep("verify");
            else setTouched(true);
          }}
          className="t2-auth-form step"
          noValidate
        >
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
                : phoneShort ?? (failure?.field === "phone" ? failure.message : null)
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
              invalid={Boolean(phoneShort) || failure?.field === "phone"}
              onBlur={() => setTouched(true)}
              onChange={(event) => (dialCode === null ? undefined : setPhone(toNational(event.target.value, dialCode)))}
            />
          </AuthBlock>

          <AuthBlock
            label="كلمة المرور الجديدة"
            htmlFor="new-password"
            error={passwordError(password) ?? (failure?.field === "password" ? failure.message : null)}
            hint="تُغلق كلُّ الجلسات المفتوحة على حسابك بعد التغيير."
          >
            <AuthSecret
              id="new-password"
              name="new-password"
              autoComplete="new-password"
              value={password}
              invalid={Boolean(passwordError(password)) || failure?.field === "password"}
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

          {failure && failure.field === null ? (
            <div className="t2-auth-banner" role="alert">
              <Icon name="error" />
              <span>{failure.message}</span>
            </div>
          ) : null}

          <div className="t2-auth-push" />
          <div className="t2-auth-actions">
            <button type="submit" className="t2-button primary" disabled={busy || dialCode === null || !ready}>
              متابعة
            </button>
          </div>
        </form>
      )}

      <p className="t2-auth-foot">
        تذكّرتَها؟ <Link to="/login">ادخل</Link>
      </p>
    </AuthPage>
  );
}
