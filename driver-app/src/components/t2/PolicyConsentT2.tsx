/** الموافقةُ على السياسات في التسجيل — **منطقُ `PolicyConsent` نفسُه** (البند ١٠، §٣٤)، **وشكلُ TAXO 2.0** (`AuthConsent`)،
 * منسوخاً من تطبيق الراكب.
 *
 * **مربّعٌ يُضغط لا جملةٌ تفترض**: الوثائقُ المنشورةُ لسوق التسجيل **ولتطبيق الكبتن** (`app=driver` — نصُّ الكبتن غيرُ نصِّ الراكب،
 * §34-٢) تُقرأ من `GET /public/policies/required`، **وما وافق عليه بعينه** يُرسل مع الطلب (`accepted_policy_ids`).
 * **وقائمةٌ فارغةٌ تُبلَّغ كذلك** — لا وثيقةَ منشورة، فلا شرطَ في الزرّ. **وتعذُّرُ القراءة ليس رفضاً**: الخلفيةُ هي التي ترفض
 * التسجيلَ إن لزمت موافقةٌ ولم تصل — فلا يُمنع أحدٌ بخطأ شبكة.
 */
import { useEffect, useState } from "react";

import { requiredPolicies } from "@/api/endpoints";
import type { CountryCode, RequiredPolicy } from "@/api/types";
import { AuthConsent } from "@/taxo2";

const TITLE: Record<string, string> = {
  privacy_policy: "سياسة الخصوصية",
  terms_of_use: "شروط الاستخدام",
};

export function PolicyConsentT2({
  country,
  checked,
  onChange,
  onLoaded,
}: {
  country: CountryCode;
  checked: boolean;
  onChange: (next: boolean) => void;
  /** يُبلّغ الشاشةَ بالمعرّفات — **وبقائمةٍ فارغةٍ حين لا وثيقةَ منشورة**. */
  onLoaded: (ids: string[]) => void;
}) {
  const [docs, setDocs] = useState<RequiredPolicy[] | null>(null);

  useEffect(() => {
    let alive = true;
    requiredPolicies(country)
      .then((rows) => {
        if (!alive) return;
        setDocs(rows);
        onLoaded(rows.map((row) => row.id));
      })
      // **والصمتُ مقصود** — انظر رأس الملف
      .catch(() => {
        if (alive) setDocs([]);
      });
    return () => {
      alive = false;
    };
  }, [country, onLoaded]);

  if (!docs?.length) return null;
  return (
    <AuthConsent
      checked={checked}
      onToggle={() => onChange(!checked)}
      docs={docs.map((doc) => ({ id: doc.id, title: TITLE[doc.doc_type] ?? doc.doc_type, body: doc.body_ar }))}
    />
  );
}
