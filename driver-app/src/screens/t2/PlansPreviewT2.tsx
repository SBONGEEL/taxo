/** «عرض الباقات» لمن طلبُه قيد المراجعة — TAXO 2.0 «C32» (`design/t2-new/captain/C32-plans-preview.dc.html` · `C32b` · `C32c`)،
 * **في المظهرين والنسائيّ** (§٦٢-ج/٣٣). يُفتح من «عرض الباقات» في «طلبك قيد المراجعة» (C03).
 *
 * **عرضٌ بلا شراء** — والشراءُ قبل الاعتماد رفضه المالك: **لا زرَّ شراءٍ ولا اختيارَ ولا قناة**، ومكانُ زرّ C10 إطارٌ متقطّعٌ يقول
 * «يُتاح الشراءُ بعد اعتماد طلبك». **والرفضُ في الخلفية لا هنا وحدَه** (`subscriptions.require_purchasable`): زرٌّ يُضاف يوماً
 * بالخطأ لا يبيع اشتراكاً يحترق في الانتظار.
 *
 * **والخططُ كما يراها المعتمَدُ حرفاً**: `GET /subscriptions/plans` — البانِي الذي يخدم C10 نفسُه، ومعه عرضُ هذا الكبتن محسوباً —
 * **وبطاقاتُ C10 بأصنافها** (`t2-sub-plan`) بلا دائرة اختيار، **وسطرُ كلِّ خطّةٍ من بيته** (`planSubLine`). **ومن اعتُمد يُحوَّل إلى
 * «الاشتراك»** حيث يشتري — فلا تَعِده هذه الصفحةُ بما صار متاحاً.
 */

import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";

import { ApiError } from "@/api/client";
import { listSubscriptionPlans } from "@/api/endpoints";
import type { SubscriptionPlan } from "@/api/types";
import { Spinner } from "@/components/ui/Feedback";
import { useGoBack } from "@/lib/back";
import { useDriver } from "@/lib/driver";
import { CURRENCY_LABEL } from "@/lib/rideFormat";
import { digits } from "@/lib/utils";

import { planSubLine } from "./SubscriptionT2";

import "@/taxo2";
import "./t2.css";
import "./plans.css";

export function PlansPreviewT2Screen() {
  // **إلى «طلبك قيد المراجعة» من حيث جاء** — والجذرُ هو هي لمن ينتظر (`DriverHome`)
  const goBack = useGoBack("/");
  const { profile } = useDriver();
  const [plans, setPlans] = useState<SubscriptionPlan[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    listSubscriptionPlans()
      .then(setPlans)
      .catch((caught: unknown) =>
        setError(caught instanceof ApiError ? caught.message : "تعذّر قراءة الباقات"),
      )
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  // **المعتمَدُ يشتري من «الاشتراك»** — وهذه الصفحةُ تقول «بعد اعتماد طلبك» فلا تُعرض له
  if (profile?.driver.status === "approved") return <Navigate to="/subscription" replace />;

  if (loading && plans === null && error === null) {
    return (
      <div className="t2 t2-sub t2-sub-loading" aria-busy="true">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="t2 t2-sub t2-plans">
      <div className="t2-sub-scroll scr">
        <div className="t2-head">
          <button type="button" className="t2-back" aria-label="رجوع" onClick={() => goBack()}>
            <span className="t2-icon" aria-hidden="true">arrow_forward</span>
          </button>
          <h1 className="t2-title">باقات الاشتراك</h1>
        </div>

        {error ? (
          <>
            <p className="t2-note danger" role="alert">
              <span className="t2-icon" aria-hidden="true">error</span>
              {error}
            </p>
            <button type="button" className="t2-button secondary t2-plans-retry" disabled={loading} onClick={load}>
              أعد المحاولة
            </button>
          </>
        ) : null}

        {plans ? (
          <>
            {/* **العمولة بنصّ C10 المبنيّ** (التصحيحاتُ §١) — بلا نسبةٍ ولا وعدٍ مطلق */}
            <div className="t2-sub-perk">
              <span>
                <b>عمولة</b> أقل بكثير من السوق
              </span>
            </div>

            {plans.length > 0 ? (
              <>
                <h2 className="t2-section">الباقات</h2>
                {/* **صفوفُ C10 بلا دائرة اختيار** — عرضٌ لا زرّ: لا اختيارَ حيث لا شراء */}
                <ul className="t2-sub-plans t2-plans-list" aria-label="الباقات">
                  {plans.map((row) => (
                    <li key={row.id} className="t2-sub-plan view">
                      <span className="t2-sub-plan-main">
                        <span className="t2-sub-plan-name">{row.name}</span>
                        <span className={row.offer_name ? "t2-sub-plan-sub ok" : "t2-sub-plan-sub"}>
                          {planSubLine(row)}
                        </span>
                      </span>
                      <span className="t2-sub-price">
                        {/* **المشطوبُ بجانب المخفَّض** — والمخفَّضُ من الخلفية، فلا طرحَ هنا (§14). **ولا شطبَ بلا عرض**،
                            والمرسومُ ما يُخصم (`price_to_pay`، SPEC §٧٠-ج/٥) */}
                        {row.price_after_discount ? <span className="t2-sub-was">{digits(row.price)}</span> : null}
                        <span className="t2-sub-num" dir="ltr">
                          {digits(row.price_to_pay ?? row.price)}
                        </span>{" "}
                        <span className="t2-sub-cur">{CURRENCY_LABEL[row.currency]}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              // **لا خطّةَ مفعَّلةً في سوقه** — جملةٌ واحدة، ولا إطارَ «يُتاح الشراء» فوق لا شيء (C32b)
              <p className="t2-empty t2-plans-empty">لا باقات معروضة في سوقك الآن.</p>
            )}
          </>
        ) : null}
      </div>

      {/* **مكانُ زرّ C10 إطارٌ متقطّعٌ لا زرّ** — لغةُ الهوية لما لم يُتَح بعد، بساعة C03 الرملية */}
      {plans && plans.length > 0 ? (
        <div className="t2-sub-foot">
          <p className="t2-plans-later">
            <span className="t2-icon" aria-hidden="true">hourglass_top</span>
            يُتاح الشراءُ بعد اعتماد طلبك
          </p>
        </div>
      ) : null}
    </div>
  );
}
