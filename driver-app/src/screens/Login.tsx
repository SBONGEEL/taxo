/** الدخول — **C01 «جاهز للطريق؟»** بلغة TAXO 2.0 (Claude Design «TAXO 2.0 - Captain»)، **وكلمةُ مرورٍ دائماً ولا شيء غيرها**.
 *
 * «الدخول كلمة مرور دائماً، والـOTP تحقُّقٌ لا دخول» (SPEC القسم 11/1 و12/1، و`DESIGN-DECISIONS.md` بند 1) — **ولا «دخولَ برمزٍ
 * لمرّةٍ واحدة» أينما رُسم** (§٦١-أ): مكانُه يحمل الدخولَ بالبصمة حيث تتاح، وهو الطريقُ الثاني الذي يملكه التطبيقُ فعلاً.
 *
 * **والمنطقُ كما كان حرفاً**: `POST /auth/login` بالرقم بصيغة E.164 والدولةِ صراحةً، **ولا دخولَ برقمٍ بُني بمفتاحٍ غيرِ منشور**،
 * وجوابُ «عاملٍ ثانٍ» يُقال لصاحبه ولا تُفتح به جلسة، والبصمةُ بشروطها الثلاثة، ومنتقي الدولة حيث سوقان. **وما تغيّر طبقةُ
 * العرض**: الـX الكبير وعلامةُ TAXO بشارة «كبتن»، **والسببُ تحت حقله** (§٦٢/٢٠) — خطأٌ يسمّي حقلاً يُكتب تحته ويُنقل إليه
 * التركيز، وما لا حقلَ له (حسابٌ موقوف، شبكة) سطرٌ فوق الزرّ.
 *
 * **وما في اللوحة ولم يُبنَ كما هو — بعلّته:**
 * - **«سجّل وابدأ خلال 24 ساعة»** تحت «كبتن جديد؟»: لا شيءَ في التطبيق يَعِد بالبدء خلال مدّة — المراجعةُ «عادةً خلال 24 ساعة»
 *   (`PendingT2`) ثمّ فحصُ المركبة والاشتراك — فالسطرُ يقول خطواتِ التسجيل كما يقولها الترحيب («بياناتك، ثم مركبتك ووثائقك»).
 * - **زرُّ الرجوع** ليس في اللوحة: الدخولُ يعود إلى الترحيب (R02 ← R01 في الراكب) — فيقع في سطر العلامة بلغة رأس C02.
 */

import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { login } from "@/api/endpoints";
import { MarketChoice } from "@/components/t2/MarketChoice";
import { reopenWelcome } from "@/components/welcome/gate";
import { biometryLabel } from "@/lib/biometric";
import { useAuthCountry, usePhoneCountry } from "@/lib/config";
import { looksComplete, toE164, toNational } from "@/lib/phone";
import { useSession } from "@/lib/session";
import {
  AuthBlock,
  AuthOr,
  AuthPage,
  AuthPhone,
  AuthSecret,
  AuthTitle,
  Icon,
  Wordmark,
} from "@/taxo2";

import "@/components/t2/captain-auth.css";

type Failure = { field: "phone" | "password" | null; message: string };

export function LoginScreen() {
  const navigate = useNavigate();
  const { signIn, biometry, signInWithBiometry } = useSession();
  // **منتقي الدولة في الثلاث لا في التسجيل وحدَه** (البند ١٠): من يحمل رقماً
  // ليبياً كان يرى مفتاحَ الأردن فيُرفض رقمُه بلا أن يفهم لماذا
  const { country, countries, setCountry } = useAuthCountry();
  const { dialCode, nationalLength } = usePhoneCountry(country);

  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [touched, setTouched] = useState(false);
  const [failure, setFailure] = useState<Failure | null>(null);
  const [busy, setBusy] = useState(false);
  const [bioBusy, setBioBusy] = useState(false);

  const complete = looksComplete(phone, nationalLength);
  const short =
    touched && phone.length > 0 && !complete && dialCode !== null
      ? `الرقم ناقص — ${nationalLength} أرقام بعد +${dialCode}.`
      : null;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || !complete || !password) {
      setTouched(true);
      return;
    }
    setBusy(true);
    setFailure(null);
    try {
      // يُرسل E.164 ومعه الدولة صراحةً: لا استنتاجَ ولا التباس
      // **ولا دخولَ برقمٍ بُني بمفتاحٍ غيرِ منشور**: يرتدّ «رقمٌ غير
      // مسجَّل» عن حسابٍ قائم، فيُقرأ الحسابُ محذوفاً ويُنشأ ثانٍ عليه
      if (dialCode === null) throw new Error("مفتاح الدولة غير متاح");
      const response = await login(toE164(phone, dialCode), password, country);
      // **جوابان لا جواب**: حسابٌ يحمل عاملاً ثانياً يعود بلا توكن (12-د).
      // ولا يُسجَّل عاملٌ إلا لحسابات اللوحة (`SecuritySelfUser`)، فهذا الجواب
      // هنا يعني حساب طاقمٍ يحاول الدخول من تطبيقٍ ليس له — ويُقال له ذلك
      // صراحةً بدل أن يُحفظ توكنٌ غائبٌ فتُفتح جلسةٌ فارغة
      if (response.totp_required || !response.user || !response.tokens) {
        setFailure({
          field: null,
          message: "هذا الحساب يحتاج تحقّقاً ثنائياً — وهو لحسابات لوحة الإدارة، فادخل من اللوحة.",
        });
        return;
      }
      signIn({ user: response.user, tokens: response.tokens });
    } catch (caught) {
      if (caught instanceof ApiError) {
        const field = caught.field("field");
        const at = field === "phone" || field === "password" ? field : null;
        setFailure({ field: at, message: caught.message });
        if (at) document.getElementById(at)?.focus();
      } else {
        setFailure({ field: null, message: "تعذّر تسجيل الدخول — أعد المحاولة" });
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="cap-auth cap-login scr">
      <AuthPage>
        {/* **الـX الكبير خلف العنوان** — زينةٌ لا تُقرأ، **وجمرُه ينتهي قبل أوّل سطرٍ يُقرأ** (`captain-auth.css`) */}
        <div className="cap-x" aria-hidden="true">
          <div className="cap-x-cut">
            <span className="cap-x-ember" />
          </div>
          <span className="cap-x-paper" />
        </div>

        <div className="cap-brand">
          {/* **الرجوعُ إلى الترحيب** — شاشةُ دخولٍ لا تاريخَ قبلها في التطبيق، فيُطلب الترحيبُ ولا يُرجَع في التاريخ */}
          <button type="button" className="t2-auth-back" onClick={() => reopenWelcome()} aria-label="رجوع">
            <Icon name="arrow_forward" />
          </button>
          <Wordmark size={26} />
          <span className="cap-pill">كبتن</span>
        </div>

        <AuthTitle title="جاهز للطريق؟" sub="ادخل لتبدأ استقبال الطلبات." />

        <form onSubmit={submit} className="t2-auth-form" noValidate>
          <MarketChoice country={country} countries={countries} onChange={setCountry} />

          <AuthBlock
            label="رقم الهاتف"
            htmlFor="phone"
            error={
              dialCode === null
                ? "مفتاحُ هذه الدولة غير متاح الآن — اختر دولةً أخرى أو أعد المحاولة."
                : short ?? (failure?.field === "phone" ? failure.message : null)
            }
          >
            {/* **البادئةُ من `GET /config`** والرقمُ الوطنيُّ وحده يُكتب — والصفرُ البادئ يُحذف فور كتابته */}
            <AuthPhone
              id="phone"
              name="phone"
              type="tel"
              inputMode="numeric"
              dial={dialCode}
              value={phone}
              maxLength={nationalLength}
              disabled={dialCode === null}
              invalid={Boolean(short) || failure?.field === "phone"}
              onBlur={() => setTouched(true)}
              onChange={(event) =>
                dialCode === null ? undefined : setPhone(toNational(event.target.value, dialCode))
              }
            />
          </AuthBlock>

          <AuthBlock
            label="كلمة المرور"
            htmlFor="password"
            error={failure?.field === "password" ? failure.message : null}
          >
            <AuthSecret
              id="password"
              name="password"
              autoComplete="current-password"
              value={password}
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
            <button type="submit" className="t2-button primary" disabled={busy || !complete || !password}>
              {busy ? "لحظة…" : "دخول"}
            </button>

            {/* **الزرُّ لا يُرسم إلا بثلاثة مجتمعة** (قرارُ المالك): جهازٌ أصليّ ·
                بصمةٌ متاحةٌ ومسجَّلة · **ورمزٌ محفوظٌ فعلاً**. و`armed` هو الثالث —
                فمن خرج مُحي رمزُه ويبقى تفضيلُه، **وزرٌّ يُرسم على التفضيل وحدَه
                زرٌّ يفشل عند الضغط**. وفي المتصفّح `available` كاذبةٌ دائماً بلا
                نداءِ ملحقٍ أصلاً. */}
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
                      .catch((caught: unknown) => {
                        // **يُقال ما وقع لا «تعذّر الدخول»**: بصمةٌ مرفوضةٌ غيرُ
                        // جلسةٍ منتهية، والثاني يعني «اكتب كلمتك» والأول «أعد إصبعك»
                        setFailure({
                          field: null,
                          message: caught instanceof Error ? caught.message : "تعذّر الدخول بالبصمة",
                        });
                      })
                      .finally(() => setBioBusy(false));
                  }}
                >
                  <Icon name="fingerprint" />
                  <span>{bioBusy ? "لحظة…" : `الدخول بـ${biometryLabel(biometry.kind)}`}</span>
                </button>
              </>
            ) : null}

            <button type="button" className="cap-join" onClick={() => navigate("/register")}>
              <Icon name="person_add" className="cap-join-icon" />
              <span className="cap-join-main">
                <span className="cap-join-title">كبتن جديد؟</span>
                <span className="cap-join-sub">سجّل بياناتك، ثم مركبتك ووثائقك.</span>
              </span>
              <Icon name="arrow_back" className="cap-join-go" />
            </button>
          </div>
        </form>
      </AuthPage>
    </div>
  );
}
