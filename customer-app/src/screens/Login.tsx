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
import { useConfig } from "@/lib/config";
import { usePhoneCountry } from "@/lib/config";
import { looksComplete } from "@/lib/phone";
import { useSession } from "@/lib/session";
import { Brand } from "@/components/Brand";

export function LoginScreen() {
  const { config } = useConfig();
  const { signIn } = useSession();
  const navigate = useNavigate();

  const countries = config?.countries.map((entry) => entry.country_code) ?? [
    "JO",
  ];
  // لا منتقيَ دولةٍ هنا كما في التصميم: البادئة ثابتةٌ من `default_country_code`
  const { country, nationalLength } = usePhoneCountry();
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
      signIn(await login(phone, password, country));
      navigate("/", { replace: true });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الدخول");
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
        <Brand subtitle="أهلاً بعودتك — سجّل الدخول لتطلب رحلتك" />

        <form onSubmit={submit} className="space-y-4">
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
                className="text-muted transition hover:text-ink"
              >
                {visible ? (
                  <EyeOff className="size-5" />
                ) : (
                  <Eye className="size-5" />
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

        <div className="flex items-center justify-between text-sm">
          <Link to="/forgot-password" className="text-muted hover:text-ink">
            نسيت كلمة المرور؟
          </Link>
          <Link to="/register" className="font-semibold text-ink">
            حساب جديد
          </Link>
        </div>
      </motion.div>
    </div>
  );
}
