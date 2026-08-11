/** إثبات ملكية الرقم — خطوةٌ واحدة بمُحقِّقين (SPEC القسم 11.1/15-أ).
 *
 * **الواجهة لا تفترض المُحقِّق**: تقرؤه من `GET /auth/method` (`verification`)
 * وترسم التدفّق المناسب — ولا تعرف ترتيب المُحقِّقين ولا تختار بينهما، ذاك
 * قرارُ `services/verification.py` وحده.
 *
 * | المُحقِّق | من يرسل الرمز | ما يصل الخلفية |
 * |---|---|---|
 * | `firebase` | Firebase من جهاز المستخدم | **رمز الهوية** بعد إدخال الرمز |
 * | `sms_otp`  | خلفيتنا عبر مزود SMS      | **الرمز** نفسه كما كتبه |
 * | `none`     | لا أحد                     | لا شيء — الخطوة تُتخطى |
 *
 * ويقع هذا الإثبات **مرتين لا أكثر في عمر الحساب**: عند التسجيل وعند
 * الاستعادة (SPEC القسم 2)، ولذلك مكوّنٌ واحد يخدم الشاشتين.
 */

import { motion } from "framer-motion";
import { ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/api/client";
import type { ChallengeResponse, VerificationMethod } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { Field } from "@/components/ui/Field";
import { firebaseConfigOf, useConfig } from "@/lib/config";
import { startPhoneVerification, type PhoneChallenge } from "@/lib/firebase";
import { toE164 } from "@/lib/phone";

const RECAPTCHA_CONTAINER = "taxo-recaptcha";

interface Props {
  phone: string;
  /** بادئةُ الدولة من `GET /config` — بها تُبنى E.164 لتدفّق Firebase. */
  dialCode: string;
  method: VerificationMethod;
  otpLength: number | null;
  /** يبدأ التحدي عند مزود SMS — مسارُ التسجيل غير مسار الاستعادة. */
  requestChallenge: () => Promise<ChallengeResponse>;
  /** يسلّم **إثباتاً** جاهزاً للإرسال مع بقية الطلب. */
  onProven: (verificationToken: string) => void;
  onBack: () => void;
}

export function PhoneVerification({
  phone,
  dialCode,
  method,
  otpLength,
  requestChallenge,
  onProven,
  onBack,
}: Props) {
  const { config } = useConfig();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(true);
  const [checking, setChecking] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const challenge = useRef<PhoneChallenge | null>(null);

  const e164 = toE164(phone, dialCode);
  const digits = otpLength ?? 6;

  const send = useCallback(async () => {
    setSending(true);
    setError(null);
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

      const response = await requestChallenge();
      // `sent=false` ليست خطأً: مُحقِّقٌ لا يحتاج تحدياً من عندنا
      setCooldown(response.resend_after ?? 60);
    } catch (caught) {
      setError(
        caught instanceof ApiError || caught instanceof Error
          ? caught.message
          : "تعذّر إرسال رمز التحقق",
      );
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
      <div className="flex items-start gap-12 rounded-16 border border-line bg-surface p-16">
        <ShieldCheck className="mt-2 size-20 text-brand" />
        <div className="text-14">
          <p className="font-medium text-ink">أرسلنا رمز التحقق إلى</p>
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

      <div className="flex items-center justify-between text-14">
        <button
          type="button"
          onClick={onBack}
          className="text-muted hover:text-ink"
        >
          تعديل الرقم
        </button>
        <button
          type="button"
          onClick={send}
          disabled={cooldown > 0 || sending}
          className="font-medium text-ink disabled:text-muted"
        >
          {cooldown > 0
            ? `إعادة الإرسال بعد ${cooldown} ثانية`
            : "إعادة إرسال الرمز"}
        </button>
      </div>
    </motion.div>
  );
}
