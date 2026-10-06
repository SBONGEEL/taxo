/** **شاشةُ الاستعادة في المهلة** — TAXO 2.0 «R27d» (`design/t2-new/rider/R27d-restore-account.dc.html`)، **في المظهرين
 *  والنسائيّ** — تُرسم بعد الدخول لكلِّ حسابٍ مجدولٍ للحذف (SPEC §59-ج)، **من كلِّ مسار** (`App.tsx::Guarded`).
 *
 * **والاستعادةُ فعلٌ صريحٌ لا أثرٌ جانبيٌّ للدخول**: من دخل ليرى التاريخَ لا
 * يُلغى طلبُه بلا قصد. زرّان: «استعادة الحساب» و«تسجيل الخروج».
 *
 * **ويقول سببَ التأجيل إن حلّ الموعدُ ولم يقع** — رصيدٌ تغيّر بعد الموافقة
 * مثلاً — فلا يظنّ صاحبُه أن حسابَه حُذف وهو باقٍ.
 *
 * **ولا شريطَ تبويبٍ تحتها**: كلُّ وجهةٍ فيه تعيد هذه الشاشةَ نفسَها في المهلة (`Guarded`) — فكانت أربعةَ أزرارٍ لا تفعل
 * شيئاً. **والصفحةُ بلغة R10**: ما يُقرأ فوق، والزرّان أسفلَ الشاشة.
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getDeletionState, restoreAccount } from "@/api/endpoints";
import type { DeletionState } from "@/api/types";
import { DELETION_TEXT as T } from "@/lib/deletion-text";
import { useCoverNav } from "@/lib/navCover";
import { useSession } from "@/lib/session";
import { formatDateTime, formatMoney } from "@/lib/utils";
import { NoteT2 } from "@/screens/t2/KitT2";
import { Icon } from "@/taxo2";

import "@/screens/t2/restore.css";

export function RestoreAccountScreen({ dueAt }: { dueAt: string }) {
  const navigate = useNavigate();
  const { refreshUser, signOut } = useSession();
  const [state, setState] = useState<DeletionState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useCoverNav(true);

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
    <div className="t2 t2-restore">
      <span className="t2-restore-icon">
        <Icon name="hourglass_top" />
      </span>
      <h1 className="t2-restore-title">{T.restoreTitle}</h1>
      <p className="t2-restore-body">{T.restoreBody(formatDateTime(dueAt))}</p>
      {state?.forfeit_amount ? (
        <p className="t2-restore-fine">{T.confirmForfeit(formatMoney(state.forfeit_amount, state.currency))}</p>
      ) : null}

      {deferred ? (
        <div className="t2-callout warn">
          <Icon name="error" fill />
          <div className="t2-callout-main">
            <p className="t2-callout-title">{T.deferredTitle}</p>
            <p className="t2-callout-body">{T.deferred[deferred] ?? deferred}</p>
          </div>
        </div>
      ) : null}

      {error ? <NoteT2 tone="danger">{error}</NoteT2> : null}

      <div className="t2-restore-push" />
      <div className="t2-restore-actions">
        <button
          type="button"
          className="t2-button primary"
          disabled={busy}
          aria-busy={busy}
          onClick={() => void restore()}
        >
          {T.restoreButton}
        </button>
        <button type="button" className="t2-button t2-quiet" disabled={busy} onClick={() => void signOut()}>
          {T.signOutButton}
        </button>
      </div>
    </div>
  );
}
