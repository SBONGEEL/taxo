/** **شاشةُ سداد دَينٍ بكليك** — نفسُ بطاقة الاشتراك، وهو مقصود.
 *
 * **بيتٌ واحدٌ لغرضين** (`components/CliqClaimView`): الرسمُ واحدٌ لأن القضيب
 * واحد، **والمختلفُ جملةُ «مؤكَّد» وحدَها** — هناك اشتراكٌ فُعِّل، وهنا دَينٌ
 * نقص.
 */

import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { listMyDebtClaims } from "@/api/endpoints";
import type { DebtClaim } from "@/api/types";
import { CliqClaimView } from "@/components/CliqClaimView";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { useGoBack } from "@/lib/back";

export function DebtCliqScreen() {
  const goBack = useGoBack("/account/debt");
  const { claimId } = useParams<{ claimId: string }>();
  const [claim, setClaim] = useState<DebtClaim | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const rows = await listMyDebtClaims();
    setClaim(rows.find((row) => row.id === claimId) ?? rows[0] ?? null);
  }, [claimId]);

  useEffect(() => {
    load().catch((caught: unknown) =>
      setError(caught instanceof ApiError ? caught.message : "تعذّرت القراءة"),
    );
  }, [load]);

  // **يُستعلَم كلَّ ١٥ ثانية ما دامت معلّقة**، ويتوقف عند أيِّ حالٍ نهائية
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
        <h1 className="text-20 font-bold text-ink">سداد المستحقّات</h1>
      </div>

      <ErrorNote message={error} />
      {claim === null && !error ? <Spinner className="mx-auto" /> : null}

      {claim ? (
        <CliqClaimView
          claim={claim}
          paidText="مؤكَّد — نقص من مستحقّاتك"
        />
      ) : null}
    </div>
  );
}
