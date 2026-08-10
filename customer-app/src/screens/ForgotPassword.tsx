/** استعادة كلمة المرور — **شاشةٌ منفصلة** (SPEC القسم 11.1).
 *
 * قاعدتان تنعكسان في ترتيب هذه الشاشة حرفياً:
 *
 * - **لا جلسةَ تُفتح بمجرد الإثبات**: تُكتب الكلمة الجديدة أولاً ثم يُرسل
 *   الإثبات معها في `POST /auth/password-reset`، فتصدر الجلسة بعد أن كُتبت
 *   الكلمة فعلاً (SPEC القسم 15/أ).
 * - **التحقق مطلوبٌ هنا دائماً** ولا يعفيه `otp_verification_enabled`: عفوُه
 *   يجعل إطفاء المفتاح طريقاً للاستيلاء على أي حساب بمعرفة رقمه (القسم 4).
 *   ولذلك لا تسأل هذه الشاشة عن المُحقِّق إن كان `none` — بل تقول إن
 *   الاستعادة غير متاحة الآن.
 */

import { motion } from "framer-motion";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { resetPassword, startPasswordReset } from "@/api/endpoints";
import type { CountryCode } from "@/api/types";
import { Brand } from "@/components/Brand";
import { PhoneInput } from "@/components/PhoneInput";
import { PhoneVerification } from "@/components/PhoneVerification";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { Field } from "@/components/ui/Field";
import { useConfig } from "@/lib/config";
import { usePhoneCountry } from "@/lib/config";
import { looksComplete } from "@/lib/phone";
import { useSession } from "@/lib/session";

export function ForgotPasswordScreen() {
  const { config } = useConfig();
  const { signIn } = useSession();
  const navigate = useNavigate();

  const countries = config?.countries.map((entry) => entry.country_code) ?? [
    "JO",
  ];
  const verification = config?.auth.verification ?? "none";

  const [step, setStep] = useState<"details" | "verify">("details");
  const [country, setCountry] = useState<CountryCode>(countries[0] ?? "JO");
  const { dialCode, nationalLength } = usePhoneCountry(country);
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const ready = useMemo(
    () => looksComplete(phone, nationalLength) && password.length >= 8,
    [phone, country, password],
  );

  async function apply(verificationToken: string) {
    setBusy(true);
    setError(null);
    try {
      signIn(
        await resetPassword({
          phone,
          country_code: country,
          verification_token: verificationToken,
          new_password: password,
        }),
      );
      navigate("/", { replace: true });
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر تغيير كلمة المرور",
      );
      setStep("details");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-full flex-col justify-center px-6 py-10 pb-safe pt-safe">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="mx-auto w-full max-w-md space-y-6"
      >
        <Brand subtitle="أثبت رقمك ثم اختر كلمة مرور جديدة" />

        {verification === "none" ? (
          <ErrorNote message="استعادة كلمة المرور غير متاحة حالياً — لا مُحقِّق مُهيأ. راجع الدعم." />
        ) : step === "details" ? (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              setStep("verify");
            }}
            className="space-y-4"
          >
            <PhoneInput
              phone={phone}
              country={country}
              countries={countries}
              onPhoneChange={setPhone}
              onCountryChange={setCountry}
              showCountry={false}
            />

            <Field
              label="كلمة المرور الجديدة"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              hint="ثمانية أحرف على الأقل — وستُغلق كل الجلسات المفتوحة على حسابك"
            />

            <ErrorNote message={error} />

            <Button type="submit" size="lg" disabled={!ready} loading={busy}>
              متابعة
            </Button>
          </form>
        ) : (
          <PhoneVerification
            phone={phone}
            dialCode={dialCode}
            method={verification}
            otpLength={config?.auth.otp_length ?? null}
            requestChallenge={() => startPasswordReset(phone, country)}
            onProven={(token) => void apply(token)}
            onBack={() => setStep("details")}
          />
        )}

        <p className="text-center text-sm text-muted">
          <Link to="/login" className="font-semibold text-ink">
            العودة للدخول
          </Link>
        </p>
      </motion.div>
    </div>
  );
}
