/** **شاشةُ الاستعادة في المهلة** — تُرسم بعد الدخول لكلِّ حسابٍ مجدولٍ للحذف (SPEC §59-ج).
 *
 * **والاستعادةُ فعلٌ صريحٌ لا أثرٌ جانبيٌّ للدخول**: من دخل ليرى التاريخَ لا
 * يُلغى طلبُه بلا قصد. زرّان: «استعادة الحساب» و«تسجيل الخروج».
 *
 * **ويقول سببَ التأجيل إن حلّ الموعدُ ولم يقع** — رصيدٌ تغيّر بعد الموافقة
 * مثلاً — فلا يظنّ صاحبُه أن حسابَه حُذف وهو باقٍ.
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getDeletionState, restoreAccount } from "@/api/endpoints";
import type { DeletionState } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/Feedback";
import { DELETION_TEXT as T } from "@/lib/deletion-text";
import { useSession } from "@/lib/session";
import { formatDateTime, formatMoney } from "@/lib/utils";

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
  return (
    <div className="scr h-full bg-bg px-16 pb-nav pt-safe">
      <h1 className="mb-16 mt-6 text-20 font-bold text-ink">{T.restoreTitle}</h1>

      <section className="mb-12 card p-15">
        <p className="text-12.5 leading-note text-ink">{T.restoreBody(formatDateTime(dueAt))}</p>
        {state?.forfeit_amount ? (
          <p className="mt-6 text-11.5 leading-note text-muted">
            {T.confirmForfeit(formatMoney(state.forfeit_amount, state.currency))}
          </p>
        ) : null}
      </section>

      {deferred ? (
        <section className="mb-12 rounded-18 border border-warn bg-surface p-15">
          <p className="text-13.5 font-semibold text-warn">{T.deferredTitle}</p>
          <p className="mt-6 text-12 leading-note text-muted">{T.deferred[deferred] ?? deferred}</p>
        </section>
      ) : null}

      <div className="flex gap-10">
        <Button loading={busy} onClick={() => void restore()}>
          {T.restoreButton}
        </Button>
        <Button variant="secondary" disabled={busy} onClick={() => void signOut()}>
          {T.signOutButton}
        </Button>
      </div>

      {error ? (
        <div className="mt-12">
          <ErrorNote message={error} />
        </div>
      ) : null}
    </div>
  );
}
