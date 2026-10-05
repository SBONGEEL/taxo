/** التسجيل — **الخطوةُ الأولى «الحساب» ثمّ إثباتُ الرقم** (SPEC القسم 12/1)، **بلغة C02** (Claude Design «TAXO 2.0 - Captain»):
 * رأسُ «إنشاء حساب كبتن» بخطواته الثلاث، وحقولُ C01. **و«الحساب» لم تُرسم في اللوحة** — فرُسمت بلغة أختها (`RegisterTop`).
 *
 * ترتيبُ الخطوات مطابقٌ للمواصفات حرفياً وليس صدفة: **الرقم يُثبت قبل أن ينتظر المراجعة** — رقمُ الكبتن هو ما تصل عليه حوالات
 * كليك (القسم 6/9)، فالإثبات شرطُ الاعتماد لا تفصيلٌ يُؤجَّل.
 *
 * والإثبات وكلمةُ المرور يُرسلان في **طلبٍ واحد** (`POST /auth/register`): حسابٌ يُفتح بالإثبات وحده حسابٌ بلا كلمة مرور،
 * وإثباتٌ يفتح جلسةً قبل أن تُكتب الكلمة يترك للمهاجم شيئاً إن انقطع الطلب بعده (القسم 15/أ).
 *
 * **وما صحّحه المالكُ في اللوحة** (§٦١-أ و§٦٢/١١): رمزٌ **بطول ما ينشره المُحقِّق** · قاعدةُ الكلمة **كما تنشرها الخلفية** (لا «بينها
 * رقم») · **تأكيدُ الكلمة** · **الدولةُ حين يُنشر سوقان** · **والموافقةُ على السياسات شرطٌ في الزرّ**.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { registerAccount, startSignupChallenge } from "@/api/endpoints";
import type { OtpChannel } from "@/api/types";
import { MarketChoice } from "@/components/t2/MarketChoice";
import { PolicyConsentT2 } from "@/components/t2/PolicyConsentT2";
import { RegisterTop } from "@/components/t2/RegisterTop";
import { VerifyCode } from "@/components/t2/VerifyCode";
import { reopenWelcome } from "@/components/welcome/gate";
import { useAuthCountry, useConfig, usePhoneCountry } from "@/lib/config";
import { confirmError, passwordConditions, passwordError, passwordsReady } from "@/lib/password";
import { looksComplete, toE164, toNational } from "@/lib/phone";
import { useSession } from "@/lib/session";
import {
  AuthBlock,
  AuthConditions,
  AuthInput,
  AuthPage,
  AuthPhone,
  AuthSecret,
  Icon,
} from "@/taxo2";

import "@/components/t2/captain-auth.css";

type Field = "name" | "phone" | "password";
type Failure = { field: Field | null; message: string };

/** يوجّه خطأَ حقلٍ من الخلفية إلى حقله في الشاشة (SPEC ١٧.٧).
 *
 * **والخريطةُ لأن اسمَ الحقل في الشاشة ليس دائماً اسمَه في المخطط**: حقلُ كلمة المرور هنا `new-password` (لدلالة الإكمال
 * التلقائي)، والخلفيةُ تسمّيه `password`. وبغير التوجيه يُعلَّم لا شيء وينتقل التركيزُ إلى لا مكان.
 */
const INPUT_ID: Record<Field, string> = {
  name: "name",
  phone: "phone",
  password: "new-password",
};

export function RegisterScreen() {
  const navigate = useNavigate();
  const { config } = useConfig();
  const { signIn } = useSession();

  // **الاختيارُ محفوظٌ على الجهاز** (البند ١٠): نسخةٌ محليةٌ هنا تعني اختياراً
  // يُنسى بين التسجيل والدخول، فيعيده صاحبُ الرقم الليبيّ في كل شاشة
  const { country, countries, setCountry } = useAuthCountry();
  const { dialCode, nationalLength } = usePhoneCountry(country);

  const [step, setStep] = useState<"details" | "verify">("details");
  const [name, setName] = useState("");
  // **الرقمُ الذي كُتب في بطاقة «سجّل كشريك»** (TAXO 2.0) — يصل مع التنقّل فلا
  // يُكتب مرّتين، **ويُطبَّع كما يُطبَّع ما يُكتب في الحقل** (الصفرُ البادئ والبادئةُ المكرَّرة)
  // فيُقرأ مكتملاً حين يكون. **ولا نداءَ يتغيّر**: التسجيلُ هنا بطلبه وترتيبه كما كان
  const location = useLocation();
  const [phone, setPhone] = useState(() => {
    const handed = (location.state as { phone?: string } | null)?.phone ?? "";
    return handed && dialCode !== null ? toNational(handed, dialCode) : handed;
  });
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [touched, setTouched] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [busy, setBusy] = useState(false);
  const page = useRef<HTMLDivElement>(null);

  // المُحقِّقُ **وطولُ رمزه** يتبعان الدولةَ المختارة لا الافتراضية (12-هـ) — والطولُ من صفِّ
  // الدولة أوّلاً ثمّ من `auth` كما كان يُقرأ، فلا يتغيّر عددُ الخانات حيث يتّفقان
  const entry = config?.countries.find((item) => item.country_code === country);
  const method = entry?.verification ?? config?.auth.verification ?? "none";
  const otpLength = entry?.otp_length ?? config?.auth.otp_length ?? null;
  // **ولا رقمَ بلا مفتاحٍ منشور** (`usePhoneCountry`): بمفتاحٍ فارغٍ يُبنى
  // رقمٌ بلا دولة، وبمفتاح سوقٍ آخرَ يُبنى رقمُ إنسانٍ آخر — فيُقال إن الرمز
  // أُرسل ولا يصل أحداً. والفراغُ هنا يُعطّل الإرسالَ ويُقال سببُه
  const e164 = dialCode === null ? "" : toE164(phone, dialCode);

  // **والقناةُ تُمرَّر لا تُهمَل**: زرُّ الارتداد يعطي القناةَ التالية، فمُغلَّفٌ
  // يتجاهلها يعيد الإرسال في القناة الفاشلة نفسها — زرٌّ يعمل ولا يفعل شيئاً
  const requestChallenge = useCallback(
    (channel?: OtpChannel) => startSignupChallenge(e164, country, channel),
    [e164, country],
  );

  // **الموافقةُ شرطٌ في الزرِّ لا في الرسالة** (البند ١٠): مربّعٌ غيرُ
  // مؤشَّرٍ يقول **قبل** الضغط ما ينقص، وزرٌّ يُضغط ثمّ يُردّ يعلّم أن الرفضَ
  // عقبةٌ تُحاوَل. **والخلفيةُ ترفض أيضاً** — حارسان لا واحد (§21).
  const [policyIds, setPolicyIds] = useState<string[]>([]);
  const [agreed, setAgreed] = useState(false);
  const consentOk = policyIds.length === 0 || agreed;

  const complete = looksComplete(phone, nationalLength);
  const ready =
    name.trim().length >= 2 &&
    complete &&
    passwordsReady(password, confirmation) &&
    consentOk;

  const errorOf = (field: Field) => (failure?.field === field ? failure.message : null);
  const nameShort =
    touched && name.length > 0 && name.trim().length < 2 ? "الاسم قصير — حرفان على الأقل." : null;
  const phoneShort =
    touched && phone.length > 0 && !complete && dialCode !== null
      ? `الرقم ناقص — ${nationalLength} أرقام بعد +${dialCode}.`
      : null;

  // الخطوةُ الجديدةُ تُفتح من أعلاها لا من حيث توقّف التمرير
  useEffect(() => {
    if (page.current) page.current.scrollTop = 0;
  }, [step]);

  function next(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (!ready) {
      setTouched(true);
      return;
    }
    setFailure(null);
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
    setFailure(null);
    try {
      signIn(
        await registerAccount({
          phone: e164,
          name: name.trim(),
          password,
          country_code: country,
          verification_token: verificationToken,
          // **ما وافق عليه بعينه** — لا `true` تستنتج منها الخلفيةُ شيئاً
          accepted_policy_ids: agreed ? policyIds : [],
        }),
      );
      navigate("/register/documents", { replace: true });
    } catch (caught) {
      if (caught instanceof ApiError) {
        const field = caught.field("field");
        const at: Field | null = field === "name" || field === "phone" || field === "password" ? field : null;
        setFailure({ field: at, message: caught.message });
        // **الحقلُ المرفوض يُعلَّم ويُنتقل إليه** — وهو في نموذج «الحساب»، فيُعاد إليه.
        // **وإثباتٌ استُهلك لا يُعاد استعماله** (401): بدايةٌ نظيفةٌ من النموذج كما كان
        if (at || caught.status === 401) setStep("details");
        if (at) window.setTimeout(() => document.getElementById(INPUT_ID[at])?.focus(), 0);
      } else {
        setFailure({ field: null, message: "تعذّر الاتصال بالخادم — أعد المحاولة" });
      }
    } finally {
      setBusy(false);
    }
  }

  if (step === "verify") {
    return (
      <div ref={page} className="cap-auth cap-reg scr">
        <AuthPage>
          <VerifyCode
            top={<RegisterTop step={1} onBack={() => setStep("details")} />}
            phone={e164}
            method={method}
            otpLength={otpLength}
            requestChallenge={requestChallenge}
            onProven={(token) => void create(token)}
            onBack={() => setStep("details")}
            note="التحقق من الرقم مرة واحدة عند التسجيل."
            outerError={failure?.field === null ? failure.message : null}
            busy={busy}
          />
        </AuthPage>
      </div>
    );
  }

  return (
    <div ref={page} className="cap-auth cap-reg scr">
      <AuthPage>
        {/* **الرجوعُ إلى الترحيب** — كالدخول: لا تاريخَ قبل التسجيل في التطبيق، فيُطلب الترحيبُ ولا يُرجَع في التاريخ */}
        <RegisterTop step={1} onBack={() => reopenWelcome()} />

        <form onSubmit={next} className="t2-auth-form" noValidate>
          <AuthBlock label="الاسم الكامل" htmlFor="name" error={nameShort ?? errorOf("name")}>
            <AuthInput
              id="name"
              name="name"
              autoComplete="name"
              placeholder="مثال: أبو محمد الزعبي"
              value={name}
              invalid={Boolean(nameShort ?? errorOf("name"))}
              onBlur={() => setTouched(true)}
              onChange={(event) => setName(event.target.value)}
            />
          </AuthBlock>

          <MarketChoice country={country} countries={countries} onChange={setCountry} />

          <AuthBlock
            label="رقم الهاتف"
            htmlFor="phone"
            error={
              dialCode === null
                ? "مفتاحُ هذه الدولة غير متاح الآن — اختر دولةً أخرى أو أعد المحاولة."
                : phoneShort ?? errorOf("phone")
            }
            hint="الرقم هو مُعرّف دخولك، ويُخزَّن بصيغة دولية."
          >
            <AuthPhone
              id="phone"
              name="phone"
              type="tel"
              inputMode="numeric"
              dial={dialCode}
              value={phone}
              maxLength={nationalLength}
              valid={complete}
              disabled={dialCode === null}
              invalid={Boolean(phoneShort ?? errorOf("phone"))}
              onBlur={() => setTouched(true)}
              onChange={(event) =>
                dialCode === null ? undefined : setPhone(toNational(event.target.value, dialCode))
              }
            />
          </AuthBlock>

          {/* **القاعدةُ كما تنشرها الخلفية** (٨–١٢٨ وقائمةُ المنع تفحصها هي) — بنودُها من `/config` لا من نصٍّ هنا */}
          <AuthBlock
            label="كلمة المرور"
            htmlFor="new-password"
            error={passwordError(password) ?? errorOf("password")}
          >
            <AuthSecret
              id="new-password"
              name="new-password"
              autoComplete="new-password"
              value={password}
              invalid={Boolean(passwordError(password) ?? errorOf("password"))}
              onChange={(event) => setPassword(event.target.value)}
            />
            <AuthConditions items={passwordConditions(password)} />
          </AuthBlock>

          <AuthBlock
            label="تأكيد كلمة المرور"
            htmlFor="confirm-password"
            error={confirmError(password, confirmation)}
          >
            <AuthSecret
              id="confirm-password"
              name="confirm-password"
              autoComplete="new-password"
              value={confirmation}
              invalid={Boolean(confirmError(password, confirmation))}
              onChange={(event) => setConfirmation(event.target.value)}
            />
          </AuthBlock>

          {/* **مربّعٌ يُضغط لا جملةٌ تفترض** (البند ١٠، ٢٠٢٦-٠٩-٠٥) — **ونصُّ الكبتن غيرُ نصِّ الراكب** (§34-٢):
              فيه رفعُ رخصةٍ وبياناتُ مركبةٍ وحسابُ صرف */}
          <PolicyConsentT2
            country={country}
            checked={agreed}
            onChange={setAgreed}
            onLoaded={setPolicyIds}
          />

          {failure && failure.field === null ? (
            <div className="t2-auth-banner" role="alert">
              <Icon name="error" />
              <span>{failure.message}</span>
            </div>
          ) : null}

          <div className="t2-auth-push" />
          <div className="t2-auth-actions">
            <button type="submit" className="t2-button primary" disabled={busy || !ready}>
              {busy ? "لحظة…" : "التالي"}
            </button>
          </div>
          {method !== "none" ? <p className="cap-after">الرقم يُثبت بالتحقق مرة واحدة.</p> : null}
        </form>

        <p className="t2-auth-foot">
          لديك حساب؟ <Link to="/login">ادخل</Link>
        </p>
      </AuthPage>
    </div>
  );
}
