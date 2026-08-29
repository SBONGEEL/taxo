/** **شاشةُ دفع اشتراكٍ بكليك — تحصيلٌ يدويٌّ يُقال صراحةً** (قرارُ المالك
 * 2026-08-29).
 *
 * **ولا يُدّعى أنها بوّابةٌ آلية**: لا حسمَ يقع لحظةَ الضغط، ولا إشعارَ من
 * بنكٍ يصل الخلفية. **مشرفٌ يقرأ كشفَه ويؤكّد** — والشاشةُ تقول ذلك بنصِّها،
 * فمن ظنّها آليّةً ينتظر ما لا يأتي ويعيد الدفع.
 *
 * **والمبلغُ مكتوبٌ سلفاً ولا يُدخله أحد**: سعرُ العرض محسوباً في الخلفية
 * (§14) — لا يكتبه الكبتنُ ولا تحسبه الشاشة.
 *
 * **والرسمُ من `components/CliqClaimView`** (2026-08-30): صار للمطالبة
 * اليدوية غرضان — اشتراكٌ ودَين — **وشاشتان تنسخان الرسمَ نفسَه تفترقان أول
 * تعديل**. فبيتٌ واحد، والمختلفُ جملةُ «مؤكَّد» وحدَها.
 *
 * **وتعمل بلا صورة** (قرارُ المالك): `qr_url` قد تكون `null` — فتُعرض
 * **الحسابُ والمبلغُ والمرجع** وسطرٌ يقول إن الرمزَ لم يُرفع بعد. **ولا تسقط
 * الشاشةُ على حقلٍ فارغ**، وباركودٌ لا يعمل أسوأُ من غيابه.
 *
 * **وجملةُ الانتظار من اللوحة لا من هنا**: «تتم المراجعة خلال {min} إلى {max}
 * دقائق» — **وعدٌ لمن يدفع**، ويومَ تكثر الطلباتُ ولا تلحق المراجعةُ **يُعدَّل
 * الرقمان بلا نشر**.
 */

import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { listMyCliqClaims } from "@/api/endpoints";
import type { CliqSubscriptionClaim } from "@/api/types";
import { CliqClaimView } from "@/components/CliqClaimView";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { useGoBack } from "@/lib/back";

export function CliqSubscriptionScreen() {
  const goBack = useGoBack("/subscription");
  const { claimId } = useParams<{ claimId: string }>();
  const [claim, setClaim] = useState<CliqSubscriptionClaim | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const rows = await listMyCliqClaims();
    setClaim(rows.find((row) => row.id === claimId) ?? rows[0] ?? null);
  }, [claimId]);

  useEffect(() => {
    load().catch((caught: unknown) =>
      setError(caught instanceof ApiError ? caught.message : "تعذّرت القراءة"),
    );
  }, [load]);

  // **يُستعلَم كلَّ ١٥ ثانية ما دامت معلّقة** — والتحصيلُ يدويّ، فالانتظارُ
  // دقائق. **ويتوقف عند أيِّ حالٍ نهائية** فلا نداءٌ بلا سبب
  useEffect(() => {
    if (!claim || claim.status !== "created") return;
    const timer = window.setInterval(() => void load().catch(() => undefined), 15000);
    return () => window.clearInterval(timer);
  }, [claim, load]);

  return (
    <div className="scr h-full bg-bg px-16 pb-12 pt-safe">
      <div className="mb-16 mt-6 flex items-center gap-10">
        <button
          type="button"
          onClick={() => goBack()}
          aria-label="رجوع"
          className="pressable text-18 text-muted"
        >
          →
        </button>
        <h1 className="text-20 font-bold text-ink">الدفع بكليك</h1>
      </div>

      <ErrorNote message={error} />
      {claim === null && !error ? <Spinner className="mx-auto" /> : null}

      {claim ? (
        <CliqClaimView claim={claim} paidText="مؤكَّد — اشتراكك فُعِّل" />
      ) : null}
    </div>
  );
}
