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
 *
 * **وبلغة TAXO 2.0** (A01 · A01b — `design/t2-new/admin/`): لغةُ دخول الكبتن C01 على الحاسوب — النموذجُ في نصف البداية، **ولوحةُ
 * العلامة في النصف الآخر بطاقةٌ تقصّ القضيبين بحافّتها**؛ وتحت ١٠٢٤ القضيبان أعلى الشاشة كما في C01. **وقطعُ النموذج من نظام
 * التصميم المشترك** (`taxo2/Auth.tsx`): الحقلُ ٥٦ بزاويةٍ ١٦، وكلمةُ المرور بعينها، وخاناتُ الرمز الستّ. **والمنطقُ حرفاً كما كان.**
 * **والخطأُ سطرٌ فوق الزرّ** (§٦٢/٢٠): «الاسمُ أو كلمةُ المرور غيرُ صحيحة» لا حقلَ له — والخلفيةُ لا تقول أيَّهما عمداً.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { login, loginWithTotp } from "@/api/endpoints";
import { ErrorNote } from "@/components/ui/Feedback";
import { useConfig } from "@/lib/config";
import { focusField } from "@/lib/validation";
import { useSession } from "@/lib/session";
import {
  AuthBlock,
  AuthCode,
  AuthInput,
  AuthSecret,
  AuthTitle,
  Icon,
  Wordmark,
} from "@/taxo2";

/** الرقم الوطني كما يُكتب أمام بادئةٍ ثابتة — بلا صفرٍ بادئ. */
function toNational(input: string, dialCode: string): string {
  let digits = input.replace(/[^0-9]/g, "");
  if (digits.startsWith("00")) digits = digits.slice(2);
  if (digits.startsWith(dialCode)) digits = digits.slice(dialCode.length);
  return digits.replace(/^0+/, "");
}

// **ولا رسالةَ خمول** (SPEC §60): الدخولُ يبقى حتى يخرج صاحبُه
const REASON_NOTE: Record<string, string> = {
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

  // **رقمٌ إن كان أرقاماً بحتة** (مع فواصلَ شائعة) — وما عداه اسمُ مستخدم
  const looksLikePhone = /^[\d\s+()-]+$/.test(phone.trim()) && phone.trim() !== "";

  function done() {
    navigate("/overview", { replace: true });
  }

  async function submitPassword() {
    setBusy(true);
    setError(null);
    try {
      // **يُميَّز بالمحتوى لا بمفتاحٍ يختاره الداخل**: زرُّ «رقم/اسم» خطوةٌ
      // زائدةٌ على شاشةٍ تُفتح مرةً في اليوم، ومن يخطئ اختيارَه يُردّ بلا سبب
      // مفهوم. وأسماءُ المستخدمين يولّدها `bootstrap_admins` بحروفٍ لاتينيةٍ
      // وشرطاتٍ سفلية، فلا تلتبس برقمٍ أبداً.
      const response = await login(
        looksLikePhone
          ? { phone: `+${dialCode}${toNational(phone, dialCode)}` }
          : { username: phone.trim() },
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
      if (caught instanceof ApiError) {
        setError(caught.message);
        const field = caught.field("field");
        if (field) focusField(field);
      } else {
        setError("تعذّر الدخول — أعد المحاولة");
      }
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
    <div className="ad-login">
      {/* **لوحةُ العلامة** — زينةٌ لا نصّ: قضيبا الـX (الجمرُ والورقُ الخافت) في بطاقةٍ تقصّهما */}
      <div className="ad-login-art" aria-hidden="true">
        <span className="ad-login-bar a" />
        <span className="ad-login-bar b" />
      </div>

      <div className="ad-login-col">
        <div className="ad-login-form">
          <div className="ad-login-brand">
            <Wordmark size={26} />
            <span className="ad-login-tag">لوحة التحكم</span>
          </div>

          <AuthTitle
            title="لوحة تحكم العمليات"
            sub={
              challenge
                ? "خطوةٌ أخيرة: الرمز من تطبيق المصادقة على هاتفك."
                : "إدارة الأسطول والرحلات والمحافظ والعقود في الأردن وليبيا من مكان واحد."
            }
          />

          {challenge ? (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void submitCode();
              }}
            >
              <div className="ad-login-2fa">
                <span className="ad-tile accent">
                  <Icon name="verified_user" />
                </span>
                التحقق الثنائي
              </div>

              {useRecovery ? (
                <AuthBlock label="رمز الاسترداد" htmlFor="recovery">
                  <div className="ad-login-recovery">
                    <AuthInput
                      id="recovery"
                      dir="ltr"
                      autoComplete="one-time-code"
                      autoFocus
                      placeholder="XXXXX-XXXXX"
                      value={recovery}
                      onChange={(event) => setRecovery(event.target.value)}
                    />
                  </div>
                </AuthBlock>
              ) : (
                // **ستُّ خاناتٍ تعرض حقلاً واحداً خلفها** (`AuthCode`): الملءُ الآليُّ ولوحةُ مفاتيح النظام كما كانا،
                // **والتباعدُ ليس زينة**: ستُّ خاناتٍ تُنسخ من شاشة هاتفٍ خانةً خانة، والرقمُ المتلاصق يُخطئ فيه الناسخ
                <AuthBlock label="رمز التحقق">
                  <AuthCode
                    length={6}
                    value={code}
                    onChange={(next) => setCode(next.replace(/[^0-9]/g, ""))}
                  />
                </AuthBlock>
              )}

              {error ? (
                <div className="mt-16">
                  <ErrorNote message={error} />
                </div>
              ) : null}

              <button
                type="submit"
                className="t2-button primary ad-login-submit"
                disabled={
                  busy || (useRecovery ? recovery.length < 8 : code.length < 6)
                }
              >
                {busy ? "…" : "تأكيد الدخول"}
              </button>

              <div className="ad-login-links">
                <button
                  type="button"
                  onClick={() => {
                    setUseRecovery((current) => !current);
                    setError(null);
                  }}
                  className="t2-auth-link"
                >
                  {useRecovery ? "استخدم رمز التطبيق" : "فقدتُ هاتفي — رمز استرداد"}
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setChallenge(null);
                    setError(null);
                  }}
                  className="ad-login-back"
                >
                  رجوع
                </button>
              </div>

              <p className="ad-login-note">
                ولا زرَّ «أعد إرسال الرمز»: الرمزُ يولّده تطبيقُك على هاتفك ولا
                نرسله نحن — يتغيّر وحده كل ثلاثين ثانية.
              </p>
            </form>
          ) : (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void submitPassword();
              }}
            >
              {/* **حقلٌ واحدٌ يقبل الاثنين، ورمزُ الدولة يظهر للرقم وحدَه.**
                  وحسابا الإنتاج يُنشآن بـ`phone=None` (`bootstrap_admins`)، فحقلُ
                  رقمٍ وحدَه يعني أن من يُدير النظامَ لا مكانَ يكتب فيه اسمَه.
                  **والحقلُ نفسُه يبقى مركَّباً حين يظهر الرمز** — موضعُه في
                  الشجرة ثابت، فلا يفقد التركيزَ تحت الإصبع. */}
              <AuthBlock label="اسم المستخدم أو رقم الهاتف" htmlFor="identity">
                <div className={looksLikePhone ? "t2-auth-field phone" : "t2-auth-field"}>
                  {looksLikePhone ? (
                    <>
                      <span className="t2-auth-dial">+{dialCode || "…"}</span>
                      <span className="t2-auth-sep" aria-hidden="true" />
                    </>
                  ) : null}
                  <input
                    id="identity"
                    dir="ltr"
                    autoComplete="username"
                    // **«أو» معزولةٌ باتّجاهها** — في حقلٍ من اليسار كانت تُقرأ «admin_name 7 أوXXXXXXXX»
                    placeholder={"admin_name  \u2067أو\u2069  7XXXXXXXX"}
                    value={phone}
                    onChange={(event) => setPhone(event.target.value)}
                  />
                </div>
              </AuthBlock>

              <AuthBlock label="كلمة المرور" htmlFor="password">
                <AuthSecret
                  id="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </AuthBlock>

              {(error ?? (lastReason ? REASON_NOTE[lastReason] : null)) ? (
                <div className="mt-16">
                  <ErrorNote
                    message={
                      error ?? (lastReason ? REASON_NOTE[lastReason] : null) ?? null
                    }
                  />
                </div>
              ) : null}

              <button
                type="submit"
                className="t2-button primary ad-login-submit"
                disabled={busy || !phone || !password}
              >
                {busy ? "…" : "متابعة"}
              </button>
            </form>
          )}

          <p className="ad-login-foot">
            الدخول مقيّد بالمستخدمين المصرّح لهم · كل إجراء يُسجَّل في سجل التدقيق
          </p>
        </div>
      </div>
    </div>
  );
}
