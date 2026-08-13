/** إثبات ملكية الرقم — خطوةٌ واحدة بمُحقِّقين (SPEC القسم 11.1/15-أ).
 *
 * **الواجهة لا تفترض المُحقِّق**: تقرؤه من `/config` **من صفِّ دولة الحساب**
 * (`countries[].verification`) لا من `auth.verification` الذي يخصّ الدولةَ
 * الافتراضية (12-هـ). وترسم التدفّق المناسب — ولا تعرف ترتيب المُحقِّقين ولا
 * تختار بينهم، ذاك قرارُ `services/verification.py` وحده.
 *
 * | المُحقِّق | من يرسل الرمز | ما يصل الخلفية |
 * |---|---|---|
 * | `firebase` | Firebase من جهاز المستخدم | **رمز الهوية** بعد إدخال الرمز |
 * | `sms_otp`  | خلفيتنا عبر مزود SMS      | **الرمز** نفسه كما كتبه |
 * | `whatsapp_otp` | خلفيتنا عبر WhatsApp Cloud API | **الرمز** نفسه (12-هـ) |
 * | `none`     | لا أحد                     | لا شيء — الخطوة تُتخطى |
 *
 * **وفشلُ قناةٍ لا يترك الراكب عالقاً**: الخلفية تردّ الخطأ ومعه
 * `fallback_channel`، فيُرسم زرُّ القناة التالية. ولا ارتدادَ صامت: الرمزُ ربما
 * وصل، وتبديلٌ لا يعلمه صاحبُه يجعله يكتب رمزاً من قناةٍ أخرى.
 *
 * ويقع هذا الإثبات **مرتين لا أكثر في عمر الحساب**: عند التسجيل وعند
 * الاستعادة (SPEC القسم 2)، ولذلك مكوّنٌ واحد يخدم الشاشتين.
 */

import { motion } from "framer-motion";
import { ChevronRight, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/api/client";
import type {
  ChallengeResponse,
  OtpChannel,
  VerificationMethod,
} from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { Field } from "@/components/ui/Field";
import { firebaseConfigOf, useConfig } from "@/lib/config";
import { startPhoneVerification, type PhoneChallenge } from "@/lib/firebase";
import { toE164 } from "@/lib/phone";

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
  phone: string;
  /** بادئةُ الدولة من `GET /config` — بها تُبنى E.164 لتدفّق Firebase. */
  dialCode: string;
  method: VerificationMethod;
  otpLength: number | null;
  /** يبدأ التحدي عند قناةٍ نرسل منها — مسارُ التسجيل غير مسار الاستعادة. */
  requestChallenge: (channel?: OtpChannel) => Promise<ChallengeResponse>;
  /** يسلّم **إثباتاً** جاهزاً للإرسال مع بقية الطلب. */
  onProven: (verificationToken: string) => void;
  onBack: () => void;
  /** مغادرةُ المصادقة كلِّها — سهمُ التصميم أعلى شاشة الرمز.
   *
   * **مخرجان لا واحد، وهما مختلفان**: «تعديل الرقم» يصحّح خطأً في الرقم ويبقى
   * في التدفّق، والسهمُ يغادره إلى الدخول. والتصميمُ يرسم الثاني وحدَه، وكان
   * المبنيُّ يرسم الأولَ وحدَه — فمن فتح الشاشة بالخطأ لم يجد بابَ خروج.
   */
  onLeave?: () => void;
}

export function PhoneVerification({
  phone,
  dialCode,
  method,
  otpLength,
  requestChallenge,
  onProven,
  onBack,
  onLeave,
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

  const e164 = toE164(phone, dialCode);
  const digits = otpLength ?? 6;

  const send = useCallback(async (pick?: OtpChannel) => {
    setSending(true);
    setError(null);
    setFallback(null);
    try {
      if (method === "firebase") {
        const firebase = firebaseConfigOf(config?.providers.firebase_auth);
        if (!firebase) {
          throw new Error(
            "إعداد Firebase غير مكتمل — راجع عقد المزود في لوحة الإدارة",
          );
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
      setFallback(next === "sms_otp" || next === "whatsapp_otp" ? next : null);
    } finally {
      setSending(false);
    }
  }, [config, e164, method, requestChallenge]);

  useEffect(() => {
    void send();
    // مرةً واحدة عند فتح الخطوة؛ ما بعدها بزر «إعادة الإرسال»
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
    setChecking(true);
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
    } finally {
      setChecking(false);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: 24 }}
      animate={{ opacity: 1, x: 0 }}
      className="space-y-20"
    >
      {onLeave ? (
        <button
          type="button"
          onClick={onLeave}
          aria-label="رجوع"
          className="pressable -ms-8 -mt-8 block rounded-full p-8 text-muted transition hover:bg-surface-2"
        >
          <ChevronRight className="size-20" />
        </button>
      ) : null}

      <div className="flex items-start gap-12 rounded-16 border border-line bg-surface p-16">
        <ShieldCheck className="mt-2 size-20 text-brand" />
        <div className="text-14">
          <p className="font-medium text-ink">
            {channel && CHANNEL_LABEL[channel]
              ? `أرسلنا رمز التحقق ${CHANNEL_LABEL[channel]} إلى`
              : "أرسلنا رمز التحقق إلى"}
          </p>
          <p dir="ltr" className="mt-2 text-muted">
            {e164}
          </p>
        </div>
      </div>

      <Field
        label="رمز التحقق"
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={digits}
        value={code}
        onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))}
        placeholder={"٠".repeat(digits)}
        className="text-center text-24 tracking-[0.5em]"
        dir="ltr"
      />

      <ErrorNote message={error} />

      {/* عنصرٌ فارغ يعلّق عليه reCAPTCHA نفسه — غير مرئي ولازم للحزمة */}
      <div id={RECAPTCHA_CONTAINER} />

      <Button
        size="lg"
        onClick={submit}
        loading={checking}
        disabled={code.length < digits || sending}
      >
        تأكيد الرمز
      </Button>

      {/* مخرجُ القناة التالية — يظهر عند فشل الإرسال وحده */}
      {fallback ? (
        <Button
          size="lg"
          variant="secondary"
          onClick={() => void send(fallback)}
          disabled={sending}
        >
          {FALLBACK_LABEL[fallback]}
        </Button>
      ) : null}

      <div className="flex items-center justify-between text-14">
        <button
          type="button"
          onClick={onBack}
          className="pressable text-muted hover:text-ink"
        >
          تعديل الرقم
        </button>
        <button
          type="button"
          onClick={() => void send()}
          disabled={cooldown > 0 || sending}
          className="pressable font-medium text-ink disabled:text-muted"
        >
          {cooldown > 0
            ? `إعادة الإرسال بعد ${cooldown} ثانية`
            : "إعادة إرسال الرمز"}
        </button>
      </div>
    </motion.div>
  );
}
