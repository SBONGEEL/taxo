/** **شاشةُ سداد دَينٍ بكليك** — TAXO 2.0 «C21» (`design/t2-new/captain/C21c-debt-cliq.dc.html`) — نفسُ قسيمة الاشتراك، وهو مقصود.
 *
 * **بيتٌ واحدٌ لغرضين** (`components/CliqClaimView`): الرسمُ واحدٌ لأن القضيب واحد، **والمختلفُ جملةُ «مؤكَّد» وحدَها** — هناك
 * اشتراكٌ فُعِّل، وهنا دَينٌ نقص. **والمنطقُ هو هو** (القراءةُ والاستعلامُ كلَّ ١٥ ثانية ما دامت معلّقة)؛ والرأسُ رأسُ C10 · C12.
 */

import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { listMyDebtClaims } from "@/api/endpoints";
import type { DebtClaim } from "@/api/types";
import { CliqClaimView } from "@/components/CliqClaimView";
import { Spinner } from "@/components/ui/Feedback";
import { useGoBack } from "@/lib/back";
import { Icon } from "@/taxo2";

import "./t2/money.css";

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
    <div className="t2 t2-clq-page scr">
      <div className="t2-head">
        <button
          type="button"
          className="t2-back"
          aria-label="رجوع"
          onClick={() => goBack()}
        >
          <Icon name="arrow_forward" />
        </button>
        <h1 className="t2-title">سداد المستحقّات</h1>
      </div>

      {error ? (
        <p className="t2-note danger" role="alert">
          <Icon name="error" fill />
          {error}
        </p>
      ) : null}
      {claim === null && !error ? (
        <div className="t2-money-wait">
          <Spinner />
        </div>
      ) : null}

      {claim ? (
        <CliqClaimView
          claim={claim}
          paidText="مؤكَّد — نقص من مستحقّاتك"
        />
      ) : null}
    </div>
  );
}
