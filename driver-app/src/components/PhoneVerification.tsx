/** إثبات ملكية الرقم — شاشةٌ واحدة بمُحقِّقين (SPEC القسم 12/1 و15/أ).
 *
 * **الواجهة لا تفترض المُحقِّق**: تقرؤه من `GET /config` (`auth.verification`)
 * وترسم التدفّق المناسب. ولا تعرف ترتيب المُحقِّقين ولا تختار بينهما — ذاك
 * قرارُ `services/verification.py` وحده.
 *
 * | المُحقِّق | من يرسل الرمز | ما يصل الخلفية |
 * |---|---|---|
 * | `firebase` | Firebase من جهاز الكبتن | **رمز الهوية** بعد إدخال الرمز |
 * | `sms_otp`  | خلفيتنا عبر مزود SMS     | **الرمز** نفسه كما كتبه |
 * | `none`     | لا أحد                    | لا شيء — الخطوة تُتخطى |
 *
 * والشكل من `design/DESIGN.md` §5.3 (شاشة «تحقق من رقمك»): عنوان 24/700،
 * نصٌّ فرعي 13 بسطرٍ 1.6، الخانات، زرٌّ أساسي، ثم سطرُ إعادة الإرسال 12.5.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "@/api/client";
import type { ChallengeResponse, CountryCode, VerificationMethod } from "@/api/types";
import { OtpBoxes } from "@/components/OtpBoxes";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { firebaseConfigOf, useConfig } from "@/lib/config";
import { startPhoneVerification, type PhoneChallenge } from "@/lib/firebase";
import { toE164 } from "@/lib/phone";
import { arabicDigits } from "@/lib/utils";

const RECAPTCHA_CONTAINER = "taxo-recaptcha";

interface Props {
  phone: string;
  country: CountryCode | undefined;
  method: VerificationMethod;
  otpLength: number | null;
  title: string;
  subtitle: string;
  /** يبدأ التحدي عند مزود SMS — مسارُ الاستعادة غير مسار التسجيل. */
  requestChallenge: () => Promise<ChallengeResponse>;
  /** يسلّم **إثباتاً** جاهزاً للإرسال مع بقية الطلب. */
  onProven: (verificationToken: string) => void;
  submitting?: boolean;
}

export function PhoneVerification({
  phone,
  country,
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
  const challenge = useRef<PhoneChallenge | null>(null);

  // بلا دولةٍ صريحة يبقى الرقم كما كتبه صاحبه؛ والخلفية تستنتجها من صيغته
  const e164 = country ? toE164(phone, country) : phone;
  const digits = otpLength ?? 6;

  const send = useCallback(async () => {
    setSending(true);
    setError(null);
    try {
      if (method === "firebase") {
        const firebase = firebaseConfigOf(config?.providers.firebase_auth);
        if (!firebase) {
          throw new Error("إعداد Firebase غير مكتمل — راجع عقد المزود في لوحة الإدارة");
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
    // مرةً واحدة عند فتح الخطوة؛ ما بعدها بزرّ «إعادة الإرسال»
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setTimeout(() => setCooldown((value) => value - 1), 1_000);
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
        caught instanceof Error ? caught.message : "رمز التحقق غير صحيح أو انتهت صلاحيته",
      );
    }
  }

  return (
    <>
      <h1 className="mt-24 text-24 font-bold text-ink">{title}</h1>
      <p className="mt-8 text-13 leading-snug text-muted">{subtitle}</p>

      <OtpBoxes value={code} onChange={setCode} length={digits} disabled={sending} />

      {/* الفجوة تقع بين عنصرين مرسومين فقط: بلا خطأٍ يلتصق الزرُّ بالخانات
          كما في التصميم (هامشها `34px 0` هو كل المسافة) */}
      <div className="flex flex-col gap-14">
        <ErrorNote message={error} />

        {/* عنصرٌ فارغ يعلّق عليه reCAPTCHA نفسه — غير مرئي ولازم للحزمة */}
        <div id={RECAPTCHA_CONTAINER} className="empty:hidden" />

        <Button
          onClick={submit}
          loading={submitting}
          disabled={code.length < digits || sending}
        >
          تحقق
        </Button>
      </div>

      <button
        type="button"
        onClick={send}
        disabled={cooldown > 0 || sending}
        className="mt-16 w-full text-center text-12.5 text-muted disabled:opacity-100"
      >
        {cooldown > 0
          ? `إعادة الإرسال خلال ٠:${arabicDigits(String(cooldown).padStart(2, "0"))}`
          : "إعادة إرسال الرمز"}
      </button>
    </>
  );
}
