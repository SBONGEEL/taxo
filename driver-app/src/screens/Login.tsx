/** الدخول — SPEC القسم 12/1، وشكلُه من `design/DESIGN.md` §5.3.
 *
 * **كلمةُ مرورٍ دائماً ولا شيء غيرها.** نموذجُ التصميم ينقل بعد «دخول» إلى
 * شاشة رمز التحقق، وذاك سهوٌ فيه لا نيّةُ تصميم: «الدخول كلمة مرور دائماً،
 * والـOTP تحقُّقٌ لا دخول» (SPEC القسم 11/1، وقرارُ `DESIGN-DECISIONS.md`
 * بند 1) — ونصوصُ التصميم نفسها تقول ذلك: «التحقق مرة واحدة عند التسجيل».
 *
 * ولا منتقيَ دولةٍ هنا كما في التصميم: البادئةُ ثابتةٌ أمام الحقل وقيمتُها من
 * `GET /config`، والرقم الوطني وحده يُكتب (`PhoneField`).
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { login } from "@/api/endpoints";
import { PhoneField } from "@/components/PhoneField";
import { AuthScreen } from "@/components/ui/AuthScreen";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { Field } from "@/components/ui/Field";
import { usePhoneCountry } from "@/lib/config";
import { looksComplete, toE164 } from "@/lib/phone";
import { useSession } from "@/lib/session";

export function LoginScreen() {
  const navigate = useNavigate();
  const { signIn } = useSession();
  const { country, dialCode, nationalLength } = usePhoneCountry();

  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      // يُرسل E.164 ومعه الدولة صراحةً: لا استنتاجَ ولا التباس
      const response = await login(toE164(phone, dialCode), password, country);
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
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر تسجيل الدخول",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthScreen>
      {/* الكتلة العلوية: `margin-top:46px; margin-bottom:38px` في التصميم */}
      <div className="mb-38 mt-46">
        <div className="text-38 font-bold tracking-brand text-brand">TAXO</div>
        <div className="mt-4 text-14 text-muted">تطبيق الكبتن</div>
      </div>

      <form
        className="flex flex-col gap-12"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <PhoneField value={phone} onChange={setPhone} />
        <Field
          label="كلمة المرور"
          name="password"
          type="password"
          autoComplete="current-password"
          placeholder="••••••••"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <button
          type="button"
          onClick={() => navigate("/forgot-password")}
          className="cursor-pointer text-end text-12 text-muted underline"
        >
          نسيت كلمة المرور؟
        </button>

        <ErrorNote message={error} />

        <Button
          type="submit"
          className="mt-24"
          loading={busy}
          disabled={!looksComplete(phone, nationalLength) || !password}
        >
          دخول
        </Button>
      </form>

      <div className="mt-auto text-center text-13 text-muted">
        كبتن جديد؟{" "}
        <button
          type="button"
          onClick={() => navigate("/register")}
          className="cursor-pointer font-semibold text-ink underline"
        >
          سجّل الآن
        </button>
      </div>
    </AuthScreen>
  );
}
