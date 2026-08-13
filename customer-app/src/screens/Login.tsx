/** الدخول — **كلمة مرور دائماً ولكل المستخدمين** (SPEC القسم 11.1).
 *
 * لا شرطَ هنا على المُحقِّق: OTP تحقّقٌ لا دخول، وشاشةُ الدخول واحدةٌ مهما
 * كانت العقود المفعّلة (SPEC القسم 2/15-أ).
 */

import { motion } from "framer-motion";
import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { login } from "@/api/endpoints";
import { PhoneInput } from "@/components/PhoneInput";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { Field } from "@/components/ui/Field";
import { useAuthCountry, usePhoneCountry } from "@/lib/config";
import { looksComplete } from "@/lib/phone";
import { useSession } from "@/lib/session";
import { Brand } from "@/components/Brand";

export function LoginScreen() {
  const { signIn } = useSession();
  const navigate = useNavigate();

  // **مصدرٌ واحدٌ لدولة شاشات المصادقة** (`useAuthCountry`) — ولا منتقيَ هنا
  // كما في التصميم: البادئة ثابتةٌ من `default_country_code`
  const { country, countries } = useAuthCountry();
  const { nationalLength } = usePhoneCountry(country);
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [visible, setVisible] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const response = await login(phone, password, country);
      // **جوابان لا جواب**: حسابٌ يحمل عاملاً ثانياً يعود بلا توكن (12-د).
      // ولا يُسجَّل عاملٌ إلا لحسابات اللوحة (`SecuritySelfUser`)، فهذا الجواب
      // هنا يعني حساب طاقمٍ يحاول الدخول من تطبيقٍ ليس له — ويُقال له ذلك
      // صراحةً بدل أن يُحفظ توكنٌ غائبٌ فتُفتح جلسةٌ فارغة
      if (response.totp_required || !response.user || !response.tokens) {
        setError(
          "هذا الحساب يحتاج تحقّقاً ثنائياً — وهو لحسابات لوحة الإدارة، فادخل من اللوحة.",
        );
        return;
      }
      signIn({ user: response.user, tokens: response.tokens });
      navigate("/", { replace: true });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الدخول");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-full flex-col px-24 py-40 pb-safe pt-safe">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        className="mx-auto mt-auto w-full max-w-md space-y-24"
      >
        <Brand subtitle="اطلب تاكسي في ثوانٍ" />

        <form onSubmit={submit} className="space-y-16">
          <PhoneInput
            phone={phone}
            country={country}
            countries={countries}
            onPhoneChange={setPhone}
            onCountryChange={() => undefined}
            disabled={busy}
            showCountry={false}
          />

          <Field
            label="كلمة المرور"
            type={visible ? "text" : "password"}
            autoComplete="current-password"
            value={password}
            disabled={busy}
            onChange={(event) => setPassword(event.target.value)}
            suffix={
              <button
                type="button"
                onClick={() => setVisible((value) => !value)}
                aria-label={visible ? "إخفاء كلمة المرور" : "إظهار كلمة المرور"}
                className="pressable text-muted transition hover:text-ink"
              >
                {visible ? (
                  <EyeOff className="size-20" />
                ) : (
                  <Eye className="size-20" />
                )}
              </button>
            }
          />

          <ErrorNote message={error} />

          <Button
            type="submit"
            size="lg"
            loading={busy}
            disabled={
              !looksComplete(phone, nationalLength) || password.length < 1
            }
          >
            دخول
          </Button>
        </form>

        <div className="text-14">
          <Link to="/forgot-password" className="pressable text-muted hover:text-ink">
            نسيت كلمة المرور؟
          </Link>
        </div>
      </motion.div>

      {/* **مثبَّتٌ أسفل الشاشة** كما في التصميم (`margin-top:auto`): سطرٌ
          يُقرأ بعد أن يفشل الدخول أو قبل أن يُحاوَل، فمكانُه الطرفُ لا وسطُ
          النموذج — ولا يزاحم الزرَّ الأساسي */}
      <p className="mt-auto pt-24 text-center text-13 text-muted">
        ليس لديك حساب؟{" "}
        <Link to="/register" className="pressable font-semibold text-ink underline">
          سجّل الآن
        </Link>
      </p>
    </div>
  );
}
