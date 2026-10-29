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
import { enrollRole, login } from "@/api/endpoints";
import { reopenWelcome } from "@/components/welcome/gate";
import { biometryLabel } from "@/lib/biometric";
import { useCountryPick } from "@/components/t2/CountryPick";
import { useAuthCountry, usePhoneCountry } from "@/lib/config";
import { looksComplete, toNational } from "@/lib/phone";
import { useSession } from "@/lib/session";
import {
  AuthBlock,
  AuthOr,
  AuthPage,
  AuthPhone,
  AuthSecret,
  AuthTitle,
  AuthTop,
  Icon,
} from "@/taxo2"; import { tr } from "@/lib/i18n";

type Failure = { field: "phone" | "password" | null; message: string };

export function LoginScreen() {
  const { signIn, biometry, signInWithBiometry } = useSession();
  const navigate = useNavigate();
  const location = useLocation();

  // **مصدرٌ واحدٌ لدولة شاشات المصادقة** (`useAuthCountry`)
  const auth = useAuthCountry("login");
  const { country } = auth;
  // **مُختارُ الدولة في حقل الهاتف** (SPEC §٧٤-أ/٤) — في الدخول كلُّ دولة، فلا يُقفل أحدٌ خارج حسابه
  const pick = useCountryPick(auth, "login");
  const { dialCode, nationalLength } = usePhoneCountry(country);
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [touched, setTouched] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  // **الرقمُ نفسُه في التطبيق الآخر** (SPEC §21.6): كلمةُ المرور صحيحة، والخلفيةُ تعرض إضافةَ هذا الملفّ إلى الحساب نفسِه برمز
  const [offer, setOffer] = useState<string | null>(null);
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
      ? tr("الرقم ناقص — {0} أرقام بعد +{1}.", { 0: nationalLength, 1: dialCode })
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
        setFailure({ field: null, message: tr("هذا الحساب يحتاج تحقّقاً ثنائياً — وهو لحسابات لوحة الإدارة، فادخل من اللوحة.") });
        return;
      }
      signIn({ user: response.user, tokens: response.tokens });
      navigate("/", { replace: true });
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === "role_can_be_added" && typeof caught.extra.enroll_token === "string") {
        setOffer(caught.extra.enroll_token);
        return;
      }
      if (caught instanceof ApiError) {
        const field = caught.field("field");
        const at = field === "phone" || field === "password" ? field : null;
        setFailure({ field: at, message: caught.message });
        if (at) document.getElementById(at)?.focus();
      } else {
        setFailure({ field: null, message: tr("تعذّر الدخول — أعد المحاولة") });
      }
    } finally {
      setBusy(false);
    }
  }


  async function addProfile() {
    if (!offer || busy) return;
    setBusy(true);
    setFailure(null);
    try {
      const added = await enrollRole(offer);
      signIn({ user: added.user, tokens: added.tokens });
      navigate("/", { replace: true });
    } catch (caught) {
      setOffer(null);
      setFailure({ field: null, message: caught instanceof ApiError ? caught.message : tr("تعذّرت إضافة الملف — أعد المحاولة") });
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthPage>
      {/* **الرجوعُ إلى الترحيب** (R02 ← R01) — شاشةُ دخولٍ لا تاريخَ قبلها في التطبيق، فيُطلب الترحيبُ ولا يُرجَع في التاريخ */}
      <AuthTop onBack={reopenWelcome} />
      <AuthTitle title={tr("أهلاً من جديد")} sub={tr("ادخل برقم هاتفك وكلمة المرور.")} />

      <form onSubmit={submit} className="t2-auth-form" noValidate>
        {/* **سوقان أو أكثر ⇒ يُختار السوق** — زرّان لا قائمة: سوقان اثنان، والقائمةُ تخفي أحدَهما خلف ضغطة */}

        <AuthBlock
          label={tr("رقم الهاتف")}
          htmlFor="phone"
          error={
            dialCode === null
              ? tr("مفتاحُ هذه الدولة غير متاح الآن — اختر دولةً أخرى أو أعد المحاولة.")
              : short ?? (failure?.field === "phone" ? failure.message : null)
          }
        >
          <AuthPhone
            id="phone"
            country={pick.trigger}
            name="phone"
            dial={dialCode}
            value={phone}
            maxLength={nationalLength}
            disabled={busy || dialCode === null}
            invalid={Boolean(short) || failure?.field === "phone"}
            onBlur={() => setTouched(true)}
            onChange={(event) => (dialCode === null ? undefined : setPhone(toNational(event.target.value, dialCode)))}
          />
          {pick.sheet}
        </AuthBlock>

        <AuthBlock label={tr("كلمة المرور")} htmlFor="password" error={failure?.field === "password" ? failure.message : null}>
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
          {tr("نسيت كلمة المرور؟")}
        </Link>

        {offer ? (
          <div className="t2-auth-banner" role="status">
            <Icon name="info" />
            <span>{tr("رقمُك مسجّلٌ في التطبيق الآخر. أضِف هذا الملفّ إلى حسابك نفسِه — رقمٌ واحد، ومحفظةٌ منفصلةٌ لكلِّ ملفّ.")}</span>
            <button type="button" className="t2-tlink accent" onClick={() => void addProfile()} disabled={busy}>
              {tr("أضف ملفّ الراكب إلى حسابي")}
            </button>
          </div>
        ) : null}

        {failure && failure.field === null ? (
          <div className="t2-auth-banner" role="alert">
            <Icon name="error" />
            <span>{failure.message}</span>
          </div>
        ) : null}

        <div className="t2-auth-push" />

        <div className="t2-auth-actions">
          <button type="submit" className="t2-button primary" disabled={busy || dialCode === null || !complete || password.length < 1}>
            {busy ? tr("لحظة…") : tr("دخول")}
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
                      setFailure({ field: null, message: caught instanceof Error ? caught.message : tr("تعذّر الدخول بالبصمة") }),
                    )
                    .finally(() => setBioBusy(false));
                }}
              >
                <Icon name="fingerprint" />
                <span>{tr("الدخول بـ")}{biometryLabel(biometry.kind)}</span>
              </button>
            </>
          ) : null}
        </div>
      </form>

      <p className="t2-auth-foot">
        {tr("جديد على TAXO؟")}{" "}<Link to="/register">{tr("أنشئ حساباً")}</Link>
      </p>
    </AuthPage>
  );
}
