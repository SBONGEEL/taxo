/** خطوةُ الرمز — **R04 «أدخل رمز التحقق»** بلغة TAXO 2.0، **ومنطقُ `PhoneVerification` نفسُه حرفاً** (SPEC القسم 12/1 و15/أ).
 *
 * **الواجهة لا تفترض المُحقِّق**: تقرؤه الشاشةُ من صفِّ دولة الحساب في `/config` وتسلّمه هنا — Firebase يرسل من جهاز الكبتن
 * ويُسلَّم **رمزُ هويته**، وSMS/واتساب ترسلهما خلفيتُنا ويُسلَّم **الرمزُ نفسُه** كما كُتب. **ولا تعرف ترتيبَ المُحقِّقين ولا
 * تختار بينهم** — ذاك قرارُ `services/verification.py` وحده.
 *
 * **وفشلُ قناةٍ لا يترك صاحبَه عالقاً**: الخلفيةُ تردّ الخطأ ومعه `fallback_channel` فيُرسم زرُّ القناة التالية. **ولا ارتدادَ
 * صامت**: الرمزُ ربما وصل، وتبديلٌ لا يعلمه صاحبُه يجعله يكتب رمزاً من قناةٍ أخرى. **ولا جلسةَ هنا**: الإثباتُ يُسلَّم للشاشة
 * فترسله مع طلبها في طلبٍ واحد (التسجيلُ أو تغييرُ الكلمة — القسم 15/أ).
 *
 * **والرمزُ بالطول الذي ينشره المُحقِّق** (§٦١-أ — ستُّ خاناتٍ اليوم لا أربعٌ مرسومة)، **ولوحةُ المفاتيح لوحةُ النظام** فيبقى
 * الملءُ الآليُّ من الرسالة (`one-time-code`). **والرأسُ من الشاشة** (`top`): «إنشاء حساب كبتن» بخطواته في التسجيل، ورجوعٌ
 * بمسار خطواتٍ في الاستعادة.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";

import { ApiError } from "@/api/client";
import type { ChallengeResponse, OtpChannel, VerificationMethod } from "@/api/types";
import { firebaseConfigOf, useConfig } from "@/lib/config";
import { startPhoneVerification, type PhoneChallenge } from "@/lib/firebase";
import { AuthCode, AuthError, AuthTitle, Icon } from "@/taxo2";

const RECAPTCHA_CONTAINER = "taxo-recaptcha";

/** القناةُ التي وصل فيها الرمزُ فعلاً (12-هـ) — **من الخلفية لا تُخمَّن**: من ينتظر رسالةً نصيةً وقد وصله واتساب يفتح تطبيقاً
 *  خطأً ثمّ يضغط «إعادة الإرسال» — وكلُّ إعادةٍ رسالةٌ مدفوعة. */
const CHANNEL_LABEL: Record<string, string> = {
  whatsapp_otp: "في واتساب",
  sms_otp: "برسالة نصية",
};

const FALLBACK_LABEL: Record<string, string> = {
  whatsapp_otp: "أرسله في واتساب",
  sms_otp: "أرسله برسالة نصية",
};

/** «0:42» — بخاناتٍ لاتينية، **والدقائقُ تُحسب** فلا يُكتب «0:120» لمهلةٍ أطولَ من دقيقة. */
function clock(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}

interface Props {
  /** بصيغة E.164 جاهزةً — تبنيها الشاشةُ من بادئة `GET /config`، **وفارغةٌ حين لا مفتاحَ منشوراً**. */
  phone: string;
  method: VerificationMethod;
  otpLength: number | null;
  /** يبدأ التحدي عند قناةٍ نرسل منها — مسارُ الاستعادة غيرُ مسار التسجيل. */
  requestChallenge: (channel?: OtpChannel) => Promise<ChallengeResponse>;
  /** يسلّم **إثباتاً** جاهزاً للإرسال مع بقية الطلب. */
  onProven: (verificationToken: string) => void;
  /** «تعديل الرقم» — يرجع إلى الخطوة السابقة ويبقى في التدفّق. */
  onBack: () => void;
  /** الرأس — يرسمه المُنادي بلغة شاشته. */
  top: ReactNode;
  /** سطرُ السياق تحت الرمز — نصُّ الشاشة القائمة («التحقق من الرقم مرة واحدة عند التسجيل.»…). */
  note?: string;
  /** الزرُّ في آخرها. */
  submitLabel?: string;
  /** خطأُ الخطوة التالية (إنشاءُ الحساب) — يُعرض هنا لأنها هي التي تُرى. */
  outerError?: string | null;
  /** الطلبُ الذي يحمل الإثباتَ جارٍ. */
  busy?: boolean;
}

export function VerifyCode({
  phone,
  method,
  otpLength,
  requestChallenge,
  onProven,
  onBack,
  top,
  note,
  submitLabel = "تحقق",
  outerError,
  busy = false,
}: Props) {
  const { config } = useConfig();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(true);
  const [checking, setChecking] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [channel, setChannel] = useState<string | null>(null);
  const [fallback, setFallback] = useState<OtpChannel | null>(null);
  const challenge = useRef<PhoneChallenge | null>(null);

  const length = otpLength ?? 6;

  const send = useCallback(
    async (pick?: OtpChannel) => {
      setSending(true);
      setError(null);
      setFallback(null);
      try {
        if (method === "firebase") {
          const firebase = firebaseConfigOf(config?.providers.firebase_auth);
          if (!firebase) {
            // **جملةُ من يقرؤها لا جملةُ من يصلحها** (2026-08-14) — والسببُ الفنيُّ في `console` لمن يفتحه
            console.error("firebase config missing in GET /config providers");
            throw new Error("التحقق من رقم هاتفك غير متاح حالياً. حاول بعد قليل.");
          }
          challenge.current = await startPhoneVerification(firebase, phone, RECAPTCHA_CONTAINER);
          setCooldown(60);
          return;
        }
        const response = await requestChallenge(pick);
        // `sent=false` ليست خطأً: مُحقِّقٌ لا يحتاج تحدياً من عندنا
        setChannel(response.channel);
        setCooldown(response.resend_after ?? 60);
      } catch (caught) {
        setError(caught instanceof ApiError || caught instanceof Error ? caught.message : "تعذّر إرسال رمز التحقق");
        // القناةُ التالية تأتي من الخلفية — وغيابُها يعني ألّا مخرجَ آخر، فلا يُرسم زرٌّ لا يعمل
        const next = caught instanceof ApiError ? caught.field("fallback_channel") : null;
        setFallback(next === "sms_otp" || next === "whatsapp_otp" ? next : null);
      } finally {
        setSending(false);
      }
    },
    [config, phone, method, requestChallenge],
  );

  useEffect(() => {
    void send();
    // مرةً واحدة عند فتح الخطوة؛ ما بعدها بـ«إعادة الإرسال»
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setTimeout(() => setCooldown((value) => value - 1), 1_000);
    return () => window.clearTimeout(timer);
  }, [cooldown]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (code.length < length || sending || checking || busy) return;
    setChecking(true);
    setError(null);
    try {
      if (method === "firebase") {
        if (!challenge.current) throw new Error("أعد إرسال الرمز أولاً");
        onProven(await challenge.current.confirm(code));
        return;
      }
      // مزوّد SMS/واتساب: الرمزُ نفسُه هو الإثبات، وتفحصه الخلفية
      onProven(code);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "رمز التحقق غير صحيح أو انتهت صلاحيته");
    } finally {
      setChecking(false);
    }
  }

  const shown = error ?? outerError ?? null;

  return (
    <>
      {top}
      <AuthTitle
        step
        title="أدخل رمز التحقق"
        sub={
          <>
            {channel && CHANNEL_LABEL[channel]
              ? `أرسلنا رمزاً ${CHANNEL_LABEL[channel]} من ${length} أرقام إلى `
              : `أرسلنا رمزاً من ${length} أرقام إلى `}
            <strong dir="ltr">{phone}</strong> ·{" "}
            <button type="button" className="t2-auth-link" onClick={onBack}>
              تعديل الرقم
            </button>
          </>
        }
      />
      <form onSubmit={submit} className="t2-auth-form step code" noValidate>
        {/* **الخاناتُ تُقفل ما دام الرمزُ يُرسل، ويعود التركيزُ إليها حين يصل** — فلا يُكتب في رمزٍ لم يُرسل */}
        <AuthCode
          length={length}
          value={code}
          onChange={setCode}
          invalid={Boolean(shown)}
          disabled={sending}
          autoFocus={!sending}
        />
        <AuthError message={shown} />

        <div className="t2-auth-resend">
          <Icon name="schedule" />
          {cooldown > 0 ? (
            <span>
              إعادة الإرسال بعد <strong>{clock(cooldown)}</strong>
            </span>
          ) : (
            <button type="button" onClick={() => void send()} disabled={sending}>
              إعادة إرسال الرمز
            </button>
          )}
        </div>
        {note ? <p className="t2-auth-hint">{note}</p> : null}

        {/* عنصرٌ فارغٌ يعلّق عليه reCAPTCHA نفسه — غيرُ مرئيٍّ ولازمٌ للحزمة */}
        <div id={RECAPTCHA_CONTAINER} />

        <div className="t2-auth-actions">
          <button
            type="submit"
            className="t2-button primary"
            disabled={code.length < length || sending || checking || busy}
          >
            {checking || busy ? "لحظة…" : submitLabel}
          </button>
          {/* مخرجُ القناة التالية — يظهر عند فشل الإرسال وحده */}
          {fallback ? (
            <button type="button" className="t2-button secondary" onClick={() => void send(fallback)} disabled={sending}>
              {FALLBACK_LABEL[fallback]}
            </button>
          ) : null}
        </div>
      </form>
    </>
  );
}
