/** يرسم نصّاً رمزاً مربّعاً — **يرسمه ولا يبنيه**، و**محلياً لا بخدمة**.
 *
 * الحمولةُ هنا `otpauth://` تحمل **سرَّ العامل الثاني** (SPEC §14.1)، فأيُّ
 * خدمةِ QR خارجية — صورةٌ من `chart.googleapis.com` أو ما شابه — تعني إرسالَ
 * السرِّ إلى طرفٍ ثالث في نداءٍ لا يراه أحد. وهي أسهلُ خطأٍ في هذه الميزة كلها،
 * ولذلك الرسمُ في المتصفح ولا شبكةَ فيه.
 *
 * ونسخةٌ من `customer-app/src/components/QrCode.tsx` بنفس القواعد: خلفيةٌ
 * بيضاء دائماً ولو في الوضع الليلي — الكاميراتُ تتوقع داكناً على فاتح، ورمزٌ
 * معكوس لا يُقرأ على بعض الأجهزة.
 */

import QRCode from "qrcode";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

export function QrCode({
  payload,
  size = 200,
  className,
}: {
  payload: string;
  size?: number;
  className?: string;
}) {
  const [dataUrl, setDataUrl] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    QRCode.toDataURL(payload, {
      width: size * 2,
      margin: 1,
      errorCorrectionLevel: "M",
      color: { dark: "#000000", light: "#ffffff" },
    })
      .then((url) => !cancelled && setDataUrl(url))
      .catch(() => !cancelled && setDataUrl(null));

    return () => {
      cancelled = true;
    };
  }, [payload, size]);

  if (!dataUrl) {
    return (
      <div
        className={cn("animate-pulse rounded-12 bg-line", className)}
        style={{ width: size, height: size }}
      />
    );
  }

  return (
    <img
      src={dataUrl}
      alt="رمز إعداد التحقق الثنائي"
      width={size}
      height={size}
      className={cn("rounded-12 bg-white p-8", className)}
    />
  );
}
