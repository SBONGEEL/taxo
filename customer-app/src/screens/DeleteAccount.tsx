/** حذفُ الحساب — **طلبٌ ثمّ مهلةُ 30 يوماً ثمّ حذفٌ حقيقي** (SPEC §59، قرارُ المالك ٢٠٢٦-٠٩-٢٩).
 *
 * حلّت محلَّ «إغلاق الحساب» الذي كان طلباً يراجعه مشرف — **وApple ترفض
 * التعليقَ بديلاً عن الحذف**. ثلاثُ خطواتٍ لا زرٌّ واحد:
 *
 * ١. **الطلب**: ما يُحذف بالاسم، وما يُحفظ ولماذا، وما يقع في المهلة.
 * ٢. **الرصيد** (إن كان): تحويلُه — حين يكون التحويلُ مفعّلاً في دولته — أو
 *    **كتابةُ المبلغ كما هو** موافقةً على ضياعه. والخلفيةُ تقارنه تحت القفل.
 * ٣. **التأكيد**: بالتاريخ، **ثمّ خروجٌ من كلِّ الأجهزة** — والعودةُ بالدخول.
 *
 * **والنصوصُ كلُّها من `lib/deletion-text.ts`** — بيتٌ واحدٌ يُراجَع.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getDeletionState, requestDeletion } from "@/api/endpoints";
import type { DeletionState } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { Field } from "@/components/ui/Field";
import { useGoBack } from "@/lib/back";
import { DELETION_TEXT as T, GRACE_DAYS, normalizeAmount } from "@/lib/deletion-text";
import { useSession } from "@/lib/session";
import { formatDateTime, formatMoney } from "@/lib/utils";

type Step = "intro" | "balance" | "confirm";

function Bullets({ items }: { items: readonly string[] }) {
  return (
    <ul className="mt-6 space-y-5">
      {items.map((item) => (
        <li key={item} className="text-11.5 leading-note text-muted">
          • {item}
        </li>
      ))}
    </ul>
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
      <div className="h-full bg-bg px-16 pt-safe">
        {error ? <ErrorNote message={error} /> : <Spinner />}
      </div>
    );
  }

  const hasBalance = Number(state.rider_balance) > 0;
  const balanceText = formatMoney(state.rider_balance, state.currency);
  const acknowledged = normalizeAmount(typed) === state.rider_balance;
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
    <div className="scr h-full bg-bg px-16 pb-nav pt-safe">
      <div className="mb-16 mt-6 flex items-center gap-10">
        <button
          type="button"
          onClick={() => (step === "intro" ? goBack() : setStep("intro"))}
          aria-label="رجوع"
          className="pressable text-18 text-muted"
        >
          →
        </button>
        <h1 className="text-20 font-bold text-ink">
          {step === "balance" ? T.balanceTitle : step === "confirm" ? T.confirmTitle : T.title}
        </h1>
      </div>

      {state.blockers.length > 0 ? (
        <section className="mb-12 rounded-18 border border-warn bg-surface p-15">
          <p className="mb-8 text-13.5 font-semibold text-warn">{T.blockedTitle}</p>
          <Bullets items={state.blockers.map((code) => T.blockers[code] ?? code)} />
        </section>
      ) : null}

      {step === "intro" ? (
        <>
          <section className="mb-12 card p-15">
            <p className="text-12 leading-note text-ink">{T.intro}</p>
            <p className="mt-14 text-13 font-bold text-ink">{T.erasedTitle}</p>
            <Bullets items={T.erased(state.is_driver)} />
            <p className="mt-14 text-13 font-bold text-ink">{T.keptTitle}</p>
            <Bullets items={T.kept} />
            <p className="mt-14 text-13 font-bold text-ink">{T.graceTitle}</p>
            <Bullets items={T.grace(state.is_driver)} />
          </section>
          <Button
            variant="danger"
            disabled={state.blockers.length > 0}
            onClick={() => setStep(hasBalance ? "balance" : "confirm")}
          >
            {T.next}
          </Button>
        </>
      ) : null}

      {step === "balance" ? (
        <>
          <p className="mb-12 text-12.5 leading-note text-ink">{T.balanceIntro(balanceText)}</p>
          {state.transfer_enabled ? (
            <section className="mb-12 card p-15">
              <p className="text-13 font-bold text-ink">{T.transferTitle}</p>
              <p className="mt-6 text-11.5 leading-note text-muted">{T.transferBody}</p>
              <Button
                className="mt-12"
                variant="secondary"
                size="sm"
                onClick={() => navigate("/wallet/transfer")}
              >
                {T.transferButton}
              </Button>
            </section>
          ) : null}
          <section className="mb-12 card p-15">
            <p className="text-13 font-bold text-ink">{T.forfeitTitle}</p>
            <div className="mt-10">
              <Field
                label={T.forfeitLabel(balanceText)}
                hint={T.forfeitHint}
                dir="ltr"
                inputMode="decimal"
                placeholder={state.rider_balance}
                value={typed}
                error={typed && !acknowledged ? T.forfeitMismatch : null}
                onChange={(event) => setTyped(event.target.value)}
              />
            </div>
          </section>
          <Button variant="danger" disabled={!acknowledged} onClick={() => setStep("confirm")}>
            {T.next}
          </Button>
        </>
      ) : null}

      {step === "confirm" ? (
        <section className="card p-15">
          <p className="text-12.5 leading-note text-ink">{T.confirmBody(dueDate)}</p>
          {hasBalance ? (
            <p className="mt-6 text-12.5 leading-note text-ink">{T.confirmForfeit(balanceText)}</p>
          ) : null}
          <p className="mt-6 text-11.5 leading-note text-muted">{T.confirmSignOut}</p>
          <div className="mt-14 flex gap-10">
            <Button variant="danger" loading={busy} onClick={() => void confirm()}>
              {T.confirmButton}
            </Button>
            <Button variant="secondary" disabled={busy} onClick={() => goBack()}>
              {T.cancelButton}
            </Button>
          </div>
        </section>
      ) : null}

      {error ? (
        <div className="mt-12">
          <ErrorNote message={error} />
        </div>
      ) : null}
    </div>
  );
}
