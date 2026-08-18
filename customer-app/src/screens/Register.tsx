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
import { ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { register, startChallenge } from "@/api/endpoints";
import { Brand } from "@/components/Brand";
import { PhoneInput } from "@/components/PhoneInput";
import { PhoneVerification } from "@/components/PhoneVerification";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { Field } from "@/components/ui/Field";
import {
  useAuthCountry,
  useConfig,
  useFeature,
  usePhoneCountry,
} from "@/lib/config";
import { COUNTRY_LABEL, looksComplete } from "@/lib/phone";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";
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
  const { config } = useConfig();
  const { signIn } = useSession();
  const navigate = useNavigate();

  const [step, setStep] = useState<"details" | "verify">("details");
  // **الدولةُ من `useAuthCountry`** — بيتٌ واحدٌ لشاشات المصادقة الثلاث.
  // **ولا نسخةَ محليةً بعد اليوم** (البند ١٠): الاختيارُ صار محفوظاً على
  // الجهاز داخل الخطّاف نفسِه، ونسخةٌ محليةٌ هنا تعني اختياراً يُنسى بين
  // «التسجيل» و«الدخول» — وهو ما يجعل صاحبَ الرقم الليبيّ يعيد اختيارَه
  // في كل شاشة
  const { country, countries, setCountry } = useAuthCountry();
  // المُحقِّقُ **وطولُ رمزه** يتبعان الدولةَ المختارة لا الافتراضية (12-هـ)
  const entry = config?.countries.find(
    (item) => item.country_code === country,
  );
  const verification =
    entry?.verification ?? config?.auth.verification ?? "none";

  const { dialCode, nationalLength } = usePhoneCountry(country);
  // الدولةُ تُختار في هذه الشاشة، فالمفتاح يُقرأ منها لا من حسابٍ لا وجود له
  const womenService = useFeature(country, "women_service_enabled");
  const [phone, setPhone] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [gender, setGender] = useState<"male" | "female" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // **والتأكيدُ شرطٌ في الواجهة وحدها** (التصميم): الخلفيةُ تأخذ كلمةً واحدة،
  // وما يحرسه الحقلُ الثاني خطأُ طباعةٍ في كلمةٍ **لا تُعرض** — ومن أخطأ فيها
  // لا يكتشف ذلك إلا حين يعجز عن الدخول، ثم يمرّ بمسار استعادةٍ كامل
  const ready = useMemo(
    () =>
      looksComplete(phone, nationalLength) &&
      name.trim().length >= 2 &&
      passwordsReady(password, confirm),
    [phone, nationalLength, name, password, confirm],
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
      if (caught instanceof ApiError) {
        const field = caught.field("field");
        setError(caught.message);
        if (field) focusField(field);
      } else {
        setError("تعذّر الاتصال بالخادم — أعد المحاولة");
      }
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
        {/* سهمُ الرجوع أعلى الشاشة كما في التصميم — و`ChevronRight` لا
            `ChevronLeft`: «رجوع» في واجهةٍ عربية يشير يميناً (`Screen.tsx`) */}
        <button
          type="button"
          onClick={() => navigate("/login")}
          aria-label="رجوع"
          className="pressable -ms-8 -mt-8 w-fit rounded-full p-8 text-muted transition hover:bg-surface-2"
        >
          <ChevronRight className="size-20" />
        </button>

        <Brand subtitle="رقمك هو مُعرّف دخولك، ويُخزَّن بصيغة دولية." />

        {step === "details" ? (
          <form onSubmit={next} className="space-y-16">
            <Field
              label="الاسم"
              autoComplete="name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="اسمك كما يظهر للكبتن"
            />

            {/* **زرّان لا قائمة** (التصميم): سوقان اثنان لا أكثر، والقائمةُ
                المنسدلة تُخفي أحدَهما خلف ضغطة. ولا يظهر الصفُّ بسوقٍ واحد */}
            {countries.length > 1 ? (
              <div>
                <div className="mb-6 text-14 text-muted">الدولة</div>
                <div className="flex gap-8">
                  {countries.map((code) => (
                    <button
                      key={code}
                      type="button"
                      onClick={() => setCountry(code)}
                      className={cn(
                        "pressable flex-1 rounded-13 border p-12 text-center text-13.5 font-semibold transition",
                        code === country
                          ? "border-brand bg-brand text-brand-ink"
                          : "border-line bg-surface text-muted hover:bg-surface-2",
                      )}
                    >
                      {COUNTRY_LABEL[code]}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            <PhoneInput
              phone={phone}
              country={country}
              countries={countries}
              onPhoneChange={setPhone}
              onCountryChange={setCountry}
              showCountry={countries.length > 1}
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
                        "pressable rounded-12 border p-12 text-center font-medium transition",
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
              error={passwordError(password) ?? undefined}
            />
          <FieldConditions rule={passwordRule()} value={password} />

            <Field
              label="تأكيد كلمة المرور"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
              error={confirmError(password, confirm) ?? undefined}
            />

            <ErrorNote message={error} />

            <Button type="submit" size="lg" disabled={!ready} loading={busy}>
              {verification === "none" ? "إنشاء الحساب" : "متابعة"}
            </Button>

            {/* **تحت الزرِّ لا فوقه** كما في التصميم: تُقرأ عند لحظة الالتزام،
                وسطرٌ فوق الزرِّ يُقرأ قبل أن يُملأ النموذج فيُنسى */}
            <p className="text-center text-11.5 leading-note text-muted">
              بالمتابعة أنت توافق على شروط الاستخدام. الرقم يُثبت بالتحقق مرة
              واحدة.
            </p>
          </form>
        ) : (
          <PhoneVerification
            phone={phone}
            dialCode={dialCode}
            method={verification}
            otpLength={entry?.otp_length ?? null}
            requestChallenge={(channel) =>
              startChallenge(phone, country, channel)
            }
            onProven={(token) => void create(token)}
            onBack={() => setStep("details")}
            onLeave={() => navigate("/login")}
          />
        )}

        <p className="text-center text-14 text-muted">
          لديك حساب؟{" "}
          <Link to="/login" className="pressable font-semibold text-ink">
            سجّل الدخول
          </Link>
        </p>
      </motion.div>
    </div>
  );
}
