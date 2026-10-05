/** الدخول — **R02 «أهلاً من جديد»** بلغة TAXO 2.0، **وكلمةُ مرورٍ دائماً ولكلِّ المستخدمين** (SPEC القسم 11.1).
 *
 * لا شرطَ هنا على المُحقِّق: OTP تحقّقٌ لا دخول، وشاشةُ الدخول واحدةٌ مهما كانت العقودُ المفعّلة (SPEC القسم 2/15-أ). **ولذلك
 * لا «دخولَ برمزٍ لمرّةٍ واحدة»** وإن رسمته اللوحة (§٦١-أ): **مكانُه يحمل الدخولَ بالبصمة** حيث تتاح — الطريقُ الثاني الذي
 * يملكه التطبيقُ فعلاً.
 *
 * **والسببُ تحت حقله** (§٦٢/٢٠): خطأٌ يسمّي حقلاً يُكتب تحته ويُنقل إليه التركيز، **وما لا حقلَ له** (حسابٌ موقوف، شبكة) سطرٌ
 * فوق الزرّ.
 */
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { login } from "@/api/endpoints";
import { reopenWelcome } from "@/components/welcome/gate";
import { biometryLabel } from "@/lib/biometric";
import { useAuthCountry, usePhoneCountry } from "@/lib/config";
import { COUNTRY_LABEL, looksComplete, toNational } from "@/lib/phone";
import { useSession } from "@/lib/session";
import {
  AuthBlock,
  AuthChoice,
  AuthOr,
  AuthPage,
  AuthPhone,
  AuthSecret,
  AuthTitle,
  AuthTop,
  Icon,
} from "@/taxo2";

type Failure = { field: "phone" | "password" | null; message: string };

export function LoginScreen() {
  const { signIn, biometry, signInWithBiometry } = useSession();
  const navigate = useNavigate();
  const location = useLocation();

  // **مصدرٌ واحدٌ لدولة شاشات المصادقة** (`useAuthCountry`)
  const { country, countries, setCountry } = useAuthCountry();
  const { dialCode, nationalLength } = usePhoneCountry(country);
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [touched, setTouched] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [busy, setBusy] = useState(false);
  const [bioBusy, setBioBusy] = useState(false);

  // **الرقمُ الذي جاء مع التنقّل** يُقرأ كلّما تغيّر — ولا نداءَ يتغيّر: الدخولُ هنا كما كان
  const handedPhone = (location.state as { phone?: string } | null)?.phone;
  useEffect(() => {
    if (handedPhone) setPhone(handedPhone);
  }, [handedPhone]);

  const complete = looksComplete(phone, nationalLength);
  const short =
    touched && phone.length > 0 && !complete && dialCode !== null
      ? `الرقم ناقص — ${nationalLength} أرقام بعد +${dialCode}.`
      : null;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!complete || password.length < 1 || busy) {
      setTouched(true);
      return;
    }
    setBusy(true);
    setFailure(null);
    try {
      const response = await login(phone, password, country);
      // **جوابان لا جواب**: حسابُ طاقمٍ يحمل عاملاً ثانياً يعود بلا توكن (12-د) — ويُقال له ذلك صراحةً
      if (response.totp_required || !response.user || !response.tokens) {
        setFailure({ field: null, message: "هذا الحساب يحتاج تحقّقاً ثنائياً — وهو لحسابات لوحة الإدارة، فادخل من اللوحة." });
        return;
      }
      signIn({ user: response.user, tokens: response.tokens });
      navigate("/", { replace: true });
    } catch (caught) {
      if (caught instanceof ApiError) {
        const field = caught.field("field");
        const at = field === "phone" || field === "password" ? field : null;
        setFailure({ field: at, message: caught.message });
        if (at) document.getElementById(at)?.focus();
      } else {
        setFailure({ field: null, message: "تعذّر الدخول — أعد المحاولة" });
      }
    } finally {
      setBusy(false);
    }
  }


  return (
    <AuthPage>
      {/* **الرجوعُ إلى الترحيب** (R02 ← R01) — شاشةُ دخولٍ لا تاريخَ قبلها في التطبيق، فيُطلب الترحيبُ ولا يُرجَع في التاريخ */}
      <AuthTop onBack={reopenWelcome} />
      <AuthTitle title="أهلاً من جديد" sub="ادخل برقم هاتفك وكلمة المرور." />

      <form onSubmit={submit} className="t2-auth-form" noValidate>
        {/* **سوقان أو أكثر ⇒ يُختار السوق** — زرّان لا قائمة: سوقان اثنان، والقائمةُ تخفي أحدَهما خلف ضغطة */}
        {countries.length > 1 ? (
          <AuthBlock label="السوق">
            <AuthChoice
              label="السوق"
              value={country}
              options={countries.map((code) => ({ value: code, label: COUNTRY_LABEL[code] }))}
              onChange={setCountry}
            />
          </AuthBlock>
        ) : null}

        <AuthBlock
          label="رقم الهاتف"
          htmlFor="phone"
          error={
            dialCode === null
              ? "مفتاحُ هذه الدولة غير متاح الآن — اختر دولةً أخرى أو أعد المحاولة."
              : short ?? (failure?.field === "phone" ? failure.message : null)
          }
        >
          <AuthPhone
            id="phone"
            name="phone"
            dial={dialCode}
            value={phone}
            maxLength={nationalLength}
            disabled={busy || dialCode === null}
            invalid={Boolean(short) || failure?.field === "phone"}
            onBlur={() => setTouched(true)}
            onChange={(event) => (dialCode === null ? undefined : setPhone(toNational(event.target.value, dialCode)))}
          />
        </AuthBlock>

        <AuthBlock label="كلمة المرور" htmlFor="password" error={failure?.field === "password" ? failure.message : null}>
          <AuthSecret
            id="password"
            name="password"
            autoComplete="current-password"
            value={password}
            disabled={busy}
            invalid={failure?.field === "password"}
            onChange={(event) => setPassword(event.target.value)}
          />
        </AuthBlock>

        <Link to="/forgot-password" className="t2-auth-link t2-auth-forgot">
          نسيت كلمة المرور؟
        </Link>

        {failure && failure.field === null ? (
          <div className="t2-auth-banner" role="alert">
            <Icon name="error" />
            <span>{failure.message}</span>
          </div>
        ) : null}

        <div className="t2-auth-push" />

        <div className="t2-auth-actions">
          <button type="submit" className="t2-button primary" disabled={busy || dialCode === null || !complete || password.length < 1}>
            {busy ? "لحظة…" : "دخول"}
          </button>

          {/* **ثلاثةٌ مجتمعة**: جهازٌ أصليّ · بصمةٌ متاحة · **ورمزٌ محفوظٌ فعلاً** (`armed`) */}
          {biometry?.available && biometry.armed ? (
            <>
              <AuthOr />
              <button
                type="button"
                className="t2-button secondary"
                disabled={bioBusy}
                onClick={() => {
                  setFailure(null);
                  setBioBusy(true);
                  void signInWithBiometry()
                    .catch((caught: unknown) =>
                      setFailure({ field: null, message: caught instanceof Error ? caught.message : "تعذّر الدخول بالبصمة" }),
                    )
                    .finally(() => setBioBusy(false));
                }}
              >
                <Icon name="fingerprint" />
                <span>الدخول بـ{biometryLabel(biometry.kind)}</span>
              </button>
            </>
          ) : null}
        </div>
      </form>

      <p className="t2-auth-foot">
        جديد على TAXO؟ <Link to="/register">أنشئ حساباً</Link>
      </p>
    </AuthPage>
  );
}
