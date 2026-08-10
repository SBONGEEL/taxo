/** استعادة كلمة المرور — SPEC القسم 12/1 (وكما في 11/1).
 *
 * ثلاث خطواتٍ في مسارٍ واحد، وشكلُ كلٍّ منها من `design/DESIGN.md` §5.3:
 * «استعادة كلمة المرور» ← «تحقق من رقمك» ← «كلمة مرور جديدة».
 *
 * **ولا جلسةَ تُفتح بمجرد الإثبات**: الإثبات وحده لا يفتح شيئاً، والتوكن
 * يُصدر بعد أن تُكتب الكلمة الجديدة فعلاً — ولذلك يُحمل الإثبات في الحالة
 * حتى الخطوة الأخيرة ويُرسل معها في طلبٍ واحد (`POST /auth/password-reset`).
 * ولو انقطع الطلب بعد الإثبات لم يبق للمهاجم شيء.
 */

import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { resetPassword, startPasswordResetChallenge } from "@/api/endpoints";
import { PhoneVerification } from "@/components/PhoneVerification";
import { AuthScreen } from "@/components/ui/AuthScreen";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { Field } from "@/components/ui/Field";
import { useConfig } from "@/lib/config";
import { useSession } from "@/lib/session";

type Step = "phone" | "verify" | "password";

export function ForgotPasswordScreen() {
  const navigate = useNavigate();
  const { config } = useConfig();
  const { signIn } = useSession();

  const [step, setStep] = useState<Step>("phone");
  const [phone, setPhone] = useState("");
  const [proof, setProof] = useState<string | null>(null);
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const method = config?.auth.verification ?? "none";

  const requestChallenge = useCallback(
    () => startPasswordResetChallenge(phone.trim()),
    [phone],
  );

  function toVerification() {
    setError(null);
    setStep("verify");
  }

  async function save() {
    if (password !== confirmation) {
      setError("كلمتا المرور غير متطابقتين");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      signIn(
        await resetPassword({
          phone: phone.trim(),
          verification_token: proof ?? "",
          new_password: password,
        }),
      );
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر تغيير كلمة المرور",
      );
      // إثباتٌ استُهلك لا يُعاد استعماله — يعود المستخدم لبدايةٍ نظيفة
      if (caught instanceof ApiError && caught.status === 401) {
        setProof(null);
        setStep("phone");
      }
    } finally {
      setBusy(false);
    }
  }

  if (step === "verify") {
    return (
      <AuthScreen onBack={() => setStep("phone")}>
        <PhoneVerification
          phone={phone.trim()}
          country={undefined}
          method={method}
          otpLength={config?.auth.otp_length ?? null}
          title="تحقق من رقمك"
          subtitle="أرسلنا رمز تحقق إلى رقمك المسجّل — هذا إثبات ملكية الرقم لا دخولاً."
          requestChallenge={requestChallenge}
          onProven={(token) => {
            setProof(token);
            setStep("password");
          }}
        />
      </AuthScreen>
    );
  }

  if (step === "password") {
    return (
      <AuthScreen onBack={() => setStep("verify")}>
        <h1 className="mt-24 text-23 font-bold text-ink">كلمة مرور جديدة</h1>
        <p className="mt-8 text-13 leading-snug text-muted">
          بعد الحفظ تُبطل كل الجلسات الأخرى على أجهزتك.
        </p>

        <form
          className="mt-22 flex flex-col gap-12"
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          <Field
            label="كلمة المرور"
            name="new-password"
            type="password"
            autoComplete="new-password"
            placeholder="••••••••"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <Field
            label="تأكيد كلمة المرور"
            name="confirm-password"
            type="password"
            autoComplete="new-password"
            placeholder="••••••••"
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
          />

          <ErrorNote message={error} />

          <Button
            type="submit"
            size="md"
            className="mt-20"
            loading={busy}
            disabled={!password || !confirmation}
          >
            حفظ كلمة المرور
          </Button>
        </form>
      </AuthScreen>
    );
  }

  return (
    <AuthScreen onBack={() => navigate("/login")}>
      <h1 className="mt-24 text-23 font-bold text-ink">استعادة كلمة المرور</h1>
      <p className="mt-8 text-13 leading-snug text-muted">
        سنرسل رمز تحقق إلى رقمك المسجّل — هذا إثبات ملكية الرقم لا دخولاً.
      </p>

      {/* **التحقق مطلوبٌ هنا دائماً** ولا يعفيه `otp_verification_enabled`:
          عفوُه يجعل إطفاء المفتاح طريقاً للاستيلاء على أي حساب بمعرفة رقمه
          (SPEC القسم 4). فبلا مُحقِّقٍ مُهيأ لا استعادةَ أصلاً، وتُقال الحقيقة
          هنا بدل أن يكتب الكبتن رمزاً لمُحقِّقٍ لا وجود له ثم يرتدّ بـ503 */}
      {method === "none" ? (
        <div className="mt-24">
          <ErrorNote message="استعادة كلمة المرور غير متاحة حالياً — لا مُحقِّق مُهيأ. راجع الدعم." />
        </div>
      ) : (
        <form
          className="mt-24"
          onSubmit={(event) => {
            event.preventDefault();
            toVerification();
          }}
        >
          <Field
            label="رقم الهاتف"
            name="phone"
            type="tel"
            dir="ltr"
            autoComplete="tel"
            placeholder="+962 7X XXX XXXX"
            value={phone}
            onChange={(event) => setPhone(event.target.value)}
          />

          <ErrorNote message={error} />

          <Button
            type="submit"
            size="md"
            className="mt-20"
            disabled={!phone.trim()}
          >
            إرسال الرمز
          </Button>
        </form>
      )}
    </AuthScreen>
  );
}
