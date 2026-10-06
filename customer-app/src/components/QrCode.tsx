/** يرسم حمولةً نصّية رمزاً مربّعاً — **يرسمها ولا يبنيها**.
 *
 * الحمولة تأتي من الخلفية جاهزةً (`cliq_charge.qr_payload`): تحمل alias
 * المستفيد والمبلغ ومرجعاً يُحاسَب عليه، وبناؤها في الخلفية حصراً (SPEC
 * القسم 14). هذا المكوّن لا يعرف من محتواها شيئاً — ولو عرف لصار طرفاً في
 * تحديد ما يُدفع.
 *
 * **بإطار TAXO 2.0** (`money.css` — لوحتا R16b · R19b): أسودُ على أبيضَ في كلِّ سِمة، والإطارُ يتبع المظهر.
 */

import { useEffect, useState } from "react";
import QRCode from "qrcode";

import { useTheme } from "@/lib/theme";

import "@/screens/t2/money.css";

export function QrCode({
  payload,
  size = 196,
}: {
  payload: string;
  size?: number;
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

  return (
    <div className="t2-m-qr-wrap">
      {dataUrl ? (
        <img src={dataUrl} alt="رمز الدفع" width={size} height={size} className="t2-m-qr" />
      ) : (
        <span className="t2-m-qr-wait" style={{ width: size, height: size }} aria-hidden="true" />
      )}
    </div>
  );
}
