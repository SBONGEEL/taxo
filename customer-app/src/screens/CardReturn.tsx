/** العودة من صفحة الدفع المستضافة (SPEC القسم 6.4).
 *
 * **الاستعلامُ شريكُ الإشعار لا احتياطُه**: أيُّهما وصل أولاً سوّى، والآخر
 * يجد الطلب محسوماً فلا يقيّد شيئاً ولا يرتدّ بخطأ. فهذه الشاشة تسأل
 * `GET /payments/card/orders/{cart_id}` ولا تفترض شيئاً عمّا حدث.
 *
 * و«لا تخمين على غير محسوم»: طلبٌ ما زال `created` يبقى معلّقاً — لا يُعرض
 * نجاحاً ولا فشلاً، وتُعاد المحاولة بضغطة.
 */

import { CheckCircle2, RefreshCw, XCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "@/api/client";
import { getCardOrder } from "@/api/endpoints";
import type { CardOrder } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { ErrorNote, Spinner } from "@/components/ui/Feedback";
import { Screen } from "@/components/ui/Screen";
import { formatMoney } from "@/lib/utils";

export function CardReturnScreen() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const cartId = params.get("cart_id") ?? params.get("cartid") ?? "";
  const rideId = sessionStorage.getItem("taxo.card_return_ride");

  const [order, setOrder] = useState<CardOrder | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const check = useCallback(async () => {
    if (!cartId) {
      setError("لا معرّف عملية في الرابط — افتح شاشة الدفع مجدداً.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setOrder(await getCardOrder(cartId));
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "تعذّر الاستعلام عن حال الدفع",
      );
    } finally {
      setLoading(false);
    }
  }, [cartId]);

  useEffect(() => {
    void check();
  }, [check]);

  const back = () => navigate(rideId ? `/rides/${rideId}/pay` : "/wallet", { replace: true });

  return (
    <Screen title="نتيجة الدفع" back={false}>
      {loading ? (
        <Spinner label="نسأل المزود عن حال العملية…" />
      ) : (
        <div className="space-y-20">
          <ErrorNote message={error} />

          {order?.status === "paid" ? (
            <div className="card flex flex-col items-center gap-8 p-24 text-center">
              <CheckCircle2 className="size-40 text-ok" />
              <p className="text-18 font-semibold text-ink">تم الدفع</p>
              <p className="text-muted">{formatMoney(order.amount, order.currency)}</p>
            </div>
          ) : order?.status === "failed" || order?.status === "cancelled" ? (
            <div className="card flex flex-col items-center gap-8 p-24 text-center">
              <XCircle className="size-40 text-danger" />
              <p className="text-18 font-semibold text-ink">لم تكتمل العملية</p>
              <p className="text-14 text-muted">
                {order.failure_reason ?? "يمكنك المحاولة بقناة أخرى."}
              </p>
            </div>
          ) : order ? (
            <div className="card space-y-12 p-24 text-center">
              <RefreshCw className="mx-auto size-32 text-muted" />
              <p className="font-semibold text-ink">العملية قيد المعالجة</p>
              <p className="text-14 text-muted">
                لم يحسمها المزود بعد. لا نعدّها مدفوعةً ولا ساقطة — أعد الاستعلام بعد
                لحظات.
              </p>
              <Button variant="secondary" onClick={check}>
                أعد الاستعلام
              </Button>
            </div>
          ) : null}

          <Button size="lg" onClick={back}>
            متابعة
          </Button>
        </div>
      )}
    </Screen>
  );
}
