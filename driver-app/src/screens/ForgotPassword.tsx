/** استعادة كلمة المرور — SPEC القسم 12/1 (وكما في 11/1)، **بلغة TAXO 2.0**: لا لوحةَ لها عند الكبتن، فرُسمت بلغة R03 · R04
 * (رجوعٌ دائريٌّ ومسارُ خطوات، وعنوانٌ وسطرُه، وحقولُ C01) **بخطواتها الثلاث كما كانت**: «استعادة كلمة المرور» ← «أدخل رمز
 * التحقق» ← «كلمة مرور جديدة».
 *
 * **ولا جلسةَ تُفتح بمجرد الإثبات**: الإثبات وحده لا يفتح شيئاً، والتوكن يُصدر بعد أن تُكتب الكلمة الجديدة فعلاً — ولذلك
 * يُحمل الإثبات في الحالة حتى الخطوة الأخيرة ويُرسل معها في طلبٍ واحد (`POST /auth/password-reset`). ولو انقطع الطلب بعد
 * الإثبات لم يبق للمهاجم شيء.
 *
 * **والتحقق مطلوبٌ هنا دائماً** ولا يعفيه `otp_verification_enabled`: عفوُه يجعل إطفاء المفتاح طريقاً للاستيلاء على أي حساب
 * بمعرفة رقمه (SPEC القسم 4) — فبلا مُحقِّقٍ مُهيأ لا استعادةَ أصلاً، وتُقال الحقيقةُ بدل رمزٍ لمُحقِّقٍ لا وجود له.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { resetPassword, startPasswordResetChallenge } from "@/api/endpoints";
import type { OtpChannel } from "@/api/types";
import { MarketChoice } from "@/components/t2/MarketChoice";
import { VerifyCode } from "@/components/t2/VerifyCode";
import { forgetToken } from "@/lib/biometric";
import { useAuthCountry, useConfig, usePhoneCountry } from "@/lib/config";
import { confirmError, passwordConditions, passwordError } from "@/lib/password";
import { looksComplete, toE164, toNational } from "@/lib/phone";
import { useSession } from "@/lib/session";
import {
  AuthBlock,
  AuthConditions,
  AuthPage,
  AuthPhone,
  AuthSecret,
  AuthTitle,
  AuthTop,
  Icon,
} from "@/taxo2";

import "@/components/t2/captain-auth.css";

type Step = "phone" | "verify" | "password";
type Failure = { field: "phone" | "password" | null; message: string };

export function ForgotPasswordScreen() {
  const navigate = useNavigate();
  const { config } = useConfig();
  const { signIn } = useSession();
  // **منتقي الدولة في الثلاث لا في التسجيل وحدَه** (البند ١٠): من يحمل رقماً
  // ليبياً كان يرى مفتاحَ الأردن فيُرفض رقمُه بلا أن يفهم لماذا
  const { country, countries, setCountry } = useAuthCountry();
  const { dialCode, nationalLength } = usePhoneCountry(country);

  const [step, setStep] = useState<Step>("phone");
  const [phone, setPhone] = useState("");
  const [proof, setProof] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [touched, setTouched] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [busy, setBusy] = useState(false);
  const page = useRef<HTMLDivElement>(null);

  // المُحقِّقُ وطولُ رمزه يتبعان الدولةَ المختارة لا الافتراضية (12-هـ)
  const entry = config?.countries.find((item) => item.country_code === country);
  const method = entry?.verification ?? config?.auth.verification ?? "none";
  const otpLength = entry?.otp_length ?? config?.auth.otp_length ?? null;

  // **ولا رقمَ بلا مفتاحٍ منشور** (`usePhoneCountry`): بمفتاحٍ فارغٍ يُبنى
  // رقمٌ بلا دولة، وبمفتاح سوقٍ آخرَ يُبنى رقمُ إنسانٍ آخر — فيُقال إن الرمز
  // أُرسل ولا يصل أحداً. والفراغُ هنا يُعطّل الإرسالَ ويُقال سببُه
  const e164 = dialCode === null ? "" : toE164(phone, dialCode);
  // القناةُ تُمرَّر لا تُهمَل — انظر `Register.tsx`
  const requestChallenge = useCallback(
    (channel?: OtpChannel) => startPasswordResetChallenge(e164, country, channel),
    [e164, country],
  );

  const complete = looksComplete(phone, nationalLength);
  const short =
    touched && phone.length > 0 && !complete && dialCode !== null
      ? `الرقم ناقص — ${nationalLength} أرقام بعد +${dialCode}.`
      : null;

  // الخطوةُ الجديدةُ تُفتح من أعلاها لا من حيث توقّف التمرير
  useEffect(() => {
    if (page.current) page.current.scrollTop = 0;
  }, [step]);

  function toVerification(event: FormEvent) {
    event.preventDefault();
    if (!complete) {
      setTouched(true);
      return;
    }
    setFailure(null);
    setStep("verify");
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    if (busy || !password || !confirmation) return;
    if (password !== confirmation) {
      // **سببُه تحت حقله** (`confirmError`) ظاهرٌ منذ الكتابة — فيُنقل إليه التركيزُ ولا يُرسل شيء
      document.getElementById("confirm-password")?.focus();
      return;
    }
    setBusy(true);
    setFailure(null);
    try {
      const response = await resetPassword({
        phone: e164,
        country_code: country,
        verification_token: proof ?? "",
        new_password: password,
      });
      // **الثانيةُ من الأربع** (قرارُ المالك): تبديلُ كلمة المرور يمحو
      // المخزَّنَ **قبل** أن تقوم الجلسةُ الجديدة.
      //
      // **وأثرُها الحقيقيُّ على الأجهزة الأخرى**: `set_password` في الخلفية
      // **يُبطل كلَّ جلسات صاحبها** (مقيس) — فجهازٌ آخرُ يحمل رمزاً مخزَّناً
      // يتلقّى ردَّ «لم تعد صالحة» فيمحوه بالثالثة. **وهنا يُمحى صراحةً**
      // ولا يُتّكل على أن الجديد سيحلّ محلَّ القديم: اتّكالٌ كهذا يترك رمزاً
      // ميتاً لو تعثّر الحفظُ الجديد.
      await forgetToken();
      signIn(response);
    } catch (caught) {
      if (caught instanceof ApiError) {
        const field = caught.field("field");
        if (caught.status === 401) {
          // إثباتٌ استُهلك لا يُعاد استعماله — يعود المستخدم لبدايةٍ نظيفة، والسببُ معه
          setFailure({ field: field === "phone" ? "phone" : null, message: caught.message });
          setProof(null);
          setStep("phone");
        } else {
          const at = field === "new_password" || field === "password" ? "password" : null;
          setFailure({ field: at, message: caught.message });
          if (at) document.getElementById("new-password")?.focus();
        }
      } else {
        setFailure({ field: null, message: "تعذّر تغيير كلمة المرور — أعد المحاولة" });
      }
    } finally {
      setBusy(false);
    }
  }

  const banner =
    failure && failure.field === null ? (
      <div className="t2-auth-banner" role="alert">
        <Icon name="error" />
        <span>{failure.message}</span>
      </div>
    ) : null;

  if (step === "verify") {
    return (
      <div ref={page} className="cap-auth scr">
        <AuthPage>
          <VerifyCode
            top={<AuthTop onBack={() => setStep("phone")} step={2} total={3} />}
            phone={e164}
            method={method}
            otpLength={otpLength}
            requestChallenge={requestChallenge}
            onProven={(token) => {
              setProof(token);
              setStep("password");
            }}
            onBack={() => setStep("phone")}
            note="هذا إثبات ملكية الرقم لا دخولاً."
          />
        </AuthPage>
      </div>
    );
  }

  if (step === "password") {
    return (
      <div ref={page} className="cap-auth scr">
        <AuthPage>
          <AuthTop onBack={() => setStep("verify")} step={3} total={3} />
          <AuthTitle step title="كلمة مرور جديدة" sub="بعد الحفظ تُبطل كل الجلسات الأخرى على أجهزتك." />

          <form onSubmit={save} className="t2-auth-form" noValidate>
            <AuthBlock
              label="كلمة المرور"
              htmlFor="new-password"
              error={passwordError(password) ?? (failure?.field === "password" ? failure.message : null)}
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

            <AuthBlock
              label="تأكيد كلمة المرور"
              htmlFor="confirm-password"
              error={confirmError(password, confirmation)}
            >
              <AuthSecret
                id="confirm-password"
                name="confirm-password"
                autoComplete="new-password"
                value={confirmation}
                invalid={Boolean(confirmError(password, confirmation))}
                onChange={(event) => setConfirmation(event.target.value)}
              />
            </AuthBlock>

            {banner}

            <div className="t2-auth-push" />
            <div className="t2-auth-actions">
              <button type="submit" className="t2-button primary" disabled={busy || !password || !confirmation}>
                {busy ? "لحظة…" : "حفظ كلمة المرور"}
              </button>
            </div>
          </form>
        </AuthPage>
      </div>
    );
  }

  return (
    <div ref={page} className="cap-auth scr">
      <AuthPage>
        <AuthTop
          onBack={() => navigate("/login")}
          step={method === "none" ? undefined : 1}
          total={method === "none" ? undefined : 3}
        />
        <AuthTitle
          step
          title="استعادة كلمة المرور"
          sub="سنرسل رمز تحقق إلى رقمك المسجّل — هذا إثبات ملكية الرقم لا دخولاً."
        />

        {/* **التحقق مطلوبٌ هنا دائماً** — بلا مُحقِّقٍ مُهيأ تُقال الحقيقة بدل أن يكتب الكبتن رمزاً لمُحقِّقٍ لا وجود له ثم يرتدّ بـ503 */}
        {method === "none" ? (
          <div className="t2-auth-banner" role="alert">
            <Icon name="error" />
            <span>استعادة كلمة المرور غير متاحة حالياً — لا مُحقِّق مُهيأ. راجع الدعم.</span>
          </div>
        ) : (
          <form onSubmit={toVerification} className="t2-auth-form" noValidate>
            <MarketChoice country={country} countries={countries} onChange={setCountry} />

            <AuthBlock
              label="رقم الهاتف"
              htmlFor="phone"
              error={
                dialCode === null
                  ? "مفتاحُ هذه الدولة غير متاح الآن — اختر دولةً أخرى أو أعد المحاولة."
                  : short ?? (failure?.field === "phone" ? failure.message : null)
              }
            >
              <AuthPhone
                id="phone"
                name="phone"
                type="tel"
                inputMode="numeric"
                dial={dialCode}
                value={phone}
                maxLength={nationalLength}
                valid={complete}
                disabled={dialCode === null}
                invalid={Boolean(short) || failure?.field === "phone"}
                onBlur={() => setTouched(true)}
                onChange={(event) =>
                  dialCode === null ? undefined : setPhone(toNational(event.target.value, dialCode))
                }
              />
            </AuthBlock>

            {banner}

            <div className="t2-auth-push" />
            <div className="t2-auth-actions">
              <button type="submit" className="t2-button primary" disabled={!complete}>
                إرسال الرمز
              </button>
            </div>
          </form>
        )}
      </AuthPage>
    </div>
  );
}
