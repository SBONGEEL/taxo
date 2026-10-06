/** وجهُ الكبتن — أو أوّلُ حرفٍ من اسمه (البند ٥٢).
 *
 * **ولا حالةَ ثالثة**: إمّا صورةٌ راجعها مشرف، وإمّا الحرف. ولا مربّعٌ فارغ
 * ولا أيقونةٌ عامة — كلاهما يُقرأ **عطباً في التطبيق** لا خياراً لصاحبته،
 * فيُبلَّغ عنه ويُصلَّح بإظهار ما أُخفي عمداً.
 *
 * **والحرفُ يُرسم لسببين لا يفرّق بينهما شيءٌ في الشاشة**، وذلك بقصد:
 * سائقةٌ ثبَّتت الإدارةُ جنسَها فأُعفيت، وكبتنٌ لم تُراجَع صورتُه بعد. ولو
 * أُضيف نصٌّ يميّز الحالين لصار **غيابُ الصورة إعلاناً بأن صاحبها امرأة** —
 * وهو بعينه ما وُجد الاستثناء ليمنعه. فلا تُضاف تلك الكلمة هنا أبداً.
 *
 * **ولا حقلَ `has_photo` في الخلفية**: الطلبُ نفسُه هو الجواب — بايتاتٌ أو
 * 404. وحقلٌ ثانٍ يقول «لها صورة» بيتٌ ثانٍ للحقيقة يفترق عن الملف أوّلَ
 * مراجعةٍ تُغيّر حالَه.
 *
 * **بلغة TAXO 2.0** (`money.css` — بطاقةُ الكبتن في R08): الحرفُ في دائرةٍ مخطّطة، ومقاسُها من صنف من يناديها
 * (`t2-trk-avatar` في ورقة التتبّع، وR18 في التفاصيل) — **والدائرةُ نفسُها في الحالين** فلا تكون الصورةُ أو غيابُها شكلاً آخر.
 */

import { useEffect, useState } from "react";

import { api } from "@/api/client";

import "@/screens/t2/money.css";

export function DriverAvatar({
  rideId,
  name,
  className,
}: {
  rideId: string;
  name: string;
  className?: string;
}) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;

    api
      .blob(`/rides/${rideId}/driver/photo`)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      })
      // **الفشلُ هو الحالُ العادية لا عطب**: ٤٠٤ تعني «ارسم الحرف»، وهي جوابُ
      // المُعفاة وجوابُ من ينتظر المراجعة معاً
      .catch(() => undefined);

    return () => {
      cancelled = true;
      // **ويُحرَّر العنوان**: `createObjectURL` يحجز الصورةَ في الذاكرة حتى
      // يُلغى، وشاشةُ تتبّعٍ تُفتح عشرَ مرات تحجز عشرَ نسخ
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [rideId]);

  const base = className ? `t2-m-avatar ${className}` : "t2-m-avatar";

  if (src) {
    return (
      <span className={base}>
        {/* **وصفٌ فارغٌ بقصد**: الاسمُ مكتوبٌ بجانبها، ووصفٌ يكرّره يجعل قارئَ الشاشة يقوله مرتين */}
        <img src={src} alt="" />
      </span>
    );
  }

  return <span className={base}>{name.slice(0, 1)}</span>;
}
