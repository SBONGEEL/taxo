/** حذفُ الحساب — TAXO 2.0 «R27» (`design/t2-new/rider/R27-delete-account.dc.html` · `R27b-…` · `R27c-…`)، **في المظهرين
 *  والنسائيّ** — **طلبٌ ثمّ مهلةُ 30 يوماً ثمّ حذفٌ حقيقي** (SPEC §59، قرارُ المالك ٢٠٢٦-٠٩-٢٩).
 *
 * حلّت محلَّ «إغلاق الحساب» الذي كان طلباً يراجعه مشرف — **وApple ترفض
 * التعليقَ بديلاً عن الحذف**. ثلاثُ خطواتٍ لا زرٌّ واحد:
 *
 * ١. **الطلب**: ما يُحذف بالاسم، وما يُحفظ ولماذا، وما يقع في المهلة.
 * ٢. **الرصيد** (إن كان): تحويلُه — حين يكون التحويلُ مفعّلاً في دولته — أو
 *    **كتابةُ المبلغ كما هو** موافقةً على ضياعه. والخلفيةُ تقارنه تحت القفل.
 * ٣. **التأكيد**: بالتاريخ، **ثمّ خروجٌ من كلِّ الأجهزة** — والعودةُ بالدخول.
 *
 * **والنصوصُ كلُّها من `lib/deletion-text.ts`** — بيتٌ واحدٌ يُراجَع. **والخطواتُ والطلباتُ وقواعدُها هي هي حرفاً** —
 * **وتأكيدُ المال باقٍ كما هو** (كتابةُ المبلغ ثمّ خطوةُ التأكيد)؛ وما تغيّر طبقةُ العرض: بطاقاتُ R15، وما يُحذف وما يُحفظ
 * بأيقونات معناه، **وأزرارُ الخطر بالأحمر** لما لا رجعةَ فيه.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getDeletionState, requestDeletion } from "@/api/endpoints";
import type { DeletionState } from "@/api/types";
import { useGoBack } from "@/lib/back";
import { DELETION_TEXT as T, GRACE_DAYS, normalizeAmount } from "@/lib/deletion-text";
import { useSession } from "@/lib/session";
import { formatDateTime, formatMoney } from "@/lib/utils";
import { LoaderT2, NoteT2, SubHeadT2 } from "@/screens/t2/KitT2";
import { AuthBlock, AuthInput, Icon } from "@/taxo2";

import "@/screens/t2/t2.css";
import "@/screens/t2/account.css";

type Step = "intro" | "balance" | "confirm";

/** قائمةٌ بأيقونة معناها — الحذفُ بالأحمر، والمحفوظُ بالخافت، والمهلةُ بالتنبيه. */
function Points({
  title,
  items,
  icon,
  tone,
}: {
  title: string;
  items: readonly string[];
  icon: string;
  tone: "danger" | "muted" | "warn";
}) {
  return (
    <>
      <p className="t2-del-h">{title}</p>
      <ul className={`t2-del-points ${tone}`}>
        {items.map((item) => (
          <li key={item}>
            <Icon name={icon} />
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </>
  );
}

export function DeleteAccountScreen() {
  const goBack = useGoBack("/account");
  const navigate = useNavigate();
  const { signOut } = useSession();
  const [state, setState] = useState<DeletionState | null>(null);
  const [step, setStep] = useState<Step>("intro");
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    getDeletionState()
      .then(setState)
      .catch((caught) =>
        setError(caught instanceof ApiError ? caught.message : "تعذّر التحميل"),
      );
  }, []);

  useEffect(load, [load]);

  if (!state) {
    return (
      <div className="t2 t2-page pb-nav">
        <SubHeadT2 title={T.title} onBack={goBack} />
        {error ? <NoteT2 tone="danger">{error}</NoteT2> : <LoaderT2 />}
      </div>
    );
  }

  const hasBalance = Number(state.rider_balance) > 0;
  const balanceText = formatMoney(state.rider_balance, state.currency);
  const acknowledged = normalizeAmount(typed) === state.rider_balance;
  const mismatch = typed && !acknowledged ? T.forfeitMismatch : null;
  const dueDate = formatDateTime(
    new Date(Date.now() + GRACE_DAYS * 24 * 60 * 60 * 1000).toISOString(),
  );

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await requestDeletion(hasBalance ? (normalizeAmount(typed) ?? undefined) : undefined);
      // **الخلفيةُ ألغت الجلسات كلَّها** — والعودةُ بالدخول إلى شاشة الاستعادة
      await signOut();
      navigate("/login", { replace: true });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "تعذّر التنفيذ");
      load();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="t2 t2-page pb-nav">
      <SubHeadT2
        title={step === "balance" ? T.balanceTitle : step === "confirm" ? T.confirmTitle : T.title}
        onBack={() => (step === "intro" ? goBack() : setStep("intro"))}
      />

      {/* **قائمةٌ لا أوّلُ سبب**: من أزال مانعاً ثم صُدم بثانٍ يقرأ الرفضَ مماطلة */}
      {state.blockers.length > 0 ? (
        <div className="t2-callout warn">
          <Icon name="error" fill />
          <div className="t2-callout-main">
            <p className="t2-callout-title">{T.blockedTitle}</p>
            <ul className="t2-del-blockers">
              {state.blockers.map((code) => (
                <li key={code}>{T.blockers[code] ?? code}</li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}

      {step === "intro" ? (
        <>
          <section className="t2-del-card">
            <p className="t2-del-lead">{T.intro}</p>
            <Points title={T.erasedTitle} items={T.erased(state.is_driver)} icon="delete" tone="danger" />
            <Points title={T.keptTitle} items={T.kept} icon="inventory_2" tone="muted" />
            <Points title={T.graceTitle} items={T.grace(state.is_driver)} icon="schedule" tone="warn" />
          </section>
          <button
            type="button"
            className="t2-button t2-destroy t2-wide t2-del-next"
            disabled={state.blockers.length > 0}
            onClick={() => setStep(hasBalance ? "balance" : "confirm")}
          >
            {T.next}
          </button>
        </>
      ) : null}

      {step === "balance" ? (
        <>
          <p className="t2-del-lead out">{T.balanceIntro(balanceText)}</p>
          {state.transfer_enabled ? (
            <section className="t2-del-card t2-del-row">
              <span className="t2-badge">
                <Icon name="sync_alt" />
              </span>
              <div className="t2-del-grow">
                <p className="t2-del-title">{T.transferTitle}</p>
                <p className="t2-del-body">{T.transferBody}</p>
                <button type="button" className="t2-cbtn soft full" onClick={() => navigate("/wallet/transfer")}>
                  {T.transferButton}
                </button>
              </div>
            </section>
          ) : null}
          <section className="t2-del-card">
            <p className="t2-del-title">{T.forfeitTitle}</p>
            {/* **سببُ الخطأ تحت حقله** (§٦٢/٢٠) — والتلميحُ مكانَه حين لا خطأ */}
            <AuthBlock label={T.forfeitLabel(balanceText)} htmlFor="forfeit" error={mismatch} hint={T.forfeitHint}>
              <AuthInput
                id="forfeit"
                dir="ltr"
                inputMode="decimal"
                placeholder={state.rider_balance}
                value={typed}
                invalid={Boolean(mismatch)}
                onChange={(event) => setTyped(event.target.value)}
              />
            </AuthBlock>
          </section>
          <button
            type="button"
            className="t2-button t2-destroy t2-wide t2-del-next"
            disabled={!acknowledged}
            onClick={() => setStep("confirm")}
          >
            {T.next}
          </button>
        </>
      ) : null}

      {step === "confirm" ? (
        <>
          <section className="t2-del-card">
            <span className="t2-del-mark">
              <Icon name="event_busy" />
            </span>
            <p className="t2-del-strong">{T.confirmBody(dueDate)}</p>
            {hasBalance ? <p className="t2-del-line">{T.confirmForfeit(balanceText)}</p> : null}
            <p className="t2-del-fine">{T.confirmSignOut}</p>
          </section>
          <div className="t2-del-actions">
            <button
              type="button"
              className="t2-button t2-destroy"
              disabled={busy}
              aria-busy={busy}
              onClick={() => void confirm()}
            >
              {T.confirmButton}
            </button>
            <button type="button" className="t2-button t2-quiet" disabled={busy} onClick={() => goBack()}>
              {T.cancelButton}
            </button>
          </div>
        </>
      ) : null}

      {error ? <NoteT2 tone="danger">{error}</NoteT2> : null}
    </div>
  );
}
