/** التسجيل — الخطوة ١ من ٣ ثم إثباتُ الرقم (SPEC القسم 12/1).
 *
 * ترتيبُ التصميم مطابقٌ للمواصفات حرفياً وليس صدفة: **الرقم يُثبت قبل أن
 * ينتظر المراجعة** — رقمُ الكبتن هو ما تصل عليه حوالات كليك (القسم 6/9)،
 * فالإثبات شرطُ الاعتماد لا تفصيلٌ يُؤجَّل.
 *
 * والإثبات وكلمةُ المرور يُرسلان في **طلبٍ واحد** (`POST /auth/register`):
 * حسابٌ يُفتح بالإثبات وحده حسابٌ بلا كلمة مرور، وإثباتٌ يفتح جلسةً قبل أن
 * تُكتب الكلمة يترك للمهاجم شيئاً إن انقطع الطلب بعده (القسم 15/أ).
 *
 * الشكل من `design/DESIGN.md` §5.3: «الخطوة ١ من ٣» 12px، العنوان 22/700،
 * الحقول بفجوة 12، ثم زرٌّ أساسي وملاحظةٌ 11.5 بسطرٍ 1.7.
 */

import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { registerAccount, startSignupChallenge } from "@/api/endpoints";
import type { CountryCode, OtpChannel } from "@/api/types";
import { PhoneField } from "@/components/PhoneField";
import { PhoneVerification } from "@/components/PhoneVerification";
import { AuthScreen } from "@/components/ui/AuthScreen";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { Field } from "@/components/ui/Field";
import { useConfig, usePhoneCountry } from "@/lib/config";
import { looksComplete, toE164 } from "@/lib/phone";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

const COUNTRY_LABEL: Record<CountryCode, string> = {
  JO: "الأردن",
  LY: "ليبيا",
};

export function RegisterScreen() {
  const navigate = useNavigate();
  const { config } = useConfig();
  const { signIn } = useSession();

  const countries = config?.countries.map((entry) => entry.country_code) ?? [];
  const [country, setCountry] = useState<CountryCode>(
    config?.default_country_code ?? "JO",
  );
  const { dialCode, nationalLength } = usePhoneCountry(country);

  const [step, setStep] = useState<"details" | "verify">("details");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // المُحقِّقُ يتبع الدولةَ المختارة لا الافتراضية (12-هـ)
  const method =
    config?.countries.find((entry) => entry.country_code === country)
      ?.verification ??
    config?.auth.verification ??
    "none";
  const e164 = toE164(phone, dialCode);

  // **والقناةُ تُمرَّر لا تُهمَل**: زرُّ الارتداد يعطي القناةَ التالية، فمُغلَّفٌ
  // يتجاهلها يعيد الإرسال في القناة الفاشلة نفسها — زرٌّ يعمل ولا يفعل شيئاً
  const requestChallenge = useCallback(
    (channel?: OtpChannel) => startSignupChallenge(e164, country, channel),
    [e164, country],
  );

  const complete =
    name.trim().length >= 2 &&
    looksComplete(phone, nationalLength) &&
    password.length >= 8 &&
    confirmation.length >= 8;

  function next() {
    setError(null);
    if (password !== confirmation) {
      setError("كلمتا المرور غير متطابقتين");
      return;
    }
    // مُحقِّقٌ مطفأ للطوارئ: الخلفية تقبل التسجيل بلا إثبات وتَسِم الحساب
    // (SPEC القسم 4)، فلا خطوةَ إثباتٍ تُعرض على أحد
    if (method === "none") {
      void create();
      return;
    }
    setStep("verify");
  }

  async function create(verificationToken?: string) {
    setBusy(true);
    setError(null);
    try {
      signIn(
        await registerAccount({
          phone: e164,
          name: name.trim(),
          password,
          country_code: country,
          verification_token: verificationToken,
        }),
      );
      navigate("/register/documents", { replace: true });
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر إنشاء الحساب",
      );
      // إثباتٌ استُهلك لا يُعاد استعماله
      if (caught instanceof ApiError && caught.status === 401)
        setStep("details");
    } finally {
      setBusy(false);
    }
  }

  if (step === "verify") {
    return (
      <AuthScreen onBack={() => setStep("details")}>
        <PhoneVerification
          phone={e164}
          method={method}
          otpLength={config?.auth.otp_length ?? null}
          title="تحقق من رقمك"
          subtitle={`أرسلنا رمز تحقق إلى ${e164} — التحقق من الرقم مرة واحدة عند التسجيل.`}
          requestChallenge={requestChallenge}
          onProven={(token) => void create(token)}
          submitting={busy}
        />
        <ErrorNote message={error} />
      </AuthScreen>
    );
  }

  return (
    <AuthScreen onBack={() => navigate("/login")} className="px-26">
      <div className="mt-20 text-12 text-muted">الخطوة ١ من ٣</div>
      <h1 className="mb-4 text-22 font-bold text-ink">إنشاء حساب كبتن</h1>
      <p className="mb-20 text-12.5 leading-snug text-muted">
        الرقم هو مُعرّف دخولك، ويُخزَّن بصيغة دولية.
      </p>

      <form
        className="flex flex-col gap-12"
        onSubmit={(event) => {
          event.preventDefault();
          next();
        }}
      >
        <Field
          label="الاسم الكامل"
          name="name"
          autoComplete="name"
          placeholder="مثال: أبو محمد الزعبي"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />

        <PhoneField value={phone} onChange={setPhone} country={country} />

        {/* منتقي الدولة هنا وحده — التصميم يضعه في التسجيل لا في الدخول،
            وهو الموضع الذي تُعرف فيه الدولة أصلاً */}
        <div>
          <span className="label">الدولة</span>
          <div className="flex gap-8">
            {countries.map((code) => (
              <button
                key={code}
                type="button"
                onClick={() => setCountry(code)}
                className={cn(
                  "pressable flex-1 rounded-13 border p-12 text-13.5 font-semibold",
                  code === country
                    ? "border-ink bg-surface-2 text-ink"
                    : "border-line text-ink",
                )}
              >
                {COUNTRY_LABEL[code]}
              </button>
            ))}
          </div>
        </div>

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
          disabled={!complete}
        >
          التالي
        </Button>
      </form>

      <p className="mt-14 text-center text-11.5 leading-note text-muted">
        بالمتابعة أنت توافق على شروط الاستخدام. الرقم يُثبت بالتحقق مرة واحدة.
      </p>
    </AuthScreen>
  );
}
