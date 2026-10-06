/** حذفُ الحساب — **طلبٌ ثمّ مهلةُ 30 يوماً ثمّ حذفٌ حقيقي** (SPEC §59، قرارُ المالك ٢٠٢٦-٠٩-٢٩).
 *
 * حلّت محلَّ «إلغاء تفعيل الحساب» الذي كان طلباً يراجعه مشرف. **والكبتنُ
 * يخرج من التوزيع لحظةَ الطلب، ويسحب رصيدَه في المهلة** — ولا يُحذف حسابٌ فيه
 * رصيد (يُؤجَّل ويُنبَّه المشرف). **ومن يحمل محفظةَ راكبٍ فيها رصيد** يُقرّ
 * بضياعه كتابةً كما في تطبيق الراكب — والتحويلُ من تطبيق الراكب وحدَه.
 *
 * **والنصوصُ كلُّها من `lib/deletion-text.ts`** — نسخةٌ حرفيّةٌ من تطبيق الراكب.
 *
 * **بلغة TAXO 2.0** «C26» (`design/t2-new/captain/C26*.dc.html`): أقسامُ «ما يُحذف · ما يُحفظ · خلال المهلة» بمربّعات «C12»
 * ونقاط، والفعلُ في ذيلٍ مثبَّتٍ (C10) **أحمرُ** لأنه يمضي إلى حذف. **والمنطقُ حرفاً**: الخطواتُ الثلاث وشروطُ تعطيلها،
 * والإقرارُ بالمبلغ كتابةً، والنداءُ ثمّ الخروجُ ثمّ الدخول.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getDeletionState, requestDeletion } from "@/api/endpoints";
import type { DeletionState } from "@/api/types";
import { useGoBack } from "@/lib/back";
import { DELETION_TEXT as T, GRACE_DAYS, normalizeAmount } from "@/lib/deletion-text";
import { useSession } from "@/lib/session";
import { DISPLAY_LOCALE, currencyLabel, digits } from "@/lib/utils";
import { Icon } from "@/taxo2";

import "@/screens/t2/account.css";

type Step = "intro" | "balance" | "confirm";

const DATE = new Intl.DateTimeFormat(DISPLAY_LOCALE, { dateStyle: "medium", timeStyle: "short" });

export function formatDue(iso: string): string {
  return digits(DATE.format(new Date(iso)));
}

export function moneyText(amount: string, currency: string): string {
  return `${digits(amount)} ${currencyLabel(currency)}`;
}

/** نقاطُ القسم — **نقطةٌ صغيرةٌ بلون الخافت** قبل كلِّ سطر (`::before`). */
function Bullets({ items }: { items: readonly string[] }) {
  return (
    <ul className="t2-del-bullets">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

/** قسمٌ بمربّع أيقونته وعنوانه ونقاطه. */
function Block({
  icon,
  tone,
  title,
  items,
}: {
  icon: string;
  tone: string;
  title: string;
  items: readonly string[];
}) {
  return (
    <section className="t2-del-block">
      <h2 className="t2-del-block-head">
        <span className={`t2-ax-tile sm ${tone}`} aria-hidden="true">
          <Icon name={icon} />
        </span>
        {title}
      </h2>
      <Bullets items={items} />
    </section>
  );
}

export function DeleteAccountScreen() {
  const goBack = useGoBack();
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

  const header = (
    <div className="t2-head">
      <button
        type="button"
        className="t2-back"
        aria-label="رجوع"
        onClick={() => (step === "intro" ? goBack() : setStep("intro"))}
      >
        <Icon name="arrow_forward" />
      </button>
      <h1 className="t2-title">
        {step === "balance" ? T.balanceTitle : step === "confirm" ? T.confirmTitle : T.title}
      </h1>
    </div>
  );

  const errorNote = error ? (
    <p className="t2-note danger" role="alert">
      <Icon name="error" />
      {error}
    </p>
  ) : null;

  if (!state) {
    return (
      <div className="t2 t2-ax t2-del">
        <div className="t2-ax-scroll">
          {header}
          {error ? (
            errorNote
          ) : (
            <div className="t2-ax-center">
              <span className="t2-ax-spin" role="status" aria-label="جارٍ التحميل" />
            </div>
          )}
        </div>
      </div>
    );
  }

  const hasBalance = Number(state.rider_balance) > 0;
  const balanceText = moneyText(state.rider_balance, state.currency);
  const acknowledged = normalizeAmount(typed) === state.rider_balance;
  const dueDate = formatDue(new Date(Date.now() + GRACE_DAYS * 24 * 60 * 60 * 1000).toISOString());
  const mismatch = Boolean(typed) && !acknowledged;

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await requestDeletion(hasBalance ? (normalizeAmount(typed) ?? undefined) : undefined);
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
    <div className="t2 t2-ax t2-del">
      <div className="t2-ax-scroll has-foot">
        {header}

        {/* **الموانعُ قائمةٌ لا أوّلُ سبب** — بلاغُ النظام (`t2-callout warn`) والفعلُ معطَّلٌ تحته */}
        {state.blockers.length > 0 ? (
          <section className="t2-callout warn" role="alert">
            <Icon name="info" fill />
            <div className="t2-callout-main">
              <p className="t2-callout-title">{T.blockedTitle}</p>
              <Bullets items={state.blockers.map((code) => T.blockers[code] ?? code)} />
            </div>
          </section>
        ) : null}

        {step === "intro" ? (
          <>
            <p className="t2-ax-card t2-del-intro">{T.intro}</p>
            <div className="t2-del-blocks">
              <Block icon="delete" tone="danger" title={T.erasedTitle} items={T.erased(state.is_driver)} />
              <Block icon="inventory_2" tone="" title={T.keptTitle} items={T.kept} />
              <Block icon="schedule" tone="warn" title={T.graceTitle} items={T.grace(state.is_driver)} />
            </div>
          </>
        ) : null}

        {step === "balance" ? (
          <>
            <p className="t2-del-lead">{T.balanceIntro(balanceText)}</p>
            {state.transfer_enabled ? (
              <section className="t2-ax-card">
                <h2 className="t2-del-block-head">
                  <span className="t2-ax-tile sm" aria-hidden="true">
                    <Icon name="swap_horiz" />
                  </span>
                  {T.transferTitle}
                </h2>
                <p className="t2-del-text">{T.transferElsewhere}</p>
              </section>
            ) : null}
            <section className="t2-ax-card">
              <h2 className="t2-del-block-head">
                <span className="t2-ax-tile sm danger" aria-hidden="true">
                  <Icon name="delete" />
                </span>
                {T.forfeitTitle}
              </h2>
              <label className="t2-ax-label" htmlFor="t2-del-forfeit">
                {T.forfeitLabel(balanceText)}
              </label>
              <input
                id="t2-del-forfeit"
                className="t2-ax-field t2-del-field"
                dir="ltr"
                inputMode="decimal"
                placeholder={state.rider_balance}
                value={typed}
                aria-invalid={mismatch || undefined}
                aria-describedby={mismatch ? "t2-del-forfeit-error" : "t2-del-forfeit-hint"}
                onChange={(event) => setTyped(event.target.value)}
              />
              {/* **سببُ الخطأ تحت حقله** (§٦٢/٢٠) */}
              {mismatch ? (
                <p className="t2-note danger" id="t2-del-forfeit-error" role="alert">
                  <Icon name="error" />
                  {T.forfeitMismatch}
                </p>
              ) : null}
              <p className="t2-ax-hint" id="t2-del-forfeit-hint">
                {T.forfeitHint}
              </p>
            </section>
          </>
        ) : null}

        {step === "confirm" ? (
          <section className="t2-ax-card t2-del-confirm">
            <span className="t2-del-confirm-icon" aria-hidden="true">
              <Icon name="delete" />
            </span>
            <p className="t2-del-confirm-body">{T.confirmBody(dueDate)}</p>
            {hasBalance ? (
              <p className="t2-del-confirm-more">{T.confirmForfeit(balanceText)}</p>
            ) : null}
            <p className="t2-del-confirm-out">{T.confirmSignOut}</p>
          </section>
        ) : null}

        {errorNote}
      </div>

      <div className="t2-ax-foot">
        {step === "intro" ? (
          <button
            type="button"
            className="t2-ax-danger"
            disabled={state.blockers.length > 0}
            onClick={() => setStep(hasBalance ? "balance" : "confirm")}
          >
            {T.next}
          </button>
        ) : null}
        {step === "balance" ? (
          <button
            type="button"
            className="t2-ax-danger"
            disabled={!acknowledged}
            onClick={() => setStep("confirm")}
          >
            {T.next}
          </button>
        ) : null}
        {step === "confirm" ? (
          <div className="t2-ax-pair">
            <button
              type="button"
              className="t2-ax-danger"
              disabled={busy}
              onClick={() => void confirm()}
            >
              {busy ? "…" : T.confirmButton}
            </button>
            <button
              type="button"
              className="t2-ax-ghost"
              disabled={busy}
              onClick={() => goBack()}
            >
              {T.cancelButton}
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
