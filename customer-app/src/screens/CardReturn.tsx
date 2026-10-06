/** العودة من صفحة الدفع المستضافة (SPEC القسم 6.4).
 *
 * **الاستعلامُ شريكُ الإشعار لا احتياطُه**: أيُّهما وصل أولاً سوّى، والآخر
 * يجد الطلب محسوماً فلا يقيّد شيئاً ولا يرتدّ بخطأ. فهذه الشاشة تسأل
 * `GET /payments/card/orders/{cart_id}` ولا تفترض شيئاً عمّا حدث.
 *
 * و«لا تخمين على غير محسوم»: طلبٌ ما زال `created` يبقى معلّقاً — لا يُعرض
 * نجاحاً ولا فشلاً، وتُعاد المحاولة بضغطة.
 *
 * **بلغة TAXO 2.0** (لوحاتُ `design/t2-new/rider/R20` · `R20b` · `R20c`): طبقةٌ بلا شريطٍ ولا رجوع — علامةُ R10 مكبَّرةً في القلب
 * بنبرة الحال (نجاحٌ · خطأٌ · محايد)، و«متابعة» في القاع. **والنداءُ والوجهتان والصوتُ حرفاً.**
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getCardOrder } from "@/api/endpoints";
import type { CardOrder } from "@/api/types";
import { isUnlocked, play } from "@/lib/sound";
import { currencyLabel, formatMoney } from "@/lib/utils";
import { Icon } from "@/taxo2";
import { BannerT2, HeadT2, WaitT2 } from "@/screens/t2/MoneyT2";

export function CardReturnScreen() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const cartId = params.get("cart_id") ?? params.get("cartid") ?? "";
  const rideId = sessionStorage.getItem("taxo.card_return_ride");

  const [order, setOrder] = useState<CardOrder | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  /** **نغمةُ النجاح مرّةً واحدة** — «أعد الاستعلام» على طلبٍ محسومٍ لا يعيدها. */
  const announced = useRef(false);

  const check = useCallback(async () => {
    if (!cartId) {
      setError("لا معرّف عملية في الرابط — افتح شاشة الدفع مجدداً.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const next = await getCardOrder(cartId);
      setOrder(next);
      // **«نجح دفعٌ أو شحن»** (§٦١-ي/١٠) — والعودةُ من صفحة المزود تحميلٌ جديد،
      // فلا صوتَ قبل أوّل لمسة (`unlock`): **لا يُحسب مُعلَناً ما لم يُسمع**، فيُسمع
      // في الاستعلام التالي بعد لمسة
      if (next.status === "paid" && !announced.current && isUnlocked()) {
        announced.current = true;
        play(rideId ? "paid" : "topup");
      }
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر الاستعلام عن حال الدفع",
      );
    } finally {
      setLoading(false);
    }
  }, [cartId, rideId]);

  useEffect(() => {
    void check();
  }, [check]);

  const back = () => navigate(rideId ? `/rides/${rideId}/pay` : "/wallet", { replace: true });

  return (
    <div className="t2 t2-m-stage">
      <HeadT2 title="نتيجة الدفع" />

      {loading ? (
        <div className="t2-m-result">
          <WaitT2 label="نسأل المزود عن حال العملية…" />
        </div>
      ) : (
        <>
          <BannerT2 tone="danger" message={error} />

          {order?.status === "paid" ? (
            <div className="t2-m-result">
              <span className="t2-m-result-mark ok" aria-hidden="true">
                <Icon name="check" />
              </span>
              <p className="t2-m-result-title">تم الدفع</p>
              <div className="t2-m-result-amount">
                <span dir="ltr" className="t2-m-num md">
                  {formatMoney(order.amount)}
                </span>
                <span className="t2-m-cur">{currencyLabel(order.currency)}</span>
              </div>
            </div>
          ) : order?.status === "failed" || order?.status === "cancelled" ? (
            <div className="t2-m-result">
              <span className="t2-m-result-mark danger" aria-hidden="true">
                <Icon name="close" />
              </span>
              <p className="t2-m-result-title">لم تكتمل العملية</p>
              <p className="t2-m-result-text">{order.failure_reason ?? "يمكنك المحاولة بقناة أخرى."}</p>
            </div>
          ) : order ? (
            <div className="t2-m-result">
              <span className="t2-m-result-mark" aria-hidden="true">
                <Icon name="hourglass_top" />
              </span>
              <p className="t2-m-result-title sm">العملية قيد المعالجة</p>
              <p className="t2-m-result-text">
                لم يحسمها المزود بعد. لا نعدّها مدفوعةً ولا ساقطة — أعد الاستعلام بعد
                لحظات.
              </p>
              <button type="button" className="t2-button secondary t2-m-again" onClick={check}>
                <Icon name="refresh" />
                أعد الاستعلام
              </button>
            </div>
          ) : (
            <div className="t2-m-push" />
          )}

          <button type="button" className="t2-button primary t2-m-cta" onClick={back}>
            متابعة
          </button>
        </>
      )}
    </div>
  );
}
