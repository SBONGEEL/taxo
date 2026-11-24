/** **«عروضي»** (أمرُ المالك ٢٠٢٦-١١-٢٤ السادس، SPEC §١١٤-د) — عروضٌ تنطبق بلا رمز، وكوبوناتُ المحلّات الشريكة، وشارةُ «راكب مميّز».
 *
 * **الأرقامُ كما تصل** من `GET /rider-offers`؛ **وعرضٌ بلا قيمةٍ مضبوطةٍ لا يصل أصلاً** — فلا يرى الراكبُ رقماً لم يقرّه المالك.
 * وزرُّ المحفظة لا يُرسم حيث لا شيءَ يُعرض.
 */

import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getMyRiderOffers, type MyRiderOffers } from "@/api/endpoints";
import { useGoBack } from "@/lib/back";
import { tr } from "@/lib/i18n";
import { DISPLAY_LOCALE, digits, formatAmount } from "@/lib/utils";
import "./support.css";
import { Icon } from "@/taxo2";

function useRiderOffers(): MyRiderOffers | null {
  const [data, setData] = useState<MyRiderOffers | null>(null);
  useEffect(() => {
    getMyRiderOffers()
      .then(setData)
      .catch(() => undefined);
  }, []);
  return data;
}

function hasAnything(data: MyRiderOffers | null): boolean {
  return data !== null && (data.premium || data.offers.length > 0 || data.coupons.length > 0 || data.premium_after_rides !== null);
}

export function RiderOffersButton() {
  const navigate = useNavigate();
  const data = useRiderOffers();
  if (!hasAnything(data)) return null;
  return (
    <button type="button" className="t2-btn ghost" onClick={() => navigate("/offers")}>
      <Icon name="confirmation_number" />
      {tr("عروضي")}
    </button>
  );
}

export function RiderOffersT2() {
  const goBack = useGoBack();
  const data = useRiderOffers();

  return (
    <div className="sp-page">
      <div className="t2-head">
        <button type="button" className="t2-back" aria-label={tr("رجوع")} onClick={goBack}>
          <Icon name="arrow_forward" />
        </button>
        <h1 className="t2-title">{tr("عروضي")}</h1>
      </div>
      <div className="sp-body">
        {data === null ? null : !hasAnything(data) ? (
          <p className="sp-hint">{tr("لا عروض الآن.")}</p>
        ) : (
          <>
            {data.premium ? (
              <div className="sp-card" data-testid="premium-badge">
                <span className="sp-label">{tr("راكب مميّز")}</span>
                <p className="sp-hint">{tr("أولويّةٌ في المطابقة مع الكباتن.")}</p>
              </div>
            ) : data.premium_after_rides !== null ? (
              <div className="sp-card">
                <span className="sp-label">{tr("راكب مميّز")}</span>
                <p className="sp-hint">
                  {tr("بعد {0} رحلة مكتملة — أكملت {1}", {
                    0: digits(String(data.premium_after_rides)),
                    1: digits(String(data.completed_rides)),
                  })}
                </p>
              </div>
            ) : null}
            {data.free_cancel_seconds ? (
              <div className="sp-card">
                <span className="sp-label">{tr("إلغاءٌ مجّانيّ")}</span>
                <p className="sp-hint">
                  {tr("خلال {0} دقيقة من الطلب", { 0: digits(String(Math.round(data.free_cancel_seconds / 60))) })}
                </p>
              </div>
            ) : null}
            {data.offers.map((offer) => (
              <div key={offer.kind} className="sp-card">
                <span className="sp-label">{offer.label}</span>
                <p className="sp-hint">
                  {offer.discount_type === "percent"
                    ? tr("خصم {0}٪", { 0: digits(offer.discount_value) })
                    : tr("خصم {0}", { 0: formatAmount(offer.discount_value, null) })}
                  {offer.max_discount ? ` · ${tr("حتى {0}", { 0: formatAmount(offer.max_discount, null) })}` : ""}
                  {" · "}
                  {tr("يُطبَّق تلقائيّاً — ولا يجتمع مع رمزٍ آخر")}
                </p>
              </div>
            ))}
            {data.coupons.length > 0 ? <h2 className="sp-label">{tr("كوبونات المحلّات الشريكة")}</h2> : null}
            {data.coupons.map((coupon) => (
              <div key={coupon.id} className="sp-card" data-testid="partner-coupon">
                <span className="sp-label">
                  {coupon.shop_name}
                  {coupon.shop_area ? ` · ${coupon.shop_area}` : ""}
                </span>
                <p className="sp-hint">{coupon.title}</p>
                {coupon.details ? <p className="sp-hint">{coupon.details}</p> : null}
                {coupon.coupon_code ? (
                  <p className="sp-hint" dir="ltr">
                    {coupon.coupon_code}
                  </p>
                ) : null}
                {coupon.valid_until ? (
                  <p className="sp-hint">
                    {tr("حتى {0}", { 0: digits(new Date(coupon.valid_until).toLocaleDateString(DISPLAY_LOCALE)) })}
                  </p>
                ) : null}
                <p className="sp-hint">{tr("الخصمُ على المحلّ لا على TAXO.")}</p>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
