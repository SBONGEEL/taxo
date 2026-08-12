/** دخول اللوحة — `DESIGN.md` §5.4، وSPEC القسم 13/8 و§14.1.
 *
 * **برقم الهاتف لا بالبريد.** النموذج يكتب «استخدم بريد العمل الخاص بك»، ولا
 * عمودَ بريدٍ في `users` أصلاً: الهوية في هذا النظام رقمُ هاتفٍ بصيغة E.164
 * لكل الأدوار، والدخولُ كلمةُ مرورٍ دائماً (`DESIGN-DECISIONS.md` بند 3).
 *
 * **والتحقّقُ الثنائي مبنيٌّ الآن** (المرحلة 12-د) فصارت الشاشةُ خطوتين، وهي
 * الشاشةُ التي رسمها التصميم في البند 26. وجملةُ «جلسة تنتهي بعد ٣٠ دقيقة
 * خمول» ما زالت **لا تُكتب هنا**: المهلةُ صارت مبنيّةً لكنها **رقمٌ يعدّله
 * المشرف** في شاشة الأمان (5–60 دقيقة)، فجملةٌ تذكر ثلاثين تكذب أوّلَ مرةٍ
 * يُغيَّر الرقم — والوعدُ الكاذب في نصٍّ أمنيّ أسوأ من غيابه.
 *
 * **ولا تُعرض الخطوةُ الثانية إلا بعد كلمة مرورٍ صحيحة**: الخلفية لا تقول إن
 * للحساب عاملاً ثانياً قبل ذلك، فلا تسأل هذه الشاشةُ عنه ولا تُبدي وجودَه.
 */

import { ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { login, loginWithTotp } from "@/api/endpoints";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { ErrorNote } from "@/components/ui/Feedback";
import { useConfig } from "@/lib/config";
import { useSession } from "@/lib/session";

/** الرقم الوطني كما يُكتب أمام بادئةٍ ثابتة — بلا صفرٍ بادئ. */
function toNational(input: string, dialCode: string): string {
  let digits = input.replace(/[^0-9]/g, "");
  if (digits.startsWith("00")) digits = digits.slice(2);
  if (digits.startsWith(dialCode)) digits = digits.slice(dialCode.length);
  return digits.replace(/^0+/, "");
}

const REASON_NOTE: Record<string, string> = {
  idle: "انتهت جلستك بعد فترة خمول — أعد الدخول للمتابعة.",
  expired: "انتهت صلاحية جلستك — أعد الدخول للمتابعة.",
};

export function LoginScreen() {
  const navigate = useNavigate();
  const { signIn, lastReason } = useSession();
  const { config } = useConfig();

  const country = config?.countries.find(
    (entry) => entry.country_code === config.default_country_code,
  );
  // `dial_code` يصل بلا «+» (`core/phone.py`)، والعلامةُ تُرسم ولا تُخزَّن
  const dialCode = country?.dial_code ?? "";

  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // الخطوةُ الثانية: تحدٍّ من الخلفية عمرُه خمسُ دقائق ويُستهلَك مرةً واحدة
  const [challenge, setChallenge] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [recovery, setRecovery] = useState("");
  const [useRecovery, setUseRecovery] = useState(false);

  function done() {
    navigate("/overview", { replace: true });
  }

  async function submitPassword() {
    setBusy(true);
    setError(null);
    try {
      const response = await login(
        `+${dialCode}${toNational(phone, dialCode)}`,
        password,
        config?.default_country_code,
      );
      if (response.totp_required && response.challenge_token) {
        setChallenge(response.challenge_token);
        // كلمةُ المرور لا تبقى في الذاكرة بعد أن أدّت دورَها
        setPassword("");
        return;
      }
      if (!response.tokens || !response.user) throw new Error("bad response");
      signIn({ user: response.user, tokens: response.tokens });
      done();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر الدخول");
    } finally {
      setBusy(false);
    }
  }

  async function submitCode() {
    if (!challenge) return;
    setBusy(true);
    setError(null);
    try {
      const response = await loginWithTotp(
        challenge,
        useRecovery ? { recovery_code: recovery } : { code },
      );
      signIn(response);
      done();
    } catch (caught) {
      const failure =
        caught instanceof ApiError ? caught : new ApiError(0, "x", "تعذّر الدخول");
      setError(failure.message);
      // تحدٍّ انتهى أو أُحرق بالمحاولات: الرجوعُ إلى كلمة المرور هو المخرج،
      // وإبقاءُ حقلِ رمزٍ لتحدٍّ ميتٍ يجعل المستخدم يعيد المحاولة إلى ما لا نهاية
      if (failure.code === "invalid_token" || failure.status === 429) {
        setChallenge(null);
        setCode("");
        setRecovery("");
        setUseRecovery(false);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg px-24">
      <div className="w-modal max-w-full">
        <div className="mb-24 text-center">
          <div className="text-30 font-bold tracking-wordmark text-ink">
            TAXO
          </div>
          <h1 className="mt-10 text-21 font-bold text-ink">
            لوحة تحكم العمليات
          </h1>
          <p className="mt-6 text-12.5 leading-note text-muted">
            {challenge
              ? "خطوةٌ أخيرة: الرمز من تطبيق المصادقة على هاتفك."
              : "إدارة الأسطول والرحلات والمحافظ والعقود في الأردن وليبيا من مكان واحد."}
          </p>
        </div>

        {challenge ? (
          <form
            className="rounded-18 border border-line bg-surface p-24"
            onSubmit={(event) => {
              event.preventDefault();
              void submitCode();
            }}
          >
            <div className="mb-16 flex items-center gap-9 text-13 font-semibold text-ink">
              <ShieldCheck size={16} />
              التحقق الثنائي
            </div>

            {useRecovery ? (
              <Field
                label="رمز الاسترداد"
                id="recovery"
                dir="ltr"
                autoComplete="one-time-code"
                autoFocus
                placeholder="XXXXX-XXXXX"
                value={recovery}
                onChange={(event) => setRecovery(event.target.value)}
              />
            ) : (
              <div>
                <label className="label" htmlFor="totp">
                  رمز التحقق
                </label>
                <input
                  id="totp"
                  dir="ltr"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  autoFocus
                  maxLength={6}
                  placeholder="······"
                  // `DESIGN.md` §2.3 حرفاً بحرف لحقل 2FA في اللوحة: تباعد
                  // `.42em` (`tracking-code` في السلّم)، مقاس 26، حشوة 15،
                  // توسيط، وزن 700. والتباعدُ ليس زينة: ستُّ خاناتٍ تُنسخ من
                  // شاشة هاتفٍ خانةً خانة، والرقمُ المتلاصق يُخطئ فيه الناسخ
                  className="fld p-15 text-center text-26 font-bold tracking-code"
                  value={code}
                  onChange={(event) =>
                    setCode(event.target.value.replace(/[^0-9]/g, ""))
                  }
                />
              </div>
            )}

            <div className="mt-16">
              <ErrorNote message={error} />
            </div>

            <Button
              className="mt-16"
              type="submit"
              loading={busy}
              disabled={useRecovery ? recovery.length < 8 : code.length < 6}
            >
              تأكيد الدخول
            </Button>

            <div className="mt-14 flex items-center justify-between gap-10">
              <button
                type="button"
                onClick={() => {
                  setUseRecovery((current) => !current);
                  setError(null);
                }}
                className="text-11.5 font-semibold text-ink underline"
              >
                {useRecovery ? "استخدم رمز التطبيق" : "فقدتُ هاتفي — رمز استرداد"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setChallenge(null);
                  setError(null);
                }}
                className="text-11.5 text-muted underline"
              >
                رجوع
              </button>
            </div>

            <p className="mt-14 text-11.5 leading-note text-muted">
              ولا زرَّ «أعد إرسال الرمز»: الرمزُ يولّده تطبيقُك على هاتفك ولا
              نرسله نحن — يتغيّر وحده كل ثلاثين ثانية.
            </p>
          </form>
        ) : (
          <form
            className="rounded-18 border border-line bg-surface p-24"
            onSubmit={(event) => {
              event.preventDefault();
              void submitPassword();
            }}
          >
            <label className="label" htmlFor="phone">
              رقم الهاتف
            </label>
            <div className="mb-16 flex items-stretch gap-8">
              <span
                dir="ltr"
                className="flex items-center rounded-13 border border-line bg-surface-2 px-14 text-14.5 text-muted"
              >
                +{dialCode || "…"}
              </span>
              <input
                id="phone"
                dir="ltr"
                inputMode="tel"
                autoComplete="username"
                className="fld"
                placeholder="7XXXXXXXX"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
              />
            </div>

            <Field
              label="كلمة المرور"
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />

            <div className="mt-16">
              <ErrorNote
                message={
                  error ?? (lastReason ? REASON_NOTE[lastReason] : null) ?? null
                }
              />
            </div>

            <Button
              className="mt-16"
              type="submit"
              loading={busy}
              disabled={!phone || !password}
            >
              متابعة
            </Button>
          </form>
        )}

        <p className="mt-16 text-center text-11.5 leading-note text-muted">
          الدخول مقيّد بالمستخدمين المصرّح لهم · كل إجراء يُسجَّل في سجل التدقيق
        </p>
      </div>
    </div>
  );
}
