/** إثبات ملكية الرقم — شاشةٌ واحدة بمُحقِّقين (SPEC القسم 12/1 و15/أ).
 *
 * **الواجهة لا تفترض المُحقِّق**: تقرؤه من `GET /config` — و**من صفِّ دولة
 * الحساب** (`countries[].verification`) لا من `auth.verification` الذي يخصّ
 * الدولةَ الافتراضية (12-هـ). وترسم التدفّق المناسب، ولا تعرف ترتيب المُحقِّقين
 * ولا تختار بينهم — ذاك قرارُ `services/verification.py` وحده.
 *
 * | المُحقِّق | من يرسل الرمز | ما يصل الخلفية |
 * |---|---|---|
 * | `firebase` | Firebase من جهاز الكبتن | **رمز الهوية** بعد إدخال الرمز |
 * | `sms_otp`  | خلفيتنا عبر مزود SMS     | **الرمز** نفسه كما كتبه |
 * | `whatsapp_otp` | خلفيتنا عبر WhatsApp Cloud API | **الرمز** نفسه (12-هـ) |
 * | `none`     | لا أحد                    | لا شيء — الخطوة تُتخطى |
 *
 * **وفشلُ قناةٍ لا يترك الكبتن عالقاً**: الخلفية تردّ الخطأ ومعه
 * `fallback_channel`، فيُرسم زرُّ القناة التالية. ولا ارتدادَ صامت: الرمزُ ربما
 * وصل، وتبديلٌ لا يعلمه صاحبُه يجعله يكتب رمزاً من قناةٍ أخرى.
 *
 * والشكل من `design/DESIGN.md` §5.3 (شاشة «تحقق من رقمك»): عنوان 24/700،
 * نصٌّ فرعي 13 بسطرٍ 1.6، الخانات، زرٌّ أساسي، ثم سطرُ إعادة الإرسال 12.5.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/api/client";
import type {
  ChallengeResponse,
  OtpChannel,
  VerificationMethod,
} from "@/api/types";
import { OtpBoxes } from "@/components/OtpBoxes";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { firebaseConfigOf, useConfig } from "@/lib/config";
import { startPhoneVerification, type PhoneChallenge } from "@/lib/firebase";
import { digits } from "@/lib/utils";

const RECAPTCHA_CONTAINER = "taxo-recaptcha";

/** نصُّ القناة التي وصل فيها الرمز فعلاً (12-هـ).
 *
 * ليس تجميلاً: من ينتظر رسالةً نصيةً وقد وصله واتساب يفتح تطبيقاً خطأً ثم يضغط
 * «إعادة الإرسال» — وكلُّ إعادةٍ رسالةٌ مدفوعة. والقناةُ تأتي من الخلفية لا
 * تُخمَّن هنا: هي وحدها تعرف أيَّ عقدٍ أرسل.
 */
const CHANNEL_LABEL: Record<string, string> = {
  whatsapp_otp: "في واتساب",
  sms_otp: "برسالة نصية",
};

const FALLBACK_LABEL: Record<string, string> = {
  whatsapp_otp: "أرسله في واتساب",
  sms_otp: "أرسله برسالة نصية",
};


interface Props {
  /** بصيغة E.164 جاهزةً — يبنيها المستدعي من بادئة `GET /config`. */
  phone: string;
  method: VerificationMethod;
  otpLength: number | null;
  title: string;
  subtitle: string;
  /** يبدأ التحدي عند قناةٍ نرسل منها — مسارُ الاستعادة غير مسار التسجيل. */
  requestChallenge: (channel?: OtpChannel) => Promise<ChallengeResponse>;
  /** يسلّم **إثباتاً** جاهزاً للإرسال مع بقية الطلب. */
  onProven: (verificationToken: string) => void;
  submitting?: boolean;
}

export function PhoneVerification({
  phone,
  method,
  otpLength,
  title,
  subtitle,
  requestChallenge,
  onProven,
  submitting = false,
}: Props) {
  const { config } = useConfig();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(true);
  const [cooldown, setCooldown] = useState(0);
  const [channel, setChannel] = useState<string | null>(null);
  const [fallback, setFallback] = useState<OtpChannel | null>(null);
  const challenge = useRef<PhoneChallenge | null>(null);

  const e164 = phone;
  const codeLength = otpLength ?? 6;

  const send = useCallback(async (pick?: OtpChannel) => {
    setSending(true);
    setError(null);
    setFallback(null);
    try {
      if (method === "firebase") {
        const firebase = firebaseConfigOf(config?.providers.firebase_auth);
        if (!firebase) {
          // **جملةُ من يقرؤها لا جملةُ من يصلحها** (2026-08-14): كانت
          // «راجع عقد المزود في لوحة الإدارة» — وهي تعليماتٌ لمشرفٍ وصلت
          // راكباً على هاتفه، فقرأ اسمَ نظامٍ لا يعرفه وطُلب منه فتحُ لوحةٍ
          // لا يملكها. والسببُ الفنيُّ يبقى في `console` لمن يفتحه.
          console.error("firebase config missing in GET /config providers");
          throw new Error("التحقق من رقم هاتفك غير متاح حالياً. حاول بعد قليل.");
        }
        challenge.current = await startPhoneVerification(
          firebase,
          e164,
          RECAPTCHA_CONTAINER,
        );
        setCooldown(60);
        return;
      }
      const response = await requestChallenge(pick);
      // `sent=false` ليست خطأً: مُحقِّقٌ لا يحتاج تحدياً من عندنا
      setChannel(response.channel);
      setCooldown(response.resend_after ?? 60);
    } catch (caught) {
      setError(
        caught instanceof ApiError || caught instanceof Error
          ? caught.message
          : "تعذّر إرسال رمز التحقق",
      );
      // القناةُ التالية تأتي من الخلفية — وغيابُها يعني ألّا مخرجَ آخر، فلا
      // يُرسم زرٌّ لا يعمل
      const next =
        caught instanceof ApiError ? caught.field("fallback_channel") : null;
      setFallback(
        next === "sms_otp" || next === "whatsapp_otp" ? next : null,
      );
    } finally {
      setSending(false);
    }
  }, [config, e164, method, requestChallenge]);

  useEffect(() => {
    void send();
    // مرةً واحدة عند فتح الخطوة؛ ما بعدها بزرّ «إعادة الإرسال»
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setTimeout(
      () => setCooldown((value) => value - 1),
      1_000,
    );
    return () => window.clearTimeout(timer);
  }, [cooldown]);

  async function submit() {
    setError(null);
    try {
      if (method === "firebase") {
        if (!challenge.current) throw new Error("أعد إرسال الرمز أولاً");
        onProven(await challenge.current.confirm(code));
        return;
      }
      // مزود SMS: الرمز نفسه هو الإثبات، وتفحصه الخلفية
      onProven(code);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "رمز التحقق غير صحيح أو انتهت صلاحيته",
      );
    }
  }

  return (
    <>
      <h1 className="mt-24 text-24 font-bold text-ink">{title}</h1>
      <p className="mt-8 text-13 leading-snug text-muted">
        {subtitle}
        {channel && CHANNEL_LABEL[channel] ? ` · أُرسل ${CHANNEL_LABEL[channel]}` : ""}
      </p>

      <OtpBoxes
        value={code}
        onChange={setCode}
        length={codeLength}
        disabled={sending}
      />

      {/* الفجوة تقع بين عنصرين مرسومين فقط: بلا خطأٍ يلتصق الزرُّ بالخانات
          كما في التصميم (هامشها `34px 0` هو كل المسافة) */}
      <div className="flex flex-col gap-14">
        <ErrorNote message={error} />

        {/* عنصرٌ فارغ يعلّق عليه reCAPTCHA نفسه — غير مرئي ولازم للحزمة */}
        <div id={RECAPTCHA_CONTAINER} className="empty:hidden" />

        <Button
          onClick={submit}
          loading={submitting}
          disabled={code.length < codeLength || sending}
        >
          تحقق
        </Button>

        {/* مخرجُ القناة التالية — يظهر عند فشل الإرسال وحده */}
        {fallback ? (
          <Button
            variant="secondary"
            onClick={() => void send(fallback)}
            disabled={sending}
          >
            {FALLBACK_LABEL[fallback]}
          </Button>
        ) : null}
      </div>

      <button
        type="button"
        onClick={() => void send()}
        disabled={cooldown > 0 || sending}
        className="pressable mt-16 w-full text-center text-12.5 text-muted disabled:opacity-100"
      >
        {cooldown > 0
          ? `إعادة الإرسال خلال 0:${digits(String(cooldown).padStart(2, "0"))}`
          : "إعادة إرسال الرمز"}
      </button>
    </>
  );
}
