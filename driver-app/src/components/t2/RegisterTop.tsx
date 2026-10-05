/** رأسُ «إنشاء حساب كبتن» وخطواتُه الثلاث — **C02 كما رُسمت** (Claude Design «TAXO 2.0 - Captain»): رجوعٌ دائريٌّ والعنوان،
 * ثمّ «الحساب · المركبة · الوثائق» — **المنتهيةُ خضراءُ بعلامة، والحاليّةُ برقمها على الجمر**، والتي لم تُبلَغ (لم تُرسم)
 * بحلقة «خطوةٍ لم تُبلَغ» من C03. وتخطيطُها في `captain-auth.css`.
 *
 * **والرجوعُ يُرسم حيث له وجهةٌ وحدَها**: «المركبة» بعد فتح الحساب لا خطوةَ قبلها تُعاد — وزرٌّ لا يفعل شيئاً أسوأُ من غيابه.
 */
import { Fragment } from "react";

import { Icon } from "@/taxo2";

const STEPS = ["الحساب", "المركبة", "الوثائق"] as const;

export function RegisterTop({ step, onBack }: { step: 1 | 2 | 3; onBack?: () => void }) {
  return (
    <>
      <div className="cap-head">
        {onBack ? (
          <button type="button" className="t2-auth-back" onClick={onBack} aria-label="رجوع">
            <Icon name="arrow_forward" />
          </button>
        ) : null}
        <h1 className="cap-head-title">إنشاء حساب كبتن</h1>
      </div>

      <div className="cap-steps" role="list" aria-label="خطوات إنشاء الحساب">
        {STEPS.map((label, index) => {
          const number = index + 1;
          const state = number < step ? "done" : number === step ? "now" : "next";
          return (
            <Fragment key={label}>
              {index > 0 ? <span className={`cap-steps-line ${state}`} aria-hidden="true" /> : null}
              <div className={`cap-step ${state}`} role="listitem" aria-current={state === "now" ? "step" : undefined}>
                <span className="cap-step-dot" aria-hidden="true">
                  {state === "done" ? <Icon name="check" /> : <span dir="ltr">{number}</span>}
                </span>
                <span className="cap-step-label">
                  {label}
                  {state === "done" ? <span className="cap-sr"> — تمّت</span> : null}
                </span>
              </div>
            </Fragment>
          );
        })}
      </div>
    </>
  );
}
