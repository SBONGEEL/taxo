/** خطوةُ الرمز — **R04 «أدخل رمز التحقق»** بلغة TAXO 2.0، ومنطقُ `PhoneVerification` نفسُه حرفاً (SPEC القسم 11.1/15-أ).
 *
 * **الواجهة لا تفترض المُحقِّق**: تقرؤه من `/config` من صفِّ دولة الحساب، وترسم التدفّق المناسب — Firebase يرسل من جهاز
 * المستخدم ويُسلَّم رمزُ هويته، وSMS/واتساب ترسلهما الخلفيةُ ويُسلَّم الرمزُ نفسُه. **وفشلُ قناةٍ لا يترك صاحبَه عالقاً**: الخلفيةُ
 * تردّ `fallback_channel` فيُرسم زرُّ القناة التالية.
 *
 * **وما صحّحه المالكُ في اللوحة** (§٦١-أ): الرمزُ **بالطول الذي ينشره المُحقِّق** (ستُّ خانات اليوم) لا أربعٌ مرسومة. **ولوحةُ
 * المفاتيح في اللوحة لوحةُ النظام** (مفاتيحُ iOS الرقمية بعينها) — فيبقى الملءُ الآليُّ من الرسالة (`one-time-code`).
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/api/client";
import type { ChallengeResponse, OtpChannel, VerificationMethod } from "@/api/types";
import { firebaseConfigOf, useConfig } from "@/lib/config";
import { startPhoneVerification, type PhoneChallenge } from "@/lib/firebase";
import { toE164 } from "@/lib/phone";
import { AuthCode, AuthError, AuthPage, AuthTitle, AuthTop, Icon } from "@/taxo2";

const RECAPTCHA_CONTAINER = "taxo-recaptcha";

/** القناةُ التي وصل فيها الرمزُ فعلاً (12-هـ) — من الخلفية لا تُخمَّن. */
const CHANNEL_LABEL: Record<string, string> = {
  whatsapp_otp: "في واتساب",
  sms_otp: "برسالة نصية",
};

const FALLBACK_LABEL: Record<string, string> = {
  whatsapp_otp: "أرسله في واتساب",
  sms_otp: "أرسله برسالة نصية",
};

function clock(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

interface Props {
  phone: string;
  /** `null` حين لا تُنشر الدولةُ في `GET /config` — **ولا يُبنى رقمٌ حينها**. */
  dialCode: string | null;
  method: VerificationMethod;
  otpLength: number | null;
  requestChallenge: (channel?: OtpChannel) => Promise<ChallengeResponse>;
  /** يسلّم **إثباتاً** جاهزاً للإرسال مع بقية الطلب. */
  onProven: (verificationToken: string) => void;
  /** «تعديل الرقم» — يرجع إلى الخطوة السابقة ويبقى في التدفّق. */
  onBack: () => void;
  /** السهمُ أعلى الشاشة — **يغادر المصادقةَ** (مخرجان مختلفان، كما في `PhoneVerification`). */
  onLeave?: () => void;
  step: number;
  total: number;
  /** الزرُّ في آخرها — «تحقق» في التسجيل، و«تغيير كلمة المرور» في الاستعادة. */
  submitLabel?: string;
  /** خطأُ الخطوة التالية (الإنشاء أو التغيير) — يُعرض هنا لأنها هي التي تُرى. */
  outerError?: string | null;
  busy?: boolean;
}

export function VerifyCode({
  phone,
  dialCode,
  method,
  otpLength,
  requestChallenge,
  onProven,
  onBack,
  onLeave,
  step,
  total,
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

  // **ولا رقمَ بلا مفتاحٍ منشور** — كما في `PhoneVerification`: الفراغُ يُعطّل الإرسالَ ويُقال سببُه
  const e164 = dialCode === null ? "" : toE164(phone, dialCode);
  const digits = otpLength ?? 6;

  const send = useCallback(
    async (pick?: OtpChannel) => {
      setSending(true);
      setError(null);
      setFallback(null);
      try {
        if (method === "firebase") {
          const firebase = firebaseConfigOf(config?.providers.firebase_auth);
          if (!firebase) {
            console.error("firebase config missing in GET /config providers");
            throw new Error("التحقق من رقم هاتفك غير متاح حالياً. حاول بعد قليل.");
          }
          challenge.current = await startPhoneVerification(firebase, e164, RECAPTCHA_CONTAINER);
          setCooldown(60);
          return;
        }
        const response = await requestChallenge(pick);
        setChannel(response.channel);
        setCooldown(response.resend_after ?? 60);
      } catch (caught) {
        setError(caught instanceof ApiError || caught instanceof Error ? caught.message : "تعذّر إرسال رمز التحقق");
        const next = caught instanceof ApiError ? caught.field("fallback_channel") : null;
        setFallback(next === "sms_otp" || next === "whatsapp_otp" ? next : null);
      } finally {
        setSending(false);
      }
    },
    [config, e164, method, requestChallenge],
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

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (code.length < digits || sending || checking || busy) return;
    setChecking(true);
    setError(null);
    try {
      if (method === "firebase") {
        if (!challenge.current) throw new Error("أعد إرسال الرمز أولاً");
        onProven(await challenge.current.confirm(code));
        return;
      }
      onProven(code);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "رمز التحقق غير صحيح أو انتهت صلاحيته");
    } finally {
      setChecking(false);
    }
  }

  const shown = error ?? outerError ?? null;

  return (
    <AuthPage>
      <AuthTop onBack={onLeave ?? onBack} step={step} total={total} />
      <AuthTitle
        step
        title="أدخل رمز التحقق"
        sub={
          <>
            {channel && CHANNEL_LABEL[channel] ? `أرسلنا رمزاً ${CHANNEL_LABEL[channel]} من ${digits} أرقام إلى ` : `أرسلنا رمزاً من ${digits} أرقام إلى `}
            <strong dir="ltr">{e164}</strong> ·{" "}
            <button type="button" className="t2-auth-link" onClick={onBack}>
              تعديل الرقم
            </button>
          </>
        }
      />
      <form onSubmit={submit} className="t2-auth-form step code" noValidate>
        <AuthCode length={digits} value={code} onChange={setCode} invalid={Boolean(shown)} disabled={sending} />
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

        {/* عنصرٌ فارغ يعلّق عليه reCAPTCHA نفسه — غير مرئي ولازم للحزمة */}
        <div id={RECAPTCHA_CONTAINER} />

        <div className="t2-auth-actions">
          <button type="submit" className="t2-button primary" disabled={code.length < digits || sending || checking || busy}>
            {checking || busy ? "لحظة…" : submitLabel}
          </button>
          {fallback ? (
            <button type="button" className="t2-button secondary" onClick={() => void send(fallback)} disabled={sending}>
              {FALLBACK_LABEL[fallback]}
            </button>
          ) : null}
        </div>
      </form>
    </AuthPage>
  );
}
