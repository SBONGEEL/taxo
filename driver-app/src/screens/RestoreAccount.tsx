/** **شاشةُ الاستعادة في المهلة** — للكبتن بعد الدخول (SPEC §59-ج).
 *
 * **والفرقُ عن الراكب بابٌ واحد**: المحفظة. **المهلةُ وقتُ سحب رصيده** — ولا
 * يُحذف حسابٌ فيه رصيد — فزرُّ «سحب الرصيد» يفتح المحفظةَ وحدَها من التطبيق،
 * والحارسُ في `App.tsx` يتركها مفتوحةً في المهلة.
 *
 * **تُعرض مكانَ كلِّ شاشةٍ محميّة** (`Guarded` في `App.tsx`) ما دام `deletion_due_at` قائماً — **فشريطُ التبويب فوقها** في
 * مسارات التبويب، ولها حشوتُه. **بلغة TAXO 2.0** «C26d» (`design/t2-new/captain/C26d-restore.dc.html`): شاشةُ حالٍ بلغة «C03» —
 * حلقةٌ بأيقونة، وعنوانٌ ٢٦، وسطرٌ خافت — والسحبُ زرُّ «C09»، والاستعادةُ زرُّ الجمر. **والمنطقُ حرفاً.**
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getDeletionState, restoreAccount } from "@/api/endpoints";
import type { DeletionState } from "@/api/types";
import { DELETION_TEXT as T } from "@/lib/deletion-text";
import { useSession } from "@/lib/session";
import { formatDue, moneyText } from "@/screens/DeleteAccount";
import { Icon } from "@/taxo2";

import "@/screens/t2/account.css";

export function RestoreAccountScreen({ dueAt }: { dueAt: string }) {
  const navigate = useNavigate();
  const { refreshUser, signOut } = useSession();
  const [state, setState] = useState<DeletionState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDeletionState()
      .then(setState)
      .catch(() => undefined);
  }, []);

  async function restore() {
    setBusy(true);
    setError(null);
    try {
      await restoreAccount();
      await refreshUser();
      navigate("/", { replace: true });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر التنفيذ");
    } finally {
      setBusy(false);
    }
  }

  const deferred = state?.deferred_reason;
  const driverBalance = state ? Number(state.driver_balance) : 0;
  return (
    <div className="t2 t2-rst">
      <div className="t2-rst-ring" aria-hidden="true">
        <span className="t2-rst-track" />
        <span className="t2-rst-arc" />
        <span className="t2-rst-core">
          <Icon name="event_upcoming" />
        </span>
      </div>

      <h1 className="t2-rst-title">{T.restoreTitle}</h1>
      <p className="t2-rst-lede">{T.restoreBody(formatDue(dueAt))}</p>
      {state?.forfeit_amount ? (
        <p className="t2-rst-lede">
          {T.confirmForfeit(moneyText(state.forfeit_amount, state.currency))}
        </p>
      ) : null}

      {state && driverBalance > 0 ? (
        <section className="t2-ax-card">
          <p className="t2-rst-text">
            {T.restoreDriverBalance(moneyText(state.driver_balance, state.currency))}
          </p>
          <button type="button" className="t2-rst-withdraw" onClick={() => navigate("/wallet")}>
            <Icon name="south_west" />
            {T.withdrawButton}
          </button>
        </section>
      ) : null}

      {deferred ? (
        <section className="t2-callout warn" role="status">
          <Icon name="info" fill />
          <div className="t2-callout-main">
            <p className="t2-callout-title">{T.deferredTitle}</p>
            <p className="t2-callout-body">{T.deferred[deferred] ?? deferred}</p>
          </div>
        </section>
      ) : null}

      <div className="t2-rst-push" />

      {error ? (
        <p className="t2-note danger" role="alert">
          <Icon name="error" />
          {error}
        </p>
      ) : null}

      <button
        type="button"
        className="t2-ax-cta t2-rst-cta"
        disabled={busy}
        onClick={() => void restore()}
      >
        {busy ? "…" : T.restoreButton}
      </button>
      <button
        type="button"
        className="t2-rst-out"
        disabled={busy}
        onClick={() => void signOut()}
      >
        {T.signOutButton}
      </button>
    </div>
  );
}
