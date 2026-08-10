/** يرسم حمولةً نصّية رمزاً مربّعاً — **يرسمها ولا يبنيها**.
 *
 * الحمولة تأتي من الخلفية جاهزةً (`cliq_charge.qr_payload`): تحمل alias
 * المستفيد والمبلغ ومرجعاً يُحاسَب عليه، وبناؤها في الخلفية حصراً (SPEC
 * القسم 14). هذا المكوّن لا يعرف من محتواها شيئاً — ولو عرف لصار طرفاً في
 * تحديد ما يُدفع.
 */

import { useEffect, useState } from "react";
import QRCode from "qrcode";

import { useTheme } from "@/lib/theme";
import { cn } from "@/lib/utils";

export function QrCode({
  payload,
  size = 220,
  className,
}: {
  payload: string;
  size?: number;
  className?: string;
}) {
  const [dataUrl, setDataUrl] = useState<string | null>(null);
  const { dark } = useTheme();

  useEffect(() => {
    let cancelled = false;
    QRCode.toDataURL(payload, {
      width: size * 2,
      margin: 1,
      errorCorrectionLevel: "M",
      // خلفيةٌ بيضاء دائماً ولو في الوضع الليلي: قارئات البنوك تتوقع تبايناً
      // داكناً على فاتح، ورمزٌ معكوس لا يُقرأ على بعض الأجهزة
      color: { dark: "#000000", light: "#ffffff" },
    })
      .then((url) => !cancelled && setDataUrl(url))
      .catch(() => !cancelled && setDataUrl(null));

    return () => {
      cancelled = true;
    };
  }, [payload, size, dark]);

  if (!dataUrl) {
    return (
      <div
        className={cn("animate-pulse rounded-xl bg-line", className)}
        style={{ width: size, height: size }}
      />
    );
  }

  return (
    <img
      src={dataUrl}
      alt="رمز الدفع"
      width={size}
      height={size}
      className={cn("rounded-xl bg-white p-2", className)}
    />
  );
}
