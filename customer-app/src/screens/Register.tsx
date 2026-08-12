/** التسجيل: **إثباتُ الرقم مرةً، ثم كلمةُ المرور في نفس الطلب** (القسم 11.1).
 *
 * الترتيب في الشاشة يتبع الترتيب في الخلفية: تُجمع البيانات كلها أولاً، ثم
 * يقع الإثبات، ثم يُرسل `POST /auth/register` **مرةً واحدة** حاملاً الإثبات
 * وكلمة المرور معاً — فلا يبقى حسابٌ نصفُ مُنشأ لرمزٍ لم يُقبل.
 *
 * و`verification_token` حقلٌ مستقل عن `password` عمداً: الإثبات والكلمة
 * يسافران في نفس الطلب، وحقلٌ واحد لا يحمل معنيين (SPEC القسم 15/أ).
 */

import { motion } from "framer-motion";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { register, startChallenge } from "@/api/endpoints";
import type { CountryCode } from "@/api/types";
import { Brand } from "@/components/Brand";
import { PhoneInput } from "@/components/PhoneInput";
import { PhoneVerification } from "@/components/PhoneVerification";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { Field } from "@/components/ui/Field";
import { useConfig, useFeature, usePhoneCountry } from "@/lib/config";
import { looksComplete } from "@/lib/phone";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

export function RegisterScreen() {
  const { config } = useConfig();
  const { signIn } = useSession();
  const navigate = useNavigate();

  const countries = config?.countries.map((entry) => entry.country_code) ?? [
    "JO",
  ];
  const [step, setStep] = useState<"details" | "verify">("details");
  // الدولةُ الافتراضية من `/config` لا أولُ عنصرٍ في القائمة: ترتيبُ التعداد
  // يجعل الأولَ ليبيا، فكانت شاشةُ التسجيل تفترض سوقاً وشاشةُ الدخول تفترض
  // غيره — و`default_country_code` نُشر لهذا بعينه (SPEC القسم 4)
  const [country, setCountry] = useState<CountryCode>(
    config?.default_country_code ?? countries[0] ?? "JO",
  );
  // المُحقِّقُ يتبع الدولةَ المختارة لا الافتراضية (12-هـ)
  const verification =
    config?.countries.find((entry) => entry.country_code === country)
      ?.verification ??
    config?.auth.verification ??
    "none";

  const { dialCode, nationalLength } = usePhoneCountry(country);
  // الدولةُ تُختار في هذه الشاشة، فالمفتاح يُقرأ منها لا من حسابٍ لا وجود له
  const womenService = useFeature(country, "women_service_enabled");
  const [phone, setPhone] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [gender, setGender] = useState<"male" | "female" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const ready = useMemo(
    () =>
      looksComplete(phone, nationalLength) &&
      name.trim().length >= 2 &&
      password.length >= 8,
    [phone, country, name, password],
  );

  async function create(verificationToken?: string) {
    setBusy(true);
    setError(null);
    try {
      signIn(
        await register({
          phone,
          name: name.trim(),
          password,
          country_code: country,
          verification_token: verificationToken,
          gender: gender ?? undefined,
        }),
      );
      navigate("/", { replace: true });
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر إنشاء الحساب",
      );
      setStep("details");
    } finally {
      setBusy(false);
    }
  }

  function next(event: React.FormEvent) {
    event.preventDefault();
    // لا مُحقِّق مُهيأ: الحساب يُنشأ غير محقق ويبقى موسوماً حتى يُثبت رقمه
    // (SPEC القسم 4) — وهو ما تقرره الخلفية لا الواجهة
    if (verification === "none") {
      void create();
      return;
    }
    setStep("verify");
  }

  return (
    <div className="flex min-h-full flex-col justify-center px-24 py-40 pb-safe pt-safe">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="mx-auto w-full max-w-md space-y-24"
      >
        <Brand subtitle="أنشئ حسابك في دقيقة" />

        {step === "details" ? (
          <form onSubmit={next} className="space-y-16">
            <Field
              label="الاسم"
              autoComplete="name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="اسمك كما يظهر للكبتن"
            />

            <PhoneInput
              phone={phone}
              country={country}
              countries={countries}
              onPhoneChange={setPhone}
              onCountryChange={setCountry}
            />

            {/* إقرارٌ ذاتيّ بلا وثيقة (المرحلة 10-ج) — **اختياريّ**: من تركه
                لا يُخمَّن عنه، ولا تصله طلبات مجنّسة ولا تُعرض عليه.
                ويظهر حيث الخدمة مفتوحة في الدولة المختارة وحدها */}
            {womenService ? (
              <div>
                <div className="mb-6 text-14 text-muted">الجنس</div>
                <div className="grid grid-cols-2 gap-8">
                  {(
                    [
                      { value: "female", label: "أنثى" },
                      { value: "male", label: "ذكر" },
                    ] as const
                  ).map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() =>
                        setGender(gender === option.value ? null : option.value)
                      }
                      className={cn(
                        "rounded-12 border p-12 text-center font-medium transition",
                        gender === option.value
                          ? "border-brand bg-brand text-brand-ink"
                          : "border-line bg-surface text-muted hover:bg-surface-2",
                      )}
                    >
                      {option.label}
                    </button>
                  ))}
                </div>
                <p className="mt-8 text-12 leading-relaxed text-muted">
                  إقرارٌ ذاتيّ — لا نطلب وثيقة. يُستعمل لمطابقة تفضيلات الرحلات
                  فقط، ولا يظهر لأي مستخدم آخر.
                </p>
              </div>
            ) : null}

            <Field
              label="كلمة المرور"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              hint="ثمانية أحرف على الأقل"
            />

            <ErrorNote message={error} />

            <Button type="submit" size="lg" disabled={!ready} loading={busy}>
              {verification === "none" ? "إنشاء الحساب" : "متابعة"}
            </Button>
          </form>
        ) : (
          <PhoneVerification
            phone={phone}
            dialCode={dialCode}
            method={verification}
            otpLength={config?.auth.otp_length ?? null}
            requestChallenge={(channel) =>
              startChallenge(phone, country, channel)
            }
            onProven={(token) => void create(token)}
            onBack={() => setStep("details")}
          />
        )}

        <p className="text-center text-14 text-muted">
          لديك حساب؟{" "}
          <Link to="/login" className="font-semibold text-ink">
            سجّل الدخول
          </Link>
        </p>
      </motion.div>
    </div>
  );
}
